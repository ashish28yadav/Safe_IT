"""HTTP interface for local incident investigations and simulator state."""

from fastapi import FastAPI, HTTPException

from incident_agent.agent.graph import IncidentAgent
from incident_agent.models import IncidentRequest, IncidentResult
from incident_agent.simulator.environment import LocalInfrastructure

infrastructure = LocalInfrastructure()
agent = IncidentAgent(infrastructure=infrastructure)
app = FastAPI(title="Safe IT-Ops Incident Agent", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local_simulation"}


@app.get("/simulator/services/{service}")
def service_telemetry(service: str) -> dict[str, object]:
    try:
        return infrastructure.telemetry(service)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/simulator/reset")
def reset_simulator() -> dict[str, str]:
    infrastructure.reset()
    return {"status": "reset"}


@app.post("/incidents/investigate", response_model=IncidentResult)
def investigate(request: IncidentRequest) -> IncidentResult:
    try:
        return agent.investigate(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
