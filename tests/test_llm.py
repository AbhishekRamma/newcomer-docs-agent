import json

import pytest

from src import llm as llm_mod
from src.llm import LLM, LLMCacheMiss, SpendLedger, cache_key, cost_usd


def test_cache_key_depends_on_every_input():
    m = [{"role": "user", "content": "hi"}]
    base = cache_key("m", m, {"t": 0})
    assert base != cache_key("m2", m, {"t": 0})
    assert base != cache_key("m", [{"role": "user", "content": "hi!"}], {"t": 0})
    assert base != cache_key("m", m, {"t": 1})


def test_cached_provider_replays_and_never_calls_network(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_mod.httpx, "post", lambda *a, **k: pytest.fail("network"))
    llm = LLM("cached", "deepseek-flash", tmp_path)
    msgs = [{"role": "user", "content": "q"}]
    with pytest.raises(LLMCacheMiss):
        llm.complete(msgs)
    key = cache_key("deepseek-flash", msgs, {"temperature": 0, "max_tokens": 700, "json": False,
                                             "thinking": "disabled"})
    (tmp_path / key[:2]).mkdir()
    (tmp_path / key[:2] / f"{key}.json").write_text(json.dumps(
        {"content": "a", "served_model": "deepseek-flash", "usage": {}}))
    r = llm.complete(msgs)
    assert r.content == "a" and r.cached and llm.stats["hits"] == 1


def test_cost_and_budget_stop(tmp_path, monkeypatch):
    usage = {"prompt_tokens": 1_000_000, "prompt_cache_hit_tokens": 0, "completion_tokens": 0}
    assert cost_usd(usage) == pytest.approx(0.30)
    ledger = SpendLedger(tmp_path / "spend.json")
    monkeypatch.setattr(llm_mod, "SPEND_CAP_USD", 0.5)
    ledger.add(usage, "m")
    ledger.check()
    ledger.add(usage, "m")
    with pytest.raises(llm_mod.BudgetExceeded):
        ledger.check()
