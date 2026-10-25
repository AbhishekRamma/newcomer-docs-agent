import { useMemo, useState } from "react";
import { createApiClient } from "./api";
import { useAuth } from "./authContext";
import { Chat } from "./components/Chat";
import { Header, type View } from "./components/Header";
import { HistoryView } from "./components/HistoryView";
import { LoginScreen } from "./components/LoginScreen";
import { config } from "./config";

export function App() {
  const auth = useAuth();
  const [view, setView] = useState<View>("chat");
  const { getToken, signIn, signOut } = auth;
  const api = useMemo(
    () => createApiClient({ baseUrl: config.apiBaseUrl, getToken, onUnauthorized: signIn }),
    [getToken, signIn],
  );

  return (
    <>
      <div className="backdrop" aria-hidden="true">
        <span className="blob b1" /><span className="blob b2" /><span className="blob b3" />
      </div>
      <div className="crt" aria-hidden="true" />
      {auth.status === "signedIn" ? (
        <Header userName={auth.userName} view={view} onNavigate={setView}
          onSignOut={() => void signOut()} />
      ) : (
        <Header userName={null} />
      )}
      <main className="window glass" aria-labelledby="title">
        <div className="titlebar" aria-hidden="true" />
        {auth.status === "loading" && <p className="lede">Checking your session…</p>}
        {auth.status === "signedOut" && <LoginScreen onSignIn={() => void signIn()} error={auth.error} />}
        {auth.status === "signedIn" && (
          <>
            {/* Chat stays mounted so the conversation survives a trip to History. */}
            <div hidden={view !== "chat"}><Chat api={api} /></div>
            {view === "history" && <HistoryView api={api} />}
          </>
        )}
      </main>
    </>
  );
}
