"""Parameterized SQLAlchemy persistence operations for incident records."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from incident_agent.incidents.models import (AlertType, Incident, IncidentHistoryEntry,
                                             IncidentSeverity, IncidentStatus)

from .database import Database
from .models import IncidentCorrelationRow, IncidentHistoryRow, IncidentRow


class DuplicateIncidentRecord(ValueError):
    """A distinct alert attempted to reuse an existing incident ID."""


class IdempotencyKeyConflict(ValueError):
    """An idempotency key was reused with a different alert payload."""


class ConcurrentIncidentUpdate(ValueError):
    """An incident changed while a lifecycle update was being committed."""


class IncidentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _related_ids(session: Session, incident_id: str) -> list[str]:
        rows = session.scalars(select(IncidentCorrelationRow).where(or_(
            IncidentCorrelationRow.left_incident_id == incident_id,
            IncidentCorrelationRow.right_incident_id == incident_id,
        ))).all()
        return sorted(row.right_incident_id if row.left_incident_id == incident_id
                      else row.left_incident_id for row in rows)

    @classmethod
    def _to_model(cls, session: Session, row: IncidentRow) -> Incident:
        return Incident(
            incident_id=row.incident_id, title=row.title, description=row.description,
            service_name=row.service_name, severity=IncidentSeverity(row.severity),
            alert_type=AlertType(row.alert_type), status=IncidentStatus(row.status),
            created_at=row.created_at, updated_at=row.updated_at,
            affected_services=row.affected_services, metrics_snapshot=row.metrics_snapshot,
            correlation_id=row.correlation_id, metadata=row.metadata_json,
            related_incident_ids=cls._related_ids(session, row.incident_id),
        )

    @staticmethod
    def _history_row(incident_id: str, entry: IncidentHistoryEntry) -> IncidentHistoryRow:
        return IncidentHistoryRow(
            incident_id=incident_id, timestamp=entry.timestamp, event=entry.event,
            previous_status=entry.previous_status.value if entry.previous_status else None,
            new_status=entry.new_status.value if entry.new_status else None,
            related_incident_id=entry.related_incident_id, details=entry.details,
        )

    def find_by_idempotency_key(self, key: str) -> tuple[Incident, str | None] | None:
        with self.database.session() as session:
            row = session.scalar(select(IncidentRow).where(IncidentRow.idempotency_key == key))
            return (self._to_model(session, row), row.payload_fingerprint) if row else None

    def find(self, incident_id: str) -> Incident | None:
        with self.database.session() as session:
            row = session.get(IncidentRow, incident_id)
            return self._to_model(session, row) if row else None

    def find_recent(self, start: datetime, end: datetime) -> list[Incident]:
        with self.database.session() as session:
            rows = session.scalars(select(IncidentRow).where(
                IncidentRow.created_at >= start, IncidentRow.created_at <= end
            )).all()
            return [self._to_model(session, row) for row in rows]

    def insert(self, incident: Incident, *, idempotency_key: str | None,
               fingerprint: str, related_incidents: Iterable[Incident]) -> tuple[Incident, bool]:
        related = list(related_incidents)
        try:
            with self.database.session() as session:
                with session.begin():
                    row = IncidentRow(
                        incident_id=incident.incident_id, idempotency_key=idempotency_key,
                        payload_fingerprint=fingerprint, title=incident.title,
                        description=incident.description, service_name=incident.service_name,
                        severity=incident.severity.value, alert_type=incident.alert_type.value,
                        status=incident.status.value, created_at=incident.created_at,
                        updated_at=incident.updated_at, affected_services=incident.affected_services,
                        metrics_snapshot=incident.metrics_snapshot, correlation_id=incident.correlation_id,
                        metadata_json=incident.metadata,
                    )
                    session.add(row)
                    session.flush()
                    created_event = IncidentHistoryEntry(
                        timestamp=incident.updated_at, event="incident_created",
                        new_status=IncidentStatus.OPEN,
                    )
                    session.add(self._history_row(incident.incident_id, created_event))
                    for prior in related:
                        left_id, right_id = sorted((incident.incident_id, prior.incident_id))
                        session.add(IncidentCorrelationRow(
                            left_incident_id=left_id, right_incident_id=right_id,
                            created_at=incident.updated_at,
                        ))
                        prior_row = session.get(IncidentRow, prior.incident_id)
                        if prior_row is not None:
                            prior_row.updated_at = incident.updated_at
                        details = "Related alert detected within configured correlation window."
                        session.add(self._history_row(incident.incident_id, IncidentHistoryEntry(
                            timestamp=incident.updated_at, event="incident_correlated",
                            related_incident_id=prior.incident_id, details=details,
                        )))
                        session.add(self._history_row(prior.incident_id, IncidentHistoryEntry(
                            timestamp=incident.updated_at, event="incident_correlated",
                            related_incident_id=incident.incident_id, details=details,
                        )))
            stored = self.find(incident.incident_id)
            assert stored is not None
            return stored, False
        except IntegrityError as exc:
            if idempotency_key:
                existing = self.find_by_idempotency_key(idempotency_key)
                if existing:
                    if existing[1] == fingerprint:
                        return existing[0], True
                    raise IdempotencyKeyConflict(
                        "Idempotency key was already used for a different alert"
                    ) from exc
            if self.find(incident.incident_id):
                raise DuplicateIncidentRecord(
                    f"Incident '{incident.incident_id}' already exists"
                ) from exc
            raise

    def list_all(self, severity: IncidentSeverity | None = None) -> list[Incident]:
        statement = select(IncidentRow)
        if severity is not None:
            statement = statement.where(IncidentRow.severity == severity.value)
        statement = statement.order_by(IncidentRow.created_at.desc(), IncidentRow.incident_id.desc())
        with self.database.session() as session:
            return [self._to_model(session, row) for row in session.scalars(statement).all()]

    def update_status(self, incident_id: str, expected_status: IncidentStatus,
                      status: IncidentStatus, timestamp: datetime) -> Incident:
        with self.database.session() as session:
            with session.begin():
                row = session.get(IncidentRow, incident_id)
                if row is None:
                    raise KeyError(f"Incident '{incident_id}' was not found")
                if row.status != expected_status.value:
                    raise ConcurrentIncidentUpdate("Incident status changed during the update")
                row.status = status.value
                row.updated_at = timestamp
                session.add(self._history_row(incident_id, IncidentHistoryEntry(
                    timestamp=timestamp, event="status_changed", previous_status=expected_status,
                    new_status=status,
                )))
            stored = self.find(incident_id)
            assert stored is not None
            return stored

    def get_history(self, incident_id: str) -> list[IncidentHistoryEntry] | None:
        with self.database.session() as session:
            if session.get(IncidentRow, incident_id) is None:
                return None
            rows = session.scalars(select(IncidentHistoryRow).where(
                IncidentHistoryRow.incident_id == incident_id
            ).order_by(IncidentHistoryRow.history_id)).all()
            return [IncidentHistoryEntry(
                timestamp=row.timestamp, event=row.event,
                previous_status=IncidentStatus(row.previous_status) if row.previous_status else None,
                new_status=IncidentStatus(row.new_status) if row.new_status else None,
                related_incident_id=row.related_incident_id, details=row.details,
            ) for row in rows]
