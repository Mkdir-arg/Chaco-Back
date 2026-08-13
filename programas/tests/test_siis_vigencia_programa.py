"""Vigencia del programa SIIS (Programa → Segmento → Subsegmento).

Cubre el ciclo completo: se congela el detalle al vincular el programa, la
sincronización detecta la baja en SIIS y el programa —con todos sus
segmentos— queda bloqueado para operar. También la pausa manual del programa,
que cascadea igual.
"""

import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.template import Context, Template
from django.test import TestCase

from programas.forms import ProgramaSiisCreateForm, RelevamientoForm, SegmentoCreateForm
from programas.models import Convocatoria, ProgramaSiis, Relevamiento, Segmento, Subsegmento
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


def crear_programa(**kwargs):
    defaults = {
        "nombre": "Fuego y Barro",
        "siis_programa_id": 38,
        "siis_programa_datos": PROGRAMA_ACTIVO,
        "siis_programa_estado": ProgramaSiis.EstadoSiis.ACTIVO,
    }
    defaults.update(kwargs)
    return ProgramaSiis.objects.create(**defaults)


class SnapshotDelProgramaTests(TestCase):
    @patch("programas.forms.listar_programas", return_value=[PROGRAMA_ACTIVO])
    def test_el_alta_congela_el_detalle_y_toma_el_nombre_del_catalogo(self, _catalogo):
        form = ProgramaSiisCreateForm({"siis_programa_id": 38})
        self.assertTrue(form.is_valid(), form.errors)
        programa = form.save()

        self.assertEqual(programa.siis_programa_id, 38)
        self.assertEqual(programa.nombre, "Fuego y Barro")
        self.assertEqual(programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)
        self.assertEqual(programa.siis_programa_datos["edad_minima"], 18)
        self.assertIsNotNone(programa.siis_vinculado_en)

    @patch("programas.forms.listar_programas", return_value=[PROGRAMA_ACTIVO])
    def test_un_programa_no_puede_vincularse_dos_veces(self, _catalogo):
        crear_programa()
        form = ProgramaSiisCreateForm({"siis_programa_id": 38})
        self.assertFalse(form.is_valid())
        self.assertIn("ya está vinculado", str(form.errors["siis_programa_id"]))


class AltaDeSegmentoTests(TestCase):
    """El segmento nace dentro de un programa y el nombre es local."""

    def setUp(self):
        self.programa = crear_programa()
        self.coordinador = User.objects.create_user("coordinador-siis", password="x")

    def _form(self, **data):
        payload = {
            "programa": self.programa.pk,
            "nombre": "Producción Territorial",
            "descripcion": "Segmento de prueba",
            "cupo_maximo": 100,
            "coordinador": self.coordinador.pk,
        }
        payload.update(data)
        form = SegmentoCreateForm(payload)
        # El queryset de coordinadores depende del RBAC; acá no interesa.
        form.fields["coordinador"].queryset = User.objects.all()
        return form

    def test_el_nombre_lo_pone_el_operador(self):
        form = self._form()
        self.assertTrue(form.is_valid(), form.errors)
        segmento = form.save()
        self.assertEqual(segmento.nombre, "Producción Territorial")
        self.assertEqual(segmento.programa, self.programa)

    def test_el_programa_es_obligatorio(self):
        form = self._form(programa="")
        self.assertFalse(form.is_valid())
        self.assertIn("programa", form.errors)

    def test_no_se_repite_el_nombre_dentro_del_programa(self):
        Segmento.objects.create(programa=self.programa, nombre="Producción Territorial", cupo_maximo=10)
        form = self._form()
        self.assertFalse(form.is_valid())
        self.assertIn("Ya existe un segmento con ese nombre", str(form.errors["nombre"]))

    def test_el_mismo_nombre_vale_en_otro_programa(self):
        otro = crear_programa(nombre="Otro", siis_programa_id=99)
        Segmento.objects.create(programa=otro, nombre="Producción Territorial", cupo_maximo=10)
        form = self._form()
        self.assertTrue(form.is_valid(), form.errors)


