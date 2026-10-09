"""Ola 7 · PR 3 — BEC-25 y los dos seguimientos MINOR de #646 que viven en `programas`.

* ``SiguienteNombreTests`` (BEC-25) — las dos pantallas que listaban relevamientos
  calculaban ``Relevamiento.proximo_nombre()`` en cada carga y lo dejaban en el
  contexto. Ningún template lo imprimía, y encima se calculaba **sin convocatoria**:
  el valor no era siquiera el nombre que el alta iba a usar.
* ``CreadoPorAlEditarTests`` (seguimiento de #646) — editar una solicitud de merendero
  no sellaba ``creado_por``, así que quien solo tiene ``merendero.crear`` corregía la
  documentación y después el link del widget le contestaba 403.
* ``InvalidacionAlCommitTests`` (seguimiento de #646) — la invalidación del cache de
  ``Programa`` corría dentro de la transacción: entre el ``cache.delete`` y el COMMIT
  otra request podía releer la fila vieja y recachearla 300 s.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core import rbac
from core.rutas_media import PREFIJO_SOLICITUD_MERENDERO
from core.views.media import _documentacion_de_merendero
from programas.models import Convocatoria, Programa, Relevamiento, Segmento, SolicitudMerendero
from programas.services.programa_cache import clave_de, programa_por_codigo
from programas.tests.test_merenderos import permiso
from users.models import RolMeta


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


class CreadoPorAlEditarTests(TestCase):
    """Seguimiento de #646 · editar una solicitud sella `creado_por` si está vacío.

    `creado_por` es lo que `core.views.media._documentacion_de_merendero` usa para
    dejar que quien solo tiene `merendero.crear` baje **su** documentación. El alta lo
    sellaba y la edición no, así que una solicitud anterior al campo quedaba con el
    link roto justo para el operador que acababa de subir el archivo.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.programa = Programa.objects.create(
            codigo="MERENDEROS", nombre="Merenderos", tipo=Programa.TipoPrograma.MERENDEROS
        )
        rol = Group.objects.create(name="Alta Merenderos")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(permiso("merendero.crear"))
        self.operador = get_user_model().objects.create_user("alta-merenderos", password="x")
        self.operador.groups.add(rol)
        self.client.force_login(self.operador)

    def _solicitud(self, codigo, creado_por=None):
        return SolicitudMerendero.objects.create(
            codigo=codigo,
            nombre="Amanecer",
            domicilio="Calle 5",
            zona="Sur",
            barrio="Barrio Sur",
            dias_horarios="Martes",
            responsable_nombre="Responsable",
            documentacion=f"{PREFIJO_SOLICITUD_MERENDERO}{codigo}.pdf",
            estado=SolicitudMerendero.Estado.OBSERVADA,
            creado_por=creado_por,
        )

    def _editar(self, solicitud, **extra):
        datos = {
            "codigo": solicitud.codigo,
            "nombre": solicitud.nombre,
            "domicilio": "Calle 5 bis",
            "zona": solicitud.zona,
            "barrio": solicitud.barrio,
            "dias_horarios": solicitud.dias_horarios,
            "responsable_nombre": solicitud.responsable_nombre,
        }
        datos.update(extra)
        return self.client.post(reverse("merenderos:solicitud_editar", args=[solicitud.pk]), datos)

    def test_una_solicitud_sin_dueno_queda_sellada_por_quien_la_edita(self):
        solicitud = self._solicitud("MER-SIN-DUENO")

        respuesta = self._editar(
            solicitud,
            documentacion=SimpleUploadedFile("respaldo.pdf", b"%PDF-1.4 corregido", content_type="application/pdf"),
        )

        self.assertEqual(respuesta.status_code, 302)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.creado_por, self.operador)

    def test_despues_de_editarla_puede_bajar_la_documentacion_que_subio(self):
        """El síntoma de la ficha: el «Actualmente: /media/…» del widget daba 403."""
        solicitud = self._solicitud("MER-403")
        self.assertFalse(_documentacion_de_merendero(self.operador, solicitud.documentacion.name))

        self._editar(solicitud)

        solicitud.refresh_from_db()
        self.assertTrue(_documentacion_de_merendero(self.operador, solicitud.documentacion.name))

    def test_no_le_roba_la_solicitud_a_un_par(self):
        """Sellar solo si está vacío: la solicitud de otro sigue siendo de otro."""
        par = get_user_model().objects.create_user("otro-alta-merenderos", password="x")
        solicitud = self._solicitud("MER-DE-UN-PAR", creado_por=par)

        self._editar(solicitud)

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.creado_por, par)


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
