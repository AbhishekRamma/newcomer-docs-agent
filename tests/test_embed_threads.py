"""Regression test for the embedding cache used from FastAPI's thread pool."""


def test_embedder_cache_usable_from_another_thread(tmp_path):
    """Regression: /ask runs in FastAPI's thread pool, so the sqlite cache must cross threads."""
    import threading

    import numpy as np

    from src.config import EMBED_DIM
    from src.embed import Embedder, EmbeddingCacheMiss, cache_key

    e = Embedder(tmp_path / "c.sqlite", provider="cached")
    vec = np.ones(EMBED_DIM, dtype=np.float32)
    e.db.execute("INSERT INTO emb VALUES (?, ?)", (cache_key("hi", "query"), vec.tobytes()))
    e.db.commit()
    errors: list[BaseException] = []

    def worker():
        try:
            assert e.embed_query("hi").shape == (EMBED_DIM,)
            try:
                e.embed_query("not cached")
            except EmbeddingCacheMiss:
                pass
        except BaseException as exc:  # noqa: BLE001 - surface any thread error to the test
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert not errors
