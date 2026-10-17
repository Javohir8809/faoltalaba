import io
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest
from accounts.models import ExternalIdentity, Role, RoleGrant, ScopeType, User
from audit.models import AuditEvent
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import override_settings
from django.utils import timezone
from integrations.hemis.adapters import HemisError, MockHemisAdapter, Page, get_adapter
from integrations.hemis.models import Resource, SyncState
from integrations.hemis.services import sync_resource
from integrations.hemis.tasks import sync_hemis
from integrations.hemis.transport import MAX_RESPONSE_BYTES, JsonGetTransport, NoRedirect
from organizations.models import Department, Faculty, Group, Subject
from rest_framework.test import APIClient
from staff.models import StaffProfile
from students.models import StudentProfile

pytestmark = pytest.mark.django_db


class Pages:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch_page(self, resource, cursor):
        self.calls.append(cursor)
        value = self.pages[cursor]
        if isinstance(value, Exception):
            raise value
        return value


def run_rows(resource, *rows):
    return sync_resource(resource, adapter=Pages({"": Page(tuple(rows))}))


def seed():
    adapter = MockHemisAdapter()
    for resource in Resource:
        sync_resource(resource, adapter=adapter)
    return adapter


def test_complete_mock_import_idempotent_and_uuid_identity():
    seed()
    profiles = [StudentProfile.objects.get(), StaffProfile.objects.get()]
    original = [(p.id, p.user_id) for p in profiles]
    seed()
    assert original == [
        (StudentProfile.objects.get().id, StudentProfile.objects.get().user_id),
        (StaffProfile.objects.get().id, StaffProfile.objects.get().user_id),
    ]
    assert (
        Faculty.objects.count(),
        Department.objects.count(),
        Group.objects.count(),
        Subject.objects.count(),
    ) == (1, 1, 1, 1)
    assert User.objects.count() == 2
    assert not RoleGrant.objects.exists()
    assert all(not p.user.has_usable_password() for p in profiles)
    assert set(ExternalIdentity.objects.values_list("external_id", flat=True)) == {
        "student:demo-s1",
        "staff:demo-t1",
    }
    assert (
        SyncState.objects.filter(
            status="SUCCEEDED", cursor="", last_success_at__isnull=False
        ).count()
        == 6
    )
    assert AuditEvent.objects.filter(action="hemis_page_imported").count() == 12


def test_import_preserves_local_auth_and_null_optional_fields():
    adapter = seed()
    student = StudentProfile.objects.get()
    user = student.user
    user.username = "local-account"
    user.set_password("Local-password!123")
    user.is_active = False
    user.save()
    RoleGrant.objects.create(user=user, role=Role.STUDENT, scope_type=ScopeType.GLOBAL)
    row = dict(adapter.data["students"][0], name="Yangi ism", department_id=None, group_id=None)
    run_rows("students", row)
    student.refresh_from_db()
    user.refresh_from_db()
    assert student.full_name == "Yangi ism"
    assert student.department_id and student.group_id
    assert user.username == "local-account" and not user.is_active
    assert user.check_password("Local-password!123")
    assert user.role_grants.get().role == Role.STUDENT


def test_changed_tombstoned_missing_and_reactivated_source():
    seed()
    faculty = Faculty.objects.get()
    run_rows("faculties", {"id": "demo-f1", "name": "Yangi fakultet"})
    faculty.refresh_from_db()
    assert faculty.name == "Yangi fakultet"
    run_rows("students", {"id": "demo-s1", "deleted": True})
    profile = StudentProfile.objects.get()
    assert not profile.hemis_active and profile.user.is_active
    run_rows("faculties")
    assert Faculty.objects.get().hemis_active  # An absent row is not a tombstone.
    run_rows("students", {"id": "unknown", "deleted": True})
    assert StudentProfile.objects.count() == 1
    sync_resource("students", adapter=MockHemisAdapter())
    assert StudentProfile.objects.get().hemis_active


