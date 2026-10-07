"""Reglas de negocio de Becas de la Ola 3 (BEC-03..BEC-24).

Cada clase cierra una ficha de `docs/internal/auditoria-2026-10/hallazgos/02-siis-becas.md`
y todas fallan contra el código anterior al PR:

* **BEC-03** — la revisión reevaluaba las condiciones de edad con la fecha de hoy.
* **BEC-04** — una condición cuya fuente no se pide en el canal dejaba el ítem
  oculto para siempre en ese canal, sin que el servidor lo exigiera.
* **BEC-05** — el cupo del subsegmento nunca se aplicó: acá queda fijado que es
  una referencia (decisión D-B05), no un olvido.
* **BEC-06** — se podía mover una convocatoria con casos a otro segmento.
* **BEC-07** — el cupo del segmento se podía bajar por debajo de los aprobados.
* **BEC-09** — un caso sin ciudadano con DNI no se podía rechazar.
* **BEC-10** — un relevamiento con casos en lista de espera no se podía terminar.
* **BEC-15** — la carga de padrón no tomaba el candado del dueño.
* **BEC-16** — el constructor mutaba sin candado y reconciliaba en cada request.
* **BEC-17** — pausar dos veces dejaba dos eventos en el historial inmutable.
* **BEC-20** — la convocatoria aceptaba fin anterior al inicio.
* **BEC-24** — la edición de contacto/apoderado no era atómica.

BEC-18 (fechas «hoy» en UTC) vive en `legajos/tests/test_fechas_locales_bec18.py`,
donde están sus pantallas; RED-50 (la edad unificada), en `test_becas_reglas.py`.
"""

import json
from datetime import date, datetime, timedelta
from datetime import timezone as tz_utc
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.tests.candados import candados_tomados
from core.tests.reloj import reloj_en
from legajos.models import Ciudadano
from programas.forms import ConvocatoriaForm
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_TERRITORIAL
from programas.models import (
    CanalFormulario,
    Convocatoria,
    DisenoFormulario,
    Formulario,
    ItemDiseno,
    ListaEspera,
    PadronHabilitado,
    PreguntaGlobal,
    ProgramaSiis,
    RegistroPausa,
    Relevamiento,
    Segmento,
    Subsegmento,
    TipoCampo,
    TracaFormulario,
    ValidacionSIS,
)
from programas.services import condiciones as cond
from programas.services.cupo import aprobar_o_poner_en_espera, get_cupo_stats
from programas.services.diseno import items_ordenados, items_planos, obtener_o_crear_diseno, reconciliar, serializar
from programas.services.padron import cargar_padron
from programas.services.pausas import cambiar_pausa
from programas.services.respuestas import fecha_de_referencia, respuestas_legibles
from programas.tests.base_becas import BecasPantallaTestCase


def _segmento(nombre="Seg BEC", cupo=100, con_programa=False):
    programa = None
    if con_programa:
        # `Segmento.programa` es obligatorio para `full_clean()`.
        programa = ProgramaSiis.objects.create(nombre=f"Prog {nombre}", siis_programa_id=abs(hash(nombre)) % 10000)
    return Segmento.objects.create(nombre=nombre, cupo_maximo=cupo, programa=programa)


def _convocatoria(segmento, nombre="Conv BEC", **extra):
    datos = {
        "nombre": nombre,
        "segmento": segmento,
        "fecha_inicio": date(2026, 1, 1),
        "fecha_fin": date(2026, 12, 31),
    }
    datos.update(extra)
    return Convocatoria.objects.create(**datos)


# ── BEC-03 ───────────────────────────────────────────────────────────────────


