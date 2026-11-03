"""FastAPI application for incident investigation and simulator inspection."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from incident_agent.agent.graph import IncidentAgent
from incident_agent.api.routes import router as infrastructure_router
from incident_agent.api.incident_routes import router as incident_router
from incident_agent.api.middleware import IncidentPayloadLimitMiddleware
from incident_agent.api.schemas import HealthResponse
from incident_agent.models import IncidentRequest, IncidentResult
from incident_agent.simulator.environment import LocalInfrastructure
from incident_agent.incidents.registry import IncidentRegistry
from incident_agent.storage.database import DEFAULT_DATABASE_URL, Database


def create_app(infrastructure: LocalInfrastructure | None = None, *, database_url: str | None = None) -> FastAPI:
    """Build an application with one shared simulator for its full lifecycle."""
    manager = infrastructure or LocalInfrastructure()
    database = Database(database_url or DEFAULT_DATABASE_URL)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.initialize()
        try:
            yield
        finally:
            database.close()

    application = FastAPI(
        title="Safe IT-Ops Incident Agent",
        version="0.2.0",
        description="Read-only, versioned inspection of deterministic simulated infrastructure.",
        lifespan=lifespan,
    )
    application.add_middleware(IncidentPayloadLimitMiddleware, max_bytes=64_000)
    application.state.infrastructure = manager
    application.state.database = database
    application.state.agent = IncidentAgent(infrastructure=manager)
    application.state.incident_registry = IncidentRegistry(manager, database=database)
    application.include_router(infrastructure_router)
    application.include_router(incident_router)

    @application.get("/health", response_model=HealthResponse, tags=["Health"])
    def health(response: Response) -> HealthResponse:
        service_count = len(manager.list_services())
        simulator_ready = service_count > 0
        storage_ready = database.check_ready()
        ready = simulator_ready and storage_ready
        if not ready:
            response.status_code = 503
        return HealthResponse(status="ok" if ready else "not_ready",
                              simulator_ready=simulator_ready, storage_ready=storage_ready,
                              registered_services=service_count, mode="local_simulation")

    # Compatibility endpoints retained for existing clients.
    @application.get("/simulator/services/{service}")
    def service_telemetry(service: str) -> dict[str, object]:
        try:
            return manager.telemetry(service)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @application.post("/simulator/reset")
    def reset_simulator() -> dict[str, str]:
        manager.reset()
        return {"status": "reset"}

    @application.post("/incidents/investigate", response_model=IncidentResult)
    def investigate(request: IncidentRequest) -> IncidentResult:
        try:
            return application.state.agent.investigate(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return application


app = create_app()
# Backward-compatible module references used by existing local clients/tests.
infrastructure = app.state.infrastructure
agent = app.state.agent
