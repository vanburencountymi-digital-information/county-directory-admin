from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


def seed_groups():
    """Create directory_editor and permissions_admin Groups with model perms."""
    editor, _ = Group.objects.get_or_create(name=settings.GROUP_DIRECTORY_EDITOR)
    admin, _ = Group.objects.get_or_create(name=settings.GROUP_PERMISSIONS_ADMIN)

    def perms_for(app_label, model, codenames):
        ct = ContentType.objects.get_for_model(apps.get_model(app_label, model))
        return list(
            Permission.objects.filter(content_type=ct, codename__in=codenames)
        )

    editor_perms = []
    editor_perms += perms_for("people", "Person", ["add_person", "change_person", "delete_person", "view_person", "trigger_wordpress_sync"])
    editor_perms += perms_for("organizations", "Organization", ["add_organization", "change_organization", "delete_organization", "view_organization"])
    editor_perms += perms_for("assignments", "Assignment", ["add_assignment", "change_assignment", "delete_assignment", "view_assignment"])
    editor_perms += perms_for("audit", "AuditLog", ["view_auditlog", "revert_auditlog"])
    editor.permissions.set(editor_perms)

    admin_perms = list(editor_perms)
    admin_perms += perms_for("accounts", "User", ["manage_directory_access", "view_user", "change_user"])
    admin.permissions.set(admin_perms)
    return editor, admin
