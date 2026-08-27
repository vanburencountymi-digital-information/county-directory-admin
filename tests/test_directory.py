from tests.conftest import make_org, make_person
from assignments.models import Assignment


def test_list_orgs(as_editor):
    make_org(name="Clerk")
    r = as_editor.get("/api/orgs")
    assert r.status_code == 200
    assert any(i["name"] == "Clerk" for i in r.json()["items"])


def test_create_org(as_editor):
    r = as_editor.post(
        "/api/orgs",
        data={"name": "Planning", "org_type": "department"},
        content_type="application/json",
    )
    assert r.status_code == 200
    assert r.json()["organization"]["slug"]


def test_patch_person_name_does_not_call_wordpress(as_editor, monkeypatch):
    p = make_person()
    called = []

    def boom(*a, **k):
        called.append(1)
        raise AssertionError("should not push")

    monkeypatch.setattr("people.api.try_push_person_to_wordpress", boom)
    r = as_editor.patch(
        f"/api/people/{p.id}",
        data={"name_first": "Updated"},
        content_type="application/json",
    )
    assert r.status_code == 200
    assert called == []
    p.refresh_from_db()
    assert p.name_first == "Updated"
    assert p.full_name.startswith("Updated")


def test_show_in_directory_calls_wordpress(as_editor, monkeypatch):
    p = make_person(show_in_directory=True)
    called = []

    def fake(tenant_id, person_id):
        called.append((str(tenant_id), str(person_id)))

    monkeypatch.setattr("people.api.try_push_person_to_wordpress", fake)
    r = as_editor.patch(
        f"/api/people/{p.id}",
        data={"show_in_directory": False},
        content_type="application/json",
    )
    assert r.status_code == 200
    assert called == [("VBC", str(p.id))]


def test_archive_calls_wordpress(as_editor, monkeypatch):
    p = make_person()
    org = make_org()
    Assignment.objects.create(tenant_id="VBC", org=org, person=p)
    called = []
    monkeypatch.setattr(
        "people.api.try_push_person_to_wordpress",
        lambda t, i: called.append(str(i)),
    )
    r = as_editor.delete(f"/api/people/{p.id}")
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.archived_at is not None
    assert Assignment.objects.get(org=org).person_id is None
    assert called == [str(p.id)]


def test_create_person_and_list(as_editor):
    r = as_editor.post(
        "/api/people",
        data={"name_first": "Bo", "name_last": "Clerk", "email_public": "bo@example.test"},
        content_type="application/json",
    )
    assert r.status_code == 200
    listed = as_editor.get("/api/people")
    assert listed.json()["total"] >= 1


def test_open_assignment(as_editor):
    org = make_org()
    r = as_editor.post(
        f"/api/orgs/{org.id}/assignments",
        data={"job_title": "Chair", "seat_no": 1},
        content_type="application/json",
    )
    assert r.status_code == 200
    open_r = as_editor.get("/api/assignments/open")
    assert len(open_r.json()["items"]) == 1


def test_print_directory(as_editor):
    org = make_org(name="Admin")
    p = make_person(show_in_directory=True)
    Assignment.objects.create(tenant_id="VBC", org=org, person=p, job_title="Clerk")
    r = as_editor.get("/api/directory/print")
    assert r.status_code == 200
    assert r.json()[0]["department"] == "Admin"
    assert r.json()[0]["entries"][0]["title"] == "Clerk"
