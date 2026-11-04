"""Synchronous investigation use case and cooperative cancellation registry."""

from __future__ import annotations

from threading import Event, RLock
from typing import Any

from incident_agent.agent.investigation.graph import InvestigationCancelled, InvestigationGraph
from incident_agent.agent.investigation.llm import LLMConfigurationError, OpenAICompatibleProvider
from incident_agent.incidents.registry import IncidentRegistry
from incident_agent.retrieval.engine import RetrievalEngine
from incident_agent.simulator.environment import InfrastructureManager
from incident_agent.storage.investigation_repository import InvestigationRepository


class InvestigationRunError(RuntimeError):
    """An execution failed after a durable investigation ID was allocated."""

    def __init__(self, investigation_id: str, cause_type: str) -> None:
        super().__init__("Investigation execution failed")
        self.investigation_id = investigation_id
        self.cause_type = cause_type


class IncidentStateConflict(ValueError):
    """The incident exists but its lifecycle state is not investigable."""


class InvestigationService:
    def __init__(self, registry: IncidentRegistry, infrastructure: InfrastructureManager,
                 retrieval: RetrievalEngine, repository: InvestigationRepository) -> None:
        self.registry = registry
        self.infrastructure = infrastructure
        self.retrieval = retrieval
        self.repository = repository
        self._active: dict[str, Event] = {}
        self._lock = RLock()

    def investigate(self, incident_id: str, *, use_llm: bool = False) -> dict[str, Any]:
        incident = self.registry.get(incident_id)
        if incident is None:
            raise KeyError(f"Incident '{incident_id}' was not found")
        if incident.status.value == "CLOSED":
            raise IncidentStateConflict("Closed incidents cannot be investigated")
        self.infrastructure.resolve_service_name(incident.service_name)
        for service in incident.affected_services:
            self.infrastructure.resolve_service_name(service)
        provider = OpenAICompatibleProvider.from_environment() if use_llm else None
        if use_llm and provider is None:
            raise LLMConfigurationError(
                "LLM-backed investigation is not configured; set the three INVESTIGATION_LLM_* variables"
            )
        graph = InvestigationGraph(self.registry, self.infrastructure, self.retrieval, provider)
        state = graph.new_state(incident_id, use_llm=use_llm)
        state["investigation_status"] = "RUNNING"
        self.repository.create(state)
        cancel_event = Event()
        investigation_id = state["investigation_id"]
        with self._lock:
            self._active[investigation_id] = cancel_event
        try:
            result = graph.run(state, cancel_event, self.repository.progress)
            self.repository.complete(result)
            stored = self.repository.get(investigation_id)
            assert stored is not None
            return stored
        except InvestigationCancelled:
            self.repository.cancelled(investigation_id)
            stored = self.repository.get(investigation_id)
            assert stored is not None
            return stored
        except Exception as exc:
            # Do not persist provider URLs, tokens, or raw request/response bodies.
            self.repository.fail(investigation_id, type(exc).__name__)
            raise InvestigationRunError(investigation_id, type(exc).__name__) from exc
        finally:
            with self._lock:
                self._active.pop(investigation_id, None)

    def cancel(self, investigation_id: str) -> bool:
        with self._lock:
            event = self._active.get(investigation_id)
        if event is None:
            return False
        event.set()
        return True

    def get(self, investigation_id: str) -> dict[str, Any] | None:
        return self.repository.get(investigation_id)

    def timeline(self, investigation_id: str) -> list[dict[str, str]] | None:
        return self.repository.timeline(investigation_id)
