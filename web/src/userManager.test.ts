import { User } from "oidc-client-ts";
import { describe, expect, it } from "vitest";
import { createUserManager } from "./userManager";

describe("createUserManager", () => {
  it("uses Authorization Code + PKCE against the configured realm", () => {
    const um = createUserManager("http://localhost:5173");
    expect(um.settings.response_type).toBe("code");
    expect(um.settings.client_id).toBe("web");
    expect(um.settings.redirect_uri).toBe("http://localhost:5173/");
    expect(um.settings.silent_redirect_uri).toBe("http://localhost:5173/silent-renew.html");
    expect(um.settings.disablePKCE).toBe(false);
  });

  it("keeps the PKCE state in sessionStorage, never localStorage", async () => {
    localStorage.clear();
    sessionStorage.clear();
    const um = createUserManager("http://localhost:5173");
    await um.settings.stateStore.set("probe", "pkce-state");
    expect(sessionStorage.getItem("oidc.probe")).toBe("pkce-state");
    expect(localStorage.length).toBe(0);
  });

  it("keeps the signed-in user (and its tokens) in memory, not in web storage", async () => {
    localStorage.clear();
    sessionStorage.clear();
    const um = createUserManager("http://localhost:5173");
    const user = new User({
      access_token: "fake-access-token-for-test", token_type: "Bearer", id_token: "fake-id",
      refresh_token: "fake-refresh", profile: { sub: "u1", iss: "x", aud: "web", exp: 0, iat: 0 },
      expires_at: Math.floor(Date.now() / 1000) + 300,
    });
    await um.storeUser(user);
    expect((await um.getUser())?.access_token).toBe("fake-access-token-for-test");
    const everything = [localStorage, sessionStorage]
      .flatMap((s) => Object.keys(s).map((k) => `${k}=${s.getItem(k) ?? ""}`)).join("\n");
    expect(everything).not.toContain("fake-access-token-for-test");
    expect(everything).not.toContain("fake-refresh");
  });
});
