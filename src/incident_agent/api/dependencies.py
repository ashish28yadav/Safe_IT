"""FastAPI dependencies shared by API routers."""

from fastapi import Request

from incident_agent.simulator.environment import InfrastructureManager
from incident_agent.incidents.registry import IncidentRegistry
from incident_agent.retrieval.engine import RetrievalEngine
from incident_agent.agent.investigation.service import InvestigationService


def get_infrastructure(request: Request) -> InfrastructureManager:
    """Return the application-lifecycle simulator instance."""
    return request.app.state.infrastructure


def get_incident_registry(request: Request) -> IncidentRegistry:
    """Return the application-lifecycle incident registry."""
    return request.app.state.incident_registry


def get_retrieval_engine(request: Request) -> RetrievalEngine:
    """Return the lifecycle-scoped persistent retrieval engine."""
    return request.app.state.retrieval_engine


def get_investigation_service(request: Request) -> InvestigationService:
    """Return the app-scoped investigation orchestrator."""
    return request.app.state.investigation_service
