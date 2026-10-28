# Library licences (web app and auth)

I checked each from its installed package metadata (`node_modules/*/package.json`, Python `importlib.metadata`):

| library | version | licence | used for |
|---|---|---|---|
| PyJWT | 2.15.1 | MIT | JWT signature and claim checks |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | RSA for PyJWT |
| react, react-dom | 18.3.1 | MIT | UI |
| oidc-client-ts | 3.5.0 | Apache-2.0 | OIDC / PKCE in the browser |
| jwt-decode (dependency of oidc-client-ts) | 4.0.0 | MIT | (pulled in by oidc-client-ts) |
| vite, @vitejs/plugin-react | 6.4.5, 4.7.0 | MIT | dev server and build |
| typescript | 5.8.3 | Apache-2.0 | type checking |
| vitest, jsdom | 3.2.7, 26.1.0 | MIT | tests |
| @testing-library/react, dom, jest-dom, user-event | 16.3.3, 10.4.2, 6.9.1, 14.6.8 | MIT | component tests |
| eslint, @eslint/js, typescript-eslint, eslint-plugin-react-hooks, eslint-plugin-react-refresh, globals | 9.39.5, 9.39.5, 8.72.0, 5.2.0, 0.5.7, 17.13.0 | MIT | lint |
| @types/react, @types/react-dom, @types/node | 18.3.31, 18.3.7, 22.20.5 | MIT | types |
| Keycloak image `quay.io/keycloak/keycloak:26.4` | 26.4 | Apache-2.0 | identity provider (run, not bundled) |
| `nginxinc/nginx-unprivileged:1.27-alpine`, `node:22-alpine` | — | nginx: BSD-2-Clause; Node.js: MIT | web image build and serving |

The production JavaScript bundle contains only MIT and Apache-2.0 code (react, react-dom, scheduler, loose-envify, js-tokens, oidc-client-ts, jwt-decode). Across all of `web/node_modules`, including dev tools, the licences are MIT, Apache-2.0, ISC, BSD-2/3-Clause, MIT-0, Python-2.0, CC-BY-4.0 (a data package) and BlueOak-1.0.0. None is copyleft.
