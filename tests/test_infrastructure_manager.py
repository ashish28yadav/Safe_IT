import pytest

from incident_agent.simulator import InfrastructureManager, LogLevel, ServiceStatus


def test_initial_services_and_metrics_are_deterministic() -> None:
    manager = InfrastructureManager()
    assert manager.list_services() == ["payment-service", "authentication-service", "notification-service", "postgres-database"]
    first = manager.query_metrics("payment-service")
    assert first["status"] == ServiceStatus.HEALTHY.value
    assert first == manager.query_metrics("payment-service")
    assert first["cpu_utilization"] >= 0 and first["request_rate"] > 0


def test_logs_are_structured_and_searchable() -> None:
    manager = InfrastructureManager()
    manager.inject_failure("service_crash")
    log = manager.search_logs("authentication-service", "service_crash")[0]
    assert {"timestamp", "level", "service_name", "message", "correlation_id", "error_details"} <= log.keys()
    assert log["level"] == LogLevel.ERROR.value
    assert log["error_details"] == "service_crash"


@pytest.mark.parametrize(("failure", "metric", "expected"), [
    ("cpu_spike", "cpu_utilization", 98.0),
    ("memory_exhaustion", "memory_utilization", 99.0),
    ("database_connection_exhaustion", "connection_pool_utilization", 1.0),
])
def test_resource_failures_reflect_in_metrics(failure: str, metric: str, expected: float) -> None:
    manager = InfrastructureManager()
    manager.inject_failure(failure)
    assert expected == manager.query_metrics(manager.FAILURE_TARGETS[failure])[metric]


def test_crash_restart_recovers_and_persistent_failure_does_not() -> None:
    manager = InfrastructureManager()
    manager.inject_failure("service_crash")
    assert manager.read_status("authentication-service") == "DOWN"
    manager.restart_service("authentication-service")
    assert manager.verify_recovery("authentication-service")
    manager.inject_failure("memory_exhaustion")
    manager.restart_service("notification-service")
    assert not manager.verify_recovery("notification-service")
    manager.clear_failure("memory_exhaustion")
    assert manager.verify_recovery("notification-service")


def test_http_500_and_latency_faults_and_invalid_requests() -> None:
    manager = InfrastructureManager()
    manager.inject_failure("high_http_500_error_rate")
    assert manager.query_metrics("payment-service")["error_rate"] == 0.42
    manager.inject_failure("high_response_latency")
    assert manager.query_metrics("authentication-service")["response_latency_ms"] == 1800
    with pytest.raises(ValueError):
        manager.telemetry("missing-service")
    with pytest.raises(ValueError):
        manager.inject_failure("unknown-fault")
    with pytest.raises(ValueError):
        manager.apply("format_disk", "payment")

