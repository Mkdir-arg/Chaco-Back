"""Vigencia del programa SIIS vinculado a un segmento.

Cubre el ciclo completo: se congela el detalle al vincular, la sincronización
detecta la baja en SIIS y el segmento queda bloqueado para operar.
"""

import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import TestCase

from programas.forms import RelevamientoForm, SegmentoCreateForm
from programas.models import Convocatoria, Relevamiento, Segmento, Subsegmento
from programas.services.siis_sync import sincronizar_estado_programas

PROGRAMA_ACTIVO = {
    "id": 38,
    "nombre": "Fuego y Barro",
    "descripcion": "Producción territorial",
    "jurisdiccion_id": 3,
    "estado": "ACTIVO",
    "controla_empleo_publico": True,
    "controla_horas_docentes": False,
    "controla_duplicidad_becas": True,
    "controla_smvm": True,
    "controla_edad_minima": True,
    "edad_minima": 18,
}


class SnapshotDelProgramaTests(TestCase):
    def setUp(self):
        self.coordinador = User.objects.create_user("coordinador-siis", password="x")

    @patch("programas.forms.listar_programas", return_value=[PROGRAMA_ACTIVO])
    def test_el_alta_congela_el_detalle_del_programa(self, _catalogo):
        form = SegmentoCreateForm(
            {
                "siis_programa_id": 38,
                "descripcion": "Segmento de prueba",
                "cupo_maximo": 100,
                "coordinador": self.coordinador.pk,
            }
        )
        # El queryset de coordinadores depende del RBAC; acá solo interesa el snapshot.
        form.fields["coordinador"].queryset = User.objects.all()
        self.assertTrue(form.is_valid(), form.errors)
        segmento = form.save()

        self.assertEqual(segmento.siis_programa_id, 38)
        self.assertEqual(segmento.siis_programa_estado, Segmento.EstadoSiis.ACTIVO)
        self.assertEqual(segmento.siis_programa_datos["nombre"], "Fuego y Barro")
        self.assertEqual(segmento.siis_programa_datos["edad_minima"], 18)
        self.assertIsNotNone(segmento.siis_vinculado_en)
        # El nombre del segmento se toma del catálogo (comportamiento del modal de alta).
        self.assertEqual(segmento.nombre, "Fuego y Barro")


