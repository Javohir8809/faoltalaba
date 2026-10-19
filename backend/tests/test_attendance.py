from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from accounts.models import RefreshSession, RoleGrant
from accounts.tokens import issue_pair
from attendance import services
from attendance.models import (
    AttendanceChange,
    AttendanceDevice,
    AttendanceRecord,
    StudentCardMapping,
)
from attendance.tokens import ADAPTERS
from clubs import memberships, sessions
from clubs import services as club_services
from django.conf import settings
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import override_settings
from django.utils import timezone
from redis import Redis
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from students.models import StudentProfile
from tests.test_clubs import client_for, make_club, make_session, world  # noqa: F401

pytestmark = pytest.mark.django_db
BASE = "/api/v1/attendance/"


@pytest.fixture
def ready(world):  # noqa: F811
    club = make_club(world, registration_policy="OPEN")
    memberships.join_club(actor=world["student"], club_id=club.pk)
    session = make_session(world, club)
    sessions.change_session(
        actor=world["admin"], club_id=club.pk, session_id=session.pk, opening=True
    )
    student = StudentProfile.objects.get(user=world["student"])
    card = services.enroll_card(
        actor=world["admin"], student_id=student.pk, kind="NFC", token="test-card-token"
    )
    return {**world, "club": club, "session": session, "profile": student, "card": card}


def scan(w, **overrides):
    args = dict(actor=w["admin"], session_id=w["session"].pk, method="NFC", token="test-card-token")
    args.update(overrides)
    return services.check_in(**args)


def endpoint(w, tail="check-in/"):
    return BASE + f"sessions/{w['session'].pk}/" + tail


def test_jwt_checkin_duplicate_history_stats(ready):
    w = ready
    client = APIClient()
    club_services.assign_leader(actor=w["admin"], club_id=w["club"].pk, user_id=w["leader"].pk)
    refresh = RefreshSession.objects.create(
        user=w["leader"], refresh_digest="0" * 64, expires_at=timezone.now() + timedelta(days=1)
    )
    client.credentials(HTTP_AUTHORIZATION="Bearer " + issue_pair(refresh)["access"])
    before = timezone.now()
    first = client.post(
        endpoint(w),
        {"method": "NFC", "token": "test-card-token", "note": "Internal"},
        format="json",
    )
    assert first.status_code == 200, first.data
    record = AttendanceRecord.objects.get()
    assert before <= record.checked_in_at <= timezone.now()
    services.enroll_card(actor=w["admin"], student_id=w["profile"].pk, kind="QR", token="qr-token")
    second = client.post(endpoint(w), {"method": "QR", "token": "qr-token"}, format="json")
    assert second.data == first.data
    assert AttendanceRecord.objects.count() == AttendanceChange.objects.count() == 1
    history = client_for(w["student"]).get("/api/v1/students/me/activity-history/")
    assert history.status_code == 200 and history.data["count"] == 1
    item = history.data["results"][0]
    assert set(item) == {
        "id",
        "activity_id",
        "activity_title",
        "session_id",
        "checked_in_at",
        "method",
        "status",
        "version",
    }
    assert client_for(w["student2"]).get("/api/v1/students/me/activity-history/").data["count"] == 0
    stats = client.get(endpoint(w, "stats/"))
    assert stats.data == {
        "total": 1,
        "present": 1,
        "voided": 0,
        "by_method": {"NFC": 1, "QR": 0, "MANUAL": 0},
    }


@pytest.mark.parametrize(
    "body",
    [
        {"method": "MANUAL"},
        {"method": "MANUAL", "reason": ""},
        {"method": "NFC", "token": "test-card-token", "checked_in_at": "2020-01-01T00:00:00Z"},
        {"method": "NFC", "token": "test-card-token", "student_id": str(uuid4())},
        {"method": "NFC", "token": "test-card-token", "reason": "override"},
        {"method": "QR"},
    ],
)
def test_strict_method_inputs(ready, body):
    response = client_for(ready["admin"]).post(endpoint(ready), body, format="json")
    assert response.status_code == 400
    assert not AttendanceRecord.objects.exists()


