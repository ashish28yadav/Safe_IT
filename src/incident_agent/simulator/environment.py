"""Local infrastructure with named, repeatable fault scenarios."""

from .services import (
    AuthenticationService,
    NotificationService,
    PaymentService,
    PostgresSimulator,
    ServiceState,
)


class LocalInfrastructure:
    SCENARIOS = {
        "payment_errors": "payment",
        "authentication_timeout": "authentication",
        "notification_backlog": "notification",
        "database_connection_exhaustion": "postgres",
    }

    def __init__(self) -> None:
        self.services: dict[str, ServiceState] = {}
        self.postgres = PostgresSimulator()
        self.reset()

    def reset(self) -> None:
        self.services = {
            "payment": PaymentService(),
            "authentication": AuthenticationService(),
            "notification": NotificationService(),
        }
        self.postgres = PostgresSimulator()

    def inject_scenario(self, scenario: str) -> None:
        if scenario not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
        target = self.SCENARIOS[scenario]
        if target == "payment":
            state = self.services[target]
            state.healthy, state.error_rate, state.latency_ms = False, 0.42, 950
            state.logs = ["gateway timeout", "payment provider circuit breaker open"]
        elif target == "authentication":
            state = self.services[target]
            state.healthy, state.latency_ms, state.error_rate = False, 1800, 0.2
            state.logs = ["token validation timeout", "identity dependency slow"]
        elif target == "notification":
            state = self.services[target]
            state.backlog, state.latency_ms = 2400, 600
            state.logs = ["queue depth above threshold", "consumer throughput degraded"]
        else:
            self.postgres.active_connections = self.postgres.connection_limit
            self.postgres.healthy = False
            self.postgres.logs = ["connection pool exhausted", "new connection rejected"]

    def telemetry(self, service: str) -> dict[str, object]:
        if service == "postgres":
            return self.postgres.telemetry()
        if service not in self.services:
            raise ValueError(f"Unknown service: {service}")
        return self.services[service].telemetry()

    def apply(self, action: str, target: str) -> str:
        """Apply an allowlisted operation to in-memory simulator state only."""
        if action == "restart_service" and target in self.services:
            state = self.services[target]
            state.healthy, state.latency_ms, state.error_rate = True, 40, 0.0
            state.logs.append("simulated restart completed")
            return f"Simulated restart completed for {target}."
        if action == "clear_notification_backlog" and target == "notification":
            self.services[target].backlog = 0
            self.services[target].logs.append("simulated backlog drain completed")
            return "Simulated notification backlog cleared."
        if action == "recycle_db_connections" and target == "postgres":
            self.postgres.active_connections = 12
            self.postgres.healthy = True
            self.postgres.logs.append("simulated connection recycle completed")
            return "Simulated PostgreSQL connections recycled."
        raise ValueError("Operation is not supported for this target")
