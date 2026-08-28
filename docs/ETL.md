# First-load ETL: `core.*` → Directory Admin

Cutover copies rows from db-dice `postgres.core.people` / `core.organizations` / `core.assignments` into the `directory` database via:

```bash
SOURCE_DATABASE_URL=… python manage.py import_from_db_dice
```

UUIDs and `tenant_id` are preserved. Caps become Django Groups (see [CUTOVER.md](CUTOVER.md)). This file is the column map: **import**, **transform**, or **drop**.

County-core PHP is unchanged. Dropped person columns are still sent on `/sync` and force-sync as `null` so existing ACF mappings do not break. `full_name` on the wire is the **resolved** display string (override if set, otherwise name parts).

## `core.people` → `people_person`

| Source (`core.people`) | Destination | Notes |
|---|---|---|
| `id` | `id` | Keep UUID |
| `tenant_id` | `tenant_id` | |
| `employee_id` | `employee_id` | Keep; LDAP match later |
| `name_first` | `name_first` | |
| `name_middle` | `name_middle` | |
| `name_last` | `name_last` | |
| `name_suffix` | `name_suffix` | |
| `full_name` | `display_name` | **Transform.** Import only when it differs from `first + middle + last + suffix`. Matching values are dropped so the name is computed. |
| `email_public` | `email_public` | |
| `phone_public` | `phone_public` | |
| `phone_public_ext` | `phone_public_ext` | |
| `show_in_directory` | `show_in_directory` | |
| `archived_at` | `archived_at` | |
| `created_at` | `created_at` | |
| `updated_at` | *(Django `auto_now`)* | Not copied; set on save |
| `job_title` | **drop** | Person-level leftover. Website titles come from `assignments.job_title`. |
| `person_key` | **drop** | Legacy unique key; not used by the admin or WordPress display. |
| `role` | **drop** | Leftover person column; not the assignment “role”. |

Resolved name used in the UI and on the WP wire is `Person.full_name` (Python property): `display_name` if set, else composed name parts (including middle and suffix).

## `core.organizations` → `organizations_organization`

| Source | Destination | Notes |
|---|---|---|
| `id` | `id` | Keep UUID |
| `tenant_id` | `tenant_id` | |
| `org_type` | `org_type` | |
| `name` | `name` | |
| `slug` | `slug` | Fallback `organization` if empty |
| `public_email` | `public_email` | |
| `phone` | `phone` | |
| `parent_id` | `parent_id` | Applied in a second pass after all orgs exist |
| `website_url` | `website_url` | |
| `hours_text` | `hours_text` | |
| `archived_at` | `archived_at` | |
| `created_at` | `created_at` | |
| `address_mailing` | `address_mailing` | |
| `address_physical` | `address_physical` | |
| `additional_information` | `additional_information` | |
| `fax` | `fax` | |
| `updated_at` | *(Django `auto_now`)* | Not copied |
| `department_id` | **drop** | Legacy string id; hierarchy is `parent_id` |
| `parent_department_id` | **drop** | Legacy string id; replaced by `parent_id` |

`sort_order` exists on the Django model (print directory) but **not** on `core.organizations`. It is not imported; clerks can set it later if needed.

## `core.assignments` → `assignments_assignment`

| Source | Destination | Notes |
|---|---|---|
| `id` | `id` | Keep UUID |
| `tenant_id` | `tenant_id` | |
| `person_id` | `person_id` | Nullable (vacant seats) |
| `org_id` | `org_id` | |
| `seat_no` | `seat_no` | |
| `status` | `status` | Print directory excludes `inactive` |
| `job_title` | `job_title` | **Keep.** This is the role title (Chair, Deputy, …). |
| `created_at` | `created_at` | Date; WP maps it to start date |
| `receives_financial_reports` | `receives_financial_reports` | Keep for WP/ACF; not in the Vue editor yet |
| `updated_at` | *(Django `auto_now`)* | Not copied |

## Caps (not directory columns)

| Source | Destination |
|---|---|
| `core.caps.cap_key` `directory_editor` / `permissions_admin` | Django `Group` |
| `core.people_caps` | `User` via `upgrade_person_to_user` + `TenantMembership` |

Not imported: `ops.otp_tokens`, FastAPI sessions.

## Looked at, kept on purpose

- **`assignments.job_title`** — the actual role name; UI already calls it “Role name”.
- **`assignments.status`**, **`seat_no`**, **`receives_financial_reports`**
- **`people.employee_id`** — uniqueness + planned LDAP match
- **Org contact/address/hours/fax/`additional_information`** — public website fields
- **`organizations.sort_order`** — print layout (new; not in `core`)
