"""Retrieval: exact cosine top-k over pgvector, optionally fused with Postgres full-text (RRF)."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass

from src.config import DATA_DIR, Settings, get_settings
from src.db import connect
from src.embed import Embedder

RRF_K = 60
CANDIDATES = 20
_WORD = re.compile(r"[a-z0-9]+")


@dataclass
class Chunk:
    id: str
    source_id: str
    url: str
    title: str
    heading: str
    text: str
    fetched_at: str
    score: float


_COLS = "id, source_id, url, title, heading, text, fetched_at"


def _row(r, score: float) -> Chunk:
    return Chunk(*r[:7], score=float(score))


class Retriever:
    def __init__(self, settings: Settings | None = None, conn=None,
                 embedder: Embedder | None = None):
        self.s = settings or get_settings()
        self.conn = conn or connect(self.s.database_url)
        self.embedder = embedder or Embedder(self.s.embed_cache_path, self.s.embed_provider)

    def vector(self, query: str, k: int) -> list[Chunk]:
        q = self.embedder.embed_query(query)
        # Exact scan (no ANN index) so results are deterministic; ties broken by id.
        rows = self.conn.execute(
            f"SELECT {_COLS}, 1 - (embedding <=> %s) AS sim FROM chunks "
            "WHERE index_name = %s ORDER BY embedding <=> %s, id LIMIT %s",
            (q, self.s.index, q, k),
        ).fetchall()
        return [_row(r, r[7]) for r in rows]

    def keyword(self, query: str, k: int) -> list[Chunk]:
        words = [w for w in _WORD.findall(query.lower()) if len(w) > 1]
        if not words:
            return []
        tsq = " | ".join(words)  # OR of stemmed terms, ranked by ts_rank_cd
        rows = self.conn.execute(
            f"SELECT {_COLS}, ts_rank_cd(tsv, q) AS rank FROM chunks, "
            "to_tsquery('english', %s) q WHERE index_name = %s AND tsv @@ q "
            "ORDER BY rank DESC, id LIMIT %s",
            (tsq, self.s.index, k),
        ).fetchall()
        return [_row(r, r[7]) for r in rows]

    def search(self, query: str, k: int | None = None) -> list[Chunk]:
        k = k or self.s.top_k
        if not self.s.hybrid:
            return self.vector(query, k)
        vec = self.vector(query, CANDIDATES)
        kw = self.keyword(query, CANDIDATES)
        fused: dict[str, float] = {}
        by_id: dict[str, Chunk] = {}
        for ranked in (vec, kw):
            for rank, c in enumerate(ranked, 1):
                fused[c.id] = fused.get(c.id, 0.0) + 1.0 / (RRF_K + rank)
                by_id.setdefault(c.id, c)
        order = sorted(fused, key=lambda i: (-fused[i], i))[:k]
        return [Chunk(**{**asdict(by_id[i]), "score": fused[i]}) for i in order]


def retrieval_metrics(expected_urls: list[str], chunks: list[Chunk]) -> dict:
    """recall@k = share of expected source URLs present among retrieved chunks;
    reciprocal rank = 1/rank of the first chunk from any expected URL (0 if none)."""
    exp = set(expected_urls)
    got = {c.url for c in chunks}
    recall = len(exp & got) / len(exp) if exp else None
    rr = 0.0
    for rank, c in enumerate(chunks, 1):
        if c.url in exp:
            rr = 1.0 / rank
            break
    return {"recall": recall, "rr": rr if exp else None}


def load_questions(name: str) -> list[dict]:
    path = DATA_DIR / "questions" / f"{name}.jsonl"
    return [json.loads(line) for line in path.open() if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser(description="Retrieval-only metrics on dev")
    # the test split is scored only by `evaluate --final`
    ap.add_argument("--split", default="dev", choices=["dev"])
    ap.add_argument("--k", type=int, default=None)
    args = ap.parse_args()
    s = get_settings()
    r = Retriever(s)
    k = args.k or s.top_k
    rows = []
    for q in load_questions(args.split):
        if not q["expected_source_urls"]:
            continue
        m = retrieval_metrics(q["expected_source_urls"], r.search(q["question"], k))
        rows.append(m)
        if m["recall"] < 1:
            print(f"  miss {q['id']} recall={m['recall']:.2f} rr={m['rr']:.2f} "
                  f"{q['question'][:60]}")
    n = len(rows)
    recall = sum(m["recall"] for m in rows) / n
    mrr = sum(m["rr"] for m in rows) / n
    print(f"index={s.index} hybrid={s.hybrid} k={k} n={n} recall@{k}={recall:.3f} MRR={mrr:.3f}")


if __name__ == "__main__":
    main()
