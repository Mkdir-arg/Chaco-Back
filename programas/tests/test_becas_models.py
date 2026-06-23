"""Tests de los modelos de Becas (#73)."""
from datetime import date
from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from legajos.models import Ciudadano
from programas.models import (
    AsignacionCoordinador,
    Convocatoria,
    Formulario,
    ListaEspera,
    PreguntaGlobal,
    Programa,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
    TracaFormulario,
)
from programas.services.becas import (
    coordinador_gestiona_segmento,
    es_menor,
    get_campos_formulario,
    get_segmentos_coordinador,
    resolver_ciudadano_offline,
)


class SeedBecasCommandTests(TestCase):
    """El command seed_becas deja el programa y los adjuntos fijos (idempotente)."""

    def test_seed_crea_programa_y_adjuntos(self):
        call_command("seed_becas", stdout=StringIO())
        self.assertTrue(Programa.objects.filter(codigo="BECAS", estado="ACTIVO").exists())
        archivos = PreguntaGlobal.objects.filter(tipo=TipoCampo.ARCHIVO, obligatorio=True, activo=True)
        self.assertGreaterEqual(archivos.count(), 5)
        self.assertTrue(archivos.filter(texto="Foto DNI - Frente").exists())

    def test_seed_es_idempotente(self):
        call_command("seed_becas", stdout=StringIO())
        call_command("seed_becas", stdout=StringIO())
        self.assertEqual(Programa.objects.filter(codigo="BECAS").count(), 1)
        self.assertEqual(
            PreguntaGlobal.objects.filter(texto="Foto DNI - Frente").count(), 1
        )


class SegmentoCupoTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Producción Territorial", cupo_maximo=200)

    def test_subsegmento_dentro_de_cupo_ok(self):
        sub = Subsegmento(segmento=self.segmento, nombre="Ladrillo", cupo_maximo=120)
        sub.full_clean()  # no levanta
        sub.save()
        self.assertEqual(self.segmento.cupo_distribuido, 120)
        self.assertEqual(self.segmento.cupo_disponible, 80)

    def test_subsegmento_supera_cupo_levanta_validation_error(self):
        Subsegmento.objects.create(segmento=self.segmento, nombre="Ladrillo", cupo_maximo=120)
        carbon = Subsegmento(segmento=self.segmento, nombre="Carbón", cupo_maximo=100)
        with self.assertRaises(ValidationError) as ctx:
            carbon.full_clean()
        self.assertIn("80", str(ctx.exception))  # máximo disponible

    def test_subsegmento_completa_cupo(self):
        Subsegmento.objects.create(segmento=self.segmento, nombre="Ladrillo", cupo_maximo=120)
        carbon = Subsegmento(segmento=self.segmento, nombre="Carbón", cupo_maximo=80)
        carbon.full_clean()
        carbon.save()
        self.assertEqual(self.segmento.cupo_distribuido, 200)
        self.assertEqual(self.segmento.cupo_disponible, 0)


class ConvocatoriaTests(TestCase):
    def setUp(self):
        self.seg_a = Segmento.objects.create(nombre="Segmento A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(nombre="Segmento B", cupo_maximo=100)
        self.sub_b = Subsegmento.objects.create(segmento=self.seg_b, nombre="Sub B", cupo_maximo=50)

    def test_subsegmento_de_otro_segmento_invalido(self):
        conv = Convocatoria(
            nombre="Conv 1",
            segmento=self.seg_a,
            subsegmento=self.sub_b,  # pertenece a seg_b
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        with self.assertRaises(ValidationError):
            conv.full_clean()

    def test_subsegmento_del_segmento_correcto_ok(self):
        conv = Convocatoria(
            nombre="Conv 2",
            segmento=self.seg_b,
            subsegmento=self.sub_b,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        conv.full_clean()
        conv.save()
        self.assertEqual(conv.segmento, self.seg_b)


class RelevamientoTests(TestCase):
    def setUp(self):
        self.territorial = User.objects.create_user("terri")
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=50)
        self.conv = Convocatoria.objects.create(
            nombre="Conv", segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31),
        )

    def test_estados_definidos(self):
        valores = {c[0] for c in Relevamiento.Estado.choices}
        self.assertEqual(
            valores,
            {"ASIGNADO", "EN_CURSO", "FINALIZANDO", "FINALIZADO", "EN_REVISION", "TERMINADO"},
        )

    def test_nombre_autogenerado(self):
        rel = Relevamiento.objects.create(
            convocatoria=self.conv, territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1), zona="Centro",
        )
        self.assertEqual(rel.nombre, "Relevamiento 001")
        self.assertEqual(rel.estado, Relevamiento.Estado.ASIGNADO)


class CamposFormularioTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.sub = Subsegmento.objects.create(segmento=self.segmento, nombre="Sub", cupo_maximo=40)
        # requisito del segmento (heredable) y del subsegmento (propio)
        self.req_seg = RequisitoNativo.objects.create(
            texto="Actividad productiva", tipo=TipoCampo.STRING, segmento=self.segmento, orden=1
        )
        self.req_sub = RequisitoNativo.objects.create(
            texto="Tipo de horno", tipo=TipoCampo.STRING, segmento=self.segmento, subsegmento=self.sub, orden=2
        )
        self.conv_sin_sub = Convocatoria.objects.create(
            nombre="Sin sub", segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31),
        )
        self.conv_con_sub = Convocatoria.objects.create(
            nombre="Con sub", segmento=self.segmento, subsegmento=self.sub,
            fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31),
        )

    def test_pregunta_inactiva_no_aparece(self):
        activa = PreguntaGlobal.objects.create(texto="Tenencia", tipo=TipoCampo.STRING, activo=True, orden=1)
        inactiva = PreguntaGlobal.objects.create(texto="Vieja", tipo=TipoCampo.STRING, activo=False, orden=2)
        globales, _ = get_campos_formulario(self.conv_sin_sub)
        self.assertIn(activa, globales)
        self.assertNotIn(inactiva, globales)

    def test_requisito_segmento_aplica_a_segmento_y_subsegmento(self):
        _, req_sin_sub = get_campos_formulario(self.conv_sin_sub)
        _, req_con_sub = get_campos_formulario(self.conv_con_sub)
        # El requisito del segmento aparece en ambos
        self.assertIn(self.req_seg, req_sin_sub)
        self.assertIn(self.req_seg, req_con_sub)
        # El requisito del subsegmento solo en la convocatoria con subsegmento
        self.assertNotIn(self.req_sub, req_sin_sub)
        self.assertIn(self.req_sub, req_con_sub)


class AsignacionCoordinadorTests(TestCase):
    def setUp(self):
        self.coord = User.objects.create_user("coord")
        self.seg_a = Segmento.objects.create(nombre="A", cupo_maximo=10)
        self.seg_b = Segmento.objects.create(nombre="B", cupo_maximo=10)
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord)

    def test_gestiona_segmento_asignado(self):
        self.assertTrue(coordinador_gestiona_segmento(self.coord, self.seg_a))

    def test_no_gestiona_segmento_no_asignado(self):
        self.assertFalse(coordinador_gestiona_segmento(self.coord, self.seg_b))

    def test_get_segmentos_coordinador(self):
        segs = get_segmentos_coordinador(self.coord)
        self.assertIn(self.seg_a, segs)
        self.assertNotIn(self.seg_b, segs)


class FormularioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("op")
        self.territorial = User.objects.create_user("terri")
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=50)
        self.conv = Convocatoria.objects.create(
            nombre="Conv", segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31),
        )
        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv, territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1), zona="Centro",
        )

    def test_data_guarda_estructura(self):
        form = Formulario.objects.create(
            relevamiento=self.rel, celular="3624100200", email_contacto="a@b.com",
            data={"globales": {"1": "Propia"}, "requisitos": {"5": "Ladrillo"}},
        )
        form.refresh_from_db()
        self.assertEqual(form.data["globales"]["1"], "Propia")
        self.assertEqual(form.data["requisitos"]["5"], "Ladrillo")

    def test_traza_edicion(self):
        form = Formulario.objects.create(
            relevamiento=self.rel, celular="3624100100", email_contacto="a@b.com",
        )
        TracaFormulario.objects.create(
            formulario=form, editado_por=self.user,
            campo="celular", valor_anterior="3624100100", valor_nuevo="3624200200",
        )
        traza = form.trazas.get()
        self.assertEqual(traza.valor_anterior, "3624100100")
        self.assertEqual(traza.valor_nuevo, "3624200200")
        self.assertEqual(traza.editado_por, self.user)

    def test_sync_offline_crea_ciudadano(self):
        form = Formulario.objects.create(
            relevamiento=self.rel, celular="3624100200", email_contacto="a@b.com",
            ciudadano=None,
            datos_identificacion={
                "dni": "99887766", "nombre": "Juan", "apellido": "Pérez",
                "fecha_nacimiento": "1990-01-15", "origen": "manual",
            },
        )
        resolver_ciudadano_offline(form)
        form.refresh_from_db()
        self.assertIsNotNone(form.ciudadano)
        self.assertEqual(form.ciudadano.dni, "99887766")
        self.assertIsNone(form.datos_identificacion)
        self.assertTrue(Ciudadano.objects.filter(dni="99887766").exists())

    def test_sync_offline_linkea_ciudadano_existente_sin_modificar(self):
        existente = Ciudadano.objects.create(dni="55554444", nombre="Ana", apellido="López")
        form = Formulario.objects.create(
            relevamiento=self.rel, celular="3624100200", email_contacto="a@b.com",
            ciudadano=None,
            datos_identificacion={"dni": "55554444", "nombre": "OTRO", "apellido": "OTRO"},
        )
        resolver_ciudadano_offline(form)
        form.refresh_from_db()
        existente.refresh_from_db()
        self.assertEqual(form.ciudadano_id, existente.id)
        # No se modifican los datos del ciudadano existente
        self.assertEqual(existente.nombre, "Ana")
        self.assertEqual(existente.apellido, "López")


class HelpersTests(TestCase):
    def test_es_menor(self):
        ref = date(2026, 6, 23)
        self.assertTrue(es_menor(date(2015, 1, 1), referencia=ref))
        self.assertFalse(es_menor(date(1990, 1, 1), referencia=ref))
        self.assertIsNone(es_menor(None))


class ProgramasGenericosIntactosTests(TestCase):
    """No se rompen los modelos genéricos preexistentes."""

    def test_modelos_genericos_funcionan(self):
        from programas.models import DerivacionPrograma, InscripcionPrograma  # noqa: F401
        prog = Programa.objects.create(codigo="X1", nombre="Otro", estado="ACTIVO")
        ciud = Ciudadano.objects.create(dni="11112222", nombre="N", apellido="A")
        insc = InscripcionPrograma.objects.create(ciudadano=ciud, programa=prog)
        self.assertTrue(insc.codigo)  # se autogenera
