"""Apply one normalized source record. Caller supplies the page transaction."""

from uuid import uuid4

from accounts.models import ExternalIdentity, User
from django.db.models import Model
from organizations.models import Department, Faculty, Group, Subject
from staff.models import StaffProfile
from students.models import StudentProfile

from .adapters import HemisError
from .models import Resource

MODELS = {
    Resource.FACULTIES: Faculty,
    Resource.DEPARTMENTS: Department,
    Resource.GROUPS: Group,
    Resource.SUBJECTS: Subject,
    Resource.STUDENTS: StudentProfile,
    Resource.STAFF: StaffProfile,
}


def text(row: dict, key: str, *, limit: int = 128) -> str:
    value = row.get(key)
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > limit
        or any(ord(c) < 32 for c in value)
    ):
        raise HemisError("INVALID_RECORD")
    return value


def reference[Reference: Model](model: type[Reference], row: dict, key: str) -> Reference:
    value = text(row, key)
    try:
        return model.objects.get(hemis_id=value)
    except model.DoesNotExist:
        raise HemisError("MISSING_REFERENCE") from None


def apply_record(resource: Resource, row: dict) -> None:
    external_id = text(row, "id")
    model = MODELS[resource]
    deleted = row.get("deleted", False)
    if not isinstance(deleted, bool):
        raise HemisError("INVALID_RECORD")
    if deleted:
        # Unknown tombstones never create incomplete profiles or remove history.
        model.objects.filter(hemis_id=external_id).update(hemis_active=False)
        return
    values = {"hemis_active": True}
    name_field = "full_name" if resource in {Resource.STUDENTS, Resource.STAFF} else "name"
    values[name_field] = text(row, "name", limit=200)
    if resource in {Resource.DEPARTMENTS, Resource.GROUPS, Resource.STUDENTS, Resource.STAFF}:
        values["faculty"] = reference(Faculty, row, "faculty_id")
    if resource in {Resource.STUDENTS, Resource.STAFF}:
        # Missing/null optional fields preserve prior values rather than clearing them.
        if row.get("department_id") is not None:
            values["department"] = reference(Department, row, "department_id")
        if resource == Resource.STUDENTS and row.get("group_id") is not None:
            values["group"] = reference(Group, row, "group_id")
        profile = model.objects.select_for_update().filter(hemis_id=external_id).first()
        namespace = "student" if resource == Resource.STUDENTS else "staff"
        mapping_id = f"{namespace}:{external_id}"
        identity = ExternalIdentity.objects.filter(source="HEMIS", external_id=mapping_id).first()
        if profile is None:
            # Never attach a source identity to a guessed local account.
            if (
                identity
                or ExternalIdentity.objects.filter(source="HEMIS", external_id=external_id).exists()
            ):
                raise HemisError("IDENTITY_CONFLICT")
            user = User.objects.create_user(username=f"hemis-{uuid4()}")
            profile = model(user=user, hemis_id=external_id)
            ExternalIdentity.objects.create(source="HEMIS", external_id=mapping_id, user=user)
        elif identity is None or identity.user_id != profile.user_id:
            raise HemisError("IDENTITY_CONFLICT")
        for key, value in values.items():
            setattr(profile, key, value)
        profile.save()
    else:
        model.objects.update_or_create(hemis_id=external_id, defaults=values)
