from django.contrib.auth.models import Group

from accounts.groups import seed_groups
from accounts.models import TenantMembership, User
from accounts.services import grant_directory_group
from tests.conftest import make_person


def test_caps_etl_equivalence(db):
    seed_groups()
    p1 = make_person(email_public="ed1@example.test")
    p2 = make_person(email_public="ed2@example.test")
    grant_directory_group(p1, "directory_editor", "VBC")
    grant_directory_group(p2, "directory_editor", "VBC")
    grant_directory_group(p1, "permissions_admin", "VBC")
    group = Group.objects.get(name="directory_editor")
    actual = set(
        str(u.person_id)
        for u in User.objects.filter(groups=group, tenant_memberships__tenant_id="VBC")
    )
    assert actual == {str(p1.id), str(p2.id)}
    assert TenantMembership.objects.filter(tenant_id="VBC").count() == 2
