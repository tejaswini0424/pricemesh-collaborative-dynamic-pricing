# API reference

Base: `/api/v1`. Authoritative request/response schemas: FastAPI `/docs` and `/openapi.json`.

| Method | Path | Behavior |
|---|---|---|
| GET | /health/live, /health/ready | Liveness and schema/database readiness |
| POST | /auth/register, /auth/login | Credentials → access JWT + refresh cookie |
| POST | /auth/refresh, /auth/logout | Rotate/revoke refresh session; X-Requested-With: PriceMesh required |
| GET | /auth/me | Current account |
| PATCH | /profile | Update display name |
| GET / PUT | /settings | Account defaults |
| GET | /resources?kind=&q=&limit=&offset= | Owner-scoped paginated resources |
| GET | /resources/{id} | Saved resource with immutable payload |
| POST | /catalogs, /scenarios, /experiments | Validated configuration snapshots |
| POST | /experiments/{id}/runs | Queue policy training |
| POST | /datasets/generate | Queue simulator dataset generation |
| POST | /evaluations, /simulations | Queue held-out evaluation or simulated rollout |
| GET | /jobs, /jobs/{id} | Actual state/progress and error details |
| POST | /jobs/{id}/cancel | Cooperative cancellation |
| POST | /jobs/{id}/control | Simulation pause/resume/step |
| GET | /jobs/{id}/events | Authenticated server-sent state events |
| GET | /resources/{id}/records | Paginated dataset/simulation rows; optional SKU filter |
| GET | /resources/{id}/download?format= | JSON/CSV/HTML export |
| POST | /analysis/compare | Pair matching evaluation snapshots and seeds |
| POST | /analysis/drift | Descriptive generated-dataset distribution shifts |
| POST | /analysis/sensitivity | Queue parameter multiplier sweep |
| POST | /analysis/diagnostics | Local actor probability perturbations |
| POST | /reports | Persist evaluation-backed report snapshot |
| GET | /dashboard, /search, /notifications | Actual account-scoped records/aggregates |
| PATCH | /notifications/{id} | Mark read |
| GET | /system/status | Authenticated service status |
| GET / PATCH | /admin/users, /admin/users/{id} | Administrator-only access management |

Use `Authorization: Bearer <access_token>` for protected requests. Access tokens expire after 30 minutes; refresh sessions expire after seven days. Logout and refresh rotation revoke old access sessions. No JWT or password is written to browser local storage.

Errors: 401 unauthenticated, 403 forbidden/origin/header check, 404 missing or unauthorized resource, 409 conflicting operation, 422 invalid configuration, 429 login/job budget. Foreign-owner resource IDs return 404. Price validation requires cost ≤ floor ≤ reference ≤ ceiling. Non-finite numerical inputs and unknown schema fields are rejected. Download fields that could be spreadsheet formulas are escaped.

Training seeds start at ≤50,000, generated datasets at ≥50,001, and final evaluation at ≥100,000. Jobs exceeding 250,000 product-steps are rejected. Refresh cookies are secure in production and SameSite=Strict: route frontend/API through one origin or compatible same-site HTTPS subdomains. Do not deploy unrelated frontend/API domains without an appropriate same-origin proxy.