def test_failed_page_rollback_and_resume_from_committed_cursor():
    pages = Pages(
        {
            "": Page(({"id": "f1", "name": "First"},), "next"),
            "next": Page(({"id": "f2", "name": "Second"}, {"id": "bad", "name": None})),
        }
    )
    with pytest.raises(HemisError, match="INVALID_RECORD"):
        sync_resource("faculties", adapter=pages)
    state = SyncState.objects.get()
    assert (state.status, state.cursor, state.records_processed) == ("FAILED", "next", 1)
    assert list(Faculty.objects.values_list("hemis_id", flat=True)) == ["f1"]
    fixed = Pages({"next": Page(({"id": "f2", "name": "Second"},))})
    sync_resource("faculties", adapter=fixed)
    assert fixed.calls == ["next"]
    assert Faculty.objects.count() == 2
    assert SyncState.objects.get().records_processed == 2


def test_failure_keeps_last_success_and_does_not_leak(caplog):
    run_rows("subjects", {"id": "s", "name": "Subject"})
    success = SyncState.objects.get().last_success_at
    with pytest.raises(HemisError, match="SYNC_FAILED"):
        sync_resource("subjects", adapter=Pages({"": RuntimeError("secret-token/private-name")}))
    assert SyncState.objects.get().last_success_at == success
    assert "secret-token" not in caplog.text
    from config.logging import JsonFormatter

    rendered = "".join(JsonFormatter().format(r) for r in caplog.records)
    assert '"error_code": "SYNC_FAILED"' in rendered
    assert '"resource": "subjects"' in rendered
    assert "private-name" not in rendered


@pytest.mark.parametrize(
    "row",
    [
        {"id": "s", "name": "Name", "faculty_id": "missing"},
        {"id": "s", "name": "Name", "faculty_id": None},
        {"id": "s", "name": "Name", "faculty_id": 1},
    ],
)
def test_missing_and_invalid_reference_cannot_create_user(row):
    with pytest.raises(HemisError):
        run_rows("students", row)
    assert not User.objects.exists() and not StudentProfile.objects.exists()


def test_invalid_profile_mapping_rolls_back_entire_page():
    adapter = seed()
    other = Faculty.objects.create(name="Other", hemis_id="other")
    row = dict(adapter.data["students"][0], faculty_id=other.hemis_id)
    with pytest.raises(HemisError, match="SYNC_FAILED"):
        run_rows("students", row)
    assert StudentProfile.objects.get().faculty.hemis_id == "demo-f1"


def test_student_employee_raw_id_overlap_is_namespaced():
    adapter = seed()
    run_rows("staff", dict(adapter.data["staff"][0], id="demo-s1"))
    assert User.objects.count() == 3
    assert (
        ExternalIdentity.objects.filter(external_id="student:demo-s1").get().user_id
        != ExternalIdentity.objects.filter(external_id="staff:demo-s1").get().user_id
    )


def test_conflicting_mapping_never_adopts_local_user():
    seed()
    user = User.objects.create_user("existing")
    ExternalIdentity.objects.create(user=user, source="HEMIS", external_id="student:conflict")
    with pytest.raises(HemisError, match="IDENTITY_CONFLICT"):
        run_rows("students", {"id": "conflict", "name": "Name", "faculty_id": "demo-f1"})
    assert not StudentProfile.objects.filter(user=user).exists()


def test_legacy_raw_identity_requires_explicit_reconciliation():
    seed()
    user = User.objects.create_user("legacy")
    ExternalIdentity.objects.create(user=user, source="HEMIS", external_id="legacy-raw")
    with pytest.raises(HemisError, match="IDENTITY_CONFLICT"):
        run_rows("students", {"id": "legacy-raw", "name": "Name", "faculty_id": "demo-f1"})
    assert not StudentProfile.objects.filter(hemis_id="legacy-raw").exists()
    assert User.objects.count() == 3


def test_long_raw_id_is_preserved():
    seed()
    raw = "x" * 128
    run_rows("students", {"id": raw, "name": "Name", "faculty_id": "demo-f1"})
    assert StudentProfile.objects.filter(hemis_id=raw).exists()
    assert ExternalIdentity.objects.filter(external_id="student:" + raw).exists()


def test_repeated_cursor_and_oversized_page_fail_without_import():
    with pytest.raises(HemisError, match="INVALID_PAGE"):
        sync_resource(
            "faculties",
            adapter=Pages(
                {"": Page((), "again"), "again": Page(({"id": "f", "name": "Name"},), "again")}
            ),
        )
    assert not Faculty.objects.exists()
    with pytest.raises(HemisError, match="INVALID_PAGE"):
        Page(tuple({} for _ in range(501))).validate()


