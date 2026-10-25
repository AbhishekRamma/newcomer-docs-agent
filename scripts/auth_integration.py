"""End-to-end auth check against the running compose stack (Keycloak + API).

Signs in as the demo users with a real Authorization Code + PKCE flow (the same requests a
browser makes: open the login page, post the form, take the code from the redirect, exchange
it with the code_verifier), then checks /ask, /history and DELETE /history/{id}.

Prints a JSON summary of status codes and ids only. It never prints or saves a token.

Usage: uv run python scripts/auth_integration.py [--question "..."]
Demo credentials (local use only) are the ones documented in keycloak/README.md.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import re
import secrets
import sys
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

API = "http://localhost:8000"
ISSUER = "http://localhost:8080/realms/newcomer"
WEB = "http://localhost:5173"
REDIRECT = f"{WEB}/"
DEMO_USERS = {"demo": "demo-only-not-a-secret", "demo2": "demo2-only-not-a-secret"}


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def authorize(username: str, password: str) -> tuple[str, str]:
    """Run the browser half of the flow. Returns (code, code_verifier)."""
    verifier = b64url(secrets.token_bytes(48))
    challenge = b64url(hashlib.sha256(verifier.encode()).digest())
    state = secrets.token_urlsafe(16)
    q = urlencode({
        "client_id": "web", "response_type": "code", "scope": "openid profile",
        "redirect_uri": REDIRECT, "state": state, "nonce": secrets.token_urlsafe(16),
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    with httpx.Client(follow_redirects=False, timeout=15) as c:
        page = c.get(f"{ISSUER}/protocol/openid-connect/auth?{q}")
        page.raise_for_status()
        m = re.search(r'<form[^>]+id="kc-form-login"[^>]+action="([^"]+)"', page.text)
        if not m:
            raise RuntimeError("login form not found")
        # Keycloak marks its cookies Secure even on http://localhost (browsers treat localhost
        # as a secure context and send them); httpx doesn't, so pass them on explicitly.
        cookie = "; ".join(f"{k.name}={k.value}" for k in c.cookies.jar)
        r = c.post(html.unescape(m.group(1)), headers={"Cookie": cookie},
                   data={"username": username, "password": password, "credentialId": ""})
    if r.status_code != 302:
        raise RuntimeError(f"login did not redirect (HTTP {r.status_code})")
    loc = urlparse(r.headers["location"])
    params = parse_qs(loc.query)
    assert f"{loc.scheme}://{loc.netloc}{loc.path}" == REDIRECT
    assert params["state"] == [state], "state mismatch"
    return params["code"][0], verifier


def exchange(code: str, verifier: str) -> httpx.Response:
    return httpx.post(f"{ISSUER}/protocol/openid-connect/token", timeout=15, data={
        "grant_type": "authorization_code", "client_id": "web", "code": code,
        "redirect_uri": REDIRECT, "code_verifier": verifier,
    })


def sign_in(username: str) -> str:
    code, verifier = authorize(username, DEMO_USERS[username])
    r = exchange(code, verifier)
    r.raise_for_status()
    return r.json()["access_token"]


def claims_summary(token: str) -> dict:
    """Unverified peek at a few non-secret claims for the evidence file (the API verifies)."""
    payload = token.split(".")[1]
    data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    aud = data.get("aud")
    return {"iss": data.get("iss"), "aud": aud if isinstance(aud, list) else [aud],
            "azp": data.get("azp"), "preferred_username": data.get("preferred_username"),
            "lifetime_s": data.get("exp", 0) - data.get("iat", 0)}


def main() -> int:
    ap = argparse.ArgumentParser()
    # A dev-set question, so the cached LLM responses cover it (no live call).
    ap.add_argument(
        "--question", default="What identification do I need to open a bank account in Canada?"
    )
    ap.add_argument("--keep", action="store_true", help="leave the new history row in place")
    args = ap.parse_args()
    out: dict = {}
    ok = True

    def check(name: str, cond: bool, **detail: object) -> None:
        nonlocal ok
        ok &= cond
        out[name] = {"pass": cond, **detail}

    api = httpx.Client(base_url=API, timeout=120)
    h = api.get("/health")
    check("health_public", h.status_code == 200, status=h.status_code, body=h.json())

    r = api.post("/ask", json={"question": args.question})
    check("ask_without_token_401", r.status_code == 401, status=r.status_code,
          www_authenticate=r.headers.get("www-authenticate"))
    r = api.post("/ask", json={"question": args.question},
                 headers={"Authorization": "Bearer not.a.jwt"})
    check("ask_with_garbage_token_401", r.status_code == 401, status=r.status_code)

    # PKCE is enforced: a valid code with the wrong verifier is refused by Keycloak.
    code, _ = authorize("demo", DEMO_USERS["demo"])
    bad = exchange(code, b64url(secrets.token_bytes(48)))
    check("pkce_wrong_verifier_refused", bad.status_code == 400,
          status=bad.status_code, error=bad.json().get("error"))

    a = sign_in("demo")
    out["demo_token_claims"] = claims_summary(a)
    ha = {"Authorization": f"Bearer {a}"}

    # A token signed correctly but altered afterwards must fail the signature check.
    head, body, sig = a.split(".")
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    claims["sub"] = "someone-else"
    tampered = ".".join([head, b64url(json.dumps(claims).encode()), sig])
    r = api.post("/ask", json={"question": args.question},
                 headers={"Authorization": f"Bearer {tampered}"})
    check("tampered_token_401", r.status_code == 401, status=r.status_code)

    r = api.post("/ask", json={"question": args.question}, headers=ha)
    body = r.json() if r.status_code == 200 else {}
    row_id = body.get("history_id")
    check("ask_with_token_200", r.status_code == 200 and isinstance(row_id, int),
          status=r.status_code, route=body.get("route"), refused=body.get("refused"),
          citations=len(body.get("citations", [])), history_id=row_id)

    r = api.get("/history", params={"limit": 5}, headers=ha)
    page = r.json()
    ids = [i["id"] for i in page.get("items", [])]
    check("history_shows_entry", r.status_code == 200 and bool(ids) and ids[0] == row_id,
          status=r.status_code, total=page.get("total"), newest_id=ids[0] if ids else None)

    b = sign_in("demo2")
    hb = {"Authorization": f"Bearer {b}"}
    r = api.get("/history", params={"limit": 100}, headers=hb)
    other_ids = [i["id"] for i in r.json().get("items", [])]
    check("second_user_cannot_see", r.status_code == 200 and row_id not in other_ids,
          status=r.status_code, demo2_total=r.json().get("total"),
          demo_row_in_demo2_list=row_id in other_ids)
    r = api.delete(f"/history/{row_id}", headers=hb)
    check("second_user_cannot_delete_404", r.status_code == 404, status=r.status_code)
    r = api.get("/history", params={"limit": 5}, headers=ha)
    check("entry_still_there_for_owner", row_id in [i["id"] for i in r.json()["items"]])

    pre = {"Access-Control-Request-Method": "POST",
           "Access-Control-Request-Headers": "authorization,content-type"}
    good = api.options("/ask", headers={"Origin": WEB, **pre})
    evil = api.options("/ask", headers={"Origin": "http://evil.example", **pre})
    check("cors_web_origin_only",
          good.headers.get("access-control-allow-origin") == WEB
          and "access-control-allow-origin" not in evil.headers,
          allowed=good.headers.get("access-control-allow-origin"),
          evil_status=evil.status_code,
          evil_allow_origin=evil.headers.get("access-control-allow-origin"))

    if not args.keep:
        r = api.delete(f"/history/{row_id}", headers=ha)
        check("owner_can_delete_204", r.status_code == 204, status=r.status_code)

    out["all_pass"] = ok
    print(json.dumps(out, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
