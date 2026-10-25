# Keycloak realm (local demo only)

`realm-newcomer.json` is imported by `docker compose` when Keycloak starts (`start-dev --import-realm`).

**DEMO CREDENTIALS, LOCAL USE ONLY.** The two users below exist only in this throwaway local
realm. They are not secrets and must never be reused anywhere real.

| user  | password                  | used for                          |
|-------|---------------------------|-----------------------------------|
| demo  | `demo-only-not-a-secret`  | signing in to the web app         |
| demo2 | `demo2-only-not-a-secret` | checking users can't see each other's history |

The Keycloak admin console (http://localhost:8080/admin) uses the bootstrap admin set in
`docker-compose.yml` (`admin` / `admin-demo-only`), also a demo value for local use only.

Client `web` is public (no client secret), allows only the Authorization Code flow with PKCE
S256, redirects only to `http://localhost:5173/*`, and has an audience mapper that adds
`newcomer-api` to access tokens; the API rejects tokens without that audience.
