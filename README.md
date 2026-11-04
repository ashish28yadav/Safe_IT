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

The persistent RAG subsystem indexes the tracked `knowledge_base/` directory with structure-aware or fixed-size chunks. ChromaDB stores vectors and `rank_bm25` stores a durable chunk mapping and rebuildable BM25 index metadata. BM25 and vector retrieval share stable chunk IDs; hybrid search uses reciprocal rank fusion. The default `local-hash-v1` embedder is deterministic and offline. BGE and MiniLM support requires a local model directory; the model is loaded lazily in local-only CPU mode and is never downloaded by application startup.

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

## Phase 6: Evidence-based incident investigations

The Phase 6 investigator is a separate finite LangGraph workflow over an existing persisted incident. It does not replace the compatibility endpoint `/incidents/investigate` or the safety-policy workflow. The new `/api/v1/investigations` API investigates the incident registry record and returns a persisted report.

### Graph and evidence model

`incident_agent.agent.investigation` owns a JSON-serializable `InvestigationState`, focused graph nodes, an optional OpenAI-compatible provider, and a narrow simulator tool adapter. The graph validates the incident, classifies symptoms, queries the existing hybrid retriever, inspects service health/metrics/logs, records dependency modeling gaps, correlates observations with cited knowledge chunks, ranks evidence-linked hypotheses, assesses missing evidence, and produces a structured report. Retrieved runbooks are reference information; they are never treated as proof of current conditions.

The graph has a 12-step limit, 18 LangGraph recursion limit, 90-second execution deadline, zero automatic node retries, one report-generation pass, and bounded LLM request timeout. The current simulator does not expose dependency topology, so dependency observations explicitly say `not_modelled`. Cancellation is cooperative at node boundaries. The API executes a run synchronously and returns only after the run finishes; it does not claim background execution.

Run one API process per simulator instance. The simulator and active cancellation registry are process-local; multiple Uvicorn workers would maintain different simulated states and cannot cancel work running in another worker. Interrupted persistent investigation rows are detected at startup and marked failed.

Allowed simulator inspections are `read_status`, `telemetry`, `query_metrics`, and bounded `search_logs`. The adapter exposes no restart, fault-clear, failure-injection, shell, SQL, or configuration operations. The investigator does not change incident lifecycle state. Incident descriptions, metadata, retrieved text, and logs are untrusted data. The optional LLM receives the incident fields as data and is instructed not to follow embedded instructions. Model suggestions are unverified and cannot become confirmed hypotheses without direct simulator evidence.

Each infrastructure observation has an `obs-...` identifier, service, type, timestamp when available, and a source method. Retrieved sources retain the real `document_id`, `chunk_id`, title, section, source, strategy, and rank. Hypotheses cite evidence IDs and use qualitative `low`, `moderate`, or `high` confidence; these labels are not calibrated probabilities. The report separates simulator facts, retrieved reference chunks, inferred hypotheses, and recommendations.

### Optional OpenAI-compatible model

Rule-based classification and evidence analysis run locally and deterministically by default. They are not represented as an LLM investigation. To request model-assisted analysis, set all of these values in the process environment (or an ignored local `.env` file used by Compose):

| Variable | Purpose |
| --- | --- |
| `INVESTIGATION_LLM_BASE_URL` | OpenAI-compatible API root, for example the provider's `/v1` endpoint |
| `INVESTIGATION_LLM_API_KEY` | Provider credential, supplied at runtime only |
| `INVESTIGATION_LLM_MODEL` | Provider model identifier |
| `INVESTIGATION_LLM_TIMEOUT_SECONDS` | Request timeout from 1 to 60 seconds; default 12 |

The service does not contain a default endpoint, key, or model name. No model is downloaded and no API call is made at startup. `use_llm: true` returns HTTP 503 with a configuration error if settings are absent or incomplete. Requests are made only for investigations that opt in. The provider receives only an allowlisted incident summary and metric fields; metadata is excluded and common inline secret assignments in title/description are redacted. Provider token usage is recorded only when the provider returns it; secrets and clients are never placed in graph state or persisted snapshots.