class RespuestasLegiblesFechaDeCargaTests(TestCase):
    """BEC-03: la revisión lee el caso con la fecha en que se respondió."""

    #: Capturado el 10/02/2026 a las 10:00 ART. Quien tenía 17 ese día cumple 18
    #: el 1/3/2026, así que «hoy» (en la revisión) ya lo ve mayor.
    CAPTURA = datetime(2026, 2, 10, 13, 0, tzinfo=tz_utc.utc)
    NACE = date(2008, 3, 1)
    HOY_EN_LA_REVISION = datetime(2026, 6, 1, 13, 0, tzinfo=tz_utc.utc)

    def setUp(self):
        self.segmento = _segmento("Seg BEC-03")
        self.convocatoria = _convocatoria(self.segmento, "Conv BEC-03")
        self.territorial = User.objects.create_user("terri-bec03", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 2, 1),
            zona="Z",
        )
        self.definicion = {
            "version": 1,
            "canal": CanalFormulario.AMBOS,
            "items": [
                {
                    "tipo": "grupo",
                    "clave": "g-datos",
                    "titulo": "Datos",
                    "condicion": None,
                    "items": [
                        {
                            "tipo_item": "campo",
                            "clave": "cp-nac",
                            "texto": "Fecha de nacimiento",
                            "tipo": TipoCampo.DATE,
                            "condicion": None,
                        }
                    ],
                },
                {
                    "tipo": "grupo",
                    "clave": "g-apoderado",
                    "titulo": "Apoderado",
                    # Solo para menores de 18.
                    "condicion": {"modo": "todas", "reglas": [{"fuente": "cp-nac", "op": "edad_menor", "valor": 18}]},
                    "items": [
                        {
                            "tipo_item": "campo",
                            "clave": "cp-apo",
                            "texto": "Nombre del apoderado",
                            "tipo": TipoCampo.STRING,
                            "condicion": None,
                        }
                    ],
                },
            ],
        }
        self.caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            definicion=self.definicion,
            respuestas={"cp-nac": self.NACE.isoformat(), "cp-apo": "Marta Tutora"},
            capturado_en=self.CAPTURA,
        )

    def test_la_fecha_de_referencia_es_la_de_captura_en_hora_local(self):
        self.assertEqual(fecha_de_referencia(self.caso), date(2026, 2, 10))

    def test_sin_captura_vale_la_fecha_de_creacion(self):
        self.caso.capturado_en = None
        self.caso.save(update_fields=["capturado_en"])
        self.assertEqual(fecha_de_referencia(self.caso), self.caso.creado.astimezone().date())

    def test_condicion_de_edad_se_evalua_a_la_fecha_de_carga(self):
        """El grupo del apoderado se pidió (tenía 17) y la revisión lo muestra,
        aunque hoy la persona ya tenga 18."""
        with reloj_en(self.HOY_EN_LA_REVISION):
            bloques = respuestas_legibles(self.caso)
        apoderado = next(b for b in bloques if b["grupo"]["clave"] == "g-apoderado")
        self.assertFalse(
            apoderado["oculto"],
            "Con la fecha de hoy el grupo sale «No se pidió» y esconde la respuesta que la persona dio.",
        )
        fila = next(i for i in apoderado["items"] if i["clave"] == "cp-apo")
        self.assertEqual(fila["valor"], "Marta Tutora")
        self.assertFalse(fila["oculto"])

    def test_un_caso_que_de_verdad_era_mayor_sigue_oculto(self):
        """El arreglo no muestra todo: con la fecha de carga, un mayor de edad
        sigue sin tener el bloque del apoderado."""
        self.caso.respuestas = {"cp-nac": "1990-05-05"}
        self.caso.save(update_fields=["respuestas"])
        with reloj_en(self.HOY_EN_LA_REVISION):
            bloques = respuestas_legibles(self.caso)
        apoderado = next(b for b in bloques if b["grupo"]["clave"] == "g-apoderado")
        self.assertTrue(apoderado["oculto"])


# ── BEC-04 ───────────────────────────────────────────────────────────────────


