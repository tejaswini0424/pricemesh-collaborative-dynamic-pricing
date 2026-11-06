# Database schema

Implemented with SQLAlchemy and Alembic revisions `0001` and `0002`.

Production on Vercel uses the linked Neon PostgreSQL database. API and worker apply serialized migrations with transaction-scoped PostgreSQL advisory locks, compatible with Neon's transaction pooler. Cloud artifacts use private Vercel Blob paths derived from server job UUIDs; local DATA_DIR is only temporary staging. Resource ownership is checked before artifact access.

| Table | Purpose and relations |
|---|---|
| users | Unique normalized email, PBKDF2 password hash, role, active flag, settings |
| sessions | User FK, hashed opaque refresh token, expiry, revocation |
| resources | Owner FK, kind, name, source resource FK, immutable validated JSON, created timestamp |
| jobs | Owner FK, config snapshot, progress/details, heartbeat, state, result resource FK, cancellation and simulation controls |
| notifications | Owner FK, job FK, read state and completion/failure message |
| audit_events | User FK where known; action, resource target, timestamp; hashed login-attempt keys |
| worker_leases | Worker identity and heartbeat |

Every ID is server-generated UUID except the worker lease ID. Artifact directories use server job UUIDs and are resolved under DATA_DIR. Source resource lineage links scenario → catalog, experiment → scenario, policy → experiment and evaluation → scenario. Evaluation payloads also retain the owner-validated policy ID.

Indexes cover owner, resource type, source, creation time, unique user email, session token hash, job state and audit lookup. JSON allows immutable schema snapshots rather than mutable joins to catalog product rows. SQLite enables foreign keys and WAL; PostgreSQL uses psycopg. SQLite is for a small local installation, not a distributed shared filesystem.

Migrate before deployment:

```powershell
python -m alembic -c backend/alembic.ini upgrade head
```

Development create_all creates missing tables only. It cannot migrate existing tables. Do not manually mark an uninitialized database as migrated. Downgrades remove data; normal releases use forward migrations and backups.