def test_page_audit_failure_rolls_back_rows_and_cursor():
    from audit.services import record_event

    def fail_page(**kwargs):
        if kwargs["action"] == "hemis_page_imported":
            raise RuntimeError("audit unavailable")
        return record_event(**kwargs)

    with patch("integrations.hemis.services.record_event", side_effect=fail_page):
        with pytest.raises(HemisError, match="SYNC_FAILED"):
            run_rows("faculties", {"id": "f", "name": "Name"})
    assert not Faculty.objects.exists()
    assert SyncState.objects.get().cursor == ""
    assert SyncState.objects.get().records_processed == 0


def test_schedule_interface_validates_timezone_and_window():
    adapter = MockHemisAdapter()
    now = timezone.now()
    assert adapter.schedule(starts_at=now, ends_at=now + timedelta(hours=1)) == ()
    with pytest.raises(HemisError):
        adapter.schedule(starts_at=now.replace(tzinfo=None), ends_at=now)


@override_settings(HEMIS_ADAPTER="mock", HEMIS_ALLOW_MOCK=False)
def test_mock_forbidden_nonlocal_and_command_fail_closed():
    with pytest.raises(HemisError, match="NOT_CONFIGURED"):
        get_adapter()
    with pytest.raises(HemisError):
        MockHemisAdapter()
    with patch("integrations.hemis.tasks.sync_hemis.apply_async") as enqueue:
        with pytest.raises(CommandError):
            call_command("sync_hemis")
        enqueue.assert_not_called()


@override_settings(HEMIS_ADAPTER="mock")
def test_command_queues_without_fetching_and_task_runs_in_dependency_order():
    with patch("integrations.hemis.tasks.sync_hemis.apply_async") as enqueue:
        call_command("sync_hemis", stdout=io.StringIO())
        enqueue.assert_called_once_with(args=["all"], retry=False)
    assert not Faculty.objects.exists()
    sync_hemis.run()
    assert StudentProfile.objects.count() == 1 and StaffProfile.objects.count() == 1


@override_settings(HEMIS_ADAPTER="mock")
def test_queue_outage_is_safe_operator_error():
    with patch(
        "integrations.hemis.tasks.sync_hemis.apply_async", side_effect=RuntimeError("secret")
    ):
        with pytest.raises(CommandError) as error:
            call_command("sync_hemis")
    assert "secret" not in str(error.value)


def test_status_api_permissions_pagination_and_no_network():
    seed()
    client = APIClient()
    url = "/api/v1/admin/integrations/hemis/sync-status/"
    assert client.get(url).status_code == 401
    plain = User.objects.create_user("plain", is_staff=True, is_superuser=True)
    client.force_authenticate(plain)
    assert client.get(url).status_code == 403
    RoleGrant.objects.create(user=plain, role=Role.YOUTH_ADMIN, scope_type=ScopeType.GLOBAL)
    assert client.get(url).status_code == 403
    admin = User.objects.create_superuser("admin", "Strong-password!123")
    client.force_authenticate(admin)
    with patch("integrations.hemis.adapters.get_adapter", side_effect=AssertionError("network")):
        response = client.get(url)
    assert response.status_code == 200 and response.data["count"] == 6
    assert all("cursor" not in r for r in response.data["results"])
    assert client.post(url, {}, format="json").status_code == 405


def response_bytes(value):
    context = Mock()
    context.__enter__ = Mock(return_value=context)
    context.__exit__ = Mock(return_value=False)
    context.read.return_value = value
    return context


def transport():
    return JsonGetTransport(origin="https://hemis.example", token="secret", timeout=2)


def test_transport_timeout_retry_and_authorization_destination():
    http = transport()
    with (
        patch.object(
            http.opener,
            "open",
            side_effect=[TimeoutError(), URLError("offline"), response_bytes(b'{"items": []}')],
        ) as opened,
        patch("integrations.hemis.transport.time.sleep"),
    ):
        assert http.get("/documented/path?page=1") == {"items": []}
    assert opened.call_count == 3
    request = opened.call_args.args[0]
    assert request.full_url == "https://hemis.example/documented/path?page=1"
    assert request.get_header("Authorization") == "Bearer secret"
    assert request.get_method() == "GET"
    assert opened.call_args.kwargs["timeout"] == 2


