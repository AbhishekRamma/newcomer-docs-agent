// React context around oidc-client-ts. Tokens stay in memory (see userManager.ts).
import type { User, UserManager } from "oidc-client-ts";
import { AuthContext, type AuthContextValue, type AuthStatus } from "./authContext";
import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

// One start-up per UserManager, so React StrictMode's double effect can't replay the
// one-time authorisation code.
const startups = new WeakMap<UserManager, Promise<User | null>>();

function hasAuthResponse(url: URL): boolean {
  return url.searchParams.has("state") &&
    (url.searchParams.has("code") || url.searchParams.has("error"));
}

async function startUp(um: UserManager): Promise<User | null> {
  const url = new URL(window.location.href);
  if (hasAuthResponse(url)) {
    try {
      return await um.signinRedirectCallback();
    } finally {
      // Drop ?code=&state= from the address bar and history.
      window.history.replaceState(window.history.state, "", url.pathname);
    }
  }
  try {
    // prompt=none in a hidden iframe: works when a Keycloak session cookie exists,
    // which is what brings the user back after a page refresh.
    return await um.signinSilent();
  } catch {
    return null;
  }
}

function displayName(user: User): string {
  const p = user.profile;
  return p.preferred_username ?? p.name ?? p.sub;
}

export function AuthProvider({ userManager, children }: {
  userManager: UserManager;
  children: ReactNode;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const userRef = useRef<User | null>(null);

  const apply = useCallback((u: User | null) => {
    userRef.current = u && !u.expired ? u : null;
    setUser(userRef.current);
    setStatus(userRef.current ? "signedIn" : "signedOut");
  }, []);

  useEffect(() => {
    let live = true;
    let p = startups.get(userManager);
    if (!p) {
      p = startUp(userManager);
      startups.set(userManager, p);
    }
    p.then((u) => { if (live) apply(u); })
      .catch(() => {
        if (!live) return;
        setError("Sign-in did not complete. Please try again.");
        apply(null);
      });

    const ev = userManager.events;
    const onLoaded = (u: User) => { apply(u); };
    const onGone = () => { apply(null); };
    ev.addUserLoaded(onLoaded);
    ev.addUserUnloaded(onGone);
    ev.addAccessTokenExpired(onGone);
    return () => {
      live = false;
      ev.removeUserLoaded(onLoaded);
      ev.removeUserUnloaded(onGone);
      ev.removeAccessTokenExpired(onGone);
    };
  }, [userManager, apply]);

  const signIn = useCallback(async () => {
    await userManager.signinRedirect();
  }, [userManager]);

  const signOut = useCallback(async () => {
    const idToken = userRef.current?.id_token;
    apply(null);
    await userManager.removeUser();
    await userManager.signoutRedirect(idToken ? { id_token_hint: idToken } : {});
  }, [userManager, apply]);

  const getToken = useCallback(() => {
    const u = userRef.current;
    return u && !u.expired ? u.access_token : null;
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    status,
    userName: user ? displayName(user) : null,
    error,
    signIn,
    signOut,
    getToken,
  }), [status, user, error, signIn, signOut, getToken]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
