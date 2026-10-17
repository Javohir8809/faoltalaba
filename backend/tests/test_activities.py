from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

import pytest
from accounts import services as access
from accounts.models import Role, RoleGrant, ScopeType, User
from activities import services
from activities.models import Activity, ActivityRole, Lifecycle, Participant
from audit.models import AuditEvent
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.db.models.deletion import ProtectedError
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from organizations.models import Department, Faculty, Group
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient
from students.models import StudentProfile

pytestmark = pytest.mark.django_db
BASE = "/api/v1/activities/"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def world():
    faculty = Faculty.objects.create(name="One")
    other = Faculty.objects.create(name="Two")
    department = Department.objects.create(name="D1", faculty=faculty)
    other_department = Department.objects.create(name="D2", faculty=other)
    group = Group.objects.create(name="G1", faculty=faculty, hemis_id="g1")
    other_group = Group.objects.create(name="G2", faculty=other, hemis_id="g2")
    users = {}
    for name, role, scope, scope_id in [
        ("admin", Role.SUPERADMIN, ScopeType.GLOBAL, None),
        ("youth", Role.YOUTH_ADMIN, ScopeType.GLOBAL, None),
        ("faculty", Role.FACULTY_YOUTH_RESPONSIBLE, ScopeType.FACULTY, faculty.id),
        ("department", Role.DEPARTMENT_RESPONSIBLE, ScopeType.DEPARTMENT, department.id),
        ("student", Role.STUDENT, ScopeType.GLOBAL, None),
    ]:
        users[name] = User.objects.create_user(name)
        RoleGrant.objects.create(user=users[name], role=role, scope_type=scope, scope_id=scope_id)
    StudentProfile.objects.create(
        user=users["student"], faculty=faculty, department=department, group=group
    )
    return {
        **users,
        "f": faculty,
        "f2": other,
        "d": department,
        "d2": other_department,
        "g": group,
        "g2": other_group,
    }


def draft(world, **changes):
    values = {
        "title": "Faoliyat",
        "type": "EVENT",
        "faculty": world["f"],
        "department": world["d"],
        "venue": "Bino 1",
        "starts_at": timezone.now() + timedelta(hours=1),
        "ends_at": timezone.now() + timedelta(hours=2),
    }
    values.update(changes)
    return services.create_activity(actor=world["admin"], data=values)


def publish(world, **changes):
    activity = draft(world, **changes)
    services.transition_activity(
        actor=world["admin"], activity_id=activity.id, state=Lifecycle.PENDING_APPROVAL
    )
    return services.transition_activity(
        actor=world["admin"], activity_id=activity.id, state=Lifecycle.PUBLISHED
    )


@pytest.mark.parametrize("actor", ["admin", "youth", "faculty", "department"])
def test_authorized_staff_create_draft_and_publish(world, actor):
    data = {
        "title": "Yangi faoliyat",
        "type": "EVENT",
        "faculty": str(world["f"].id),
        "department": str(world["d"].id),
        "starts_at": (timezone.now() + timedelta(hours=1)).isoformat(),
        "ends_at": (timezone.now() + timedelta(hours=2)).isoformat(),
        "venue": "Zal",
    }
    client = client_for(world[actor])
    response = client.post(BASE, data, format="json")
    assert response.status_code == 201
    assert response.data["state"] == "DRAFT"
    assert str(response.data["organizer"]) == str(world[actor].id)
    path = BASE + str(response.data["id"]) + "/transitions/"
    assert client.post(path, {"state": "PENDING_APPROVAL"}, format="json").status_code == 200
    assert client.post(path, {"state": "PUBLISHED"}, format="json").status_code == 200
    assert AuditEvent.objects.filter(action="activity_transitioned").count() == 2


@pytest.mark.parametrize("actor", ["faculty", "department"])
def test_scope_isolation_create_list_detail_update(world, actor):
    own = draft(world)
    unrelated = draft(world, faculty=world["f2"], department=world["d2"])
    client = client_for(world[actor])
    listed = client.get(BASE)
    assert listed.status_code == 200 and listed.data["count"] == 1
    assert str(listed.data["results"][0]["id"]) == str(own.id)
    assert client.get(BASE + str(unrelated.id) + "/").status_code == 404
    assert (
        client.patch(BASE + str(unrelated.id) + "/", {"title": "No"}, format="json").status_code
        == 404
    )
    assert (
        client.post(
            BASE,
            {
                "title": "No",
                "type": "EVENT",
                "faculty": str(world["f2"].id),
                "department": str(world["d2"].id),
            },
            format="json",
        ).status_code
        == 403
    )


