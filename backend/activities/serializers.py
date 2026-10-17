from rest_framework import serializers

from .models import Activity, ActivityRole, Lifecycle


class StrictInputMixin:
    def to_internal_value(self, data):
        if isinstance(data, dict):
            writable = {key for key, field in self.fields.items() if not field.read_only}
            if not data.keys() <= writable:
                raise serializers.ValidationError(
                    {"activity": "Noma'lum yoki o'zgarmas maydon."}, code="immutable_field"
                )
        return super().to_internal_value(data)


class ActivitySerializer(StrictInputMixin, serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = [
            "id",
            "title",
            "description",
            "type",
            "organizer",
            "faculty",
            "department",
            "state",
            "visibility",
            "audience",
            "audience_faculty",
            "audience_department",
            "audience_group",
            "capacity",
            "starts_at",
            "ends_at",
            "venue",
            "registration_policy",
            "attendance_policy",
            "evidence_required",
            "result_policy",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organizer", "state", "published_at", "created_at", "updated_at"]

    def to_internal_value(self, data):
        if (
            self.instance is not None
            and isinstance(data, dict)
            and data.keys() & {"type", "faculty", "department"}
        ):
            raise serializers.ValidationError(
                {"activity": "Tashkilot va tur o'zgartirilmaydi."}, code="immutable_field"
            )
        return super().to_internal_value(data)

    def validate_capacity(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError("Sig'im musbat bo'lishi kerak.")
        return value


class TransitionSerializer(StrictInputMixin, serializers.Serializer):
    state = serializers.ChoiceField(choices=Lifecycle.choices)


class ActivityRoleSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="grant.user_id", read_only=True)
    role = serializers.CharField(source="grant.role", read_only=True)

    class Meta:
        model = ActivityRole
        fields = ["id", "grant", "user_id", "role"]
        read_only_fields = fields
