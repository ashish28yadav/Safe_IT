from pathlib import Path
import json

import fitz
import pytest

from incident_agent.retrieval.config import RetrievalConfig
from incident_agent.retrieval.documents import DocumentLoader, chunk_documents
from incident_agent.retrieval.engine import RetrievalEngine


def config(tmp_path: Path, knowledge: Path, *, model: str = "local-hash-v1", strategy: str = "structure") -> RetrievalConfig:
    return RetrievalConfig(
        knowledge_base_dir=knowledge, vector_dir=tmp_path / "vectors", bm25_dir=tmp_path / "bm25",
        collection_name="test_ops", embedding_model=model, chunk_size=35, chunk_overlap=8,
        chunking_strategy=strategy,
    )


def test_loads_markdown_text_and_pdf_with_metadata(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    (knowledge / "runbook.md").write_text(
        "# Payment outage\n\n**Document ID:** payment-1\n**Service:** payment-service\n"
        "**Incident category:** availability\n**Document type:** runbook\n\n## Symptoms\nGateway errors rise.",
        encoding="utf-8",
    )
    (knowledge / "notes.txt").write_text(
        "# Database pressure\nDocument ID: db-1\nService: postgres-database\n"
        "Category: capacity\nType: runbook\n\nDisk is nearly full.", encoding="utf-8",
    )
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "# Authentication issue\nDocument ID: auth-1\nService: authentication-service\nCategory: availability\nType: runbook\n\nLogin requests fail.")
    pdf.save(knowledge / "auth.pdf")
    pdf.close()

    documents, errors = DocumentLoader().load(knowledge)
    assert not errors
    assert {document.document_id for document in documents} == {"payment-1", "db-1", "auth-1"}
    assert next(document for document in documents if document.document_id == "payment-1").service == "payment-service"
    assert "Login requests fail" in next(document for document in documents if document.document_id == "auth-1").content


