from rest_framework import serializers

from .models import Role, RoleGrant, ScopeType, User


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=False)
    password = serializers.CharField(max_length=1024, write_only=True, trim_whitespace=False)


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class RoleGrantSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoleGrant
        fields = ["id", "role", "scope_type", "scope_id"]
        read_only_fields = fields


class GrantInputSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)
    scope_type = serializers.ChoiceField(choices=ScopeType.choices)
    scope_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class UserSerializer(serializers.ModelSerializer):
    roles = RoleGrantSerializer(source="role_grants", many=True, read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "is_active", "roles"]
        read_only_fields = fields


class StatusSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class ErrorBodySerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField()


class ErrorSerializer(serializers.Serializer):
    error = ErrorBodySerializer()
