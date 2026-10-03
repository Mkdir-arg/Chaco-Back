"""El catálogo geográfico de `/api/core/` es de solo lectura (SEC-13, auditoría oct-2026).

Las provincias, municipios y localidades se administran desde la web
(`configuracion/views/geografia.py`, con `config.administrar`). La API existía como
`ModelViewSet` y, con la sesión de cualquier usuario del backoffice, un
`DELETE /api/core/provincias/<id>/` devolvía 204 y arrastraba en cascada municipios y
localidades. Nadie escribe por esta API: el formulario de domicilio usa
`core.views.public.load_municipios` / `load_localidad`.
"""

from django.contrib.auth.models import Group, User
from django.test import TestCase
from rest_framework.test import APIClient

from core import rbac
from core.models import Localidad, Municipio, Provincia


class GeoApiSoloLecturaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.provincia = Provincia.objects.create(nombre="Chaco API")
        cls.municipio = Municipio.objects.create(nombre="Municipio API", provincia=cls.provincia)
        cls.localidad = Localidad.objects.create(nombre="Localidad API", municipio=cls.municipio)

    def _cliente_backoffice(self):
        cliente = APIClient()
        cliente.force_authenticate(User.objects.create_user("agente-geo", password="Clave-Seg-2026x"))
        return cliente

    def test_escritura_405(self):
        cliente = self._cliente_backoffice()
        escrituras = (
            ("post", "/api/core/provincias/", {"nombre": "Inventada"}),
            ("put", f"/api/core/provincias/{self.provincia.pk}/", {"nombre": "Renombrada"}),
            ("patch", f"/api/core/provincias/{self.provincia.pk}/", {"nombre": "Renombrada"}),
            ("delete", f"/api/core/provincias/{self.provincia.pk}/", None),
            ("post", "/api/core/municipios/", {"nombre": "Inventado", "provincia": self.provincia.pk}),
            ("delete", f"/api/core/municipios/{self.municipio.pk}/", None),
            ("post", "/api/core/localidades/", {"nombre": "Inventada", "municipio": self.municipio.pk}),
            ("delete", f"/api/core/localidades/{self.localidad.pk}/", None),
        )

        for metodo, url, datos in escrituras:
            with self.subTest(metodo=metodo, url=url):
                respuesta = (
                    getattr(cliente, metodo)(url, datos, format="json") if datos else getattr(cliente, metodo)(url)
                )
                self.assertEqual(respuesta.status_code, 405)

        self.assertTrue(Provincia.objects.filter(pk=self.provincia.pk).exists())
        self.assertTrue(Municipio.objects.filter(pk=self.municipio.pk).exists())
        self.assertTrue(Localidad.objects.filter(pk=self.localidad.pk).exists())

    def test_lectura_autenticado_200(self):
        cliente = self._cliente_backoffice()

        for url in (
            "/api/core/provincias/",
            f"/api/core/provincias/{self.provincia.pk}/",
            f"/api/core/provincias/{self.provincia.pk}/municipios/",
            "/api/core/municipios/",
            f"/api/core/municipios/{self.municipio.pk}/localidades/",
            "/api/core/localidades/",
            "/api/core/sexos/",
            "/api/core/meses/",
            "/api/core/dias/",
        ):
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 200)

    def test_ciudadano_del_portal_no_lee_el_catalogo(self):
        # SEC-01 punto 2: estas vistas declaran `permission_classes` y por eso no
        # heredan el default de DRF; el freno explícito es `BackofficeAutenticado`.
        ciudadano = User.objects.create_user("30111222", password="Clave-Seg-2026x")
        ciudadano.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        cliente = APIClient()
        cliente.force_authenticate(ciudadano)

        self.assertEqual(cliente.get("/api/core/provincias/").status_code, 403)
