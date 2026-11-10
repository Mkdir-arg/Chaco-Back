"""Ola 7 · PR 3 — BEC-25 y el seguimiento MINOR de #646 que vive en `programas`.

* ``SiguienteNombreTests`` (BEC-25) — las dos pantallas que listaban relevamientos
  calculaban ``Relevamiento.proximo_nombre()`` en cada carga y lo dejaban en el
  contexto. Ningún template lo imprimía, y encima se calculaba **sin convocatoria**:
  el valor no era siquiera el nombre que el alta iba a usar.
* ``InvalidacionAlCommitTests`` (seguimiento de #646) — la invalidación del cache de
  ``Programa`` corría dentro de la transacción: entre el ``cache.delete`` y el COMMIT
  otra request podía releer la fila vieja y recachearla 300 s.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from programas.models import Convocatoria, Programa, Relevamiento, Segmento
from programas.services.programa_cache import clave_de, programa_por_codigo


class SiguienteNombreTests(TestCase):
    """BEC-25 · nadie leía `siguiente_nombre` y la clase ya no lo calcula."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.usuario = get_user_model().objects.create_superuser("admin-bec25", "a@b.com", "x")
        self.client.force_login(self.usuario)
        hoy = timezone.localdate()
        self.segmento = Segmento.objects.create(nombre="Segmento BEC-25", cupo_maximo=100, activo=True)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria BEC-25",
            segmento=self.segmento,
            fecha_inicio=hoy,
            fecha_fin=hoy,
            activo=True,
        )

    def test_el_detalle_de_convocatoria_no_calcula_el_nombre_siguiente(self):
        respuesta = self.client.get(reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("siguiente_nombre", respuesta.context)

    def test_el_listado_de_relevamientos_no_calcula_el_nombre_siguiente(self):
        respuesta = self.client.get(reverse("becas:relevamientos"))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("siguiente_nombre", respuesta.context)

    def test_el_nombre_real_lo_sigue_poniendo_el_alta(self):
        """Lo que se borró es el preview muerto, no la numeración.

        Si esto cayera, el borrado se habría llevado el nombre de verdad, que es lo
        único que la persona ve.
        """
        territorial = get_user_model().objects.create_user("territorial-bec25", password="x")
        relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=territorial,
            fecha_asignada=timezone.localdate(),
            zona="Zona BEC-25",
        )

        self.assertEqual(relevamiento.nombre, f"Relevamiento {relevamiento.numero:03d} · {self.convocatoria.nombre}")

    def test_la_clase_ya_no_expone_proximo_nombre(self):
        """El classmethod se fue con sus dos únicos llamadores; sus piezas quedan."""
        self.assertFalse(hasattr(Relevamiento, "proximo_nombre"))
        self.assertTrue(hasattr(Relevamiento, "proximo_numero"))
        self.assertTrue(hasattr(Relevamiento, "nombre_para"))


class InvalidacionAlCommitTests(TestCase):
    """Seguimiento de #646 · la clave de `Programa` se borra **después** del COMMIT.

    El changeform de `/admin/` es atómico. Con el `cache.delete` adentro de la
    transacción, entre el borrado y el COMMIT cualquier otra request todavía lee la
    fila **anterior** en la base y la vuelve a cachear 300 s: queda exactamente el
    modo de falla que RED-80 fue a cerrar.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.programa = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")

    def test_el_borrado_de_la_clave_espera_al_commit(self):
        programa_por_codigo("DISPOSITIVOS")
        self.assertIsNotNone(cache.get(clave_de("DISPOSITIVOS")))

        with self.captureOnCommitCallbacks(execute=True):
            self.programa.nombre = "Dispositivos y Hogares"
            self.programa.save()
            # Todavía adentro de la transacción: la fila que los demás pueden leer
            # sigue siendo la vieja, así que borrar la clave acá no sirve de nada.
            self.assertIsNotNone(cache.get(clave_de("DISPOSITIVOS")))

        self.assertIsNone(cache.get(clave_de("DISPOSITIVOS")))

    def test_un_cambio_de_codigo_borra_las_dos_claves_al_commitear(self):
        programa_por_codigo("DISPOSITIVOS")

        with self.captureOnCommitCallbacks(execute=True):
            self.programa.codigo = "DISPOSITIVOS_V2"
            self.programa.save()

        self.assertIsNone(cache.get(clave_de("DISPOSITIVOS")))
        self.assertIsNone(cache.get(clave_de("DISPOSITIVOS_V2")))

    def test_una_transaccion_revertida_no_borra_nada(self):
        """Si el alta se revierte, la fila nunca cambió: la clave sigue siendo válida."""
        programa_por_codigo("DISPOSITIVOS")

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.programa.nombre = "Nunca commiteado"
            self.programa.save()

        self.assertEqual(len(callbacks), 1)
        self.assertIsNotNone(cache.get(clave_de("DISPOSITIVOS")))

    def test_el_borrado_de_un_programa_tambien_espera_al_commit(self):
        programa_por_codigo("DISPOSITIVOS")

        with self.captureOnCommitCallbacks(execute=True):
            self.programa.delete()
            self.assertIsNotNone(cache.get(clave_de("DISPOSITIVOS")))

        self.assertIsNone(cache.get(clave_de("DISPOSITIVOS")))
