# Build the React app with Node, then serve the static files with unprivileged nginx on 5173.
FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_OIDC_AUTHORITY=http://localhost:8080/realms/newcomer
ARG VITE_OIDC_CLIENT_ID=web
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_OIDC_AUTHORITY=$VITE_OIDC_AUTHORITY \
    VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
ENV API_ORIGIN=http://localhost:8000 OIDC_ORIGIN=http://localhost:8080
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 5173
