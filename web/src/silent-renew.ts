// Runs inside the hidden iframe after Keycloak redirects back with prompt=none.
// It passes the result to the parent window; it stores nothing itself.
import { createUserManager } from "./userManager";

void createUserManager().signinSilentCallback();
