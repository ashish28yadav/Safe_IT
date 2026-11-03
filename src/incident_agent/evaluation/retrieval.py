"""Offline retrieval benchmark for BM25, local transformers and RRF."""

from __future__ import annotations

import csv
import gc
import json
import math
import os
import statistics
import time
from pathlib import Path

from incident_agent.retrieval.config import RetrievalConfig
from incident_agent.retrieval.engine import RetrievalEngine
from incident_agent.retrieval.models import SearchHit

ROOT = Path(__file__).resolve().parents[3]
QUERY_FILE = Path(__file__).with_name("retrieval_queries.json")
OUTPUT = Path(os.getenv("RETRIEVAL_EVALUATION_OUTPUT", str(ROOT / "evaluation" / "retrieval")))
CONFIGURATIONS = {
    "E1": ("bm25", "local-hash-v1", "BM25 only"),
    "E2": ("vector", "sentence-transformers/all-MiniLM-L6-v2", "MiniLM vector only"),
    "E3": ("vector", "BAAI/bge-small-en-v1.5", "BGE vector only"),
    "E4": ("hybrid", "sentence-transformers/all-MiniLM-L6-v2", "BM25 + MiniLM hybrid"),
    "E5": ("hybrid", "BAAI/bge-small-en-v1.5", "BM25 + BGE hybrid"),
}


def _reciprocal_rank(ids: list[str], relevant: set[str]) -> float:
    for rank, item_id in enumerate(ids, 1):
        if item_id in relevant:
            return 1.0 / rank
    return 0.0


def _document_ranking(hits: list[SearchHit]) -> list[str]:
    """Collapse chunk hits to a stable first-seen document ranking."""
    ordered_hits = sorted(hits, key=lambda hit: (hit.rank, hit.document_id, hit.chunk_id))
    seen: set[str] = set()
    ranking: list[str] = []
    for hit in ordered_hits:
        if hit.document_id not in seen:
            seen.add(hit.document_id)
            ranking.append(hit.document_id)
    return ranking


def _metrics(hits: list[list[SearchHit]], relevant: list[set[str]], latencies: list[float]) -> dict[str, float]:
    if not hits or len(hits) != len(relevant) or len(hits) != len(latencies):
        raise ValueError("Each query must have one ranking, non-empty relevance set, and latency measurement")
    if any(not expected for expected in relevant):
        raise ValueError("Each benchmark query must have at least one relevant document ID")
    rankings = [_document_ranking(query_hits) for query_hits in hits]
    size = len(rankings)
    result: dict[str, float] = {}
    for at_k in (1, 3, 5):
        result[f"recall_at_{at_k}"] = sum(
            len(set(ranking[:at_k]) & wanted) / len(wanted)
            for ranking, wanted in zip(rankings, relevant)
        ) / size
    # Recall and MRR use the same deduplicated document-level rankings and macro-average per query.
    result["mrr"] = sum(_reciprocal_rank(ranking, wanted)
                        for ranking, wanted in zip(rankings, relevant)) / size
    result["query_latency_ms_mean"] = statistics.fmean(latencies) if latencies else 0.0
    result["query_latency_ms_p95"] = sorted(latencies)[math.ceil(len(latencies) * .95) - 1]
    return result


