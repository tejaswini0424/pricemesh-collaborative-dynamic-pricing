# Deployment

## Local Docker Compose

Copy `.env.example` to `.env`, replace both secrets and keep APP_ENV=development for local HTTP. Use a URL-safe PostgreSQL password or correctly URL-encode it in DATABASE_URL. Run `docker compose up --build`; open http://localhost:8080. Database and artifact named volumes persist. Migrations run before API and worker startup. API readiness is checked before the frontend starts.

Docker is not installed in the current execution environment, so image builds, PostgreSQL runtime and container restart persistence remain **unverified**. The SQLite migration and persistence workflow have been tested locally. Do not describe the container stack as production verified until these commands succeed on the target host.

Optional tracking profile: set `MLFLOW_TRACKING_URI=http://mlflow:5000` in `.env` and start with `docker compose --profile tracking up --build`. The MLflow endpoint is private to the Compose network and stores artifacts in its tracking volume. Test compatibility with the resolved MLflow version before relying on this mirror; no MLflow service was run here.

## Public production

Set APP_ENV=production, a long random JWT_SECRET, explicit HTTPS CORS_ORIGINS and persistent DATABASE_URL/DATA_DIR. Put a TLS reverse proxy/load balancer in front of Nginx. Cookies are Secure in production; HTTP login will not retain refresh sessions. Publish only the frontend/proxy. Keep PostgreSQL and tracking services private. Configure trusted proxy addresses for your own ingress rather than trusting arbitrary forwarding headers.

API and worker must share the same artifact volume and database. Back up both consistently, test restore, apply migrations once per release and monitor worker heartbeats, queued jobs, failed jobs, disk capacity and API readiness. Use an external load balancer for ingress limits and managed secret injection. The application enforces login throttling and per-account job budgets; it is not a replacement for infrastructure abuse protection.

## Vercel frontend

### Connect the persistent backend

The repository includes a ready-to-review Render Blueprint: [deploy backend](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Ftejaswini0424%2Fpricemesh-collaborative-dynamic-pricing).

1. Sign in to Render and review `render.yaml`. It proposes one **paid Standard** Python web service and a **1 GB persistent disk**. Review Render's charges before approving creation; no backend service has been purchased or created by this configuration alone.
2. Render generates JWT_SECRET. The disk stores SQLite and artifacts under `/var/data`. The hosted launcher runs migrations at startup and supervises API and worker in the same instance, because Render cannot share one disk between separate services. This is a single-instance research deployment, not high availability; back up the database and artifacts.
3. Wait for the Render service to become healthy. Copy its actual HTTPS origin, such as the URL shown in Render's dashboard. Do not assume that a service name implies a particular available hostname.
4. From the repository root, run `node scripts/connect-backend.mjs https://YOUR-ACTUAL-BACKEND-HOST`. The script checks PriceMesh readiness before updating frontend/vercel.json with same-origin API and documentation rewrites. An invalid/unreachable backend leaves the frontend configuration unchanged.
5. Commit and push the generated vercel.json change. Vercel automatically redeploys. Keep VITE_API_BASE_URL unset, so the browser calls `/api/v1` on the frontend domain. CORS_ORIGINS must include the exact production frontend origin; the Blueprint includes the current Vercel domain.
6. Verify `/api/v1/health/ready` through the Vercel domain, then register, reload, train and export through the public UI. Check worker status in System health. Only after these pass is the online backend connection complete.

The hosted launcher was exercised locally with production-mode configuration, a fresh migrated database and a real API-to-worker dataset job. Render itself still requires your account and service creation. See [Render disk limitations](https://render.com/docs/disks) and [Blueprint reference](https://render.com/docs/blueprint-spec).

Live frontend: https://pricemesh-dynamic-pricing.vercel.app. The Vercel project `pricemesh-dynamic-pricing` is connected to the GitHub repository with its Root Directory set to `frontend`. GitHub pushes build that directory using `npm run build` and publish `dist`. The supplied vercel.json rewrites frontend routes to index.html. This **does not host the Python worker**. Deploy the persistent API/worker to a suitable container/VM host to enable online account and research operations.

Preferred routing is a same-origin Vercel rewrite from `/api/:path*` to the actual deployed backend `/api/:path*`; add that exact destination only after a real backend URL exists. Route Swagger/OpenAPI too if desired. Leave VITE_API_BASE_URL=/api/v1. Alternatively use same-site HTTPS subdomains and set VITE_API_BASE_URL to the API URL before building. Unrelated domains will conflict with Strict refresh cookies and are unsupported without a proxy.

Vercel authorization and frontend production deployment completed on 5 November 2026. The production root, dashboard and training deep link returned HTTP 200. No public backend URL is configured, so public authentication → job → export remains unverified and unavailable. Frontend publication alone is not a full-stack deployment.

## Release verification

Run component/backend/browser suites and production frontend build. Then verify production health, registration, login after reload, catalog persistence after API restart, worker execution, cancellation, result ownership, simulation SSE/reconnect, report download, deep links, mobile navigation and backup restore. Check the configured MLflow endpoint with a real run if tracking is enabled.
