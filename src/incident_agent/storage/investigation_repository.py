"""Transactional persistence for investigation results and timeline events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from incident_agent.storage.database import Database
from incident_agent.storage.models import InvestigationRow, InvestigationTimelineRow


class InvestigationRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, state: dict[str, Any]) -> None:
        with self.database.session() as session, session.begin():
            session.add(InvestigationRow(
                investigation_id=str(state["investigation_id"]), incident_id=str(state["incident_id"]),
                status=str(state.get("investigation_status", "RUNNING")), start_time=_datetime(str(state["start_time"])),
                completion_time=None, state_json=state, report_json=None, errors_json=[],
            ))

    def mark_interrupted(self) -> int:
        """Close stale RUNNING rows left by a process restart before serving requests."""
        now = datetime.now().astimezone()
        with self.database.session() as session, session.begin():
            rows = session.scalars(select(InvestigationRow).where(InvestigationRow.status == "RUNNING")).all()
            for row in rows:
                row.status = "FAILED"
                row.completion_time = now
                row.errors_json = ["Process restarted before investigation completed"]
                row.state_json = {**row.state_json, "investigation_status": "FAILED",
                                  "investigation_errors": row.errors_json}
                session.add(InvestigationTimelineRow(
                    investigation_id=row.investigation_id, timestamp=now,
                    step="process_restart", detail="Marked interrupted investigation as failed on startup",
                ))
            return len(rows)

    def progress(self, state: dict[str, Any], node_name: str) -> None:
        steps = state.get("investigation_steps", [])
        step = steps[-1] if steps else {"timestamp": datetime.now().astimezone().isoformat(),
                                        "step": node_name, "detail": "Node completed"}
        with self.database.session() as session, session.begin():
            row = session.get(InvestigationRow, str(state["investigation_id"]))
            if row is None:
                return
            row.status = str(state.get("investigation_status", "RUNNING"))
            row.state_json = dict(state)
            session.add(InvestigationTimelineRow(
                investigation_id=row.investigation_id, timestamp=_datetime(step["timestamp"]),
                step=str(step.get("step", node_name)), detail=str(step.get("detail", "")),
            ))

    def complete(self, state: dict[str, Any]) -> None:
        with self.database.session() as session, session.begin():
            row = session.get(InvestigationRow, str(state["investigation_id"]))
            if row is None:
                raise KeyError("Investigation record disappeared before completion")
            row.status = str(state.get("investigation_status", "COMPLETED"))
            row.completion_time = _datetime(str(state["completion_time"])) if state.get("completion_time") else None
            row.state_json = state
            row.report_json = state.get("report")
            row.errors_json = list(state.get("investigation_errors", []))

    def fail(self, investigation_id: str, error: str) -> None:
        with self.database.session() as session, session.begin():
            row = session.get(InvestigationRow, investigation_id)
            if row is not None:
                row.status = "FAILED"
                row.completion_time = datetime.now().astimezone()
                row.errors_json = [error[:500]]
                row.state_json = {**row.state_json, "investigation_status": "FAILED",
                                  "investigation_errors": [error[:500]]}

    def cancelled(self, investigation_id: str) -> None:
        with self.database.session() as session, session.begin():
            row = session.get(InvestigationRow, investigation_id)
            if row is not None:
                row.status = "CANCELLED"
                row.completion_time = datetime.now().astimezone()
                row.state_json = {**row.state_json, "investigation_status": "CANCELLED"}

    def get(self, investigation_id: str) -> dict[str, Any] | None:
        with self.database.session() as session:
            row = session.get(InvestigationRow, investigation_id)
            if row is None:
                return None
            return {"investigation_id": row.investigation_id, "incident_id": row.incident_id,
                    "status": row.status, "start_time": row.start_time.isoformat(),
                    "completion_time": row.completion_time.isoformat() if row.completion_time else None,
                    "report": row.report_json, "errors": list(row.errors_json),
                    "evidence": list(row.state_json.get("evidence", [])),
                    "state": row.state_json}

    def timeline(self, investigation_id: str) -> list[dict[str, str]] | None:
        with self.database.session() as session:
            if session.get(InvestigationRow, investigation_id) is None:
                return None
            rows = session.scalars(select(InvestigationTimelineRow).where(
                InvestigationTimelineRow.investigation_id == investigation_id
            ).order_by(InvestigationTimelineRow.event_id)).all()
            return [{"timestamp": row.timestamp.isoformat(), "step": row.step, "detail": row.detail}
                    for row in rows]


def _datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Investigation timestamps must be timezone-aware")
    return parsed
