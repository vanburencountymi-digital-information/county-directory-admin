from django.contrib.auth.models import Group
from django.db import transaction

from .models import TenantMembership, User


def upgrade_person_to_user(person) -> User:
    """Create a User for this Person if one does not exist yet.

    Email is mirrored from person.email_public. Call this before adding the
    person to a Group in the grant-access admin flow.
    """
    existing = User.objects.filter(person=person).first()
    if existing:
        return existing
    email = (person.email_public or "").strip().lower()
    if not email:
        raise ValueError("Person must have email_public before they can become a User")
    other = User.objects.filter(email=email).first()
    if other:
        if other.person_id == person.id:
            return other
        raise ValueError(f"A user with email {email} already exists")
    with transaction.atomic():
        user = User.objects.create_user(email=email, person=person)
    return user


def ensure_tenant_membership(user: User, tenant_id: str) -> TenantMembership:
    membership, _ = TenantMembership.objects.get_or_create(user=user, tenant_id=tenant_id)
    return membership


def grant_directory_group(person, group_name: str, tenant_id: str) -> User:
    user = upgrade_person_to_user(person)
    group = Group.objects.get(name=group_name)
    user.groups.add(group)
    ensure_tenant_membership(user, tenant_id)
    return user
