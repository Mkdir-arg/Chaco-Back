"""Ningún módulo de tests de Becas vuelve a depender de que otro haya corrido antes.

TST-02. El 06-oct-2026, corriendo los 77 módulos de `programas/tests/` **uno por
uno**, cinco fallaban: `test_becas_handlers_inline` (12 fallas), `test_pausa_form`
(6), `test_becas_cupo_diseno` (4), `test_becas_convocatoria_subsegmentos` (3) y
`test_pausas` (1), casi todas con `403 != 200`. Pasaban en la suite porque un módulo
anterior corría `seed_becas` y dejaba el Programa Becas en la clave de proceso
`programas:becas`, que **sobrevive al rollback de la base**. Con `--shuffle` la suite
se ponía roja: 21 fallas con la semilla 1234 y 26 con la 777.

Este módulo tiene dos mitades y ninguna intenta ser una ley general:

1. **El mecanismo, probado de verdad** (`MecanismoDelGuardTests`). Sin la fila
   `Programa(codigo="BECAS")` y con la caché limpia, una pantalla de Becas da 403
   **también para un superusuario**; con `ProgramaBecasSembrado` da 200. Si alguien
   le saca el `crear_programas` o el `cache.clear()` al mixin, acá se ve. Y la
   contracara —el 403 que se convierte en 200 por una caché sucia que la base ya no
   respalda— es el modo de falla exacto que hacía que los cinco módulos pasaran
   "gratis".
2. **El ratchet de los seis módulos medidos** (`ModulosMedidosTests`). Una clase
   nueva en cualquiera de ellos sin el mixin los devuelve a depender del orden.

Lo que **no** se intentó: deducir por AST qué módulo necesita el Programa. Medido,
ese criterio marca 10 módulos que en realidad pasan solos (lo consiguen por caminos
que el AST no ve), así que sería un gate que miente. La propiedad general —«cada
módulo pasa solo»— se mide corriendo la suite en otro orden, y eso vive en el job
**no bloqueante** `Orden y paralelo` de `pr-backend.yml` (`manage.py test --shuffle`),
que es la única forma honesta de afirmarla.
"""

import unittest
from io import StringIO

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from programas.models import Programa
from programas.tests.base_becas import BecasPantallaTestCase, ProgramaBecasSembrado

#: Módulos que **se midieron** fallando solos (más el que estrenó el patrón en R-11)
#: y que por eso tienen que seguir heredando el mixin en todas sus clases.
MODULOS_MEDIDOS = {
    "test_becas_handlers_inline": 12,
    "test_pausa_form": 6,
    "test_becas_cupo_diseno": 4,
    "test_becas_convocatoria_subsegmentos": 3,
    "test_pausas": 1,
    # No estaba entre los cinco: lo arregló antes el Cambio 130 (PR R-11) con este
    # mismo patrón, y es de donde salió el mixin.
    "test_becas_convocatorias_diseno": 0,
}


class MecanismoDelGuardTests(TestCase):
    """Por qué el orden importaba: el guard de Becas falla cerrado (RED-56)."""

    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_superuser("admin-aislamiento", password="x")
        self.client.force_login(self.admin)

    def test_sin_el_programa_becas_la_pantalla_da_403_aunque_seas_superusuario(self):
        self.assertFalse(Programa.objects.filter(codigo=Programa.TipoPrograma.BECAS).exists())

        respuesta = self.client.get(reverse("becas:convocatorias"))

        self.assertEqual(respuesta.status_code, 403)

    def test_con_el_programa_sembrado_la_misma_pantalla_abre(self):
        """Control: el 403 de arriba es por el Programa, no por otra cosa."""
        call_command("crear_programas", stdout=StringIO())
        cache.clear()

        self.assertEqual(self.client.get(reverse("becas:convocatorias")).status_code, 200)

    def test_la_cache_sucia_abre_una_pantalla_que_la_base_ya_no_respalda(self):
        """El modo de falla que hacía pasar «gratis» a los cinco módulos.

        La clave `programas:becas` es de proceso: el rollback de la base entre tests
        no la toca. Un módulo que corrió antes deja ahí el Programa y el siguiente
        abre la pantalla **sin tener la fila**. Por eso limpiar la caché es parte del
        arreglo y no un detalle: sin el `cache.clear()`, el mixin tapa el problema en
        vez de resolverlo.
        """
        call_command("crear_programas", stdout=StringIO())
        self.client.get(reverse("becas:convocatorias"))  # calienta `programas:becas`
        Programa.objects.filter(codigo=Programa.TipoPrograma.BECAS).delete()

        self.assertEqual(self.client.get(reverse("becas:convocatorias")).status_code, 200)

        cache.clear()

        self.assertEqual(self.client.get(reverse("becas:convocatorias")).status_code, 403)


class MixinSiembraTests(BecasPantallaTestCase):
    """El mixin hace lo que dice: Programa puesto y caché limpia, en cada test."""

    def test_el_programa_becas_existe_al_entrar_al_test(self):
        self.assertTrue(Programa.objects.filter(codigo=Programa.TipoPrograma.BECAS).exists())

    def test_la_pantalla_de_becas_abre_sin_que_haya_corrido_ningun_otro_modulo(self):
        self.client.force_login(User.objects.create_superuser("admin-mixin", password="x"))

        self.assertEqual(self.client.get(reverse("becas:convocatorias")).status_code, 200)


class ModulosMedidosTests(SimpleTestCase):
    """Ratchet: los seis módulos medidos siguen sembrando su propio Programa."""

    def test_todas_las_clases_de_los_modulos_medidos_heredan_el_mixin(self):
        import importlib

        sin_sembrar = []
        for modulo in sorted(MODULOS_MEDIDOS):
            importado = importlib.import_module(f"programas.tests.{modulo}")
            for nombre in dir(importado):
                clase = getattr(importado, nombre)
                if not isinstance(clase, type) or not issubclass(clase, unittest.TestCase):
                    continue
                if clase.__module__ != importado.__name__:
                    continue  # importada de otro lado: la gobierna su propio módulo
                if not issubclass(clase, ProgramaBecasSembrado):
                    sin_sembrar.append(f"{modulo}.{nombre}")

        self.assertEqual(
            sin_sembrar,
            [],
            "Estos módulos ya fallaron corridos solos (TST-02) y volverían a hacerlo: "
            "toda clase suya tiene que heredar de "
            "`programas.tests.base_becas.BecasPantallaTestCase` (o sumar el mixin "
            "`ProgramaBecasSembrado` a su base) y llamar a `super().setUp()`. "
            f"Clases sin sembrar: {sin_sembrar}",
        )

    def test_los_modulos_medidos_existen(self):
        """Un ratchet que apunta a un módulo renombrado deja de medir y nadie se entera."""
        import importlib.util

        faltantes = [m for m in MODULOS_MEDIDOS if importlib.util.find_spec(f"programas.tests.{m}") is None]

        self.assertEqual(faltantes, [])