def test_anonymous_student_and_django_flags_never_grant_write(world):
    assert APIClient().get(BASE).status_code == 401
    flags = User.objects.create_user("flags", is_staff=True, is_superuser=True)
    for actor in [flags, world["student"]]:
        assert (
            client_for(actor)
            .post(BASE, {"title": "No", "type": "EVENT"}, format="json")
            .status_code
            == 403
        )
    activity = publish(world)
    client = client_for(world["student"])
    assert (
        client.patch(BASE + str(activity.id) + "/", {"title": "No"}, format="json").status_code
        == 403
    )
    assert client.delete(BASE + str(activity.id) + "/").status_code == 403
    assert client.get(BASE + str(activity.id) + "/roles/").status_code == 403


@pytest.mark.parametrize(
    "audience,field",
    [
        ("ALL_STUDENTS", None),
        ("FACULTY", "audience_faculty"),
        ("DEPARTMENT", "audience_department"),
        ("GROUP", "audience_group"),
    ],
)
def test_student_audience_discovery_and_source_status(world, audience, field):
    values = {"audience": audience}
    if field:
        key = {"FACULTY": "f", "DEPARTMENT": "d", "GROUP": "g"}[audience]
        values[field] = world[key]
        publish(world, **{**values, field: world[key + "2"]})
    shown = publish(world, **values)
    draft(world)
    publish(world, visibility="MANAGERS_ONLY")
    client = client_for(world["student"])
    response = client.get(BASE)
    assert response.data["count"] == 1
    assert str(response.data["results"][0]["id"]) == str(shown.id)
    StudentProfile.objects.filter(user=world["student"]).update(hemis_active=False)
    assert client.get(BASE).data["count"] == 0
    assert client.get(BASE + str(shown.id) + "/").status_code == 404


def test_student_requires_role_profile_and_active_affiliation(world):
    publish(world)
    client = client_for(world["student"])
    world["g"].hemis_active = False
    world["g"].save()
    assert client.get(BASE).data["count"] == 0
    world["g"].hemis_active = True
    world["g"].save()
    world["student"].role_grants.all().delete()
    assert client.get(BASE).data["count"] == 0


def test_jwt_create_publish_and_student_search_end_to_end(world):
    for name in ["admin", "student"]:
        world[name].set_password("Example-password!123")
        world[name].save()
    admin = APIClient()
    pair = admin.post(
        "/api/v1/auth/login/",
        {"username": "admin", "password": "Example-password!123"},
        format="json",
    )
    assert pair.status_code == 200
    admin.credentials(HTTP_AUTHORIZATION="Bearer " + pair.data["access"])
    result = admin.post(
        BASE,
        {
            "title": "Sport uchrashuvi",
            "type": "SPORT",
            "venue": "Zal",
            "starts_at": (timezone.now() + timedelta(hours=1)).isoformat(),
            "ends_at": (timezone.now() + timedelta(hours=2)).isoformat(),
        },
        format="json",
    )
    assert result.status_code == 201
    student = APIClient()
    pair = student.post(
        "/api/v1/auth/login/",
        {"username": "student", "password": "Example-password!123"},
        format="json",
    )
    student.credentials(HTTP_AUTHORIZATION="Bearer " + pair.data["access"])
    assert student.get(BASE).data["count"] == 0
    endpoint = BASE + str(result.data["id"]) + "/transitions/"
    for state in ["PENDING_APPROVAL", "PUBLISHED"]:
        assert admin.post(endpoint, {"state": state}, format="json").status_code == 200
    result = student.get(BASE + "?type=SPORT&search=Sport&ordering=title")
    assert result.data["count"] == 1 and result.data["results"][0]["title"] == "Sport uchrashuvi"
    assert student.get(BASE + "?type=CLUB").data["count"] == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("state", "PUBLISHED"),
        ("organizer", "00000000-0000-0000-0000-000000000000"),
        ("id", "00000000-0000-0000-0000-000000000000"),
        ("unknown", "value"),
        ("type", "CLUB"),
        ("faculty", None),
        ("department", None),
    ],
)
def test_immutable_or_unknown_fields_rejected(world, field, value):
    activity = draft(world)
    response = client_for(world["admin"]).patch(
        BASE + str(activity.id) + "/", {field: value}, format="json"
    )
    assert response.status_code == 400
    activity.refresh_from_db()
    assert activity.state == Lifecycle.DRAFT and activity.type == "EVENT"


@pytest.mark.parametrize(
    "changes",
    [
        {"capacity": 0},
        {"title": ""},
        {"starts_at": None},
        {"ends_at": timezone.now() - timedelta(days=1)},
        {"audience": "FACULTY"},
    ],
)
def test_invalid_draft_data_does_not_mutate_existing(world, changes):
    activity = draft(world)
    with pytest.raises(ValidationError):
        services.update_activity(actor=world["admin"], activity_id=activity.id, data=changes)
    activity.refresh_from_db()
    assert activity.title == "Faoliyat" and activity.capacity is None


