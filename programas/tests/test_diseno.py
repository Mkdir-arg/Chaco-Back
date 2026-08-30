"""Diseño del formulario por convocatoria y definición v2 (Cambio 58, tasks
#339 y #340, análisis #326)."""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from programas.models import (
    CanalFormulario,
    Convocatoria,
    DisenoFormulario,
    GrupoRequisito,
    ItemDiseno,
    OrigenRequisito,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)
from programas.services import condiciones
from programas.services.becas import definicion_formulario
from programas.services.diseno import (
    clave_pregunta,
    clave_requisito,
    items_ordenados,
    items_planos,
    obtener_o_crear_diseno,
    plan_por_defecto,
    reconciliar,
    serializar,
)


class _Base(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=100)
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Resistencia", cupo_maximo=40)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas Secundaria 2026",
            segmento=self.segmento,
            subsegmento=self.subsegmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario", "Terciario"],
            segmento=self.segmento,
            orden=1,
        )
        self.certificado = RequisitoNativo.objects.create(
            texto="Certificado de alumno regular", tipo=TipoCampo.ARCHIVO, segmento=self.segmento, orden=2
        )
        self.localidad = RequisitoNativo.objects.create(
            texto="Barrio", tipo=TipoCampo.STRING, segmento=self.segmento, subsegmento=self.subsegmento, orden=1
        )
        self.tenencia = PreguntaGlobal.objects.create(
            texto="Tenencia de la vivienda", tipo=TipoCampo.SELECTOR, opciones=["Propia", "Alquilada"], orden=600
        )
        self.territorial = User.objects.create_user("terri_dis")
        self.rel_app = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=timezone.now(),
            zona="Zona",
        )
        self.rel_link = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )

    def _claves(self, items):
        return [i.clave for i in items]


class PlanPorDefectoTests(_Base):
    def test_arranca_con_los_grupos_del_catalogo_y_uno_por_nivel(self):
        items = plan_por_defecto(self.convocatoria)
        grupos = [i.clave for i in items if i.es_grupo]
        self.assertEqual(
            grupos,
            ["g-datos_personales", "g-contacto", "g-apoderado", "g-cuestionario", "g-segmento", "g-subsegmento"],
        )
        # Cada campo cuelga del grupo que lo precede.
        for item in items:
            if item.es_campo:
                self.assertIsNotNone(item.padre)
        self.assertIn(clave_pregunta(self.tenencia), self._claves(items))
        self.assertIn(clave_requisito(self.nivel), self._claves(items))
        self.assertIn(clave_requisito(self.localidad), self._claves(items))

    def test_el_apoderado_nace_con_la_condicion_por_defecto(self):
        apoderado = next(i for i in plan_por_defecto(self.convocatoria) if i.clave == "g-apoderado")
        self.assertEqual(apoderado.condicion["reglas"][0]["op"], "edad_menor")
        self.assertEqual(apoderado.titulo, "Apoderado")
        self.assertTrue(apoderado.subtitulo)

    def test_no_escribe_nada(self):
        plan_por_defecto(self.convocatoria)
        self.assertFalse(DisenoFormulario.objects.exists())
        self.assertFalse(ItemDiseno.objects.exists())

    def test_un_grupo_sin_preguntas_no_aparece(self):
        GrupoRequisito.objects.create(clave="vacio", nombre="Vacío", orden=5)
        self.assertNotIn("g-vacio", self._claves(plan_por_defecto(self.convocatoria)))

    def test_sin_programa_no_hay_grupo_de_programa(self):
        self.assertNotIn("g-programa", self._claves(plan_por_defecto(self.convocatoria)))


