"""Service state and deterministic telemetry for simulated services."""

from dataclasses import dataclass, field


@dataclass
class ServiceState:
    name: str
    healthy: bool = True
    latency_ms: int = 40
    error_rate: float = 0.0
    backlog: int = 0
    logs: list[str] = field(default_factory=list)

    def telemetry(self) -> dict[str, object]:
        return {
            "service": self.name,
            "healthy": self.healthy,
            "latency_ms": self.latency_ms,
            "error_rate": self.error_rate,
            "backlog": self.backlog,
            "logs": list(self.logs),
        }


class PaymentService(ServiceState):
    def __init__(self) -> None:
        super().__init__("payment")


class AuthenticationService(ServiceState):
    def __init__(self) -> None:
        super().__init__("authentication")


class NotificationService(ServiceState):
    def __init__(self) -> None:
        super().__init__("notification")


class PostgresSimulator:
    """In-memory PostgreSQL facade; it never opens a database connection."""

    def __init__(self) -> None:
        self.connection_limit = 100
        self.active_connections = 12
        self.healthy = True
        self.logs: list[str] = ["database ready"]

    def telemetry(self) -> dict[str, object]:
        return {
            "service": "postgres",
            "healthy": self.healthy,
            "active_connections": self.active_connections,
            "connection_limit": self.connection_limit,
            "logs": list(self.logs),
        }
