// oidc-client-ts set up for Authorization Code + PKCE with tokens kept in memory only.
// The user (access, ID and refresh tokens) lives in an InMemoryWebStorage, so nothing
// token-bearing touches localStorage or sessionStorage. The short-lived PKCE state
// (code_verifier, state, nonce) stays in sessionStorage only across the login redirect,
// because the page is reloaded in between; oidc-client-ts removes it after the callback.
import { InMemoryWebStorage, UserManager, WebStorageStateStore } from "oidc-client-ts";
import { config } from "./config";

export function createUserManager(origin: string = window.location.origin): UserManager {
  return new UserManager({
    authority: config.oidcAuthority,
    client_id: config.oidcClientId,
    redirect_uri: `${origin}/`,
    post_logout_redirect_uri: `${origin}/`,
    silent_redirect_uri: `${origin}/silent-renew.html`,
    response_type: "code",
    scope: "openid profile",
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
    // oidc-client-ts defaults the state store to localStorage; keep it per-tab and short-lived.
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: true,
    monitorSession: false,
  });
}
