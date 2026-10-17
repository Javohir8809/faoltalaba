from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from accounts.models import Role, RoleGrant, ScopeType, User
from activities import services as activity_services
from activities.models import Activity, ActivityRole, Participant
from audit.models import AuditEvent
from clubs import memberships, services, sessions
from clubs.models import Club, ClubMembership, ClubSchedule, ClubSession
from clubs.queries import visible_clubs
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from organizations.models import Faculty
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient
from students.models import StudentProfile

pytestmark = pytest.mark.django_db
BASE = "/api/v1/clubs/"


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def world():
    f1 = Faculty.objects.create(name="Faculty 1")
    f2 = Faculty.objects.create(name="Faculty 2")
    users = {}
    for name, role, scope, scope_id in [
        ("admin", Role.SUPERADMIN, ScopeType.GLOBAL, None),
        ("youth", Role.YOUTH_ADMIN, ScopeType.GLOBAL, None),
        ("faculty", Role.FACULTY_YOUTH_RESPONSIBLE, ScopeType.FACULTY, f1.id),
        ("other_manager", Role.FACULTY_YOUTH_RESPONSIBLE, ScopeType.FACULTY, f2.id),
        ("student", Role.STUDENT, ScopeType.GLOBAL, None),
        ("student2", Role.STUDENT, ScopeType.GLOBAL, None),
        ("outsider", Role.STUDENT, ScopeType.GLOBAL, None),
    ]:
        users[name] = User.objects.create_user(name)
        RoleGrant.objects.create(user=users[name], role=role, scope_type=scope, scope_id=scope_id)
    for name, faculty in [("student", f1), ("student2", f1), ("outsider", f2)]:
        StudentProfile.objects.create(
            user=users[name], faculty=faculty, full_name="Synthetic " + name
        )
    users["leader"] = User.objects.create_user("leader")
    return {**users, "f1": f1, "f2": f2}


def make_club(world, *, published=True, **changes):
    now = timezone.now()
    data = {
        "title": "Namuna to'garak",
        "faculty": world["f1"],
        "audience": "FACULTY",
        "audience_faculty": world["f1"],
        "registration_policy": "APPROVAL",
        "starts_at": now - timedelta(days=1),
        "ends_at": now + timedelta(days=60),
        "venue": "Bino 1",
        "capacity": 10,
    }
    data.update(changes)
    club = services.create_club(actor=world["admin"], activity=data)
    if published:
        for state in ["PENDING_APPROVAL", "PUBLISHED"]:
            activity_services.transition_activity(
                actor=world["admin"], activity_id=club.pk, state=state
            )
    club.refresh_from_db()
    return club


def make_session(world, club, **changes):
    now = timezone.now()
    data = {
        "starts_at": now - timedelta(minutes=1),
        "ends_at": now + timedelta(hours=1),
        "idempotency_key": uuid4(),
    }
    data.update(changes)
    return sessions.create_session(actor=world["admin"], club_id=club.pk, **data)


