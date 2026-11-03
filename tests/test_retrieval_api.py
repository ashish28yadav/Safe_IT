from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from incident_agent.api.app import create_app
from incident_agent.retrieval.config import RetrievalConfig
from incident_agent.retrieval.engine import RetrievalEngine

ROOT = Path(__file__).resolve().parents[1]


def make_client(tmp_path: Path, *, development: bool = False) -> tuple[TestClient, RetrievalEngine]:
    engine = RetrievalEngine(RetrievalConfig(
        knowledge_base_dir=ROOT / "knowledge_base", vector_dir=tmp_path / "chroma",
        bm25_dir=tmp_path / "bm25", collection_name="api_test",
        embedding_model="local-hash-v1", development_mode=development,
    ))
    database_url = f"sqlite:///{(tmp_path / 'incidents.db').as_posix()}"
    return TestClient(create_app(database_url=database_url, retrieval_engine=engine)), engine


def test_retrieval_health_and_search_response_schema(tmp_path: Path) -> None:
    client, _engine = make_client(tmp_path)
    with client:
        health = client.get("/api/v1/retrieval/health")
        assert health.status_code == 200
        body = health.json()
        assert body["vector_store_ready"] and body["bm25_index_ready"]
        assert body["indexed_document_count"] == 31
        assert body["indexed_chunk_count"] > body["indexed_document_count"]
        assert body["embedding_model"] == "local-hash-v1"
        assert "path" not in str(body).casefold()

        response = client.post("/api/v1/retrieval/search", json={
            "query": "PostgreSQL connection pool exhaustion", "top_k": 3, "strategy": "hybrid",
            "service": "postgres-database", "category": "database", "document_type": "runbook",
        })
        assert response.status_code == 200
        result = response.json()
        assert len(result["results"]) <= 3
        assert result["bm25_ranking"] and result["vector_ranking"]
        assert result["results"][0]["service"] == "postgres-database"
        assert {"chunk_id", "document_id", "source", "section", "content_hash", "rank"} <= set(result["results"][0])


@pytest.mark.parametrize("payload", [
    {"query": ""}, {"query": "ok", "top_k": 0}, {"query": "ok", "top_k": 100},
    {"query": "ok", "strategy": "other"}, {"query": "ok", "not_allowed": True},
    {"query": "x" * 2001},
])
def test_search_validates_request(tmp_path: Path, payload: dict[str, object]) -> None:
    client, _engine = make_client(tmp_path)
    with client:
        assert client.post("/api/v1/retrieval/search", json=payload).status_code == 422


def test_index_rebuild_is_forbidden_outside_explicit_local_mode(tmp_path: Path) -> None:
    client, _engine = make_client(tmp_path)
    with client:
        response = client.post("/api/v1/retrieval/index/rebuild")
    assert response.status_code == 403


def test_api_retrieval_persists_across_application_restart(tmp_path: Path) -> None:
    client, _engine = make_client(tmp_path)
    with client:
        first = client.post("/api/v1/retrieval/search", json={
            "query": "database connection pool exhaustion", "strategy": "bm25", "top_k": 3,
        }).json()
    restarted, _engine2 = make_client(tmp_path)
    with restarted:
        health = restarted.get("/api/v1/retrieval/health").json()
        second = restarted.post("/api/v1/retrieval/search", json={
            "query": "database connection pool exhaustion", "strategy": "bm25", "top_k": 3,
        }).json()
    assert health["indexed_chunk_count"] > 0
    assert [hit["chunk_id"] for hit in first["results"]] == [hit["chunk_id"] for hit in second["results"]]


def test_local_development_rebuild_is_available_and_reports_ingestion(tmp_path: Path) -> None:
    client, _engine = make_client(tmp_path, development=True)
    with client:
        response = client.post("/api/v1/retrieval/index/rebuild")
    assert response.status_code == 200
    assert response.json()["indexed_document_count"] == 31
    assert response.json()["error_count"] == 0


def test_search_errors_return_consistent_service_unavailable(tmp_path: Path) -> None:
    client, engine = make_client(tmp_path)
    engine.search = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("index unavailable"))  # type: ignore[method-assign]
    with client:
        response = client.post("/api/v1/retrieval/search", json={"query": "database", "strategy": "bm25"})
    assert response.status_code == 503
    assert response.json() == {"detail": "Retrieval index unavailable"}


def test_openapi_documents_retrieval_endpoints(tmp_path: Path) -> None:
    client, _engine = make_client(tmp_path)
    with client:
        paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/retrieval/search" in paths
    assert "/api/v1/retrieval/health" in paths
    assert "/api/v1/retrieval/index/rebuild" in paths
