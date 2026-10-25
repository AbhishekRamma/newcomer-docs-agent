"""Per-user question history in Postgres (table created by src/migrations/001_*.sql)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


@dataclass
class HistoryRow:
    id: int
    question: str
    answer: dict[str, Any]
    route: str
    created_at: datetime


class HistoryStore(Protocol):
    def add(self, user_sub: str, question: str, answer: dict[str, Any], route: str) -> int: ...

    def list(self, user_sub: str, limit: int, offset: int) -> tuple[list[HistoryRow], int]: ...

    def delete(self, user_sub: str, row_id: int) -> bool: ...


class PostgresHistoryStore:
    """Every query filters on user_sub, so one user can never read or delete another's rows."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _conn(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, autocommit=True, row_factory=dict_row)

    def add(self, user_sub: str, question: str, answer: dict[str, Any], route: str) -> int:
        with self._conn() as c:
            row = c.execute(
                "INSERT INTO question_history (user_sub, question, answer_json, route) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (user_sub, question, Jsonb(answer), route),
            ).fetchone()
        assert row is not None
        return int(row["id"])

    def list(self, user_sub: str, limit: int, offset: int) -> tuple[list[HistoryRow], int]:
        with self._conn() as c:
            total = c.execute(
                "SELECT count(*) AS n FROM question_history WHERE user_sub = %s", (user_sub,)
            ).fetchone()
            rows = c.execute(
                "SELECT id, question, answer_json, route, created_at FROM question_history "
                "WHERE user_sub = %s ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
                (user_sub, limit, offset),
            ).fetchall()
        items = [
            HistoryRow(r["id"], r["question"], r["answer_json"], r["route"], r["created_at"])
            for r in rows
        ]
        return items, int(total["n"]) if total else 0

    def delete(self, user_sub: str, row_id: int) -> bool:
        with self._conn() as c:
            cur = c.execute(
                "DELETE FROM question_history WHERE id = %s AND user_sub = %s",
                (row_id, user_sub),
            )
            return cur.rowcount == 1
