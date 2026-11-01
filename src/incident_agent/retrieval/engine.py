"""Hybrid BM25 and Chroma retrieval with offline-safe embeddings."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import chromadb
from rank_bm25 import BM25Okapi

from incident_agent.config import settings


@dataclass(frozen=True)
class Runbook:
    id: str
    service: str
    title: str
    content: str


RUNBOOKS = [
    Runbook("payment-provider", "payment", "Investigate payment provider errors", "Check gateway timeout rates and provider circuit breaker logs. Confirm dependency health. Prefer failover only after approval; restart only after evidence confirms a stuck process."),
    Runbook("auth-latency", "authentication", "Investigate authentication timeouts", "Compare token validation latency with identity dependency latency. Check timeout and retry logs. Avoid disabling authentication controls."),
    Runbook("notification-queue", "notification", "Drain a notification backlog safely", "Inspect queue depth and consumer throughput. Restore consumer health before draining. Monitor duplicate delivery and rate limits."),
    Runbook("postgres-pool", "postgres", "Recover PostgreSQL connection pool exhaustion", "Check active connections against pool limits. Identify the source before recycling connections. Preserve database state and confirm recovery via telemetry."),
]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _hash_embedding(text: str, dimensions: int = 256) -> list[float]:
    """Stable local vectorizer used when no local transformer model is configured."""
    vector = [0.0] * dimensions
    for token in _tokens(text):
        index = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % dimensions
        vector[index] += 1.0
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / norm for value in vector]


class HybridRetriever:
    def __init__(self) -> None:
        self.runbooks = RUNBOOKS
        self._transformer = None
        if settings.use_local_sentence_transformer:
            from sentence_transformers import SentenceTransformer

            model_path = Path(settings.embedding_model_path)
            if not model_path.exists():
                raise FileNotFoundError(f"Local embedding model not found: {model_path}")
            self._transformer = SentenceTransformer(str(model_path), local_files_only=True)
        self.client = chromadb.EphemeralClient()
        # Ephemeral Chroma clients may share an in-process system; unique names
        # keep repeated agent construction safe (for example, evaluation runs).
        self.collection = self.client.create_collection(f"incident_runbooks_{uuid4().hex}")
        embeddings = [self._embed(book.title + ". " + book.content) for book in self.runbooks]
        self.collection.add(
            ids=[book.id for book in self.runbooks],
            documents=[book.title + ". " + book.content for book in self.runbooks],
            metadatas=[{"service": book.service, "title": book.title} for book in self.runbooks],
            embeddings=embeddings,
        )
        self.bm25 = BM25Okapi([_tokens(book.title + " " + book.content) for book in self.runbooks])

    def _embed(self, text: str) -> list[float]:
        if self._transformer is not None:
            return self._transformer.encode(text, normalize_embeddings=True).tolist()
        return _hash_embedding(text)

    def search(self, query: str, service: str, limit: int = 3) -> list[dict[str, str]]:
        bm25_scores = self.bm25.get_scores(_tokens(query))
        dense = self.collection.query(query_embeddings=[self._embed(query)], n_results=len(self.runbooks))
        dense_distances = dict(zip(dense["ids"][0], dense["distances"][0]))
        maximum = max(bm25_scores) if len(bm25_scores) else 0.0
        ranked: list[tuple[float, Runbook]] = []
        for index, book in enumerate(self.runbooks):
            lexical = float(bm25_scores[index]) / maximum if maximum > 0 else 0.0
            semantic = 1.0 / (1.0 + float(dense_distances.get(book.id, 1.0)))
            service_match = 0.15 if book.service == service else 0.0
            ranked.append((0.55 * lexical + 0.45 * semantic + service_match, book))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [{"id": book.id, "title": book.title, "service": book.service} for _, book in ranked[:limit]]
