"""JWT validation and the protected endpoints, with a locally generated RSA key and a fake JWKS.

No network and no database: the JWKS fetch and the history store are replaced in memory.
"""

from __future__ import annotations

import importlib
import json
import time
from datetime import UTC, datetime
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import src.api as api_module
from src.auth import AuthConfig, AuthError, JwksCache, TokenVerifier, get_auth_config, get_verifier
from src.history import HistoryRow

ISS = "http://keycloak.test/realms/newcomer"
AUD = "newcomer-api"
KID = "test-key-1"


def _keypair() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


SIGNING_KEY = _keypair()
OTHER_KEY = _keypair()  # same kid, wrong key: a forged signature


def _jwks(key: rsa.RSAPrivateKey, kid: str = KID) -> dict[str, Any]:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


class FakeJwks:
    def __init__(self, doc: dict[str, Any]) -> None:
        self.doc = doc
        self.calls = 0

    def __call__(self, url: str) -> dict[str, Any]:
        self.calls += 1
        return self.doc


def make_token(
    sub: str = "user-a",
    key: rsa.RSAPrivateKey = SIGNING_KEY,
    kid: str | None = KID,
    alg: str = "RS256",
    drop: tuple[str, ...] = (),
    **claims: Any,
) -> str:
    now = int(time.time())
    body: dict[str, Any] = {"iss": ISS, "aud": [AUD, "account"], "sub": sub, "iat": now,
                            "exp": now + 300, "preferred_username": sub}
    body.update(claims)
    for k in drop:
        body.pop(k, None)
    headers = {"kid": kid} if kid else {}
    return jwt.encode(body, key, algorithm=alg, headers=headers)


@pytest.fixture
def fake_jwks() -> FakeJwks:
    return FakeJwks(_jwks(SIGNING_KEY))


@pytest.fixture
def verifier(fake_jwks: FakeJwks) -> TokenVerifier:
    cfg = AuthConfig(disabled=False, issuer=ISS, audience=AUD, jwks_url="http://jwks.test")
    return TokenVerifier(cfg, JwksCache(cfg.jwks_url, fetch=fake_jwks))


# --- token validation -------------------------------------------------------------------

def test_valid_token_passes(verifier: TokenVerifier) -> None:
    claims = verifier.verify(make_token())
    assert claims["sub"] == "user-a"


@pytest.mark.parametrize(
    ("token_kwargs", "reason"),
    [
        ({"exp": int(time.time()) - 120}, "token expired"),
        ({"iss": "http://evil.test/realms/newcomer"}, "wrong issuer"),
        ({"aud": "account"}, "wrong audience"),
        ({"key": OTHER_KEY}, "bad signature"),
        ({"drop": ("exp",)}, "missing claim exp"),
        ({"drop": ("sub",)}, "missing claim sub"),
        ({"drop": ("aud",)}, "missing claim aud"),
        ({"kid": None}, "token has no key id"),
        ({"kid": "unknown-kid"}, "unknown signing key id"),
    ],
)
def test_bad_tokens_fail(verifier: TokenVerifier, token_kwargs: dict, reason: str) -> None:
    with pytest.raises(AuthError, match=reason):
        verifier.verify(make_token(**token_kwargs))


def test_hs256_token_is_rejected(verifier: TokenVerifier) -> None:
    """Algorithm confusion: an HMAC-signed token must never be accepted, whatever the secret."""
    now = int(time.time())
    forged = jwt.encode({"iss": ISS, "aud": AUD, "sub": "x", "iat": now, "exp": now + 60},
                        "s" * 32, algorithm="HS256", headers={"kid": KID})
    with pytest.raises(AuthError, match="unexpected signing algorithm"):
        verifier.verify(forged)


def test_unsigned_and_garbage_tokens_are_rejected(verifier: TokenVerifier) -> None:
    unsigned = jwt.encode({"sub": "x"}, None, algorithm="none")
    with pytest.raises(AuthError):
        verifier.verify(unsigned)
    with pytest.raises(AuthError, match="malformed"):
        verifier.verify("not-a-jwt")


def test_jwks_is_cached(verifier: TokenVerifier, fake_jwks: FakeJwks) -> None:
    for _ in range(5):
        verifier.verify(make_token())
    assert fake_jwks.calls == 1


