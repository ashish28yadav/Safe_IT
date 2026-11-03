"""FastAPI dependencies shared by API routers."""

from fastapi import Request

from incident_agent.simulator.environment import InfrastructureManager
from incident_agent.incidents.registry import IncidentRegistry


def get_infrastructure(request: Request) -> InfrastructureManager:
    """Return the application-lifecycle simulator instance."""
    return request.app.state.infrastructure


def get_incident_registry(request: Request) -> IncidentRegistry:
    """Return the application-lifecycle incident registry."""
    return request.app.state.incident_registry
