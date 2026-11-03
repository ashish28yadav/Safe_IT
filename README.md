# Safe IT-Ops Incident Agent

A local-first incident investigation prototype. It investigates seeded faults in in-memory Payment, Authentication, Notification, and PostgreSQL simulators. It does not connect to real infrastructure.

## Quick start

Requires Python 3.11+ and `uv`.

```powershell
uv sync --group dev
uv run python main.py
```

The API listens on `http://127.0.0.1:8000`; interactive API docs are at `/docs`.

```powershell
uv run pytest
uv run python -m incident_agent.evaluation.run
```

## API example

POST the following JSON to `/incidents/investigate`:

```json
{
  "title": "Payment provider errors",
  "description": "Payment requests time out at the gateway",
  "service": "payment",
  "scenario": "payment_errors",
  "approved": false
}
```

Proposed simulator actions require explicit approval by default (`approved: true`). `POST /simulator/reset` clears seeded faults. Supported scenarios are `payment_errors`, `authentication_timeout`, `notification_backlog`, and `database_connection_exhaustion`.

## Local retrieval

Runbooks are held in source and indexed in an ephemeral local Chroma collection with BM25 lexical retrieval. A stable local hashing embedder is the default and requires no network access. To use Sentence Transformers, provide model files locally and set `USE_LOCAL_SENTENCE_TRANSFORMER=true` and `EMBEDDING_MODEL_PATH` to that directory; the model is loaded in local-files-only mode.

## Docker and persistent local storage

Docker Compose runs the API as a non-root user and mounts the named `incident_data` volume at `/app/data`. SQLite is stored at `/app/data/incidents.db`; only the HTTP API is published, on loopback at `127.0.0.1:8000` by default. The SQLite file is never exposed as a network service. The container health check verifies `/health`, which reports unhealthy if simulator or database readiness fails. FastAPI applies Alembic migrations before serving requests and closes SQLAlchemy connections during graceful shutdown.

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://127.0.0.1:8000/health
```

Change the host-side API port only when needed by setting `APP_PORT` (for example, `$env:APP_PORT = "8080"` before `docker compose up --build -d`). The container continues to listen on port 8000. To recreate the application container while preserving its database volume:

```powershell
docker compose stop incident-agent
docker compose rm -f incident-agent
docker compose up -d --build incident-agent
```

Do not remove the named volume when recreating the container. For local development outside Docker, `INCIDENT_AGENT_DATABASE_URL` defaults to `sqlite:///./data/incidents.db`. All infrastructure simulations remain in process; no production infrastructure adapters or credentials are used.

## Infrastructure simulator

`InfrastructureManager` in `incident_agent.simulator` is the unified interface to four deterministic in-memory services: `payment-service`, `authentication-service`, `notification-service`, and `postgres-database`. Each exposes status, CPU and memory use, request and error counts/rates, response latency, uptime/availability, and database connection pool metrics. Logs are structured records with a fixed simulated timestamp and correlation ID, so repeated runs produce reproducible evidence.

Supported injected faults are `cpu_spike`, `memory_exhaustion`, `database_connection_exhaustion`, `high_http_500_error_rate`, `service_crash`, and `high_response_latency`. Existing workflow scenarios (`payment_errors`, `authentication_timeout`, and `notification_backlog`) remain supported. Faults stay active until cleared or remediated; restarting a crashed process recovers it, while a restart alone does not remove persistent resource or dependency failures.

```python
from incident_agent.simulator import InfrastructureManager

infra = InfrastructureManager()
infra.inject_failure("cpu_spike")
print(infra.query_metrics("payment-service")["cpu_utilization"])  # 98.0
infra.restart_service("payment-service")  # CPU fault remains active
print(infra.verify_recovery("payment-service"))  # False
infra.clear_failure("cpu_spike")
print(infra.verify_recovery("payment-service"))  # True
```

Run simulator and application tests with `uv run pytest`.

## Versioned infrastructure API

FastAPI routes live in `incident_agent.api.routes`; Pydantic response schemas are in `incident_agent.api.schemas`. The application creates one `InfrastructureManager` for its lifecycle and provides it to route handlers through a dependency. Inspection endpoints do not mutate simulator state. The existing incident investigation, simulator telemetry, and reset routes remain available for compatibility; simulator reset is a state-changing development operation. There are no new remediation routes.

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | API and simulator readiness |
| GET | `/api/v1/services` | Service names and current statuses |
| GET | `/api/v1/services/{service_name}` | Detailed service state and telemetry |
| GET | `/api/v1/services/{service_name}/metrics` | Resource, request, error, latency, and applicable database metrics |
| GET | `/api/v1/services/{service_name}/logs` | Logs filtered by `level`, `limit` (1–500), and `search` |
| GET | `/api/v1/services/{service_name}/recovery` | Health verification and currently active faults |

Example request:

```http
GET http://127.0.0.1:8000/api/v1/services/payment-service/metrics
```

Example response:

