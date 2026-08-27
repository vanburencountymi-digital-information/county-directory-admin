# Staging Cloud SQL + Cloud Run

GCP project: `core-db-475718`. Region: `us-central1`.

Directory data lives in a **separate Postgres database** named `directory` on the existing Cloud SQL instance `db-dice`. That keeps Cloud SQL instance cost at one box. Do **not** run Django migrations against the `postgres` database (Sqitch/`core.*` live there). Django `DATABASE_URL` must use `dbname=directory`.

ETL `SOURCE_DATABASE_URL` still points at `db-dice` / `postgres` so `import_from_db_dice` can read `core.people` / `core.organizations` / `core.assignments`.

## Two WordPress secrets

| Secret Manager name | Env var | Used for |
|---|---|---|
| `DIRECTORY_SYNC_API_SECRET` | `SYNC_API_SECRET` | county-core → Django `GET /sync/*` Bearer |
| `WP_SYNC_TRIGGER_SECRET` (or existing `SYNC_SECRET`) | `WP_SYNC_TRIGGER_SECRET` | Django → WordPress REST header `X-County-Directory-Admin-Secret` |

Do not reuse one secret for both. Mixing them locks WordPress out of `/sync` or lets the wrong caller trigger admin pushes.

Also store:

- `DIRECTORY_DATABASE_URL` — Cloud SQL unix-socket URL for instance `db-dice`, database `directory`
- `DIRECTORY_DJANGO_SECRET_KEY`
- existing `WP_EMAIL_API_KEY` and `WP_SYNC_TRIGGER_URL_BY_TENANT` (same as Directory Admin today)

## Provision

From a workstation with `gcloud` authenticated to `core-db-475718`:

```bash
./scripts/provision-staging.sh
```

On Windows PowerShell:

```powershell
.\scripts\provision-staging.ps1
```

The script creates database `directory` on `db-dice` if missing, plus Secret Manager placeholders. Cloud Run uses the same serverless VPC connector and `--add-cloudsql-instances=...:db-dice` as `directory-admin`.

Point a **staging** WordPress (or a dry-run site) at:

- Sync API URL: `https://<staging-host>/`
- Sync API secret: the inbound Bearer (`DIRECTORY_SYNC_API_SECRET`)

Confirm the county-core admin page shows **HTTP**, not `COUNTY_PG_*`.

Production FastAPI (`directory-admin`) writing `postgres.core.*` stays the only production directory writer until [CUTOVER.md](CUTOVER.md).