### Investigation API

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/investigations` | Run investigation for an existing incident; synchronous, returns 201 after completion |
| GET | `/api/v1/investigations/{investigation_id}` | Get persisted status and timestamps |
| GET | `/api/v1/investigations/{investigation_id}/report` | Get completed structured report |
| GET | `/api/v1/investigations/{investigation_id}/evidence` | Get observation and knowledge evidence records |
| GET | `/api/v1/investigations/{investigation_id}/timeline` | Get the persisted node timeline |
| POST | `/api/v1/investigations/{investigation_id}/cancel` | Request cooperative cancellation if currently running (202); otherwise 409 |

Example:

```powershell
$body = @{ incident_id = "inc-..."; use_llm = $false } | ConvertTo-Json
$run = Invoke-RestMethod http://127.0.0.1:8000/api/v1/investigations -Method Post -ContentType "application/json" -Body $body
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/investigations/$($run.investigation_id)/report"
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/investigations/$($run.investigation_id)/evidence"
```

Reports include an executive summary, incident context, affected services, timeline, simulator health/metrics/logs, retrieved knowledge citations, hypotheses with support/contradiction IDs, confidence assessment, missing evidence, recommendations, safety warnings, and simulator limitations. Every current infrastructure fact points to an observation ID. Knowledge references cite the exact retrieved document and chunk.

### Persistence and evaluation

Alembic revision `0002_investigation_storage` adds `investigations` and `investigation_timeline` tables to the existing SQLite database. JSON snapshots persist the latest graph state, report, and evidence; timeline entries are separate rows. They share the existing `/app/data/incidents.db` named Docker volume. On startup, unfinished `RUNNING` records are marked failed with an interruption timeline event so clients do not poll forever after a process restart. No Redis, database server, or new volume is introduced.

The deterministic benchmark is in `src/incident_agent/evaluation/investigation_scenarios.json` and contains 31 labeled cases across all four services, including incomplete/conflicting alerts and hostile incident/log/reference text. Run it with:

```powershell
uv run python -m incident_agent.evaluation.investigation
```

It reports completion, root-cause identification, evidence precision, citation correctness, unsupported-claim rate, read-only tool selection, unsafe tool attempts, step count, latency, and available token usage. It uses the local hash retriever and no LLM calls. Model-assisted evaluation is separate and must be run explicitly against a configured provider; no model-based scores are implied by the deterministic benchmark.

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

## Phase 5: Operational knowledge retrieval

### Architecture and corpus

`incident_agent.retrieval.documents` loads Markdown, TXT, and PDF (PyMuPDF) documents, normalizes metadata and text, and produces either heading-aware chunks or fixed word windows with configurable overlap. Malformed/empty documents are reported by filename in application logs and in the local rebuild response. Chunk identifiers are stable for the same document, chunking strategy, order, and content. Each chunk preserves document ID, chunk ID, title, relative source name, service, category, document type, section, and a SHA-256 content hash.

The tracked [`knowledge_base/`](knowledge_base/) contains 31 operational runbooks and synthetic incident examples for payment, authentication, notification, PostgreSQL, and cross-service failure classes. Historical examples say “Synthetic example only” and do not describe real customer events. Runbooks require operator review and authorization before state changes; no document automatically authorizes a destructive action.

At startup, one lifecycle-scoped `RetrievalEngine` indexes the corpus. Chroma persists vectors below `./data/chroma`; BM25 chunk mappings and metadata are stored below `./data/bm25`. In Docker these resolve to `/app/data/chroma` and `/app/data/bm25` within the existing named `incident_data` volume, separate from `/app/data/incidents.db`. Re-indexing is idempotent and removes stale chunk IDs. Collection metadata records the embedding model identity; reusing a collection with a different model fails closed.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `KNOWLEDGE_BASE_DIR` | `./knowledge_base` | Source documents |
| `RETRIEVAL_VECTOR_DIR` | `./data/chroma` | Persistent Chroma directory |
| `RETRIEVAL_BM25_DIR` | `./data/bm25` | Persistent BM25 metadata |
| `RETRIEVAL_COLLECTION_NAME` | `operational_knowledge` | Chroma collection |
| `RETRIEVAL_EMBEDDING_MODEL` | `local-hash-v1` | `local-hash-v1`, `BAAI/bge-small-en-v1.5`, or `sentence-transformers/all-MiniLM-L6-v2` |
| `RETRIEVAL_EMBEDDING_MODEL_PATH` | unset | Local transformer model directory; required for transformer modes |
| `RETRIEVAL_CHUNK_SIZE` / `RETRIEVAL_CHUNK_OVERLAP` | `220` / `40` | Word window and overlap |
| `RETRIEVAL_CHUNKING_STRATEGY` | `structure` | `structure` or `fixed` |
| `RETRIEVAL_RRF_CONSTANT` | `60` | Reciprocal-rank fusion constant |
| `APP_ENV` | `production` | Rebuild route is enabled only for explicit `development` or `local` |

For a local deterministic setup:

```powershell
uv sync --group dev
uv run python main.py
```

To enable the local-only index rebuild route, explicitly set `$env:APP_ENV = "development"` before starting the API. For a transformer, set `RETRIEVAL_EMBEDDING_MODEL` to one of the supported identities and `RETRIEVAL_EMBEDDING_MODEL_PATH` to an already-present local model folder. No model is fetched automatically. Transformer inference runs on CPU; use the hashing default on memory-constrained hosts.

Download model files explicitly into local ignored storage when you want to evaluate them (these commands are not run by the app):

```powershell
uv run hf download sentence-transformers/all-MiniLM-L6-v2 --local-dir .\models\all-MiniLM-L6-v2
uv run hf download BAAI/bge-small-en-v1.5 --local-dir .\models\bge-small-en-v1.5
$env:EVAL_MINILM_MODEL_PATH = (Resolve-Path .\models\all-MiniLM-L6-v2).Path
$env:EVAL_BGE_MODEL_PATH = (Resolve-Path .\models\bge-small-en-v1.5).Path
```

The evaluator reads exactly `EVAL_MINILM_MODEL_PATH` and `EVAL_BGE_MODEL_PATH`. Each Chroma collection stores its `RETRIEVAL_EMBEDDING_MODEL` identity and rejects reuse with an incompatible embedding model. If downloading is not desired, point these variables to existing local directories. For Docker, mount a host model folder with `RETRIEVAL_MODEL_HOST_DIR` and set `RETRIEVAL_EMBEDDING_MODEL_PATH` to its `/app/models/...` path.

### Retrieval API

| Method | Path | Description |
| --- | --- | --- |
| POST | `/api/v1/retrieval/search` | Search with `bm25`, `vector`, or `hybrid`; optional service/category/document type filters |
| GET | `/api/v1/retrieval/health` | Index readiness and document/chunk counts; no storage paths are returned |
| POST | `/api/v1/retrieval/index/rebuild` | Rebuild indexes in explicit `APP_ENV=development` or `local` only (HTTP 403 otherwise) |

Example:

```powershell
$body = @{
  query = "PostgreSQL connection pool exhaustion and payment timeouts"
  top_k = 5
  strategy = "hybrid"
  service = "postgres-database"
  category = "database"
  document_type = "runbook"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/retrieval/search `
  -ContentType "application/json" -Body $body
```

The response includes BM25 and vector candidate rankings plus the RRF fused results. BM25 scores are returned only for BM25 candidates; vector hits do not receive a fabricated relevance score. Results preserve the source and chunk metadata. Request sizes are bounded by Pydantic validation (`query` max 2,000 characters, `top_k` 1–50, and optional `candidate_count` 1–100).

### Evaluation

Thirty manually reviewed queries and relevant operational document IDs are in `src/incident_agent/evaluation/retrieval_queries.json`. Run:

```powershell
uv run python -m incident_agent.evaluation.retrieval
```

The harness evaluates E1 BM25, E2 MiniLM vectors, E3 BGE vectors, E4 BM25+MiniLM, and E5 BM25+BGE with both chunking strategies. It writes `evaluation/retrieval/results.json`, `results.csv`, and `report.md`. The evaluator collapses chunk hits into a stable document ranking before calculating all metrics. Recall@1/3/5 is the macro-average per query of relevant documents found in the top K divided by that query’s relevant document count. MRR is the macro-average reciprocal rank of the first relevant document. Since some queries have multiple relevant documents, MRR can be 1.0 while Recall@1 is below 1.0 when the first result is relevant but other relevant documents rank later. Indexing time forces a full rebuild; mean/p95 query latency is measured at run time. Transformer cases are marked `not_run` unless their local model paths are configured; the harness never downloads weights. Scores are not inferred for skipped cases.

Docker Compose defaults `APP_ENV` to `production`, keeps Chroma and BM25 below the existing `/app/data` named volume, and disables API-triggered rebuilds. The container health check verifies both API/storage and retrieval-index readiness. Swagger UI documents all routes at `/docs`. PDF loading requires the locked PyMuPDF dependency. There is no external LLM call, live monitoring integration, production infrastructure connection, or automatic remediation in this phase.
