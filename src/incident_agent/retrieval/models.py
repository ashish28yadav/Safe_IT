"""Typed knowledge document and retrieval result models."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    title: str
    source: str
    service: str
    category: str
    document_type: str
    content: str


@dataclass(frozen=True)
class DocumentChunk:
    document_id: str
    chunk_id: str
    title: str
    source: str
    service: str
    category: str
    document_type: str
    section: str
    content_hash: str
    content: str

    def metadata(self) -> dict[str, str]:
        return {
            "document_id": self.document_id, "chunk_id": self.chunk_id,
            "title": self.title, "source": self.source, "service": self.service,
            "category": self.category, "document_type": self.document_type,
            "section": self.section, "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class IngestionError:
    filename: str
    error: str


@dataclass(frozen=True)
class IngestionReport:
    documents: tuple[KnowledgeDocument, ...]
    chunks: tuple[DocumentChunk, ...]
    errors: tuple[IngestionError, ...]


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    title: str
    source: str
    service: str
    category: str
    document_type: str
    section: str
    content_hash: str
    content: str
    rank: int
    score: float | None = None


@dataclass(frozen=True)
class SearchResponse:
    query: str
    strategy: Literal["bm25", "vector", "hybrid"]
    bm25: tuple[SearchHit, ...]
    vector: tuple[SearchHit, ...]
    results: tuple[SearchHit, ...]


@dataclass(frozen=True)
class RetrievalHealth:
    vector_ready: bool
    bm25_ready: bool
    document_count: int
    chunk_count: int
    embedding_model: str
    collection_name: str
