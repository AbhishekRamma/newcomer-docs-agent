from src.retrieve import Chunk, retrieval_metrics


def _c(url):
    return Chunk("id", "s", url, "t", "h", "x", "d", 0.0)


def test_recall_and_reciprocal_rank():
    m = retrieval_metrics(["a", "b"], [_c("z"), _c("b"), _c("q")])
    assert m == {"recall": 0.5, "rr": 0.5}
    assert retrieval_metrics(["a"], [_c("z")]) == {"recall": 0.0, "rr": 0.0}
    assert retrieval_metrics([], [_c("z")]) == {"recall": None, "rr": None}
