from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import UUID, uuid4

import jwt
import pytest
from accounts import services, tokens
from accounts.models import ExternalIdentity, RefreshSession, Role, RoleGrant, ScopeType, User
from accounts.policies import has_capability
from audit.models import AuditEvent
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import override_settings
from django.utils import timezone
from organizations.models import Department, Faculty
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient
from staff.models import StaffProfile
from students.models import StudentProfile

pytestmark = pytest.mark.django_db


@pytest.fixture
def student():
    user = User.objects.create_user("student", "Test-password!123")
    RoleGrant.objects.create(user=user, role=Role.STUDENT, scope_type=ScopeType.GLOBAL)
    return user


@pytest.fixture
def superadmin():
    return User.objects.create_superuser("superadmin", "Test-password!123")


def client_for(user: User) -> APIClient:
    client = APIClient()
    pair = tokens.login(username=user.username, password="Test-password!123")
    client.credentials(HTTP_AUTHORIZATION="Bearer " + pair["access"])
    return client


def test_uuid_external_mapping_and_password_storage(student) -> None:
    assert isinstance(student.id, UUID)
    assert student.password != "Test-password!123"
    identity = ExternalIdentity.objects.create(user=student, source="HEMIS", external_id="123456")
    assert identity.external_id != str(student.id)
    other = User.objects.create_user("other", "Test-password!123")
    with pytest.raises(IntegrityError), transaction.atomic():
        ExternalIdentity.objects.create(user=other, source="HEMIS", external_id="123456")
    student.id = uuid4()
    with pytest.raises(ValidationError):
        student.save()
    with pytest.raises(IntegrityError), transaction.atomic():
        # This user has no FK dependants: the UUID trigger itself must reject it.
        User.objects.filter(pk=other.id).update(id=uuid4())


def test_provisioning_rejects_weak_passwords() -> None:
    with pytest.raises(ValidationError):
        User.objects.create_user("weak-password-user", "123")
    assert not User.objects.filter(username="weak-password-user").exists()


def test_login_refresh_logout_end_to_end(student) -> None:
    client = APIClient()
    pair = client.post(
        "/api/v1/auth/login/",
        {"username": student.username, "password": "Test-password!123"},
        format="json",
    )
    assert pair.status_code == 200
    assert pair["Cache-Control"] == "no-store"
    access, refresh = pair.data["access"], pair.data["refresh"]
    claims = tokens.decode_token(access, "access")
    assert claims["sub"] == str(student.id)
    assert "username" not in claims and "roles" not in claims
    assert RefreshSession.objects.get(pk=claims["sid"]).refresh_digest != refresh
    client.credentials(HTTP_AUTHORIZATION="Bearer " + access)
    assert client.get("/api/v1/auth/me/").status_code == 200
    rotated = client.post("/api/v1/auth/refresh/", {"refresh": refresh}, format="json")
    assert rotated.status_code == 200 and rotated.data["refresh"] != refresh
    assert (
        client.post(
            "/api/v1/auth/logout/", {"refresh": rotated.data["refresh"]}, format="json"
        ).status_code
        == 204
    )
    assert client.get("/api/v1/auth/me/").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh/", {"refresh": rotated.data["refresh"]}, format="json"
        ).status_code
        == 401
    )


def test_refresh_replay_commits_session_revocation(student) -> None:
    pair = tokens.login(username=student.username, password="Test-password!123")
    rotated = tokens.refresh(pair["refresh"])
    with pytest.raises(AuthenticationFailed):
        tokens.refresh(pair["refresh"])
    assert RefreshSession.objects.get().revoked_at is not None
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer " + rotated["access"])
    assert client.get("/api/v1/auth/me/").status_code == 401


