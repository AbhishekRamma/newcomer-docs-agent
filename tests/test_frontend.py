"""The chat page and its static assets are served without needing the DB or a model."""

import re

from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)


def test_root_serves_chat_page():
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert 'id="ask"' in html and 'id="q"' in html
    assert "not legal, tax or immigration advice" in html.lower()
    for topic in ("SIN", "OHIP", "Bank account", "First tax return", "Driver's licence"):
        assert f">{topic}</button>" in html


def test_static_assets_referenced_and_served():
    html = client.get("/").text
    assets = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
    assert {"/static/app.css", "/static/app.js"} <= set(assets)
    for path in assets:
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.content


def test_page_loads_nothing_from_other_origins():
    for path in ("/", "/static/app.css", "/static/app.js"):
        body = client.get(path).text
        assert not re.search(r'(?:src|href)="https?://', body), path
        assert "@import" not in body and "fonts.googleapis" not in body


def test_missing_static_file_is_404():
    assert client.get("/static/nope.js").status_code == 404


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