class GenerarYReconciliarTests(_Base):
    def test_abrir_por_primera_vez_persiste_el_plan(self):
        diseno, avisos = obtener_o_crear_diseno(self.convocatoria)
        self.assertEqual(avisos, {})
        self.assertEqual(diseno.version, 1)
        guardados = items_ordenados(diseno)
        self.assertEqual(self._claves(guardados), self._claves(plan_por_defecto(self.convocatoria)))
        self.assertTrue(all(i.padre_id for i in guardados if i.es_campo))

    def test_un_requisito_nuevo_aparece_al_final_de_su_grupo(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        nuevo = RequisitoNativo.objects.create(texto="Escuela", tipo=TipoCampo.STRING, segmento=self.segmento, orden=3)
        _, avisos = obtener_o_crear_diseno(self.convocatoria)
        self.assertEqual(avisos["agregados"], ["Escuela"])
        diseno.refresh_from_db()
        self.assertEqual(diseno.version, 2)
        segmento = [i for i in items_ordenados(diseno) if i.padre is not None and i.padre.clave == "g-segmento"]
        self.assertEqual(segmento[-1].clave, clave_requisito(nuevo))

    def test_una_pregunta_nueva_va_a_su_grupo_del_catalogo(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        contacto = GrupoRequisito.objects.get(clave="contacto")
        nueva = PreguntaGlobal.objects.create(texto="Teléfono alternativo", tipo=TipoCampo.STRING, grupo=contacto, orden=650)
        reconciliar(diseno)
        item = diseno.items.get(clave=clave_pregunta(nueva))
        self.assertEqual(item.padre.clave, "g-contacto")

    def test_lo_borrado_o_inactivo_sale_y_se_avisa(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        self.tenencia.activo = False
        self.tenencia.save(update_fields=["activo"])
        self.certificado.delete()  # CASCADE borra el ítem; la reconciliación lo informa como ausente sin romperse
        avisos = reconciliar(diseno)
        self.assertIn("Tenencia de la vivienda", avisos["quitados"])
        self.assertFalse(diseno.items.filter(clave=clave_pregunta(self.tenencia)).exists())
        self.assertFalse(diseno.items.filter(clave=clave_requisito(self.certificado)).exists())

    def test_quitar_la_fuente_elimina_la_condicion_con_aviso(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        cert = diseno.items.get(clave=clave_requisito(self.certificado))
        cert.condicion = {"modo": "todas", "reglas": [{"fuente": clave_requisito(self.nivel), "op": "es", "valor": "Terciario"}]}
        cert.save(update_fields=["condicion"])
        RequisitoNativo.objects.filter(pk=self.nivel.pk).delete()
        avisos = reconciliar(diseno)
        self.assertEqual(avisos["condiciones_quitadas"], ["Certificado de alumno regular"])
        cert.refresh_from_db()
        self.assertIsNone(cert.condicion)

    def test_sin_cambios_no_sube_la_version(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        reconciliar(diseno)
        diseno.refresh_from_db()
        self.assertEqual(diseno.version, 1)

    def test_el_orden_del_diseno_manda_sobre_el_catalogo(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        nivel = diseno.items.get(clave=clave_requisito(self.nivel))
        cert = diseno.items.get(clave=clave_requisito(self.certificado))
        nivel.orden, cert.orden = 5, 0
        nivel.save(update_fields=["orden"])
        cert.save(update_fields=["orden"])
        reconciliar(diseno)
        segmento = [i.clave for i in items_ordenados(diseno) if i.padre is not None and i.padre.clave == "g-segmento"]
        self.assertEqual(segmento, [clave_requisito(self.certificado), clave_requisito(self.nivel)])

    def test_la_etiqueta_del_diseno_sobreescribe_el_texto(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        item = diseno.items.get(clave=clave_requisito(self.nivel))
        item.etiqueta = "¿Hasta dónde estudiaste?"
        item.save(update_fields=["etiqueta"])
        campo = next(c for g in serializar(items_ordenados(diseno)) for c in g["items"] if c.get("clave") == item.clave)
        self.assertEqual(campo["texto"], "¿Hasta dónde estudiaste?")
        self.assertEqual(campo["tipo"], TipoCampo.SELECTOR)  # el catálogo sigue mandando el tipo


class SerializacionTests(_Base):
    def test_grupos_con_campos_y_condiciones(self):
        grupos = serializar(plan_por_defecto(self.convocatoria), CanalFormulario.LINK)
        claves = [g["clave"] for g in grupos]
        self.assertEqual(claves[:3], ["g-datos_personales", "g-contacto", "g-apoderado"])
        apoderado = grupos[2]
        self.assertEqual(apoderado["titulo"], "Apoderado")
        self.assertEqual(apoderado["condicion"]["modo"], "todas")
        dni = next(c for c in grupos[0]["items"] if c["vinculo"] == "dni")
        self.assertEqual(dni["origen"], OrigenRequisito.LEGAJO)
        self.assertEqual(dni["tipo_item"], "campo")
        self.assertTrue(dni["clave"].startswith("pg-"))

    def test_filtra_por_canal_y_omite_grupos_vacios(self):
        solo_app = PreguntaGlobal.objects.create(texto="Foto DNI físico", tipo=TipoCampo.ARCHIVO, canal="app", orden=700)
        grupo_app = GrupoRequisito.objects.create(clave="solo-app", nombre="Solo en campo", orden=6, canal="app")
        PreguntaGlobal.objects.create(texto="Observación del territorial", tipo=TipoCampo.STRING, grupo=grupo_app, orden=701)
        items = plan_por_defecto(self.convocatoria)
        link = serializar(items, CanalFormulario.LINK)
        app = serializar(items, CanalFormulario.APP)
        claves_link = [c["clave"] for g in link for c in g["items"]]
        claves_app = [c["clave"] for g in app for c in g["items"]]
        self.assertNotIn(clave_pregunta(solo_app), claves_link)
        self.assertIn(clave_pregunta(solo_app), claves_app)
        self.assertNotIn("g-solo-app", [g["clave"] for g in link])
        self.assertIn("g-solo-app", [g["clave"] for g in app])

    def test_items_planos_para_el_motor(self):
        planos = items_planos(plan_por_defecto(self.convocatoria), CanalFormulario.LINK)
        self.assertEqual(condiciones.validar_coherencia(planos), {})
        apoderado = next(p for p in planos if p["clave"] == "g-apoderado")
        fecha = next(p for p in planos if p["clave"].startswith("pg-") and p.get("tipo_campo") == TipoCampo.DATE)
        # La fuente de la condición del apoderado es la fecha de nacimiento del titular, que está antes.
        self.assertLess(planos.index(fecha), planos.index(apoderado))

    def test_campo_propio_se_serializa_desde_su_definicion(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        grupo = diseno.items.get(clave="g-segmento")
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-abc12345",
            padre=grupo,
            orden=9,
            canal="link",
            propio={"texto": "Escuela a la que asistís", "tipo": "SELECTOR", "opciones": ["A", "B"], "presentacion": "BUSCADOR", "obligatorio": False},
        )
        ItemDiseno.objects.create(diseno=diseno, tipo=ItemDiseno.Tipo.TEXTO, clave="t-1", padre=grupo, orden=8, texto="Adjuntá el certificado.")
        link = serializar(items_ordenados(diseno), CanalFormulario.LINK)
        segmento = next(g for g in link if g["clave"] == "g-segmento")
        tipos = [c.get("tipo_item") or c["tipo"] for c in segmento["items"]]
        self.assertIn("texto", tipos)
        propio = next(c for c in segmento["items"] if c.get("clave") == "cp-abc12345")
        self.assertEqual(propio["alcance"], "propio")
        self.assertEqual(propio["presentacion"], "BUSCADOR")
        self.assertIsNone(propio["id"])
        app = serializar(items_ordenados(diseno), CanalFormulario.APP)
        self.assertNotIn("cp-abc12345", [c.get("clave") for g in app for c in g["items"]])


class DefinicionV2Tests(_Base):
    def test_sin_diseno_sirve_el_plan_por_defecto_sin_escribir(self):
        definicion = definicion_formulario(self.rel_link)
        self.assertEqual(definicion["version"], 0)
        self.assertEqual(definicion["canal"], "link")
        self.assertEqual([g["clave"] for g in definicion["items"]][:3], ["g-datos_personales", "g-contacto", "g-apoderado"])
        self.assertFalse(DisenoFormulario.objects.exists())

    def test_con_diseno_sirve_lo_guardado_con_su_version(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        diseno.tocar()
        definicion = definicion_formulario(self.rel_app)
        self.assertEqual(definicion["version"], 2)
        self.assertEqual(definicion["canal"], "app")

    def test_las_listas_planas_siguen_igual_para_la_app_vieja(self):
        definicion = definicion_formulario(self.rel_app)
        self.assertEqual([c["texto"] for c in definicion["globales"] if c["origen"] == "pregunta"], [c["texto"] for c in definicion["globales"]])
        self.assertIn("Tenencia de la vivienda", [c["texto"] for c in definicion["globales"]])
        self.assertEqual({c["texto"] for c in definicion["requisitos"]}, {"Nivel educativo", "Certificado de alumno regular", "Barrio"})
        for clave in ("requiere_gps", "globales", "requisitos"):
            self.assertIn(clave, definicion)

    def test_los_vinculados_viajan_en_items_pero_no_en_las_planas(self):
        definicion = definicion_formulario(self.rel_link)
        anidados = [c for g in definicion["items"] for c in g["items"] if c.get("tipo_item") == "campo"]
        self.assertTrue(any(c["origen"] == "legajo" for c in anidados))
        self.assertFalse(any(c["origen"] == "legajo" for c in definicion["globales"]))