@pytest.mark.parametrize(
    "kind", ["expired", "audience", "issuer", "refresh", "algorithm", "missing", "malformed"]
)
def test_invalid_access_tokens_are_rejected(student, kind) -> None:
    pair = tokens.login(username=student.username, password="Test-password!123")
    claims = tokens.decode_token(pair["access"], "access")
    algorithm = "HS256"
    if kind == "expired":
        claims["exp"] = int((timezone.now() - timedelta(seconds=5)).timestamp())
    if kind == "audience":
        claims["aud"] = "another-app"
    if kind == "issuer":
        claims["iss"] = "another-service"
    if kind == "refresh":
        claims["type"] = "refresh"
    if kind == "algorithm":
        algorithm = "HS384"
    if kind == "missing":
        del claims["exp"]
    token = (
        "malformed"
        if kind == "malformed"
        else jwt.encode(claims, settings.JWT_SIGNING_KEY, algorithm=algorithm)
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
    response = client.get("/api/v1/auth/me/")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_TOKEN"
    assert token not in response.content.decode()


def test_password_change_revokes_existing_tokens(student) -> None:
    client = client_for(student)
    student.set_password("Different-password!123")
    student.save(update_fields=["password"])
    assert client.get("/api/v1/auth/me/").status_code == 401
    assert AuditEvent.objects.filter(action="password_changed", object_id=student.id).exists()


def test_login_does_not_use_a_stale_password_check(student) -> None:
    stale = User.objects.get(pk=student.pk)
    student.set_password("Different-password!123")
    student.save(update_fields=["password"])
    with patch("accounts.tokens.authenticate", return_value=stale):
        with pytest.raises(AuthenticationFailed):
            tokens.login(username=student.username, password="Test-password!123")
    assert not RefreshSession.objects.exists()


def test_invalid_and_missing_user_login_are_indistinguishable(student) -> None:
    client = APIClient()
    responses = [
        client.post("/api/v1/auth/login/", {"username": name, "password": "wrong"}, format="json")
        for name in (student.username, "missing-user")
    ]
    assert all(response.status_code == 401 for response in responses)
    assert responses[0].json() == responses[1].json()


@pytest.mark.parametrize(
    "role",
    [
        value
        for value in Role.values
        if value
        not in (
            Role.SUPERADMIN,
            Role.YOUTH_ADMIN,
            Role.FACULTY_YOUTH_RESPONSIBLE,
            Role.DEPARTMENT_RESPONSIBLE,
        )
    ],
)
def test_role_matrix_denies_general_admin_read(role) -> None:
    user = User.objects.create_user(
        "role-test", "Test-password!123", is_staff=True, is_superuser=True
    )
    scope = (
        ScopeType.ACTIVITY
        if role in (Role.CLUB_LEADER, Role.ACTIVITY_RESPONSIBLE)
        else ScopeType.GLOBAL
    )
    RoleGrant.objects.create(
        user=user,
        role=role,
        scope_type=scope,
        scope_id=uuid4() if scope == ScopeType.ACTIVITY else None,
    )
    assert client_for(user).get("/api/v1/admin/users/").status_code == 403


@pytest.mark.parametrize(
    "scope_type,role",
    [
        (ScopeType.FACULTY, Role.FACULTY_YOUTH_RESPONSIBLE),
        (ScopeType.DEPARTMENT, Role.DEPARTMENT_RESPONSIBLE),
    ],
)
def test_academic_scope_isolation(student, scope_type, role) -> None:
    faculty_a = Faculty.objects.create(name="Faculty A")
    faculty_b = Faculty.objects.create(name="Faculty B")
    department_a = Department.objects.create(faculty=faculty_a, name="Department A")
    department_b = Department.objects.create(faculty=faculty_b, name="Department B")
    StudentProfile.objects.create(user=student, faculty=faculty_a, department=department_a)
    other = User.objects.create_user("other-student", "Test-password!123")
    StaffProfile.objects.create(user=other, faculty=faculty_b, department=department_b)
    leader = User.objects.create_user("leader", "Test-password!123")
    scope_id = faculty_a.id if scope_type == ScopeType.FACULTY else department_a.id
    RoleGrant.objects.create(user=leader, role=role, scope_type=scope_type, scope_id=scope_id)
    client = client_for(leader)
    response = client.get("/api/v1/admin/users/")
    assert response.status_code == 200
    assert [item["id"] for item in response.data["results"]] == [str(student.id)]
    assert client.get(f"/api/v1/admin/users/{other.id}/").status_code == 404
    assert (
        client.patch(
            f"/api/v1/admin/users/{student.id}/status/", {"is_active": False}, format="json"
        ).status_code
        == 403
    )
    assert not has_capability(leader, "activities.manage", scopes={scope_type: uuid4()})
    assert has_capability(leader, "activities.manage", scopes={scope_type: scope_id})


def test_activity_scope_matches_only_owned_activity(student) -> None:
    activity_id = uuid4()
    RoleGrant.objects.create(
        user=student, role=Role.CLUB_LEADER, scope_type=ScopeType.ACTIVITY, scope_id=activity_id
    )
    assert has_capability(student, "activities.manage", scopes={ScopeType.ACTIVITY: activity_id})
    assert not has_capability(student, "activities.manage", scopes={ScopeType.ACTIVITY: uuid4()})
    assert not has_capability(student, "activities.manage")


def test_privileged_changes_audited_and_last_admin_guarded(superadmin, student) -> None:
    client = client_for(superadmin)
    response = client.post(
        f"/api/v1/admin/users/{student.id}/roles/",
        {"role": Role.YOUTH_ADMIN, "scope_type": ScopeType.GLOBAL},
        format="json",
    )
    assert response.status_code == 201
    assert AuditEvent.objects.filter(
        action="role_granted", actor_id=superadmin.id, object_id=student.id
    ).exists()
    student_client = client_for(student)
    assert student_client.get("/api/v1/admin/users/").status_code == 200
    assert (
        student_client.post(
            f"/api/v1/admin/users/{student.id}/roles/",
            {"role": Role.SUPERADMIN, "scope_type": ScopeType.GLOBAL},
            format="json",
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/api/v1/admin/users/{student.id}/roles/{response.data['id']}/").status_code
        == 204
    )
    assert student_client.get("/api/v1/admin/users/").status_code == 403
    assert (
        client.patch(
            f"/api/v1/admin/users/{student.id}/status/", {"is_active": False}, format="json"
        ).status_code
        == 200
    )
    assert student_client.get("/api/v1/auth/me/").status_code == 401
    assert AuditEvent.objects.filter(action="user_status_changed", object_id=student.id).exists()
    assert (
        client.patch(
            f"/api/v1/admin/users/{superadmin.id}/status/", {"is_active": False}, format="json"
        ).status_code
        == 400
    )
    own_grant = superadmin.role_grants.get()
    assert (
        client.delete(f"/api/v1/admin/users/{superadmin.id}/roles/{own_grant.id}/").status_code
        == 400
    )


def test_role_constraints_and_scope_validation(superadmin, student) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        RoleGrant.objects.create(
            user=student, role=Role.FACULTY_YOUTH_RESPONSIBLE, scope_type=ScopeType.GLOBAL
        )
    client = client_for(superadmin)
    for role, scope in (
        (Role.FACULTY_YOUTH_RESPONSIBLE, ScopeType.FACULTY),
        (Role.CLUB_LEADER, ScopeType.ACTIVITY),
    ):
        assert (
            client.post(
                f"/api/v1/admin/users/{student.id}/roles/",
                {"role": role, "scope_type": scope, "scope_id": str(uuid4())},
                format="json",
            ).status_code
            == 400
        )


def test_audit_is_immutable_at_model_queryset_and_sql_levels(student) -> None:
    event = AuditEvent.objects.first()
    with pytest.raises(ValueError):
        event.delete()
    with pytest.raises(ValueError):
        event.save()
    for statement in (
        "UPDATE audit_auditevent SET action='changed'",
        "DELETE FROM audit_auditevent",
        "TRUNCATE audit_auditevent",
    ):
        with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement)
    assert AuditEvent.objects.filter(pk=event.id).exists()


def test_role_change_rolls_back_when_audit_fails(superadmin, student) -> None:
    with patch("accounts.services.record_event", side_effect=RuntimeError("audit unavailable")):
        with pytest.raises(RuntimeError):
            services.grant_role(
                actor=superadmin,
                target=student,
                role=Role.YOUTH_ADMIN,
                scope_type=ScopeType.GLOBAL,
                scope_id=None,
            )
    assert not student.role_grants.filter(role=Role.YOUTH_ADMIN).exists()


def test_profile_requires_matching_department_faculty(student) -> None:
    faculty_a = Faculty.objects.create(name="Faculty A")
    faculty_b = Faculty.objects.create(name="Faculty B")
    department = Department.objects.create(faculty=faculty_b, name="Department B")
    for profile in (StudentProfile, StaffProfile):
        with pytest.raises(ValidationError):
            profile.objects.create(user=student, faculty=faculty_a, department=department)


def test_auth_rate_limiter_fails_closed(student) -> None:
    with (
        override_settings(AUTH_THROTTLE_ENABLED=True),
        patch(
            "accounts.throttling.Redis.from_url",
            side_effect=RedisConnectionError("private-redis-url"),
        ),
    ):
        response = APIClient().post(
            "/api/v1/auth/login/",
            {"username": student.username, "password": "Test-password!123"},
            format="json",
        )
    assert response.status_code == 503
    assert "private-redis-url" not in response.content.decode()


def test_invalid_json_shape_returns_validation_error() -> None:
    with override_settings(AUTH_THROTTLE_ENABLED=True):
        response = APIClient().post(
            "/api/v1/auth/login/", [], format="json", REMOTE_ADDR="test-" + str(uuid4())
        )
    assert response.status_code == 400


def test_login_rate_limit_atomic_with_real_redis(student) -> None:
    address = "test-" + str(uuid4())
    with override_settings(AUTH_THROTTLE_ENABLED=True, AUTH_IP_LIMIT=2, AUTH_ACCOUNT_LIMIT=100):
        responses = [
            APIClient().post(
                "/api/v1/auth/login/",
                {"username": student.username, "password": "wrong"},
                format="json",
                REMOTE_ADDR=address,
            )
            for _ in range(3)
        ]
    assert [response.status_code for response in responses] == [401, 401, 429]


@pytest.mark.django_db(transaction=True)
def test_concurrent_refresh_cannot_create_two_valid_sessions() -> None:
    user = User.objects.create_user("concurrent", "Test-password!123")
    pair = tokens.login(username=user.username, password="Test-password!123")
    barrier = Barrier(2)

    def attempt():
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return tokens.refresh(pair["refresh"])
        except AuthenticationFailed:
            return None
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    assert sum(item is not None for item in results) == 1
    assert RefreshSession.objects.get().revoked_at is not None


@pytest.mark.django_db(transaction=True)
def test_concurrent_deactivation_keeps_one_active_superadmin() -> None:
    admins = [
        User.objects.create_superuser(f"admin-{index}", "Test-password!123") for index in range(2)
    ]
    barrier = Barrier(2)

    def deactivate(user):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            services.set_user_status(actor=user, target=user, is_active=False)
            return True
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as APIValidationError

            if not isinstance(exc, APIValidationError):
                raise
            return False
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(deactivate, admins))
    assert sorted(results) == [False, True]
    assert services.active_superadmins() == 1
