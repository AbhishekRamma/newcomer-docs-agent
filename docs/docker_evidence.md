# Docker evidence (2026-10-24, America/Toronto)

Docker 26 with Compose 2.26.1, run with `sudo` on my build machine.

## 1. Plain `docker compose up`: image builds, stack does not work on this host

- `sudo docker compose build` succeeded (image `newcomer-docs-agent-app`, CPU-only torch, bge-small baked in).
- `sudo docker compose up -d` started both containers and the db became healthy, but the app's ingest step hung with no output. From inside the app container:
  - `db` resolved to 172.19.0.2, but a TCP connect to db:5432 timed out;
  - `httpx.get("https://www.ontario.ca")` failed with "Temporary failure in name resolution".
- So the default bridge network on this host blocks container-to-container traffic and DNS. I have not tested plain compose on another machine, so whether it works elsewhere is **not verified**.

## 2. Host-network override: works

```
sudo docker compose -f docker-compose.yml -f docker-compose.hostnet.yml up -d
```

```
NAME                        IMAGE                     STATUS
newcomer-docs-agent-app-1   newcomer-docs-agent-app   Up About a minute
newcomer-docs-agent-db-1    pgvector/pgvector:pg16    Up About a minute (healthy)
```

App log: `index c500: 290 chunks`, `embedding cache: 290 hits, 0 computed`, `Uvicorn running on http://0.0.0.0:8000`.

## 3. curl

Answer text that paraphrases government pages is left out of the repo; everything else is verbatim.

```
$ curl -s localhost:8000/health
{"status":"ok","index":"c500","chunks":290,"llm_provider":"live","model":"deepseek-flash"}

$ curl -s -X POST localhost:8000/ask -H 'Content-Type: application/json' -d '{"question": "How long do I have to exchange my foreign driver's licence after moving to Ontario?"}'
{
    "question": "How long do I have to exchange my foreign driver's licence after moving to Ontario?",
    "route": "in_scope",
    "answer": "[62-word generated answer omitted from the repo; it paraphrases page text]",
    "refused": false,
    "refusal_reason": null,
    "citations": [
        {
            "chunk_id": "s17-c500-000",
            "url": "https://www.ontario.ca/page/exchange-out-province-drivers-licence",
            "title": "Exchange an out-of-province driver\u2019s licence",
            "heading": "Exchange an out-of-province driver\u2019s licence",
            "fetched_at": "2026-10-24"
        },
        {
            "chunk_id": "s19-c500-000",
            "url": "https://www.ontario.ca/document/official-mto-drivers-handbook/getting-your-drivers-licence",
            "title": "Getting Your Driver\u2019s Licence",
            "heading": "Getting Your Driver\u2019s Licence > Requirements for driving in Ontario",
            "fetched_at": "2026-10-24"
        }
    ],
    "disclaimer": "This is general information from official government pages, not legal, tax or immigration advice.",
    "served_models": [
        "deepseek-flash"
    ]
}

$ curl -s -X POST localhost:8000/ask -H 'Content-Type: application/json' -d '{"question": "Should I claim my spouse's income on my first Canadian tax return to get a bigger refund?"}'
{
    "question": "Should I claim my spouse's income on my first Canadian tax return to get a bigger refund?",
    "route": "needs_professional",
    "answer": "This needs advice about your own situation, which I can't give. Please contact a licensed professional (a lawyer or paralegal licensed by the Law Society of Ontario, a licensed immigration consultant, or a tax professional) or the government office directly.",
    "refused": true,
    "refusal_reason": "needs_professional",
    "citations": [],
    "disclaimer": "This is general information from official government pages, not legal, tax or immigration advice.",
    "served_models": [
        "deepseek-flash"
    ]
}

$ curl -s -X POST localhost:8000/ask -H 'Content-Type: application/json' -d '{"question": "What is the best restaurant in Toronto?"}'
{
    "question": "What is the best restaurant in Toronto?",
    "route": "out_of_scope",
    "answer": "This is outside what I cover. I only answer questions about SIN, OHIP, opening a bank account, a first Canadian tax return, and Ontario driver's licences or Photo Cards, using official government pages.",
    "refused": true,
    "refusal_reason": "out_of_scope",
    "citations": [],
    "disclaimer": "This is general information from official government pages, not legal, tax or immigration advice.",
    "served_models": [
        "deepseek-flash"
    ]
}
```
