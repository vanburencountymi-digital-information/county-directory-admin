from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.management.commands import import_from_db_dice as etl
from assignments.models import Assignment
from organizations.models import Organization
from people.models import Person


class FakeCursor:
    def __init__(self, tables):
        self.tables = tables
        self.description = []
        self._rows = []

    def execute(self, sql):
        text = " ".join(sql.split()).lower()
        if "core.organizations" in text:
            cols, rows = self.tables["organizations"]
        elif "core.people" in text and "people_caps" not in text:
            cols, rows = self.tables["people"]
        elif "core.assignments" in text:
            cols, rows = self.tables["assignments"]
        elif "from core.caps" in text:
            cols, rows = self.tables["caps"]
        elif "people_caps" in text:
            cols, rows = self.tables["people_caps"]
        else:
            raise AssertionError(f"unexpected sql: {sql}")
        self.description = [(c,) for c in cols]
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeHandler:
    databases = {"source": {}}

    def __init__(self, cursor):
        self._cursor = cursor

    def __getitem__(self, alias):
        @contextmanager
        def cursor():
            yield self._cursor

        class Conn:
            def cursor(_self):
                return cursor()

        return Conn()


@pytest.mark.django_db
def test_import_from_db_dice_preserves_uuids_and_caps(monkeypatch):
    org_id = uuid4()
    person_id = uuid4()
    asg_id = uuid4()
    cap_id = uuid4()
    now = datetime.now(timezone.utc)
    tables = {
        "organizations": (
            [
                "id",
                "tenant_id",
                "org_type",
                "name",
                "slug",
                "public_email",
                "phone",
                "website_url",
                "hours_text",
                "archived_at",
                "created_at",
                "department_id",
                "parent_department_id",
                "address_mailing",
                "address_physical",
                "additional_information",
                "fax",
                "parent_id",
            ],
            [
                (
                    org_id,
                    "VBC",
                    "department",
                    "Clerk",
                    "clerk",
                    None,
                    None,
                    None,
                    None,
                    None,
                    now,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
            ],
        ),
        "people": (
            [
                "id",
                "tenant_id",
                "employee_id",
                "name_first",
                "name_middle",
                "name_last",
                "name_suffix",
                "full_name",
                "email_public",
                "phone_public",
                "phone_public_ext",
                "job_title",
                "person_key",
                "role",
                "show_in_directory",
                "archived_at",
                "created_at",
            ],
            [
                (
                    person_id,
                    "VBC",
                    None,
                    "Ada",
                    None,
                    "Lovelace",
                    None,
                    "Ada L.",
                    "ada-etl@example.test",
                    None,
                    None,
                    None,
                    None,
                    None,
                    True,
                    None,
                    now,
                )
            ],
        ),
        "assignments": (
            [
                "id",
                "tenant_id",
                "person_id",
                "org_id",
                "seat_no",
                "status",
                "job_title",
                "created_at",
                "receives_financial_reports",
            ],
            [(asg_id, "VBC", person_id, org_id, 1, None, "Clerk", None, None)],
        ),
        "caps": (["cap_key", "id"], [("directory_editor", cap_id)]),
        "people_caps": (
            ["person_id", "cap_id", "tenant_id"],
            [(person_id, cap_id, "VBC")],
        ),
    }
    handler = FakeHandler(FakeCursor(tables))
    monkeypatch.setattr(etl, "connections", handler)
    call_command("import_from_db_dice")
    assert Organization.objects.get(id=org_id).name == "Clerk"
    person = Person.objects.get(id=person_id)
    assert person.email_public == "ada-etl@example.test"
    assert person.show_in_directory is True
    assert person.display_name == "Ada L."
    assert person.full_name == "Ada L."
    assert Assignment.objects.get(id=asg_id).org_id == org_id
    assert person.user.groups.filter(name="directory_editor").exists()
    assert person.user.tenant_memberships.filter(tenant_id="VBC").exists()


@pytest.mark.django_db
def test_import_dry_run_does_not_write(monkeypatch):
    tables = {
        "organizations": (["id"], []),
        "people": (["id"], []),
        "assignments": (["id"], []),
        "caps": (["cap_key", "id"], []),
        "people_caps": (["person_id", "cap_id", "tenant_id"], []),
    }
    monkeypatch.setattr(etl, "connections", FakeHandler(FakeCursor(tables)))
    call_command("import_from_db_dice", dry_run=True)
    assert Organization.objects.count() == 0


def test_import_requires_source_alias():
    with pytest.raises(CommandError):
        call_command("import_from_db_dice", source_alias="missing")
