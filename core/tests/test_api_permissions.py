"""Permisos DRF de `core.api_permissions` (SEC-01 punto 2, auditoría oct-2026).

`BackofficeAutenticado` es la defensa en profundidad para las vistas de `/api/`
que declaran `permission_classes` explícitas y por eso **no heredan** el default
de `REST_FRAMEWORK` (`IsAuthenticated`) que puso el Cambio 100: exige sesión de
backoffice y deja afuera al ciudadano del portal, que no tiene nada que hacer ahí.
"""

from django.contrib.auth.models import AnonymousUser, Group, User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from core import rbac
from core.api_permissions import BackofficeAutenticado


class BackofficeAutenticadoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.grupo_portal = Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL)

    def _permiso(self, usuario):
        peticion = APIRequestFactory().get("/api/cualquier-cosa/")
        peticion.user = usuario
        return BackofficeAutenticado().has_permission(peticion, view=None)

    def test_anonimo_no_pasa(self):
        self.assertFalse(self._permiso(AnonymousUser()))

    def test_ciudadano_del_portal_no_pasa(self):
        ciudadano = User.objects.create_user("30111222", password="Clave-Seg-2026x")
        ciudadano.groups.add(self.grupo_portal)

        self.assertFalse(self._permiso(ciudadano))

    def test_usuario_de_backoffice_pasa(self):
        # Sin capacidades: este permiso solo separa portal de backoffice; lo que
        # puede hacer cada uno lo sigue decidiendo `RequiereCapacidad`.
        agente = User.objects.create_user("agente-api", password="Clave-Seg-2026x")

        self.assertTrue(self._permiso(agente))

    def test_superusuario_pasa(self):
        root = User.objects.create_superuser("root-api", "root-api@example.com", "Clave-Seg-2026x")

        self.assertTrue(self._permiso(root))