def test_cross_faculty_owner_and_naive_dates_rejected(world):
    with pytest.raises(ValidationError):
        draft(world, department=world["d2"])
    now = timezone.now().replace(tzinfo=None)
    with pytest.raises(ValidationError):
        draft(world, starts_at=now, ends_at=now + timedelta(hours=1))


def test_invalid_lifecycle_and_publication_requirements(world):
    activity = draft(world, starts_at=None, ends_at=None, venue="")
    with pytest.raises(ValidationError):
        services.transition_activity(actor=world["admin"], activity_id=activity.id, state="ACTIVE")
    services.transition_activity(
        actor=world["admin"], activity_id=activity.id, state="PENDING_APPROVAL"
    )
    with pytest.raises(ValidationError):
        services.transition_activity(
            actor=world["admin"], activity_id=activity.id, state="PUBLISHED"
        )
    activity.refresh_from_db()
    assert activity.state == "PENDING_APPROVAL" and activity.published_at is None


def test_registration_active_completion_time_gates(world):
    activity = publish(world, registration_policy="OPEN")
    services.transition_activity(
        actor=world["admin"], activity_id=activity.id, state="REGISTRATION_OPEN"
    )
    with pytest.raises(ValidationError):
        services.transition_activity(actor=world["admin"], activity_id=activity.id, state="ACTIVE")
    with patch("activities.services.timezone.now", return_value=activity.starts_at):
        services.transition_activity(actor=world["admin"], activity_id=activity.id, state="ACTIVE")
        with pytest.raises(ValidationError):
            services.transition_activity(
                actor=world["admin"], activity_id=activity.id, state="COMPLETED"
            )
    with patch("activities.services.timezone.now", return_value=activity.ends_at):
        services.transition_activity(
            actor=world["admin"], activity_id=activity.id, state="COMPLETED"
        )
    services.archive_activity(actor=world["admin"], activity_id=activity.id)
    with pytest.raises(ValidationError):
        services.transition_activity(actor=world["admin"], activity_id=activity.id, state="DRAFT")


def test_no_registration_without_policy_and_no_edit_after_publication(world):
    activity = publish(world)
    with pytest.raises(ValidationError):
        services.transition_activity(
            actor=world["admin"], activity_id=activity.id, state="REGISTRATION_OPEN"
        )
    assert (
        client_for(world["admin"])
        .patch(BASE + str(activity.id) + "/", {"title": "Cannot"}, format="json")
        .status_code
        == 400
    )


def test_delete_archives_and_preserves_participant_history(world):
    activity = draft(world)
    Participant.objects.create(activity=activity, student=world["student"].student_profile)
    client = client_for(world["admin"])
    assert client.delete(BASE + str(activity.id) + "/").status_code == 204
    assert client.delete(BASE + str(activity.id) + "/").status_code == 204
    activity.refresh_from_db()
    assert activity.state == "ARCHIVED" and Participant.objects.count() == 1
    assert (
        AuditEvent.objects.filter(action="activity_transitioned", object_id=activity.id).count()
        == 1
    )
    with pytest.raises(ProtectedError):
        activity.delete()
    assert client.delete(BASE + str(publish(world).id) + "/").status_code == 400


def test_activity_assignment_grant_revoke_and_review_isolation(world):
    activity = draft(world, type="CLUB")
    leader = User.objects.create_user("leader")
    client = client_for(world["admin"])
    path = f"/api/v1/admin/users/{leader.id}/roles/"
    result = client.post(
        path,
        {"role": "CLUB_LEADER", "scope_type": "ACTIVITY", "scope_id": str(activity.id)},
        format="json",
    )
    assert result.status_code == 201
    assert str(ActivityRole.objects.get().grant_id) == str(result.data["id"])
    leader_client = client_for(leader)
    detail = BASE + str(activity.id) + "/"
    assert leader_client.patch(detail, {"title": "Leader draft"}, format="json").status_code == 200
    assert (
        leader_client.post(
            detail + "transitions/", {"state": "PENDING_APPROVAL"}, format="json"
        ).status_code
        == 200
    )
    assert (
        leader_client.post(
            detail + "transitions/", {"state": "PUBLISHED"}, format="json"
        ).status_code
        == 403
    )
    assert (
        leader_client.post(BASE, {"title": "New", "type": "CLUB"}, format="json").status_code == 403
    )
    assert leader_client.get(detail + "roles/").data["count"] == 1
    assert client.delete(path + str(result.data["id"]) + "/").status_code == 204
    assert not ActivityRole.objects.exists()
    assert leader_client.get(detail).status_code == 404


