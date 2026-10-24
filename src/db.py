"""PostgreSQL + pgvector storage for chunks."""

from __future__ import annotations

import psycopg
from pgvector.psycopg import register_vector

from src.config import EMBED_DIM

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunks (
    id          TEXT PRIMARY KEY,
    index_name  TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    url         TEXT NOT NULL,
    title       TEXT NOT NULL,
    heading     TEXT NOT NULL,
    text        TEXT NOT NULL,
    n_tokens    INTEGER NOT NULL,
    fetched_at  TEXT NOT NULL,
    embedding   vector({EMBED_DIM}) NOT NULL,
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', heading || ' ' || text)) STORED
);
CREATE INDEX IF NOT EXISTS chunks_index_name ON chunks (index_name);
CREATE INDEX IF NOT EXISTS chunks_tsv ON chunks USING gin (tsv);
"""


def connect(url: str) -> psycopg.Connection:
    conn = psycopg.connect(url, autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def init_schema(conn: psycopg.Connection) -> None:
    conn.execute(SCHEMA)


def replace_index(conn: psycopg.Connection, index_name: str, rows: list[dict]) -> None:
    """Delete and re-insert all chunks of one index (e.g. `c500`) in one transaction."""
    with conn.transaction():
        conn.execute("DELETE FROM chunks WHERE index_name = %s", (index_name,))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (id, index_name, source_id, url, title, heading, text, "
                "n_tokens, fetched_at, embedding) VALUES "
                "(%(id)s, %(index_name)s, %(source_id)s, %(url)s, %(title)s, %(heading)s, "
                "%(text)s, %(n_tokens)s, %(fetched_at)s, %(embedding)s)",
                rows,
            )
