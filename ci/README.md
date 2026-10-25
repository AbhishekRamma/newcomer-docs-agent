# CI fixtures

CI cannot use the real government pages: their text must not be committed, and fetching them from GitHub-hosted runners is unreliable. So CI runs the real pipeline (chunking, pgvector + full-text retrieval, the LangGraph agent, verification, scoring) against stand-in documents.

- `docs/` holds 16 short markdown pages I wrote as paraphrased summaries of the facts the dev questions need. They are **not authoritative** and are not copies of the official pages; each one links to the page it stands in for. Released under CC0.
- `embed_cache.sqlite` holds bge-small-en-v1.5 vectors keyed by sha256(model, kind, text). It stores no text.
- `llm_cache/` holds DeepSeek responses (served model, JSON content, token usage) keyed by sha256 of the model, messages and parameters. Prompts are not stored. The content is model output written from the fixture pages above.

Both caches were filled by one live run, rebuilt with [`scripts/build_ci_cache.sh`](../scripts/build_ci_cache.sh) whenever prompts change (fresh `rag_ci` database, live ingest of the fixtures, one live dev run), (`ci-dev` in `eval_runs/`) and CI replays them with `EMBED_PROVIDER=cached LLM_PROVIDER=cached`. A cache miss makes the agent refuse (`llm_cache_miss`), so any change to prompts, retrieval or chunking that alters what the model would see shows up as a drop in the gate metrics rather than passing silently.

`thresholds.json` sits a little below the cached run's values. In the second round I raised it to route 0.97, recall@5 0.95, MRR 0.97, fact recall 0.97, all-facts 0.96, citation URL hit 0.97, citation support 0.97 and refusal accuracy 0.97 (from 0.95, 0.95, 0.95, 0.93, 0.92, 0.95, 0.95, 0.95). The second-round rebuild produced route 1.0, recall@5 0.9821, MRR 1.0, fact recall 1.0, all-facts 1.0, citation URL hit 1.0, citation support 1.0 and refusal accuracy 1.0 (`eval_runs/ci-dev`).

What this proves: the code paths run end to end and are deterministic on replay. What it does not prove: answer quality on the real pages, or behaviour of a fresh model call. Those come from the local dev and test runs.