def test_manual_reason_and_device(ready):
    w = ready
    device = services.save_device(
        actor=w["admin"], installation_id=uuid4(), label="Reader", nfc_supported=True
    )
    same = services.save_device(
        actor=w["admin"], installation_id=device.installation_id, label="Retry"
    )
    assert same.pk == device.pk
    record = services.check_in(
        actor=w["admin"],
        session_id=w["session"].pk,
        method="MANUAL",
        student_id=w["profile"].pk,
        reason="Card unavailable",
        device_id=device.pk,
    )
    assert record.device_id == device.pk
    assert record.changes.get().reason == "Card unavailable"
    device.refresh_from_db()
    assert device.last_seen_at == record.checked_in_at


@pytest.mark.parametrize(
    "token", ["", " token", "token ", "line\nvalue", "o‘quvchi", "x" * 257, None]
)
def test_tokens_reject_invalid_without_echo(token):
    with pytest.raises(ValidationError) as failure:
        ADAPTERS["NFC"].digest(token)
    assert "invalid_card" in str(failure.value.get_codes())


def test_token_domain_separation_and_enrollment_conflicts(ready):
    w = ready
    assert ADAPTERS["NFC"].digest("same") != ADAPTERS["QR"].digest("same")
    assert ADAPTERS["NFC"].digest("ABC") != ADAPTERS["NFC"].digest("abc")
    card = services.enroll_card(
        actor=w["admin"], student_id=w["profile"].pk, kind="NFC", token="test-card-token"
    )
    assert card.pk == w["card"].pk
    from clubs.sessions import IdempotencyConflict

    with pytest.raises(IdempotencyConflict):
        services.enroll_card(
            actor=w["admin"],
            student_id=StudentProfile.objects.get(user=w["student2"]).pk,
            kind="NFC",
            token="test-card-token",
        )
    services.revoke_card(actor=w["admin"], card_id=card.pk, reason="Lost")
    with pytest.raises(IdempotencyConflict):
        services.enroll_card(
            actor=w["admin"], student_id=w["profile"].pk, kind="NFC", token="test-card-token"
        )
    with pytest.raises(ValidationError):
        scan(w)
    with pytest.raises(ValidationError):
        scan(w, method="QR")
    response = client_for(w["admin"]).get(BASE + "card-mappings/")
    assert "token_digest" not in str(response.data) and "test-card-token" not in str(response.data)


@pytest.mark.parametrize("who", ["student", "outsider", "other_manager"])
def test_scope_and_role_isolation(ready, who):
    w = ready
    response = client_for(w[who]).post(
        endpoint(w), {"method": "NFC", "token": "test-card-token"}, format="json"
    )
    assert response.status_code == (404 if who == "other_manager" else 403)
    assert client_for(w[who]).post(BASE + "card-mappings/", {}, format="json").status_code == 403
    assert not AttendanceRecord.objects.exists()


def test_flags_and_anonymous_do_not_authorize(ready):
    w = ready
    w["student"].is_staff = w["student"].is_superuser = True
    w["student"].save()
    assert client_for(w["student"]).get(BASE + "devices/").status_code == 403
    assert APIClient().post(endpoint(w), {}, format="json").status_code == 401


@pytest.mark.parametrize(
    "change",
    ["left", "pending", "inactive_source", "inactive_user", "role_removed", "closed", "expired"],
)
def test_current_eligibility_and_window(ready, change):
    w = ready
    if change == "left":
        memberships.leave_club(actor=w["student"], club_id=w["club"].pk)
    elif change == "pending":
        from clubs.models import ClubMembership

        ClubMembership.objects.update(status="PENDING")
    elif change == "inactive_source":
        StudentProfile.objects.filter(pk=w["profile"].pk).update(hemis_active=False)
    elif change == "inactive_user":
        type(w["student"]).objects.filter(pk=w["student"].pk).update(is_active=False)
    elif change == "role_removed":
        RoleGrant.objects.filter(user=w["student"]).delete()
    elif change == "closed":
        sessions.change_session(
            actor=w["admin"], club_id=w["club"].pk, session_id=w["session"].pk, opening=False
        )
    else:
        with patch(
            "clubs.sessions.timezone.now", return_value=w["session"].ends_at + timedelta(seconds=1)
        ):
            with pytest.raises(ValidationError):
                scan(w)
        return
    with pytest.raises(ValidationError):
        scan(w)
    assert not AttendanceRecord.objects.exists()


