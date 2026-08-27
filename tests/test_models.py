import pytest
from django.db import IntegrityError

from accounts.models import User
from accounts.services import upgrade_person_to_user
from organizations.models import Organization, hierarchy_family
from organizations.services import validate_org_parent
from ninja.errors import HttpError
from people.models import Person, derive_full_name
from tests.conftest import make_org, make_person
from assignments.models import Assignment


def test_full_name_derivation():
    assert derive_full_name("Ada", "Lovelace") == "Ada Lovelace"
    assert derive_full_name("Ada", "Lovelace", "Ada L.") == "Ada L."
    assert derive_full_name("", "", None) == ""


@pytest.mark.django_db
def test_person_save_sets_full_name():
    p = make_person(name_first="Grace", name_last="Hopper", full_name="")
    p.refresh_from_db()
    assert p.full_name == "Grace Hopper"


@pytest.mark.django_db
def test_user_requires_person(person):
    user = upgrade_person_to_user(person)
    assert user.person_id == person.id
    assert upgrade_person_to_user(person).id == user.id


@pytest.mark.django_db
def test_upgrade_requires_email():
    p = make_person(email_public="")
    with pytest.raises(ValueError):
        upgrade_person_to_user(p)


@pytest.mark.django_db
def test_user_protects_person(person):
    upgrade_person_to_user(person)
    with pytest.raises(Exception):
        person.delete()


@pytest.mark.django_db
def test_org_uniqueness_allows_same_name_different_type():
    make_org(name="Board of Commissioners", org_type="department", slug="boc")
    make_org(name="Board of Commissioners", org_type="board", slug="boc")
    assert Organization.objects.filter(name="Board of Commissioners").count() == 2


@pytest.mark.django_db
def test_vacant_seats_do_not_collide():
    org = make_org()
    Assignment.objects.create(tenant_id="VBC", org=org, seat_no=1)
    Assignment.objects.create(tenant_id="VBC", org=org, seat_no=1)
    assert Assignment.objects.filter(org=org, person__isnull=True).count() == 2


@pytest.mark.django_db
def test_hierarchy_family():
    assert hierarchy_family("board") == "board"
    assert hierarchy_family("department") == "department"
    assert hierarchy_family("authority") == "board"


@pytest.mark.django_db
def test_parent_cycle_rejected():
    a = make_org(name="A", slug="a")
    b = make_org(name="B", slug="b", parent=a)
    with pytest.raises(HttpError):
        validate_org_parent(tenant_id="VBC", org_id=a.id, parent_id=b.id, child_org_type="department")
