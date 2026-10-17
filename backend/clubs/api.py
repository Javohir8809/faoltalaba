from accounts.serializers import ErrorSerializer, RoleGrantSerializer
from activities.policies import can_manage
from django.shortcuts import get_object_or_404
from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework import filters, generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import memberships, services, sessions
from .models import Club, ClubMembership, ClubSession
from .queries import visible_clubs
from .serializers import (
    AnalyticsSerializer,
    ClubCreateSerializer,
    ClubSerializer,
    ClubUpdateSerializer,
    DecisionSerializer,
    EmptyInputSerializer,
    LeaderInputSerializer,
    MembershipSerializer,
    RosterSerializer,
    ScheduleInputSerializer,
    ScheduleSerializer,
    SessionInputSerializer,
    SessionSerializer,
)


def validated(serializer_class, data) -> dict:
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class ClubQueryMixin:
    queryset = Club.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Club.objects.none()
        return visible_clubs(self.request.user)

    def club(self, *, manage: bool = False) -> Club:
        club = get_object_or_404(self.get_queryset(), pk=self.kwargs["pk"])
        if manage and not can_manage(self.request.user, club.activity):
            raise PermissionDenied()
        return club


class ClubListView(ClubQueryMixin, generics.ListCreateAPIView):
    serializer_class = ClubSerializer
    filter_backends = [*generics.GenericAPIView.filter_backends, filters.SearchFilter]
    filterset_fields = ["activity__state", "activity__faculty", "activity__department"]
    search_fields = ["activity__title", "activity__description"]

    @extend_schema(request=ClubCreateSerializer, responses={201: ClubSerializer})
    def post(self, request) -> Response:
        club = services.create_club(
            actor=request.user, **validated(ClubCreateSerializer, request.data)
        )
        return Response(ClubSerializer(self.get_queryset().get(pk=club.pk)).data, status=201)


class ClubDetailView(ClubQueryMixin, generics.RetrieveAPIView):
    serializer_class = ClubSerializer

    @extend_schema(request=ClubUpdateSerializer, responses=ClubSerializer)
    def patch(self, request, pk) -> Response:
        self.club(manage=True)
        services.update_timezone(
            actor=request.user, club_id=pk, **validated(ClubUpdateSerializer, request.data)
        )
        return Response(ClubSerializer(self.get_queryset().get(pk=pk)).data)


class ScheduleView(ClubQueryMixin, generics.GenericAPIView):
    serializer_class = ScheduleSerializer

    @extend_schema(responses=ScheduleSerializer(many=True))
    def get(self, request, pk) -> Response:
        return Response(ScheduleSerializer(self.club().schedule.all(), many=True).data)

    @extend_schema(request=ScheduleInputSerializer, responses=ScheduleSerializer(many=True))
    def put(self, request, pk) -> Response:
        self.club(manage=True)
        services.replace_schedule(
            actor=request.user, club_id=pk, **validated(ScheduleInputSerializer, request.data)
        )
        return self.get(request, pk)


class OwnMembershipView(generics.GenericAPIView):
    serializer_class = MembershipSerializer
    queryset = ClubMembership.objects.none()

    def own(self, actor, pk):
        return get_object_or_404(
            ClubMembership.objects.select_related("participant"),
            participant__activity_id=pk,
            participant__student__user=actor,
        )

    def get(self, request, pk) -> Response:
        return Response(MembershipSerializer(self.own(request.user, pk)).data)

    @extend_schema(request=EmptyInputSerializer, responses=MembershipSerializer)
    def post(self, request, pk) -> Response:
        get_object_or_404(visible_clubs(request.user), pk=pk)
        validated(EmptyInputSerializer, request.data)
        result = memberships.join_club(actor=request.user, club_id=pk)
        return Response(MembershipSerializer(result).data)

    @extend_schema(responses={204: None})
    def delete(self, request, pk) -> Response:
        self.own(request.user, pk)
        memberships.leave_club(actor=request.user, club_id=pk)
        return Response(status=204)


class MemberListView(ClubQueryMixin, generics.ListAPIView):
    serializer_class = RosterSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ClubMembership.objects.none()
        club = get_object_or_404(visible_clubs(self.request.user), pk=self.kwargs["pk"])
        if not can_manage(self.request.user, club.activity):
            raise PermissionDenied()
        return ClubMembership.objects.filter(participant__activity_id=club.pk).select_related(
            "participant__student"
        )


