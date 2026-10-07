"""Los contadores de la home y quién los invalida (RED-51).

Hay **dos** funciones llamadas `invalidate_dashboard_cache`:

- `dashboard/utils.py` borra cinco claves y la llama `CiudadanosService.
  invalidate_ciudadanos_cache()`, que usan las tres vistas de alta/edición/borrado de
  ciudadanos.
- `core/performance/cache_utils.py` borra **dos** y está cableada por señales
  (`post_save`/`post_delete` de `Ciudadano` y de `User`).

Y hay un receiver colgado del modelo equivocado: `legajos/signals/core.py` borra
`stats_legajos` al guardar un `LegajoAtencion`, pero esa clave la escribe
`contar_legajos()`, que cuenta **`InscripcionPrograma`**. Una inscripción nueva no
refresca nada; un legajo de atención refresca algo que no cambió.

Por qué importa: la limpieza de OPS-10 (Ola 7) va a «deduplicar» las dos funciones. Si
se queda con la de `core/performance` —la que tiene las señales— se pierden tres
claves; si se queda con la de `dashboard` se pierden los receivers. En producción el
cache es Redis compartido con TTL de 300 s, así que el síntoma es un contador viejo en
la home durante cinco minutos; en los tests es LocMem y esta familia de bugs es
invisible para la suite entera.

Dos de estos tests están rojos (`expectedFailure`): son los bugs. **Ola 4:**
`dashboard/cache.py` con las claves como constantes y el mapa `{modelo: [claves]}`,
el receiver de `stats_legajos` con `sender=InscripcionPrograma`, y el test que afirma
que ya no quedan dos funciones con el mismo nombre.
"""

import unittest

from django.core.cache import cache
from django.test import TestCase

from dashboard.utils import contar_alertas_activas, contar_ciudadanos, contar_legajos
from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from programas.models import InscripcionPrograma, Programa


class InvalidacionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.ciudadano = Ciudadano.objects.create(nombre="Ana", apellido="Pérez", dni="20111222")
        self.programa = Programa.objects.create(nombre="Programa cache", codigo="CACHE")

    def _calentar(self):
        """Deja las tres claves escritas, como después de un render de la home."""
        contar_ciudadanos()
        contar_legajos()
        contar_alertas_activas()

    def test_el_andamio_calienta_las_tres_claves(self):
        """Control: sin esto, un `assertIsNone` pasaría porque la clave nunca existió."""
        self._calentar()

        for clave in ("contar_ciudadanos", "stats_legajos", "alertas_activas"):
            with self.subTest(clave=clave):
                self.assertIsNotNone(cache.get(clave))

    def test_ciudadano_nuevo_invalida_contar_ciudadanos(self):
        """El único de los tres que anda hoy: lo cablea `core/performance/cache_utils.py`.

        Es también el que la limpieza de OPS-10 puede romper sin querer, si «deduplica»
        quedándose con la función de `dashboard/utils.py`, que no tiene señales.
        """
        self._calentar()

        Ciudadano.objects.create(nombre="Beto", apellido="Gómez", dni="20333444")

        self.assertIsNone(cache.get("contar_ciudadanos"))

    def test_usuario_nuevo_invalida_contar_usuarios(self):
        """El otro receiver cableado, por el mismo camino."""
        from django.contrib.auth import get_user_model

        contar_usuarios_valor = cache.get("contar_usuarios")
        self.assertIsNone(contar_usuarios_valor)
        from dashboard.utils import contar_usuarios

        contar_usuarios()

        get_user_model().objects.create_user(username="cache_user", password="x")

        self.assertIsNone(cache.get("contar_usuarios"))

    def test_el_login_no_invalida_los_contadores(self):
        """`update_last_login` guarda el User en cada login y no cambia ningún
        contador: el receiver lo saltea a propósito. Perder esa rama hace que la home
        recalcule todo en cada ingreso."""
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        usuario = get_user_model().objects.create_user(username="cache_login", password="x")
        self._calentar()

        usuario.last_login = timezone.now()
        usuario.save(update_fields=["last_login"])

        self.assertIsNotNone(cache.get("contar_ciudadanos"))

    @unittest.expectedFailure
    def test_inscripcion_nueva_invalida_stats_legajos(self):
        """RED-51 — se invierte en la Ola 4.

        `stats_legajos` lo escribe `contar_legajos()`, que agrega sobre
        `InscripcionPrograma`. El único receiver que borra esa clave está colgado de
        `LegajoAtencion` (`legajos/signals/core.py`). Resultado: el número de legajos
        de la home queda viejo hasta que expire el TTL.
        """
        self._calentar()
        total_antes = cache.get("stats_legajos")["total"]

        InscripcionPrograma.objects.create(ciudadano=self.ciudadano, programa=self.programa)

        self.assertIsNone(
            cache.get("stats_legajos"),
            f"la clave sigue cacheada en {total_antes}: el receiver mira el modelo equivocado.",
        )

    def test_hoy_quien_invalida_stats_legajos_es_legajoatencion(self):
        """El andamio del `expectedFailure`: deja escrito el receiver que **sí** existe,
        para que el arreglo de la Ola 4 no lo borre al mover el `sender`."""
        self._calentar()

        LegajoAtencion.objects.create()

        self.assertIsNone(cache.get("stats_legajos"))

    @unittest.expectedFailure
    def test_alerta_nueva_invalida_alertas_activas(self):
        """RED-51 — se invierte en la Ola 4.

        `contar_alertas_activas()` cachea `alertas_activas` 60 s. Nadie borra esa clave
        cuando nace una alerta: solo la limpia `dashboard.utils.invalidate_dashboard_cache`,
        que corre al dar de alta o editar un **ciudadano**. El badge de alertas de la
        home puede tardar un minuto en reflejar una alerta crítica nueva.
        """
        self._calentar()

        AlertaCiudadano.objects.create(
            ciudadano=self.ciudadano,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Alerta de prueba",
        )

        self.assertIsNone(cache.get("alertas_activas"))

    def test_el_alta_de_un_ciudadano_si_limpia_alertas_activas(self):
        """Por dónde se limpia hoy, que es el camino que no hay que perder: la vista de
        alta de ciudadanos llama a `CiudadanosService.invalidate_ciudadanos_cache()`."""
        from legajos.services.ciudadanos import CiudadanosService

        self._calentar()

        CiudadanosService.invalidate_ciudadanos_cache()

        self.assertIsNone(cache.get("alertas_activas"))


