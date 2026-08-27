from tests.conftest import make_org, make_person
from assignments.models import Assignment


def test_link_unlink_delete_assignment(as_editor):
    org = make_org()
    person = make_person()
    created = as_editor.post(
        f"/api/orgs/{org.id}/assignments",
        data={"job_title": "Chair"},
        content_type="application/json",
    )
    assert created.status_code == 200
    aid = created.json()["assignment"]["id"]
    linked = as_editor.post(
        f"/api/assignments/{aid}/person",
        data={"person_id": str(person.id)},
        content_type="application/json",
    )
    assert linked.status_code == 200
    assert linked.json()["assignment"]["person_id"] == str(person.id)
    busy = as_editor.delete(f"/api/assignments/{aid}")
    assert busy.status_code == 409
    unlinked = as_editor.delete(f"/api/assignments/{aid}/person")
    assert unlinked.status_code == 200
    deleted = as_editor.delete(f"/api/assignments/{aid}")
    assert deleted.status_code == 200
    assert not Assignment.objects.filter(id=aid).exists()


def test_patch_org(as_editor):
    org = make_org(name="Before")
    r = as_editor.patch(
        f"/api/orgs/{org.id}",
        data={"phone": "269-555-0100", "public_email": "org@example.test"},
        content_type="application/json",
    )
    assert r.status_code == 200
    org.refresh_from_db()
    assert org.phone == "269-555-0100"


def test_audit_revert_person(as_editor):
    p = make_person(name_first="Ada")
    patched = as_editor.patch(
        f"/api/people/{p.id}",
        data={"name_first": "Augusta"},
        content_type="application/json",
    )
    assert patched.status_code == 200
    audit_id = patched.json()["audit_id"]
    reverted = as_editor.post(f"/api/audit/{audit_id}/revert")
    assert reverted.status_code == 200
    p.refresh_from_db()
    assert p.name_first == "Ada"
