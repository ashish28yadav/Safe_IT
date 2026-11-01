"""Development entry point for the local incident-agent API."""

from pathlib import Path
import sys


# Support launching this script directly before the project is installed as a
# package (for example, from an IDE using the repository's virtualenv).
SOURCE_DIR = Path(__file__).resolve().parent / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))


if __name__ == "__main__":
    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        if exc.name != "uvicorn":
            raise
        raise SystemExit(
            "uvicorn is not installed in this Python environment. "
            "Install the project dependencies with `uv sync`, then rerun `python main.py`."
        ) from exc

    uvicorn.run("incident_agent.api.app:app", host="127.0.0.1", port=8000, reload=False)