class CoherenciaPorCanalTests(BecasPantallaTestCase):
    """BEC-04: una condición cuya fuente no entra en el canal es imposible ahí."""

    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = _segmento("Seg BEC-04")
        self.convocatoria = _convocatoria(self.segmento, "Conv BEC-04")
        self.diseno = DisenoFormulario.objects.create(convocatoria=self.convocatoria)
        self.grupo = ItemDiseno.objects.create(
            diseno=self.diseno, tipo=ItemDiseno.Tipo.GRUPO, clave="g-1", orden=0, etiqueta="Grupo"
        )
        # Campo propio que solo se pide en la app.
        self.fuente = ItemDiseno.objects.create(
            diseno=self.diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-solo-app",
            padre=self.grupo,
            orden=0,
            canal=CanalFormulario.APP,
            propio={"texto": "Foto del DNI", "tipo": TipoCampo.STRING, "presentacion": "LISTA"},
        )
        # Campo de ambos canales condicionado a la fuente de arriba.
        self.destino = ItemDiseno.objects.create(
            diseno=self.diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-ambos",
            padre=self.grupo,
            orden=1,
            canal=CanalFormulario.AMBOS,
            propio={"texto": "Aclaración", "tipo": TipoCampo.STRING, "presentacion": "LISTA"},
            condicion={"modo": "todas", "reglas": [{"fuente": "cp-solo-app", "op": "completo"}]},
        )

    def test_el_diseno_entero_sigue_siendo_coherente(self):
        """Control: mirado sin canal no hay nada mal —la fuente existe y está
        antes—, que es por lo que el bug no se veía."""
        self.assertEqual(cond.validar_coherencia(items_planos(items_ordenados(self.diseno))), {})

    def test_condicion_con_fuente_solo_app_en_item_ambos_se_rechaza(self):
        items = items_planos(items_ordenados(self.diseno), CanalFormulario.LINK)
        errores = cond.fuentes_fuera_del_canal(items, "el link público")
        self.assertIn("cp-ambos", errores)
        self.assertIn("no se pide en el link público", errores["cp-ambos"][0])

    def test_en_el_canal_de_la_fuente_no_hay_error(self):
        items = items_planos(items_ordenados(self.diseno), CanalFormulario.APP)
        self.assertEqual(cond.fuentes_fuera_del_canal(items, "la app de campo"), {})

    def test_el_constructor_rechaza_guardar_un_diseno_asi(self):
        """Poner esa condición desde el editor pasa a devolver 400 con el motivo."""
        self.destino.condicion = None
        self.destino.save(update_fields=["condicion"])
        admin = User.objects.create_user("admin-bec04", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)
        resp = self.client.post(
            reverse("becas:formulario_condicion", args=[self.convocatoria.pk, self.destino.clave]),
            data=json.dumps({"condicion": {"modo": "todas", "reglas": [{"fuente": "cp-solo-app", "op": "completo"}]}}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertIn("no se pide en el link público", resp.json()["message"])
        self.destino.refresh_from_db()
        self.assertIsNone(self.destino.condicion, "La mutación tiene que deshacerse entera.")

    def test_una_condicion_entre_campos_del_mismo_canal_se_guarda(self):
        """El arreglo no bloquea lo sano: dos campos «ambos» siguen pudiendo
        condicionarse entre sí."""
        self.fuente.canal = CanalFormulario.AMBOS
        self.fuente.save(update_fields=["canal"])
        self.destino.condicion = None
        self.destino.save(update_fields=["condicion"])
        admin = User.objects.create_user("admin-bec04b", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)
        resp = self.client.post(
            reverse("becas:formulario_condicion", args=[self.convocatoria.pk, self.destino.clave]),
            data=json.dumps({"condicion": {"modo": "todas", "reglas": [{"fuente": "cp-solo-app", "op": "completo"}]}}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.destino.refresh_from_db()
        self.assertIsNotNone(self.destino.condicion)

    def test_definicion_link_no_trae_condiciones_con_fuente_fuera_de_canal(self):
        """Lo ya guardado se sigue sirviendo, pero sin la condición imposible:
        pedir de más es recuperable, no pedir nunca un obligatorio no."""
        items = items_ordenados(self.diseno)
        por_link = serializar(items, CanalFormulario.LINK)
        destino = next(i for g in por_link for i in g["items"] if i["clave"] == "cp-ambos")
        self.assertIsNone(destino["condicion"])

    def test_en_la_app_la_condicion_se_sirve_intacta(self):
        items = items_ordenados(self.diseno)
        por_app = serializar(items, CanalFormulario.APP)
        destino = next(i for g in por_app for i in g["items"] if i["clave"] == "cp-ambos")
        self.assertEqual(destino["condicion"], self.destino.condicion)

    def test_el_comando_de_diagnostico_lo_encuentra_antes_de_desplegar(self):
        from programas.management.commands.verificar_json_guardado import revisar

        problemas = [p for p in revisar() if p["problema"] == "condicion_con_fuente_fuera_del_canal"]
        self.assertEqual(len(problemas), 1, problemas)
        self.assertIn("cp-ambos", problemas[0]["donde"])


# ── BEC-05 ───────────────────────────────────────────────────────────────────


class CupoDelSubsegmentoEsReferenciaTests(TestCase):
    """BEC-05 · decisión **D-B05 = no es tope duro** (default del README §2).

    Queda escrito como conducta esperada, no como olvido: si mañana el cliente
    decide que sí es tope, este test se da vuelta y hay que escribir el conteo
    por subsegmento bajo el mismo lock del segmento.
    """

    def setUp(self):
        self.segmento = _segmento("Seg BEC-05", cupo=10, con_programa=True)
        self.subsegmento = Subsegmento.objects.create(segmento=self.segmento, nombre="Sub", cupo_maximo=1)
        self.convocatoria = _convocatoria(self.segmento, "Conv BEC-05", subsegmento=self.subsegmento)
        self.territorial = User.objects.create_user("terri-bec05", password="x")
        self.usuario = User.objects.create_user("op-bec05", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 2, 1),
            zona="Z",
        )

    def _caso(self, dni):
        """Un caso aprobable: ciudadano con DNI, identidad validada y la consulta
        SIIS en OK, que es lo que `validar_aprobacion` exige además del cupo."""
        ciudadano = Ciudadano.objects.create(dni=dni, nombre="Ana", apellido="Aprobable")
        caso = Formulario.objects.create(
            relevamiento=self.relevamiento,
            estado=Formulario.Estado.ENVIADO,
            ciudadano=ciudadano,
            validado_renaper=True,
        )
        ValidacionSIS.objects.create(
            formulario=caso,
            estado=ValidacionSIS.Estado.OK,
            id_programa=self.segmento.programa.siis_programa_id,
            documento=ciudadano.dni,
            respuesta={"resultado": "OK", "apto": True},
            solicitado_por=self.usuario,
        )
        return caso

    def test_el_cupo_se_mide_por_segmento_no_por_subsegmento(self):
        self.assertEqual(aprobar_o_poner_en_espera(self._caso("30111001"), self.usuario), "aprobado")
        # El subsegmento ya se pasó de su cupo de 1, pero al segmento le sobran 9.
        self.assertEqual(aprobar_o_poner_en_espera(self._caso("30111002"), self.usuario), "aprobado")
        self.assertEqual(get_cupo_stats(self.segmento)["cupo_ocupado"], 2)
        self.assertEqual(Formulario.objects.filter(estado=Formulario.Estado.APROBADO).count(), 2)

    def test_la_suma_de_los_subsegmentos_si_se_valida(self):
        """RN-40 sigue en pie: lo distribuido no puede pasarse del segmento."""
        Subsegmento.objects.create(segmento=self.segmento, nombre="Sub 2", cupo_maximo=20)
        self.segmento.refresh_from_db()
        with self.assertRaises(ValidationError) as caja:
            self.segmento.full_clean()
        self.assertIn("cupo_maximo", caja.exception.message_dict)


# ── BEC-06 y BEC-20 ──────────────────────────────────────────────────────────


class ConvocatoriaEdicionTests(TestCase):
    def setUp(self):
        self.seg_a = _segmento("Seg A BEC-06")
        self.seg_b = _segmento("Seg B BEC-06")
        self.convocatoria = _convocatoria(self.seg_a, "Conv BEC-06")
        self.territorial = User.objects.create_user("terri-bec06", password="x")

    def _data(self, **cambios):
        datos = {
            "nombre": self.convocatoria.nombre,
            "segmento": self.seg_a.pk,
            "subsegmento": "",
            "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-12-31",
            "descripcion": "",
            "activo": "on",
        }
        datos.update(cambios)
        return datos

    def _con_relevamiento(self):
        Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 2, 1),
            zona="Z",
        )

    def test_sin_relevamientos_el_segmento_se_puede_cambiar(self):
        form = ConvocatoriaForm(self._data(segmento=self.seg_b.pk), instance=self.convocatoria)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().segmento_id, self.seg_b.pk)

    def test_no_cambia_segmento_con_relevamientos(self):
        self._con_relevamiento()
        form = ConvocatoriaForm(self._data(segmento=self.seg_b.pk), instance=self.convocatoria)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().segmento_id, self.seg_a.pk, "El POST pisó el segmento igual.")

    def test_los_campos_de_alcance_quedan_deshabilitados(self):
        self._con_relevamiento()
        form = ConvocatoriaForm(instance=self.convocatoria)
        self.assertTrue(form.alcance_congelado)
        for nombre in ConvocatoriaForm.CAMPOS_DE_ALCANCE:
            self.assertTrue(form.fields[nombre].disabled, nombre)
            self.assertIn("relevamientos", form.fields[nombre].help_text)

    def test_el_modelo_tambien_lo_rechaza(self):
        """El form deshabilita; el modelo cubre al admin y a cualquier `full_clean`.

        Se relee de la base porque el alcance original lo guarda `from_db`: un
        objeto recién creado en memoria no tiene contra qué comparar, y pagar una
        consulta en cada `clean()` encarecía toda edición de convocatoria.
        """
        self._con_relevamiento()
        convocatoria = Convocatoria.objects.get(pk=self.convocatoria.pk)
        convocatoria.segmento = self.seg_b
        with self.assertRaises(ValidationError) as caja:
            convocatoria.full_clean()
        self.assertIn("segmento", caja.exception.message_dict)

    def test_sin_relevamientos_el_modelo_no_molesta(self):
        convocatoria = Convocatoria.objects.get(pk=self.convocatoria.pk)
        convocatoria.segmento = self.seg_b
        convocatoria.full_clean()

    def test_guardar_sin_tocar_el_alcance_no_consulta_los_relevamientos(self):
        """El chequeo solo cuesta una consulta cuando el alcance cambió de verdad:
        editar el nombre de una convocatoria no paga nada (presupuesto de
        `edicion_convocatoria`)."""
        self._con_relevamiento()
        convocatoria = Convocatoria.objects.get(pk=self.convocatoria.pk)
        convocatoria.nombre = "Otro nombre"
        with self.assertNumQueries(0):
            convocatoria._validar_alcance_congelado()

    def test_la_fecha_de_fin_no_puede_ser_anterior_a_la_de_inicio(self):
        """BEC-20: si no, nace vencida y `procesar_vencimientos` la cierra sola."""
        form = ConvocatoriaForm(self._data(fecha_inicio="2026-06-01", fecha_fin="2026-05-01"))
        self.assertFalse(form.is_valid())
        self.assertIn("fecha_fin", form.errors)
        self.assertIn("anterior a la de inicio", form.errors["fecha_fin"][0])

    def test_el_modelo_tambien_valida_el_orden_de_las_fechas(self):
        convocatoria = Convocatoria(
            nombre="Al revés",
            segmento=self.seg_a,
            fecha_inicio=date(2026, 6, 1),
            fecha_fin=date(2026, 5, 1),
        )
        with self.assertRaises(ValidationError) as caja:
            convocatoria.full_clean()
        self.assertIn("fecha_fin", caja.exception.message_dict)

    def test_el_mismo_dia_de_inicio_y_fin_es_valido(self):
        form = ConvocatoriaForm(self._data(fecha_inicio="2026-06-01", fecha_fin="2026-06-01", activo=""))
        self.assertTrue(form.is_valid(), form.errors)


