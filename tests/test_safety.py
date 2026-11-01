from incident_agent.models import ActionProposal
from incident_agent.safety.policy import SafetyPolicy
from incident_agent.simulator.environment import LocalInfrastructure


def test_action_requires_approval() -> None:
    infrastructure = LocalInfrastructure()
    proposal = ActionProposal(action="restart_service", target="payment", reason="unhealthy")
    result = SafetyPolicy().execute(proposal, approved=False, infrastructure=infrastructure)
    assert result.status == "approval_required"
    assert infrastructure.telemetry("payment")["healthy"] is True


def test_policy_blocks_invalid_action_target() -> None:
    infrastructure = LocalInfrastructure()
    proposal = ActionProposal(action="restart_service", target="postgres", reason="not allowed")
    result = SafetyPolicy().execute(proposal, approved=True, infrastructure=infrastructure)
    assert result.status == "blocked"