def run_evaluation() -> list[dict[str, object]]:
    queries = json.loads(QUERY_FILE.read_text(encoding="utf-8"))
    OUTPUT.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for strategy in ("structure", "fixed"):
        for code, (mode, model, name) in CONFIGURATIONS.items():
            model_env = "EVAL_MINILM_MODEL_PATH" if "MiniLM" in model else "EVAL_BGE_MODEL_PATH"
            model_path = os.getenv(model_env, "")
            if model != "local-hash-v1" and not (model_path and Path(model_path).is_dir()):
                results.append({
                    "configuration": code, "name": name, "chunking": strategy,
                    "embedding_model": model,
                    "status": "not_run", "reason": f"No local model provided via {model_env}; network downloads are disabled.",
                })
                continue
            # Chroma's Windows HNSW index may retain file handles until process exit;
            # keep these disposable indexes under the ignored workspace temp directory.
            root = ROOT / ".pytest-tmp" / "retrieval-evaluation" / f"{code.lower()}-{strategy}"
            config = RetrievalConfig(
                knowledge_base_dir=ROOT / "knowledge_base", vector_dir=root / "chroma",
                bm25_dir=root / "bm25", collection_name=f"eval_{code.lower()}_{strategy}",
                embedding_model=model, embedding_model_path=model_path,
                chunk_size=220, chunk_overlap=40, chunking_strategy=strategy,
            )
            engine = RetrievalEngine(config)
            try:
                start = time.perf_counter()
                # Always clear and rebuild for an indexing-time measurement; do not
                # accidentally report an incremental/no-op warm-start as full indexing.
                report = engine.initialize(force_rebuild=True)
                index_seconds = time.perf_counter() - start
                per_query: list[list[SearchHit]] = []
                latencies: list[float] = []
                relevant_ids: list[set[str]] = []
                for record in queries:
                    query_start = time.perf_counter()
                    corpus_chunk_count = max(1, len(report.chunks))
                    response = engine.search(
                        record["query"], strategy=mode,
                        top_k=corpus_chunk_count, candidate_count=corpus_chunk_count,
                    )
                    latencies.append((time.perf_counter() - query_start) * 1000)
                    per_query.append(list(response.results))
                    relevant_ids.append(set(record["relevant_document_ids"]))
                metrics = _metrics(per_query, relevant_ids, latencies)
                results.append({
                    "configuration": code, "name": name, "embedding_model": model,
                    "chunking": strategy, "status": "completed", "query_count": len(queries),
                    "document_count": len(report.documents), "chunk_count": len(report.chunks),
                    "indexing_time_seconds": index_seconds, **metrics,
                })
            except Exception as exc:
                detail = str(exc).replace(model_path, "<local model>") if model_path else str(exc)
                results.append({
                    "configuration": code, "name": name, "embedding_model": model,
                    "chunking": strategy, "status": "failed",
                    "reason": f"{type(exc).__name__}: {detail[:300]}",
                })
            finally:
                engine.close()
            gc.collect()
    (OUTPUT / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    with (OUTPUT / "results.csv").open("w", newline="", encoding="utf-8") as file:
        columns = sorted({key for row in results for key in row})
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(results)
    lines = [
        "# Retrieval Evaluation", "",
        "Thirty manually reviewed queries use relevant document IDs from `retrieval_queries.json`. Chunk rankings are deduplicated by document ID before all metrics are computed; Recall@K and MRR therefore use the same document ranking. Recall is macro-averaged per query as retrieved relevant documents divided by the query's relevant document count. MRR is macro-averaged reciprocal rank of the first relevant document. Because some queries have multiple relevant documents, MRR=1.0 can coexist with Recall@1 below 1.0 when each top-ranked document is relevant but not every relevant document is retrieved. Each configuration is run with both fixed and structure-aware chunking.", "",
        "Transformer evaluations run only when local model directories are provided. No model downloads are performed.", "",
        "| Config | Embedding | Chunking | Status | Recall@1 | Recall@3 | Recall@5 | MRR | Mean latency (ms) | Index time (s) | Notes |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in results:
        lines.append(
            f"| {row['configuration']} | {row.get('embedding_model', '—')} | {row['chunking']} | {row['status']} | "
            f"{row.get('recall_at_1', '—')} | {row.get('recall_at_3', '—')} | {row.get('recall_at_5', '—')} | "
            f"{row.get('mrr', '—')} | {row.get('query_latency_ms_mean', '—')} | "
            f"{row.get('indexing_time_seconds', '—')} | {row.get('reason', '')} |"
        )
    (OUTPUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results


if __name__ == "__main__":
    for result in run_evaluation():
        print(result)
