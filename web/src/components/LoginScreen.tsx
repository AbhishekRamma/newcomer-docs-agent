export function LoginScreen({ onSignIn, error }: { onSignIn: () => void; error: string | null }) {
  return (
    <>
      <h1 id="title" className="pixel">Sign in to ask</h1>
      <p className="lede">
        Newcomer Desk answers questions about SIN, OHIP, bank accounts, your first tax return and
        Ontario driver&apos;s licences from official government pages. Sign in so your questions
        are saved to your own history.
      </p>
      {error && <p className="msg-error" role="alert">{error}</p>}
      <p className="login-row">
        <button type="button" className="gel" onClick={onSignIn}>Sign in</button>
      </p>
      <p className="fineprint">
        You will be sent to the local Keycloak sign-in page and brought back here. This is a
        local demo stack and is not production-ready.
      </p>
    </>
  );
}
