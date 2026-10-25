# Journal

Built on 2026-10-24 (America/Toronto): a first version, then a second round of polish and accuracy work (decisions 21–28). Each decision is listed with its reason. "Fixed by the brief" means the brief decided it and I did not reopen it.

## Decisions

| # | decision | reason |
|---|---|---|
| 1 | Stack: Python 3.11 (uv), LangGraph, FastAPI, Pydantic, pytest, Postgres 16 + pgvector, Docker Compose, GitHub Actions | fixed by the brief |
| 2 | LLM model `deepseek-flash`, called at `https://api.deepseek.com/chat/completions` with thinking disabled, temperature 0, JSON output, max 700 tokens | DeepSeek's docs list `deepseek-chat` as a legacy alias; `deepseek-flash` is the current cheap model. Thinking off because these are short extraction tasks and thinking tokens are billed as output. Every response's `model` field was `deepseek-flash` (621 of 621 ledgered calls; the one smoke call before the ledger existed is labelled separately). |
| 3 | Embeddings: local `BAAI/bge-small-en-v1.5`, 384 dims, query instruction prefix, batches of 16, on-disk cache keyed by sha256(model, kind, text) storing only vectors | model fixed by the brief; batch size because only ~3 GB RAM was free; the cache lets CI replay without torch |
| 4 | Retrieval scan is exact (no ANN index) | 290 chunks; an exact cosine scan is milliseconds and removes index recall as a variable |
| 5 | Chunking: heading-first, then ~500 tokens / 80 overlap, token count from a regex tokeniser (not bge's tokeniser) | split rule fixed by the brief; regex tokeniser so CI does not need the model. Because pages split on headings, chunks average ~129 tokens, so the size setting rarely bites (confirmed by the 300/500/800 experiment). |
| 6 | Fetching: httpx first, headless Chrome fallback; raw HTML cached in gitignored `data/local/raw/` | Canada.ca intermittently blocked httpx; caching means one fetch per page |
| 7 | 20 sources: 3 SIN, 4 OHIP, 2 banking, 7 tax/benefits, 3 driving, 1 Photo Card | covers the five topics in the brief; Photo Card added because newcomers without a licence need ID |
| 8 | Questions: 70 drafted by me (the agent) from the fetched pages, every key fact mechanically checked to appear in its expected page. Categories: in_scope, out_of_scope, needs_professional, unclear and unanswerable (in scope, but the pages don't say) | the brief asked for refusal testing; "unanswerable" tests the "could not find" path separately from routing |
| 9 | Split dev 40 / test 30, stratified by category, seed 20261024; test frozen with sha256, `--final` required | fixed by the brief. Taking the first 50 in-scope drafts left the topics unbalanced (too few driving questions), so I dropped 13 drafts by a fixed list before splitting, giving 7 dev / 5 test driving questions. |
| 10 | Metrics: route accuracy, recall@k and MRR (page level), key-fact recall and all-facts (rule-based string match), citation URL hit, citation support (lexical), refusal accuracy; each with n and a 10,000-resample bootstrap CI (seed 42) | no LLM judge, so metrics are free, deterministic and replayable in CI |
| 11 | Verify = rule checks (citations exist and point at retrieved chunks; every number in the answer appears in the cited chunks) **then** the LLM verifier | the brief requires numbers and dates to be in the sources; a rule check does that exactly and cheaply, the LLM handles "is this claim supported" |
| 12 | LLM cache stores only served model, response content and token usage, keyed by a hash of the prompt | prompts contain page text; storing only the key keeps page text out of the committed CI cache |
| 13 | Spend ledger with a $1.50 hard stop checked before every live call; cost estimated at **peak** prices | brief's cap; peak prices give an upper bound because I can't see which calls fell off-peak |
| 14 | CI on 16 fixture pages I wrote (paraphrased, CC0) with committed embedding and LLM caches, gate thresholds just under the cached run | the real page text can't be committed, so the brief's fixture option applied. A pre-push scan found one 12-word run in a fixture matching an official sentence; I reworded it and regenerated both caches. |
| 15 | Selection rule for dev experiments, written before comparing: highest all-facts, then refusal accuracy, then cost | avoids picking whichever metric looks best afterwards |
| 16 | Chose hybrid retrieval (500 tokens, k=5, verify on) | won by the rule (0.929 vs 0.857 baseline), but by 2 questions of 28 with overlapping CIs |
| 17 | Kept the verify node although it caught nothing on dev | the design requires it, it's cheap (about one extra call per answer), and dev-sized samples can't show the rare case it exists for |
| 18 | Docker image installs CPU-only torch and bakes the bge model in; the container ingests on start, reading cached pages from the mounted `data/local/` | small image, no model download at run time, no page text in the image |
| 19 | Git: small initial commit on `main`, all work on branches merged by PR after CI passed; no force pushes; `scripts/prepush_scan.py` run before every push | brief's rules |
| 20 | Commit author `AbhishekRamma <91196410+AbhishekRamma@users.noreply.github.com>` | the box had no git identity; the noreply address avoids publishing a personal email |
| 21 | Second round: change routing and answer prompts, tuned on dev only; never open new test failures | the first test run had shown over-cautious routing (already documented); the frozen set may only be scored, not tuned on |
| 22 | Routing prompt v4: general rules, options, processes, fees, forms, deadlines and "what can I do after a refusal" are in scope even in the first person; `needs_professional` only for advice that depends on judging the person's own case | v2 overcorrected (dev-21, dev-26 to `needs_professional`, dev-30 to `in_scope`); v3 sent dev-34/37 to `out_of_scope` and dev-39 (comparing bank accounts) to `out_of_scope`, so v4 added a sentence for each. These sentences are fitted to dev questions. |
| 23 | Answer prompt v5: "never repeat a fact", merge excerpts that say the same thing into one sentence with all their citations; name forms and programmes exactly as the excerpts do | the chat-page licence answer stated the 60-day rule in four sentences; dev-28 kept leaving out form RC151 |
| 24 | Deterministic dedupe in the output node: drop a sentence whose content words and numbers (at least 3) all appear in one earlier sentence, moving its citations to that sentence | the prompt alone did not reliably stop repeats; a pure subset rule cannot remove a sentence that adds anything new |
| 25 | Cross-encoder reranker `BAAI/bge-reranker-base` implemented (`RAG_RERANK`), scores cached in sqlite, **off by default** | best of three small open cross-encoders on dev retrieval (MiniLM-L6, mxbai-xsmall, bge-base); but end to end it scored all-facts 0.9643 vs 1.0 without it, so the pre-set rule left it out |
| 26 | Kept hybrid retrieval, no reranker, prompts v5 + dedupe ("v6") as the configuration, chosen on dev before the second test run | the selection rule (all-facts, then refusal accuracy, then cost). I would have kept it even if the test run had been worse. |
| 27 | `--compare` reports a paired bootstrap CI of the difference (10,000 resamples of question ids, seed 42) | two unpaired CIs overlapping says little about a paired change |
| 28 | Ask button and user bubble darkened to at least 4.5:1 with white text, measured on the rendered page | white on the tangerine gel was 1.60:1, below WCAG AA |

## Deviations from the brief

1. **Hybrid retrieval instead of pure cosine top-5.** Still top 5, but fused with Postgres full-text search (RRF, k=60, 20 candidates per side). Reason: best on dev by the pre-set rule. Cost: it caused one held-out miss (test-21), see failure analysis.
2. **Rule-based checks inside verify** in addition to the LLM verifier (decision 11).
3. **A fifth question category, "unanswerable"** (decision 8).
4. **Host-network Compose override** (`docker-compose.hostnet.yml`), because plain `docker compose up` could not network on this box.
5. **Pre-push scanner script** that checks for keys and 12-word runs copied from the pages, so the "no page text" rule is tested rather than assumed.
6. **`deepseek-flash` instead of `deepseek-chat`** (decision 2).

No early stop: spend stayed far under the cap and no login was missing.

## Spend

Prices from DeepSeek's pricing page (<https://api-docs.deepseek.com/quick_start/pricing>), read 2026-10-24, for `deepseek-flash` per million tokens at peak (01:00–04:00 and 06:00–10:00 UTC on weekdays): $0.30 input cache miss, $0.006 input cache hit, $1.20 output; off-peak is half. All figures below are **estimates** from the token counts in the API responses, not a bill.

| stage | live calls | est. cost (peak prices) |
|---|---|---|
| smoke test + dev experiments (7 runs; later runs reuse cached route calls) | 354 | $0.1035 |
| CI fixture caches (first build, then rebuilt after rewording a fixture) | 194 | $0.0247 |
| Docker curl tests | 5 | under $0.001 |
| frontend screenshots (3 new questions; repeats came from the cache) | 3 | $0.0009 |
| held-out test run (`--final`) | 69 | $0.0189 |
| first round total | 625 | $0.149 |
| second round: dev runs (9 runs with live calls; 3 fully cached) | 330 | $0.1109 |
| second round: CI fixture cache rebuild | 99 | $0.0141 |
| second round: held-out test run (`--final`) | 71 | $0.0209 |
| second round: screenshots, the licence-answer check and one call whose cache write failed (a permissions error on `data/local`) | 15 | $0.0021 |
| **total** | **1,140** | **$0.2969** (ledger peak estimate $0.2968914) |

First-round tokens: 363,254 input cache-miss, 86,777 input cache-hit, 32,875 output. Second-round costs per run come from each run's `config.json` (`est_cost_usd_peak_this_run`); the last row is the ledger total minus the run totals. Ledger totals for both rounds: 733,586 input cache-miss, 156,017 input cache-hit and 63,232 output tokens; off-peak lower bound $0.1484. Served model: `deepseek-flash` on all 1,139 ledgered calls (plus the one smoke call from before the ledger).

## Experiments (dev, n=40; retrieval and facts on the 28 answerable)

See the README table; the raw files are in `eval_runs/`. Observations:

- Chunk size made almost no difference (chunks are heading-bounded and average ~129 tokens).
- k=3 hurt (all-facts 0.786); k=8 and 800 tokens each helped all-facts by one question but each produced one citation that failed the lexical support check.
- Hybrid recovered dev-05 (a fact in a chunk cosine ranked lower).
- Verify on vs off: the only verify retry on dev (dev-19, baseline) was a false positive that cost a fact, so "no verify" scored one question higher. On this data, verification added cost without catching an error.
- After fixing a number-normalisation bug ("0.50" was read as ".5"), I re-ran the chosen config from cache: identical metrics.

## Second round on dev

The full table is in the README. In order:

- Reranker, retrieval only (no LLM cost): `bge-reranker-base` over the vector top 20 gave recall@5 1.000 and MRR 0.964, against 0.982 and 0.929 for the hybrid baseline. MiniLM-L6 also reached recall@5 1.000 but with MRR 0.946; mxbai-xsmall did not beat the baseline.
- Prompts v2: all-facts fell to 0.8929 and route accuracy to 0.925; my first routing rewrite overcorrected.
- v3 and v4: routing back to 1.0 on dev only after v4's extra sentences; all-facts 0.9643.
- v5 (anti-repeat and exact form names): all-facts 1.0, dev-28 fixed.
- v6 (v5 + dedupe): same metrics as v5, from cache. Against the first-round choice: dev-14 and dev-28 gained, nothing lost; paired change in all-facts +0.0714 (95% CI 0.0–0.1786, n=28).
- Reranker with v6: all-facts 0.9643 (vector pool; dev-05 lost the vision-test fact) and 0.9286 (hybrid pool; dev-05 and dev-28).

A perfect dev score after four prompt versions mostly says the prompts now fit these 40 questions.

## CI and the degrade check

- PR #1 (pipeline) CI passed; merged; `main` CI passed after the merge.
- Second round: the prompts changed, so every cached CI response would miss. I rebuilt both fixture caches with `scripts/build_ci_cache.sh` (fresh database, live ingest of the fixtures, one live dev run: 99 calls). The embedding cache came out byte-identical; the LLM cache was replaced. Locally, with the CI environment and no API key, the replay passed the gate (99 cache hits, 0 misses), and `RAG_TOP_K=1` failed it (route 0.225, recall@k 0.821, all-facts 0.0, refusal 0.300; 31 cache misses). I raised the gate thresholds to sit just under the new cached run (for example all-facts 0.92 to 0.96, fact recall 0.93 to 0.97; full list in `ci/README.md`).
- PR #2 set top-k to 1. The gate failed: recall@k fell from 0.982 to 0.821 (a pure retrieval signal), and the 30 changed prompts missed the LLM cache, so answer metrics collapsed. Closed unmerged. This shows the gate catches regressions, but also that a cached gate cannot tell a good prompt change from a bad one.

## Held-out run

First run, after CI, Docker and the configuration were settled: all-facts 0.773 (CI 0.591–0.909, n=22), refusal accuracy 0.900 (CI 0.767–1.000, n=30). Nothing was changed after it within that round.

Second run (`test-c500-k5-hybrid-verify-v6`), once, after the second-round configuration was fixed on dev. Before it I checked that the test file's sha256 still matched `data/questions/test.sha256` (43c8eb99…2e931). Results against the first run, paired CIs:

| metric | first | second | change | 95% CI of change | n |
|---|---|---|---|---|---|
| all-facts | 0.7727 | 0.8636 | +0.0909 | 0.0–0.2273 | 22 |
| key-fact recall | 0.8182 | 0.9091 | +0.0909 | 0.0–0.2273 | 22 |
| recall@5 | 0.9545 | 0.9545 | 0.0 | 0.0–0.0 | 22 |
| route accuracy | 0.9 | 0.9667 | +0.0667 | 0.0–0.1667 | 30 |
| refusal accuracy | 0.9 | 0.9667 | +0.0667 | 0.0–0.1667 | 30 |

The two gains (test-02, test-22) are the over-cautious routing cases the first run had exposed, so this is not independent evidence: the direction of the router change came partly from the test set, even though I tuned only on dev. No question got worse. The configuration was chosen on dev and I would have kept it if the test numbers had dropped.

## Frontend

A single chat page at `/`, added after the backend was finished.

- **No build step.** Plain HTML, CSS and JavaScript in `src/static/`, served by FastAPI's `StaticFiles`. It ships in the existing image (the Dockerfile already copies `src/`) and Compose needs no extra service. A Node toolchain would add a second ecosystem for one page.
- **Nothing from other origins.** No font CDN, analytics or icon kit. Headings use the system monospace stack (`ui-monospace`, Menlo, Consolas, DejaVu Sans Mono…) for the retro display feel, so there is no font licence to track. The pixel logo is drawn with CSS box-shadows and the grain is an inline SVG noise filter. A test fails if `/`, the CSS or the JS points at another origin.
- **Look.** Retro: monospace headings with a pixel-offset shadow, a menu-bar strip, a pinstriped title strip, faint CRT scanlines and grain, a warm pastel palette (peach, lilac, mint, butter) and glossy gel buttons in tangerine. Glass: translucent panels with `backdrop-filter: blur(22px) saturate(170%)`, an inset top highlight, a radial "lens" highlight and a gradient rim (masked border) for a refraction-like edge, over slowly drifting colour blobs. I left out window controls, system icons and any logo so it reads as its own design rather than a copy of an operating system.
- **Readability on glass.** Body text is dark plum (#241c2b) on panels that stay at least 42% opaque, and answers sit on 66% opaque glass. If `backdrop-filter` isn't supported, or the user asks for more contrast, panels become solid cream and the scanlines are removed.
- **States.** Answers are green-tagged with numbered citation links and a sources list (page, section, fetch date). Refusals use an amber panel with a dashed rim, a warning glyph and a label such as "Out of scope · out_of_scope", so they can't be mistaken for an answer. Errors get a red panel: "can't reach the server" (which also rechecks `/health`), the 503 budget stop and 422 length errors each have their own message. A barber-pole bar shows while it is working.
- **Safety.** Model output and page titles are inserted with `textContent` and built elements, never `innerHTML`. Citation links are only made from the `[chunk-id](url)` pattern, and only for http(s) URLs.
- **Accessibility.** A labelled textarea (Enter sends, Shift+Enter adds a line), real buttons for the chips, `aria-live` on the conversation and the health status, visible focus rings, and logical tab order (checked in headless Chrome). `prefers-reduced-motion` turns off every animation (checked: computed `animation-name` is `none`). Under 600px the topic list and health detail are hidden and nothing overflows sideways at 390px.
- **Bug found on the way.** The second `/ask` in a running server failed with a 500: FastAPI runs sync endpoints in a thread pool, and the embedding cache's sqlite connection refused use from another thread. It depends on which pool thread serves a request, which is probably why my earlier one-at-a-time curl tests passed (not verified). I opened the connection with `check_same_thread=False` and put a lock around it, with a regression test that fails without the fix.
- **Checks.** pytest checks that `/` serves the page, every referenced static asset returns 200, no asset loads from another origin, and a missing asset is 404. Screenshots were taken with Playwright driving the box's Chrome: an answer, a refusal and a 390px phone width. The README uses the refusal shot because its text is my own refusal wording, not page text. With the host-network override, the Docker image served `/`, the CSS and the JS (200), and the same Playwright run passed against it, using cached answers at no extra cost.

## Frontend, second round

- **Contrast.** White "Ask" text on the tangerine gel measured 1.60:1 (1280 px) and 1.56:1 (390 px); the user bubble 2.67:1. I darkened the gel gradient (#c2502c to #a83c1a), kept the gloss to a 9 px band at the top, and darkened the bubble. Measured on the rendered page by `scripts/check_contrast.py` (white against the lightest pixel behind the text): 5.10:1, 4.96:1 and 5.73:1.
- **Repeats.** The licence chip answer went from four sentences giving the 60-day rule to two that say different things (how long you can drive, and that you must switch after that). I checked this by reading the answer; the lexical `repeat_free` metric is only a rough guide.
- Screenshots retaken (answer, refusal, 390 px phone); no console errors. Whether the page reads well with a real screen reader is not yet verified by me.

## Web app and OIDC sign-in (third round)

Built on 2026-10-24 (America/Toronto) on the branch `feature/web-auth`. The brief fixed the main choices: React 18 + TS strict + Vite, Keycloak with a public PKCE client, `oidc-client-ts` with in-memory tokens, PyJWT + cryptography with my own dependency, a plain-SQL migration, and the endpoint contract. Below are the decisions I made inside those limits.

| # | decision | reason |
|---|---|---|
| 29 | Removed the static page (`src/static/`, its test) and serve the React app from its own nginx container on :5173 | the brief replaces the plain HTML page. A separate origin also makes CORS and the CSP real rather than theoretical |
| 30 | Keycloak 26.4 in `start-dev --import-realm`, with `KC_HOSTNAME=http://localhost:8080` and a dynamic backchannel | the issuer must be the same URL for the browser and for the API's `iss` check, while the API fetches the JWKS over the internal network. Hence a separate `OIDC_JWKS_URL` |
| 31 | An audience mapper on the `web` client puts `newcomer-api` in access tokens; the API requires that audience | Keycloak's default access-token `aud` is `account`. Requiring my own audience means tokens minted for other clients in the realm are refused, and ID tokens (`aud: web`) can't be used as access tokens |
| 32 | **Two** demo users (`demo`, `demo2`) instead of the brief's one | step 6 needs a second user to show that history is isolated. Both have obviously-demo passwords and are labelled local-only |
| 33 | Token checks: RS256 only, `kid` must be in the JWKS, required `exp`/`iat`/`iss`/`aud`/`sub`, 10 s leeway | the brief's list plus `sub` (the history key) and `iat`. An allow-list of one algorithm blocks the HS256 key-confusion and `alg: none` tricks, and unit tests cover both |
| 34 | JWKS cached for 5 min, refetched on an unknown `kid` at most every 30 s, old keys kept if a refresh fails | handles key rotation without letting junk `kid`s turn the API into a Keycloak load generator |
| 35 | Keycloak unreachable on the first JWKS fetch, or auth on with no issuer configured → **503**, not 401 | "the sign-in service is down" is not "your token is bad". It also fails closed: no request gets through unauthenticated |
| 36 | `AUTH_DISABLED=1` runs every request as `local-dev`; off by default; the README says so | fixed by the brief. The eval calls the agent directly, so it doesn't even need the flag |
| 37 | History table and index created by `src/migrate.py` from numbered `.sql` files, tracked in `schema_migrations` under a Postgres advisory lock | plain SQL as the brief asked. The lock means two API containers starting together can't race the migration |
| 38 | History is paginated with `limit` (1–100, default 20) and `offset`, plus `total`; another user's row and a missing row both return 404 | 404 rather than 403 doesn't confirm that someone else's id exists |
| 39 | Tokens in `InMemoryWebStorage`; PKCE state in `sessionStorage`; silent sign-in on load plus `automaticSilentRenew` through `silent-renew.html` | the brief rules out `localStorage`. Memory alone would mean signing in again on every refresh, so the Keycloak session cookie is used through a hidden iframe to get new tokens. Cost and caveats are in `docs/auth_design.md` |
| 40 | Typed API client with run-time shape guards (`isAskResponse`, `isHistoryPage`) instead of casting `res.json()` | strict TS with no `any` is only honest if the network boundary is checked. A 401 or a missing token calls `onUnauthorized`, which starts a new sign-in |
| 41 | ESLint 9 with typescript-eslint `strictTypeChecked`, `--max-warnings 0`; TS `exactOptionalPropertyTypes` and `noUncheckedIndexedAccess` | the strictest common settings. They found a needless type assertion and a hook exported from a component file |
| 42 | nginx serves the built app with a CSP (`script-src 'self'`, `connect-src` = API + Keycloak, `frame-src` = self + Keycloak) | in-memory tokens are only as safe as the page is from XSS |
| 43 | Integration check scripted twice: httpx doing the real PKCE login form (`scripts/auth_integration.py`), and Playwright on the real UI (`scripts/ui_check.py`) | the httpx script proves the API contract without a browser. Playwright proves the browser flow, the storage claims and silent sign-in |
| 44 | CI: three separate jobs (`web-lint`, `web-typecheck`, `web-test` including a production build) on Node 22; pytest gets `REQUIRE_PG=1` so the Postgres history test can't skip quietly; thresholds unchanged | separate jobs name the failing check on the PR. Node 22 matches the web Dockerfile (I ran the checks locally on Node 20.19) |

**Problems found on the way (all fixed):**

- **Lint and type errors.** ruff B008 on `Depends(...)` defaults, fixed with `Annotated` aliases. `node:path` and `import.meta.dirname` were untyped, fixed by adding `@types/node`. ESLint `unbound-method` in a test, fixed with a standalone `vi.fn`.
- **Scripted login returned 400** (`cookie_not_found` in Keycloak's log). Keycloak 26 sets its login-session cookies `Secure; SameSite=None` even on http://localhost. Browsers send them, because localhost counts as a secure context; httpx doesn't. The script now forwards them explicitly.
- **The first scripted `/ask` came back as a 200 refusal** with reason `llm_cache_miss`: that question wasn't in the LLM cache, and the cached provider never calls the API. I switched to a dev-set question to keep spend at zero.
- **Silent sign-in failed on reload**, with a CSP violation in the console. My own `frame-src` allowed Keycloak but not `'self'`, and the iframe lands on `/silent-renew.html`. I added `'self'`.
- **PKCE state was in `localStorage`.** oidc-client-ts defaults the *state* store to `localStorage`. I had only set the user store. I set the state store to `sessionStorage` and added a test. No access token was ever stored there.

**Checks (local, 2026-10-24, 22:09–22:16 EDT):**

- pytest: 62 passed, with the Postgres test running against a real database. ruff is clean.
- Vitest: 17 passed. ESLint and `tsc --noEmit` are clean, and `vite build` works.
- Integration: all 12 pass/fail checks passed. Headless Chromium signed in, asked, showed history, re-signed silently on reload, and signed out ([`auth_evidence.md`](auth_evidence.md)).
- Dev evaluation, `AUTH_DISABLED=1 LLM_PROVIDER=cached`, run `dev-c500-k5-hybrid-verify-v6-authcheck`: identical to `dev-c500-k5-hybrid-verify-v6` on every metric (route 1.0, recall@5 0.9821, MRR 0.9286, fact recall 1.0, all facts 1.0, citation URL hit 1.0, citation support 1.0, refusal 1.0). It made 99 cache hits, 0 misses and 0 live calls.
- I passed `--gate ci/thresholds.json` to that local run by habit, and it reported FAIL on MRR (0.9286 < 0.97). That is expected and not new: the thresholds belong to the CI replay on the fixture pages (where MRR is 1.0, `eval_runs/ci-dev`), not to the real 20-page index, whose MRR has been 0.9286 since round one. I left the thresholds unchanged. The CI gate result is in the PR checks.

**Spend:** $0. The ledger was byte-identical before and after this round (1,140 calls, $0.2968914 total).

**Not verified:** plain bridge-network Compose with the new services, Firefox and Safari, silent renew at the 300 s expiry, a TLS or non-localhost deployment, and the React app's colour contrast (the old page was measured; this one wasn't).

## Gate thresholds review

| # | decision | reason |
|---|---|---|
| 45 | I reviewed the stricter thresholds I raised in PR #5 and chose to **keep** them as they are in `ci/thresholds.json`: route 0.97, recall@5 0.95, MRR 0.97, fact recall 0.97, all key facts 0.96, citation URL hit 0.97, citation support 0.97, refusal accuracy 0.97 (raised from 0.95, 0.95, 0.95, 0.93, 0.92, 0.95, 0.95, 0.95) | CI passes on main with them, and a stricter gate guards against quiet regressions. If a legitimate change trips one, I'll lower that single threshold deliberately, in its own commit with the reason, rather than loosening the whole gate. They are calibrated for the CI replay on the fixture pages (`eval_runs/ci-dev`: recall@5 0.9821, every other metric 1.0), not for the full dev run on the real pages, where MRR is 0.9286 and would fail the 0.97 MRR line by design |

## How I'd improve this

1. **A new held-out set.** This one has been scored twice and the second run measured fixes for its own documented failures. Any further claim needs fresh questions, written before looking at the system's answers.
2. **Router.** The second round fixed dev-14, test-02 and test-22, but test-30 still goes to `out_of_scope` instead of retrieval. I'd send borderline cases to retrieval rather than refusing.
3. **Retrieval fusion.** Weight the vector side in RRF or only add full-text hits that also appear in the vector top 20 (test-21), and add chunk-level recall next to page-level recall (test-01).
4. **Scoring.** Add an entailment or LLM judge alongside the string-match key facts and report both, so correct paraphrases (test-16) aren't scored as misses.
5. **Questions.** Have a person review all 70 (still pending), and grow the test set: n=22 answerable gives ±16-point CIs.
6. **Freshness.** A scheduled job that refetches pages, diffs the text and flags questions whose source chunks changed.
7. **CI.** Add a small weekly live job on the fixtures, capped at a few cents, so prompt changes are graded instead of only detected.
8. **Auth.** Move to a backend-for-frontend with an httpOnly session cookie so tokens never reach JavaScript, add token revocation checks (introspection or short-lived tokens plus back-channel logout), and run Keycloak in production mode with TLS and a real database.
9. **Docker.** Test plain Compose on a second machine and include headless Chrome in the image so a cold start can fetch Canada.ca pages.
