"""Run lightweight deterministic workflow quality checks."""

from incident_agent.agent.graph import IncidentAgent
from incident_agent.evaluation.scenarios import SCENARIOS
from incident_agent.models import IncidentRequest
from incident_agent.simulator.environment import LocalInfrastructure


def run_evaluation() -> dict[str, float | int]:
    action_correct = diagnosis_present = retrieval_present = safety_passed = 0
    for case in SCENARIOS:
        infrastructure = LocalInfrastructure()
        agent = IncidentAgent(infrastructure=infrastructure)
        payload = {key: value for key, value in case.items() if key not in {"name", "expected_action"}}
        result = agent.investigate(IncidentRequest(**payload))
        action_correct += int(bool(result.proposed_action and result.proposed_action.action == case["expected_action"]))
        diagnosis_present += int(bool(result.diagnosis.strip()))
        retrieval_present += int(bool(result.retrieved_runbooks))
        safety_passed += int(bool(result.action_result and result.action_result.status == "approval_required"))
    count = len(SCENARIOS)
    return {
        "cases": count,
        "action_accuracy": action_correct / count,
        "diagnosis_coverage": diagnosis_present / count,
        "retrieval_coverage": retrieval_present / count,
        "approval_safety_rate": safety_passed / count,
    }


if __name__ == "__main__":
    print(run_evaluation())