def test_device_ownership_and_active_state(ready):
    w = ready
    device = services.save_device(actor=w["faculty"], installation_id=uuid4(), label="Other")
    assert (
        client_for(w["admin"])
        .patch(BASE + f"devices/{device.pk}/", {"label": "Hijack"}, format="json")
        .status_code
        == 404
    )
    response = client_for(w["admin"]).post(
        endpoint(w),
        {"method": "NFC", "token": "test-card-token", "device_id": str(device.pk)},
        format="json",
    )
    assert response.status_code == 404
    services.save_device(actor=w["faculty"], device_id=device.pk, is_active=False)
    response = client_for(w["faculty"]).post(
        endpoint(w),
        {"method": "NFC", "token": "test-card-token", "device_id": str(device.pk)},
        format="json",
    )
    assert response.status_code == 404


def correction(w, record, **overrides):
    args = dict(
        actor=w["admin"],
        record_id=record.pk,
        status="VOIDED",
        reason="Incorrect scan",
        expected_version=1,
        idempotency_key=uuid4(),
        note="Internal review",
    )
    args.update(overrides)
    return services.correct_record(**args)


def test_correction_history_replay_version_and_closed_session(ready):
    w = ready
    record = scan(w)
    original_time = record.checked_in_at
    sessions.change_session(
        actor=w["admin"], club_id=w["club"].pk, session_id=w["session"].pk, opening=False
    )
    key = uuid4()
    corrected = correction(w, record, idempotency_key=key)
    assert corrected.version == 2 and corrected.status == "VOIDED"
    assert corrected.checked_in_at == original_time and corrected.method == "NFC"
    assert correction(w, record, idempotency_key=key).version == 2
    from clubs.sessions import IdempotencyConflict

    with pytest.raises(IdempotencyConflict):
        correction(w, record, idempotency_key=key, reason="Different")
    with pytest.raises(IdempotencyConflict):
        correction(w, record)
    restored = correction(w, record, expected_version=2, status="PRESENT")
    assert restored.version == 3
    assert correction(w, record, idempotency_key=key).status == "PRESENT"
    assert record.changes.count() == 3
    history = client_for(w["faculty"]).get(BASE + f"records/{record.pk}/changes/")
    assert history.status_code == 200 and history.data["count"] == 3
    assert client_for(w["student"]).get(BASE + f"records/{record.pk}/changes/").status_code == 403
    assert client_for(w["other_manager"]).get(BASE + f"records/{record.pk}/").status_code == 404
    with pytest.raises(ValidationError):
        scan(w)


def test_voided_record_not_restored_by_rescan(ready):
    record = scan(ready)
    correction(ready, record)
    duplicate = scan(ready)
    assert duplicate.status == "VOIDED" and duplicate.version == 2


@pytest.mark.parametrize(
    "operation",
    ["time", "note", "change_update", "change_delete", "truncate", "card_rebind", "card_delete"],
)
def test_database_guards(ready, operation):
    record = scan(ready)
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
    with pytest.raises(IntegrityError), transaction.atomic():
        if operation == "time":
            AttendanceRecord.objects.filter(pk=record.pk).update(checked_in_at=timezone.now())
        elif operation == "note":
            AttendanceRecord.objects.filter(pk=record.pk).update(note="Unlogged")
        elif operation == "change_update":
            AttendanceChange.objects.filter(record=record).update(reason="Forged")
        elif operation == "change_delete":
            AttendanceChange.objects.filter(record=record).delete()
        elif operation == "truncate":
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE attendance_attendancechange CASCADE")
        elif operation == "card_rebind":
            StudentCardMapping.objects.filter(pk=ready["card"].pk).update(
                student=StudentProfile.objects.get(user=ready["student2"])
            )
        else:
            StudentCardMapping.objects.filter(pk=ready["card"].pk).delete()


