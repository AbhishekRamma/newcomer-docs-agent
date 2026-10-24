"""LangGraph pipeline: route -> retrieve -> answer -> verify (retry once) -> output."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from src import prompts
from src.config import Settings, get_settings
from src.llm import LLM, LLMCacheMiss
from src.retrieve import Chunk, Retriever
from src.textnorm import numbers_in

ROUTES = ("in_scope", "out_of_scope", "needs_professional", "unclear")
DISCLAIMER = ("This is general information from official government pages, not legal, tax or "
              "immigration advice.")
NOT_FOUND = "I could not find this in the sources."
REFUSALS = {
    "out_of_scope": "This is outside what I cover. I only answer questions about SIN, OHIP, "
                    "opening a bank account, a first Canadian tax return, and Ontario driver's "
                    "licences or Photo Cards, using official government pages.",
    "needs_professional": "This needs advice about your own situation, which I can't give. "
                          "Please contact a licensed professional (a lawyer or paralegal "
                          "licensed by the Law Society of Ontario, a licensed immigration "
                          "consultant, or a tax professional) or the government office "
                          "directly.",
    "unclear": "I'm not sure what you're asking. Could you say which topic (SIN, OHIP, banking, "
               "taxes, or driver's licence) and what you want to know?",
}
CITE = re.compile(r"\[([a-z0-9,\s\-]+)\]")
CHUNK_ID = re.compile(r"s\d{2}-c\d+-\d{3}")
_WORDNUM = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen twenty".split())}


class State(TypedDict, total=False):
    question: str
    route: str
    route_reason: str
    chunks: list[Chunk]
    draft: str
    answerable: bool
    attempts: int
    problems: list[str]
    verified: bool
    final: dict
    events: list[str]
    served_models: list[str]


def cited_ids(text: str) -> list[str]:
    out: list[str] = []
    for group in CITE.findall(text):
        for cid in CHUNK_ID.findall(group):
            if cid not in out:
                out.append(cid)
    return out


def strip_citations(text: str) -> str:
    return CITE.sub("", text)


def source_numbers(text: str) -> set[str]:
    nums = numbers_in(text)
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in _WORDNUM:
            nums.add(_WORDNUM[w])
    return nums


def format_context(chunks: list[Chunk]) -> str:
    return "\n\n".join(f"[{c.id}] ({c.title} — {c.heading})\n{c.text}" for c in chunks)


def rule_checks(draft: str, chunks: list[Chunk]) -> list[str]:
    """Deterministic checks: citations exist and point at retrieved chunks; every number
    in the answer appears in the cited chunks."""
    problems = []
    by_id = {c.id: c for c in chunks}
    ids = cited_ids(draft)
    if not ids:
        problems.append("The answer has no [chunk-id] citations.")
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        problems.append(f"Cites ids that were not provided: {', '.join(unknown)}.")
    cited_text = " ".join(by_id[i].heading + " " + by_id[i].text for i in ids if i in by_id)
    missing = sorted(numbers_in(strip_citations(draft)) - source_numbers(cited_text))
    if missing:
        problems.append("Numbers not found in the cited excerpts: " + ", ".join(missing) + ".")
    return problems


class Agent:
    def __init__(self, settings: Settings | None = None, retriever: Retriever | None = None,
                 llm: LLM | None = None):
        self.s = settings or get_settings()
        self.retriever = retriever or Retriever(self.s)
        self.llm = llm or LLM(self.s.llm_provider, self.s.model, self.s.llm_cache_dir)
        self.graph = self._build()

    # --- helpers -----------------------------------------------------------------------
    def _json(self, state: State, system: str, user: str) -> dict:
        resp = self.llm.complete([{"role": "system", "content": system},
                                  {"role": "user", "content": user}], json_mode=True)
        state.setdefault("served_models", []).append(resp.served_model)
        try:
            return json.loads(resp.content)
        except json.JSONDecodeError:
            return {}

    # --- nodes -------------------------------------------------------------------------
    def route(self, state: State) -> State:
        out = self._json(state, prompts.ROUTE_SYSTEM, state["question"])
        label = out.get("label") if out.get("label") in ROUTES else "unclear"
        return {"route": label, "route_reason": str(out.get("reason", ""))[:300],
                "served_models": state.get("served_models", [])}

    def retrieve(self, state: State) -> State:
        return {"chunks": self.retriever.search(state["question"], self.s.top_k), "attempts": 0}

    def answer(self, state: State) -> State:
        user = prompts.ANSWER_USER.format(question=state["question"],
                                          context=format_context(state["chunks"]))
        if state.get("problems"):
            user += prompts.RETRY_NOTE.format(problems="\n".join(f"- {p}" for p in
                                                                 state["problems"]))
        out = self._json(state, prompts.ANSWER_SYSTEM, user)
        draft = str(out.get("answer") or "").strip()
        answerable = bool(out.get("answerable")) and bool(draft)
        return {"draft": draft, "answerable": answerable, "attempts": state["attempts"] + 1,
                "served_models": state.get("served_models", [])}

    def verify(self, state: State) -> State:
        if not state["answerable"]:
            return {"verified": False, "problems": []}
        if not self.s.verify:
            return {"verified": True, "problems": []}
        problems = rule_checks(state["draft"], state["chunks"])
        if not problems:
            by_id = {c.id: c for c in state["chunks"]}
            cited = [by_id[i] for i in cited_ids(state["draft"]) if i in by_id]
            out = self._json(state, prompts.VERIFY_SYSTEM, prompts.VERIFY_USER.format(
                answer=state["draft"], context=format_context(cited)))
            if not out.get("supported", False):
                claims = out.get("unsupported_claims") or ["(no detail given)"]
                problems = [f"Unsupported claim: {c}" for c in claims[:5]]
        return {"verified": not problems, "problems": problems,
                "events": state.get("events", []) + [f"verify#{state['attempts']}: "
                                                      f"{'ok' if not problems else problems}"]}

    def after_verify(self, state: State) -> str:
        if state["verified"] or not state["answerable"]:
            return "output"
        return "answer" if state["attempts"] < 2 else "output"

    def output(self, state: State) -> State:
        route = state.get("route", "unclear")
        base = {"route": route, "route_reason": state.get("route_reason", ""),
                "disclaimer": DISCLAIMER, "citations": [], "retrieved": [],
                "verify_events": state.get("events", []), "attempts": state.get("attempts", 0)}
        if route != "in_scope":
            return {"final": {**base, "answer": REFUSALS[route], "refused": True,
                              "refusal_reason": route}}
        chunks = state["chunks"]
        base["retrieved"] = [{"id": c.id, "url": c.url, "score": round(c.score, 4)}
                             for c in chunks]
        if not state.get("answerable") or not state.get("verified"):
            reason = "not_in_sources" if not state.get("answerable") else "failed_verification"
            return {"final": {**base, "answer": NOT_FOUND, "refused": True,
                              "refusal_reason": reason}}
        by_id = {c.id: c for c in chunks}
        ids = [i for i in cited_ids(state["draft"]) if i in by_id]

        def link(m: re.Match) -> str:
            found = [i for i in CHUNK_ID.findall(m.group(1)) if i in by_id]
            return " ".join(f"[{i}]({by_id[i].url})" for i in found) if found else ""

        text = CITE.sub(link, state["draft"])
        cits = [{"chunk_id": i, "url": by_id[i].url, "title": by_id[i].title,
                 "heading": by_id[i].heading, "fetched_at": by_id[i].fetched_at} for i in ids]
        return {"final": {**base, "answer": text, "refused": False, "refusal_reason": None,
                          "citations": cits}}

    def _build(self):
        g = StateGraph(State)
        for name in ("route", "retrieve", "answer", "verify", "output"):
            g.add_node(name, getattr(self, name))
        g.set_entry_point("route")
        g.add_conditional_edges("route", lambda s: "retrieve" if s["route"] == "in_scope"
                                else "output", {"retrieve": "retrieve", "output": "output"})
        g.add_edge("retrieve", "answer")
        g.add_edge("answer", "verify")
        g.add_conditional_edges("verify", self.after_verify,
                                {"answer": "answer", "output": "output"})
        g.add_edge("output", END)
        return g.compile()

    def ask(self, question: str) -> dict:
        try:
            state = self.graph.invoke({"question": question})
        except LLMCacheMiss:
            # Replay mode with a prompt that is not in the cache (e.g. code changed): fail safe.
            return {"route": "error", "route_reason": "", "answer": NOT_FOUND, "refused": True,
                    "refusal_reason": "llm_cache_miss", "citations": [], "retrieved": [],
                    "disclaimer": DISCLAIMER, "verify_events": [], "attempts": 0,
                    "served_models": []}
        final = state["final"]
        final["served_models"] = sorted(set(state.get("served_models", [])))
        return final


@lru_cache(maxsize=1)
def default_agent() -> Agent:
    return Agent()


def _main() -> None:
    import sys
    a = default_agent()
    out: dict[str, Any] = a.ask(" ".join(sys.argv[1:]))
    print(json.dumps(out, indent=2, ensure_ascii=False))
    print("llm stats:", a.llm.stats, file=sys.stderr)


if __name__ == "__main__":
    _main()