# ── BEC-07 ───────────────────────────────────────────────────────────────────


class CupoDelSegmentoNoBajaDeLosAprobadosTests(TestCase):
    def setUp(self):
        self.segmento = _segmento("Seg BEC-07", cupo=10, con_programa=True)
        self.convocatoria = _convocatoria(self.segmento, "Conv BEC-07")
        self.territorial = User.objects.create_user("terri-bec07", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 2, 1),
            zona="Z",
        )
        for _ in range(3):
            Formulario.objects.create(relevamiento=self.relevamiento, estado=Formulario.Estado.APROBADO)

    def test_bajar_el_cupo_por_debajo_de_los_aprobados_se_rechaza(self):
        self.segmento.cupo_maximo = 2
        with self.assertRaises(ValidationError) as caja:
            self.segmento.full_clean()
        mensaje = caja.exception.message_dict["cupo_maximo"][0]
        self.assertIn("3 beneficiarios", mensaje)

    def test_bajarlo_hasta_los_aprobados_se_permite(self):
        self.segmento.cupo_maximo = 3
        self.segmento.full_clean()

    def test_los_no_aprobados_no_cuentan(self):
        Formulario.objects.create(relevamiento=self.relevamiento, estado=Formulario.Estado.ENVIADO)
        self.segmento.cupo_maximo = 3
        self.segmento.full_clean()


