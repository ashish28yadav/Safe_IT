"""Persistent BM25, Chroma vector and reciprocal-rank-fusion retrieval."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from functools import wraps
from pathlib import Path
from threading import RLock
from typing import Callable, Literal, TypeVar

import chromadb
from rank_bm25 import BM25Plus

from incident_agent.retrieval.config import RetrievalConfig
from incident_agent.retrieval.documents import ingest_directory
from incident_agent.retrieval.models import (
    DocumentChunk, IngestionReport, RetrievalHealth, SearchHit, SearchResponse,
)

logger = logging.getLogger(__name__)
EmbeddingFunction = Callable[[list[str]], list[list[float]]]
TOKEN_RE = re.compile(r"[a-z0-9_]+")
_Return = TypeVar("_Return")


def _serialized(method: Callable[..., _Return]) -> Callable[..., _Return]:
    """Keep read and rebuild operations consistent across concurrent requests."""
    @wraps(method)
    def wrapped(self: "RetrievalEngine", *args: object, **kwargs: object) -> _Return:
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.casefold())


def hash_embeddings(texts: list[str], dimensions: int = 384) -> list[list[float]]:
    """Deterministic offline embedding fallback with no external model downloads."""
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * dimensions
        for token in tokenize(text):
            index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % dimensions
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        vectors.append([value / norm for value in vector])
    return vectors


class EmbeddingProvider:
    """Lazily load an explicitly configured, local-only transformer model."""

    def __init__(self, config: RetrievalConfig, override: EmbeddingFunction | None = None) -> None:
        self.config = config
        self.override = override
        self._model = None
        self._lock = RLock()

    @property
    def identity(self) -> str:
        if self.override is not None:
            return "test-injected-embedding-v1"
        return self.config.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.override is not None:
            return self.override(texts)
        if self.config.embedding_model == "local-hash-v1":
            return hash_embeddings(texts)
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                model_ref = self.config.embedding_model_path or self.config.embedding_model
                model_path = Path(model_ref)
                if not model_path.exists():
                    raise FileNotFoundError(
                        "Configured embedding model is not available locally; set "
                        "RETRIEVAL_EMBEDDING_MODEL_PATH to a local model directory"
                    )
                self._model = SentenceTransformer(str(model_path), local_files_only=True, device="cpu")
            encoded = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return encoded.tolist()

    def close(self) -> None:
        """Release a locally loaded transformer model from this application lifecycle."""
        with self._lock:
            self._model = None


class RetrievalEngine:
    """Own persistent indexes and expose deterministic, attributed retrieval."""

    def __init__(
        self,
        config: RetrievalConfig | None = None,
        *,
        embedding_function: EmbeddingFunction | None = None,
    ) -> None:
        self.config = config or RetrievalConfig()
        self.embedding = EmbeddingProvider(self.config, embedding_function)
        self._lock = RLock()
        self._initialized = False
        self._chunks: dict[str, DocumentChunk] = {}
        self._bm25: BM25Plus | None = None
        self._vector_collection = None
        self._client = None
        self.last_ingestion_report = IngestionReport((), (), ())

    def initialize(self, *, force_rebuild: bool = False) -> IngestionReport:
        """Load source documents, refresh both indexes, and persist BM25 metadata."""
        with self._lock:
            self.config.vector_dir.mkdir(parents=True, exist_ok=True)
            self.config.bm25_dir.mkdir(parents=True, exist_ok=True)
            report = ingest_directory(
                self.config.knowledge_base_dir, chunk_size=self.config.chunk_size,
                overlap=self.config.chunk_overlap, strategy=self.config.chunking_strategy,
            )
            if report.errors:
                for error in report.errors:
                    logger.error(
                        "Knowledge document ingestion failed",
                        extra={"filename": error.filename, "ingestion_error": error.error},
                    )
            self.last_ingestion_report = report
            self._chunks = {chunk.chunk_id: chunk for chunk in report.chunks}

            self._client = chromadb.PersistentClient(path=str(self.config.vector_dir))
            try:
                collection = self._client.get_collection(self.config.collection_name)
                metadata = collection.metadata or {}
                existing_model = metadata.get("embedding_model")
                if existing_model != self.embedding.identity:
                    raise ValueError(
                        f"Collection '{self.config.collection_name}' uses embedding model "
                        f"{existing_model!r}; configured model is {self.embedding.identity!r}"
                    )
            except ValueError:
                raise
            except Exception as exc:
                # Chroma renamed its not-found exception between major releases.
                if type(exc).__name__ not in {"NotFoundError", "InvalidCollectionException"}:
                    raise
                collection = self._client.create_collection(
                    self.config.collection_name,
                    metadata={"embedding_model": self.embedding.identity, "hnsw:space": "cosine"},
                )
            self._vector_collection = collection
            existing_ids = collection.get(include=[]).get("ids", [])
            desired_ids = set(self._chunks)
            stale_ids = sorted(set(existing_ids) - desired_ids)
            if stale_ids:
                collection.delete(ids=stale_ids)
            current_ids = set(existing_ids) - set(stale_ids)
            new_chunks = [chunk for key, chunk in sorted(self._chunks.items()) if key not in current_ids]
            # Rebuild is deliberately idempotent: unchanged content hashes already exist.
            if force_rebuild:
                new_chunks = [self._chunks[key] for key in sorted(self._chunks)]
                if existing_ids:
                    collection.delete(ids=existing_ids)
            if new_chunks:
                vectors = self.embedding.embed([chunk.title + ". " + chunk.content for chunk in new_chunks])
                collection.upsert(
                    ids=[chunk.chunk_id for chunk in new_chunks],
                    documents=[chunk.content for chunk in new_chunks],
                    metadatas=[chunk.metadata() for chunk in new_chunks], embeddings=vectors,
                )
            self._bm25 = BM25Plus([tokenize(chunk.title + " " + chunk.content) for chunk in self._chunks.values()]) if self._chunks else None
            self._persist_bm25()
            self._initialized = True
            logger.info("Retrieval indexes ready: %d documents, %d chunks", len(report.documents), len(report.chunks))
            return report

    def _persist_bm25(self) -> None:
        target = self.config.bm25_dir / "chunks.json"
        temporary = target.with_suffix(".json.tmp")
        records = [
            {**chunk.metadata(), "content": chunk.content}
            for _, chunk in sorted(self._chunks.items())
        ]
        temporary.write_text(json.dumps({"embedding_model": self.embedding.identity, "chunks": records}, ensure_ascii=False), encoding="utf-8")
        temporary.replace(target)

    @_serialized
    def health(self) -> RetrievalHealth:
        count = len(self._chunks) if self._initialized else 0
        docs = len({chunk.document_id for chunk in self._chunks.values()}) if self._initialized else 0
        return RetrievalHealth(
            vector_ready=self._initialized and self._vector_collection is not None,
            bm25_ready=self._initialized and (self._bm25 is not None or not count),
            document_count=docs, chunk_count=count,
            embedding_model=self.embedding.identity, collection_name=self.config.collection_name,
        )

    @staticmethod
    def _matches(chunk: DocumentChunk, service: str | None, category: str | None, document_type: str | None) -> bool:
        return ((service is None or chunk.service == service.casefold())
                and (category is None or chunk.category == category.casefold())
                and (document_type is None or chunk.document_type == document_type.casefold()))

    def _candidate_chunks(self, service: str | None, category: str | None, document_type: str | None) -> list[DocumentChunk]:
        return [chunk for chunk in self._chunks.values() if self._matches(chunk, service, category, document_type)]

    @_serialized
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        strategy: Literal["bm25", "vector", "hybrid"] = "hybrid",
        service: str | None = None,
        category: str | None = None,
        document_type: str | None = None,
        candidate_count: int | None = None,
    ) -> SearchResponse:
        if top_k < 1 or top_k > 1000:
            raise ValueError("top_k must be between 1 and 1000")
        if strategy not in {"bm25", "vector", "hybrid"}:
            raise ValueError("Unsupported retrieval strategy")
        if not self._initialized:
            self.initialize()
        query_tokens = tokenize(query)
        if not query.strip() or not query_tokens or not self._chunks:
            return SearchResponse(query=query, strategy=strategy, bm25=(), vector=(), results=())
        count = max(top_k, min(candidate_count or top_k * 3, 1000))
        candidates = self._candidate_chunks(service, category, document_type)
        candidate_ids = {chunk.chunk_id for chunk in candidates}
        bm25_hits: list[SearchHit] = []
        vector_hits: list[SearchHit] = []
        if strategy in {"bm25", "hybrid"} and candidates and self._bm25:
            all_chunks = list(self._chunks.values())
            scores = self._bm25.get_scores(query_tokens)
            ranked = sorted(
                ((float(scores[index]), chunk) for index, chunk in enumerate(all_chunks) if chunk.chunk_id in candidate_ids),
                key=lambda pair: (-pair[0], pair[1].chunk_id),
            )[:count]
            bm25_hits = [self._hit(chunk, rank, score) for rank, (score, chunk) in enumerate(ranked, 1)]
        if strategy in {"vector", "hybrid"} and candidates:
            vectors = self.embedding.embed([query])[0]
            where: dict[str, object] = {}
            filters = []
            for key, value in (("service", service), ("category", category), ("document_type", document_type)):
                if value is not None:
                    filters.append({key: value.casefold()})
            if len(filters) == 1:
                where = filters[0]
            elif filters:
                where = {"$and": filters}
            response = self._vector_collection.query(
                query_embeddings=[vectors], n_results=min(count, len(candidates)),
                where=where or None, include=["metadatas", "documents", "distances"],
            )
            ids = response.get("ids", [[]])[0]
            distances = response.get("distances", [[]])[0]
            vector_ids = sorted(
                ((item_id, float(distance)) for item_id, distance in zip(ids, distances)
                 if item_id in self._chunks and item_id in candidate_ids),
                key=lambda pair: (pair[1], pair[0]),
            )
            vector_hits = [self._hit(self._chunks[item_id], rank, None)
                           for rank, (item_id, _distance) in enumerate(vector_ids, 1)]
        if strategy == "bm25":
            results = bm25_hits[:top_k]
        elif strategy == "vector":
            results = vector_hits[:top_k]
        else:
            ranks: dict[str, float] = {}
            for hits in (bm25_hits, vector_hits):
                for hit in hits:
                    ranks[hit.chunk_id] = ranks.get(hit.chunk_id, 0.0) + 1.0 / (self.config.rrf_constant + hit.rank)
            ordered = sorted(ranks.items(), key=lambda item: (-item[1], item[0]))[:top_k]
            results = [self._hit(self._chunks[key], rank, score) for rank, (key, score) in enumerate(ordered, 1)]
        return SearchResponse(query=query, strategy=strategy, bm25=tuple(bm25_hits), vector=tuple(vector_hits), results=tuple(results))

    @staticmethod
    def _hit(chunk: DocumentChunk, rank: int, score: float | None = None) -> SearchHit:
        return SearchHit(
            chunk_id=chunk.chunk_id, document_id=chunk.document_id, title=chunk.title,
            source=chunk.source, service=chunk.service, category=chunk.category,
            document_type=chunk.document_type, section=chunk.section,
            content_hash=chunk.content_hash, content=chunk.content, rank=rank, score=score,
        )

    @_serialized
    def close(self) -> None:
        """Drop direct Chroma references; its persisted data remains untouched."""
        self._client = None
        self._vector_collection = None
        self._initialized = False
        self.embedding.close()


class HybridRetriever:
    """Backward-compatible adapter used by the pre-RAG incident workflow."""

    def __init__(self, engine: RetrievalEngine | None = None) -> None:
        self.engine = engine or RetrievalEngine()

    def search(self, query: str, service: str = "general", limit: int = 3) -> list[dict[str, str]]:
        aliases = {
            "payment": "payment-service", "authentication": "authentication-service",
            "notification": "notification-service", "postgres": "postgres-database",
        }
        response = self.engine.search(query, strategy="hybrid", service=aliases.get(service, service), top_k=limit)
        return [{"id": hit.document_id, "title": hit.title, "service": hit.service} for hit in response.results]
