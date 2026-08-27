# Production cutover

db-dice remains the production source of truth until this window. No dual-write.

## Before the window

- [ ] Staging Cloud Run + `db-dice` database `directory` healthy ([STAGING.md](STAGING.md))
- [ ] `pytest` green; WordPress golden tests passing (booleans, `full_name`, `tenant_id`)
- [ ] Confirm each production WP site’s county-core admin page: Sync API URL mode, not `COUNTY_PG_*`
- [ ] Announce: **all Directory Admin sessions end**. FastAPI HMAC cookies cannot become Django sessions. Every clerk requests a new magic link after cutover.
- [ ] Freeze plan for Cloud Run `directory-admin` (scale to 0 or read-only)

## Cutover steps

1. **Freeze FastAPI** so nothing writes `core.people` / `core.organizations` / `core.assignments` on db-dice.
2. Set `SOURCE_DATABASE_URL` to db-dice (Secret Manager / Cloud Run job) and run:

   ```bash
   python manage.py import_from_db_dice
   ```

   The command copies people, organizations, and assignments **preserving UUIDs and `tenant_id`**, then maps `core.caps` / `core.people_caps` into Groups (`directory_editor`, `permissions_admin`), Users via `upgrade_person_to_user`, and `TenantMembership`. It asserts membership equivalence. It does **not** import `ops.otp_tokens`.
3. Point Django `DATABASE_URL` at `db-dice` database `directory` (not the `postgres` database).
4. Point each WordPress site’s **Sync API URL** at Django (`https://<county-directory-host>/`) and the inbound `SYNC_API_SECRET`. Confirm HTTP mode, not libpq.
5. Run incremental/full county-core sync, then Directory Admin “Check website drift”.
6. Keep db-dice `core.people` / `core.organizations` / `core.assignments` in place as UUID-stable stubs (documents FKs, dice-portal auth). Do not drop them.
7. Scale `directory-admin` to 0. The old Sync API Cloud Run must not remain the WP target.

## After

- Clerks sign in via magic link on the new app. The login page explains previous sessions ended.
- New staff created only in the directory DB will not appear in dice-portal until a follow-up.
- county-data-services: do not keep evolving directory DDL in Sqitch except for stub compatibility.
