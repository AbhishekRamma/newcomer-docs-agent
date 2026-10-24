# newcomer-docs-agent

- **What it does:** answers Ontario newcomer questions (SIN, OHIP, bank account, first tax return, driver's licence) only from 20 official government pages, with an inline citation on every sentence, and refuses when the pages don't cover it or the question needs personal legal, tax or immigration advice.
- **Stack:** Python 3.11, LangGraph, FastAPI, Pydantic, PostgreSQL + pgvector, local `BAAI/bge-small-en-v1.5` embeddings, DeepSeek (`deepseek-flash`) through its OpenAI-compatible API, pytest, Docker Compose, GitHub Actions.
- **Best held-out result (frozen test set, run once):** all key facts present in 77.3% of answerable questions (95% bootstrap CI 59.1–90.9%, n=22); refusal accuracy 90.0% (CI 76.7–100%, n=30); every answered, answerable question cited an expected source (n=19).
- **Run:** `uv sync --extra embed --extra dev` → `python -m src.ingest` → `python -m src.graph "How do I apply for a SIN?"` or `docker compose up` (see [Run it](#run-it)); evaluate with `python -m src.evaluate --split dev`.
- **Chat page:** open <http://localhost:8000/> once the API is running: a retro, frosted-glass page that shows cited answers, refusals with their route, and API health (see [Use the chat page](#use-the-chat-page)).
- **Local-only:** page text, embedding and LLM caches, full answers and the spend ledger live in the gitignored `data/local/`; CI runs on paraphrased fixture pages with cached responses.

## The problem

Someone new to Ontario has the same five errands in their first weeks: get a SIN, apply for OHIP, open a bank account, file a first tax return, and exchange a driver's licence. The answers are on Canada.ca and ontario.ca, but spread over dozens of pages, and a general chatbot will happily invent a waiting period or a form number. I wanted an assistant that only says what the official pages say, shows where each sentence came from, and says "I could not find this in the sources" or "please talk to a professional" instead of guessing.

## How it works

```mermaid
flowchart LR
    Q[Question] --> R{route<br/>LLM classifier}
    R -- in_scope --> RET[retrieve<br/>pgvector cosine + Postgres full-text<br/>fused with RRF, top 5]
    R -- out_of_scope / needs_professional / unclear --> OUT
    RET --> A[answer<br/>JSON, every sentence cites a chunk id]
    A --> V{verify<br/>rules: citations exist, every number is in the cited chunks<br/>LLM: each claim supported}
    V -- pass --> OUT[output<br/>citations as chunk id + URL, disclaimer]
    V -- fail, first time --> A
    V -- fail again --> NF[I could not find this in the sources.] --> OUT
```

- **Ingest** (`src/ingest.py`): fetches the 20 pages listed in [`data/SOURCES.md`](data/SOURCES.md), strips navigation, splits on headings first and then into chunks of at most ~500 tokens with 80 tokens of overlap, embeds them with bge-small (batches of 16) and stores them in pgvector. Each chunk keeps its heading path, URL and fetch date.
- **Graph** (`src/graph.py`): a LangGraph `StateGraph` with the five nodes above. Route labels are `in_scope`, `out_of_scope`, `needs_professional` and `unclear`.
- **LLM** (`src/llm.py`): one interface with a `live` provider (DeepSeek) and a `cached` replay provider. Every response is stored on disk under a sha256 of the model, messages and parameters; a spend ledger estimates cost from the token usage and refuses new live calls past $1.50.
- **API** (`src/api.py`): `POST /ask` and `GET /health`.

## Results

### Held-out test set (30 questions, frozen by sha256, scored once with `--final`)

| metric | value | 95% CI | n |
|---|---|---|---|
| all key facts present (`facts_all`) | 0.773 | 0.591–0.909 | 22 answerable |
| key-fact recall | 0.818 | 0.659–0.955 | 22 |
| retrieval recall@5 (expected URL retrieved) | 0.955 | 0.864–1.000 | 22 |
| retrieval MRR | 0.901 | 0.788–1.000 | 22 |
| answer cites an expected URL | 1.000 | 1.000–1.000 | 19 answered |
| every cited sentence passes the support check | 1.000 | 1.000–1.000 | 19 |
| route accuracy | 0.900 | 0.767–1.000 | 30 |
| refusal accuracy (refused exactly when it should) | 0.900 | 0.767–1.000 | 30 |

Configuration: 500-token chunks, top 5, hybrid retrieval, verification on (chosen on dev before the test run). CIs are percentile bootstrap, 10,000 resamples, seed 42. Cost of the test run: about $0.019 (estimate, see below). Breakdown of the six test failures: [`docs/failure_analysis.md`](docs/failure_analysis.md).

The drop from dev (0.929 all-facts) to test (0.773) sits inside overlapping CIs, but I treat it as the honest number: dev is where I looked at failures and chose the configuration. I changed nothing after seeing the test results. One test miss (test-21) was caused by the hybrid retrieval I chose on dev: vector search alone would have found the page.

### Dev experiments (40 questions; retrieval and fact metrics on the 28 answerable ones)

| run | recall@k | MRR | fact recall | all facts (95% CI) | citation support | refusal acc. | live LLM calls | est. cost |
|---|---|---|---|---|---|---|---|---|
| 500 tokens, k=5, vector, verify (baseline) | 0.964 | 0.946 | 0.926 | 0.857 (0.714–0.964) | 1.000 | 0.975 | 81 | $0.0191 |
| 300 tokens | 0.964 | 0.946 | 0.923 | 0.857 | 1.000 | 0.975 | 57 | $0.0185 |
| 800 tokens | 0.964 | 0.946 | 0.934 | 0.893 | 0.963 | 0.975 | 57 | $0.0200 |
| k=3 | 0.929 | 0.946 | 0.878 | 0.786 | 1.000 | 0.950 | 46 | $0.0082 |
| k=8 | 0.982 | 0.946 | 0.934 | 0.893 | 0.963 | 0.975 | 44 | $0.0131 |
| **hybrid (vector + full-text, RRF) — chosen** | 0.982 | 0.929 | 0.946 | **0.929 (0.821–1.000)** | 1.000 | 0.975 | 47 | $0.0197 |
| no verify node | 0.964 | 0.946 | 0.934 | 0.893 | 1.000 | 0.975 | 0 (all cached) | $0 |

Route accuracy was 0.975 (n=40) and expected-URL citation 1.000 (n=26–27) in every run. Every difference above is one to three questions out of 28, inside the CIs. I picked hybrid by a rule written down before comparing (highest all-facts, then refusal accuracy, then cost), not because it is clearly better. Raw outputs: [`eval_runs/`](eval_runs/).

## Run it

Needs Python 3.11, [uv](https://docs.astral.sh/uv/), Docker, and a DeepSeek API key in `.env` (copy `.env.example`).

```bash
uv sync --extra embed --extra dev
docker run -d --name ndocs-pg -e POSTGRES_USER=rag -e POSTGRES_PASSWORD=rag -e POSTGRES_DB=rag \
  -p 5433:5432 pgvector/pgvector:pg16
uv run python -m src.ingest --sizes 500          # fetch the 20 pages into data/local/, chunk, embed
uv run python -m src.graph "Is there a waiting period for OHIP?"
uv run python -m src.evaluate --split dev        # metrics with CIs into eval_runs/
uv run pytest -q && uv run ruff check .
```

Docker: `docker compose up --build` starts Postgres and the API on <http://localhost:8000>:

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/ask -H 'Content-Type: application/json' \
  -d '{"question": "How long can I drive in Ontario on a licence from another country?"}'
```

### Use the chat page

With the API running (`uv run uvicorn src.api:app` locally, or Docker as below), open <http://localhost:8000/>. Type a question and press Enter, or tap one of the example chips. Citation numbers link to the official page each sentence came from, and the sources list under the answer shows the page, section and fetch date. Refusals (out of scope, needs a professional, unclear, could not find it) show in an amber panel with their route label. The top strip shows `/health`. The page is plain HTML, CSS and JavaScript in `src/static/`, served by FastAPI, with no build step and nothing loaded from other sites.

![The chat page refusing an out-of-scope question](docs/frontend.png)

On my machine the default bridge network was broken, so I ran it with the host-network override: `docker compose -f docker-compose.yml -f docker-compose.hostnet.yml up` (details in [`docs/docker_evidence.md`](docs/docker_evidence.md)).

The test split is frozen: `python -m src.evaluate --split test` refuses to run without `--final`, and checks the file against `data/questions/test.sha256`.

## Known limitations

- **CI runs on cached responses, which proves less than it looks.** GitHub Actions lints, runs 21 unit tests, ingests 16 short fixture pages I wrote (paraphrases, not the official text), and replays the dev evaluation with cached embeddings and cached DeepSeek responses, failing below [`ci/thresholds.json`](ci/thresholds.json). That proves the whole pipeline runs and is deterministic, and that a change to retrieval, chunking or prompts is noticed: in [the degrade PR](https://github.com/AbhishekRamma/newcomer-docs-agent/pull/2) (top 5 → top 1) the gate went red. It does **not** grade new model output: a changed prompt misses the cache and the agent refuses, so the gate goes red whether or not the change was good. Answer quality on the real pages comes only from local runs.
- **The questions were drafted by the agent from the sources.** All 70 questions, their expected routes, expected URLs and key facts were drafted by the agent from the sources, and every key fact was checked mechanically against the fetched pages. My own review of them is pending, so treat the question set as **not verified**.
- **Rule-based scoring.** Key facts are matched as normalised strings (with alternatives), so a correct paraphrase can score as a miss (test-16 is one). Citation support is a lexical heuristic (≥60% of content words and every number present in the cited chunk), not an entailment model.
- **The verify node caught nothing real on dev.** It triggered one retry in the baseline run, which was a false positive. I kept it because it is part of the design and it is cheap insurance, but on these 40 questions it did not earn its cost.
- **Small samples.** n=22 answerable test questions gives CIs about ±16 points wide.
- **Plain `docker compose up` did not work on my build box** (no container-to-container traffic or DNS on the bridge network); the host-network override did. Plain compose on another machine is not verified. The container also expects the pages already fetched into `data/local/`; a cold start fetches them with httpx, and Canada.ca sometimes blocks that (locally I fall back to headless Chrome, which the image doesn't include).
- **Pages change.** Answers are only as current as the fetch date shown on every citation (2026-10-24).
- **Spend figures are estimates** from token counts and DeepSeek's published prices, not a bill.

## Data and licence notes

- No government page text is committed. The repo holds the URL list, my code, the questions, metric files without answer text, and CI fixtures I wrote myself (CC0). A pre-push script ([`scripts/prepush_scan.py`](scripts/prepush_scan.py)) checks every tracked file and the full `git log -p` for API keys and for any 12-word run copied from the fetched pages.
- Canada.ca pages: reusable for non-commercial purposes with attribution and a link ([terms](https://www.canada.ca/en/transparency/terms.html)). ontario.ca pages: © King's Printer for Ontario; non-commercial reproduction allowed with credit and without changes ([copyright](https://www.ontario.ca/page/copyright-information)). Page-specific notices and Open Government Licence – Ontario labels were not checked page by page: **unverified**. See [`data/SOURCES.md`](data/SOURCES.md).
- This is general information, not legal, tax or immigration advice, and it is not affiliated with any government.
- Decisions, spend and what I'd change next: [`docs/journal.md`](docs/journal.md).
