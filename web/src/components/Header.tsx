export type View = "chat" | "history";

export function Header({ userName, view, onNavigate, onSignOut }: {
  userName: string | null;
  view?: View;
  onNavigate?: (v: View) => void;
  onSignOut?: () => void;
}) {
  return (
    <header className="menubar glass">
      <span className="logo" aria-hidden="true" />
      <span className="brand pixel">Newcomer Desk</span>
      {onNavigate && (
        <nav className="tabs" aria-label="Sections">
          <button type="button" aria-current={view === "chat" ? "page" : undefined}
            onClick={() => { onNavigate("chat"); }}>Ask</button>
          <button type="button" aria-current={view === "history" ? "page" : undefined}
            onClick={() => { onNavigate("history"); }}>History</button>
        </nav>
      )}
      <span className="spacer" />
      {userName && (
        <span className="who" title="Signed in">
          <span className="dot" aria-hidden="true" />
          <span className="visually-hidden">Signed in as </span>{userName}
        </span>
      )}
      {onSignOut && <button type="button" className="signout" onClick={onSignOut}>Sign out</button>}
    </header>
  );
}
