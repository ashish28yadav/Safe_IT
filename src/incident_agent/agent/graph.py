"""Rule-grounded LangGraph workflow over local simulator evidence."""

from typing import TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from incident_agent.config import settings
from incident_agent.models import ActionProposal, IncidentRequest, IncidentResult
from incident_agent.retrieval.engine import HybridRetriever
from incident_agent.safety.policy import SafetyPolicy
from incident_agent.simulator.environment import LocalInfrastructure


class IncidentState(TypedDict, total=False):
    incident: IncidentRequest
    incident_id: str
    telemetry: dict[str, object]
    evidence: list[str]
    runbooks: list[dict[str, str]]
    diagnosis: str
    proposal: ActionProposal | None
    action_result: dict[str, str] | None


class IncidentAgent:
    def __init__(self, infrastructure: LocalInfrastructure | None = None, retriever: HybridRetriever | None = None) -> None:
        self.infrastructure = infrastructure or LocalInfrastructure()
        self.retriever = retriever or HybridRetriever()
        self.policy = SafetyPolicy(require_approval=settings.require_action_approval)
        graph = StateGraph(IncidentState)
        graph.add_node("collect", self._collect)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("diagnose", self._diagnose)
        graph.add_node("safety", self._safety)
        graph.add_edge(START, "collect")
        graph.add_edge("collect", "retrieve")
        graph.add_edge("retrieve", "diagnose")
        graph.add_edge("diagnose", "safety")
        graph.add_edge("safety", END)
        self.graph = graph.compile()

    def investigate(self, incident: IncidentRequest) -> IncidentResult:
        if incident.scenario:
            self.infrastructure.inject_scenario(incident.scenario)
        state = self.graph.invoke({"incident": incident, "incident_id": str(uuid4())})
        proposal = state.get("proposal")
        from incident_agent.models import ActionResult

        action_result = ActionResult(**state["action_result"]) if state.get("action_result") else None
        return IncidentResult(
            incident_id=state["incident_id"], title=incident.title, diagnosis=state["diagnosis"],
            evidence=state["evidence"], retrieved_runbooks=[item["title"] for item in state["runbooks"]],
            proposed_action=proposal, action_result=action_result,
        )

    def _collect(self, state: IncidentState) -> dict[str, object]:
        incident = state["incident"]
        telemetry = self.infrastructure.telemetry(incident.service)
        evidence = [f"{key}: {value}" for key, value in telemetry.items() if key != "service"]
        return {"telemetry": telemetry, "evidence": evidence}

    def _retrieve(self, state: IncidentState) -> dict[str, object]:
        incident = state["incident"]
        query = f"{incident.title}. {incident.description} {state['evidence']}"
        return {"runbooks": self.retriever.search(query, incident.service)}

    def _diagnose(self, state: IncidentState) -> dict[str, object]:
        incident = state["incident"]
        telemetry = state["telemetry"]
        logs = " ".join(str(value) for value in telemetry.get("logs", []))
        if incident.service == "postgres":
            diagnosis = "PostgreSQL connection pool is exhausted." if not telemetry.get("healthy") else "PostgreSQL telemetry is within normal limits."
            proposal = ActionProposal(action="recycle_db_connections", target="postgres", reason=diagnosis) if not telemetry.get("healthy") else None
        elif incident.service == "notification":
            diagnosis = f"Notification queue backlog is {telemetry.get('backlog', 0)} messages."
            proposal = ActionProposal(action="clear_notification_backlog", target="notification", reason=diagnosis) if int(telemetry.get("backlog", 0)) > 100 else None
        else:
            diagnosis = f"{incident.service.title()} service is {'unhealthy' if not telemetry.get('healthy') else 'healthy'}; observed logs: {logs or 'none'}."
            proposal = ActionProposal(action="restart_service", target=incident.service, reason=diagnosis) if not telemetry.get("healthy") else None
        return {"diagnosis": diagnosis, "proposal": proposal}

    def _safety(self, state: IncidentState) -> dict[str, object]:
        proposal = state.get("proposal")
        if proposal is None:
            return {"action_result": None}
        incident = state["incident"]
        result = self.policy.execute(proposal, incident.approved, self.infrastructure)
        return {"action_result": result.model_dump()}
