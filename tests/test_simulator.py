from incident_agent.simulator.environment import LocalInfrastructure


def test_scenarios_set_expected_local_telemetry() -> None:
    infrastructure = LocalInfrastructure()
    infrastructure.inject_scenario("payment_errors")
    telemetry = infrastructure.telemetry("payment")
    assert telemetry["healthy"] is False
    assert telemetry["error_rate"] == 0.42
    infrastructure.inject_scenario("database_connection_exhaustion")
    assert infrastructure.telemetry("postgres")["active_connections"] == 100


def test_reset_restores_simulated_services() -> None:
    infrastructure = LocalInfrastructure()
    infrastructure.inject_scenario("notification_backlog")
    infrastructure.reset()
    assert infrastructure.telemetry("notification")["backlog"] == 0


def test_apply_changes_only_simulated_state() -> None:
    infrastructure = LocalInfrastructure()
    infrastructure.inject_scenario("notification_backlog")
    infrastructure.apply("clear_notification_backlog", "notification")
    assert infrastructure.telemetry("notification")["backlog"] == 0
