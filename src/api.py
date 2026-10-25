"""FastAPI service: POST /ask, GET /history, DELETE /history/{id} (all need a bearer token)
and GET /health (public). The React front end in `web/` is served separately."""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.auth import CurrentUser, current_user
from src.config import get_settings
from src.db import connect
from src.graph import default_agent
from src.history import HistoryStore, PostgresHistoryStore
from src.llm import BudgetExceeded

app = FastAPI(title="newcomer-docs-agent", version="0.2.0")


def cors_origins() -> list[str]:
    """Exact origins from WEB_ORIGINS (comma-separated). A wildcard is refused."""
    origins = [o.strip().rstrip("/") for o in os.getenv("WEB_ORIGINS", "").split(",")]
    origins = [o for o in origins if o]
    if "*" in origins:
        raise RuntimeError("WEB_ORIGINS must list exact origins, not '*'")
    return origins


if _origins := cors_origins():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        allow_credentials=False,  # the token travels in a header, not a cookie
        max_age=600,
    )


@lru_cache(maxsize=1)
def get_history_store() -> HistoryStore:
    return PostgresHistoryStore(get_settings().database_url)


User = Annotated[CurrentUser, Depends(current_user)]
Store = Annotated[HistoryStore, Depends(get_history_store)]


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
    history_id: int | None = None


class HistoryItem(BaseModel):
    id: int
    question: str
    route: str
    created_at: datetime
    answer: AskResponse


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    total: int
    limit: int
    offset: int


@app.get("/")
def root() -> dict:
    return {"service": "newcomer-docs-agent", "docs": "/docs", "health": "/health"}


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
def ask(
    req: AskRequest,
    user: User,
    store: Store,
) -> AskResponse:
    try:
        out = default_agent().ask(req.question)
    except BudgetExceeded as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    resp = AskResponse(question=req.question, **{k: out[k] for k in AskResponse.model_fields
                                                  if k not in ("question", "history_id")})
    resp.history_id = store.add(user.sub, req.question,
                                resp.model_dump(exclude={"history_id"}), resp.route)
    return resp


@app.get("/history", response_model=HistoryPage)
def history(
    user: User,
    store: Store,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HistoryPage:
    rows, total = store.list(user.sub, limit, offset)
    items = [
        HistoryItem(id=r.id, question=r.question, route=r.route, created_at=r.created_at,
                    answer=AskResponse.model_validate({**r.answer, "history_id": r.id}))
        for r in rows
    ]
    return HistoryPage(items=items, total=total, limit=limit, offset=offset)


@app.delete("/history/{row_id}", status_code=204)
def delete_history(
    row_id: int,
    user: User,
    store: Store,
) -> Response:
    # Someone else's row and a missing row look the same: 404, so ids can't be probed.
    if not store.delete(user.sub, row_id):
        raise HTTPException(status_code=404, detail="No such history entry.")
    return Response(status_code=204)


@app.get("/me")
def me(user: User) -> dict:
    return {"sub": user.sub, "username": user.username}