class DosFuncionesTests(TestCase):
    """La duplicación en sí, caracterizada. La Ola 4 escribe el test inverso
    (`test_no_quedan_dos_funciones_llamadas_invalidate_dashboard_cache`) y este se
    actualiza en el mismo PR."""

    def test_hay_dos_funciones_con_el_mismo_nombre(self):
        from core.performance.cache_utils import invalidate_dashboard_cache as de_performance
        from dashboard.utils import invalidate_dashboard_cache as de_dashboard

        self.assertIsNot(de_dashboard, de_performance)

    def test_no_borran_las_mismas_claves(self):
        """Lo que vuelve peligrosa la «deduplicación»: no son copias, una borra tres
        claves más. Los números son el ratchet; si cambian, la Ola 4 tiene que decir
        por qué."""
        from core.performance import cache_utils
        from dashboard import utils

        cache.clear()
        self.addCleanup(cache.clear)
        claves = ("contar_usuarios", "contar_ciudadanos", "stats_legajos", "alertas_activas")

        for clave in claves:
            cache.set(clave, "valor", 300)
        cache_utils.invalidate_dashboard_cache()
        sobreviven_a_performance = {c for c in claves if cache.get(c) is not None}

        for clave in claves:
            cache.set(clave, "valor", 300)
        utils.invalidate_dashboard_cache()
        sobreviven_a_dashboard = {c for c in claves if cache.get(c) is not None}

        self.assertEqual(sobreviven_a_performance, {"stats_legajos", "alertas_activas"})
        self.assertEqual(sobreviven_a_dashboard, set())

    def test_el_servicio_de_ciudadanos_tiene_llamadores(self):
        """Desvío de la ficha, verificado contra el código: la ficha decía que
        `CiudadanosService.invalidate_ciudadanos_cache` no tenía llamadores. Los tiene
        —las tres vistas de ciudadanos—, así que la función de `dashboard/utils.py`
        **sí** se ejecuta en producción y borrarla no es gratis.
        """
        import ast
        from pathlib import Path

        fuente = (Path(__file__).resolve().parents[2] / "legajos" / "views" / "ciudadanos.py").read_text(
            encoding="utf-8"
        )
        arbol = ast.parse(fuente)
        llamadas = [
            nodo
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr == "invalidate_ciudadanos_cache"
        ]

        self.assertEqual(len(llamadas), 3)
