"""Apply the plain-SQL migrations in `src/migrations/` in file-name order, once each.

Usage: python -m src.migrate   (uses DATABASE_URL)

Applied versions are recorded in `schema_migrations`; an advisory lock stops two starting
containers from applying the same file at once.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg

from src.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
LOCK_ID = 7_202_610_24


def pending(conn: psycopg.Connection) -> list[Path]:
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    return [p for p in sorted(MIGRATIONS_DIR.glob("*.sql")) if p.stem not in done]


def migrate(database_url: str) -> list[str]:
    applied: list[str] = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
            )
            for path in pending(conn):
                with conn.transaction():
                    conn.execute(path.read_text())
                    conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)",
                                 (path.stem,))
                applied.append(path.stem)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
    return applied


def main() -> int:
    applied = migrate(get_settings().database_url)
    print(f"migrations applied: {applied or 'none (up to date)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
