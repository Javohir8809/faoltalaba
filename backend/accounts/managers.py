from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

if TYPE_CHECKING:
    from .models import User


class UserManager(BaseUserManager):
    @transaction.atomic
    def create_user(self, username: str, password: str | None = None, **extra_fields) -> User:
        if not username or username != username.strip():
            raise ValueError("Username is required without surrounding whitespace")
        user = self.model(username=username, **extra_fields)
        if password is not None:
            validate_password(password, user)
        user.set_password(password)
        user.full_clean()
        user.save(using=self._db)
        from audit.services import record_event

        record_event(actor_id=None, action="user_created", object_id=user.id)
        return user

    @transaction.atomic
    def create_superuser(self, username: str, password: str | None = None, **extra_fields) -> User:
        if not password:
            raise ValueError("Superadmin password is required")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Invalid superuser flags")
        user = self.create_user(username, password, **extra_fields)
        from audit.services import record_event

        from .models import Role, RoleGrant, ScopeType

        RoleGrant.objects.create(user=user, role=Role.SUPERADMIN, scope_type=ScopeType.GLOBAL)
        record_event(actor_id=user.id, action="superadmin_bootstrapped", object_id=user.id)
        return user
