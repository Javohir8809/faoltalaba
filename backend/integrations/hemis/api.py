from accounts.models import Role, ScopeType
from accounts.serializers import ErrorSerializer
from django.urls import path
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, serializers
from rest_framework.permissions import BasePermission, IsAuthenticated

from .models import SyncState


class CanReadSyncStatus(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_active
            and request.user.role_grants.filter(
                role=Role.SUPERADMIN, scope_type=ScopeType.GLOBAL
            ).exists()
        )


class SyncStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncState
        fields = [
            "id",
            "resource",
            "status",
            "last_attempt_at",
            "last_success_at",
            "error_code",
            "records_processed",
        ]
        read_only_fields = fields


@extend_schema_view(
    get=extend_schema(
        tags=["HEMIS"],
        responses={200: SyncStateSerializer(many=True), 401: ErrorSerializer, 403: ErrorSerializer},
    )
)
class SyncStatusView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, CanReadSyncStatus]
    serializer_class = SyncStateSerializer
    queryset = SyncState.objects.all()


urlpatterns = [path("sync-status/", SyncStatusView.as_view(), name="hemis-sync-status")]