# ── BEC-09 y BEC-10 ──────────────────────────────────────────────────────────


class _BaseRevisionBec(BecasPantallaTestCase):
    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = _segmento("Seg BEC-09")
        self.convocatoria = _convocatoria(self.segmento, "Conv BEC-09")
        self.territorial = User.objects.create_user("terri-bec09", password="x")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        self.admin = User.objects.create_user("admin-bec09", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=date(2026, 2, 1),
            zona="Z",
            estado=Relevamiento.Estado.FINALIZADO,
        )
        self.caso = Formulario.objects.create(
            relevamiento=self.relevamiento, estado=Formulario.Estado.ENVIADO, celular="3624100100"
        )
        self.client.force_login(self.admin)


class RechazoSinSiisTests(_BaseRevisionBec):
    """BEC-09: documentar la decisión local no depende de poder consultar SIIS."""

    def _rechazar(self):
        return self.client.post(
            reverse("becas:formulario_rechazar", args=[self.caso.pk]), {"motivo": "No cumple requisitos"}
        )

    def test_rechaza_caso_sin_ciudadano(self):
        self.assertIsNone(self.caso.ciudadano_id)
        self._rechazar()
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Formulario.Estado.RECHAZADO)
        self.assertEqual(self.caso.motivo_rechazo, "No cumple requisitos")

    def test_el_motivo_de_la_no_consulta_queda_en_la_traza(self):
        self._rechazar()
        traza = TracaFormulario.objects.filter(formulario=self.caso, campo="Consulta SIIS")
        self.assertEqual(traza.count(), 1)
        self.assertIn("SIIS", traza.first().valor_nuevo)
        self.assertEqual(traza.first().valor_anterior, "No se pudo consultar")

    def test_rechaza_caso_de_segmento_sin_programa_siis(self):
        self.caso.ciudadano = Ciudadano.objects.create(dni="30111222", nombre="A", apellido="B")
        self.caso.save(update_fields=["ciudadano"])
        self.assertIsNone(self.segmento.programa_id)
        self._rechazar()
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Formulario.Estado.RECHAZADO)

    def test_un_caso_ya_resuelto_sigue_sin_poder_rechazarse(self):
        """El arreglo no abre la puerta: la guarda de estado sigue donde estaba."""
        self.caso.estado = Formulario.Estado.APROBADO
        self.caso.save(update_fields=["estado"])
        self._rechazar()
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.estado, Formulario.Estado.APROBADO)

    def test_el_relevamiento_se_puede_terminar_despues_del_rechazo(self):
        """Era la consecuencia real: el caso quedaba ENVIADO para siempre."""
        self.relevamiento.estado = Relevamiento.Estado.EN_REVISION
        self.relevamiento.save(update_fields=["estado"])
        self._rechazar()
        self.client.post(reverse("becas:revision_terminar", args=[self.relevamiento.pk]))
        self.relevamiento.refresh_from_db()
        self.assertEqual(self.relevamiento.estado, Relevamiento.Estado.TERMINADO)


