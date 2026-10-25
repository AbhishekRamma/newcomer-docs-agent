# Auth evidence (2026-10-24, America/Toronto)

What I ran against the real stack on my build box, and what came back. No tokens, cookies or
client secrets appear here (the `web` client is public and has none); the demo passwords are the
labelled local-only ones in [`keycloak/realm-newcomer.json`](../keycloak/realm-newcomer.json).

## Stack

Docker 26.1.5, Compose 2.26.1, with `sudo`. Plain `docker compose up` cannot network on this
host (see [`docker_evidence.md`](docker_evidence.md)), so I used the host-network override:

```bash
LLM_PROVIDER=cached sudo -E docker compose -f docker-compose.yml -f docker-compose.hostnet.yml up -d --build
```

```
NAME                             IMAGE                            STATUS
newcomer-docs-agent-app-1        newcomer-docs-agent-app          Up 6 minutes
newcomer-docs-agent-db-1         pgvector/pgvector:pg16           Up 6 minutes (healthy)
newcomer-docs-agent-keycloak-1   quay.io/keycloak/keycloak:26.4   Up 6 minutes
newcomer-docs-agent-web-1        newcomer-docs-agent-web          Up 2 minutes
```

App log on start: migrations applied `['001_question_history']`, `embedding cache: 290 hits, 0 computed`,
Uvicorn on :8000. `LLM_PROVIDER=cached` means every answer came from the LLM cache: the
spend ledger (`data/local/spend.json`) was byte-identical before and after (1,140 calls, $0.2968914).

Table created by the migration (`\d question_history` in the db container):

```
 id          | bigint                   | not null | nextval('question_history_id_seq'::regclass)
 user_sub    | text                     | not null |
 question    | text                     | not null |
 answer_json | jsonb                    | not null |
 route       | text                     | not null |
 created_at  | timestamp with time zone | not null | now()
Indexes:
    "question_history_pkey" PRIMARY KEY, btree (id)
    "question_history_user_newest" btree (user_sub, created_at DESC, id DESC)
```

Keycloak discovery (`/realms/newcomer/.well-known/openid-configuration`): issuer
`http://localhost:8080/realms/newcomer`, `code_challenge_methods_supported: ["plain", "S256"]`
(the `web` client itself is pinned to S256). The JWKS has one RS256 signing key and one RSA-OAEP
encryption key; the API only uses keys whose `kid` matches the token header.

## 1. curl without a token

```
$ curl -i -X POST localhost:8000/ask -H 'Content-Type: application/json' \
    -d '{"question":"What identification do I need to open a bank account in Canada?"}'
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
content-type: application/json

{"detail":"Not signed in, or the session has expired."}

$ curl -i localhost:8000/history
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer

{"detail":"Not signed in, or the session has expired."}
```

## 2. Scripted sign-in and isolation check

[`scripts/auth_integration.py`](../scripts/auth_integration.py) signs in the way the browser
does: Authorization Code + PKCE (S256) against Keycloak's real login form with httpx, then the
code-for-token exchange with the verifier. It never prints a token; it prints only a few
non-secret claims. Run: `.venv/bin/python scripts/auth_integration.py`. Full output from
22:09 EDT:

```json
{
  "health_public": {
    "pass": true,
    "status": 200,
    "body": {
      "status": "ok",
      "index": "c500",
      "chunks": 290,
      "llm_provider": "cached",
      "model": "deepseek-flash"
    }
  },
  "ask_without_token_401": {
    "pass": true,
    "status": 401,
    "www_authenticate": "Bearer"
  },
  "ask_with_garbage_token_401": {
    "pass": true,
    "status": 401
  },
  "pkce_wrong_verifier_refused": {
    "pass": true,
    "status": 400,
    "error": "invalid_grant"
  },
  "demo_token_claims": {
    "iss": "http://localhost:8080/realms/newcomer",
    "aud": [
      "newcomer-api"
    ],
    "azp": "web",
    "preferred_username": "demo",
    "lifetime_s": 300
  },
  "tampered_token_401": {
    "pass": true,
    "status": 401
  },
  "ask_with_token_200": {
    "pass": true,
    "status": 200,
    "route": "in_scope",
    "refused": false,
    "citations": 3,
    "history_id": 15
  },
  "history_shows_entry": {
    "pass": true,
    "status": 200,
    "total": 1,
    "newest_id": 15
  },
  "second_user_cannot_see": {
    "pass": true,
    "status": 200,
    "demo2_total": 0,
    "demo_row_in_demo2_list": false
  },
  "second_user_cannot_delete_404": {
    "pass": true,
    "status": 404
  },
  "entry_still_there_for_owner": {
    "pass": true
  },
  "cors_web_origin_only": {
    "pass": true,
    "allowed": "http://localhost:5173",
    "evil_status": 400,
    "evil_allow_origin": null
  },
  "owner_can_delete_204": {
    "pass": true,
    "status": 204
  },
  "all_pass": true
}
```

