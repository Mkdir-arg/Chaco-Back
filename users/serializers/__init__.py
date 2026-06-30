from django.contrib.auth.models import Group, User
from rest_framework import serializers

from ..models import Profile


class GroupSerializer(serializers.ModelSerializer):
    """Serializer para Group"""

    class Meta:
        model = Group
        fields = ["id", "name"]


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer para Profile"""

    class Meta:
        model = Profile
        fields = ["id", "dark_mode"]


class UserSerializer(serializers.ModelSerializer):
    """Serializer para User"""

    profile = ProfileSerializer(read_only=True)
    groups = GroupSerializer(many=True, read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "date_joined",
            "last_login",
            "groups",
            "profile",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear usuarios"""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    groups = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), many=True, required=False)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "password", "password_confirm", "is_active", "groups"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        groups = validated_data.pop("groups", [])
        password = validated_data.pop("password")

        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()

        if groups:
            user.groups.set(groups)

        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar usuarios"""

    groups = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), many=True, required=False)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "is_active", "groups"]

    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if groups is not None:
            instance.groups.set(groups)

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer para cambiar contraseña"""

    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError("Las contraseñas nuevas no coinciden")
        return attrs
