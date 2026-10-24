import json

from src.config import get_settings
from src.graph import NOT_FOUND, Agent, cited_ids, rule_checks
from src.llm import LLMResponse
from src.retrieve import Chunk

CHUNKS = [
    Chunk("s01-c500-000", "s01", "https://example.gc.ca/sin", "SIN", "Fees",
          "There is no fee to get a SIN. Apply within 30 days.", "2026-10-24", 0.9),
    Chunk("s01-c500-001", "s01", "https://example.gc.ca/sin", "SIN", "Online",
          "You can apply online.", "2026-10-24", 0.8),
]


class FakeRetriever:
    def search(self, q, k):
        return CHUNKS[:k]


class FakeLLM:
    """Scripted responses keyed by which system prompt is in use."""

    def __init__(self, route, answers, verdicts=None):
        self.route, self.answers, self.verdicts = route, list(answers), list(verdicts or [])
        self.stats = {}

    def complete(self, messages, json_mode=False, max_tokens=700):
        sys = messages[0]["content"]
        if sys.startswith("You classify"):
            out = {"label": self.route, "reason": "r"}
        elif sys.startswith("You answer"):
            out = self.answers.pop(0)
        else:
            out = self.verdicts.pop(0) if self.verdicts else {"supported": True}
        return LLMResponse(json.dumps(out), "fake", {}, cached=True)


def _agent(llm, **kw):
    return Agent(get_settings(**kw), retriever=FakeRetriever(), llm=llm)


def test_answer_has_linked_citations_and_disclaimer():
    ans = {"answerable": True, "answer": "There is no fee to get a SIN [s01-c500-000]."}
    out = _agent(FakeLLM("in_scope", [ans])).ask("Does a SIN cost money?")
    assert not out["refused"]
    assert "[s01-c500-000](https://example.gc.ca/sin)" in out["answer"]
    assert "not legal, tax or immigration advice" in out["disclaimer"]
    assert out["citations"][0]["chunk_id"] == "s01-c500-000"


def test_invented_number_is_retried_then_refused():
    bad = {"answerable": True, "answer": "Apply within 60 days [s01-c500-000]."}
    out = _agent(FakeLLM("in_scope", [bad, bad])).ask("How long do I have?")
    assert out["refused"] and out["answer"] == NOT_FOUND
    assert out["refusal_reason"] == "failed_verification" and out["attempts"] == 2


def test_retry_can_recover():
    bad = {"answerable": True, "answer": "Apply within 60 days [s01-c500-000]."}
    good = {"answerable": True, "answer": "Apply within 30 days [s01-c500-000]."}
    out = _agent(FakeLLM("in_scope", [bad, good])).ask("How long do I have?")
    assert not out["refused"] and "30 days" in out["answer"]


def test_llm_verifier_rejection_leads_to_refusal():
    ans = {"answerable": True, "answer": "You can apply online [s01-c500-001]."}
    v = {"supported": False, "unsupported_claims": ["x"]}
    out = _agent(FakeLLM("in_scope", [ans, ans], [v, v])).ask("Online?")
    assert out["refused"]


def test_verify_off_skips_checks():
    bad = {"answerable": True, "answer": "Apply within 60 days [s01-c500-000]."}
    out = _agent(FakeLLM("in_scope", [bad]), verify=False).ask("How long?")
    assert not out["refused"]


def test_non_scope_routes_refuse_without_retrieval():
    for label in ("out_of_scope", "needs_professional", "unclear"):
        out = _agent(FakeLLM(label, [])).ask("q")
        assert out["refused"] and out["refusal_reason"] == label and out["retrieved"] == []


def test_rule_checks_and_cited_ids():
    assert cited_ids("a [s01-c500-000, s01-c500-001] b [s01-c500-000]") == [
        "s01-c500-000", "s01-c500-001"]
    assert rule_checks("No citation here.", CHUNKS)
    assert rule_checks("Bad id [s09-c500-009].", CHUNKS)
    assert not rule_checks("Within thirty days, 30 days [s01-c500-000].", CHUNKS)
