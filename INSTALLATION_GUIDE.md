# Installation

See README for the three local processes. Install dependencies into a dedicated virtual environment. Python/PyTorch compatibility depends on available platform wheels; choose a supported Python release when pip reports no compatible wheel. A GPU is not required.

The frontend uses npm's committed lockfile (`npm ci`). Python dependencies are bounded in backend/requirements.txt; resolved backend versions in this environment were FastAPI 0.138.2, SQLAlchemy 2.1.8, NumPy 2.5.2, PyTorch 2.15.0+cpu and Uvicorn 0.49.0. These are execution-environment observations, not a universal lock across platforms. Generate a deployment lock after resolving dependencies on the target OS.

Database defaults to `artifacts/pricemesh.db`; artifacts and the development signing key also live under artifacts/. Set DATA_DIR for a different persistent location. DATABASE_URL accepts `postgresql+psycopg://...`. The Python app reads process environment variables; it does not automatically load a `.env` file. Docker Compose reads `.env` automatically.

In development, the signing secret is generated once and saved to the ignored artifact directory. Production requires an explicit JWT_SECRET of at least 32 characters. Provision the initial admin only after registration:

```powershell
python -m backend.app.admin --email your-email@example.com
```

This operator command changes access; do not expose it through an unauthenticated HTTP endpoint. Register real credentials yourself. Never publish test credentials or the development signing key.

Optional tracking: install backend/requirements-tracking.txt, set MLFLOW_TRACKING_URI and start/reach the MLflow service. Mirror failures are reported in the result metadata; they do not erase database results.
