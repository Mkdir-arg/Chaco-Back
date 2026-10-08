"""La API de ciudadanos es de solo lectura y pide capacidad (SEC-02, auditoría oct-2026).

Antes de este cambio `CiudadanoViewSet` era un `ModelViewSet` con solo
`IsAuthenticated`: cualquier usuario del backoffice con sesión —sin un solo rol—
podía listar el padrón entero, cambiarle el DNI a un ciudadano con un PATCH y
borrarlo con un DELETE (cascada sobre alertas, inscripciones y derivaciones).
Además `search_fields` estaba declarado pero `SearchFilter` no estaba en
`filter_backends`, así que el `?search=` del buscador de «Agregar familiar»
(`ciudadano_detail.html`) se ignoraba y devolvía 10 ciudadanos cualesquiera.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIClient

from core import rbac
from core.api_permissions import BackofficeAutenticado
from legajos.models import Ciudadano
from users.models import Capacidad, RolMeta


def _usuario_con(*codigos, username=None):
    """Usuario de backoffice con exactamente esas capacidades."""
    nombre_rol = "Rol " + ("-".join(codigos) or "sin-capacidades")
    grupo, _ = Group.objects.get_or_create(name=nombre_rol)
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario = User.objects.create_user(username or f"u-{nombre_rol}", password="Clave-Seg-2026x")
    usuario.groups.add(grupo)
    return usuario


class ApiCiudadanosRbacTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gomez = Ciudadano.objects.create(
            dni="22333444",
            nombre="Luis",
            apellido="Gomez",
            telefono="3624111111",
            email="luis@example.com",
            domicilio="Calle Falsa 123",
        )
        cls.peralta = Ciudadano.objects.create(dni="25666777", nombre="Ana", apellido="Peralta")

    def _cliente(self, usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def test_sin_capacidad_403(self):
        cliente = self._cliente(_usuario_con())

        self.assertEqual(cliente.get("/api/legajos/ciudadanos/?search=gom").status_code, 403)

    def test_ciudadano_del_portal_403(self):
        """`BackofficeAutenticado`: la API es del backoffice (SEC-01 punto 2)."""
        ciudadano = User.objects.create_user("30111222", password="Clave-Seg-2026x")
        ciudadano.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))

        self.assertEqual(self._cliente(ciudadano).get("/api/legajos/ciudadanos/?search=gom").status_code, 403)

    def test_patch_y_delete_405(self):
        """Ni con `ciudadano.editar`: el ViewSet es de solo lectura."""
        cliente = self._cliente(_usuario_con("ciudadano.ver", "ciudadano.editar"))

        patch = cliente.patch(f"/api/legajos/ciudadanos/{self.gomez.pk}/", {"dni": "99999999"}, format="json")
        self.assertEqual(patch.status_code, 405)
        self.gomez.refresh_from_db()
        self.assertEqual(self.gomez.dni, "22333444")

        self.assertEqual(cliente.delete(f"/api/legajos/ciudadanos/{self.gomez.pk}/").status_code, 405)
        self.assertTrue(Ciudadano.objects.filter(pk=self.gomez.pk).exists())

        post = cliente.post(
            "/api/legajos/ciudadanos/",
            {"dni": "11000111", "nombre": "Nuevo", "apellido": "Ciudadano"},
            format="json",
        )
        self.assertEqual(post.status_code, 405)

    def test_con_ciudadano_ver_200_sin_sensibles(self):
        cliente = self._cliente(_usuario_con("ciudadano.ver"))

        respuesta = cliente.get("/api/legajos/ciudadanos/?search=gom")

        self.assertEqual(respuesta.status_code, 200)
        fila = respuesta.json()["results"][0]
        self.assertEqual(fila["dni"], "22333444")
        for campo in ("telefono", "email", "domicilio"):
            self.assertNotIn(campo, fila)

    def test_con_ciudadano_sensible_ve_los_campos(self):
        cliente = self._cliente(_usuario_con("ciudadano.ver", "ciudadano.sensible"))

        fila = cliente.get("/api/legajos/ciudadanos/?search=gom").json()["results"][0]

        self.assertEqual(fila["telefono"], "3624111111")
        self.assertEqual(fila["email"], "luis@example.com")
        self.assertEqual(fila["domicilio"], "Calle Falsa 123")

    def test_search_filtra_por_texto(self):
        cliente = self._cliente(_usuario_con("ciudadano.ver"))

        resultados = cliente.get("/api/legajos/ciudadanos/?search=peralta").json()["results"]

        self.assertEqual([c["dni"] for c in resultados], ["25666777"])

    def test_search_vacio_devuelve_vacio(self):
        """Sin búsqueda no se vuelca el padrón; menos de 3 caracteres tampoco."""
        cliente = self._cliente(_usuario_con("ciudadano.ver"))

        for url in ("/api/legajos/ciudadanos/", "/api/legajos/ciudadanos/?search=go"):
            with self.subTest(url=url):
                respuesta = cliente.get(url)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.json()["results"], [])


class ApiLegajosBackofficeAutenticadoTests(TestCase):
    """SEC-01 punto 2: las vistas DRF de legajos no heredan el default de DRF."""

    URLS = (
        "/api/legajos/alertas/",
        "/api/legajos/alertas/count/",
    )

    def test_ciudadano_del_portal_no_entra(self):
        ciudadano = User.objects.create_user("30111333", password="Clave-Seg-2026x")
        ciudadano.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        cliente = APIClient()
        cliente.force_authenticate(ciudadano)

        for url in self.URLS:
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 403)

    def test_usuario_de_backoffice_entra(self):
        cliente = APIClient()
        # `ciudadano.sensible`: `AlertasViewSet` la pide desde D-11 (Cambio 179).
        cliente.force_authenticate(_usuario_con("ciudadano.ver", "ciudadano.sensible", username="backoffice-legajos"))

        for url in self.URLS:
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 200)

    def test_viewsets_de_contactos_declaran_el_permiso(self):
        """`HistorialContactoViewSet` no tiene URL —su router se borró con LEG-03—:
        se verifica la declaración, no el HTTP. `VinculoFamiliarViewSet` ya no existe."""
        from legajos.api_views.contactos import HistorialContactoViewSet

        self.assertIs(HistorialContactoViewSet.permission_classes[0], BackofficeAutenticado)


class ApiCiudadanosRetrieveYOrdenTests(TestCase):
    """R0b-04 y R0b-05, seguimientos de la revisión de #542.

    `get_queryset` aplicaba el mínimo de búsqueda **también** en `retrieve`, así
    que `GET /api/legajos/ciudadanos/<pk>/` daba 404 aunque el ciudadano
    existiera. Y `ordering` estaba declarado sin `OrderingFilter`, que es el
    único backend que lo lee: la paginación salía sin orden garantizado y dos
    páginas consecutivas podían repetir o saltear filas.
    """

    @classmethod
    def setUpTestData(cls):
        cls.gomez = Ciudadano.objects.create(dni="22333555", nombre="Hugo", apellido="Gomez")
        # Mismo apellido y mismo nombre: sin el desempate por pk el orden lo
        # decide el motor, y MariaDB y MySQL no tienen por qué coincidir.
        for i in range(14):
            Ciudadano.objects.create(dni=f"280000{i:02d}", nombre="Mellizo", apellido="Gomez")

    def _cliente(self, usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def test_retrieve_con_ciudadano_ver_200(self):
        cliente = self._cliente(_usuario_con("ciudadano.ver", username="ve-retrieve"))

        respuesta = cliente.get(f"/api/legajos/ciudadanos/{self.gomez.pk}/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["dni"], "22333555")

    def test_retrieve_sin_capacidad_403(self):
        cliente = self._cliente(_usuario_con(username="sin-rol-retrieve"))

        self.assertEqual(cliente.get(f"/api/legajos/ciudadanos/{self.gomez.pk}/").status_code, 403)

    def test_retrieve_de_un_pk_inexistente_sigue_siendo_404(self):
        cliente = self._cliente(_usuario_con("ciudadano.ver", username="ve-retrieve-404"))

        self.assertEqual(cliente.get("/api/legajos/ciudadanos/999999/").status_code, 404)

    def test_el_listado_sigue_pidiendo_tres_caracteres(self):
        """El mínimo de SEC-02 vale para `list`, que es donde se enumera."""
        cliente = self._cliente(_usuario_con("ciudadano.ver", username="ve-list-minimo"))

        self.assertEqual(cliente.get("/api/legajos/ciudadanos/?search=go").json()["results"], [])

    def test_dos_paginas_no_repiten_ni_saltean(self):
        cliente = self._cliente(_usuario_con("ciudadano.ver", username="ve-paginado"))

        primera = cliente.get("/api/legajos/ciudadanos/?search=gomez&page=1").json()["results"]
        segunda = cliente.get("/api/legajos/ciudadanos/?search=gomez&page=2").json()["results"]

        ids = [fila["id"] for fila in primera + segunda]
        self.assertEqual(len(ids), 15)
        self.assertEqual(len(set(ids)), 15)

    def test_ordering_declarado_tiene_su_backend(self):
        from rest_framework import filters

        from legajos.api_views import CiudadanoViewSet

        self.assertIn(filters.OrderingFilter, CiudadanoViewSet.filter_backends)
