"""Local-first application settings."""

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("INCIDENT_AGENT_DATA_DIR", "./data"))
    use_local_sentence_transformer: bool = os.getenv("USE_LOCAL_SENTENCE_TRANSFORMER", "false").lower() == "true"
    embedding_model_path: str = os.getenv("EMBEDDING_MODEL_PATH", "./models/all-MiniLM-L6-v2")
    require_action_approval: bool = os.getenv("REQUIRE_ACTION_APPROVAL", "true").lower() == "true"


settings = Settings()
