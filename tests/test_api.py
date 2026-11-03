import pytest
from fastapi.testclient import TestClient

from incident_agent.api.app import create_app
from incident_agent.simulator.environment import InfrastructureManager


@pytest.fixture
def setup_api(tmp_path):
    manager = InfrastructureManager()
    database_url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    with TestClient(create_app(manager, database_url=database_url)) as client:
        yield manager, client


def test_health_and_service_listing(setup_api: tuple[InfrastructureManager, TestClient]) -> None:
    _, client = setup_api
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "simulator_ready": True, "storage_ready": True,
                             "registered_services": 4, "mode": "local_simulation"}
    services = client.get("/api/v1/services")
    assert services.status_code == 200
    assert len(services.json()) == 4
    assert set(services.json()[0]) == {"service_name", "status", "healthy"}


def test_service_details_and_metrics_schema(setup_api: tuple[InfrastructureManager, TestClient]) -> None:
    _, client = setup_api
    details = client.get("/api/v1/services/postgres-database")
    assert details.status_code == 200
    assert details.json()["service_name"] == "postgres-database"
    assert details.json()["status"] == "HEALTHY"
    metrics = client.get("/api/v1/services/postgres-database/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["active_connections"] == 12
    assert metrics.json()["connection_pool_utilization"] == 0.12
    assert "logs" not in metrics.json()


def test_log_filters_limit_and_search(setup_api: tuple[InfrastructureManager, TestClient]) -> None:
    manager, client = setup_api
    manager.inject_failure("cpu_spike")
    manager.inject_failure("high_http_500_error_rate")
    response = client.get("/api/v1/services/payment-service/logs?level=ERROR&limit=1&search=Injected")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["logs"][0]["level"] == "ERROR"
    assert body["logs"][0]["service_name"] == "payment-service"


def test_recovery_reports_faults(setup_api: tuple[InfrastructureManager, TestClient]) -> None:
    manager, client = setup_api
    manager.inject_failure("memory_exhaustion")
    response = client.get("/api/v1/services/notification-service/recovery")
    assert response.status_code == 200
    assert response.json()["recovered"] is False
    assert response.json()["active_faults"] == ["memory_exhaustion"]


def test_unknown_services_return_404_and_query_errors_422(setup_api: tuple[InfrastructureManager, TestClient]) -> None:
    _, client = setup_api
    assert client.get("/api/v1/services/no-such-service").status_code == 404
    assert client.get("/api/v1/services/no-such-service/metrics").status_code == 404
    assert client.get("/api/v1/services/payment-service/logs?limit=0").status_code == 422
    assert client.get("/api/v1/services/payment-service/logs?level=TRACE").status_code == 422
    assert client.get("/api/v1/services/payment-service/logs?search=x&limit=501").status_code == 422


def test_state_is_shared_between_requests(setup_api: tuple[InfrastructureManager, TestClient]) -> None:
    manager, client = setup_api
    manager.inject_failure("cpu_spike")
    metrics = client.get("/api/v1/services/payment-service/metrics").json()
    details = client.get("/api/v1/services/payment-service").json()
    assert metrics["cpu_utilization"] == details["cpu_utilization"] == 98.0


def test_read_only_endpoints_do_not_mutate_state(setup_api: tuple[InfrastructureManager, TestClient]) -> None:
    manager, client = setup_api
    manager.inject_failure("service_crash")
    before = manager.telemetry("authentication-service")
    client.get("/health")
    client.get("/api/v1/services")
    client.get("/api/v1/services/authentication-service")
    client.get("/api/v1/services/authentication-service/metrics")
    client.get("/api/v1/services/authentication-service/logs")
    client.get("/api/v1/services/authentication-service/recovery")
    assert manager.telemetry("authentication-service") == before


def test_openapi_describes_versioned_routes(setup_api: tuple[InfrastructureManager, TestClient]) -> None:
    _, client = setup_api
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/services/{service_name}/recovery" in paths
    assert "/health" in paths
