# Deployment

## Current Vercel deployment

Application: https://pricemesh-dynamic-pricing.vercel.app/dashboard
API readiness: https://pricemesh-dynamic-pricing.vercel.app/api/v1/health/ready
API documentation: https://pricemesh-dynamic-pricing.vercel.app/docs

Root `vercel.json` defines:

- `frontend`: Vite service rooted at frontend/.
- `backend`: Python CPU container from Dockerfile.vercel, routed under /api and /docs.
- `training-worker`: one 1 GiB Vercel Daemon in iad1, built from Dockerfile.worker.

Services and Daemons are beta products. Both service images and worker built on Vercel; no local Docker daemon was needed for the cloud builds. The production API returned ready, and Vercel reported one ready worker on 6 November 2026.

The linked Vercel project's Root Directory is the repository root (not frontend). Framework, build and output settings belong to the frontend service. GitHub pushes build and release the whole application together. Do not change the root back to frontend or run scripts/connect-backend.mjs for this multi-service deployment; that script belongs to the optional external-backend setup.

## Persistent data and environment

Neon resource `pricemesh-database` was provisioned on its free plan in iad1. Vercel private Blob store `pricemesh-artifacts` holds datasets/checkpoints. Neither API nor worker treats temporary local files as durable storage. Session signing secrets are generated privately and are never committed.

Production environment settings:

| Variable | Purpose |
|---|---|
| DATABASE_URL | Provisioned Neon connection; normalized to SQLAlchemy psycopg |
| BLOB_READ_WRITE_TOKEN | Provisioned private Blob access; never expose to clients |
| JWT_SECRET | Secret session-signing key, at least 32 characters |
| APP_ENV=production | Secure session cookies |
| ARTIFACT_STORAGE=vercel-blob | Durable cloud artifact adapter |
| AUTO_MIGRATE=1 | Serialized API/worker migrations at startup |
| PORT=8000 | Backend container listener |
| CORS_ORIGINS | Exact public frontend HTTPS origin |
| WORKER_POLL_SECONDS=5 | Durable queue polling interval |

The application uses relative `/api/v1` URLs, so browser sessions remain same-origin. No VITE_API_BASE_URL is needed. PostgreSQL migration locks are transaction-scoped for compatibility with the Neon pooler. Private artifact downloads are authorized through the API; exports stream to avoid a buffered function-response size ceiling.

Never commit `.env.local`, pulled Vercel settings, credentials, or data. The integration values belong to the linked project; do not copy production database URLs into automated tests. Preview databases and test fixtures must remain separate from production accounts.

## Deploy and inspect

From the repository root after verifying the intended project:

```powershell
npx vercel project inspect --non-interactive
npx vercel deploy --prod --skip-domain
npx vercel curl https://YOUR-STAGED-URL/api/v1/health/ready
npx vercel promote https://YOUR-STAGED-URL
npx vercel daemons inspect training-worker
```

Staged production deployments use production settings but do not replace the public domain until promoted. Daemons start when the deployment becomes the production deployment, and only run in production during beta. Do not switch public domains until service builds and API readiness pass. Test accounts belong in isolated databases, not the live production database.

## Quotas, operations and limits

The account was not upgraded to a paid plan. Hobby quotas apply to backend invocations, private storage and daemon compute. A continuously running 1 GiB worker consumes Provisioned Memory quota even while idle. Current limits are documented at https://vercel.com/docs/daemons/limits. When quotas run out, workers may stop until the next period; do not promise unlimited training or continuous availability.

Vercel starts/restarts the worker; the application database stores job progress. Interrupted jobs become failed after their heartbeat expires, rather than being falsely reported complete. Check worker status in System health and daemon logs. Back up the database and artifacts consistently and verify restore. Monitor job failures, database/storage limits and compute use. Scaling workers requires deliberate concurrency/resource review.

MLflow remains optional and unconfigured in this deployment. Training convergence and real-world profitability are not deployment acceptance claims.

## Local Docker Compose and alternative Render host

Local Docker Compose configuration remains available: copy .env.example to .env, replace secrets and run `docker compose up --build`. Local Compose startup/PostgreSQL/MLflow has not been executed on this machine. Vercel image startup does not establish Compose correctness.

The repository also retains render.yaml and backend.app.serve as an optional paid, disk-backed alternative. It is not used or required by the current Vercel deployment. Review the provider's charges before creating it. Migrating to that alternative requires intentionally replacing the Vercel service routing, rather than simply adding a second backend URL.
