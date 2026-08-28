# County Directory

Public staff directory admin and WordPress sync API for Van Buren County and St. Joseph County.

This repository is the Django + Vue **Directory Admin** (and inbound `/sync` API for county-core). Public website display lives in **county-core**. The older WordPress plugin of the same domain lives in a separate repo, [`county-directory`](https://github.com/vanburencountymi-digital-information/county-directory).

Linear: [DIC-1241](https://linear.app/dicelabs/issue/DIC-1241/isolate-directory-public-repo-own-database-on-db-dice)

## Stack

- **Backend:** Django 5.2, Django Ninja, gunicorn, WhiteNoise
- **Frontend:** Vue 3 + Vite + TypeScript
- **Auth:** custom `accounts.User` (required `OneToOne` to `people.Person`), magic-link OTP via `MagicLinkBackend` and Django sessions
- **Permissions:** Django `auth.Group` (`directory_editor`, `permissions_admin`) plus `TenantMembership` for VBC/SJC
- **Database:** Postgres database `directory` on Cloud SQL instance `db-dice`. Do **not** run Django migrations against the `postgres` database (Sqitch / `core.*`).

## Local development

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_groups
python manage.py runserver 8080
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api`, `/sync`, and `/health` to `http://127.0.0.1:8080`.

## Tests

```bash
pytest
```

CI runs `pytest --cov --cov-fail-under=80` against Postgres 17.

```bash
cd frontend
npm test
```

## WordPress contract (do not change county-core PHP)

| Surface | Auth |
|---|---|
| `GET /sync/people`, `/sync/organizations`, `/sync/assignments` | `Authorization: Bearer <SYNC_API_SECRET>` |
| `GET /health` | unauthenticated |
| Clerk APIs (`/api/wordpress/*`) | Django session + `directory_editor` |
| Outbound `force-sync-person` / incremental / reconciliation | header `X-County-Directory-Admin-Secret: <WP_SYNC_TRIGGER_SECRET>` |

Those two secrets are **different**. Person JSON still uses the historical county-core field names (`full_name`, `tenant_id`, booleans). `full_name` on the wire is the resolved display name. Dropped person columns (`job_title`, `person_key`, `role`) are sent as `null` so PHP mappings stay valid. Force-sync runs only on archive, `show_in_directory` toggle, and the manual push button — explicit `wordpress.services` calls, not Django signals.

See [docs/ETL.md](docs/ETL.md) for the first-load column map from `core.*`.

Tenant IDs in production are `VBC` and `SJC`.

## Docker

```bash
docker build -t county-directory .
docker run --rm -p 8080:8080 --env-file .env county-directory
```

## Staging / production

See [docs/STAGING.md](docs/STAGING.md) and [docs/CUTOVER.md](docs/CUTOVER.md). Cutover copies people/orgs/assignments **preserving UUIDs**, maps caps to Groups, then points WordPress **Sync API URL** at this app (HTTP, not `COUNTY_PG_*`). FastAPI sessions cannot be translated — every clerk requests a new magic link.

## LDAP (later)

Add `django-auth-ldap` as a second `AUTHENTICATION_BACKENDS` entry. Recommended default: match an existing Person by `employee_id`; do not auto-provision directory rows from AD.
