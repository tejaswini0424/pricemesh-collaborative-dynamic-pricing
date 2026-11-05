# Testing

Commands are in README. Backend tests use unittest and temporary SQLite databases; they never use production data. Run outside a restricted sandbox if the operating system prevents temporary SQLite/artifact writes. Test teardown disposes pooled connections before deleting temporary files.

Executed at the current implementation milestone:

- 14 backend tests passed: simulator/accounting/constraints, reproducible tapes, held-out evaluation, IPPO/MAPPO/shared-PPO checkpoint round trips, owner isolation, invalid input, session rotation/revocation, admin authorization, dataset → training → evaluation → analysis → report → simulation workflow, simulation pause/step/resume and SSE, fresh Alembic migration and idempotent restart.
- 43 frontend component tests passed, including all 32 route headings and active navigation, unknown/root routes, client navigation, theme persistence, sign-in dialog, empty metrics, authenticated API form submission, direct dashboard logout/login and full-month date formatting across an India/UTC date boundary. API responses are mocked only in isolated component tests.
- Strict TypeScript/Vite production build passed. Bundle chunks split React and charts.
- The route manifest check confirms exactly 32 unique routes.

The real-browser workflow passed twice consecutively in installed Chrome (38.3 seconds including services). It exercised actual UI registration, catalog, scenario, MAPPO training, seven-condition robustness evaluation, JSON report download, session restoration after reload and mobile navigation. No browser runtime errors were reported. Desktop/dashboard and mobile/policy screenshots were generated and visually inspected. The mobile policy view had no horizontal overflow. Test definition: frontend/e2e/workflow.spec.ts. Test data and API/worker services are isolated from the local development database. The test explicitly waits for route completion before interacting with similarly named controls.

The standalone research runner was also smoke-tested with two independent training seeds, two training episodes and two evaluation episodes for each of IPPO/MAPPO/shared PPO. It produced 21 algorithm-condition summaries and seven paired training-seed comparisons. This tiny run verifies the aggregation pipeline and is insufficient for scientific performance conclusions.

The latest browser run passed in 25.9 seconds including startup, with additional assertions for the dashboard month-name date, direct logout, hiding the previous session's results and logging back into the same account. It reported no browser runtime errors.

Not verified here: Docker image startup, PostgreSQL behavior, MLflow service mirroring, HTTPS production cookie routing, backup restore, sustained load and training convergence. These remain target-environment release checks. Statistical effectiveness requires multi-training-seed research runs; tests do not manufacture a positive learning result.

Hosted-backend preparation: the supervised production launcher passed a real local HTTP test covering migrations, account creation and an API-to-worker dataset job. Two Node tests passed for HTTPS backend URL validation and repeatable Vercel proxy configuration. These checks do not mean a Render service has been provisioned or that public routing is connected.
