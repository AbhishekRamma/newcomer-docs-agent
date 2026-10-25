"""Evaluation harness.

    python -m src.evaluate --split dev                 # score dev, write eval_runs/<name>/
    python -m src.evaluate --split test --final        # the one held-out run
    python -m src.evaluate --compare RUN_A RUN_B       # metric diff between two saved runs
    python -m src.evaluate --split dev --gate ci/thresholds.json   # exit 1 below thresholds

Metrics (each reported with its sample size n and a bootstrap 95% CI):
- route_accuracy: predicted route == expected route (all questions)
- recall_at_k / mrr: retrieval against expected source URLs (questions that have them)
- fact_recall: share of key facts found in the answer, rule-based (answerable questions;
  a refusal scores 0); facts_all: 1 if every key fact is found
- citation_url_hit: the answer cites at least one expected URL (answered + answerable)
- citation_support: every cited sentence passes a lexical support heuristic (answered)
- refusal_accuracy: refused == (question should not be answered) (all questions)
- repeat_free: no sentence mostly restates an earlier one (>= 80% of its content words; answered
  questions; diagnostic only, a lexical heuristic that misses reworded repeats)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from src.config import DATA_DIR, LOCAL_DIR, ROOT, get_settings
from src.graph import CHUNK_ID, Agent
from src.llm import SpendLedger
from src.retrieve import load_questions, retrieval_metrics
from src.textnorm import fact_present, normalize, numbers_in

RUNS_DIR = ROOT / "eval_runs"
METRICS = ["route_accuracy", "recall_at_k", "mrr", "fact_recall", "facts_all",
           "citation_url_hit", "citation_support", "refusal_accuracy", "repeat_free"]
STOP = set("""about above after again against also because been before being below between
both could does doing down during each from further have having here into itself just more
most must only other over same should some such than that their them then there these they
this those through under until very were what when where which while will with would your
yours you the and for are can not but its may""".split())
BOOT_N, BOOT_SEED = 10_000, 42


def verify_test_hash() -> str:
    qdir = DATA_DIR / "questions"
    expected = (qdir / "test.sha256").read_text().split()[0]
    actual = hashlib.sha256((qdir / "test.jsonl").read_bytes()).hexdigest()
    if actual != expected:
        sys.exit(f"test.jsonl hash {actual[:12]} does not match frozen {expected[:12]}; refusing.")
    return actual


def bootstrap_ci(values: list[float], n: int = BOOT_N, seed: int = BOOT_SEED):
    if not values:
        return None
    arr = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = arr[rng.integers(0, len(arr), size=(n, len(arr)))].mean(axis=1)
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def _content_words(text: str) -> set[str]:
    return {w[:6] for w in normalize(text).split()
            if len(w) > 3 and w not in STOP and not w.isdigit()}


def sentence_supported(sentence: str, chunk_texts: list[str]) -> bool:
    """Heuristic: >= 60% of the sentence's content words (6-char prefixes) appear in the cited
    chunks, and every number in the sentence appears there too."""
    src = " ".join(chunk_texts)
    words = _content_words(sentence)
    if words and len(words & _content_words(src)) / len(words) < 0.6:
        return False
    return numbers_in(sentence) <= numbers_in(src)


def citation_support(answer: str, chunk_text: dict[str, str]) -> bool:
    ok = True
    for sent in re.split(r"(?<=[.!?])\s+|\n+", answer):
        ids = CHUNK_ID.findall(sent)
        if not ids:
            continue
        clean = re.sub(r"\[[^\]]*\]\([^)]*\)", "", sent)
        if not sentence_supported(clean, [chunk_text.get(i, "") for i in ids]):
            ok = False
    return ok


def has_repeat(answer: str, threshold: float = 0.8) -> bool:
    """True if some sentence's content words are >= threshold covered by one earlier sentence
    (it mostly restates it). A lexical heuristic: reworded repeats can slip through."""
    clean = re.sub(r"\[[^\]]*\]\([^)]*\)|\[[^\]]*\]", "", answer)
    sents = [_content_words(x) for x in re.split(r"(?<=[.!?])\s+|\n+", clean)]
    sents = [w for w in sents if len(w) >= 3]
    return any(len(b & a) / len(b) >= threshold for i, b in enumerate(sents) for a in sents[:i])


def git_hash() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "uncommitted"


def score(q: dict, out: dict, retrieved, chunk_text: dict[str, str], k: int) -> dict:
    should = q["should_answer"]
    refused = out["refused"]
    r = {"id": q["id"], "category": q["category"], "topic": q.get("topic"),
         "expected_route": q["expected_route"], "route": out["route"],
         "refused": refused, "refusal_reason": out.get("refusal_reason"),
         "route_accuracy": float(out["route"] == q["expected_route"]),
         "refusal_accuracy": float(refused == (not should)),
         "cited_urls": sorted({c["url"] for c in out.get("citations", [])})}
    if q["expected_source_urls"]:
        m = retrieval_metrics(q["expected_source_urls"], retrieved)
        r["recall_at_k"], r["mrr"] = m["recall"], m["rr"]
    if should:
        answer = "" if refused else out["answer"]
        norm = normalize(re.sub(r"\]\([^)]*\)", "]", answer))
        found = [f for f in q["key_facts"] if fact_present(f, norm, normalized=True)]
        r["missing_facts"] = [f for f in q["key_facts"] if f not in found]
        r["fact_recall"] = len(found) / len(q["key_facts"])
        r["facts_all"] = float(len(found) == len(q["key_facts"]))
        if not refused:
            r["citation_url_hit"] = float(bool(set(r["cited_urls"]) &
                                               set(q["expected_source_urls"])))
    if not refused:
        r["citation_support"] = float(citation_support(out["answer"], chunk_text))
        r["repeat_free"] = float(not has_repeat(out["answer"]))
    return r


def summarise(rows: list[dict]) -> dict:
    out = {}
    for m in METRICS:
        vals = [r[m] for r in rows if r.get(m) is not None]
        out[m] = {"value": round(float(np.mean(vals)), 4) if vals else None, "n": len(vals),
                  "ci95": bootstrap_ci(vals)}
    return out


def run(split: str, name: str | None, limit: int | None) -> Path:
    s = get_settings()
    qhash = verify_test_hash() if split == "test" else hashlib.sha256(
        (DATA_DIR / "questions" / f"{split}.jsonl").read_bytes()).hexdigest()
    questions = load_questions(split)[:limit] if limit else load_questions(split)
    agent = Agent(s)
    ledger = SpendLedger()
    spend_before = ledger.load()["est_usd_peak"]
    name = name or (f"{split}-{s.index}-k{s.top_k}-{'hybrid' if s.hybrid else 'vector'}-"
                    f"{'verify' if s.verify else 'noverify'}")
    out_dir = RUNS_DIR / name
    out_dir.mkdir(parents=True, exist_ok=True)
    ans_dir = LOCAL_DIR / "eval_answers"
    ans_dir.mkdir(parents=True, exist_ok=True)
    rows, answers, served = [], [], set()
    t0 = time.time()
    for i, q in enumerate(questions, 1):
        out = agent.ask(q["question"])
        served.update(out.get("served_models", []))
        retrieved = agent.retriever.search(q["question"], s.top_k)
        ids = list({*CHUNK_ID.findall(out["answer"])})
        chunk_text = {}
        if ids:
            for cid, h, t in agent.retriever.conn.execute(
                    "SELECT id, heading, text FROM chunks WHERE id = ANY(%s)", (ids,)):
                chunk_text[cid] = h + " " + t
        row = score(q, out, retrieved, chunk_text, s.top_k)
        rows.append(row)
        answers.append({"id": q["id"], "question": q["question"], **out})
        flag = "ok" if row["refusal_accuracy"] and row.get("facts_all", 1) else "FAIL"
        print(f"[{i:02d}/{len(questions)}] {q['id']} {flag} route={out['route']} "
              f"refused={out['refused']} facts={row.get('fact_recall', '-')}", flush=True)
    metrics = summarise(rows)
    spend_after = ledger.load()["est_usd_peak"] if ledger.path.exists() else spend_before
    config = {"split": split, "n_questions": len(questions), "questions_sha256": qhash,
              "settings": s.public_dict(), "git_commit": git_hash(),
              "bootstrap": {"resamples": BOOT_N, "seed": BOOT_SEED},
              "served_models": sorted(served), "llm_cache": agent.llm.stats,
              "est_cost_usd_peak_this_run": round(spend_after - spend_before, 6),
              "elapsed_s": round(time.time() - t0, 1),
              "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out_dir / "config.json").write_text(json.dumps(config, indent=2))
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    with (out_dir / "per_question.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    # Answer text quotes government pages, so it stays in gitignored data/local/.
    with (ans_dir / f"{name}.jsonl").open("w") as f:
        for a in answers:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    print_metrics(name, metrics, config)
    print_failures(rows)
    return out_dir


def print_metrics(name: str, metrics: dict, config: dict | None = None) -> None:
    print(f"\n== {name} ==")
    for m, v in metrics.items():
        ci = f"[{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]" if v["ci95"] else "-"
        val = f"{v['value']:.3f}" if v["value"] is not None else "-"
        print(f"  {m:18s} {val:>6s}  95% CI {ci:16s} n={v['n']}")
    if config:
        print(f"  llm_cache={config['llm_cache']} served={config['served_models']} "
              f"cost≈${config['est_cost_usd_peak_this_run']:.4f} (peak-rate estimate)")


def print_failures(rows: list[dict]) -> None:
    fails = [r for r in rows if not r["refusal_accuracy"] or r.get("facts_all") == 0.0
             or not r["route_accuracy"]]
    if not fails:
        return
    print(f"\nPer-question failures ({len(fails)}):")
    for r in fails:
        why = []
        if not r["route_accuracy"]:
            why.append(f"route {r['route']}≠{r['expected_route']}")
        if not r["refusal_accuracy"]:
            why.append("wrongly refused" if r["refused"] else "should have refused")
        if r.get("missing_facts"):
            why.append(f"missing {r['missing_facts']}")
        print(f"  {r['id']} ({r['category']}/{r['topic']}): {'; '.join(why)}")


def compare(a: str, b: str) -> None:
    ma = json.loads((RUNS_DIR / a / "metrics.json").read_text())
    mb = json.loads((RUNS_DIR / b / "metrics.json").read_text())
    print(f"{'metric':18s} {a[:24]:>24s} {b[:24]:>24s}   delta")
    for m in METRICS:
        if m not in ma or m not in mb:
            continue
        va, vb = ma[m]["value"], mb[m]["value"]
        d = f"{vb - va:+.3f}" if va is not None and vb is not None else "-"
        print(f"{m:18s} {str(va):>24s} {str(vb):>24s}   {d}  (n={ma[m]['n']}/{mb[m]['n']})")


def gate(run_dir: Path, thresholds_path: str) -> int:
    th = json.loads(Path(thresholds_path).read_text())
    metrics = json.loads((run_dir / "metrics.json").read_text())
    bad = [f"{m}={metrics[m]['value']} < {v}" for m, v in th.items()
           if metrics[m]["value"] is None or metrics[m]["value"] < v]
    print("\nGATE:", "FAIL " + "; ".join(bad) if bad else "PASS")
    return 1 if bad else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--final", action="store_true", help="required to score the test split")
    ap.add_argument("--name")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--gate", help="thresholds JSON; exit 1 if any metric is below")
    ap.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"))
    args = ap.parse_args()
    if args.compare:
        compare(*args.compare)
        return
    if args.split == "test" and not args.final:
        sys.exit("Refusing to score the frozen test split without --final.")
    out_dir = run(args.split, args.name, args.limit)
    if args.gate:
        sys.exit(gate(out_dir, args.gate))


if __name__ == "__main__":
    main()
