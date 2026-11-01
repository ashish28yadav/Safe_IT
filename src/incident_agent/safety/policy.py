"""Fail-closed action validation and approval boundary."""

from incident_agent.models import ActionProposal, ActionResult
from incident_agent.simulator.environment import LocalInfrastructure


class SafetyPolicy:
    ALLOWED = {
        ("restart_service", "payment"),
        ("restart_service", "authentication"),
        ("restart_service", "notification"),
        ("clear_notification_backlog", "notification"),
        ("recycle_db_connections", "postgres"),
    }

    def __init__(self, require_approval: bool = True) -> None:
        self.require_approval = require_approval

    def execute(self, proposal: ActionProposal, approved: bool, infrastructure: LocalInfrastructure) -> ActionResult:
        key = (proposal.action, proposal.target)
        if key not in self.ALLOWED:
            return ActionResult(status="blocked", detail="Action and target are not on the safety allowlist.")
        if self.require_approval and not approved:
            return ActionResult(status="approval_required", detail="Action is simulated and requires explicit approval.")
        try:
            detail = infrastructure.apply(proposal.action, proposal.target)
        except ValueError as exc:
            return ActionResult(status="blocked", detail=str(exc))
        return ActionResult(status="applied", detail=detail)