def test_reports_invalid_and_empty_documents_with_filenames(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    (knowledge / "empty.md").write_text("  \n", encoding="utf-8")
    (knowledge / "bad.txt").write_bytes(b"\xff\xfe")
    docs, errors = DocumentLoader().load(knowledge)
    assert not docs
    assert {error.filename for error in errors} == {"empty.md", "bad.txt"}
    assert all(error.error for error in errors)


def test_chunking_overlap_stable_ids_and_metadata(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    file = knowledge / "guide.md"
    file.write_text(
        "# Guide\nDocument ID: guide-1\nService: payment-service\nCategory: availability\nType: runbook\n\n"
        "## Symptoms\n" + " ".join(f"term{i}" for i in range(90)) + "\n\n## Recovery\nCheck status.",
        encoding="utf-8",
    )
    documents, _ = DocumentLoader().load(knowledge)
    first = chunk_documents(documents, chunk_size=30, overlap=10, strategy="structure")
    second = chunk_documents(documents, chunk_size=30, overlap=10, strategy="structure")
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert len(first) >= 4
    assert first[0].metadata()["document_id"] == "guide-1"
    assert first[0].metadata()["source"] == "guide.md"
    assert first[0].section == "Symptoms"
    assert first[0].content_hash
    assert set(first[0].content.split()) & set(first[1].content.split())


def test_bm25_vector_hybrid_filters_and_unique_fused_results(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    (knowledge / "payment.md").write_text(
        "# Payment pool exhaustion\nDocument ID: payment-pool\nService: payment-service\nCategory: database\nType: runbook\n\n"
        "## Diagnosis\nPayment request database connection pool exhausted connection timeout.", encoding="utf-8",
    )
    (knowledge / "dns.md").write_text(
        "# DNS failures\nDocument ID: dns-failure\nService: general\nCategory: network\nType: runbook\n\n"
        "## Diagnosis\nDNS resolver cannot resolve dependency names.", encoding="utf-8",
    )
    engine = RetrievalEngine(config(tmp_path, knowledge))
    report = engine.initialize()
    assert len(report.documents) == 2
    bm = engine.search("database connection pool exhaustion", strategy="bm25", top_k=2)
    vector = engine.search("database connection pool exhaustion", strategy="vector", top_k=2)
    hybrid = engine.search("database connection pool exhaustion", strategy="hybrid", top_k=2)
    assert bm.results[0].document_id == "payment-pool"
    assert vector.results
    assert hybrid.bm25 and hybrid.vector
    assert len({hit.chunk_id for hit in hybrid.results}) == len(hybrid.results)
    filtered = engine.search("resolver", strategy="hybrid", service="payment-service", top_k=5)
    assert all(hit.service == "payment-service" for hit in filtered.results)
    assert engine.health().document_count == 2


def test_collection_rejects_incompatible_embedding_model(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    (knowledge / "one.md").write_text("# One\nDocument ID: one\n\n## Text\nA database alert.", encoding="utf-8")
    first = RetrievalEngine(config(tmp_path, knowledge, model="local-hash-v1"))
    first.initialize()
    first.close()
    incompatible = RetrievalEngine(config(tmp_path, knowledge, model="BAAI/bge-small-en-v1.5"))
    with pytest.raises(ValueError, match="uses embedding model"):
        incompatible.initialize()


def test_index_persists_across_engine_restart_and_empty_query(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    (knowledge / "one.md").write_text("# Pool\nDocument ID: pool\n\n## Symptoms\nDatabase pool exhausted.", encoding="utf-8")
    settings = config(tmp_path, knowledge)
    first = RetrievalEngine(settings)
    first.initialize()
    first.close()
    second = RetrievalEngine(settings)
    second.initialize()
    result = second.search("database pool exhausted", strategy="hybrid")
    assert result.results and result.results[0].document_id == "pool"
    assert second.search("  ").results == ()


def test_empty_index_is_ready_and_returns_no_hits(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    engine = RetrievalEngine(config(tmp_path, knowledge))
    engine.initialize()
    assert engine.health().chunk_count == 0
    assert engine.search("anything", strategy="hybrid").results == ()


def test_repeated_rebuild_is_idempotent_and_chunk_ids_match_indexes(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    (knowledge / "one.md").write_text(
        "# Pool\nDocument ID: pool\nService: postgres\nCategory: database\nType: runbook\n\n"
        "## Symptoms\nPostgreSQL connection pool is exhausted.", encoding="utf-8",
    )
    engine = RetrievalEngine(config(tmp_path, knowledge))
    first = engine.initialize()
    first_ids = {chunk.chunk_id for chunk in first.chunks}
    second = engine.initialize(force_rebuild=True)
    assert {chunk.chunk_id for chunk in second.chunks} == first_ids
    assert engine.health().chunk_count == len(first_ids)
    assert first.documents[0].service == "postgres-database"


def test_vector_retrieval_accepts_mock_embeddings(tmp_path: Path) -> None:
    knowledge = tmp_path / "kb"
    knowledge.mkdir()
    (knowledge / "one.md").write_text("# One\nDocument ID: one\n\n## Text\nPool exhausted.", encoding="utf-8")
    engine = RetrievalEngine(config(tmp_path, knowledge), embedding_function=lambda values: [[1.0, 0.0] for _ in values])
    engine.initialize()
    assert engine.search("pool", strategy="vector").results[0].document_id == "one"


def test_evaluation_queries_reference_known_documents() -> None:
    root = Path(__file__).resolve().parents[1]
    query_path = root / "src" / "incident_agent" / "evaluation" / "retrieval_queries.json"
    queries = json.loads(query_path.read_text(encoding="utf-8"))
    documents, errors = DocumentLoader().load(root / "knowledge_base")
    known_ids = {document.document_id for document in documents}
    assert not errors
    assert len(queries) >= 30
    assert all(query["query"].strip() and set(query["relevant_document_ids"]) <= known_ids for query in queries)