@pytest.mark.parametrize("operation", ["scan", "correction", "device", "card", "revoke"])
def test_audit_failure_rolls_back(ready, operation):
    w = ready
    if operation == "correction":
        record = scan(w)
    counts = [
        model.objects.count()
        for model in [AttendanceRecord, AttendanceChange, AttendanceDevice, StudentCardMapping]
    ]
    with (
        patch("attendance.services.record_event", side_effect=RuntimeError("audit failed")),
        pytest.raises(RuntimeError),
    ):
        if operation == "scan":
            scan(w)
        elif operation == "correction":
            correction(w, record)
        elif operation == "device":
            services.save_device(actor=w["admin"], installation_id=uuid4(), label="Reader")
        elif operation == "card":
            services.enroll_card(
                actor=w["admin"], student_id=w["profile"].pk, kind="QR", token="new"
            )
        else:
            services.revoke_card(actor=w["admin"], card_id=w["card"].pk, reason="Lost")
    assert counts == [
        model.objects.count()
        for model in [AttendanceRecord, AttendanceChange, AttendanceDevice, StudentCardMapping]
    ]
    if operation == "correction":
        record.refresh_from_db()
        assert record.version == 1 and record.status == "PRESENT"
    w["card"].refresh_from_db()
    assert w["card"].revoked_at is None


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_scans(ready):
    barrier = Barrier(2)

    def run():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return scan(ready).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    assert AttendanceRecord.objects.count() == AttendanceChange.objects.count() == 1


@pytest.mark.redis_integration
def test_real_redis_limit_and_outage(ready):
    w = ready
    client = client_for(w["admin"])
    redis = Redis.from_url(settings.REDIS_URL)
    # Isolated keys: the actor UUID is fresh in this database fixture.
    with override_settings(ATTENDANCE_THROTTLE_ENABLED=True, ATTENDANCE_ACTOR_LIMIT=1):
        assert client.get(endpoint(w, "stats/")).status_code == 200
        assert client.get(endpoint(w, "stats/")).status_code == 429
        keys = list(redis.scan_iter("attendance-limit:*"))
        assert keys and all(
            b"test-card-token" not in key
            and b"127.0.0.1" not in key
            and str(w["admin"].pk).encode() not in key
            for key in keys
        )
    with override_settings(ATTENDANCE_THROTTLE_ENABLED=True, REDIS_URL="redis://127.0.0.1:1/0"):
        response = client.get(endpoint(w, "stats/"))
        assert response.status_code == 503
        assert response.data["error"]["code"] == "ATTENDANCE_UNAVAILABLE"


def test_correction_api_and_strict_original_fields(ready):
    w = ready
    record = scan(w)
    url = BASE + f"records/{record.pk}/corrections/"
    body = {
        "status": "VOIDED",
        "reason": "Review",
        "expected_version": 1,
        "idempotency_key": str(uuid4()),
    }
    client = client_for(w["admin"])
    assert (
        client.post(
            url, {**body, "checked_in_at": timezone.now().isoformat()}, format="json"
        ).status_code
        == 400
    )
    assert client.post(url, {**body, "reason": " "}, format="json").status_code == 400
    result = client.post(url, body, format="json")
    assert result.status_code == 200 and result.data["version"] == 2
    assert client.post(url, body, format="json").data == result.data
    assert client.post(url, {**body, "reason": "Changed"}, format="json").status_code == 409
    assert client_for(w["other_manager"]).post(url, body, format="json").status_code == 404
    RoleGrant.objects.filter(user=w["student"]).delete()
    assert client_for(w["student"]).get("/api/v1/students/me/activity-history/").data["count"] == 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("other", ["close", "leave"])
def test_scan_serializes_with_close_or_leave(ready, other):
    w = ready
    barrier = Barrier(2)

    def run_scan():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                return scan(w).pk
            except ValidationError:
                return None
        finally:
            close_old_connections()

    def run_other():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            if other == "close":
                sessions.change_session(
                    actor=w["admin"],
                    club_id=w["club"].pk,
                    session_id=w["session"].pk,
                    opening=False,
                )
            else:
                memberships.leave_club(actor=w["student"], club_id=w["club"].pk)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        scan_future = pool.submit(run_scan)
        other_future = pool.submit(run_other)
        result = scan_future.result(timeout=30)
        other_future.result(timeout=30)
    assert AttendanceRecord.objects.count() == (1 if result else 0)
    with pytest.raises(ValidationError):
        scan(w)


@pytest.mark.django_db(transaction=True)
def test_initial_record_requires_history_on_commit(ready):
    with pytest.raises(IntegrityError), transaction.atomic():
        AttendanceRecord.objects.create(
            session=ready["session"],
            student=ready["profile"],
            recorded_by=ready["admin"],
            checked_in_at=timezone.now(),
            method="NFC",
        )
    assert not AttendanceRecord.objects.exists()
