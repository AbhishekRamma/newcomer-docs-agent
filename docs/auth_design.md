# Auth design

About one page. It covers how signing in works, what the API checks and doesn't, and where the tokens live. Everything here is a local demo, **not a production setup**.

## The flow: Authorization Code + PKCE

```mermaid
sequenceDiagram
    participant B as Browser (React, oidc-client-ts)
    participant K as Keycloak (realm newcomer)
    participant A as FastAPI
    participant P as Postgres
    B->>B: make code_verifier (random), code_challenge = BASE64URL(SHA256(verifier)), state, nonce
    B->>K: redirect to /auth?client_id=web&code_challenge=…&code_challenge_method=S256&state=…
    K->>B: login form; user signs in; 302 back to http://localhost:5173/?code=…&state=…
    B->>K: POST /token (code + code_verifier), no client secret
    K->>K: SHA256(verifier) must equal the challenge from step 2
    K->>B: access token (RS256 JWT, 300 s), ID token, refresh token
    B->>A: POST /ask, Authorization: Bearer <access token>
    A->>K: GET /certs (JWKS), only on first use, every 5 min, or for an unknown kid
    A->>A: verify signature + claims, take sub
    A->>P: INSERT question_history (user_sub = sub, …)
```

`web` is a **public client**. A single-page app can't keep a secret, so it has none. PKCE stands in for one: whoever intercepts the `code` on the redirect can't exchange it without the verifier, which never leaves the tab. The client is pinned to `S256`, and the implicit and password grants are off. Redirects are allowed only to `http://localhost:5173/*`. The integration script checks that the wrong verifier gets `400 invalid_grant`.

## What the API validates (`src/auth.py`)

For every protected request (`POST /ask`, `GET /history`, `DELETE /history/{id}`, `GET /me`):

1. **Header.** The request needs an `Authorization: Bearer <token>` header. If it's missing or malformed, the API returns 401 with `WWW-Authenticate: Bearer`.
2. **Algorithm.** It must be `RS256`, and nothing else. `HS256` (the classic "use the public key as an HMAC secret" attack) and `alg: none` are rejected; unit tests cover both.
3. **Key.** The header's `kid` must match an RS256 signing key from the realm's JWKS. The keys are cached for 5 minutes. An unknown `kid` triggers one refetch, at most once every 30 s, which handles key rotation without letting junk `kid`s hammer Keycloak. If a refresh fails, the old keys are kept. If Keycloak can't be reached on the very first fetch, the API returns **503**, not 401, because "the sign-in service is down" and "your token is bad" are different problems.
4. **Signature.** PyJWT checks it against that key. Nothing is decoded and trusted before this; the header is the only part read unverified, to pick the key.
5. **Claims.** `exp`, `iat`, `iss`, `aud` and `sub` must all be present. `exp` must not have passed (10 s leeway). `iss` must equal `OIDC_ISSUER` exactly. `aud` must contain `OIDC_AUDIENCE` (`newcomer-api`). Keycloak puts that audience in only because of an audience mapper on the `web` client, so tokens minted for other clients in the realm are refused. If `nbf` is present, PyJWT checks it too.
6. **Identity.** `sub` becomes `user_sub`. Every history query filters on it, so another user's row looks exactly like a missing one (404).

Failures are logged with the reason only (for example "expired", "wrong audience"), never the token. One test captures the logs and asserts the token string isn't in them.

**What it does not do:**

- **No revocation check.** Validation is local (no token introspection), so a token stays valid until it expires, up to 300 s, even after the user signs out or an admin disables them. The short lifetime is the mitigation.
- **No roles or scopes.** Any signed-in realm user may ask questions; there is no `realm_access` or scope check.
- **No `azp` or `typ` check.** The audience is the gate. An ID token isn't accepted by accident, because its `aud` is `web`, not `newcomer-api`.
- **No sender-constrained tokens.** There is no DPoP or mTLS, so a stolen access token works from anywhere until it expires.
- **No rate limiting** on `/ask`.
- **Local eval and CI switch.** With `AUTH_DISABLED=1` (off by default, meant for local evaluation and CI only), every request runs as `local-dev`. With auth on but no issuer configured, the API answers 503 rather than silently letting requests through.

## Where the tokens live, and what that costs

- **Tokens are in memory only.** The access, ID and refresh tokens are held in `oidc-client-ts`'s `InMemoryWebStorage` user store. They are never written to `localStorage` or `sessionStorage`, so a script running on the page later, or another tab, can't read them from storage. A Vitest test stores a user and asserts that neither storage contains the token. The Playwright run found both storages empty after sign-in.
- **PKCE state is in `sessionStorage` briefly.** The code verifier, state and nonce have to survive the redirect to Keycloak and back, so they sit in `sessionStorage` and are removed after the callback. The library's default would have been `localStorage`. I caught that in the browser run and changed it.
- **The cost of in-memory tokens.** A page refresh, or a new tab, loses the tokens. Without anything else, every refresh would mean signing in again.
- **What I chose: silent sign-in.** On load, the app tries `signinSilent()`: a hidden iframe goes to Keycloak with `prompt=none`, and if the Keycloak session cookie is still valid, it comes back with a fresh code. `automaticSilentRenew` does the same shortly before the access token expires. In headless Chromium, a reload signed me straight back in, and after Sign out a reload showed the login screen. **Not verified:** renewal at the actual 300 s expiry, and Firefox or Safari. Browsers that block third-party cookies in iframes would break silent renew whenever Keycloak is on a different *site* from the app. Here both are `localhost`, so it is the same site. The fallback is the login screen, not an error.
- **The XSS caveat.** Memory storage limits theft from storage, but an XSS on the page could still call the API, or read the tokens from the JavaScript heap while it runs. So the other half of the defence is no `innerHTML` (model output is rendered as text, and only `http(s)` citation URLs become links), plus a strict CSP on the nginx-served app: `script-src 'self'`, `connect-src` limited to the API and Keycloak, `frame-src` limited to self and Keycloak, and `frame-ancestors 'self'`.
- **Why not a backend-for-frontend with an httpOnly session cookie?** That keeps tokens out of JavaScript entirely, and it is what I'd use in production. The brief fixed browser-side `oidc-client-ts` with in-memory storage, and a BFF would also need CSRF protection and a session store.

## CORS

The API allows only the origins in `WEB_ORIGINS` (comma-separated; in Compose, `http://localhost:5173`). It allows only GET, POST and DELETE, and only the `Authorization` and `Content-Type` headers, without credentials (the token travels in a header, not a cookie). The API refuses to start if `WEB_ORIGINS` contains `*`.
