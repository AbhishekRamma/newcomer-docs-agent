"""Bearer-token authentication for the API: validates Keycloak access tokens (RS256 JWTs).

What is checked, for every request to a protected endpoint:
- an `Authorization: Bearer <token>` header is present;
- the token header says `alg: RS256` and names a `kid` found in the realm's JWKS;
- the signature verifies with that key;
- `iss` equals the configured issuer, `aud` contains the configured audience;
- `exp`, `iat`, `iss`, `aud` and `sub` are present, and `exp` has not passed (small leeway).

Tokens are never logged. `AUTH_DISABLED=1` skips all of this and treats every caller as one
local user; it exists for local evaluation and CI only and is off by default.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request

log = logging.getLogger("auth")

LOCAL_USER_SUB = "local-dev"


def _flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AuthConfig:
    disabled: bool
    issuer: str
    audience: str
    jwks_url: str
    leeway_s: int = 10

    @classmethod
    def from_env(cls) -> AuthConfig:
        issuer = os.getenv("OIDC_ISSUER", "").rstrip("/")
        # The API may reach Keycloak by a different host name than the browser does (inside
        # Compose), so the JWKS URL can be set separately; the issuer must match the token.
        jwks = os.getenv("OIDC_JWKS_URL", "") or (
            f"{issuer}/protocol/openid-connect/certs" if issuer else ""
        )
        return cls(
            disabled=_flag("AUTH_DISABLED"),
            issuer=issuer,
            audience=os.getenv("OIDC_AUDIENCE", "newcomer-api"),
            jwks_url=jwks,
        )


class AuthError(Exception):
    """A token was missing or failed validation. The message is safe to log (no token)."""


class KeysUnavailable(AuthError):
    """The identity provider's JWKS could not be loaded: a server problem, not the caller's."""


def _http_fetch(url: str) -> dict[str, Any]:
    r = httpx.get(url, timeout=5.0)
    r.raise_for_status()
    return r.json()


class JwksCache:
    """Signing keys from the realm's JWKS endpoint, cached in memory.

    Keys are kept for `ttl_s`. An unknown `kid` triggers one refetch (Keycloak key rotation),
    but at most once per `min_refetch_s`, so tokens with made-up key ids can't make the API
    hammer Keycloak.
    """

    def __init__(
        self,
        url: str,
        fetch: Callable[[str], dict[str, Any]] = _http_fetch,
        ttl_s: float = 300.0,
        min_refetch_s: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.url = url
        self._fetch = fetch
        self._ttl = ttl_s
        self._min_refetch = min_refetch_s
        self._clock = clock
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None
        self._last_attempt: float | None = None
        self._lock = threading.Lock()
        self.fetch_count = 0

    def _refresh(self) -> None:
        doc = self._fetch(self.url)
        keys: dict[str, Any] = {}
        for jwk in doc.get("keys", []):
            if jwk.get("kty") != "RSA" or jwk.get("use", "sig") != "sig":
                continue
            if jwk.get("alg", "RS256") != "RS256" or "kid" not in jwk:
                continue
            keys[jwk["kid"]] = jwt.PyJWK.from_json(json.dumps(jwk)).key
        self._keys = keys
        self._fetched_at = self._clock()
        self.fetch_count += 1

    def get_key(self, kid: str) -> Any:
        with self._lock:
            now = self._clock()
            stale = self._fetched_at is None or now - self._fetched_at > self._ttl
            may_try = self._last_attempt is None or now - self._last_attempt >= self._min_refetch
            if (stale or kid not in self._keys) and may_try:
                self._last_attempt = now
                try:
                    self._refresh()
                except Exception as e:  # network or JSON error: keep old keys, or fail closed
                    if not self._keys:
                        why = type(e).__name__
                        raise KeysUnavailable(f"could not load signing keys: {why}") from e
                    log.warning("JWKS refresh failed (%s); using cached keys", type(e).__name__)
            key = self._keys.get(kid)
        if key is None:
            raise AuthError("unknown signing key id")
        return key


class TokenVerifier:
    def __init__(self, config: AuthConfig, jwks: JwksCache) -> None:
        self.config = config
        self.jwks = jwks

    def verify(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)  # only to choose the key; nothing trusted
        except jwt.InvalidTokenError as e:
            raise AuthError("malformed token") from e
        if header.get("alg") != "RS256":
            raise AuthError("unexpected signing algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise AuthError("token has no key id")
        key = self.jwks.get_key(kid)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.config.audience,
                issuer=self.config.issuer,
                leeway=self.config.leeway_s,
                options={
                    "require": ["exp", "iat", "iss", "aud", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except jwt.ExpiredSignatureError as e:
            raise AuthError("token expired") from e
        except jwt.InvalidAudienceError as e:
            raise AuthError("wrong audience") from e
        except jwt.InvalidIssuerError as e:
            raise AuthError("wrong issuer") from e
        except jwt.InvalidSignatureError as e:
            raise AuthError("bad signature") from e
        except jwt.MissingRequiredClaimError as e:
            raise AuthError(f"missing claim {e.claim}") from e
        except jwt.InvalidTokenError as e:
            raise AuthError(f"invalid token ({type(e).__name__})") from e
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise AuthError("empty subject")
        return claims


@dataclass(frozen=True)
class CurrentUser:
    sub: str
    username: str


@lru_cache(maxsize=1)
def get_auth_config() -> AuthConfig:
    return AuthConfig.from_env()


@lru_cache(maxsize=1)
def get_verifier() -> TokenVerifier | None:
    cfg = get_auth_config()
    if cfg.disabled or not cfg.issuer:
        return None
    return TokenVerifier(cfg, JwksCache(cfg.jwks_url))


def _unauthorized(reason: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Not signed in, or the session has expired.",
        headers={"WWW-Authenticate": f'Bearer error="invalid_token", error_description="{reason}"'},
    )


def current_user(
    request: Request,
    config: Annotated[AuthConfig, Depends(get_auth_config)],
    verifier: Annotated[TokenVerifier | None, Depends(get_verifier)],
) -> CurrentUser:
    """FastAPI dependency: the authenticated caller, or 401."""
    if config.disabled:
        return CurrentUser(sub=LOCAL_USER_SUB, username="local (auth disabled)")
    if verifier is None:  # fail closed when auth is on but not configured
        raise HTTPException(status_code=503, detail="Authentication is not configured.")
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Not signed in, or the session has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        claims = verifier.verify(token.strip())
    except KeysUnavailable as e:
        log.warning("cannot verify tokens: %s", e)
        raise HTTPException(status_code=503, detail="Sign-in service unavailable.") from None
    except AuthError as e:
        log.info("rejected token: %s", e)  # reason only, never the token
        raise _unauthorized(str(e)) from None
    username = claims.get("preferred_username")
    return CurrentUser(sub=claims["sub"], username=username if isinstance(username, str) else "")
