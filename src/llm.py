"""One LLM interface with two providers.

- ``live``: DeepSeek through its OpenAI-compatible Chat Completions API. Every response is
  written to an on-disk cache keyed by sha256(model, messages, params) and every call is
  added to a spend ledger. New calls are refused once the estimated spend reaches the cap.
- ``cached``: replay only. A cache miss raises ``LLMCacheMiss``; nothing touches the network.

Cache files store the response text, the served model and token usage. They never store the
prompt, so a cache built from fixture documents cannot leak page text through prompts.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from src.config import LOCAL_DIR

API_URL = "https://api.deepseek.com/chat/completions"
# USD per 1M tokens, deepseek-flash PEAK rates from api-docs.deepseek.com/quick_start/pricing
# (fetched 2026-10-24). Off-peak is half. We estimate at peak as a conservative upper bound.
PRICE_PEAK = {"input_miss": 0.30, "input_hit": 0.006, "output": 1.20}
SPEND_CAP_USD = float(os.getenv("LLM_SPEND_CAP_USD", "1.50"))
SPEND_PATH = Path(os.getenv("SPEND_PATH", LOCAL_DIR / "spend.json"))


class LLMCacheMiss(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class LLMResponse:
    content: str
    served_model: str
    usage: dict
    cached: bool


def cache_key(model: str, messages: list[dict], params: dict) -> str:
    blob = json.dumps({"model": model, "messages": messages, "params": params},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def cost_usd(usage: dict, prices: dict = PRICE_PEAK) -> float:
    out = usage.get("completion_tokens", 0)
    hit = usage.get("prompt_cache_hit_tokens", 0)
    miss = usage.get("prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
    return (miss * prices["input_miss"] + hit * prices["input_hit"] + out * prices["output"]) / 1e6


class SpendLedger:
    def __init__(self, path: Path = SPEND_PATH):
        self.path = Path(path)

    def load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {"calls": 0, "prompt_cache_miss_tokens": 0, "prompt_cache_hit_tokens": 0,
                "completion_tokens": 0, "est_usd_peak": 0.0, "served_models": {}}

    def check(self) -> float:
        spent = self.load()["est_usd_peak"]
        if spent >= SPEND_CAP_USD:
            raise BudgetExceeded(f"estimated spend ${spent:.4f} reached cap ${SPEND_CAP_USD:.2f}")
        return spent

    def add(self, usage: dict, served_model: str) -> None:
        d = self.load()
        hit = usage.get("prompt_cache_hit_tokens", 0)
        d["calls"] += 1
        d["prompt_cache_hit_tokens"] += hit
        d["prompt_cache_miss_tokens"] += usage.get(
            "prompt_cache_miss_tokens", usage.get("prompt_tokens", 0) - hit)
        d["completion_tokens"] += usage.get("completion_tokens", 0)
        d["est_usd_peak"] = round(d["est_usd_peak"] + cost_usd(usage), 8)
        d["est_usd_offpeak"] = round(d["est_usd_peak"] / 2, 8)
        d["served_models"][served_model] = d["served_models"].get(served_model, 0) + 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(d, indent=2))


class LLM:
    """``complete(messages, json_mode)`` -> LLMResponse. Temperature 0, thinking disabled."""

    def __init__(self, provider: str, model: str, cache_dir: str | Path):
        if provider not in {"live", "cached"}:
            raise ValueError(f"unknown LLM provider {provider!r}")
        self.provider, self.model = provider, model
        self.cache_dir = Path(cache_dir)
        self.ledger = SpendLedger()
        self.stats = {"hits": 0, "misses": 0, "live_calls": 0}

    def _path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def complete(self, messages: list[dict], json_mode: bool = False,
                 max_tokens: int = 700) -> LLMResponse:
        params = {"temperature": 0, "max_tokens": max_tokens, "json": json_mode,
                  "thinking": "disabled"}
        key = cache_key(self.model, messages, params)
        path = self._path(key)
        if path.exists():
            self.stats["hits"] += 1
            d = json.loads(path.read_text())
            return LLMResponse(d["content"], d["served_model"], d["usage"], cached=True)
        self.stats["misses"] += 1
        if self.provider == "cached":
            raise LLMCacheMiss(key)
        return self._live(messages, params, path)

    def _live(self, messages, params, path: Path) -> LLMResponse:
        self.ledger.check()
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set (put it in .env)")
        body = {"model": self.model, "messages": messages, "temperature": 0,
                "max_tokens": params["max_tokens"], "thinking": {"type": "disabled"},
                "stream": False}
        if params["json"]:
            body["response_format"] = {"type": "json_object"}
        last = None
        for attempt in range(4):
            try:
                r = httpx.post(API_URL, json=body, timeout=120,
                               headers={"Authorization": f"Bearer {api_key}"})
                if r.status_code in (429, 500, 502, 503) and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                r.raise_for_status()
                break
            except httpx.TransportError as e:  # network hiccup: retry, never log headers
                last = e
                time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"DeepSeek request failed: {type(last).__name__}")
        data = r.json()
        content = data["choices"][0]["message"].get("content") or ""
        served = data.get("model", "unknown")
        usage = data.get("usage", {})
        self.stats["live_calls"] += 1
        self.ledger.add(usage, served)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"served_model": served, "content": content, "usage": {
            k: usage.get(k) for k in ("prompt_tokens", "completion_tokens",
                                      "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")}},
            ensure_ascii=False, indent=1))
        return LLMResponse(content, served, usage, cached=False)
