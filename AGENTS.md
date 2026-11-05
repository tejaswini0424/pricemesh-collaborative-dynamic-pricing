# Development guidance

The approved design is PROJECT_BLUEPRINT.md. The repository now contains an integrated frontend, FastAPI service, durable queue, worker, simulator and PPO research engine. PROJECT_REQUIREMENTS.md records deviations and release boundaries.

- Preserve all 32 approved routes and their distinct domain responsibilities.
- Never populate dashboards with invented experiment metrics or label browser drafts as persisted backend records.
- Validate ownership, resource budgets, simulator accounting and reproducibility when implementing the backend.
- Keep training inputs separate from privileged critic-only state and final held-out evaluation data.
- Use `cd frontend; npm test` and `npm run build` after frontend changes. Run `node scripts/check-routes.mjs` from the repository root when changing the catalog.
- Run `python -m unittest discover -s tests -v` for changes affecting backend contracts, simulator, training or persistence. Tests use disposable databases; never point them at a live database.
- Run Alembic migrations before restarting API/worker after a schema change. Development create_all is a bootstrap convenience, not a replacement for migrations.
- All artifact and resource access must remain owner-scoped. Never load arbitrary pickle checkpoints.
- Keep README milestone status and known limitations accurate.

## Verified at this milestone

See TESTING_GUIDE.md for current executed checks. Never call a Docker/MLflow/PostgreSQL deployment verified unless it was actually run. Keep browser test fixtures separate from real accounts and data.