def test_create_edit_schedule_and_publish_api(world):
    client = client_for(world["faculty"])
    response = client.post(
        BASE,
        {
            "activity": {
                "title": "Club",
                "faculty": str(world["f1"].id),
                "registration_policy": "OPEN",
                "starts_at": (timezone.now() + timedelta(hours=1)).isoformat(),
                "ends_at": (timezone.now() + timedelta(days=30)).isoformat(),
                "venue": "Room",
            }
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["activity"]["type"] == "CLUB"
    detail = BASE + str(response.data["id"]) + "/"
    assert (
        client.patch(detail, {"timezone_name": "Asia/Tashkent"}, format="json").status_code == 200
    )
    assert client.patch(detail, {"timezone_name": "invalid-zone"}, format="json").status_code == 400
    assert (
        client.put(
            detail + "schedule/",
            {"slots": [{"weekday": 2, "starts_at": "14:00", "ends_at": "15:00"}]},
            format="json",
        ).status_code
        == 200
    )
    first_id = client.get(detail + "schedule/").data[0]["id"]
    assert (
        client.put(
            detail + "schedule/",
            {"slots": [{"weekday": 2, "starts_at": "14:00", "ends_at": "15:00"}]},
            format="json",
        ).data[0]["id"]
        == first_id
    )
    for state in ["PENDING_APPROVAL", "PUBLISHED"]:
        assert (
            client.post(
                "/api/v1/activities/" + str(response.data["id"]) + "/transitions/",
                {"state": state},
                format="json",
            ).status_code
            == 200
        )
    assert client.put(detail + "schedule/", {"slots": []}, format="json").status_code == 400
    assert client_for(world["student"]).get(detail).status_code == 200


def test_auto_join_retry_leave_and_rejoin_share_participant(world):
    club = make_club(world, registration_policy="OPEN")
    client = client_for(world["student"])
    path = BASE + str(club.pk) + "/membership/"
    first = client.post(path, {}, format="json")
    assert first.status_code == 200 and first.data["status"] == "ACTIVE"
    retry = client.post(path, {}, format="json")
    assert retry.data["id"] == first.data["id"]
    assert Participant.objects.count() == ClubMembership.objects.count() == 1
    assert client.delete(path).status_code == 204
    assert Participant.objects.get().state == "CANCELLED"
    assert client.post(path, {}, format="json").data["id"] == first.data["id"]
    assert Participant.objects.get().state == "ACTIVE"


def test_manual_join_approval_and_eligibility(world):
    club = make_club(world)
    services.assign_leader(actor=world["faculty"], club_id=club.pk, user_id=world["leader"].id)
    membership = memberships.join_club(actor=world["student"], club_id=club.pk)
    assert membership.status == "PENDING" and membership.participant.state == "PENDING"
    session = make_session(world, club)
    sessions.change_session(
        actor=world["leader"], club_id=club.pk, session_id=session.id, opening=True
    )
    assert not sessions.eligible_for_attendance(session=session, student=world["student"])
    memberships.decide_membership(
        actor=world["leader"], club_id=club.pk, membership_id=membership.pk, decision="APPROVE"
    )
    assert sessions.eligible_for_attendance(session=session, student=world["student"])
    StudentProfile.objects.filter(user=world["student"]).update(hemis_active=False)
    assert not sessions.eligible_for_attendance(session=session, student=world["student"])
    StudentProfile.objects.filter(user=world["student"]).update(hemis_active=True)
    assert sessions.eligible_for_attendance(session=session, student=world["student"])
    memberships.leave_club(actor=world["student"], club_id=club.pk)
    assert not sessions.eligible_for_attendance(session=session, student=world["student"])


def test_reject_reason_required_and_no_reapply_bypass(world):
    club = make_club(world)
    member = memberships.join_club(actor=world["student"], club_id=club.pk)
    with pytest.raises(ValidationError):
        memberships.decide_membership(
            actor=world["admin"], club_id=club.pk, membership_id=member.pk, decision="REJECT"
        )
    memberships.decide_membership(
        actor=world["admin"],
        club_id=club.pk,
        membership_id=member.pk,
        decision="REJECT",
        reason="Namuna sabab",
    )
    assert Participant.objects.get().state == "CANCELLED"
    memberships.leave_club(actor=world["student"], club_id=club.pk)
    with pytest.raises(ValidationError):
        memberships.join_club(actor=world["student"], club_id=club.pk)


def test_capacity_checked_on_approval_not_pending(world):
    club = make_club(world, capacity=1)
    first = memberships.join_club(actor=world["student"], club_id=club.pk)
    second = memberships.join_club(actor=world["student2"], club_id=club.pk)
    memberships.decide_membership(
        actor=world["admin"], club_id=club.pk, membership_id=first.pk, decision="APPROVE"
    )
    with pytest.raises(ValidationError):
        memberships.decide_membership(
            actor=world["admin"], club_id=club.pk, membership_id=second.pk, decision="APPROVE"
        )
    second.refresh_from_db()
    assert second.status == "PENDING"
    memberships.leave_club(actor=world["student"], club_id=club.pk)
    memberships.decide_membership(
        actor=world["admin"], club_id=club.pk, membership_id=second.pk, decision="APPROVE"
    )


@pytest.mark.parametrize("mode", ["draft", "closed", "none", "audience"])
def test_join_denied_for_nonoperational_or_ineligible(world, mode):
    club = make_club(
        world, published=mode != "draft", registration_policy="NONE" if mode == "none" else "OPEN"
    )
    if mode == "closed":
        activity_services.transition_activity(
            actor=world["admin"], activity_id=club.pk, state="CANCELLED"
        )
    actor = world["outsider"] if mode == "audience" else world["student"]
    with pytest.raises((ValidationError, PermissionDenied)):
        memberships.join_club(actor=actor, club_id=club.pk)
    assert not ClubMembership.objects.exists()


def test_own_membership_leave_survives_hidden_club(world):
    club = make_club(world, registration_policy="OPEN")
    memberships.join_club(actor=world["student"], club_id=club.pk)
    activity_services.transition_activity(
        actor=world["admin"], activity_id=club.pk, state="SUSPENDED"
    )
    client = client_for(world["student"])
    root = BASE + str(club.pk) + "/"
    assert client.get(root).status_code == 404
    assert client.get(root + "membership/").status_code == 200
    assert client.delete(root + "membership/").status_code == 204


def test_student_and_cross_scope_roster_analytics_decisions_denied(world):
    club = make_club(world)
    member = memberships.join_club(actor=world["student"], club_id=club.pk)
    for actor in [world["student"], world["outsider"], world["other_manager"]]:
        client = client_for(actor)
        for route in ["members/", "analytics/"]:
            assert client.get(BASE + str(club.pk) + "/" + route).status_code in {403, 404}
        assert client.post(
            BASE + str(club.pk) + f"/members/{member.pk}/decision/",
            {"decision": "APPROVE"},
            format="json",
        ).status_code in {403, 404}
    assert (
        client_for(world["student2"]).get(BASE + str(club.pk) + "/membership/").status_code == 404
    )
    assert APIClient().get(BASE).status_code == 401


def test_scoped_leader_delegation_cannot_escalate_or_cross_club(world):
    club = make_club(world)
    other = make_club(world, faculty=world["f2"], audience_faculty=world["f2"])
    client = client_for(world["faculty"])
    path = BASE + str(club.pk) + "/leaders/"
    result = client.post(path, {"user_id": str(world["leader"].id)}, format="json")
    assert result.status_code == 200
    assert (
        client.post(path, {"user_id": str(world["leader"].id)}, format="json").data["id"]
        == result.data["id"]
    )
    assert ActivityRole.objects.count() == 1
    assert (
        client.post(
            path, {"user_id": str(world["leader"].id), "role": "SUPERADMIN"}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.post(
            BASE + str(other.pk) + "/leaders/", {"user_id": str(world["leader"].id)}, format="json"
        ).status_code
        == 404
    )
    leader = client_for(world["leader"])
    assert (
        leader.post(path, {"user_id": str(world["student"].id)}, format="json").status_code == 403
    )
    assert (
        leader.post(
            "/api/v1/admin/users/" + str(world["student"].id) + "/roles/",
            {"role": "SUPERADMIN", "scope_type": "GLOBAL"},
            format="json",
        ).status_code
        == 403
    )
    assert client.delete(path + str(result.data["id"]) + "/").status_code == 204
    assert leader.get(BASE + str(club.pk) + "/members/").status_code == 404
    assert not ActivityRole.objects.exists()


def test_session_idempotency_conflict_windows_and_server_timestamps(world):
    club = make_club(world)
    member = memberships.join_club(actor=world["student"], club_id=club.pk)
    memberships.decide_membership(
        actor=world["admin"], club_id=club.pk, membership_id=member.pk, decision="APPROVE"
    )
    session = make_session(world, club)
    same = make_session(
        world,
        club,
        starts_at=session.starts_at,
        ends_at=session.ends_at,
        idempotency_key=session.idempotency_key,
    )
    assert same.id == session.id
    with pytest.raises(sessions.IdempotencyConflict):
        make_session(
            world,
            club,
            starts_at=session.starts_at,
            ends_at=session.ends_at + timedelta(minutes=1),
            idempotency_key=session.idempotency_key,
        )
    opened = sessions.change_session(
        actor=world["admin"], club_id=club.pk, session_id=session.id, opening=True
    )
    assert session.starts_at < opened.opened_at <= timezone.now()
    retry = sessions.change_session(
        actor=world["admin"], club_id=club.pk, session_id=session.id, opening=True
    )
    assert retry.opened_at == opened.opened_at
    assert sessions.eligible_for_attendance(session=session, student=world["student"])
    second = make_session(world, club)
    with pytest.raises(ValidationError):
        sessions.change_session(
            actor=world["admin"], club_id=club.pk, session_id=second.id, opening=True
        )
    with patch("clubs.sessions.timezone.now", return_value=session.ends_at + timedelta(minutes=1)):
        assert not sessions.eligible_for_attendance(session=session, student=world["student"])
        closed = sessions.change_session(
            actor=world["admin"], club_id=club.pk, session_id=session.id, opening=False
        )
        assert closed.closed_at > session.ends_at
    assert closed.status == "CLOSED"
    assert (
        sessions.change_session(
            actor=world["admin"], club_id=club.pk, session_id=session.id, opening=False
        ).closed_at
        == closed.closed_at
    )
    with pytest.raises(ValidationError):
        sessions.change_session(
            actor=world["admin"], club_id=club.pk, session_id=session.id, opening=True
        )


def test_future_session_cannot_open_and_cross_club_session_hidden(world):
    club = make_club(world)
    session = make_session(
        world,
        club,
        starts_at=timezone.now() + timedelta(days=1),
        ends_at=timezone.now() + timedelta(days=1, hours=1),
    )
    with pytest.raises(ValidationError):
        sessions.change_session(
            actor=world["admin"], club_id=club.pk, session_id=session.id, opening=True
        )
    other = make_club(world)
    response = client_for(world["admin"]).post(
        BASE + str(other.pk) + f"/sessions/{session.id}/open/", {}, format="json"
    )
    assert response.status_code == 404
    assert (
        client_for(world["admin"])
        .post(
            BASE + str(club.pk) + f"/sessions/{session.id}/open/",
            {"opened_at": timezone.now().isoformat()},
            format="json",
        )
        .status_code
        == 400
    )


@pytest.mark.parametrize(
    "slot",
    [
        {"weekday": 8, "starts_at": time(10), "ends_at": time(11)},
        {"weekday": 1, "starts_at": time(11), "ends_at": time(10)},
    ],
)
def test_schedule_invalid_replacement_preserves_previous(world, slot):
    club = make_club(world, published=False)
    services.replace_schedule(
        actor=world["admin"],
        club_id=club.pk,
        slots=[{"weekday": 1, "starts_at": time(10), "ends_at": time(11)}],
    )
    with pytest.raises(ValidationError):
        services.replace_schedule(actor=world["admin"], club_id=club.pk, slots=[slot])
    assert ClubSchedule.objects.get().ends_at == time(11)


def test_schedule_overlap_and_oversized_payload_denied(world):
    club = make_club(world, published=False)
    slots = [
        {"weekday": 1, "starts_at": time(10), "ends_at": time(11)},
        {"weekday": 1, "starts_at": time(10, 30), "ends_at": time(12)},
    ]
    with pytest.raises(ValidationError):
        services.replace_schedule(actor=world["admin"], club_id=club.pk, slots=slots)
    assert (
        client_for(world["admin"])
        .put(
            BASE + str(club.pk) + "/schedule/",
            {"slots": [{"weekday": 1, "starts_at": "10:00", "ends_at": "11:00"}] * 22},
            format="json",
        )
        .status_code
        == 400
    )


def test_analytics_dormancy_and_aggregates_are_not_join_multiplied(world):
    club = make_club(world, starts_at=timezone.now() - timedelta(days=60))
    Activity.objects.filter(pk=club.pk).update(created_at=timezone.now() - timedelta(days=40))
    assert visible_clubs(world["admin"]).get(pk=club.pk).dormant
    memberships.join_club(actor=world["student"], club_id=club.pk)
    m2 = memberships.join_club(actor=world["student2"], club_id=club.pk)
    memberships.decide_membership(
        actor=world["admin"], club_id=club.pk, membership_id=m2.pk, decision="APPROVE"
    )
    for _ in range(2):
        session = make_session(world, club)
        sessions.change_session(
            actor=world["admin"], club_id=club.pk, session_id=session.id, opening=True
        )
        sessions.change_session(
            actor=world["admin"], club_id=club.pk, session_id=session.id, opening=False
        )
    response = client_for(world["admin"]).get(BASE + str(club.pk) + "/analytics/")
    assert response.status_code == 200
    assert (
        response.data["active_members"],
        response.data["pending_members"],
        response.data["closed_sessions"],
        response.data["dormant"],
    ) == (1, 1, 2, False)


@pytest.mark.parametrize("operation", ["join", "approve", "open", "leader", "schedule"])
def test_audit_failure_rolls_back_domain_writes(world, operation):
    club = make_club(world, published=operation != "schedule")
    member = (
        memberships.join_club(actor=world["student"], club_id=club.pk)
        if operation == "approve"
        else None
    )
    session = make_session(world, club) if operation == "open" else None
    module = {
        "join": "clubs.memberships",
        "approve": "clubs.memberships",
        "open": "clubs.sessions",
        "leader": "accounts.services",
        "schedule": "clubs.services",
    }[operation]
    with patch(module + ".record_event", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            if operation == "join":
                memberships.join_club(actor=world["student"], club_id=club.pk)
            elif operation == "approve":
                memberships.decide_membership(
                    actor=world["admin"],
                    club_id=club.pk,
                    membership_id=member.pk,
                    decision="APPROVE",
                )
            elif operation == "open":
                sessions.change_session(
                    actor=world["admin"], club_id=club.pk, session_id=session.id, opening=True
                )
            elif operation == "leader":
                services.assign_leader(
                    actor=world["faculty"], club_id=club.pk, user_id=world["leader"].id
                )
            else:
                services.replace_schedule(
                    actor=world["admin"],
                    club_id=club.pk,
                    slots=[{"weekday": 1, "starts_at": time(10), "ends_at": time(11)}],
                )
    if operation == "join":
        assert not ClubMembership.objects.exists() and not Participant.objects.exists()
    elif operation == "approve":
        member.refresh_from_db()
        assert member.status == "PENDING" and Participant.objects.get().state == "PENDING"
    elif operation == "open":
        session.refresh_from_db()
        assert session.status == "PLANNED" and session.opened_at is None
    elif operation == "leader":
        assert not ActivityRole.objects.exists()
    else:
        assert not ClubSchedule.objects.exists()


def test_club_list_queries_bounded_and_no_roster_pii(world):
    club = make_club(world)
    services.assign_leader(actor=world["admin"], club_id=club.pk, user_id=world["leader"].id)
    memberships.join_club(actor=world["student"], club_id=club.pk)
    client = client_for(world["student"])
    with CaptureQueriesContext(connection) as first:
        response = client.get(BASE)
    assert str(world["leader"].id) in [str(x) for x in response.data["results"][0]["leader_ids"]]
    assert "Synthetic" not in str(response.data) and "reason" not in str(response.data)
    for _ in range(5):
        make_club(world)
    with CaptureQueriesContext(connection) as many:
        assert client.get(BASE).data["count"] == 6
    assert len(many) == len(first) and len(many) <= 12


def test_jwt_manual_club_flow_through_open_session_eligibility(world):
    club = make_club(world)
    services.assign_leader(actor=world["faculty"], club_id=club.pk, user_id=world["leader"].id)
    clients = {}
    for key in ["student", "leader"]:
        world[key].set_password("Example-password!123")
        world[key].save()
        client = APIClient()
        pair = client.post(
            "/api/v1/auth/login/",
            {"username": key, "password": "Example-password!123"},
            format="json",
        )
        assert pair.status_code == 200
        client.credentials(HTTP_AUTHORIZATION="Bearer " + pair.data["access"])
        clients[key] = client
    root = BASE + str(club.pk) + "/"
    member = clients["student"].post(root + "membership/", {}, format="json")
    assert member.status_code == 200 and member.data["status"] == "PENDING"
    assert (
        clients["leader"]
        .post(
            root + "members/" + str(member.data["id"]) + "/decision/",
            {"decision": "APPROVE"},
            format="json",
        )
        .data["status"]
        == "ACTIVE"
    )
    now = timezone.now()
    session = clients["leader"].post(
        root + "sessions/",
        {
            "starts_at": (now - timedelta(minutes=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
            "idempotency_key": str(uuid4()),
        },
        format="json",
    )
    assert session.status_code == 200
    path = root + "sessions/" + str(session.data["id"]) + "/"
    assert clients["leader"].post(path + "open/", {}, format="json").data["status"] == "OPEN"
    assert sessions.eligible_for_attendance(
        session=ClubSession.objects.get(pk=session.data["id"]), student=world["student"]
    )
    assert clients["leader"].post(path + "close/", {}, format="json").data["status"] == "CLOSED"


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("same_user", [False, True])
def test_concurrent_auto_join_last_seat_is_not_overbooked(world, same_user):
    club = make_club(world, registration_policy="OPEN", capacity=1)
    barrier = Barrier(2)

    def join(user):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                memberships.join_club(actor=user, club_id=club.pk)
                return "joined"
            except ValidationError:
                return "full"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(join, [world["student"], world["student"] if same_user else world["student2"]])
        )
    assert sorted(results) == (["joined", "joined"] if same_user else ["full", "joined"])
    assert ClubMembership.objects.filter(status="ACTIVE").count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_session_open_keeps_one_audited_open_session(world):
    club = make_club(world)
    first = make_session(world, club)
    second = make_session(world, club, starts_at=first.starts_at + timedelta(seconds=1))
    barrier = Barrier(2)

    def open_once(session):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                sessions.change_session(
                    actor=world["admin"], club_id=club.pk, session_id=session.id, opening=True
                )
                return "opened"
            except ValidationError:
                return "blocked"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(open_once, [first, second]))
    assert sorted(results) == ["blocked", "opened"]
    assert ClubSession.objects.filter(status="OPEN").count() == 1
    assert AuditEvent.objects.filter(action="club_session_opened").count() == 1


def test_create_club_and_session_audit_failure_roll_back(world):
    with patch("clubs.services.record_event", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            make_club(world, published=False)
    assert not Activity.objects.exists() and not Club.objects.exists()
    club = make_club(world)
    with patch("clubs.sessions.record_event", side_effect=RuntimeError("audit")):
        with pytest.raises(RuntimeError):
            make_session(world, club)
    assert not ClubSession.objects.exists()


def test_database_session_and_membership_constraints(world):
    club = make_club(world)
    member = memberships.join_club(actor=world["student"], club_id=club.pk)
    with pytest.raises(IntegrityError), transaction.atomic():
        ClubMembership.objects.filter(pk=member.pk).update(status="INVALID")
    first = make_session(world, club)
    sessions.change_session(
        actor=world["admin"], club_id=club.pk, session_id=first.id, opening=True
    )
    second = make_session(world, club)
    with pytest.raises(IntegrityError), transaction.atomic():
        ClubSession.objects.filter(pk=second.pk).update(
            status="OPEN", opened_at=timezone.now(), opened_by=world["admin"]
        )