def test_unknown_kid_refetch_is_rate_limited(fake_jwks: FakeJwks) -> None:
    now = [1000.0]
    cache = JwksCache("http://jwks.test", fetch=fake_jwks, min_refetch_s=30, clock=lambda: now[0])
    cache.get_key(KID)
    for _ in range(3):
        with pytest.raises(AuthError):
            cache.get_key("rotated")
    assert fake_jwks.calls == 1  # within 30 s of the last fetch: no refetch
    now[0] += 31
    fake_jwks.doc = _jwks(SIGNING_KEY, kid="rotated")
    assert cache.get_key("rotated") is not None  # key rotation picked up
    assert fake_jwks.calls == 2


def test_jwks_unreachable_fails_closed() -> None:
    def down(url: str) -> dict[str, Any]:
        raise ConnectionError("keycloak down")

    with pytest.raises(AuthError, match="could not load signing keys"):
        JwksCache("http://jwks.test", fetch=down).get_key(KID)


# --- endpoints ----------------------------------------------------------------------------

class MemoryStore:
    def __init__(self) -> None:
        self.rows: list[tuple[str, HistoryRow]] = []
        self.next_id = 1

    def add(self, user_sub: str, question: str, answer: dict[str, Any], route: str) -> int:
        row = HistoryRow(self.next_id, question, answer, route, datetime.now(UTC))
        self.rows.append((user_sub, row))
        self.next_id += 1
        return row.id

    def list(self, user_sub: str, limit: int, offset: int) -> tuple[list[HistoryRow], int]:
        mine = [r for s, r in self.rows if s == user_sub]
        mine.sort(key=lambda r: (r.created_at, r.id), reverse=True)
        return mine[offset:offset + limit], len(mine)

    def delete(self, user_sub: str, row_id: int) -> bool:
        for i, (s, r) in enumerate(self.rows):
            if r.id == row_id and s == user_sub:
                del self.rows[i]
                return True
        return False


class FakeAgent:
    def ask(self, question: str) -> dict[str, Any]:
        return {
            "route": "in_scope", "answer": "Apply online [s01-c500-000](https://example.ca/sin).",
            "refused": False, "refusal_reason": None,
            "citations": [{"chunk_id": "s01-c500-000", "url": "https://example.ca/sin",
                           "title": "SIN", "heading": "Apply", "fetched_at": "2026-10-24"}],
            "disclaimer": "General information only.", "served_models": ["cached"],
        }


@pytest.fixture
def store() -> MemoryStore:
    return MemoryStore()


@pytest.fixture
def client(verifier: TokenVerifier, store: MemoryStore, monkeypatch: pytest.MonkeyPatch):
    app = api_module.app
    app.dependency_overrides[get_auth_config] = lambda: verifier.config
    app.dependency_overrides[get_verifier] = lambda: verifier
    app.dependency_overrides[api_module.get_history_store] = lambda: store
    monkeypatch.setattr(api_module, "default_agent", FakeAgent)
    yield TestClient(app)
    app.dependency_overrides.clear()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


Q = {"question": "How do I get a SIN?"}


def test_ask_without_header_is_401(client: TestClient, store: MemoryStore) -> None:
    r = client.post("/ask", json=Q)
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Bearer")
    assert store.rows == []


@pytest.mark.parametrize("header", ["Basic dXNlcjpwYXNz", "Bearer", "Bearer   ", "token abc"])
def test_ask_with_malformed_header_is_401(client: TestClient, header: str) -> None:
    assert client.post("/ask", json=Q, headers={"Authorization": header}).status_code == 401


def test_ask_with_expired_token_is_401(client: TestClient) -> None:
    r = client.post("/ask", json=Q, headers=bearer(make_token(exp=int(time.time()) - 120)))
    assert r.status_code == 401
    assert "token expired" in r.headers["www-authenticate"]


def test_ask_with_wrong_audience_is_401(client: TestClient) -> None:
    r = client.post("/ask", json=Q, headers=bearer(make_token(aud="account")))
    assert r.status_code == 401


def test_ask_with_valid_token_saves_history(client: TestClient, store: MemoryStore) -> None:
    r = client.post("/ask", json=Q, headers=bearer(make_token("user-a")))
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "in_scope" and body["history_id"] == 1
    assert [(s, row.question) for s, row in store.rows] == [("user-a", Q["question"])]


def test_history_is_per_user_newest_first_and_paginated(client: TestClient) -> None:
    a, b = bearer(make_token("user-a")), bearer(make_token("user-b"))
    for q in ("first question", "second question", "third question"):
        assert client.post("/ask", json={"question": q}, headers=a).status_code == 200
    client.post("/ask", json={"question": "b's question"}, headers=b)

    page = client.get("/history?limit=2&offset=0", headers=a).json()
    assert page["total"] == 3 and page["limit"] == 2
    assert [i["question"] for i in page["items"]] == ["third question", "second question"]
    page2 = client.get("/history?limit=2&offset=2", headers=a).json()
    assert [i["question"] for i in page2["items"]] == ["first question"]
    assert page["items"][0]["answer"]["citations"][0]["url"] == "https://example.ca/sin"

    other = client.get("/history", headers=b).json()
    assert [i["question"] for i in other["items"]] == ["b's question"]


