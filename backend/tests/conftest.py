"""Test database DDL guard for immutable audit rows and pytest flush teardown."""

import pytest
from django.db import connection


@pytest.fixture(autouse=True)
def audit_test_database_guard(request, django_db_setup, django_db_blocker):
    # Only test tooling may disable TRUNCATE guards to let Django flush its disposable DB.
    # Runtime migrations and application code always keep both guards enabled.
    with django_db_blocker.unblock(), connection.cursor() as cursor:
        assert connection.settings_dict["NAME"].startswith("test_")
        cursor.execute("ALTER TABLE audit_auditevent ENABLE TRIGGER audit_immutable_rows")
        cursor.execute("ALTER TABLE audit_auditevent ENABLE TRIGGER audit_immutable_truncate")
        for table, trigger in [
            ("attendance_attendancechange", "attendance_changes_truncate"),
            ("attendance_attendancerecord", "attendance_records_truncate"),
            ("attendance_studentcardmapping", "attendance_cards_truncate"),
        ]:
            cursor.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")
    yield
    marker = request.node.get_closest_marker("django_db")
    if marker and marker.kwargs.get("transaction", False):
        with django_db_blocker.unblock(), connection.cursor() as cursor:
            assert connection.settings_dict["NAME"].startswith("test_")
            cursor.execute("ALTER TABLE audit_auditevent DISABLE TRIGGER audit_immutable_truncate")

            for table, trigger in [
                ("attendance_attendancechange", "attendance_changes_truncate"),
                ("attendance_attendancerecord", "attendance_records_truncate"),
                ("attendance_studentcardmapping", "attendance_cards_truncate"),
            ]:
                cursor.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
