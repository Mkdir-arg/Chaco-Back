"""La página navegable de DRF no da 500 (#521, QA de testing 06/10/2026).

`django-filter` está en `requirements.txt` y seis ViewSets declaran
`DjangoFilterBackend`, pero `django_filters` no estaba en `INSTALLED_APPS`: el
cargador de templates por app no encontraba
`django_filters/rest_framework/form.html` y **cualquier GET desde el navegador**
—el `Accept: text/html` que manda el browser— moría con `TemplateDoesNotExist`
al dibujar el formulario de filtros. Con `Accept: application/json` no pasaba:
ahí no se renderiza formulario, así que el front nunca lo vio y el bug solo
aparecía cuando alguien abría la URL a mano.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from core import rbac
from users.models import Capacidad, RolMeta

# Las rutas registradas de los ViewSets que declaran `DjangoFilterBackend`.
# `legajos.api_views.contactos.HistorialContactoViewSet` también lo declara pero
# **no tiene URL** (su router se borró con LEG-03), así que no se puede pedir por
# HTTP: lo cubre `legajos.tests.test_api_ciudadanos_rbac`.
URLS_CON_FILTROS = (
    "/api/legajos/ciudadanos/",
    "/api/legajos/alertas/",
    "/api/core/municipios/",
    "/api/core/localidades/",
)


def _rol_con(nombre, codigos):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    return grupo


class ApiNavegableTests(TestCase):
    """#521: `Accept: text/html` sobre la API devuelve la página navegable, no un 500."""

    @classmethod
    def setUpTestData(cls):
        cls.operador = User.objects.create_user("operador-navegable", password="Clave-Seg-2026x")
        # `ciudadano.sensible` por `/api/legajos/alertas/`: el texto de la alerta
        # pide esa capacidad por cualquier canal desde D-11 (Cambio 179).
        cls.operador.groups.add(_rol_con("Operador navegable", ["ciudadano.ver", "ciudadano.sensible"]))

    def test_navegador_recibe_la_pagina_navegable(self):
        self.client.force_login(self.operador)

        for url in URLS_CON_FILTROS:
            with self.subTest(url=url):
                respuesta = self.client.get(url, HTTP_ACCEPT="text/html")
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn("text/html", respuesta["Content-Type"])

    def test_json_sigue_igual(self):
        self.client.force_login(self.operador)

        for url in URLS_CON_FILTROS:
            with self.subTest(url=url):
                respuesta = self.client.get(url, HTTP_ACCEPT="application/json")
                self.assertEqual(respuesta.status_code, 200)
                self.assertIn("application/json", respuesta["Content-Type"])
                self.assertIn("results", respuesta.json())

    def test_superusuario_tambien_entra_por_el_navegador(self):
        self.client.force_login(User.objects.create_superuser("root-navegable", "root@example.com", "Clave-Seg-2026x"))

        for url in URLS_CON_FILTROS:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, HTTP_ACCEPT="text/html").status_code, 200)

    def test_anonimo_no_ve_nada(self):
        """La API sigue detrás de login: arreglar el 500 no abre la puerta."""
        for url in URLS_CON_FILTROS:
            with self.subTest(url=url):
                respuesta = self.client.get(url, HTTP_ACCEPT="text/html")
                self.assertIn(respuesta.status_code, (301, 302, 401, 403))

    def test_sin_capacidad_no_lista_ciudadanos_ni_alertas(self):
        """Un usuario de backoffice sin capacidades sigue en 403, no en 500."""
        self.client.force_login(User.objects.create_user("sin-rol-navegable", password="Clave-Seg-2026x"))

        for url in ("/api/legajos/ciudadanos/", "/api/legajos/alertas/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url, HTTP_ACCEPT="text/html").status_code, 403)
