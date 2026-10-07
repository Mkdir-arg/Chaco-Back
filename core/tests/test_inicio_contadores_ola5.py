"""Ola 5 · PR 7 — G2-04: los contadores del inicio no miden lo que dicen.

Cuatro defectos distintos, todos de rótulo o de ventana, ninguno de cálculo:

1. «Total ciudadanos · ↑N **nuevos este mes**» muestra `registros_mes`, que son
   las `InscripcionPrograma` del mes, no los ciudadanos dados de alta.
2. «Seguimientos hoy: X · **X actividades hoy**» imprime el mismo número dos
   veces: `actividad_hoy` es `seguimientos_hoy` copiado en otra clave.
3. «N **usuarios activos hoy**» cuenta cualquier `last_login` de las últimas
   24 h, incluidos los ciudadanos del portal, que no son usuarios del
   backoffice; y «activos» sugiere actividad sostenida, no un ingreso.
4. `tendencias_datos` arranca la serie en `hoy - dias` y recorre `range(dias)`:
   el último punto es **ayer**. El gráfico nunca incluye hoy.

**D-G204** (README §2 de la auditoría): se corrigen las etiquetas ahora; que el
inicio muestre indicadores de Becas es un requerimiento aparte.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from core.rbac import GRUPO_CIUDADANO_PORTAL
from core.views.public import inicio_view


class ContextoDelInicioTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _contexto(self, usuario):
        request = RequestFactory().get("/inicio/")
        request.user = usuario

        from unittest.mock import patch

        with patch("core.views.public.render", return_value=HttpResponse()) as renderizar:
            inicio_view.__wrapped__(request)
        return renderizar.call_args.args[2]

    def test_el_contexto_no_repite_el_mismo_numero_en_dos_claves(self):
        usuario = get_user_model().objects.create_user(username="inicio-contadores")

        contexto = self._contexto(usuario)

        self.assertIn("seguimientos_hoy", contexto)
        self.assertNotIn("actividad_hoy", contexto)

    def test_los_ingresos_no_cuentan_a_los_ciudadanos_del_portal(self):
        """El grupo `Ciudadanos` es identidad de portal, no un rol del backoffice
        (`core.rbac.es_ciudadano_portal`): sumarlos infla el número del inicio."""
        User = get_user_model()
        ahora = timezone.now()
        portal = Group.objects.create(name=GRUPO_CIUDADANO_PORTAL)

        backoffice = User.objects.create_user(username="operadora", last_login=ahora)
        ciudadano = User.objects.create_user(username="ciudadano-portal", last_login=ahora)
        ciudadano.groups.add(portal)

        contexto = self._contexto(backoffice)

        self.assertEqual(contexto["ingresos_24h"], 1)

    def test_los_ingresos_viejos_quedan_fuera_de_la_ventana(self):
        User = get_user_model()
        usuario = User.objects.create_user(username="operadora-2", last_login=timezone.now())
        User.objects.create_user(username="hace-dos-dias", last_login=timezone.now() - timedelta(days=2))

        contexto = self._contexto(usuario)

        self.assertEqual(contexto["ingresos_24h"], 1)


class EtiquetasDelInicioTests(TestCase):
    """Lo que se lee en pantalla, que es donde está el hallazgo."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.usuario = get_user_model().objects.create_user(username="inicio-etiquetas", password="x")
        self.client.force_login(self.usuario)

    def test_las_inscripciones_del_mes_no_se_llaman_ciudadanos_nuevos(self):
        html = self.client.get(reverse("core:inicio")).content.decode()

        self.assertNotIn("nuevos este mes", html)
        self.assertIn("inscripciones este mes", html)

    def test_no_queda_la_linea_duplicada_de_actividades(self):
        html = self.client.get(reverse("core:inicio")).content.decode()

        self.assertNotIn("actividades hoy", html)

    def test_los_ingresos_se_nombran_por_lo_que_miden(self):
        html = self.client.get(reverse("core:inicio")).content.decode()

        self.assertNotIn("usuarios activos hoy", html)
        self.assertIn("al backoffice en las últimas 24 h", html)


class TendenciasIncluyenHoyTests(TestCase):
    """`dashboard:api_tendencias` alimenta el gráfico del inicio."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def _labels(self, periodo="7d"):
        from django.test import RequestFactory

        from dashboard.api_views import tendencias_datos

        usuario = get_user_model().objects.create_user(username=f"tendencias-{periodo}")
        usuario.is_superuser = True
        usuario.save(update_fields=["is_superuser"])

        request = RequestFactory().get("/api/tendencias/", {"periodo": periodo})
        request.user = usuario
        return tendencias_datos(request).data

    def test_el_ultimo_punto_de_la_serie_es_hoy(self):
        datos = self._labels()

        self.assertEqual(datos["labels"][-1], timezone.now().date().strftime("%d/%m"))

    def test_la_serie_conserva_la_cantidad_de_dias_del_periodo(self):
        datos = self._labels()

        self.assertEqual(len(datos["labels"]), 7)
        self.assertEqual(len(datos["datos"]), 7)

    def test_una_inscripcion_de_hoy_entra_en_la_serie(self):
        from legajos.models import Ciudadano
        from programas.models import InscripcionPrograma, Programa

        programa = Programa.objects.create(nombre="Serie", estado=Programa.Estado.ACTIVO)
        ciudadano = Ciudadano.objects.create(dni="40111222", nombre="Ana", apellido="Serie")
        InscripcionPrograma.objects.create(
            ciudadano=ciudadano, programa=programa, fecha_inscripcion=timezone.now().date()
        )

        datos = self._labels()

        self.assertEqual(datos["datos"][-1], 1)
