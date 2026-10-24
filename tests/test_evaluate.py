import subprocess
import sys

from src.evaluate import bootstrap_ci, citation_support, score, sentence_supported
from src.retrieve import Chunk


def test_bootstrap_is_deterministic_and_bounded():
    vals = [1, 0, 1, 1, 0, 1, 1, 1]
    a, b = bootstrap_ci(vals), bootstrap_ci(vals)
    assert a == b and 0 <= a[0] <= 0.75 <= a[1] <= 1
    assert bootstrap_ci([]) is None


def test_test_split_requires_final_flag():
    r = subprocess.run([sys.executable, "-m", "src.evaluate", "--split", "test"],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "--final" in r.stderr


def test_sentence_support_heuristic():
    src = ["There is no fee to apply for a Social Insurance Number."]
    assert sentence_supported("There is no fee to apply for a Social Insurance Number.", src)
    assert not sentence_supported("Applicants must pay 45 dollars at the bank.", src)
    ans = "No fee applies to a Social Insurance Number [s01-c500-000](u)."
    assert citation_support(ans, {"s01-c500-000": src[0]})


def test_score_refusal_and_facts():
    q = {"id": "d1", "category": "in_scope", "topic": "sin", "expected_route": "in_scope",
         "should_answer": True, "expected_source_urls": ["u"], "key_facts": ["no fee", "30 days"]}
    out = {"route": "in_scope", "refused": False, "answer": "There is no fee [s01-c500-000](u).",
           "citations": [{"url": "u"}]}
    r = score(q, out, [Chunk("s01-c500-000", "s01", "u", "t", "h", "x", "d", 1)], {}, 5)
    assert r["fact_recall"] == 0.5 and r["missing_facts"] == ["30 days"]
    assert r["citation_url_hit"] == 1.0 and r["refusal_accuracy"] == 1.0