class TerminarRelevamientoTests(_BaseRevisionBec):
    """BEC-10 · decisión **D-B10 = «en espera» cuenta como revisado**."""

    def setUp(self):
        super().setUp()
        self.relevamiento.estado = Relevamiento.Estado.EN_REVISION
        self.relevamiento.save(update_fields=["estado"])

    def _terminar(self):
        return self.client.post(reverse("becas:revision_terminar", args=[self.relevamiento.pk]), follow=True)

    def test_casos_en_espera_no_bloquean_terminar(self):
        ListaEspera.objects.create(formulario=self.caso, segmento=self.segmento, posicion=1)
        self._terminar()
        self.relevamiento.refresh_from_db()
        self.assertEqual(self.relevamiento.estado, Relevamiento.Estado.TERMINADO)

    def test_un_caso_sin_revisar_sigue_bloqueando(self):
        self._terminar()
        self.relevamiento.refresh_from_db()
        self.assertEqual(self.relevamiento.estado, Relevamiento.Estado.EN_REVISION)

    def test_el_mensaje_aclara_cuantos_hay_en_espera(self):
        ListaEspera.objects.create(formulario=self.caso, segmento=self.segmento, posicion=1)
        pendiente = Formulario.objects.create(relevamiento=self.relevamiento, estado=Formulario.Estado.ENVIADO)
        self.assertIsNotNone(pendiente.pk)
        resp = self._terminar()
        mensajes = [m.message for m in resp.context["messages"]]
        self.assertTrue(any("1 caso(s) sin revisar (1 en lista de espera no cuentan)" in m for m in mensajes), mensajes)

    def test_un_promovido_vuelve_a_contar_como_pendiente(self):
        """Promovido = ya salió de la espera; si sigue ENVIADO, está sin revisar."""
        ListaEspera.objects.create(formulario=self.caso, segmento=self.segmento, posicion=1, promovido=True)
        self._terminar()
        self.relevamiento.refresh_from_db()
        self.assertEqual(self.relevamiento.estado, Relevamiento.Estado.EN_REVISION)