class DetalleInformativoTests(TestCase):
    """El filtro que alimenta el botón "!" del listado y del detalle."""

    def setUp(self):
        self.programa = crear_programa(
            siis_programa_datos={**PROGRAMA_ACTIVO, "descripcion": 'Con "comillas" y <b>'},
            siis_programa_estado=ProgramaSiis.EstadoSiis.INACTIVO,
        )

    def test_el_atributo_renderizado_queda_como_json_valido(self):
        """Las comillas se escapan a &quot; y el navegador las devuelve al parsear."""
        render = Template('{% load becas_extras %}<button @click="openInfo({{ p|siis_info }})">').render(
            Context({"p": self.programa})
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

    def test_programa_sin_snapshot_no_rompe(self):
        programa = ProgramaSiis.objects.create(nombre="Sin datos", siis_programa_id=77)

        datos = json.loads(
            Template("{% load becas_extras %}{{ p|siis_info }}")
            .render(Context({"p": programa}))
            .replace("&quot;", '"')
        )

        self.assertEqual(datos["id"], 77)
        self.assertEqual(datos["nombre"], "Sin datos")
        self.assertFalse(datos["bloqueado"])
        self.assertEqual(datos["vinculado"], "")


class SincronizacionDeEstadoTests(TestCase):
    def setUp(self):
        self.programa = crear_programa()

    def _sincronizar(self, catalogo, **kwargs):
        with patch("programas.services.siis_sync.listar_programas_todos", return_value=catalogo):
            return sincronizar_estado_programas(**kwargs)

    def test_detecta_que_el_programa_paso_a_inactivo(self):
        cambios = self._sincronizar([{**PROGRAMA_ACTIVO, "estado": "INACTIVO"}])

        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_programa_estado, ProgramaSiis.EstadoSiis.INACTIVO)
        self.assertIsNotNone(self.programa.siis_verificado_en)
        self.assertEqual([(c[1], c[2]) for c in cambios], [("ACTIVO", "INACTIVO")])

    def test_programa_ausente_del_catalogo_queda_desconocido(self):
        self._sincronizar([{"id": 99, "nombre": "Otro", "estado": "ACTIVO"}])

        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_programa_estado, ProgramaSiis.EstadoSiis.DESCONOCIDO)

    def test_es_idempotente(self):
        self.assertEqual(self._sincronizar([PROGRAMA_ACTIVO]), [])

    def test_dry_run_no_escribe(self):
        cambios = self._sincronizar([{**PROGRAMA_ACTIVO, "estado": "INACTIVO"}], dry_run=True)

        self.programa.refresh_from_db()
        self.assertEqual(len(cambios), 1)
        self.assertEqual(self.programa.siis_programa_estado, ProgramaSiis.EstadoSiis.ACTIVO)

    def test_el_snapshot_no_se_pisa_al_sincronizar(self):
        """El detalle informativo es la foto del vínculo, no el estado corriente."""
        self._sincronizar([{**PROGRAMA_ACTIVO, "estado": "INACTIVO", "nombre": "Renombrado"}])

        self.programa.refresh_from_db()
        self.assertEqual(self.programa.siis_programa_datos["nombre"], "Fuego y Barro")


class BloqueoPorSiisTests(TestCase):
    def setUp(self):
        self.territorial = User.objects.create_user("territorial-siis", password="x")
        self.programa = crear_programa()
        self.segmento = Segmento.objects.create(programa=self.programa, nombre="Fuego y Barro", cupo_maximo=100)
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
        self.programa.siis_programa_estado = ProgramaSiis.EstadoSiis.INACTIVO
        self.programa.save(update_fields=["siis_programa_estado", "modificado"])

    def test_programa_vigente_no_bloquea(self):
        self.assertIsNone(self.programa.pausa_efectiva)
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
        relevamiento = Relevamiento.objects.select_related("convocatoria__segmento__programa").get(
            pk=self.relevamiento.pk
        )

        self.assertIsNotNone(relevamiento.pausa_efectiva)
        self.assertFalse(relevamiento.habilitado_en(date(2026, 8, 7)))

    def test_la_pausa_manual_del_programa_cascadea_a_los_segmentos(self):
        self.programa.pausado = True
        self.programa.pausa_motivo = "Pausa operativa del programa"
        self.programa.save(update_fields=["pausado", "pausa_motivo", "modificado"])

        self.assertEqual(self.segmento.pausa_efectiva.pausa_motivo, "Pausa operativa del programa")
        self.assertIsNotNone(self.subsegmento.pausa_efectiva)

    def test_la_pausa_manual_del_segmento_tiene_precedencia_y_conserva_su_motivo(self):
        self._marcar_inactivo()
        self.segmento.pausado = True
        self.segmento.pausa_motivo = "Pausa operativa"
        self.segmento.save(update_fields=["pausado", "pausa_motivo", "modificado"])

        self.assertEqual(self.segmento.pausa_efectiva.pausa_motivo, "Pausa operativa")

    def test_segmento_sin_programa_historico_no_bloquea(self):
        """Los segmentos anteriores al nivel Programa siguen operando."""
        historico = Segmento.objects.create(nombre="Histórico", cupo_maximo=10)
        self.assertIsNone(historico.pausa_efectiva)

    def test_la_convocatoria_sale_del_selector_de_relevamientos(self):
        form = RelevamientoForm()
        self.assertIn(self.convocatoria, form.fields["convocatoria"].queryset)

        self._marcar_inactivo()

        form = RelevamientoForm()
        self.assertNotIn(self.convocatoria, form.fields["convocatoria"].queryset)

    def test_la_pausa_manual_del_programa_tambien_saca_la_convocatoria(self):
        self.programa.pausado = True
        self.programa.save(update_fields=["pausado", "modificado"])

        form = RelevamientoForm()
        self.assertNotIn(self.convocatoria, form.fields["convocatoria"].queryset)
