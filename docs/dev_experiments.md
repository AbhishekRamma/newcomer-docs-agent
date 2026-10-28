# Dev experiments

Every configuration I compared on the 40 dev questions. Held-out results are in the [README](../README.md#held-out-results).

## First round (40 questions; retrieval and fact metrics on the 28 answerable ones)

| run | recall@k | MRR | fact recall | all facts (95% CI) | citation support | refusal acc. | live LLM calls | est. cost |
|---|---|---|---|---|---|---|---|---|
| 500 tokens, k=5, vector, verify (baseline) | 0.964 | 0.946 | 0.926 | 0.857 (0.714–0.964) | 1.000 | 0.975 | 81 | $0.0191 |
| 300 tokens | 0.964 | 0.946 | 0.923 | 0.857 | 1.000 | 0.975 | 57 | $0.0185 |
| 800 tokens | 0.964 | 0.946 | 0.934 | 0.893 | 0.963 | 0.975 | 57 | $0.0200 |
| k=3 | 0.929 | 0.946 | 0.878 | 0.786 | 1.000 | 0.950 | 46 | $0.0082 |
| k=8 | 0.982 | 0.946 | 0.934 | 0.893 | 0.963 | 0.975 | 44 | $0.0131 |
| **hybrid (vector + full-text, RRF) — chosen** | 0.982 | 0.929 | 0.946 | **0.929 (0.821–1.000)** | 1.000 | 0.975 | 47 | $0.0197 |
| no verify node | 0.964 | 0.946 | 0.934 | 0.893 | 1.000 | 0.975 | 0 (all cached) | $0 |

Route accuracy was 0.975 (n=40) and expected-URL citation 1.000 (n=26–27) in every run. Every difference above is one to three questions out of 28, inside the CIs. I picked hybrid by a rule written down before comparing (highest all-facts, then refusal accuracy, then cost), not because it is clearly better. Raw outputs: [`eval_runs/`](../eval_runs/).

## Second round: prompts, repeated sentences and a reranker

All on dev only. "v2"–"v5" are successive prompt versions (routing calibration and an anti-repetition rule in the answer prompt); "v6" is v5 plus a deterministic step that drops a sentence whose words and numbers all appear in one earlier sentence (moving its citations onto that sentence). `bge-rerank` means `BAAI/bge-reranker-base` reorders the pooled candidates.

| run | route acc. | recall@k | MRR | fact recall | all facts (95% CI) | refusal acc. | live LLM calls | est. cost |
|---|---|---|---|---|---|---|---|---|
| first-round choice (hybrid, prompts v1) | 0.975 | 0.9821 | 0.9286 | 0.9464 | 0.9286 (0.8214–1.0) | 0.975 | 47 | — |
| hybrid, prompts v2 | 0.925 | 0.9821 | 0.9286 | 0.9167 | 0.8929 (0.7857–1.0) | 0.95 | 90 | $0.0271 |
| bge-rerank (vector pool), v2 | 0.925 | 1.0 | 0.9643 | 0.8988 | 0.8571 (0.7143–0.9643) | 0.95 | 46 | $0.0203 |
| bge-rerank (hybrid pool), v2 | 0.925 | 0.9821 | 0.9643 | 0.8988 | 0.8571 (0.7143–0.9643) | 0.95 | 8 | $0.0031 |
| hybrid, v3 | 0.925 | 0.9821 | 0.9286 | 0.9881 | 0.9643 (0.8929–1.0) | 1.0 | 37 | $0.0055 |
| bge-rerank (vector pool), v3 | 0.925 | 1.0 | 0.9643 | 0.9702 | 0.9286 (0.8214–1.0) | 1.0 | 3 | $0.0013 |
| hybrid, v4 | 1.0 | 0.9821 | 0.9286 | 0.9881 | 0.9643 (0.8929–1.0) | 1.0 | 40 | $0.0032 |
| bge-rerank (vector pool), v4 | 1.0 | 1.0 | 0.9643 | 0.9702 | 0.9286 (0.8214–1.0) | 1.0 | 0 | $0 |
| bge-rerank (hybrid pool), v4 | 1.0 | 0.9821 | 0.9643 | 0.9702 | 0.9286 (0.8214–1.0) | 1.0 | 0 | $0 |
| hybrid, v5 | 1.0 | 0.9821 | 0.9286 | 1.0 | 1.0 (1.0–1.0) | 1.0 | 51 | $0.0257 |
| **hybrid, v6 — chosen** | 1.0 | 0.9821 | 0.9286 | 1.0 | **1.0 (1.0–1.0)** | 1.0 | 0 (all cached) | $0 |
| bge-rerank (vector pool), v6 | 1.0 | 1.0 | 0.9643 | 0.9881 | 0.9643 (0.8929–1.0) | 1.0 | 46 | $0.0211 |
| bge-rerank (hybrid pool), v6 | 1.0 | 0.9821 | 0.9643 | 0.9702 | 0.9286 (0.8214–1.0) | 1.0 | 9 | $0.0036 |

Citation URL hit and citation support were 1.0 in every run. Against the first-round choice, the chosen v6 config gained dev-14 (now routed in scope) and dev-28 (now names form RC151); paired change in all-facts +0.0714 (95% CI 0.0–0.1786, n=28). The v4 routing sentences (about bank-account comparisons and about personal advice outside the covered topics) and the v5 rule to name forms exactly were written for specific dev misses (dev-39, dev-34, dev-37 and dev-28). I applied the same selection rule as before, and it picked v6 **without** the reranker. A dev score of 1.0 after four prompt revisions on the same 40 questions is overfitted to dev, which is part of why the held-out test number in the README matters.

**Reranker.** I compared three small open cross-encoders on dev retrieval only (no LLM calls), reranking the vector top 20 or the union of vector and full-text top 20 ([`eval_runs/retrieval-dev-rerank/results.txt`](../eval_runs/retrieval-dev-rerank/results.txt)):

| reranker (params) | pool | recall@1 | recall@3 | recall@5 | MRR (top 5) |
|---|---|---|---|---|---|
| none (vector only) | — | 0.750 | 0.929 | 0.964 | 0.946 |
| none (hybrid RRF, chosen) | — | 0.714 | 0.911 | 0.982 | 0.929 |
| cross-encoder/ms-marco-MiniLM-L-6-v2 (22M) | vector / hybrid | 0.732 | 0.946 | 1.000 | 0.946 |
| mixedbread-ai/mxbai-rerank-xsmall-v1 (~70M) | vector / hybrid | 0.714 | 0.964 | 0.982 | 0.923 |
| BAAI/bge-reranker-base (278M) | vector | 0.768 | 0.964 | 1.000 | 0.964 |
| BAAI/bge-reranker-base (278M) | hybrid | 0.768 | 0.964 | 0.982 | 0.964 |

`bge-reranker-base` was the best reranker on every dev retrieval number. The 28 questions took about 54 s on 8 CPU cores, including loading the model, so the latency is acceptable for a chat page. It was the one I took into full runs. End to end it lost by one question on all-facts (0.9643 vs 1.0), so the rule left it out. It stays in the code behind `RAG_RERANK=<model>` (scores cached in sqlite like the embeddings), off by default, and is not in the Docker image. I did not try larger rerankers such as `bge-reranker-v2-m3` (568M).

**Repeated sentences.** The chat page's licence example used to state the 60-day rule in four sentences. With the v5 prompt and the v6 dedupe step it states it in two (how long you can drive, then that you must switch after that). I also added a `repeat_free` diagnostic (a sentence with at least 80% of its content words in one earlier sentence counts as a repeat). Recomputed from the saved answers it was 26/27 → 27/28 on dev and 16/19 → 18/21 on test. It is a lexical heuristic that misses repeats in different words, so I don't gate on it.