```json
{
  "service_name": "payment-service",
  "status": "HEALTHY",
  "cpu_utilization": 15.0,
  "memory_utilization": 30.0,
  "request_count": 1000,
  "request_rate": 16.6666666667,
  "error_count": 0,
  "error_rate": 0.0,
  "latency_ms": 40,
  "response_latency_ms": 40,
  "active_connections": 12,
  "max_connections": 100,
  "connection_pool_utilization": 0.12,
  "connection_limit": null
}
```

Unknown services return HTTP 404. Invalid log filters return HTTP 422. Start locally with `uv run python main.py`, then open Swagger UI at `http://127.0.0.1:8000/docs` (or the OpenAPI schema at `/openapi.json`). All exposed infrastructure data is simulated; no route connects to actual hosts, databases, or cloud services. New remediation operations must use the existing safety policy and approval checks.

## Incident ingestion and management

The versioned incident API accepts monitoring alerts as untrusted input. Request middleware rejects bodies above 64 KB before parsing; `RawAlert` then validates required text, alert type, optional severity, timezone-aware timestamps, metric bounds, metadata limits, and metric count. The ingestion service canonicalizes simulated service aliases, normalizes descriptions, metric keys and timestamps, preserves metadata and scalar metric values, assigns an `inc-...` ID when absent, and uses no external monitoring service. Descriptions and metadata remain inert data; instruction-like text is never executed or interpreted as an action.

The normalized incident model includes identity, service, severity, alert type, lifecycle status, timestamps, affected services, metric snapshot, correlation ID, metadata, and related incident IDs. Severity classification is deterministic and configurable through `SeverityThresholds`: service unavailable or `service_available: false` is **CRITICAL**; error rate above 30% is **CRITICAL**; above 15% is **HIGH**; CPU or memory at/above 85%, or latency at/above 1000 ms, is **MEDIUM**; otherwise the supplied valid severity is kept, falling back to **LOW**. Higher-priority rules override a supplied lower severity.

Allowed lifecycle transitions are `OPEN → INVESTIGATING → MITIGATING → RESOLVED → CLOSED`. `INVESTIGATING` can resolve directly, `MITIGATING` can return to investigation, and `RESOLVED` can be reopened as `INVESTIGATING`; `CLOSED` is terminal. Invalid transitions return HTTP 409. Repeating a caller-supplied incident ID returns 409; generated IDs are unique.

Alerts with the same correlation ID, or payment/database alerts, are related when their timestamps are within the default five-minute window. The registry records the relationship and history on both original incident records; it does not merge incidents. The window and severity thresholds can be configured when constructing the registry/classifier.

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/incidents` | Ingest and normalize a monitoring alert (201) |
| GET | `/api/v1/incidents` | List incidents; optional `severity`, `service_name`, and `limit` filters |
| GET | `/api/v1/incidents/{incident_id}` | Retrieve one normalized incident |
| PATCH | `/api/v1/incidents/{incident_id}/status` | Apply a valid lifecycle transition |
| GET | `/api/v1/incidents/{incident_id}/history` | Retrieve creation, correlation, and status history |

Example ingestion request:

```http
POST http://127.0.0.1:8000/api/v1/incidents
Content-Type: application/json
```

```json
{
  "title": "Payment error rate elevated",
  "description": "Payment service reports elevated gateway errors",
  "service_name": "payment",
  "alert_type": "ERROR_RATE",
  "metrics_snapshot": {"error_rate": 0.22, "cpu_utilization": 61},
  "metadata": {"source": "local-monitor-simulator"}
}
```

The response is a normalized incident with a generated ID, canonical `payment-service` name, `HIGH` severity, and `OPEN` status. Start locally with `uv run python main.py`; explore request and response schemas at `http://127.0.0.1:8000/docs`. Run all regression and incident tests with `uv run pytest`.

## Persistent incident storage

The incident registry uses SQLAlchemy 2.x through a repository boundary. SQLite is the only supported storage backend; the default file is `./data/incidents.db` (ignored by Git). Set `INCIDENT_AGENT_DATABASE_URL` to a different local SQLite URL when needed. The application owns one engine and session factory, applies Alembic migrations during startup, and disposes connections at shutdown. Repository mutations use database transactions; descriptions and metadata are stored as data and never interpreted as SQL or commands.

Schema overview:

- `incidents` stores normalized incident fields, JSON metric/metadata snapshots, a unique optional idempotency key, and its payload fingerprint.
- `incident_history` stores creation, correlation, and lifecycle events with timestamps and previous/new status.
- `incident_correlations` stores unique pairs of related incident IDs. It preserves both original records.
- `alembic_version` tracks the schema revision.

Include `idempotency_key` in a `POST /api/v1/incidents` request to make alert delivery retry-safe. The database enforces uniqueness. A repeated key with the same normalized alert content returns the existing incident; reusing the key for different content returns HTTP 409. Requests without a key create new incidents. The registry also guards duplicate caller-supplied incident IDs. Correlation uses the configured time window and does not deduplicate alerts.

Apply or inspect schema migrations using:

```powershell
uv run alembic upgrade head
uv run alembic current
```

The app also applies pending migrations on startup. To use an alternate local file, set `INCIDENT_AGENT_DATABASE_URL` before starting the app. Tests configure isolated SQLite files under pytest temporary directories and never use the development database.
