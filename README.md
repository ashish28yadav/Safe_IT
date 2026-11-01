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

## Docker

```sh
docker build -t safe-it-ops-agent .
docker run --rm -p 8000:8000 safe-it-ops-agent
```

All simulator mutations remain in process memory. Never add production infrastructure adapters or credentials to this prototype.
