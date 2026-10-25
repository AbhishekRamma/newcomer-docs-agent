import sqlite3
import struct

import pytest

from src.evaluate import has_repeat
from src.rerank import RerankCacheMiss, Reranker, rerank_key


def _seed(path, model, query, scores):
    db = sqlite3.connect(str(path))
    db.execute("CREATE TABLE IF NOT EXISTS score (key TEXT PRIMARY KEY, val BLOB)")
    for passage, s in scores.items():
        db.execute("INSERT INTO score VALUES (?, ?)",
                   (rerank_key(model, query, passage), struct.pack("<d", s)))
    db.commit()
    db.close()


def test_cached_scores_replay_without_model(tmp_path):
    path = tmp_path / "r.sqlite"
    _seed(path, "m", "q", {"a": 0.25, "b": -1.5})
    r = Reranker("m", path, provider="cached")
    assert r.scores("q", ["b", "a"]) == [-1.5, 0.25]
    n = r.export_subset(r.used_keys, tmp_path / "sub.sqlite")
    assert n == 2
    assert Reranker("m", tmp_path / "sub.sqlite", "cached").scores("q", ["a"]) == [0.25]


def test_cache_miss_raises_in_cached_mode(tmp_path):
    r = Reranker("m", tmp_path / "r.sqlite", provider="cached")
    with pytest.raises(RerankCacheMiss):
        r.scores("q", ["unseen"])


def test_key_depends_on_model_query_and_passage():
    k = rerank_key("m", "q", "p")
    assert k != rerank_key("m2", "q", "p") != rerank_key("m", "q2", "p")
    assert k != rerank_key("m", "q", "p2")


def test_has_repeat():
    assert has_repeat("Bring your passport to apply [a](u). To apply, bring your passport [b](u).")
    assert not has_repeat("The fee is $10 [a](u). The card lasts five years [b](u).")
