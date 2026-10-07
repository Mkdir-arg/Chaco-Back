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
   el último punto es **ayer**. El gráfico nunca incluye hoy. Y el «hoy» con el
   que arma la ventana era el de **UTC**, mientras que `fecha_inscripcion` lleva
   el de Argentina: entre las 21 y las 24 el último bucket rotulaba «mañana» y
   salía siempre en cero (ronda 2; es la corrección que propone BEC-18 para
   este uso).

El quinto contador —«Legajos activos», que agregaba `InscripcionPrograma` en vez
de `LegajoAtencion`— va en `core.tests.test_inicio_legajos_ola5_pr7`.

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
        # El sustantivo se pluraliza en el template («1 inscripción», «2 inscripciones»),
        # así que el test mira la raíz y no una de las dos formas.
        self.assertIn("inscripci", html)
        self.assertIn("este mes", html)

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

        self.assertEqual(datos["labels"][-1], timezone.localdate().strftime("%d/%m"))

    def test_la_serie_conserva_la_cantidad_de_dias_del_periodo(self):
        datos = self._labels()

        self.assertEqual(len(datos["labels"]), 7)
        self.assertEqual(len(datos["datos"]), 7)

    def test_una_inscripcion_del_ultimo_dia_entra_en_la_serie(self):
        """Sin forzar la fecha: el `create()` y la ventana usan el mismo reloj.

        `InscripcionPrograma.fecha_inscripcion` se escribe con `timezone.localdate()`
        —el `default` del campo, desde BEC-18— y la ventana se arma con la misma
        función, así que un alta recién hecha cae en el último bucket a cualquier hora
        del día y en cualquier zona horaria del proceso. Con el `auto_now_add` que el
        campo tenía antes, el alta quedaba con `datetime.date.today()`: en un proceso
        que no corre en hora de Argentina —los contenedores, en UTC— es otro día y este
        test se ponía rojo sin que nadie hubiera tocado nada.
        """
        from legajos.models import Ciudadano
        from programas.models import InscripcionPrograma, Programa

        programa = Programa.objects.create(nombre="Serie", estado=Programa.Estado.ACTIVO)
        ciudadano = Ciudadano.objects.create(dni="40111222", nombre="Ana", apellido="Serie")
        InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=programa)

        datos = self._labels()

        self.assertEqual(datos["datos"][-1], 1)

    def test_la_ventana_usa_la_fecha_local_y_no_la_utc(self):
        """El borde que el CI encontró, con el reloj congelado para que sea determinista.

        A las 23:30 de Argentina son las 02:30 UTC **del día siguiente**. Con
        `timezone.now().date()` el último bucket quedaba rotulado con la fecha de
        mañana —y siempre en cero, porque ninguna fila puede tener esa fecha—. Con
        `timezone.localdate()` el último bucket es el día en curso en Argentina.
        """
        from datetime import datetime
        from datetime import timezone as tz_utc
        from unittest.mock import patch

        instante = datetime(2026, 10, 7, 2, 30, tzinfo=tz_utc.utc)  # 23:30 ART del 06/10

        with patch("django.utils.timezone.now", return_value=instante):
            datos = self._labels()

        self.assertEqual(datos["labels"][-1], "06/10")
        self.assertEqual(datos["labels"][0], "30/09")

    def test_antes_el_ultimo_dia_quedaba_fuera_de_la_ventana(self):
        """La regresión concreta de G2-04, en el borde opuesto.

        Con `fecha_inicio = hoy - dias` y `range(dias)` la serie terminaba **ayer**:
        un registro del día de hoy no aparecía en ningún bucket. Acá se verifica que
        el registro de hoy sí está y que la serie no se corrió un día: el primer
        bucket es `hoy - (dias - 1)`. La fecha vieja se fuerza con `update()` porque
        `auto_now_add` descarta cualquier valor que se le pase al `create()`.
        """
        from legajos.models import Ciudadano
        from programas.models import InscripcionPrograma, Programa

        hoy = timezone.localdate()
        programa = Programa.objects.create(nombre="Borde", estado=Programa.Estado.ACTIVO)
        ciudadano = Ciudadano.objects.create(dni="40111333", nombre="Eva", apellido="Borde")
        inscripcion = InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=programa)
        InscripcionPrograma.objects.filter(pk=inscripcion.pk).update(fecha_inscripcion=hoy - timedelta(days=6))

        datos = self._labels()

        self.assertEqual(datos["labels"][0], (hoy - timedelta(days=6)).strftime("%d/%m"))
        self.assertEqual(datos["datos"][0], 1)
        self.assertEqual(datos["datos"][-1], 0)
