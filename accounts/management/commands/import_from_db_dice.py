"""Import directory rows from db-dice (core.* + caps) into this database.

Usage:
  SOURCE_DATABASE_URL=postgres://... python manage.py import_from_db_dice [--dry-run]

Preserves people/org/assignment UUIDs and tenant_id. Maps core.caps/people_caps
into Groups, Users (via upgrade_person_to_user), and TenantMembership.
Does not import OTP tokens or FastAPI sessions.
"""

from collections import defaultdict
from uuid import UUID

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from django.utils.dateparse import parse_date, parse_datetime

from accounts.groups import seed_groups
from accounts.models import TenantMembership, User
from accounts.services import grant_directory_group, upgrade_person_to_user
from assignments.models import Assignment
from organizations.models import Organization
from people.models import Person


def _dt(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value
    return parse_datetime(str(value))


def _d(value):
    if value is None:
        return None
    if hasattr(value, "isoformat") and not hasattr(value, "hour"):
        return value
    return parse_date(str(value))


class Command(BaseCommand):
    help = "Copy directory data from a db-dice SOURCE_DATABASE_URL, preserving UUIDs."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--source-alias",
            default="source",
            help="Django DB alias configured for the source (default: source).",
        )

    def handle(self, *args, **options):
        alias = options["source_alias"]
        if alias not in connections.databases:
            raise CommandError(
                f"Database alias {alias!r} is not configured. "
                "Set SOURCE_DATABASE_URL and include it in settings DATABASES['source']."
            )
        dry = options["dry_run"]
        src = connections[alias]
        stats = {}
        with src.cursor() as cur:
            cur.execute("SELECT * FROM core.organizations")
            org_cols = [c[0] for c in cur.description]
            orgs = [dict(zip(org_cols, row)) for row in cur.fetchall()]
            cur.execute("SELECT * FROM core.people")
            people_cols = [c[0] for c in cur.description]
            people = [dict(zip(people_cols, row)) for row in cur.fetchall()]
            cur.execute("SELECT * FROM core.assignments")
            asg_cols = [c[0] for c in cur.description]
            assignments = [dict(zip(asg_cols, row)) for row in cur.fetchall()]
            cur.execute("SELECT cap_key, id FROM core.caps")
            caps = {row[1]: row[0] for row in cur.fetchall()}
            cur.execute("SELECT person_id, cap_id, tenant_id FROM core.people_caps")
            grants = cur.fetchall()

        stats["organizations_source"] = len(orgs)
        stats["people_source"] = len(people)
        stats["assignments_source"] = len(assignments)
        stats["grants_source"] = len(grants)

        if dry:
            self.stdout.write(self.style.WARNING(f"Dry run: {stats}"))
            return

        seed_groups()
        with transaction.atomic():
            by_id = {}
            for row in orgs:
                oid = row["id"]
                obj, _ = Organization.objects.update_or_create(
                    id=oid,
                    defaults={
                        "tenant_id": row["tenant_id"],
                        "org_type": row["org_type"],
                        "name": row["name"],
                        "slug": row.get("slug") or "organization",
                        "public_email": row.get("public_email"),
                        "phone": row.get("phone"),
                        "website_url": row.get("website_url"),
                        "hours_text": row.get("hours_text"),
                        "archived_at": _dt(row.get("archived_at")),
                        "created_at": _dt(row.get("created_at")),
                        "department_id": row.get("department_id"),
                        "parent_department_id": row.get("parent_department_id"),
                        "address_mailing": row.get("address_mailing"),
                        "address_physical": row.get("address_physical"),
                        "additional_information": row.get("additional_information"),
                        "fax": row.get("fax"),
                    },
                )
                by_id[oid] = (obj, row.get("parent_id"))
            for obj, parent_id in by_id.values():
                if parent_id:
                    obj.parent_id = parent_id
                    obj.save(update_fields=["parent"])

            for row in people:
                Person.objects.update_or_create(
                    id=row["id"],
                    defaults={
                        "tenant_id": row["tenant_id"],
                        "employee_id": row.get("employee_id"),
                        "name_first": row.get("name_first"),
                        "name_middle": row.get("name_middle"),
                        "name_last": row.get("name_last"),
                        "name_suffix": row.get("name_suffix"),
                        "full_name": row.get("full_name"),
                        "email_public": row.get("email_public"),
                        "phone_public": row.get("phone_public"),
                        "phone_public_ext": row.get("phone_public_ext"),
                        "job_title": row.get("job_title"),
                        "person_key": row.get("person_key"),
                        "role": row.get("role"),
                        "show_in_directory": bool(row.get("show_in_directory", True)),
                        "archived_at": _dt(row.get("archived_at")),
                        "created_at": _dt(row.get("created_at")),
                    },
                )

            for row in assignments:
                Assignment.objects.update_or_create(
                    id=row["id"],
                    defaults={
                        "tenant_id": row["tenant_id"],
                        "person_id": row.get("person_id"),
                        "org_id": row["org_id"],
                        "seat_no": row.get("seat_no"),
                        "status": row.get("status"),
                        "job_title": row.get("job_title"),
                        "created_at": _d(row.get("created_at")),
                        "receives_financial_reports": row.get("receives_financial_reports"),
                    },
                )

            expected = defaultdict(set)
            for person_id, cap_id, tenant_id in grants:
                cap_key = caps.get(cap_id)
                if cap_key not in ("directory_editor", "permissions_admin"):
                    continue
                person = Person.objects.get(id=person_id)
                try:
                    grant_directory_group(person, cap_key, tenant_id)
                except ValueError:
                    self.stderr.write(f"Skip grant for {person_id}: no email")
                    continue
                expected[(cap_key, tenant_id)].add(str(person_id))

        # Equivalence: person UUIDs in each Group per tenant
        mismatches = []
        for (cap_key, tenant_id), person_ids in expected.items():
            group = Group.objects.get(name=cap_key)
            actual = set(
                str(u.person_id)
                for u in User.objects.filter(
                    groups=group,
                    tenant_memberships__tenant_id=tenant_id,
                )
            )
            if actual != person_ids:
                mismatches.append((cap_key, tenant_id, person_ids, actual))
        stats["organizations_imported"] = Organization.objects.count()
        stats["people_imported"] = Person.objects.count()
        stats["assignments_imported"] = Assignment.objects.count()
        stats["users_created"] = User.objects.count()
        stats["memberships"] = TenantMembership.objects.count()
        if mismatches:
            raise CommandError(f"Group membership mismatch: {mismatches}")
        if Organization.objects.count() != len(orgs) or Person.objects.count() != len(people):
            raise CommandError(f"UUID row-count mismatch: {stats}")
        self.stdout.write(self.style.SUCCESS(f"Import complete: {stats}"))
