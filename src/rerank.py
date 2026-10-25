"""Cross-encoder reranking with an on-disk score cache.

The reranker reads the question and each candidate chunk together, which ranks better than
comparing two separately computed vectors. Scores are cached in sqlite keyed by
sha256(model, query, passage), so CI can replay them without torch or the model
(`EMBED_PROVIDER=cached` covers both caches). The cache stores no text.
"""

from __future__ import annotations

import hashlib
import sqlite3
import struct
import threading
from pathlib import Path


class RerankCacheMiss(RuntimeError):
    pass


def rerank_key(model: str, query: str, passage: str) -> str:
    return hashlib.sha256(f"{model}\0{query}\0{passage}".encode()).hexdigest()


class Reranker:
    def __init__(self, model: str, cache_path: str | Path, provider: str = "local"):
        self.model_name = model
        self.provider = provider
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.cache_path), check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS score (key TEXT PRIMARY KEY, val BLOB)")
        self._lock = threading.RLock()
        self._model = None
        self.used_keys: set[str] = set()

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder  # optional dependency

            self._model = CrossEncoder(self.model_name, device="cpu", max_length=512)
        return self._model

    def scores(self, query: str, passages: list[str]) -> list[float]:
        with self._lock:
            keys = [rerank_key(self.model_name, query, p) for p in passages]
            self.used_keys.update(keys)
            out: list[float | None] = []
            for k in keys:
                row = self.db.execute("SELECT val FROM score WHERE key = ?", (k,)).fetchone()
                out.append(struct.unpack("<d", row[0])[0] if row else None)
            todo = [i for i, v in enumerate(out) if v is None]
            if todo:
                if self.provider != "local":
                    raise RerankCacheMiss(f"{len(todo)} rerank score(s) not in {self.cache_path}")
                new = self._load().predict([(query, passages[i]) for i in todo],
                                           batch_size=16, show_progress_bar=False)
                for i, v in zip(todo, new, strict=True):
                    out[i] = float(v)
                    self.db.execute("INSERT OR REPLACE INTO score VALUES (?, ?)",
                                    (keys[i], struct.pack("<d", float(v))))
                self.db.commit()
            return [float(v) for v in out]

    def export_subset(self, keys: set[str], dest: str | Path) -> int:
        """Copy only the given entries to a new sqlite file (for the CI cache)."""
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()
        out = sqlite3.connect(str(dest))
        out.execute("CREATE TABLE score (key TEXT PRIMARY KEY, val BLOB)")
        n = 0
        with self._lock:
            for k in sorted(keys):
                row = self.db.execute("SELECT val FROM score WHERE key = ?", (k,)).fetchone()
                if row is not None:
                    out.execute("INSERT INTO score VALUES (?, ?)", (k, row[0]))
                    n += 1
        out.commit()
        out.execute("VACUUM")
        out.close()
        return n
