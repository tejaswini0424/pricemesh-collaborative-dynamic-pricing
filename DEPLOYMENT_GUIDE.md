# Deployment

## Local Docker Compose

Copy `.env.example` to `.env`, replace both secrets and keep APP_ENV=development for local HTTP. Use a URL-safe PostgreSQL password or correctly URL-encode it in DATABASE_URL. Run `docker compose up --build`; open http://localhost:8080. Database and artifact named volumes persist. Migrations run before API and worker startup. API readiness is checked before the frontend starts.

Docker is not installed in the current execution environment, so image builds, PostgreSQL runtime and container restart persistence remain **unverified**. The SQLite migration and persistence workflow have been tested locally. Do not describe the container stack as production verified until these commands succeed on the target host.

Optional tracking profile: set `MLFLOW_TRACKING_URI=http://mlflow:5000` in `.env` and start with `docker compose --profile tracking up --build`. The MLflow endpoint is private to the Compose network and stores artifacts in its tracking volume. Test compatibility with the resolved MLflow version before relying on this mirror; no MLflow service was run here.

## Public production

Set APP_ENV=production, a long random JWT_SECRET, explicit HTTPS CORS_ORIGINS and persistent DATABASE_URL/DATA_DIR. Put a TLS reverse proxy/load balancer in front of Nginx. Cookies are Secure in production; HTTP login will not retain refresh sessions. Publish only the frontend/proxy. Keep PostgreSQL and tracking services private. Configure trusted proxy addresses for your own ingress rather than trusting arbitrary forwarding headers.

API and worker must share the same artifact volume and database. Back up both consistently, test restore, apply migrations once per release and monitor worker heartbeats, queued jobs, failed jobs, disk capacity and API readiness. Use an external load balancer for ingress limits and managed secret injection. The application enforces login throttling and per-account job budgets; it is not a replacement for infrastructure abuse protection.

## Vercel frontend

From frontend/: `npx vercel --prod`. The supplied vercel.json builds Vite and rewrites frontend routes to index.html. This **does not host the Python worker**. Deploy the persistent API/worker to a suitable container/VM host first.

Preferred routing is a same-origin Vercel rewrite from `/api/:path*` to the actual deployed backend `/api/:path*`; add that exact destination only after a real backend URL exists. Route Swagger/OpenAPI too if desired. Leave VITE_API_BASE_URL=/api/v1. Alternatively use same-site HTTPS subdomains and set VITE_API_BASE_URL to the API URL before building. Unrelated domains will conflict with Strict refresh cookies and are unsupported without a proxy.

The previous Vercel login request required user authorization. No public full-stack deployment has been confirmed. Do not claim a deployed URL exists until the CLI reports success and the public authentication → job → export workflow passes.

## Release verification

Run component/backend/browser suites and production frontend build. Then verify production health, registration, login after reload, catalog persistence after API restart, worker execution, cancellation, result ownership, simulation SSE/reconnect, report download, deep links, mobile navigation and backup restore. Check the configured MLflow endpoint with a real run if tracking is enabled.
