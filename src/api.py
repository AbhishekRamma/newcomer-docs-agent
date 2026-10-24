"""FastAPI service: POST /ask and GET /health."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.config import get_settings
from src.db import connect
from src.graph import default_agent
from src.llm import BudgetExceeded

app = FastAPI(title="newcomer-docs-agent", version="0.1.0")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class Citation(BaseModel):
    chunk_id: str
    url: str
    title: str
    heading: str
    fetched_at: str


class AskResponse(BaseModel):
    question: str
    route: str
    answer: str
    refused: bool
    refusal_reason: str | None
    citations: list[Citation]
    disclaimer: str
    served_models: list[str]


@app.get("/health")
def health() -> dict:
    s = get_settings()
    try:
        conn = connect(s.database_url)
        n = conn.execute("SELECT count(*) FROM chunks WHERE index_name = %s",
                         (s.index,)).fetchone()[0]
        conn.close()
    except Exception as e:  # report, don't crash: health must answer even when the DB is down
        return {"status": "degraded", "db": f"error: {type(e).__name__}"}
    return {"status": "ok" if n else "empty_index", "index": s.index, "chunks": n,
            "llm_provider": s.llm_provider, "model": s.model}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    try:
        out = default_agent().ask(req.question)
    except BudgetExceeded as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return AskResponse(question=req.question, **{k: out[k] for k in AskResponse.model_fields
                                                  if k != "question"})