class DecisionView(ClubQueryMixin, generics.GenericAPIView):
    serializer_class = DecisionSerializer

    @extend_schema(responses=MembershipSerializer)
    def post(self, request, pk, membership_id) -> Response:
        self.club(manage=True)
        result = memberships.decide_membership(
            actor=request.user,
            club_id=pk,
            membership_id=membership_id,
            **validated(DecisionSerializer, request.data),
        )
        return Response(MembershipSerializer(result).data)


class LeaderView(ClubQueryMixin, generics.GenericAPIView):
    serializer_class = LeaderInputSerializer

    @extend_schema(responses=RoleGrantSerializer)
    def post(self, request, pk) -> Response:
        self.club(manage=True)
        grant = services.assign_leader(
            actor=request.user, club_id=pk, **validated(LeaderInputSerializer, request.data)
        )
        return Response(RoleGrantSerializer(grant).data)


class RevokeLeaderView(ClubQueryMixin, generics.GenericAPIView):
    serializer_class = EmptyInputSerializer

    @extend_schema(responses={204: None})
    def delete(self, request, pk, grant_id) -> Response:
        self.club(manage=True)
        services.revoke_leader(actor=request.user, club_id=pk, grant_id=grant_id)
        return Response(status=204)


class SessionListView(ClubQueryMixin, generics.ListCreateAPIView):
    serializer_class = SessionSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ClubSession.objects.none()
        club = get_object_or_404(visible_clubs(self.request.user), pk=self.kwargs["pk"])
        return ClubSession.objects.filter(club=club)

    @extend_schema(
        request=SessionInputSerializer,
        responses={
            200: SessionSerializer,
            400: ErrorSerializer,
            403: ErrorSerializer,
            409: ErrorSerializer,
        },
    )
    def post(self, request, pk) -> Response:
        get_object_or_404(visible_clubs(request.user), pk=pk)
        result = sessions.create_session(
            actor=request.user, club_id=pk, **validated(SessionInputSerializer, request.data)
        )
        return Response(SessionSerializer(result).data)


class OpenSessionView(ClubQueryMixin, generics.GenericAPIView):
    serializer_class = EmptyInputSerializer
    opening = True

    @extend_schema(responses=SessionSerializer)
    def post(self, request, pk, session_id) -> Response:
        self.club(manage=True)
        validated(EmptyInputSerializer, request.data)
        result = sessions.change_session(
            actor=request.user, club_id=pk, session_id=session_id, opening=self.opening
        )
        return Response(SessionSerializer(result).data)


class CloseSessionView(OpenSessionView):
    opening = False


class AnalyticsView(ClubQueryMixin, generics.GenericAPIView):
    serializer_class = AnalyticsSerializer

    def get(self, request, pk) -> Response:
        return Response(AnalyticsSerializer(self.club(manage=True)).data)


urlpatterns = [
    path("", ClubListView.as_view(), name="club-list"),
    path("<uuid:pk>/", ClubDetailView.as_view(), name="club-detail"),
    path("<uuid:pk>/schedule/", ScheduleView.as_view(), name="club-schedule"),
    path("<uuid:pk>/membership/", OwnMembershipView.as_view(), name="club-membership"),
    path("<uuid:pk>/members/", MemberListView.as_view(), name="club-members"),
    path(
        "<uuid:pk>/members/<uuid:membership_id>/decision/",
        DecisionView.as_view(),
        name="club-member-decision",
    ),
    path("<uuid:pk>/leaders/", LeaderView.as_view(), name="club-leader"),
    path(
        "<uuid:pk>/leaders/<uuid:grant_id>/", RevokeLeaderView.as_view(), name="club-leader-revoke"
    ),
    path("<uuid:pk>/sessions/", SessionListView.as_view(), name="club-sessions"),
    path(
        "<uuid:pk>/sessions/<uuid:session_id>/open/",
        OpenSessionView.as_view(),
        name="club-session-open",
    ),
    path(
        "<uuid:pk>/sessions/<uuid:session_id>/close/",
        CloseSessionView.as_view(),
        name="club-session-close",
    ),
    path("<uuid:pk>/analytics/", AnalyticsView.as_view(), name="club-analytics"),
]