class DetalleInformativoTests(TestCase):
    """El filtro que alimenta el botón "!" del listado y del detalle."""

    def setUp(self):
        self.segmento = Segmento.objects.create(
            nombre="Fuego y Barro",
            cupo_maximo=100,
            siis_programa_id=38,
            siis_programa_datos={**PROGRAMA_ACTIVO, "descripcion": 'Con "comillas" y <b>'},
            siis_programa_estado=Segmento.EstadoSiis.INACTIVO,
        )

    def test_el_atributo_renderizado_queda_como_json_valido(self):
        """Las comillas se escapan a &quot; y el navegador las devuelve al parsear."""
        render = Template('{% load becas_extras %}<button @click="openInfo({{ s|siis_info }})">').render(
            Context({"s": self.segmento})
        )

        self.assertNotIn('openInfo({"', render)
        self.assertIn("&quot;", render)
        crudo = render.split("openInfo(", 1)[1].rsplit(")", 1)[0]
        datos = json.loads(crudo.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
        self.assertEqual(datos["id"], 38)
        self.assertEqual(datos["nombre"], "Fuego y Barro")
        self.assertEqual(datos["descripcion"], 'Con "comillas" y <b>')
        self.assertEqual(datos["estadoVinculado"], "ACTIVO")
        self.assertEqual(datos["estadoActual"], "INACTIVO")
        self.assertTrue(datos["bloqueado"])
        self.assertIn("Fuego y Barro", datos["motivo"])
        self.assertIn(["Empleo público", True], datos["controles"])
        self.assertEqual(datos["edadMinima"], 18)

    def test_segmento_sin_snapshot_no_rompe(self):
        segmento = Segmento.objects.create(nombre="Sin SIIS", cupo_maximo=10)

        datos = json.loads(
            Template("{% load becas_extras %}{{ s|siis_info }}")
            .render(Context({"s": segmento}))
            .replace("&quot;", '"')
        )

        self.assertIsNone(datos["id"])
        self.assertFalse(datos["bloqueado"])
        self.assertEqual(datos["vinculado"], "")


class SincronizacionDeEstadoTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(
            nombre="Fuego y Barro",
            cupo_maximo=100,
            siis_programa_id=38,
            siis_programa_datos=PROGRAMA_ACTIVO,
            siis_programa_estado=Segmento.EstadoSiis.ACTIVO,
        )

    def _sincronizar(self, catalogo, **kwargs):
        with patch("programas.services.siis_sync.listar_programas_todos", return_value=catalogo):
            return sincronizar_estado_programas(**kwargs)

    def test_detecta_que_el_programa_paso_a_inactivo(self):
        cambios = self._sincronizar([{**PROGRAMA_ACTIVO, "estado": "INACTIVO"}])

        self.segmento.refresh_from_db()
        self.assertEqual(self.segmento.siis_programa_estado, Segmento.EstadoSiis.INACTIVO)
        self.assertIsNotNone(self.segmento.siis_verificado_en)
        self.assertEqual([(c[1], c[2]) for c in cambios], [("ACTIVO", "INACTIVO")])

    def test_programa_ausente_del_catalogo_queda_desconocido(self):
        self._sincronizar([{"id": 99, "nombre": "Otro", "estado": "ACTIVO"}])

        self.segmento.refresh_from_db()
        self.assertEqual(self.segmento.siis_programa_estado, Segmento.EstadoSiis.DESCONOCIDO)

    def test_es_idempotente(self):
        self.assertEqual(self._sincronizar([PROGRAMA_ACTIVO]), [])

    def test_dry_run_no_escribe(self):
        cambios = self._sincronizar([{**PROGRAMA_ACTIVO, "estado": "INACTIVO"}], dry_run=True)

        self.segmento.refresh_from_db()
        self.assertEqual(len(cambios), 1)
        self.assertEqual(self.segmento.siis_programa_estado, Segmento.EstadoSiis.ACTIVO)

    def test_el_snapshot_no_se_pisa_al_sincronizar(self):
        """El detalle informativo es la foto del vínculo, no el estado corriente."""
        self._sincronizar([{**PROGRAMA_ACTIVO, "estado": "INACTIVO", "nombre": "Renombrado"}])

        self.segmento.refresh_from_db()
        self.assertEqual(self.segmento.siis_programa_datos["nombre"], "Fuego y Barro")


class BloqueoPorSiisTests(TestCase):
    def setUp(self):
        self.territorial = User.objects.create_user("territorial-siis", password="x")
        self.segmento = Segmento.objects.create(nombre="Fuego y Barro", cupo_maximo=100, siis_programa_id=38)
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Ladrillo", cupo_maximo=50)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Convocatoria",
            segmento=self.segmento,
            subsegmento=self.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 8, 7),
            fecha_hasta=date(2026, 8, 8),
            zona="Centro",
        )

    def _marcar_inactivo(self):
        self.segmento.siis_programa_datos = PROGRAMA_ACTIVO
        self.segmento.siis_programa_estado = Segmento.EstadoSiis.INACTIVO
        self.segmento.save(update_fields=["siis_programa_datos", "siis_programa_estado", "modificado"])

    def test_segmento_vigente_no_bloquea(self):
        self.assertIsNone(self.segmento.pausa_efectiva)
        self.assertTrue(self.relevamiento.habilitado_en(date(2026, 8, 7)))

    def test_programa_inactivo_bloquea_y_explica_el_motivo(self):
        self._marcar_inactivo()

        pausa = self.segmento.pausa_efectiva
        self.assertIsNotNone(pausa)
        self.assertIn("Fuego y Barro", pausa.pausa_motivo)
        self.assertIn("INACTIVO", pausa.pausa_motivo)

    def test_el_bloqueo_cascadea_hasta_el_relevamiento(self):
        self._marcar_inactivo()
        relevamiento = Relevamiento.objects.select_related("convocatoria__segmento").get(pk=self.relevamiento.pk)

        self.assertIsNotNone(relevamiento.pausa_efectiva)
        self.assertFalse(relevamiento.habilitado_en(date(2026, 8, 7)))

    def test_la_pausa_manual_tiene_precedencia_y_conserva_su_motivo(self):
        self._marcar_inactivo()
        self.segmento.pausado = True
        self.segmento.pausa_motivo = "Pausa operativa"
        self.segmento.save(update_fields=["pausado", "pausa_motivo", "modificado"])

        self.assertEqual(self.segmento.pausa_efectiva.pausa_motivo, "Pausa operativa")

    def test_la_convocatoria_sale_del_selector_de_relevamientos(self):
        form = RelevamientoForm()
        self.assertIn(self.convocatoria, form.fields["convocatoria"].queryset)

        self._marcar_inactivo()

        form = RelevamientoForm()
        self.assertNotIn(self.convocatoria, form.fields["convocatoria"].queryset)
