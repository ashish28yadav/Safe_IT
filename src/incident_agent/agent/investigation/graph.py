"""Finite LangGraph workflow for evidence collection and report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Event, RLock
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from incident_agent.agent.investigation.llm import InvestigationLLMProvider
from incident_agent.agent.investigation.models import InvestigationState
from incident_agent.agent.investigation.nodes import InvestigationNodes
from incident_agent.agent.investigation.tools import ReadOnlyInfrastructureTools
from incident_agent.incidents.registry import IncidentRegistry
from incident_agent.retrieval.engine import RetrievalEngine
from incident_agent.simulator.environment import InfrastructureManager

MAX_INVESTIGATION_STEPS = 12
MAX_GRAPH_RECURSION = 18
MAX_REPORT_ATTEMPTS = 1
MAX_NODE_RETRIES = 0
MAX_INVESTIGATION_SECONDS = 90.0


class InvestigationCancelled(RuntimeError):
    pass


class InvestigationGraph:
    """Compile a static, bounded, read-only investigation StateGraph."""

    def __init__(self, registry: IncidentRegistry, infrastructure: InfrastructureManager,
                 retrieval: RetrievalEngine,
                 provider: InvestigationLLMProvider | None = None) -> None:
        self.nodes = InvestigationNodes(registry, ReadOnlyInfrastructureTools(infrastructure), retrieval, provider)
        self._run_lock = RLock()
        self._cancel_events: dict[str, Event] = {}
        self._start_times: dict[str, float] = {}
        graph = StateGraph(InvestigationState)
        graph.add_node("validate_incident", self._guard(self.nodes.validate_incident))
        graph.add_node("classify_incident", self._guard(self.nodes.classify_incident))
        graph.add_node("retrieve_knowledge", self._guard(self.nodes.retrieve_knowledge))
        graph.add_node("inspect_service_health", self._guard(self.nodes.inspect_service_health))
        graph.add_node("inspect_metrics", self._guard(self.nodes.inspect_metrics))
        graph.add_node("inspect_logs", self._guard(self.nodes.inspect_logs))
        graph.add_node("correlate_evidence", self._guard(self.nodes.correlate_evidence))
        graph.add_node("generate_hypotheses", self._guard(self.nodes.generate_hypotheses))
        graph.add_node("assess_missing_evidence", self._guard(self.nodes.assess_missing_evidence))
        graph.add_node("generate_report", self._guard(self.nodes.generate_report))
        graph.add_edge(START, "validate_incident")
        graph.add_edge("validate_incident", "classify_incident")
        graph.add_edge("classify_incident", "retrieve_knowledge")
        graph.add_edge("retrieve_knowledge", "inspect_service_health")
        graph.add_edge("inspect_service_health", "inspect_metrics")
        graph.add_edge("inspect_metrics", "inspect_logs")
        graph.add_edge("inspect_logs", "correlate_evidence")
        graph.add_edge("correlate_evidence", "generate_hypotheses")
        graph.add_edge("generate_hypotheses", "assess_missing_evidence")
        graph.add_conditional_edges(
            "assess_missing_evidence", self._next,
            {"report": "generate_report", "stop": END},
        )
        graph.add_edge("generate_report", END)
        self.compiled = graph.compile()

    @staticmethod
    def _next(state: InvestigationState) -> str:
        # All currently modeled observations are collected in the first pass. If
        # future nodes add useful follow-up observations, this is the finite routing gate.
        if len(state.get("investigation_steps", [])) >= state.get("step_budget", MAX_INVESTIGATION_STEPS):
            return "stop"
        return "report"

    def _guard(self, node: Any) -> Any:
        def bounded(state: InvestigationState) -> dict[str, Any]:
            investigation_id = str(state.get("investigation_id", ""))
            with self._run_lock:
                cancel_event = self._cancel_events.get(investigation_id)
                started_at = self._start_times.get(investigation_id, monotonic())
            if cancel_event is not None and cancel_event.is_set():
                raise InvestigationCancelled("Investigation was cancelled")
            if monotonic() - started_at > MAX_INVESTIGATION_SECONDS:
                raise TimeoutError("Investigation exceeded its execution time limit")
            if len(state.get("investigation_steps", [])) >= int(state.get("step_budget", MAX_INVESTIGATION_STEPS)):
                raise TimeoutError("Investigation step budget exceeded")
            return node(state)
        return bounded

    @staticmethod
    def new_state(incident_id: str, *, use_llm: bool = False) -> InvestigationState:
        started = datetime.now(timezone.utc).isoformat()
        return {
            "investigation_id": f"inv-{uuid4()}", "incident_id": incident_id,
            "investigation_status": "PENDING", "investigation_steps": [],
            "retrieved_documents": [], "retrieved_sources": [],
            "service_observations": [], "metric_observations": [], "log_observations": [],
            "dependency_observations": [], "hypotheses": [], "evidence": [],
            "missing_evidence": [], "recommended_actions": [], "investigation_errors": [],
            "token_usage": {}, "start_time": started, "use_llm": use_llm,
            "step_budget": MAX_INVESTIGATION_STEPS,
        }

    def run(self, initial: InvestigationState, cancel_event: Event | None = None,
            progress_callback: Callable[[InvestigationState, str], None] | None = None) -> InvestigationState:
        investigation_id = initial["investigation_id"]
        event = cancel_event or Event()
        with self._run_lock:
            self._cancel_events[investigation_id] = event
            self._start_times[investigation_id] = monotonic()
        try:
            state = dict(initial)
            for update in self.compiled.stream(
                initial, config={"recursion_limit": MAX_GRAPH_RECURSION}, stream_mode="updates"
            ):
                for node_name, values in update.items():
                    if isinstance(values, dict):
                        state.update(values)
                        if progress_callback is not None:
                            progress_callback(state, str(node_name))
            return state  # type: ignore[return-value]
        finally:
            with self._run_lock:
                self._cancel_events.pop(investigation_id, None)
                self._start_times.pop(investigation_id, None)

    def cancel(self, investigation_id: str) -> bool:
        with self._run_lock:
            event = self._cancel_events.get(investigation_id)
        if event is None:
            return False
        event.set()
        return True
