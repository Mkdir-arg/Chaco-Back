"""API REST de usuarios: solo el perfil propio.

El ABM de usuarios y roles vive en el backoffice web (`users/views/admin.py`),
con sus reglas: alcance por programa, roles asignables según el operador,
`asegurar_admin_restante`, roles protegidos y validación de contraseñas. Los
ViewSets de DRF que convivían acá eran un ABM paralelo sin ninguna de esas
reglas y con permisos propios más flojos, así que se retiraron (decisión D-05 de
la auditoría oct-2026: SEC-05, SEC-16 y SEC-17). No tenían consumidores.

Queda `UsuarioActualView`, de solo lectura y sobre `request.user`.
"""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api_permissions import BackofficeAutenticado

from ..serializers import UserSerializer


class UsuarioActualView(APIView):
    """Datos del usuario de la sesión actual."""

    permission_classes = [BackofficeAutenticado]
    serializer_class = UserSerializer

    @extend_schema(description="Obtiene el perfil del usuario actual", responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)
