import { createContext, useContext } from "react";

export type AuthStatus = "loading" | "signedOut" | "signedIn";

export interface AuthContextValue {
  status: AuthStatus;
  userName: string | null;
  error: string | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => string | null;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const v = useContext(AuthContext);
  if (!v) throw new Error("useAuth must be used inside <AuthProvider>");
  return v;
}
