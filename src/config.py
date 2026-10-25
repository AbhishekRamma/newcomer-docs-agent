"""Runtime settings, read from the environment (and `.env` when present)."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
LOCAL_DIR = Path(os.getenv("LOCAL_DIR", DATA_DIR / "local"))
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_DIM = 384


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    """Everything that changes a run's behaviour. Saved with every eval run."""

    index: str = field(default_factory=lambda: os.getenv("RAG_INDEX", "c500"))
    top_k: int = field(default_factory=lambda: int(os.getenv("RAG_TOP_K", "5")))
    hybrid: bool = field(default_factory=lambda: _bool("RAG_HYBRID", True))
    # Cross-encoder model name, or "" for no reranking.
    rerank: str = field(default_factory=lambda: os.getenv("RAG_RERANK", ""))
    verify: bool = field(default_factory=lambda: _bool("RAG_VERIFY", True))
    model: str = field(default_factory=lambda: os.getenv("DEEPSEEK_MODEL", "deepseek-flash"))
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "live"))
    embed_provider: str = field(default_factory=lambda: os.getenv("EMBED_PROVIDER", "local"))
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "postgresql://rag:rag@localhost:5433/rag"
        )
    )
    llm_cache_dir: str = field(
        default_factory=lambda: os.getenv("LLM_CACHE_DIR", str(LOCAL_DIR / "llm_cache"))
    )
    embed_cache_path: str = field(
        default_factory=lambda: os.getenv(
            "EMBED_CACHE_PATH", str(LOCAL_DIR / "embed_cache.sqlite")
        )
    )
    rerank_cache_path: str = field(
        default_factory=lambda: os.getenv(
            "RERANK_CACHE_PATH", str(LOCAL_DIR / "rerank_cache.sqlite")
        )
    )

    def public_dict(self) -> dict:
        """Config metadata safe to write into run files (no credentials)."""
        d = asdict(self)
        d.pop("database_url", None)
        return d


def get_settings(**overrides) -> Settings:
    s = Settings()
    for k, v in overrides.items():
        if v is not None:
            setattr(s, k, v)
    return s
