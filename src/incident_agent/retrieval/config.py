"""Environment-based retrieval settings."""

from dataclasses import dataclass, field
import os
from pathlib import Path


@dataclass(frozen=True)
class RetrievalConfig:
    knowledge_base_dir: Path = field(default_factory=lambda: Path(os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge_base")))
    vector_dir: Path = field(default_factory=lambda: Path(os.getenv("RETRIEVAL_VECTOR_DIR", "./data/chroma")))
    bm25_dir: Path = field(default_factory=lambda: Path(os.getenv("RETRIEVAL_BM25_DIR", "./data/bm25")))
    collection_name: str = field(default_factory=lambda: os.getenv("RETRIEVAL_COLLECTION_NAME", "operational_knowledge"))
    embedding_model: str = field(default_factory=lambda: os.getenv("RETRIEVAL_EMBEDDING_MODEL", "local-hash-v1"))
    embedding_model_path: str = field(default_factory=lambda: os.getenv("RETRIEVAL_EMBEDDING_MODEL_PATH", ""))
    chunk_size: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_CHUNK_SIZE", "220")))
    chunk_overlap: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_CHUNK_OVERLAP", "40")))
    chunking_strategy: str = field(default_factory=lambda: os.getenv("RETRIEVAL_CHUNKING_STRATEGY", "structure"))
    rrf_constant: int = field(default_factory=lambda: int(os.getenv("RETRIEVAL_RRF_CONSTANT", "60")))
    development_mode: bool = field(default_factory=lambda: os.getenv("APP_ENV", "production").lower() in {"development", "local"})

    def __post_init__(self) -> None:
        if self.embedding_model not in {
            "local-hash-v1", "BAAI/bge-small-en-v1.5", "sentence-transformers/all-MiniLM-L6-v2",
        }:
            raise ValueError("Unsupported retrieval embedding model")
        if self.rrf_constant < 1:
            raise ValueError("RRF constant must be positive")
        if self.chunk_size < 20 or self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            raise ValueError("Invalid retrieval chunk size or overlap")
        if self.chunking_strategy not in {"structure", "fixed"}:
            raise ValueError("Invalid retrieval chunking strategy")
