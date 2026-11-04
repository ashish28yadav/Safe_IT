"""Explicit allowlist of bounded, read-only simulator inspection operations."""

from __future__ import annotations

from typing import Any

from incident_agent.simulator.environment import InfrastructureManager


class ReadOnlyInfrastructureTools:
    """Narrow view that cannot invoke mutation methods on InfrastructureManager."""

    __slots__ = ("_manager", "max_query_chars")

    def __init__(self, manager: InfrastructureManager, max_query_chars: int = 200) -> None:
        self._manager = manager
        self.max_query_chars = max_query_chars

    @property
    def allowed_operations(self) -> frozenset[str]:
        return frozenset({"read_status", "telemetry", "query_metrics", "search_logs", "inspect_dependencies"})

    def canonical_services(self, service_names: list[str]) -> list[str]:
        if not service_names or len(service_names) > 4:
            raise ValueError("Investigation must target between one and four services")
        canonical = list(dict.fromkeys(self._manager.resolve_service_name(name) for name in service_names))
        if len(canonical) > 4:
            raise ValueError("Investigation service limit exceeded")
        return canonical

    def inspect_status(self, service: str) -> dict[str, Any]:
        name = self._manager.resolve_service_name(service)
        telemetry = self._manager.telemetry(name)
        return {"service_name": name, "status": self._manager.read_status(name),
                "healthy": bool(telemetry["healthy"]), "uptime_seconds": telemetry["uptime_seconds"],
                "availability": telemetry["availability"]}

    def inspect_metrics(self, service: str) -> dict[str, Any]:
        return self._manager.query_metrics(self._manager.resolve_service_name(service))

    def inspect_logs(self, service: str, query: str = "") -> list[dict[str, str | None]]:
        if len(query) > self.max_query_chars:
            raise ValueError("Log search query exceeds the supported length")
        return self._manager.search_logs(self._manager.resolve_service_name(service), query)

    def inspect_dependencies(self, service: str) -> dict[str, Any]:
        name = self._manager.resolve_service_name(service)
        # The simulator does not model a service dependency graph. Report that explicitly.
        return {"service_name": name, "dependency_state": "not_modelled", "dependencies": []}