# ── BEC-15 ───────────────────────────────────────────────────────────────────


class PadronConcurrenteTests(TestCase):
    """BEC-15: la carga toma el candado del dueño antes de borrar y reinsertar."""

    def setUp(self):
        self.segmento = _segmento("Seg BEC-15")
        self.convocatoria = _convocatoria(self.segmento, "Conv BEC-15")

    def test_la_carga_bloquea_la_fila_del_duenio(self):
        with candados_tomados(Convocatoria.objects) as candados:
            cargar_padron(self.convocatoria, None, [{"dni": "30111222", "sexo": "F"}])
        self.assertIn(
            "padron.py:cargar_padron",
            candados,
            "Sin el candado del dueño, dos cargas en paralelo se intercalan y el padrón queda mezclado.",
        )

    def test_el_candado_de_un_padron_propio_es_el_del_relevamiento(self):
        territorial = User.objects.create_user("terri-bec15", password="x")
        relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=territorial,
            fecha_asignada=date(2026, 2, 1),
            zona="Z",
        )
        with candados_tomados(Relevamiento.objects) as candados:
            cargar_padron(relevamiento, None, [{"dni": "30111222", "sexo": "F"}])
        self.assertIn("padron.py:cargar_padron", candados)

    def test_la_segunda_carga_reemplaza_y_no_duplica(self):
        cargar_padron(self.convocatoria, None, [{"dni": "30111222", "sexo": "F"}])
        cargar_padron(self.convocatoria, None, [{"dni": "30111222", "sexo": "F"}])
        self.assertEqual(PadronHabilitado.objects.filter(convocatoria=self.convocatoria).count(), 1)


# ── BEC-16 ───────────────────────────────────────────────────────────────────


