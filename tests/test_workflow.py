from fastapi.testclient import TestClient

from incident_agent.api.app import app, infrastructure


def test_investigation_retrieves_runbook_and_requires_approval() -> None:
    infrastructure.reset()
    response = TestClient(app).post(
        "/incidents/investigate",
        json={
            "title": "Payment provider errors",
            "description": "Payment requests return gateway timeout errors",
            "service": "payment",
            "scenario": "payment_errors",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["proposed_action"]["action"] == "restart_service"
    assert result["action_result"]["status"] == "approval_required"
    assert result["retrieved_runbooks"]
