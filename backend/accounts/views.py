from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services, tokens
from .models import RoleGrant, User
from .policies import CanManageAccess, CanReadUsers, visible_users
from .serializers import (
    ErrorSerializer,
    GrantInputSerializer,
    LoginSerializer,
    RefreshSerializer,
    RoleGrantSerializer,
    StatusSerializer,
    TokenPairSerializer,
    UserSerializer,
)
from .throttling import AuthThrottle


class PublicAuthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthThrottle]
    throttle_account = False

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def get_authenticate_header(self, request) -> str:
        return "Bearer"


class LoginView(PublicAuthView):
    throttle_account = True

    @extend_schema(
        request=LoginSerializer,
        responses={
            200: TokenPairSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            429: ErrorSerializer,
            503: ErrorSerializer,
        },
        auth=[],
        tags=["Auth"],
    )
    def post(self, request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(tokens.login(**serializer.validated_data))


class RefreshView(PublicAuthView):
    @extend_schema(
        request=RefreshSerializer,
        responses={
            200: TokenPairSerializer,
            400: ErrorSerializer,
            401: ErrorSerializer,
            429: ErrorSerializer,
            503: ErrorSerializer,
        },
        auth=[],
        tags=["Auth"],
    )
    def post(self, request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(tokens.refresh(serializer.validated_data["refresh"]))


class LogoutView(PublicAuthView):
    @extend_schema(request=RefreshSerializer, responses={204: None}, auth=[], tags=["Auth"])
    def post(self, request) -> Response:
        serializer = RefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens.logout(serializer.validated_data["refresh"])
        return Response(status=204)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserSerializer, tags=["Auth"])
    def get(self, request) -> Response:
        user = User.objects.prefetch_related("role_grants").get(pk=request.user.pk)
        return Response(UserSerializer(user).data)


class UserListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, CanReadUsers]
    serializer_class = UserSerializer
    queryset = User.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        return visible_users(self.request.user)


class UserDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, CanReadUsers]
    serializer_class = UserSerializer
    queryset = User.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return User.objects.none()
        return visible_users(self.request.user)


class UserStatusView(APIView):
    permission_classes = [IsAuthenticated, CanManageAccess]

    @extend_schema(request=StatusSerializer, responses=UserSerializer, tags=["Access"])
    def patch(self, request, pk) -> Response:
        serializer = StatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = get_object_or_404(User, pk=pk)
        updated = services.set_user_status(
            actor=request.user, target=target, **serializer.validated_data
        )
        return Response(UserSerializer(updated).data)


class RoleListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, CanManageAccess]
    serializer_class = RoleGrantSerializer
    queryset = RoleGrant.objects.none()

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return RoleGrant.objects.none()
        target = get_object_or_404(User, pk=self.kwargs["pk"])
        return RoleGrant.objects.filter(user=target).order_by("created_at", "id")

    @extend_schema(
        request=GrantInputSerializer, responses={201: RoleGrantSerializer}, tags=["Access"]
    )
    def post(self, request, pk) -> Response:
        serializer = GrantInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = get_object_or_404(User, pk=pk)
        grant = services.grant_role(actor=request.user, target=target, **serializer.validated_data)
        return Response(RoleGrantSerializer(grant).data, status=201)


class RoleRevokeView(APIView):
    permission_classes = [IsAuthenticated, CanManageAccess]

    @extend_schema(responses={204: None}, tags=["Access"])
    def delete(self, request, pk, grant_id) -> Response:
        grant = get_object_or_404(RoleGrant, pk=grant_id, user_id=pk)
        services.revoke_role(actor=request.user, grant=grant)
        return Response(status=204)
