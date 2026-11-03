"""Deterministic, in-process infrastructure simulation and remediation API."""

from __future__ import annotations

from typing import Any

from .services import (AuthenticationService, LogLevel, NotificationService, PaymentService,
                       PostgresSimulator, ServiceState, ServiceStatus)


class InfrastructureManager:
    """Unified interface to simulated services; all operations are local state changes."""

    SERVICE_ALIASES = {
        "payment": "payment-service", "authentication": "authentication-service",
        "notification": "notification-service", "postgres": "postgres-database",
    }
    FAILURE_TARGETS = {
        "cpu_spike": "payment-service", "memory_exhaustion": "notification-service",
        "database_connection_exhaustion": "postgres-database",
        "high_http_500_error_rate": "payment-service", "http_500_rate": "payment-service",
        "service_crash": "authentication-service", "high_response_latency": "authentication-service",
        "payment_errors": "payment-service", "authentication_timeout": "authentication-service",
        "notification_backlog": "notification-service",
    }

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.services: dict[str, ServiceState] = {
            service.name: service for service in (PaymentService(), AuthenticationService(),
                                                   NotificationService(), PostgresSimulator())
        }
        self.postgres = self.services["postgres-database"]

    def _name(self, service: str) -> str:
        return self.resolve_service_name(service)

    def resolve_service_name(self, service: str) -> str:
        """Return the registered canonical name for a service or raise ValueError."""
        canonical = self.SERVICE_ALIASES.get(service, service)
        if canonical not in self.services:
            raise ValueError(f"Unknown service: {service}")
        return canonical

    def list_services(self) -> list[str]:
        return list(self.services)

    def read_status(self, service: str) -> str:
        return self.services[self._name(service)].status.value

    def telemetry(self, service: str) -> dict[str, Any]:
        return self.services[self._name(service)].telemetry()

    def query_metrics(self, service: str) -> dict[str, Any]:
        return {key: value for key, value in self.telemetry(service).items() if key != "logs"}

    def search_logs(self, service: str, query: str = "") -> list[dict[str, str | None]]:
        state = self.services[self._name(service)]
        needle = query.casefold()
        return [entry.as_dict() for entry in state.logs
                if needle in (entry.message + " " + (entry.error_details or "")).casefold()]

    def inject_failure(self, failure: str, service: str | None = None) -> None:
        if failure not in self.FAILURE_TARGETS:
            raise ValueError(f"Unknown failure scenario: {failure}")
        target = self._name(service) if service else self.FAILURE_TARGETS[failure]
        state = self.services[target]
        state.active_failures.add(failure)
        if failure in {"cpu_spike"}:
            state.cpu_utilization, state.status = 98.0, ServiceStatus.DEGRADED
        elif failure == "memory_exhaustion":
            state.memory_utilization, state.status = 99.0, ServiceStatus.DEGRADED
        elif failure == "database_connection_exhaustion":
            state.active_connections = state.max_connections
            state.healthy, state.status, state.error_rate = False, ServiceStatus.DOWN, 1.0
            state.error_count = 100
        elif failure in {"high_http_500_error_rate", "http_500_rate", "payment_errors"}:
            state.error_rate, state.error_count = 0.42, 420
            state.healthy, state.status = False, ServiceStatus.DEGRADED
        elif failure == "service_crash":
            state.healthy, state.status, state.error_rate = False, ServiceStatus.DOWN, 1.0
        elif failure in {"high_response_latency", "authentication_timeout"}:
            state.latency_ms, state.status, state.healthy = 1800, ServiceStatus.DEGRADED, False
            state.error_rate, state.error_count = 0.2, 200
        elif failure == "notification_backlog":
            state.backlog, state.latency_ms = 2400, 600
            state.status = ServiceStatus.DEGRADED
        state.add_log(f"Injected failure: {failure}", LogLevel.ERROR,
                      error_details=failure, correlation_id=f"failure-{failure}")

    def inject_scenario(self, scenario: str) -> None:
        self.inject_failure(scenario)

    def clear_failure(self, failure: str, service: str | None = None) -> None:
        if failure not in self.FAILURE_TARGETS:
            raise ValueError(f"Unknown failure scenario: {failure}")
        target = self._name(service) if service else self.FAILURE_TARGETS[failure]
        state = self.services[target]
        state.active_failures.discard(failure)
        # Recompute fault metrics from remaining failure conditions.
        remaining = set(state.active_failures)
        if not remaining:
            state.cpu_utilization, state.memory_utilization = 15.0, 30.0
            state.latency_ms, state.error_rate, state.error_count, state.backlog = 40, 0.0, 0, 0
            state.active_connections = 12
            state.healthy, state.status = True, ServiceStatus.HEALTHY
        state.add_log(f"Cleared failure: {failure}", LogLevel.INFO)

    def restart_service(self, service: str) -> str:
        state = self.services[self._name(service)]
        state.status = ServiceStatus.RESTARTING
        # A restart recovers a crashed process only. Resource pressure and external
        # dependency faults remain active and therefore remain visible after restart.
        state.active_failures.discard("service_crash")
        state.uptime_seconds = 0
        persistent = state.active_failures
        state.healthy = not persistent
        state.status = ServiceStatus.DEGRADED if persistent else ServiceStatus.HEALTHY
        if not persistent:
            state.cpu_utilization, state.memory_utilization = 15.0, 30.0
            state.latency_ms, state.error_rate, state.error_count = 40, 0.0, 0
        state.add_log("Simulated restart completed", LogLevel.INFO)
        return f"Simulated restart completed for {state.name}."

    def verify_recovery(self, service: str) -> bool:
        state = self.services[self._name(service)]
        return state.healthy and state.status == ServiceStatus.HEALTHY and not state.active_failures

    def check_service_health(self, service: str) -> bool:
        return self.verify_recovery(service)

    def apply(self, action: str, target: str) -> str:
        """Compatibility entry point for previously supported simulated actions."""
        name = self._name(target)
        if action == "restart_service":
            return self.restart_service(name)
        if action == "clear_notification_backlog" and name == "notification-service":
            state = self.services[name]
            state.backlog = 0
            state.active_failures.discard("notification_backlog")
            state.status, state.healthy = ServiceStatus.HEALTHY, True
            state.add_log("Simulated backlog drain completed")
            return "Simulated notification backlog cleared."
        if action == "recycle_db_connections" and name == "postgres-database":
            state = self.postgres
            state.active_connections = 12
            state.active_failures.discard("database_connection_exhaustion")
            state.status, state.healthy, state.error_rate = ServiceStatus.HEALTHY, True, 0.0
            state.add_log("Simulated connection recycle completed")
            return "Simulated PostgreSQL connections recycled."
        raise ValueError("Operation is not supported for this target")


class LocalInfrastructure(InfrastructureManager):
    """Backward compatible name used by the existing workflow and evaluation."""