def test_club_leader_wrong_type_and_scoped_grant_audit_rollback(world):
    activity = draft(world)
    target = User.objects.create_user("target")
    with pytest.raises(ValidationError):
        access.grant_role(
            actor=world["admin"],
            target=target,
            role=Role.CLUB_LEADER,
            scope_type=ScopeType.ACTIVITY,
            scope_id=activity.id,
        )
    with patch("accounts.services.record_event", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            access.grant_role(
                actor=world["admin"],
                target=target,
                role=Role.ACTIVITY_RESPONSIBLE,
                scope_type=ScopeType.ACTIVITY,
                scope_id=activity.id,
            )
    assert not ActivityRole.objects.exists() and not target.role_grants.exists()


def test_activity_update_audit_failure_rolls_back(world):
    activity = draft(world)
    with patch("activities.services.record_event", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            services.update_activity(
                actor=world["admin"], activity_id=activity.id, data={"title": "Rollback"}
            )
    activity.refresh_from_db()
    assert activity.title == "Faoliyat"


def test_create_and_transition_audit_failures_roll_back(world):
    with patch("activities.services.record_event", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            draft(world)
    assert not Activity.objects.exists()
    activity = draft(world)
    with patch("activities.services.record_event", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            services.transition_activity(
                actor=world["admin"], activity_id=activity.id, state="PENDING_APPROVAL"
            )
    activity.refresh_from_db()
    assert activity.state == "DRAFT"


def test_suspension_hides_discovery_resume_preserves_first_publication(world):
    activity = publish(world)
    first_publication = activity.published_at
    student = client_for(world["student"])
    services.transition_activity(actor=world["admin"], activity_id=activity.id, state="SUSPENDED")
    assert student.get(BASE).data["count"] == 0
    activity = services.transition_activity(
        actor=world["admin"], activity_id=activity.id, state="PUBLISHED"
    )
    assert activity.published_at == first_publication
    assert student.get(BASE).data["count"] == 1
    services.transition_activity(actor=world["admin"], activity_id=activity.id, state="CANCELLED")
    assert student.get(BASE).data["results"][0]["state"] == "CANCELLED"


def test_rejection_resubmission_and_unpublished_cancellation(world):
    activity = draft(world)
    for state in ["PENDING_APPROVAL", "REJECTED"]:
        services.transition_activity(actor=world["admin"], activity_id=activity.id, state=state)
    services.update_activity(
        actor=world["admin"], activity_id=activity.id, data={"title": "Corrected"}
    )
    for state in ["DRAFT", "PENDING_APPROVAL", "CANCELLED"]:
        services.transition_activity(actor=world["admin"], activity_id=activity.id, state=state)
    assert client_for(world["student"]).get(BASE).data["count"] == 0


def test_organizer_provenance_does_not_bypass_revoked_authority(world):
    activity = services.create_activity(
        actor=world["faculty"], data={"title": "Owned", "type": "EVENT", "faculty": world["f"]}
    )
    grant = world["faculty"].role_grants.get()
    access.revoke_role(actor=world["admin"], grant=grant)
    assert client_for(world["faculty"]).get(BASE + str(activity.id) + "/").status_code == 404
    with pytest.raises(PermissionDenied):
        services.update_activity(
            actor=world["faculty"], activity_id=activity.id, data={"title": "No"}
        )


def test_db_participant_enum_duplicate_and_capacity_constraints(world):
    activity = draft(world)
    Participant.objects.create(activity=activity, student=world["student"].student_profile)
    with pytest.raises(IntegrityError), transaction.atomic():
        Participant.objects.create(activity=activity, student=world["student"].student_profile)
    for changes in [{"state": "BAD"}, {"capacity": 0}, {"audience": "GROUP"}]:
        with pytest.raises(IntegrityError), transaction.atomic():
            Activity.objects.filter(pk=activity.id).update(**changes)
    with pytest.raises(IntegrityError), transaction.atomic():
        Participant.objects.update(state="BAD")


def test_catalog_query_count_does_not_grow_per_activity(world):
    publish(world)
    client = client_for(world["student"])
    with CaptureQueriesContext(connection) as one:
        assert client.get(BASE).status_code == 200
    for _ in range(8):
        publish(world)
    with CaptureQueriesContext(connection) as many:
        response = client.get(BASE)
    assert response.data["count"] == 9
    assert len(many) == len(one) and len(many) <= 10


@pytest.mark.django_db(transaction=True)
def test_concurrent_publication_has_one_audited_transition(world):
    activity = draft(world)
    services.transition_activity(
        actor=world["admin"], activity_id=activity.id, state="PENDING_APPROVAL"
    )
    barrier = Barrier(2)

    def publish_once():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                services.transition_activity(
                    actor=world["admin"], activity_id=activity.id, state="PUBLISHED"
                )
                return "published"
            except ValidationError:
                return "rejected"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: publish_once(), range(2)))
    assert sorted(results) == ["published", "rejected"]
    assert (
        AuditEvent.objects.filter(
            object_id=activity.id, action="activity_transitioned", metadata__to_state="PUBLISHED"
        ).count()
        == 1
    )
