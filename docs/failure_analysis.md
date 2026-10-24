# Failure analysis

Configuration for both splits: 500-token chunks, top 5, hybrid retrieval, verification on. Full answer text is kept locally in `data/local/eval_answers/` (it paraphrases government pages, so it is not committed); the per-question metrics are in `eval_runs/*/per_question.jsonl`.

## Held-out test set (scored once, `--final`): 6 of 30 questions had a failure

| id | category / topic | what happened | failure type | the agent's answer was |
|---|---|---|---|---|
| test-02 | in_scope / banking | Asked how many debit transactions a low-cost or no-cost account must include. The router called it `out_of_scope` ("bank account product features"), so nothing was retrieved, although recall@5 for the question was 1.0. | router too narrow | a safe but unhelpful refusal |
| test-22 | in_scope / tax | Asked how the CRA treats property such as shares owned before immigrating (deemed disposition at fair market value). The router read "I owned" as a request for personal tax advice and sent it to `needs_professional`. | router over-cautious | a safe but unhelpful refusal |
| test-30 | unanswerable / tax | Asked for exact 2027 payment dates of the Canada Groceries and Essentials Benefit, which the sources don't list. Refused, which is correct, but as `out_of_scope` instead of going through retrieval to "could not find". | wrong route, right outcome | correct refusal, wrong label |
| test-21 | in_scope / tax | Asked the minimum age for the Canada Groceries and Essentials Benefit. The eligibility page (s15) was not in the top 5. Vector search alone had it at rank 5, but full-text search did not match it at all, so rank fusion pushed it below chunks from s10 and s16 that both searches found. The answer node correctly said it could not find the age. | retrieval miss caused by the hybrid choice | a correct "not found" given what it retrieved |
| test-01 | in_scope / banking | Asked about accounts with no monthly fee. The answer covered low-cost and no-cost accounts but left out the first-year fee waiver for newcomers. Four of the five retrieved chunks came from the right page, but not the one chunk (s09-c500-002) that mentions the waiver, so page-level recall@5 was 1.0 while chunk-level retrieval missed. | partial answer from a chunk-level retrieval miss | correct but incomplete |
| test-16 | in_scope / sin | Asked what a SIN starting with 9 means. The answer said it is a temporary SIN that expires with your immigration documents, which is right, but did not use the words "temporary resident", so the rule-based scorer marked one fact missing. | scorer strictness | arguably correct |

### What the test failures say

- **No hallucinations were detected.** All 19 answered, answerable questions cited an expected URL and passed the citation-support check; every failure was a refusal or an omission, not an invented fact. This is the failure direction I designed for, but "detected" matters: the support check is lexical, not an entailment model.
- **The router is the weakest component (3 of 6).** It errs towards refusing, mostly on questions phrased in the first person ("I owned…") or about details it considers off-topic. Same pattern as dev-14 below.
- **Retrieval caused two misses (test-21, test-01).** test-21 is a cost of the hybrid choice I made on dev: vector search alone would have retrieved the eligibility page at rank 5. test-01 shows that my recall@k metric is page-level, so it can read 1.0 while the chunk with the fact is missing. Dev never needed s15, so neither was visible before the test run.
- **One miss is a scoring artefact (test-16).** Counting it as correct would move all-facts from 17/22 to 18/22. I report the scorer's number, not my reading.

## Dev set (40 questions): recurring failures across the experiment runs

| id | what happened | runs affected |
|---|---|---|
| dev-14 (in_scope / ohip) | Asked what to do if ServiceOntario says you don't qualify for OHIP. Routed `needs_professional`, so the review and appeal options on the page were never shown. | all runs |
| dev-28 (in_scope / tax) | Asked whether newcomers can get benefit payments before filing a first return. Answered "yes" with citations but did not name form RC151. | all runs |
| dev-05 (in_scope / driving) | Asked where to exchange a licence. The vector baseline's answer missed that a vision test is part of the visit. | baseline; fixed in the hybrid run |
| dev-19 (in_scope / sin) | Asked which primary document a temporary resident needs for a SIN. Baseline only: the LLM verifier rejected the first answer (probably because the tabbed layout on the SIN application page is flattened when parsed, so the supporting sentence reads oddly), the retry dropped the work-permit fact. | baseline (vector, verify) |

## What I would fix first

1. **Router:** give it explicit examples showing that a first-person question about a general rule ("I owned shares before I came…") is still `in_scope`, and route borderline cases to retrieval rather than refusing. This would address dev-14, test-02 and test-22. It would need re-tuning on dev and a fresh held-out set to measure honestly, because this test set has now been seen.
2. **Retrieval:** only fuse full-text results when they agree with vector search, or weight the vector side higher in RRF (test-21); add a chunk-level recall metric beside the page-level one (test-01).
3. **Scorer:** add an LLM or entailment judge for key facts as a second opinion beside the string match, and report both.
