from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from django.contrib.auth.models import User, Group
from django.db import transaction

from core import rbac
from core.api_permissions import RequiereCapacidad
from ..models import Profile
from ..serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    GroupSerializer, ProfileSerializer, ChangePasswordSerializer
)


@extend_schema_view(
    list=extend_schema(description="Lista todos los usuarios"),
    create=extend_schema(description="Crea un nuevo usuario"),
    retrieve=extend_schema(description="Obtiene un usuario específico"),
    update=extend_schema(description="Actualiza un usuario"),
    partial_update=extend_schema(description="Actualiza parcialmente un usuario"),
)
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar usuarios.

    Lectura: usuario autenticado. Escritura: capacidad ``usuario.administrar``.
    No hay borrado físico: usar ``deactivate``.
    """
    queryset = User.objects.select_related('profile').prefetch_related('groups')
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active', 'is_staff', 'groups']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['username']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer

    def get_permissions(self):
        """Escritura: capacidad usuario.administrar. Lectura: autenticado."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [RequiereCapacidad("usuario.administrar")()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        """El borrado físico está deshabilitado: usar deactivate."""
        return Response(
            {'error': 'El borrado físico de usuarios está deshabilitado. Usá deactivate.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @extend_schema(description="Obtiene el perfil del usuario actual")
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Obtiene el perfil del usuario actual"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @extend_schema(
        description="Cambia la contraseña del usuario actual",
        request=ChangePasswordSerializer
    )
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Cambia la contraseña del usuario actual"""
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            user = request.user

            if not user.check_password(serializer.validated_data['old_password']):
                return Response(
                    {'old_password': ['Contraseña actual incorrecta']},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.set_password(serializer.validated_data['new_password'])
            user.save()

            return Response({'message': 'Contraseña cambiada exitosamente'})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(description="Activa un usuario")
    @action(detail=True, methods=['post'], permission_classes=[RequiereCapacidad("usuario.administrar")])
    def activate(self, request, pk=None):
        """Activa un usuario"""
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({'status': 'Usuario activado'})

    @extend_schema(description="Desactiva un usuario")
    @action(detail=True, methods=['post'], permission_classes=[RequiereCapacidad("usuario.administrar")])
    def deactivate(self, request, pk=None):
        """Desactiva un usuario (con auto-protección)."""
        user = self.get_object()
        if user == request.user:
            return Response(
                {'error': 'No podés desactivar tu propio usuario.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            with transaction.atomic():
                user.is_active = False
                user.save()
                rbac.asegurar_admin_restante()
        except rbac.SinAdministradorError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'status': 'Usuario desactivado'})


@extend_schema_view(
    list=extend_schema(description="Lista todos los roles"),
    create=extend_schema(description="Crea un nuevo rol"),
    retrieve=extend_schema(description="Obtiene un rol específico"),
    update=extend_schema(description="Actualiza un rol"),
    partial_update=extend_schema(description="Actualiza parcialmente un rol"),
    destroy=extend_schema(description="Elimina un rol no protegido"),
)
class GroupViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar roles (Group).

    Lectura: autenticado. Escritura: capacidad ``rol.administrar``.
    Los roles protegidos no se pueden eliminar.
    """
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name']
    ordering = ['name']

    def get_permissions(self):
        """Escritura: capacidad rol.administrar. Lectura: autenticado."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [RequiereCapacidad("rol.administrar")()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        meta = getattr(group, "meta", None)
        if meta and meta.protegido:
            return Response(
                {'error': 'El rol está protegido y no puede eliminarse.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(description="Obtiene los usuarios de un rol")
    @action(detail=True, methods=['get'])
    def users(self, request, pk=None):
        """Obtiene los usuarios de un rol específico"""
        group = self.get_object()
        users = group.user_set.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(description="Lista todos los perfiles"),
    retrieve=extend_schema(description="Obtiene un perfil específico"),
    update=extend_schema(description="Actualiza un perfil"),
    partial_update=extend_schema(description="Actualiza parcialmente un perfil")
)
class ProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet para gestionar perfiles de usuario.
    """
    queryset = Profile.objects.select_related('user')
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'put', 'patch']  # Solo lectura y actualización

    def get_queryset(self):
        """Cada usuario ve su propio perfil; quien administra usuarios, todos."""
        if rbac.puede(self.request.user, "usuario.administrar"):
            return self.queryset
        return self.queryset.filter(user=self.request.user)
