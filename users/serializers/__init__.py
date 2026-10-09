"""Serializers de `/api/users/me/`.

Los de alta, edición y cambio de contraseña se retiraron junto con los ViewSets
de usuarios y roles (D-05 de la auditoría oct-2026): el ABM web es el único
camino de escritura. Ver `users/api_views/__init__.py`.
"""

from django.contrib.auth.models import Group, User
from rest_framework import serializers

from ..models import Profile


class GroupSerializer(serializers.ModelSerializer):
    """Serializer para Group"""

    class Meta:
        model = Group
        fields = ["id", "name"]


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer para Profile.

    Sin `dark_mode` (RED-75, D-RED-07 = A): la preferencia de tema vive en el
    `localStorage` del navegador. La columna sigue en la base —sacarla es
    *contract*, dos releases después de que nadie la lea— pero nadie la escribe,
    así que exponerla solo prometía un dato que siempre vale el default.
    """

    class Meta:
        model = Profile
        fields = ["id", "dni", "telefono", "institucion", "observacion"]


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

    # RED-37: siempre devuelve algo (cae al `username`), así que no es anulable.
    def get_full_name(self, obj) -> str:
        return obj.get_full_name() or obj.username
