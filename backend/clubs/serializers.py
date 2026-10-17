from uuid import UUID

from activities.serializers import ActivitySerializer, StrictInputMixin
from rest_framework import serializers

from .models import Club, ClubMembership, ClubSchedule, ClubSession


class ClubActivityInput(ActivitySerializer):
    class Meta(ActivitySerializer.Meta):
        fields = [field for field in ActivitySerializer.Meta.fields if field != "type"]


class ClubCreateSerializer(StrictInputMixin, serializers.Serializer):
    activity = ClubActivityInput()
    timezone_name = serializers.CharField(max_length=64, default="Asia/Tashkent")


class ClubUpdateSerializer(StrictInputMixin, serializers.Serializer):
    timezone_name = serializers.CharField(max_length=64)


class ClubSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="activity_id", read_only=True)
    activity = ActivitySerializer(read_only=True)
    active_members = serializers.IntegerField(read_only=True)
    last_session_at = serializers.DateTimeField(read_only=True, allow_null=True)
    dormant = serializers.BooleanField(read_only=True)
    leader_ids = serializers.SerializerMethodField()

    def get_leader_ids(self, obj) -> list[UUID]:
        return [assignment.grant.user_id for assignment in obj.activity.club_leader_assignments]

    class Meta:
        model = Club
        fields = [
            "id",
            "activity",
            "timezone_name",
            "active_members",
            "last_session_at",
            "dormant",
            "leader_ids",
        ]
        read_only_fields = fields


class ScheduleSlotSerializer(StrictInputMixin, serializers.Serializer):
    weekday = serializers.IntegerField(min_value=1, max_value=7)
    starts_at = serializers.TimeField()
    ends_at = serializers.TimeField()


class ScheduleInputSerializer(StrictInputMixin, serializers.Serializer):
    slots = ScheduleSlotSerializer(many=True, max_length=21)


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubSchedule
        fields = ["id", "weekday", "starts_at", "ends_at"]
        read_only_fields = fields


class EmptyInputSerializer(StrictInputMixin, serializers.Serializer):
    pass


class MembershipSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="participant_id", read_only=True)
    student_id = serializers.UUIDField(source="participant.student_id", read_only=True)
    club_id = serializers.UUIDField(source="participant.activity_id", read_only=True)

    class Meta:
        model = ClubMembership
        fields = [
            "id",
            "club_id",
            "student_id",
            "status",
            "reviewed_at",
            "reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class RosterSerializer(MembershipSerializer):
    full_name = serializers.CharField(source="participant.student.full_name", read_only=True)

    class Meta(MembershipSerializer.Meta):
        fields = [*MembershipSerializer.Meta.fields, "full_name"]
        read_only_fields = fields


class DecisionSerializer(StrictInputMixin, serializers.Serializer):
    decision = serializers.ChoiceField(choices=["APPROVE", "REJECT"])
    reason = serializers.CharField(max_length=500, required=False, default="", allow_blank=True)


class LeaderInputSerializer(StrictInputMixin, serializers.Serializer):
    user_id = serializers.UUIDField()


class SessionInputSerializer(StrictInputMixin, serializers.Serializer):
    idempotency_key = serializers.UUIDField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class SessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClubSession
        fields = ["id", "club", "starts_at", "ends_at", "status", "opened_at", "closed_at"]
        read_only_fields = fields


class AnalyticsSerializer(serializers.Serializer):
    active_members = serializers.IntegerField(read_only=True)
    pending_members = serializers.IntegerField(read_only=True)
    closed_sessions = serializers.IntegerField(read_only=True)
    last_session_at = serializers.DateTimeField(read_only=True, allow_null=True)
    dormant = serializers.BooleanField(read_only=True)