@pytest.mark.parametrize("code,retries", [(401, 1), (403, 1), (302, 1), (429, 3), (503, 3)])
def test_transport_only_retries_safe_transient_failures(code, retries):
    http = transport()
    with (
        patch.object(
            http.opener,
            "open",
            side_effect=lambda *a, **kw: (_ for _ in ()).throw(
                HTTPError("https://hemis.example", code, "secret", {}, None)
            ),
        ) as opened,
        patch("integrations.hemis.transport.time.sleep"),
    ):
        with pytest.raises(HemisError) as error:
            http.get("/path")
    assert opened.call_count == retries and "secret" not in str(error.value)
    assert NoRedirect().redirect_request(None, None, None, None, None, None) is None


@pytest.mark.parametrize(
    "value",
    [b"private-invalid-json", b"[]", b"x" * (MAX_RESPONSE_BYTES + 1)],
    ids=["invalid-json", "non-object", "oversized"],
)
def test_transport_rejects_invalid_and_unbounded_payload(value):
    http = transport()
    with patch.object(http.opener, "open", return_value=response_bytes(value)) as opened:
        with pytest.raises(HemisError, match="INVALID_RESPONSE"):
            http.get("/path")
    assert opened.call_count == 1


@pytest.mark.parametrize(
    "path", ["//evil.example/a", "https://evil.example/", "/\\evil", "/a\n", "/a#fragment"]
)
def test_transport_rejects_external_and_unsafe_paths(path):
    http = transport()
    with patch.object(http.opener, "open") as opened:
        with pytest.raises(HemisError):
            http.get(path)
    opened.assert_not_called()


@override_settings(
    HEMIS_BASE_URL="https://hemis.example",
    HEMIS_API_TOKEN="only-in-env",
    HEMIS_HTTP_TIMEOUT=4,
    HEMIS_HTTP_ATTEMPTS=2,
)
def test_url_and_token_configuration():
    configured = JsonGetTransport.from_settings()
    assert configured.origin == "https://hemis.example"
    assert configured.timeout == 4 and configured.attempts == 2
    with pytest.raises(HemisError):
        JsonGetTransport(origin="http://hemis.example", token="secret")


def test_base_url_accepts_rest_prefix_and_blocks_path_escape():
    http = JsonGetTransport(origin="https://hemis.example/rest", token="secret")
    with patch.object(http.opener, "open", return_value=response_bytes(b"{}")) as opened:
        assert http.get("/versioned/resource") == {}
    assert opened.call_args.args[0].full_url == "https://hemis.example/rest/versioned/resource"
    for path in ["/../escape", "/%2e%2e/escape"]:
        with pytest.raises(HemisError):
            http.get(path)


@pytest.mark.django_db(transaction=True)
def test_concurrent_sync_rejected_while_source_is_slow():
    entered, release = Event(), Event()

    class SlowAdapter:
        def fetch_page(self, resource, cursor):
            entered.set()
            assert release.wait(10)
            return Page(({"id": "one", "name": "One"},))

    def background():
        close_old_connections()
        try:
            return sync_resource("faculties", adapter=SlowAdapter()).status
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(background)
        try:
            assert entered.wait(10)
            with pytest.raises(HemisError, match="SYNC_BUSY"):
                run_rows("subjects", {"id": "subject", "name": "Subject"})
            assert not Subject.objects.exists()
        finally:
            release.set()
        assert pending.result(timeout=10) == "SUCCEEDED"


@pytest.mark.redis_integration
@pytest.mark.django_db(transaction=True)
@override_settings(HEMIS_ADAPTER="mock")
def test_real_celery_redis_worker_imports_all_resources():
    from celery.contrib.testing.worker import start_worker
    from config.celery import app

    queue = "hemis-test-" + uuid4().hex
    with start_worker(
        app,
        pool="solo",
        concurrency=1,
        perform_ping_check=False,
        queues=[queue],
        shutdown_timeout=15,
    ):
        sync_hemis.apply_async(args=["all"], queue=queue, retry=False)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if SyncState.objects.filter(status="SUCCEEDED").count() == 6:
                break
            time.sleep(0.1)
        assert SyncState.objects.filter(status="SUCCEEDED").count() == 6
        assert StudentProfile.objects.count() == 1
        assert StaffProfile.objects.count() == 1
