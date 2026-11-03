from fastapi.testclient import TestClient

from incident_agent.api.app import app, create_app, infrastructure


def test_investigation_retrieves_runbook_and_requires_approval(tmp_path) -> None:
    infrastructure.reset()
    test_app = create_app(infrastructure, database_url=f"sqlite:///{(tmp_path / 'workflow.db').as_posix()}")
    response = TestClient(test_app).post(
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