What this shows:

| check | result |
|---|---|
| `/health` public | 200 |
| `/ask` without a token | **401**, `WWW-Authenticate: Bearer` |
| `/ask` with a garbage token / a token with one signature byte changed | 401 / 401 |
| token exchange with the wrong PKCE verifier | 400 `invalid_grant` from Keycloak |
| demo's access token | `iss` = the realm, `aud` = `newcomer-api`, `azp` = `web`, 300 s lifetime |
| `/ask` with demo's token | **200**, in-scope answer with 3 citations, saved as history row 15 |
| demo's `/history` | shows that row (newest first) |
| demo2's `/history` | **0 rows**; demo's row not in it |
| demo2 `DELETE /history/<demo's id>` | **404**, and the row is still there for demo |
| CORS preflight from `http://localhost:5173` / from `https://evil.example` | allowed / 400 with no `Access-Control-Allow-Origin` |
| demo deletes own row | 204 |

One wrinkle on the way: the first run's login POST came back 400, and Keycloak logged
`error="cookie_not_found"`. Keycloak 26 marks its login-session cookies `Secure; SameSite=None`
even on `http://localhost`. Browsers treat localhost as a secure context and send them; httpx
does not send `Secure` cookies over plain http. The script now forwards them explicitly. This was
a test-client problem, not an app problem: the browser run below signed in without it.

The first scripted question (about SIN applications) was not in the LLM cache, so the agent
returned its offline refusal (`llm_cache_miss`) with a 200. I switched the script to a dev-set
question, which the cache covers, so the run made no live call.

## 3. Real browser (headless Chromium, Playwright)

[`scripts/ui_check.py`](../scripts/ui_check.py) drives the built `web` container on
<http://localhost:5173>: click Sign in, fill Keycloak's form as `demo`, come back, ask one
answerable and one refusal question (both cached), open History, reload, sign out, reload.
Summary it printed (22:15 EDT):

```json
{
  "keycloak_login_url_has_pkce": true,
  "header_user": "Signed in as\ndemo",
  "url_after_callback": "http://localhost:5173/",
  "localStorage_keys": [],
  "sessionStorage_keys": [],
  "access_token_in_web_storage": false,
  "cite_links": 6,
  "refusal_tags": [
    "NEEDS A PROFESSIONAL \u00b7 NEEDS_PROFESSIONAL"
  ],
  "history_rows": 2,
  "after_refresh": "signed in again silently",
  "console_after_refresh": [],
  "after_sign_out": "login screen",
  "after_sign_out_refresh": "login screen",
  "console_errors": []
}
```

- The redirect to Keycloak carried `code_challenge_method=S256`, and after the callback the URL was
  clean (`code` and `state` removed).
- After sign-in, `localStorage` and `sessionStorage` were both empty, so no token was in web
  storage. The tokens were only in memory.
- Reloading signed me in again silently (a hidden iframe with `prompt=none` reuses the Keycloak
  session cookie). After Sign out, a reload showed the login screen.
- No console errors.

Two bugs this run caught, both fixed before the run above:

1. **Silent sign-in was blocked by my own CSP.** The page's `frame-src` allowed Keycloak but not
   `'self'`, and the silent iframe ends on `/silent-renew.html` on the web origin, so Chromium
   refused to load it and every reload showed the login screen. I added `'self'` to `frame-src`
   in `web/nginx.conf.template`.
2. **PKCE state went to `localStorage`.** oidc-client-ts defaults its *state* store (the
   short-lived code verifier, state and nonce) to `localStorage`. I had moved only the user store
   into memory. The state store is now `sessionStorage`, and a Vitest test checks it. No access
   token was ever in `localStorage`, but the verifier should not outlive the tab.

Screenshots: [`web_login.png`](web_login.png), [`web_chat.png`](web_chat.png),
[`web_history.png`](web_history.png).

## Not verified

- Plain `docker compose up` (bridge networking) with the new `keycloak` and `web` services. On this
  host bridge networking does not work at all, so I could not test it here.
- Firefox and Safari. Only headless Chromium was tested, and Safari's third-party-cookie rules are
  known to break silent iframe renew. See [`auth_design.md`](auth_design.md).
- Automatic silent renew at the 300 s expiry. I did not leave a session open past five minutes in
  the browser run, so this is configured but **not verified**.
- Behaviour under real TLS or a non-localhost hostname.
