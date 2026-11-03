"""Versioned, read-only retrieval endpoints and local-only index rebuild."""

from typing import Literal
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from incident_agent.api.dependencies import get_retrieval_engine
from incident_agent.retrieval.engine import RetrievalEngine

router = APIRouter(prefix="/api/v1/retrieval", tags=["Retrieval v1"])
logger = logging.getLogger(__name__)


class RetrievalSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    candidate_count: int | None = Field(default=None, ge=1, le=100)
    strategy: Literal["bm25", "vector", "hybrid"] = "hybrid"
    service: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    document_type: str | None = Field(default=None, max_length=50)


class RetrievalHitResponse(BaseModel):
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


class RetrievalSearchResponse(BaseModel):
    query: str
    strategy: str
    bm25_ranking: list[RetrievalHitResponse]
    vector_ranking: list[RetrievalHitResponse]
    results: list[RetrievalHitResponse]


class RetrievalHealthResponse(BaseModel):
    vector_store_ready: bool
    bm25_index_ready: bool
    indexed_document_count: int
    indexed_chunk_count: int
    embedding_model: str
    collection_name: str


class RebuildResponse(BaseModel):
    indexed_document_count: int
    indexed_chunk_count: int
    error_count: int
    errors: list[dict[str, str]]


@router.get("/health", response_model=RetrievalHealthResponse, summary="Inspect retrieval index readiness")
def retrieval_health(
    response: Response,
    engine: RetrievalEngine = Depends(get_retrieval_engine),
) -> RetrievalHealthResponse:
    health = engine.health()
    if not health.vector_ready or not health.bm25_ready:
        response.status_code = 503
    return RetrievalHealthResponse(
        vector_store_ready=health.vector_ready, bm25_index_ready=health.bm25_ready,
        indexed_document_count=health.document_count, indexed_chunk_count=health.chunk_count,
        embedding_model=health.embedding_model, collection_name=health.collection_name,
    )


@router.post("/search", response_model=RetrievalSearchResponse, summary="Search operational knowledge")
def search(
    request: RetrievalSearchRequest,
    engine: RetrievalEngine = Depends(get_retrieval_engine),
) -> RetrievalSearchResponse:
    try:
        response = engine.search(
            request.query, top_k=request.top_k, strategy=request.strategy,
            service=request.service, category=request.category, document_type=request.document_type,
            candidate_count=request.candidate_count,
        )
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        logger.warning("Retrieval request unavailable: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Retrieval index unavailable") from exc
    except Exception as exc:
        logger.exception("Unexpected retrieval search failure")
        raise HTTPException(status_code=503, detail="Retrieval index unavailable") from exc
    return RetrievalSearchResponse(
        query=response.query, strategy=response.strategy,
        bm25_ranking=[RetrievalHitResponse(**hit.__dict__) for hit in response.bm25],
        vector_ranking=[RetrievalHitResponse(**hit.__dict__) for hit in response.vector],
        results=[RetrievalHitResponse(**hit.__dict__) for hit in response.results],
    )


@router.post("/index/rebuild", response_model=RebuildResponse, summary="Rebuild local retrieval indexes")
def rebuild(
    engine: RetrievalEngine = Depends(get_retrieval_engine),
) -> RebuildResponse:
    if not engine.config.development_mode:
        raise HTTPException(status_code=403, detail="Index rebuild is available only in local development mode")
    try:
        report = engine.initialize(force_rebuild=True)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        logger.warning("Retrieval rebuild unavailable: %s", type(exc).__name__)
        raise HTTPException(status_code=503, detail="Retrieval index rebuild failed") from exc
    except Exception as exc:
        logger.exception("Unexpected retrieval rebuild failure")
        raise HTTPException(status_code=503, detail="Retrieval index rebuild failed") from exc
    return RebuildResponse(
        indexed_document_count=len(report.documents), indexed_chunk_count=len(report.chunks),
        error_count=len(report.errors), errors=[{"filename": error.filename, "error": error.error} for error in report.errors],
    )
