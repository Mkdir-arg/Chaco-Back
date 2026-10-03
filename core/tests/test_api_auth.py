"""La API del backoffice se autentica solo por sesión (SEC-01, auditoría oct-2026).

HTTP Basic salteaba las tres barreras que sí respeta el login web: la separación
portal/backoffice (`core.middleware.PortalCiudadanoMiddleware`), la sesión única
de backoffice y el cambio obligatorio de clave provisoria (ambas en
`users.middleware`, que exime `/api/` a propósito). La app de campo no usa Basic:
declara `TokenAuthentication` en sus propias vistas, así que sigue andando.
"""

import base64

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core import rbac
from users.models import Capacidad, RolMeta


def _basic(usuario, clave):
    return "Basic " + base64.b64encode(f"{usuario}:{clave}".encode()).decode()


def _rol_con(nombre, codigos):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


class ApiBackofficeSoloSesionTests(TestCase):
    """SEC-01: `/api/` no acepta HTTP Basic, y lo que sí se usa sigue andando."""

    URLS_BACKOFFICE = (
        # `/api/users/` quedó reducida a `me` (D-05, auditoría oct-2026).
        "/api/users/me/",
        "/api/legajos/ciudadanos/",
        "/api/buscar-ciudadanos/?q=123",
    )

    def test_basic_auth_rechazada_en_api_backoffice(self):
        # Un superusuario: si Basic estuviera habilitada entraría a todo. Lo que
        # se verifica es el esquema de autenticación, no las capacidades.
        User.objects.create_superuser("root", "root@example.com", "Clave-Seg-2026x")
        cliente = APIClient()
        auth = _basic("root", "Clave-Seg-2026x")

        for url in self.URLS_BACKOFFICE:
            with self.subTest(url=url):
                respuesta = cliente.get(url, HTTP_AUTHORIZATION=auth)
                self.assertIn(respuesta.status_code, (401, 403))

    def test_token_campo_sigue_funcionando(self):
        territorial = User.objects.create_user("terri-api", password="Terr-2026-x")
        territorial.groups.add(_rol_con("Territorial de prueba", ["becas.campo"]))

        cliente = APIClient()
        login = cliente.post(
            reverse("becas_api:token"),
            {"username": "terri-api", "password": "Terr-2026-x"},
            format="json",
        )
        self.assertEqual(login.status_code, 200)

        cliente.credentials(HTTP_AUTHORIZATION=f"Token {login.json()['token']}")
        self.assertEqual(cliente.get(reverse("becas_api:relevamiento-list")).status_code, 200)

    def test_ciudadano_portal_con_sesion_no_entra_a_api(self):
        ciudadano = User.objects.create_user("30111222", password="Clave-Seg-2026x")
        ciudadano.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        self.client.force_login(ciudadano)

        respuesta = self.client.get("/api/users/me/")

        self.assertEqual(respuesta.status_code, 302)
        # SEC-29: «mi perfil» ya no existe (el portal ciudadano está apagado); el
        # middleware sigue sacando al ciudadano de la API, ahora hacia la home.
        self.assertEqual(respuesta["Location"], reverse("portal:home"))
