import pytest

from incident_agent.evaluation.retrieval import _document_ranking, _metrics
from incident_agent.retrieval.models import SearchHit


def hit(document_id: str, rank: int, chunk_id: str | None = None) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id or f"{document_id}-{rank}", document_id=document_id,
        title=document_id, source=f"{document_id}.md", service="general",
        category="test", document_type="runbook", section="test",
        content_hash="hash", content="test", rank=rank,
    )


def test_standard_metrics_have_expected_values_for_one_relevant_document() -> None:
    result = _metrics(
        [[hit("irrelevant", 1), hit("relevant", 2), hit("other", 3)]],
        [{"relevant"}], [10.0],
    )
    assert result["recall_at_1"] == 0.0
    assert result["recall_at_3"] == 1.0
    assert result["recall_at_5"] == 1.0
    assert result["mrr"] == 0.5


def test_metrics_macro_average_each_query_independently() -> None:
    result = _metrics(
        [[hit("a", 1)], [hit("x", 1), hit("b", 2), hit("y", 3)]],
        [{"a"}, {"b", "c"}], [5.0, 15.0],
    )
    assert result["recall_at_1"] == 0.5
    assert result["recall_at_3"] == 0.75
    assert result["recall_at_5"] == 0.75
    assert result["mrr"] == 0.75
    assert result["query_latency_ms_mean"] == 10.0


def test_duplicate_chunks_are_collapsed_before_recall_and_mrr() -> None:
    result = _metrics(
        [[hit("irrelevant", 1), hit("irrelevant", 2), hit("relevant", 3)]],
        [{"relevant"}], [10.0],
    )
    assert result["recall_at_1"] == 0.0
    assert result["recall_at_3"] == 1.0
    assert result["mrr"] == 0.5


def test_equal_rank_ties_are_resolved_stably_by_document_then_chunk_id() -> None:
    assert _document_ranking([hit("z-doc", 1), hit("a-doc", 1)]) == ["a-doc", "z-doc"]


def test_multi_relevance_explains_mrr_one_with_recall_at_one_below_one() -> None:
    result = _metrics(
        [[hit("relevant-a", 1), hit("irrelevant", 2)]],
        [{"relevant-a", "relevant-b"}], [10.0],
    )
    assert result["recall_at_1"] == 0.5
    assert result["mrr"] == 1.0


@pytest.mark.parametrize("rankings,relevance,latencies", [
    ([], [], []),
    ([[hit("a", 1)]], [], [1.0]),
    ([[hit("a", 1)]], [set()], [1.0]),
    ([[hit("a", 1)]], [{"a"}], []),
])
def test_metrics_reject_mismatched_or_missing_ground_truth(rankings, relevance, latencies) -> None:
    with pytest.raises(ValueError):
        _metrics(rankings, relevance, latencies)
