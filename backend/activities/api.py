from accounts.serializers import ErrorSerializer
from django.shortcuts import get_object_or_404
from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import services
from .models import Activity, ActivityRole
from .policies import can_manage, visible_activities
from .serializers import ActivityRoleSerializer, ActivitySerializer, TransitionSerializer


class ActivityQueryMixin:
    queryset = Activity.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Activity.objects.none()
        return visible_activities(self.request.user)


class ActivityListView(ActivityQueryMixin, generics.ListCreateAPIView):
    serializer_class = ActivitySerializer
    filter_backends = [
        *generics.GenericAPIView.filter_backends,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["type", "state", "faculty", "department", "audience"]
    search_fields = ["title", "description", "venue"]
    ordering_fields = ["created_at", "starts_at", "title"]

    def perform_create(self, serializer) -> None:
        serializer.instance = services.create_activity(
            actor=self.request.user, data=serializer.validated_data
        )


class ActivityDetailView(ActivityQueryMixin, generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ActivitySerializer

    def perform_update(self, serializer) -> None:
        serializer.instance = services.update_activity(
            actor=self.request.user,
            activity_id=serializer.instance.id,
            data=serializer.validated_data,
        )

    def perform_destroy(self, instance) -> None:
        services.archive_activity(actor=self.request.user, activity_id=instance.id)


class ActivityTransitionView(ActivityQueryMixin, generics.GenericAPIView):
    serializer_class = TransitionSerializer

    @extend_schema(
        responses={
            200: ActivitySerializer,
            400: ErrorSerializer,
            403: ErrorSerializer,
            404: ErrorSerializer,
        }
    )
    def post(self, request, pk) -> Response:
        activity = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = services.transition_activity(
            actor=request.user, activity_id=activity.id, **serializer.validated_data
        )
        return Response(ActivitySerializer(updated).data, status=status.HTTP_200_OK)


class ActivityRoleListView(generics.ListAPIView):
    serializer_class = ActivityRoleSerializer
    queryset = ActivityRole.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ActivityRole.objects.none()
        activity = get_object_or_404(visible_activities(self.request.user), pk=self.kwargs["pk"])
        if not can_manage(self.request.user, activity):
            raise PermissionDenied()
        return (
            ActivityRole.objects.filter(activity=activity)
            .select_related("grant__user")
            .order_by("id")
        )


urlpatterns = [
    path("", ActivityListView.as_view(), name="activity-list"),
    path("<uuid:pk>/", ActivityDetailView.as_view(), name="activity-detail"),
    path("<uuid:pk>/transitions/", ActivityTransitionView.as_view(), name="activity-transition"),
    path("<uuid:pk>/roles/", ActivityRoleListView.as_view(), name="activity-roles"),
]
