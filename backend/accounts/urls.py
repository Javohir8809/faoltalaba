from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    MeView,
    RefreshView,
    RoleListView,
    RoleRevokeView,
    UserDetailView,
    UserListView,
    UserStatusView,
)

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", RefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("admin/users/", UserListView.as_view(), name="user-list"),
    path("admin/users/<uuid:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("admin/users/<uuid:pk>/status/", UserStatusView.as_view(), name="user-status"),
    path("admin/users/<uuid:pk>/roles/", RoleListView.as_view(), name="user-roles"),
    path(
        "admin/users/<uuid:pk>/roles/<uuid:grant_id>/", RoleRevokeView.as_view(), name="role-revoke"
    ),
]
