from accounts.policies import CanManageAccess
from activities.models import Activity
from activities.policies import managed_query
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from . import serializers as s
from . import services
from .models import AttendanceChange, AttendanceDevice, AttendanceRecord, Method, StudentCardMapping
from .session_policy import visible_sessions
from .throttling import AttendanceThrottle


def validated(cls, data) -> dict:
    serializer = cls(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


class CanOperateAttendance(BasePermission):
    def has_permission(self, request, view) -> bool:
        services.manager(request.user)
        return True


class OperatorView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, CanOperateAttendance]
    throttle_classes = [AttendanceThrottle]


class DeviceList(OperatorView, generics.ListAPIView):
    serializer_class = s.DeviceSerializer
    queryset = AttendanceDevice.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return AttendanceDevice.objects.filter(owner=self.request.user).order_by("created_at", "id")

    @extend_schema(request=s.DeviceInput, responses={201: s.DeviceSerializer})
    def post(self, request):
        device = services.save_device(actor=request.user, **validated(s.DeviceInput, request.data))
        return Response(s.DeviceSerializer(device).data, status=201)


class DeviceDetail(OperatorView):
    serializer_class = s.DeviceSerializer
    queryset = AttendanceDevice.objects.none()

    @extend_schema(request=s.DeviceUpdate, responses=s.DeviceSerializer)
    def patch(self, request, pk):
        device = services.save_device(
            actor=request.user, device_id=pk, **validated(s.DeviceUpdate, request.data)
        )
        return Response(s.DeviceSerializer(device).data)


class CardList(OperatorView, generics.ListAPIView):
    permission_classes = [IsAuthenticated, CanManageAccess]
    serializer_class = s.CardSerializer
    queryset = StudentCardMapping.objects.order_by("created_at", "id")

    @extend_schema(request=s.CardInput, responses={201: s.CardSerializer})
    def post(self, request):
        card = services.enroll_card(actor=request.user, **validated(s.CardInput, request.data))
        return Response(s.CardSerializer(card).data, status=201)


class CardRevoke(OperatorView):
    permission_classes = [IsAuthenticated, CanManageAccess]
    serializer_class = s.CardSerializer
    queryset = StudentCardMapping.objects.none()

    @extend_schema(request=s.ReasonInput, responses=s.CardSerializer)
    def post(self, request, pk):
        card = services.revoke_card(
            actor=request.user, card_id=pk, **validated(s.ReasonInput, request.data)
        )
        return Response(s.CardSerializer(card).data)


class SessionCheckIn(OperatorView):
    serializer_class = s.RecordSerializer
    queryset = AttendanceRecord.objects.none()

    @extend_schema(request=s.CheckInInput, responses=s.RecordSerializer)
    def post(self, request, pk):
        record = services.check_in(
            actor=request.user, session_id=pk, **validated(s.CheckInInput, request.data)
        )
        return Response(s.RecordSerializer(record).data)


class SessionRecords(OperatorView, generics.ListAPIView):
    serializer_class = s.RecordSerializer
    queryset = AttendanceRecord.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        session = get_object_or_404(visible_sessions(self.request.user), pk=self.kwargs["pk"])
        return AttendanceRecord.objects.filter(session=session).select_related("session")


class SessionStats(OperatorView):
    serializer_class = s.AttendanceStatsSerializer
    queryset = AttendanceRecord.objects.none()

    def get(self, request, pk):
        session = get_object_or_404(visible_sessions(request.user), pk=pk)
        records = AttendanceRecord.objects.filter(session=session)
        counts = records.aggregate(
            total=Count("id"),
            present=Count("id", filter=Q(status="PRESENT")),
            voided=Count("id", filter=Q(status="VOIDED")),
        )
        counts["by_method"] = {
            method: records.filter(method=method, status="PRESENT").count()
            for method in Method.values
        }
        return Response(s.AttendanceStatsSerializer(counts).data)


class RecordDetail(OperatorView, generics.RetrieveAPIView):
    serializer_class = s.RecordSerializer
    queryset = AttendanceRecord.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return AttendanceRecord.objects.filter(
            session__club_id__in=Activity.objects.filter(managed_query(self.request.user)).values(
                "pk"
            )
        ).select_related("session")


class RecordCorrection(RecordDetail):
    http_method_names = ["post", "options"]

    @extend_schema(request=s.CorrectionInput, responses=s.RecordSerializer)
    def post(self, request, pk):
        self.get_object()
        record = services.correct_record(
            actor=request.user, record_id=pk, **validated(s.CorrectionInput, request.data)
        )
        return Response(s.RecordSerializer(record).data)


class RecordChanges(OperatorView, generics.ListAPIView):
    serializer_class = s.ChangeSerializer
    queryset = AttendanceChange.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        record = get_object_or_404(
            AttendanceRecord.objects.filter(
                session__club_id__in=Activity.objects.filter(
                    managed_query(self.request.user)
                ).values("pk")
            ),
            pk=self.kwargs["pk"],
        )
        return record.changes.all()


class OwnHistory(generics.ListAPIView):
    serializer_class = s.HistorySerializer
    queryset = AttendanceRecord.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return AttendanceRecord.objects.filter(student__user=self.request.user).select_related(
            "session__club__activity"
        )


urlpatterns = [
    path("attendance/devices/", DeviceList.as_view()),
    path("attendance/devices/<uuid:pk>/", DeviceDetail.as_view()),
    path("attendance/card-mappings/", CardList.as_view()),
    path("attendance/card-mappings/<uuid:pk>/revoke/", CardRevoke.as_view()),
    path("attendance/sessions/<uuid:pk>/check-in/", SessionCheckIn.as_view()),
    path("attendance/sessions/<uuid:pk>/records/", SessionRecords.as_view()),
    path("attendance/sessions/<uuid:pk>/stats/", SessionStats.as_view()),
    path("attendance/records/<uuid:pk>/", RecordDetail.as_view()),
    path("attendance/records/<uuid:pk>/corrections/", RecordCorrection.as_view()),
    path("attendance/records/<uuid:pk>/changes/", RecordChanges.as_view()),
    path("students/me/activity-history/", OwnHistory.as_view()),
]
