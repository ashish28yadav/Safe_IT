# Repository Guidelines

## Project Structure

Application code lives in `src/incident_agent/`, grouped by responsibility: `api/`, `agent/`, `retrieval/`, `safety/`, `simulator/`, and `evaluation/`. Tests are in `tests/`. `main.py` starts the local API. `pyproject.toml` and `uv.lock` define the Python environment; `Dockerfile` packages the service.

## Development Commands

- `uv sync --group dev` installs application and development dependencies.
- `uv run python main.py` starts the API at `127.0.0.1:8000`.
- `uv run pytest` runs the test suite.
- `uv run python -m incident_agent.evaluation.run` evaluates the fixed simulator scenarios.
- `docker build -t safe-it-ops-agent .` builds the container image.

## Style and Tests

Use four-space indentation, type annotations on public functions, `snake_case` for functions and variables, and `CapWords` for classes. Keep simulator behavior deterministic and local. Add pytest files as `tests/test_<area>.py` and name tests `test_<behavior>`. Cover simulator scenarios, action allowlisting and approval, retrieval, and end-to-end workflow behavior when changing those components.

## Safety and Configuration

Infrastructure operations must remain in-process simulator changes. Do not add production adapters, external service credentials, or real incident data. Actions must pass through `safety/policy.py`; keep approval required by default. The default retrieval embedder is offline and deterministic. Sentence Transformer models must be supplied locally and loaded with local-only settings. Keep generated data, model files, caches, and virtual environments out of version control.

## Changes and Reviews

Use concise imperative commit subjects, such as `Add database exhaustion scenario`. Pull requests should describe the incident behavior affected, list validation commands and results, and include API examples or screenshots when useful. Keep `pyproject.toml` and `uv.lock` in sync when dependencies change.