class ConstructorConcurrenciaTests(BecasPantallaTestCase):
    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = _segmento("Seg BEC-16")
        self.convocatoria = _convocatoria(self.segmento, "Conv BEC-16")
        self.pregunta = PreguntaGlobal.objects.create(texto="Pregunta", tipo=TipoCampo.STRING, orden=1)

    def test_reconciliar_dos_veces_no_duplica_claves(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        antes = set(diseno.items.values_list("clave", flat=True))
        reconciliar(diseno)
        reconciliar(diseno)
        self.assertEqual(set(diseno.items.values_list("clave", flat=True)), antes)

    def test_reconciliar_toma_el_candado_del_diseno(self):
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        with candados_tomados(DisenoFormulario.objects) as candados:
            reconciliar(diseno)
        self.assertIn(
            "diseno.py:bloquear",
            candados,
            "Reconciliar escribe: sin candado dos aperturas simultáneas dan IntegrityError.",
        )

    def test_un_post_de_mutacion_no_reconcilia(self):
        """Reconciliar en cada POST metía una segunda escritura del diseño dentro
        de cada guardado, compitiendo por las mismas claves."""
        admin = User.objects.create_user("admin-bec16", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)
        self.client.get(reverse("becas:convocatoria_formulario", args=[self.convocatoria.pk]))
        # Una pregunta nueva del catálogo: el GET la habría incorporado.
        PreguntaGlobal.objects.create(texto="Pregunta nueva", tipo=TipoCampo.STRING, orden=2)
        with patch("programas.services.diseno.reconciliar") as reconciliar_mock:
            resp = self.client.post(
                reverse("becas:formulario_grupo_crear", args=[self.convocatoria.pk]),
                {"etiqueta": "Grupo nuevo", "subtitulo": "", "canal": CanalFormulario.AMBOS},
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        reconciliar_mock.assert_not_called()

    def test_el_mutar_toma_el_candado(self):
        admin = User.objects.create_user("admin-bec16b", password="x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)
        with candados_tomados(DisenoFormulario.objects) as candados:
            resp = self.client.post(
                reverse("becas:formulario_grupo_crear", args=[self.convocatoria.pk]),
                {"etiqueta": "Grupo con candado", "subtitulo": "", "canal": CanalFormulario.AMBOS},
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("diseno.py:bloquear", candados)


# ── BEC-17 ───────────────────────────────────────────────────────────────────


class CambiarPausaTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("op-bec17", password="x")
        self.segmento = _segmento("Seg BEC-17")

    def test_pausar_dos_veces_un_solo_registro(self):
        cambiar_pausa(self.segmento, self.usuario, True, "Tormenta")
        cambiar_pausa(self.segmento, self.usuario, True, "Tormenta")
        self.assertEqual(RegistroPausa.objects.count(), 1)

    def test_reanudar_sin_estar_pausado_no_registra_nada(self):
        cambiar_pausa(self.segmento, self.usuario, False, "Nada que reanudar")
        self.assertEqual(RegistroPausa.objects.count(), 0)
        self.segmento.refresh_from_db()
        self.assertFalse(self.segmento.pausado)

    def test_el_ciclo_completo_sigue_dejando_los_dos_eventos(self):
        cambiar_pausa(self.segmento, self.usuario, True, "Tormenta")
        cambiar_pausa(self.segmento, self.usuario, False, "Pasó")
        self.assertEqual(
            list(RegistroPausa.objects.order_by("pk").values_list("accion", flat=True)),
            [RegistroPausa.Accion.PAUSAR, RegistroPausa.Accion.REANUDAR],
        )

    def test_el_motivo_sigue_siendo_obligatorio(self):
        with self.assertRaises(ValueError):
            cambiar_pausa(self.segmento, self.usuario, True, "   ")


# ── BEC-24 ───────────────────────────────────────────────────────────────────


class EdicionContactoTests(_BaseRevisionBec):
    """BEC-24: la edición de contacto/apoderado es una sola escritura."""

    def _post(self, **cambios):
        datos = {
            "celular": "3624999999",
            "email_contacto": "nuevo@b.com",
            "apoderado_nombre": "",
            "apoderado_apellido": "",
            "apoderado_dni": "",
            "apoderado_genero": "",
            "apoderado_fecha_nacimiento": "",
        }
        datos.update(cambios)
        return self.client.post(reverse("becas:formulario_detalle", args=[self.caso.pk]), datos)

    def test_la_edicion_feliz_sigue_guardando_y_trazando(self):
        self._post()
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.celular, "3624999999")
        self.assertTrue(TracaFormulario.objects.filter(formulario=self.caso, campo="Celular").exists())

    def test_falla_en_resolver_revierte_todo(self):
        with patch("programas.views.revision.resolver_ciudadano_offline", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self._post()
        self.caso.refresh_from_db()
        self.assertEqual(self.caso.celular, "3624100100", "Las columnas quedaron escritas sin traza.")
        self.assertFalse(TracaFormulario.objects.filter(formulario=self.caso).exists())


# ── BEC-18 (el borde del día, con el relevamiento que se vence) ──────────────


class VencimientoEnHoraLocalTests(TestCase):
    """La fecha de corte de una convocatoria ya usaba `localdate()`; este caso la
    deja atada para que el barrido de BEC-18 no la mueva sin querer."""

    def setUp(self):
        self.segmento = _segmento("Seg BEC-18")

    def test_a_las_23_de_chaco_la_convocatoria_que_vence_hoy_sigue_vigente(self):
        convocatoria = _convocatoria(self.segmento, "Conv BEC-18", fecha_fin=date(2026, 6, 30))
        with reloj_en(datetime(2026, 7, 1, 2, 0, tzinfo=tz_utc.utc)):  # 23:00 ART del 30/06
            self.assertFalse(convocatoria.esta_vencida)

    def test_al_dia_siguiente_si_esta_vencida(self):
        convocatoria = _convocatoria(self.segmento, "Conv BEC-18b", fecha_fin=date(2026, 6, 30))
        with reloj_en(datetime(2026, 7, 1, 15, 0, tzinfo=tz_utc.utc)):  # 12:00 ART del 01/07
            self.assertTrue(convocatoria.esta_vencida)


def _hace(dias):
    """Atajo legible para los tests que miden antigüedad."""
    return date(2026, 6, 30) - timedelta(days=dias)
