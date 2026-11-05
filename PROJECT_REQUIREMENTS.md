# Implemented scope and release boundaries

The project title is **Collaborative Multi-Agent Reinforcement Learning Framework for Dynamic Pricing in E-Commerce**. The supplied fraud project was adapted with the user's architecture approval.

Implemented: 32 frontend routes; synthetic product catalogs; immutable scenario and experiment snapshots; demand/inventory simulator; finite-horizon pricing; fixed/inventory/myopic baselines; IPPO, MAPPO and shared-reward local-critic PPO; checkpoints; database jobs; real progress; simulation controls; held-out and seven-shift robustness evaluation; drift, sensitivity and policy diagnostics; authenticated accounts, session revocation, ownership, operator-provisioned administrators; search, notifications, exports; multi-seed study runner; local and container configuration.

## Deliberate implementation differences

- A typed, versioned `resources` table stores immutable catalogs, scenarios, experiments, policies, datasets, evaluations, simulations and reports. Ownership and source lineage use relational foreign keys. This replaces the blueprint's many small metadata tables while preserving snapshots. Large trajectories and weights are stored as artifacts.
- The initial simulator uses integer-rounded lognormal demand and exogenous shock tapes; it does not implement a Poisson/negative-binomial choice model, shared customer budget or competitor-price process. Positive cross-elasticity models substitution approximately; coefficients are user assumptions.
- Algorithms use separate product actors, explicit observation scaling and a central MAPPO critic. No Gymnasium/PettingZoo adapter, category grouping, hyperparameter search or observation-sharing ablation is included. Final fixed-budget checkpoints are saved; there is no best-validation checkpoint claim.
- Dataset generation is a simulator rollout, not CTGAN/TVAE; those fraud-oriented requirements do not apply to this pricing project.
- Policy explanations are controlled actor perturbations. They are not SHAP or causal consumer explanations.
- UI updates poll job state each second. A tested authenticated SSE endpoint is also available. Simulations expose live step decisions; training progress is persisted after each completed episode.
- Reports support JSON, CSV and printable HTML. Direct server-side PDF generation is not included; use browser print-to-PDF.
- MLflow mirroring is optional and records a failed/disabled status honestly. The database remains the source of truth.
- The frontend uses authored CSS rather than Tailwind. All 32 routes use reusable, domain-specific views instead of 32 separate duplicated React files.

## Production release gates

Configure HTTPS, unique secrets, allowed origins, a persistent artifact volume, backups, monitoring and a persistent worker host. Execute the Docker/PostgreSQL and optional MLflow checks in the target environment. Public deployment is not complete until health, authentication, cookie behavior, job execution and exports work through the deployed URL. Vercel account access and a backend host are external requirements.

Resource budgets: at most 20 products, 365 steps per episode, 250,000 product-steps per job and three queued/running jobs per account. The local worker is sequential. A paused simulation occupies its worker. This is a research application, not a high-availability enterprise service.
