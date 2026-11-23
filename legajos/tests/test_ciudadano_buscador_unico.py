"""#1031 — con un único resultado, el buscador abre el legajo.

Los dos buscadores (el del header y el del propio listado) llegan a ``CiudadanoListView``
con ``?search=``, así que la regla vive ahí y no distingue de dónde viene la búsqueda.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from legajos.selectors import get_ciudadano_unico_de_busqueda
from users.models import Capacidad, RolMeta


def usuario_con(*codigos):
    grupo, _ = Group.objects.get_or_create(name="Rol buscador " + ("-".join(codigos) or "nada"))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario = User.objects.create_user("u-" + ("-".join(codigos) or "nada"), password="Clave-Seg-2026x")
    usuario.groups.add(grupo)
    return usuario


class BuscadorUnicoResultadoTests(TestCase):
    def setUp(self):
        self.url = reverse("legajos:ciudadanos")
        self.zapiola = Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Zapiola")
        Ciudadano.objects.create(dni="30555987", nombre="Luis", apellido="Gómez")
        Ciudadano.objects.create(dni="30666988", nombre="Eva", apellido="Gómez")
        Ciudadano.objects.create(dni="30999888", nombre="Inés", apellido="Baja", activo=False)
        self.client.force_login(usuario_con("ciudadano.ver"))

    def _detalle(self, ciudadano):
        return reverse("legajos:ciudadano_detalle", kwargs={"pk": ciudadano.pk})

    def test_dni_completo_con_un_resultado_abre_el_legajo(self):
        respuesta = self.client.get(self.url, {"search": "30111222"})

        self.assertRedirects(respuesta, self._detalle(self.zapiola), fetch_redirect_response=False)

    def test_apellido_con_un_resultado_abre_el_legajo(self):
        respuesta = self.client.get(self.url, {"search": "Zapiola"})

        self.assertRedirects(respuesta, self._detalle(self.zapiola), fetch_redirect_response=False)

    def test_dni_parcial_con_un_resultado_abre_el_legajo(self):
        respuesta = self.client.get(self.url, {"search": "1112"})

        self.assertRedirects(respuesta, self._detalle(self.zapiola), fetch_redirect_response=False)

    def test_la_redireccion_es_302(self):
        self.assertEqual(self.client.get(self.url, {"search": "Zapiola"}).status_code, 302)

    def test_dos_resultados_muestran_el_listado(self):
        respuesta = self.client.get(self.url, {"search": "Gómez"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["ciudadanos"]), 2)

    def test_sin_resultados_muestra_el_listado_vacio(self):
        respuesta = self.client.get(self.url, {"search": "zzzz"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["ciudadanos"]), 0)

    def test_sin_busqueda_o_busqueda_vacia_es_el_listado(self):
        for parametros in ({}, {"search": ""}, {"search": "   "}, {"page": "1"}):
            with self.subTest(parametros=parametros):
                self.assertEqual(self.client.get(self.url, parametros).status_code, 200)

    def test_el_ciudadano_inactivo_no_cuenta_como_coincidencia(self):
        respuesta = self.client.get(self.url, {"search": "30999888"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["ciudadanos"]), 0)

    def test_otros_parametros_no_cambian_la_regla(self):
        """Con 2 o más resultados el listado sigue, aunque vengan page u otros parámetros."""
        respuesta = self.client.get(self.url, {"search": "Gómez", "page": "1", "orden": "dni"})

        self.assertEqual(respuesta.status_code, 200)

    def test_la_exportacion_csv_no_redirige(self):
        usuario = usuario_con("ciudadano.ver", "ciudadano.exportar")
        self.client.force_login(usuario)

        respuesta = self.client.get(reverse("legajos:ciudadanos_exportar_csv"), {"search": "Zapiola"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["Content-Type"], "text/csv; charset=utf-8")

    def test_sin_ciudadano_ver_sigue_denegado(self):
        self.client.force_login(usuario_con())

        respuesta = self.client.get(self.url, {"search": "Zapiola"})

        self.assertNotEqual(respuesta.get("Location"), self._detalle(self.zapiola))
        self.assertIn(respuesta.status_code, (302, 403))
        if respuesta.status_code == 302:
            self.assertEqual(respuesta["Location"], reverse("core:inicio"))

    def test_anonimo_va_al_login(self):
        self.client.logout()

        respuesta = self.client.get(self.url, {"search": "Zapiola"})

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("next=", respuesta["Location"])

    def test_el_selector_lee_dos_filas_y_no_cuenta(self):
        with self.assertNumQueries(1):
            self.assertEqual(get_ciudadano_unico_de_busqueda("Zapiola"), self.zapiola.pk)
        with self.assertNumQueries(1):
            self.assertIsNone(get_ciudadano_unico_de_busqueda("Gómez"))
        with self.assertNumQueries(0):
            self.assertIsNone(get_ciudadano_unico_de_busqueda(""))
