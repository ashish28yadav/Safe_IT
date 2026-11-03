"""Incident ingestion, lifecycle, idempotency, and correlation service."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

from incident_agent.simulator.environment import InfrastructureManager
from incident_agent.storage.database import Database
from incident_agent.storage.repository import (ConcurrentIncidentUpdate, DuplicateIncidentRecord,
                                               IdempotencyKeyConflict, IncidentRepository)

from .classification import SeverityClassifier
from .models import (Incident, IncidentHistoryEntry, IncidentSeverity, IncidentStatus,
                     RawAlert)


class DuplicateIncidentError(ValueError):
    """Raised when a caller reuses an incident ID already in storage."""


class IdempotencyConflictError(ValueError):
    """Raised when an idempotency key is reused for a different alert."""


class InvalidIncidentTransition(ValueError):
    """Raised when a requested incident status transition is not allowed."""


class IncidentRegistry:
    TRANSITIONS = {
        IncidentStatus.OPEN: {IncidentStatus.INVESTIGATING},
        IncidentStatus.INVESTIGATING: {IncidentStatus.MITIGATING, IncidentStatus.RESOLVED},
        IncidentStatus.MITIGATING: {IncidentStatus.INVESTIGATING, IncidentStatus.RESOLVED},
        IncidentStatus.RESOLVED: {IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED},
        IncidentStatus.CLOSED: set(),
    }
    DEFAULT_CORRELATED_PAIRS = {
        frozenset({"payment-service", "postgres-database"}),
    }

    def __init__(self, infrastructure: InfrastructureManager, *,
                 correlation_window: timedelta = timedelta(minutes=5),
                 classifier: SeverityClassifier | None = None,
                 database: Database | None = None) -> None:
        self.infrastructure = infrastructure
        self.correlation_window = correlation_window
        self.classifier = classifier or SeverityClassifier()
        self.database = database or Database()
        self.repository = IncidentRepository(self.database)
        self._lock = RLock()

    @staticmethod
    def _fingerprint(alert: RawAlert, service_name: str, affected_services: list[str]) -> str:
        payload = alert.model_dump(mode="json", exclude={
            "incident_id", "idempotency_key", "created_at",
        })
        payload["service_name"] = service_name
        payload["affected_services"] = affected_services
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def create(self, alert: RawAlert) -> Incident:
        with self._lock:
            try:
                service_name = self.infrastructure.resolve_service_name(alert.service_name)
                affected_services = list(dict.fromkeys(
                    self.infrastructure.resolve_service_name(name)
                    for name in (alert.affected_services or [service_name])
                ))
            except ValueError as exc:
                raise ValueError(str(exc)) from exc

            fingerprint = self._fingerprint(alert, service_name, affected_services)
            if alert.idempotency_key:
                previous = self.repository.find_by_idempotency_key(alert.idempotency_key)
                if previous:
                    if previous[1] == fingerprint:
                        return previous[0]
                    raise IdempotencyConflictError(
                        "Idempotency key was already used for a different alert"
                    )

            now = datetime.now(timezone.utc)
            created_at = alert.created_at or now
            if created_at > now + timedelta(minutes=5):
                raise ValueError("created_at cannot be more than five minutes in the future")
            incident_id = alert.incident_id or f"inc-{uuid4()}"
            correlation_id = alert.correlation_id or f"corr-{uuid4()}"
            incident = Incident(
                incident_id=incident_id, title=alert.title.strip(), description=alert.description,
                service_name=service_name, severity=self.classifier.classify(alert),
                alert_type=alert.alert_type, status=IncidentStatus.OPEN,
                created_at=created_at, updated_at=now,
                affected_services=affected_services, metrics_snapshot=dict(alert.metrics_snapshot),
                correlation_id=correlation_id, metadata=dict(alert.metadata),
            )
            start, end = created_at - self.correlation_window, created_at + self.correlation_window
            candidates = self.repository.find_recent(start, end)
            related = [existing for existing in candidates if self._are_correlated(existing, incident)]
            try:
                stored, _was_existing = self.repository.insert(
                    incident, idempotency_key=alert.idempotency_key,
                    fingerprint=fingerprint, related_incidents=related,
                )
                return stored
            except DuplicateIncidentRecord as exc:
                raise DuplicateIncidentError(str(exc)) from exc
            except IdempotencyKeyConflict as exc:
                raise IdempotencyConflictError(str(exc)) from exc

    def _are_correlated(self, first: Incident, second: Incident) -> bool:
        if abs(first.created_at - second.created_at) > self.correlation_window:
            return False
        if first.correlation_id == second.correlation_id:
            return True
        return frozenset({first.service_name, second.service_name}) in self.DEFAULT_CORRELATED_PAIRS

    def get(self, incident_id: str) -> Incident | None:
        return self.repository.find(incident_id)

    def list(self, *, severity: IncidentSeverity | None = None, service_name: str | None = None,
             limit: int = 100) -> list[Incident]:
        canonical_service = self.infrastructure.resolve_service_name(service_name) if service_name else None
        records = self.repository.list_all(severity=severity)
        if canonical_service:
            records = [incident for incident in records
                       if canonical_service == incident.service_name
                       or canonical_service in incident.affected_services]
        return records[:limit]

    def update_status(self, incident_id: str, status: IncidentStatus) -> Incident:
        with self._lock:
            incident = self.repository.find(incident_id)
            if incident is None:
                raise KeyError(f"Incident '{incident_id}' was not found")
            if status == incident.status:
                return incident
            if status not in self.TRANSITIONS[incident.status]:
                raise InvalidIncidentTransition(
                    f"Cannot transition incident from {incident.status.value} to {status.value}"
                )
            now = datetime.now(timezone.utc)
            try:
                return self.repository.update_status(incident_id, incident.status, status, now)
            except ConcurrentIncidentUpdate as exc:
                current = self.repository.find(incident_id)
                if current and current.status == status:
                    return current
                if current is None:
                    raise KeyError(f"Incident '{incident_id}' was not found") from exc
                raise InvalidIncidentTransition(
                    f"Incident status changed concurrently to {current.status.value}"
                ) from exc

    def resolve(self, incident_id: str) -> Incident:
        return self.update_status(incident_id, IncidentStatus.RESOLVED)

    def history(self, incident_id: str) -> list[IncidentHistoryEntry] | None:
        return self.repository.get_history(incident_id)