def test_history_requires_token(client: TestClient) -> None:
    assert client.get("/history").status_code == 401
    assert client.delete("/history/1").status_code == 401


def test_history_limit_is_bounded(client: TestClient) -> None:
    a = bearer(make_token("user-a"))
    assert client.get("/history?limit=0", headers=a).status_code == 422
    assert client.get("/history?limit=101", headers=a).status_code == 422


def test_cannot_delete_another_users_row(client: TestClient, store: MemoryStore) -> None:
    a, b = bearer(make_token("user-a")), bearer(make_token("user-b"))
    row_id = client.post("/ask", json=Q, headers=a).json()["history_id"]
    assert client.delete(f"/history/{row_id}", headers=b).status_code == 404
    assert len(store.rows) == 1  # still there
    assert client.delete(f"/history/{row_id}", headers=a).status_code == 204
    assert client.delete(f"/history/{row_id}", headers=a).status_code == 404
    assert store.rows == []


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_auth_disabled_flag_allows_anonymous(store: MemoryStore, monkeypatch) -> None:
    app = api_module.app
    cfg = AuthConfig(disabled=True, issuer="", audience=AUD, jwks_url="")
    app.dependency_overrides[get_auth_config] = lambda: cfg
    app.dependency_overrides[get_verifier] = lambda: None
    app.dependency_overrides[api_module.get_history_store] = lambda: store
    monkeypatch.setattr(api_module, "default_agent", FakeAgent)
    try:
        assert TestClient(app).post("/ask", json=Q).status_code == 200
        assert store.rows[0][0] == "local-dev"
    finally:
        app.dependency_overrides.clear()


def test_auth_is_on_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    assert AuthConfig.from_env().disabled is False


def test_auth_on_but_not_configured_fails_closed(store: MemoryStore) -> None:
    app = api_module.app
    cfg = AuthConfig(disabled=False, issuer="", audience=AUD, jwks_url="")
    app.dependency_overrides[get_auth_config] = lambda: cfg
    app.dependency_overrides[get_verifier] = lambda: None
    app.dependency_overrides[api_module.get_history_store] = lambda: store
    try:
        assert TestClient(app).post("/ask", json=Q).status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_token_never_logged(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    token = make_token(exp=int(time.time()) - 120)
    with caplog.at_level("DEBUG"):
        client.post("/ask", json=Q, headers=bearer(token))
    assert token not in caplog.text
    assert token.split(".")[2] not in caplog.text


# --- CORS -----------------------------------------------------------------------------------

def test_cors_allows_only_configured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_ORIGINS", "http://localhost:5173")
    mod = importlib.reload(api_module)
    try:
        c = TestClient(mod.app)
        pre = {"Access-Control-Request-Method": "POST",
               "Access-Control-Request-Headers": "authorization,content-type"}
        ok = c.options("/ask", headers={"Origin": "http://localhost:5173", **pre})
        assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
        bad = c.options("/ask", headers={"Origin": "http://evil.test", **pre})
        assert "access-control-allow-origin" not in bad.headers
    finally:
        monkeypatch.delenv("WEB_ORIGINS")
        importlib.reload(api_module)


def test_cors_wildcard_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WEB_ORIGINS", "*")
    with pytest.raises(RuntimeError):
        api_module.cors_origins()


def test_identity_provider_down_is_503_not_401(store: MemoryStore) -> None:
    def down(url: str) -> dict[str, Any]:
        raise ConnectionError("keycloak down")

    cfg = AuthConfig(disabled=False, issuer=ISS, audience=AUD, jwks_url="http://jwks.test")
    v = TokenVerifier(cfg, JwksCache(cfg.jwks_url, fetch=down))
    app = api_module.app
    app.dependency_overrides[get_auth_config] = lambda: cfg
    app.dependency_overrides[get_verifier] = lambda: v
    app.dependency_overrides[api_module.get_history_store] = lambda: store
    try:
        r = TestClient(app).post("/ask", json=Q, headers=bearer(make_token()))
        assert r.status_code == 503
        assert store.rows == []
    finally:
        app.dependency_overrides.clear()
