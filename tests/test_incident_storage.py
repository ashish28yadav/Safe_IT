from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from incident_agent.api.app import create_app
from incident_agent.incidents.models import (AlertType, Incident, IncidentSeverity,
                                             IncidentStatus, RawAlert)
from incident_agent.incidents.registry import IncidentRegistry
from incident_agent.simulator.environment import InfrastructureManager
from incident_agent.storage.database import Database
from incident_agent.storage.repository import IncidentRepository


def make_alert(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Payment alert",
        "description": "Repeated payment errors from the local monitor",
        "service_name": "payment-service",
        "alert_type": "ERROR_RATE",
        "metrics_snapshot": {"error_rate": 0.2},
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def database(tmp_path):
    db = Database(f"sqlite:///{(tmp_path / 'incidents.db').as_posix()}")
    yield db
    db.close()


@pytest.fixture
def persistent_client(database: Database):
    manager = InfrastructureManager()
    with TestClient(create_app(manager, database_url=database.url)) as client:
        yield client


def test_database_initializes_schema_through_migrations(database: Database) -> None:
    database.initialize()
    with database.engine.connect() as connection:
        tables = set(connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).scalars())
    assert {"incidents", "incident_history", "incident_correlations", "alembic_version"} <= tables


def test_create_and_retrieve_after_database_reconnection(database: Database) -> None:
    registry = IncidentRegistry(InfrastructureManager(), database=database)
    created = registry.create(RawAlert.model_validate(make_alert(
        incident_id="persistent-1", metadata={"source": "test"},
    )))
    url = database.url
    database.close()

    reconnected = Database(url)
    try:
        retrieved = IncidentRegistry(InfrastructureManager(), database=reconnected).get("persistent-1")
        assert retrieved == created
        assert retrieved is not None and retrieved.metadata == {"source": "test"}
    finally:
        reconnected.close()


def test_incident_survives_application_restart(tmp_path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    with TestClient(create_app(database_url=database_url)) as first_app:
        created = first_app.post("/api/v1/incidents", json=make_alert()).json()
    with TestClient(create_app(database_url=database_url)) as restarted_app:
        response = restarted_app.get(f"/api/v1/incidents/{created['incident_id']}")
    assert response.status_code == 200
    assert response.json()["incident_id"] == created["incident_id"]


def test_lifecycle_history_survives_reconnection(database: Database) -> None:
    registry = IncidentRegistry(InfrastructureManager(), database=database)
    incident = registry.create(RawAlert.model_validate(make_alert()))
    registry.update_status(incident.incident_id, IncidentStatus.INVESTIGATING)
    registry.update_status(incident.incident_id, IncidentStatus.RESOLVED)
    database.close()
    reconnected = Database(database.url)
    try:
        history = IncidentRegistry(InfrastructureManager(), database=reconnected).history(incident.incident_id)
        assert history is not None
        assert [entry.event for entry in history] == ["incident_created", "status_changed", "status_changed"]
        assert history[1].previous_status == IncidentStatus.OPEN
        assert history[1].new_status == IncidentStatus.INVESTIGATING
    finally:
        reconnected.close()


def test_same_idempotency_key_returns_existing_only_for_same_payload(
    persistent_client: TestClient,
) -> None:
    first = persistent_client.post("/api/v1/incidents", json=make_alert(idempotency_key="monitor-42"))
    repeated = persistent_client.post("/api/v1/incidents", json=make_alert(idempotency_key="monitor-42"))
    assert first.status_code == repeated.status_code == 201
    assert first.json()["incident_id"] == repeated.json()["incident_id"]
    assert len(persistent_client.get("/api/v1/incidents").json()) == 1

    conflict = persistent_client.post("/api/v1/incidents", json=make_alert(
        idempotency_key="monitor-42", title="Different unrelated alert",
    ))
    assert conflict.status_code == 409


def test_different_idempotency_keys_create_distinct_incidents(
    persistent_client: TestClient,
) -> None:
    first = persistent_client.post("/api/v1/incidents", json=make_alert(idempotency_key="monitor-A"))
    second = persistent_client.post("/api/v1/incidents", json=make_alert(idempotency_key="monitor-B"))
    assert first.status_code == second.status_code == 201
    assert first.json()["incident_id"] != second.json()["incident_id"]


def test_concurrent_duplicate_submissions_are_unique(database: Database) -> None:
    manager = InfrastructureManager()
    registries = [IncidentRegistry(manager, database=database) for _ in range(8)]
    alert = RawAlert.model_validate(make_alert(idempotency_key="concurrent-monitor-alert"))

    def submit(index: int) -> str:
        return registries[index].create(alert).incident_id

    with ThreadPoolExecutor(max_workers=len(registries)) as executor:
        incident_ids = list(executor.map(submit, range(len(registries))))
    assert len(set(incident_ids)) == 1
    assert len(registries[0].list()) == 1


def test_failed_insert_rolls_back_incident_and_history(database: Database) -> None:
    repository = IncidentRepository(database)
    now = datetime.now(timezone.utc)
    incident = Incident(
        incident_id="transaction-rollback", title="Test rollback", description="Testing atomic rollback",
        service_name="payment-service", severity=IncidentSeverity.LOW,
        alert_type=AlertType.MONITORING_ALERT, status=IncidentStatus.OPEN,
        created_at=now, updated_at=now, affected_services=["payment-service"],
        metrics_snapshot={}, correlation_id="corr-test", metadata={},
    )
    missing_related = incident.model_copy(update={"incident_id": "zz-missing-related"})
    with pytest.raises(IntegrityError):
        repository.insert(incident, idempotency_key=None, fingerprint="f" * 64,
                          related_incidents=[missing_related])
    assert repository.find("transaction-rollback") is None
    assert repository.get_history("transaction-rollback") is None


def test_correlation_relationship_and_history_persist(database: Database) -> None:
    registry = IncidentRegistry(InfrastructureManager(), database=database)
    first = registry.create(RawAlert.model_validate(make_alert(
        incident_id="payment-original", correlation_id="shared-alert-group",
    )))
    second = registry.create(RawAlert.model_validate(make_alert(
        incident_id="database-original", service_name="postgres-database",
        alert_type="DATABASE_CONNECTIONS", correlation_id="shared-alert-group",
    )))
    database.close()
    reconnected = Database(database.url)
    try:
        durable_registry = IncidentRegistry(InfrastructureManager(), database=reconnected)
        assert second.incident_id in durable_registry.get(first.incident_id).related_incident_ids
        assert first.incident_id in durable_registry.get(second.incident_id).related_incident_ids
        assert durable_registry.history(first.incident_id)[-1].related_incident_id == second.incident_id
    finally:
        reconnected.close()
