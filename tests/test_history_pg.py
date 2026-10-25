"""The migration and the Postgres history store against a real database (skipped if none)."""

from __future__ import annotations

import os
import uuid

import pytest

from src.history import PostgresHistoryStore
from src.migrate import migrate

DB_URL = os.getenv("DATABASE_URL", "postgresql://rag:rag@localhost:5433/rag")


@pytest.fixture(scope="module")
def store() -> PostgresHistoryStore:
    try:
        import psycopg

        psycopg.connect(DB_URL, connect_timeout=2).close()
    except Exception:  # noqa: BLE001 - any connection problem means "no DB here"
        if os.getenv("REQUIRE_PG") == "1":  # set in CI so this can't silently skip
            raise
        pytest.skip("Postgres not reachable")
    migrate(DB_URL)
    assert migrate(DB_URL) == []  # second run applies nothing
    return PostgresHistoryStore(DB_URL)


def test_store_isolates_users(store: PostgresHistoryStore) -> None:
    a, b = f"test-a-{uuid.uuid4()}", f"test-b-{uuid.uuid4()}"
    ids = [store.add(a, f"q{i}", {"answer": f"a{i}", "n": i}, "in_scope") for i in range(3)]
    b_id = store.add(b, "b question", {"answer": "b"}, "out_of_scope")
    try:
        rows, total = store.list(a, limit=2, offset=0)
        assert total == 3
        assert [r.question for r in rows] == ["q2", "q1"]
        assert rows[0].answer == {"answer": "a2", "n": 2}
        rows, _ = store.list(a, limit=2, offset=2)
        assert [r.id for r in rows] == [ids[0]]
        assert store.delete(a, b_id) is False  # not a's row
        assert store.list(b, 10, 0)[1] == 1
        assert store.delete(a, ids[0]) is True
        assert store.delete(a, ids[0]) is False
        assert store.list(a, 10, 0)[1] == 2
    finally:
        for sub, rid in [(a, i) for i in ids] + [(b, b_id)]:
            store.delete(sub, rid)
