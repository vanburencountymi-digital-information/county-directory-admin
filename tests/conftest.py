from pathlib import Path
from uuid import uuid4

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.groups import seed_groups
from accounts.models import MagicLinkToken, TenantMembership
from accounts.services import grant_directory_group, upgrade_person_to_user
from assignments.models import Assignment
from organizations.models import Organization
from people.models import Person

User = get_user_model()


@pytest.fixture(scope="session", autouse=True)
def _staticfiles_dir():
    Path(settings.STATIC_ROOT).mkdir(parents=True, exist_ok=True)


@pytest.fixture(autouse=True)
def _groups(db):
    seed_groups()


@pytest.fixture
def tenant():
    return "VBC"


@pytest.fixture
def person(db, tenant):
    return Person.objects.create(
        tenant_id=tenant,
        name_first="Ada",
        name_last="Lovelace",
        email_public="ada@example.test",
        show_in_directory=True,
    )


@pytest.fixture
def editor(db, person, tenant):
    user = grant_directory_group(person, settings.GROUP_DIRECTORY_EDITOR, tenant)
    return user


@pytest.fixture
def client():
    from django.test import Client

    return Client(enforce_csrf_checks=False)


@pytest.fixture
def as_editor(client, editor):
    client.force_login(editor, backend="django.contrib.auth.backends.ModelBackend")
    session = client.session
    session["active_tenant_id"] = "VBC"
    session.save()
    return client


def make_org(tenant="VBC", **kwargs):
    defaults = {
        "tenant_id": tenant,
        "name": kwargs.pop("name", f"Org {uuid4().hex[:6]}"),
        "org_type": kwargs.pop("org_type", "department"),
        "slug": kwargs.pop("slug", f"org-{uuid4().hex[:8]}"),
    }
    defaults.update(kwargs)
    return Organization.objects.create(**defaults)


def make_person(tenant="VBC", **kwargs):
    defaults = {
        "tenant_id": tenant,
        "name_first": "Pat",
        "name_last": "Person",
        "email_public": f"p-{uuid4().hex[:8]}@example.test",
        "show_in_directory": True,
    }
    defaults.update(kwargs)
    return Person.objects.create(**defaults)
