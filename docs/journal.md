# Journal

Built on 2026-10-24 (America/Toronto) in three rounds: the retrieval and evaluation pipeline, a second round of accuracy work on dev, then the React web app with OIDC sign-in. Raw evaluation outputs are in [`eval_runs/`](../eval_runs/) and the dev comparisons in [`dev_experiments.md`](dev_experiments.md).

## Decisions

**Write the selection rule before comparing configurations.**
Why: highest all-facts, then refusal accuracy, then cost, fixed in advance, so I couldn't pick whichever metric looked best afterwards. It chose hybrid retrieval (0.929 vs 0.857 baseline on dev) and later left out a reranker that won on retrieval but scored 0.9643 vs 1.0 end to end.
Trade-off: the hybrid win was two questions of 28 with overlapping CIs, and hybrid fusion caused one held-out miss (test-21).

**Freeze the test set and score it only with `--final`.**
Why: 70 questions split dev 40 / test 30, stratified by category (seed 20261024); the test file is checked against a sha256 before every scored run.
Trade-off: a second test run after the routing changes means the second-run numbers are not clean. I report both runs with paired CIs and say so.

**Score with rules, not an LLM judge.**
Why: route accuracy, recall@k, MRR, key-fact string matching, citation URL hit, lexical support and refusal accuracy, each with n and a 10,000-resample bootstrap CI (seed 42). Free, deterministic and replayable in CI.
Trade-off: a correct paraphrase can score as a miss, and the support check is lexical, not entailment.

**Verify with rule checks first, then the LLM.**
Why: citations must point at retrieved chunks and every number must appear in the cited chunks; a rule does that exactly and cheaply. I kept the verify node although it caught nothing real on dev, because dev-sized samples can't show the rare case it exists for.
Trade-off: about one extra call per answer, and its one dev retry was a false positive that cost a fact.

**Gate CI on a cached replay over fixture pages.**
Why: page text can't be committed, so CI ingests 16 paraphrased CC0 fixture pages and replays cached embeddings and LLM responses against [`ci/thresholds.json`](../ci/thresholds.json), set just under the cached run. I proved it with broken PRs (#2, #6 and #8), all red and closed unmerged.
Trade-off: a changed prompt misses the cache, so the gate can't tell a good prompt change from a bad one.

**Cap spend before every live call.**
Why: a ledger with a $1.50 hard stop, costed at peak prices to give an upper bound. The LLM cache stores only the served model, response content and token usage, keyed by a prompt hash, so no page text lands in the committed cache.
Trade-off: the totals are estimates, not billed amounts.

**Strict token checks and in-memory tokens.**
Why: RS256 only, `kid` from the JWKS, required `exp`/`iat`/`iss`/`aud`/`sub`, and an audience mapper so only tokens minted for `newcomer-api` are accepted. JWKS is cached with rotation handling; if Keycloak is unreachable the API returns 503, not open access. Tokens live in memory, with silent sign-in through the Keycloak session cookie and a CSP on the web app.
Trade-off: silent renew uses a hidden iframe, which browsers that block third-party cookies would break if Keycloak ran on a different site; details in [`auth_design.md`](auth_design.md).

**Use `deepseek-flash`, not `deepseek-chat`.**
Why: DeepSeek's docs list `deepseek-chat` as a legacy alias. I logged the served `model` on every response (621 of 621 ledgered calls were `deepseek-flash`).
Trade-off: results are tied to whatever DeepSeek serves under that name.

## What went wrong and how I fixed it

- **sqlite across threads.** The second `/ask` on a running server returned 500: FastAPI runs sync endpoints in a thread pool, and the embedding cache's sqlite connection refused use from another thread. I opened it with `check_same_thread=False`, added a lock and a regression test that fails without the fix.
- **Scripted Keycloak login returned 400** (`cookie_not_found`). Keycloak 26 sets its login cookies `Secure; SameSite=None` even on http://localhost; browsers send them, httpx doesn't. The integration script now forwards them.
- **PKCE state in `localStorage`.** oidc-client-ts defaults its state store to `localStorage`; I had only set the user store. I moved state to `sessionStorage` and added a test. No access token was ever stored there.
- **Silent sign-in blocked by my own CSP.** `frame-src` allowed Keycloak but not `'self'`, and the iframe lands on `/silent-renew.html`. I added `'self'`.
- **Docker bridge networking failed on my build machine.** I added `docker-compose.hostnet.yml` and documented it.
- **Number normalization read "0.50" as ".5".** Fixed; a cached re-run of the chosen configuration gave identical metrics.
- **The first test run steered the second round.** It exposed over-cautious routing, and I tuned the router on dev to fix it. That's why the second test run is flagged as not clean.

**Spend:** 1,140 calls, about $0.2969 estimated at peak prices, under a $1.50 cap.
