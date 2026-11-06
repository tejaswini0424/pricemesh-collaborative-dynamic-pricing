# PriceMesh

Collaborative Multi-Agent Reinforcement Learning Framework for Dynamic Pricing in E-Commerce.

**Live application:** https://pricemesh-dynamic-pricing.vercel.app

Frontend and API are deployed together with Vercel Services. A Vercel Daemon runs the pricing-training worker. Persistent records use the linked free Neon PostgreSQL database; datasets and checkpoints use private Vercel Blob. The full local workflow remains available as well.

API readiness: https://pricemesh-dynamic-pricing.vercel.app/api/v1/health/ready. API documentation: https://pricemesh-dynamic-pricing.vercel.app/docs. Register your own account using Login; no default password exists. Vercel Services and Daemons are beta products and Hobby quotas apply.

An integrated research application for a **synthetic single-retailer** marketplace. React frontend, authenticated FastAPI service, durable database queue, independent worker and explicit PyTorch IPPO/MAPPO implementations. The approved design is in [PROJECT_BLUEPRINT.md](PROJECT_BLUEPRINT.md); implementation differences are recorded in [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md).

## Run locally

Use Python 3.12+ with a supported PyTorch wheel, Node.js 22+ and npm. The development workflow was checked with Python 3.14 and Node 26 on this machine. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt -r backend/requirements-test.txt
python -m alembic -c backend/alembic.ini upgrade head
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In another terminal, activate the same environment and run the worker from the root:

```powershell
python -m backend.app.worker
```

In a third terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open [PriceMesh](http://127.0.0.1:5173). Create your own account; no default credentials exist. API docs: [Swagger](http://127.0.0.1:8000/docs).

The dashboard includes a Login/Logout control and the current date with the full month name (for example, 5 November 2026). Its calendar uses India Standard Time and updates automatically.

```powershell
npm run build
npm run preview
```

Vite proxies `/api` to the local backend. `npm run preview` serves only the built frontend and does not proxy the API. For integrated deployment use the supplied reverse proxy. Google Fonts is optional; fallback fonts work offline.

## Demonstrate the full workflow

1. Product catalog: review the editable synthetic example and save a catalog.
2. Market scenarios: select that catalog and save the horizon, demand and constraints.
3. Generate dataset: run seeded synthetic transactions, then inspect quality and download CSV/JSON.
4. Training studio: select a scenario, choose IPPO/MAPPO/shared PPO, and submit training. Start with 2 episodes to check execution; longer runs are required to study learning.
5. Robustness suite: select the resulting policy and run held-out evaluations.
6. Performance/comparison: inspect actual profit, paired fixed-price differences and episode-bootstrap intervals.
7. Market simulation: stream artificial decisions with pause/resume/step controls, then inspect inventory and analytics.
8. Reports: save evaluation-backed JSON, CSV or printable HTML. HTML can be saved as PDF through the browser.

Experiments snapshot scenarios; existing artifacts remain immutable. Dashboard metrics are derived from the current account's saved results. Training losses and progress reflect actual completed work. There is no connection to a real store.

## Verification

```powershell
python -m unittest discover -s tests -v
node scripts/check-routes.mjs
cd frontend
npm test
npm run build
npm run test:e2e
```

The backend suite covers end-to-end API/worker behavior, all three PPO variants, accounting, bounds, ownership, refresh rotation, migrations, simulation controls and SSE. Component tests cover all 32 routes and authenticated forms. See [TESTING_GUIDE.md](TESTING_GUIDE.md) for executed checks and limitations.

## Deployment and limits

Copy `.env.example` to `.env`, replace both secrets, then use `docker compose up --build` when Docker is installed. The local container entrypoint is [localhost:8080](http://localhost:8080). Docker/PostgreSQL and MLflow integration are configured but have not been executed on this machine. See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md).

Vercel builds from the repository root using root vercel.json, which defines the frontend/API services and training-worker daemon. Do not change its Root Directory back to frontend. No Render service is required. See DEPLOYMENT_GUIDE.md for environment settings and quotas.

No real-world profit or convergence claims are made. Single-policy intervals describe episode uncertainty; use the multi-training-seed runner in [MODEL_EVALUATION.md](MODEL_EVALUATION.md) for research. Full demand-model calibration, consumer segmentation, learned elasticity, and live commerce integrations are outside this release.
