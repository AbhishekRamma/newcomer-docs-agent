"""Local embeddings (BAAI/bge-small-en-v1.5) with an on-disk cache.

`EMBED_PROVIDER=local` computes missing vectors with sentence-transformers on CPU.
`EMBED_PROVIDER=cached` only replays vectors already in the cache (used by CI, so CI
needs neither the model download nor torch).
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from pathlib import Path

import numpy as np

from src.config import EMBED_DIM, EMBED_MODEL

# bge v1.5 recommends this instruction for short retrieval queries (not for passages).
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
BATCH_SIZE = 16  # small batches: the box has ~3 GB of free RAM


class EmbeddingCacheMiss(RuntimeError):
    pass


def cache_key(text: str, kind: str) -> str:
    return hashlib.sha256(f"{EMBED_MODEL}\0{kind}\0{text}".encode()).hexdigest()


class Embedder:
    def __init__(self, cache_path: str | Path, provider: str = "local"):
        self.provider = provider
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        # FastAPI runs sync endpoints in a thread pool, so the cache connection is shared
        # across threads; a lock serialises access instead of sqlite's same-thread check.
        self.db = sqlite3.connect(str(self.cache_path), check_same_thread=False)
        self._lock = threading.RLock()
        self.db.execute("CREATE TABLE IF NOT EXISTS emb (key TEXT PRIMARY KEY, vec BLOB)")
        self._model = None
        self.hits = 0
        self.misses = 0

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # optional dependency

            self._model = SentenceTransformer(EMBED_MODEL, device="cpu")
        return self._model

    def _get(self, key: str) -> np.ndarray | None:
        row = self.db.execute("SELECT vec FROM emb WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        return np.frombuffer(row[0], dtype=np.float32)

    def embed(self, texts: list[str], kind: str = "passage") -> np.ndarray:
        with self._lock:
            return self._embed(texts, kind)

    def _embed(self, texts: list[str], kind: str) -> np.ndarray:
        if kind not in {"passage", "query"}:
            raise ValueError(kind)
        keys = [cache_key(t, kind) for t in texts]
        out: list[np.ndarray | None] = [self._get(k) for k in keys]
        todo = [i for i, v in enumerate(out) if v is None]
        self.hits += len(texts) - len(todo)
        self.misses += len(todo)
        if todo:
            if self.provider != "local":
                raise EmbeddingCacheMiss(
                    f"{len(todo)} embedding(s) not in cache {self.cache_path} "
                    f"(provider={self.provider})"
                )
            model = self._load_model()
            prefix = QUERY_INSTRUCTION if kind == "query" else ""
            for start in range(0, len(todo), BATCH_SIZE):
                idx = todo[start : start + BATCH_SIZE]
                vecs = model.encode(
                    [prefix + texts[i] for i in idx],
                    batch_size=BATCH_SIZE,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                ).astype(np.float32)
                for i, v in zip(idx, vecs, strict=True):
                    out[i] = v
                    self.db.execute(
                        "INSERT OR REPLACE INTO emb VALUES (?, ?)", (keys[i], v.tobytes())
                    )
                self.db.commit()
        arr = np.vstack(out).astype(np.float32)
        assert arr.shape[1] == EMBED_DIM
        return arr

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed([text], kind="query")[0]

    def export_subset(self, keys: set[str], dest: str | Path) -> int:
        """Copy only the given cache entries to a new sqlite file (for the CI cache)."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        out = sqlite3.connect(str(dest))
        out.execute("CREATE TABLE emb (key TEXT PRIMARY KEY, vec BLOB)")
        n = 0
        for k in sorted(keys):
            row = self.db.execute("SELECT vec FROM emb WHERE key = ?", (k,)).fetchone()
            if row is not None:
                out.execute("INSERT INTO emb VALUES (?, ?)", (k, row[0]))
                n += 1
        out.commit()
        out.execute("VACUUM")
        out.close()
        return n
