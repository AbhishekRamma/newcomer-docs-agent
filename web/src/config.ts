// Public build-time settings (Vite env vars). None of these is a secret.
export interface AppConfig {
  apiBaseUrl: string;
  oidcAuthority: string;
  oidcClientId: string;
}

export const config: AppConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  oidcAuthority: import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8080/realms/newcomer",
  oidcClientId: import.meta.env.VITE_OIDC_CLIENT_ID ?? "web",
};
