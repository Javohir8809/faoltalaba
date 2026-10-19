from activities.serializers import StrictInputMixin
from rest_framework import serializers

from .models import (
    AttendanceChange,
    AttendanceDevice,
    AttendanceRecord,
    AttendanceStatus,
    Method,
    StudentCardMapping,
)


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceDevice
        fields = [
            "id",
            "installation_id",
            "label",
            "platform",
            "nfc_supported",
            "camera_supported",
            "is_active",
            "created_at",
            "last_seen_at",
        ]
        read_only_fields = fields


class DeviceInput(StrictInputMixin, serializers.Serializer):
    installation_id = serializers.UUIDField()
    label = serializers.CharField(max_length=80)
    platform = serializers.ChoiceField(
        choices=AttendanceDevice._meta.get_field("platform").choices, default="UNKNOWN"
    )
    nfc_supported = serializers.BooleanField(required=False, allow_null=True)
    camera_supported = serializers.BooleanField(required=False, allow_null=True)


class DeviceUpdate(StrictInputMixin, serializers.Serializer):
    label = serializers.CharField(max_length=80, required=False)
    platform = serializers.ChoiceField(
        choices=AttendanceDevice._meta.get_field("platform").choices, required=False
    )
    nfc_supported = serializers.BooleanField(required=False, allow_null=True)
    camera_supported = serializers.BooleanField(required=False, allow_null=True)
    is_active = serializers.BooleanField(required=False)


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentCardMapping
        fields = [
            "id",
            "student_id",
            "kind",
            "protocol",
            "variant",
            "uid_readable",
            "created_at",
            "enrolled_by_id",
            "revoked_at",
            "revoked_by_id",
            "revocation_reason",
        ]
        read_only_fields = fields


class CardInput(StrictInputMixin, serializers.Serializer):
    student_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=["NFC", "QR"])
    token = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
    protocol = serializers.ChoiceField(
        choices=StudentCardMapping._meta.get_field("protocol").choices, default="UNKNOWN"
    )
    variant = serializers.CharField(max_length=64, allow_blank=True, required=False)
    uid_readable = serializers.BooleanField(allow_null=True, required=False)


class ReasonInput(StrictInputMixin, serializers.Serializer):
    reason = serializers.CharField(max_length=500)


class CheckInInput(StrictInputMixin, serializers.Serializer):
    method = serializers.ChoiceField(choices=Method.choices)
    token = serializers.CharField(
        max_length=256, trim_whitespace=False, write_only=True, required=False
    )
    student_id = serializers.UUIDField(required=False)
    reason = serializers.CharField(max_length=500, required=False)
    device_id = serializers.UUIDField(required=False)
    note = serializers.CharField(max_length=500, allow_blank=True, required=False)

    def validate(self, attrs):
        manual = attrs["method"] == "MANUAL"
        if manual and ("student_id" not in attrs or "reason" not in attrs or "token" in attrs):
            raise serializers.ValidationError("Talaba va sabab majburiy.")
        if not manual and ("token" not in attrs or "student_id" in attrs or "reason" in attrs):
            raise serializers.ValidationError("Skanerlash identifikatori kerak.")
        return attrs


class CorrectionInput(ReasonInput):
    status = serializers.ChoiceField(choices=AttendanceStatus.choices)
    note = serializers.CharField(max_length=500, allow_blank=True, required=False)
    expected_version = serializers.IntegerField(min_value=1)
    idempotency_key = serializers.UUIDField()


class RecordSerializer(serializers.ModelSerializer):
    activity_id = serializers.UUIDField(source="session.club_id", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "activity_id",
            "session_id",
            "student_id",
            "checked_in_at",
            "method",
            "status",
            "recorded_by_id",
            "device_id",
            "note",
            "version",
        ]
        read_only_fields = fields


class HistorySerializer(serializers.ModelSerializer):
    activity_id = serializers.UUIDField(source="session.club_id", read_only=True)
    activity_title = serializers.CharField(source="session.club.activity.title", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id",
            "activity_id",
            "activity_title",
            "session_id",
            "checked_in_at",
            "method",
            "status",
            "version",
        ]
        read_only_fields = fields


class ChangeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceChange
        fields = [
            "id",
            "record_id",
            "version",
            "actor_id",
            "created_at",
            "action",
            "reason",
            "previous_status",
            "new_status",
            "previous_note",
            "new_note",
        ]
        read_only_fields = fields


class AttendanceStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    present = serializers.IntegerField()
    voided = serializers.IntegerField()
    by_method = serializers.DictField(child=serializers.IntegerField())
