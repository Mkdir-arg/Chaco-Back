"""Formulario «Relevamiento» por tipo y su entrega al territorial por la API de campo.

Lo que se fija acá, y por qué:

1. **D1/D3: el formulario sale del tipo de la institución** y se fija al asignar
   (``InspeccionEdificio.diseno``); sin formulario, o dado de baja, se asigna igual con ``diseno=None``.
2. **D2: el formulario complementa el resultado fijo.** Un obligatorio sin responder, un valor de
   tipo inválido o una condición mal aplicada se rechazan con 400; un ARCHIVO obligatorio **no**
   bloquea el resultado (llega después por ``adjuntos/``).
3. **D4: siempre la versión VIGENTE.** La foto de la definición y la versión se toman al recibir; la
   ``version_capturada`` distinta se acepta y se marca; lo que ya no está en el diseño va a ``anteriores``.
4. **Aislamiento entre módulos:** solo ``becas.campo`` recibe 403 ``SIN_MODULO`` en ``/api/dispositivos/``
   y solo ``inspeccion.relevar`` en ``/api/becas/``; lo ajeno es 404 y lo reasignado, 409.
5. **Idempotencia** de ``resultado/`` y de ``adjuntos/`` por ``uuid_cliente``.
"""

import uuid
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from programas.management.commands.seed_becas import ROL_TERRITORIAL
from programas.models import (
    AdjuntoRespuestaRelevamiento,
    DisenoFormulario,
    Edificio,
    InspeccionEdificio,
    ItemDiseno,
    MomentoFormulario,
    RespuestasRelevamiento,
    TipoDispositivo,
)
from programas.services import constructor
from programas.services.formularios_tipo import (
    aviso_sin_formulario,
    crear_formulario,
    eliminar_formulario,
    formularios_de_los_tipos,
)
from programas.services.inspecciones import (
    cancelar_inspeccion,
    crear_inspeccion,
    reasignar_inspeccion,
)
from programas.services.respuestas_dispositivo import foto_vigente
from programas.tests.test_api_campo_inspecciones import (
    BaseApiInspecciones,
    _detalle,
    _lista,
    _resultado,
)
from programas.tests.test_dispositivos_inspecciones import TODAS_DE_DISPOSITIVOS

Criticidad = InspeccionEdificio.Criticidad
Estado = InspeccionEdificio.Estado

PDF = b"%PDF-1.4\n%prueba\n"
AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


def _adjuntos(pk):
    return reverse("dispositivos_api:inspeccion-adjuntos", args=[pk])


def _pdf(nombre="plano.pdf", contenido=PDF):
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


class BaseFormulario(BaseApiInspecciones):
    """Un tipo con su formulario «Relevamiento» y un relevamiento en curso que lo trae.

    Campos: estado del techo (selector, obligatorio), baños (entero, obligatorio), detalle del
    daño (texto, obligatorio **solo si el techo está «Malo»**), servicios (selector múltiple), última
    inspección (fecha), observación técnica (texto) y plano (archivo, obligatorio).
    """

    def setUp(self):
        super().setUp()
        # El relevamiento que arma la base se hizo antes de que el tipo tuviera formulario.
        self.sin_formulario = self.inspeccion
        cancelar_inspeccion(self._fresco(self.coordinador), self.sin_formulario, "Se rehace con el formulario")

        self.admin = self._usuario("admin_formulario", TODAS_DE_DISPOSITIVOS)
        self.diseno = crear_formulario(self.tipo, MomentoFormulario.RELEVAMIENTO, self.admin)
        self.grupo = self._grupo(self.diseno, "Estado del edificio")
        self.techo = self._campo("Estado del techo", "SELECTOR", obligatorio=True, opciones=["Bueno", "Malo"])
        self.banos = self._campo("Cantidad de baños", "INT", obligatorio=True)
        self.detalle_dano = self._campo("Detalle del daño", "STRING", obligatorio=True)
        self._mutar(
            lambda: constructor.poner_condicion(
                self.detalle_dano,
                {"modo": "todas", "reglas": [{"fuente": self.techo.clave, "op": "es", "valor": "Malo"}]},
            )
        )
        self.servicios = self._campo("Servicios", "SELECTOR_MULTIPLE", opciones=["Agua", "Gas", "Cloaca"])
        self.ultima = self._campo("Última inspección", "DATE")
        self.tecnica = self._campo("Observación técnica", "STRING")
        self.plano = self._campo("Plano", "ARCHIVO", obligatorio=True)

        self.inspeccion = self._crear()

    # ── helpers ──
    def _mutar(self, operacion):
        constructor.mutar(self.diseno, self.admin, operacion)
        self.diseno.refresh_from_db()

    def _grupo(self, diseno, titulo):
        constructor.mutar(
            diseno,
            self.admin,
            lambda: constructor.crear_grupo(diseno, {"etiqueta": titulo, "subtitulo": "", "canal": "ambos"}),
        )
        diseno.refresh_from_db()
        return diseno.items.get(tipo=ItemDiseno.Tipo.GRUPO, etiqueta=titulo)

    def _campo(self, texto, tipo="STRING", *, obligatorio=False, opciones=()):
        propio = {
            "texto": texto,
            "tipo": tipo,
            "opciones": list(opciones),
            "presentacion": "LISTA",
            "obligatorio": obligatorio,
        }
        self._mutar(lambda: constructor.crear_propio(self.diseno, self.grupo, {"propio": propio, "canal": "ambos"}))
        return self.diseno.items.get(tipo=ItemDiseno.Tipo.CAMPO, propio__texto=texto)

    def _completas(self, **extra):
        """Un envío válido: el techo bueno (no pide el detalle del daño) y los baños."""
        respuestas = {self.techo.clave: "Bueno", self.banos.clave: 3}
        respuestas.update(extra)
        return respuestas

    def _resultado_con(self, respuestas, usuario=None, pk=None, **extra):
        return self._enviar_resultado(usuario or self.agente, pk or self.inspeccion.pk, respuestas=respuestas, **extra)

    def _enviar_adjunto(self, usuario, pk, clave=None, uuid_cliente=None, archivo=None):
        cuerpo = {
            "clave": clave or self.plano.clave,
            "archivo": archivo or _pdf(),
            "uuid_cliente": str(uuid_cliente or uuid.uuid4()),
        }
        return self._como(usuario).post(_adjuntos(pk), cuerpo, format="multipart")


# ── A1 · el momento ──────────────────────────────────────────────────────────


class MomentoTests(BaseFormulario):
    def test_el_momento_relevamiento_se_ofrece_y_se_crea_desde_el_alta_de_formulario(self):
        otro = TipoDispositivo.objects.create(codigo="HOGAR", nombre="Hogar")
        self.client.force_login(self.admin)

        respuesta = self.client.post(
            reverse("dispositivos:formulario_crear", args=[otro.pk]), {"momento": "relevamiento"}
        )

        self.assertEqual(respuesta.status_code, 302)
        creado = DisenoFormulario.objects.get(tipo_dispositivo=otro)
        self.assertEqual(creado.momento, MomentoFormulario.RELEVAMIENTO)
        self.assertEqual(creado.version, 1)

    def test_el_momento_se_lee_en_la_pantalla_del_tipo(self):
        self.client.force_login(self.admin)
        sin_formulario = TipoDispositivo.objects.create(codigo="HOGAR", nombre="Hogar")

        respuesta = self.client.get(reverse("dispositivos:tipo_detalle", args=[sin_formulario.pk]))

        self.assertContains(respuesta, "Relevamiento")


# ── D1 / D3 · el formulario que se fija al asignar ───────────────────────────


class AsignarFormularioTests(BaseFormulario):
    def _edificio_con_dos_tipos(self):
        otro_tipo = TipoDispositivo.objects.create(codigo="GERIATRICO", nombre="Geriátrico tipo")
        residencia = self._dispositivo("RES-9", "Residencia")
        residencia.tipo = otro_tipo
        residencia.save(update_fields=["tipo"])
        otro = self._dispositivo("ALB-9", "Albergue 9")
        edificio = Edificio.objects.create(codigo="ED-MIXTO", nombre="Edificio mixto")
        edificio.dispositivos.add(residencia, otro)
        coordinador = self._usuario("coord_mixto", ("inspeccion.asignar", "dispositivo.ver"), [residencia, otro])
        return edificio, otro_tipo, coordinador

    def test_un_edificio_de_un_solo_tipo_toma_el_formulario_de_ese_tipo(self):
        self.assertEqual(self.inspeccion.diseno_id, self.diseno.pk)

    def test_el_diseno_queda_fijado_aunque_el_formulario_cambie_despues(self):
        self._campo("Extra", "STRING")
        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.diseno_id, self.diseno.pk)

    def test_un_tipo_sin_formulario_asigna_igual_con_diseno_none(self):
        edificio, otro_tipo, coordinador = self._edificio_con_dos_tipos()

        inspeccion = crear_inspeccion(
            coordinador,
            edificio=edificio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
            tipo=otro_tipo,
        )

        self.assertIsNone(inspeccion.diseno_id)

    def test_con_varios_tipos_hay_que_elegir(self):
        edificio, otro_tipo, coordinador = self._edificio_con_dos_tipos()

        with self.assertRaises(Exception) as contexto:
            crear_inspeccion(
                coordinador, edificio=edificio, asignado_a=self._fresco(self.agente), fecha_vencimiento=self.vence
            )
        self.assertIn("tipo", contexto.exception.message_dict)

        elegido = crear_inspeccion(
            coordinador,
            edificio=edificio,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
            tipo=self.tipo,
        )
        self.assertEqual(elegido.diseno_id, self.diseno.pk)

    def test_un_tipo_ajeno_al_edificio_se_rechaza(self):
        ajeno = TipoDispositivo.objects.create(codigo="OTRO", nombre="Otro tipo")
        crear_formulario(ajeno, MomentoFormulario.RELEVAMIENTO, self.admin)
        cancelar_inspeccion(self._fresco(self.coordinador), self.inspeccion, "Prueba")

        with self.assertRaises(Exception) as contexto:
            crear_inspeccion(
                self._fresco(self.coordinador),
                edificio=self.predio,
                asignado_a=self._fresco(self.agente),
                fecha_vencimiento=self.vence,
                tipo=ajeno,
            )
        self.assertIn("tipo", contexto.exception.message_dict)

    def test_un_formulario_dado_de_baja_se_asigna_con_diseno_none(self):
        # Respondido no se borra: se da de baja.
        self._resultado_con(self._completas())
        self.assertEqual(eliminar_formulario(self.diseno), "baja")
        self.diseno.refresh_from_db()

        nueva = self._crear()

        self.assertIsNone(nueva.diseno_id)
        self.assertIsNone(self._como(self.agente).get(_detalle(nueva.pk)).data["formulario"])

    def test_reasignar_conserva_el_formulario(self):
        reasignada = reasignar_inspeccion(
            self._fresco(self.coordinador), self.inspeccion, self._fresco(self.otro_agente)
        )

        self.assertEqual(reasignada.diseno_id, self.diseno.pk)

    def test_el_aviso_sin_formulario_nombra_el_tipo(self):
        sin = TipoDispositivo.objects.create(codigo="SIN", nombre="Sin formulario")

        self.assertEqual(aviso_sin_formulario(self.tipo), "")
        self.assertIn("Sin formulario", aviso_sin_formulario(sin))
        self.assertIn("«Relevamiento»", aviso_sin_formulario(sin))

    def test_formularios_de_los_tipos_marca_los_tipos_sin_formulario(self):
        edificio, otro_tipo, _ = self._edificio_con_dos_tipos()

        por_tipo = {tipo.pk: formulario for tipo, formulario in formularios_de_los_tipos(edificio)}

        self.assertEqual(por_tipo[self.tipo.pk].pk, self.diseno.pk)
        self.assertIsNone(por_tipo[otro_tipo.pk])


class ModalDeAsignarTests(BaseFormulario):
    def setUp(self):
        super().setUp()
        cancelar_inspeccion(self._fresco(self.coordinador), self.inspeccion, "Se libera el edificio")
        self.client.force_login(self.coordinador)
        self.url_edificio = reverse("dispositivos:relevamiento_asignar", args=[self.predio.pk])
        self.url_parador = reverse("dispositivos:relevamiento_asignar_dispositivo", args=[self.parador.pk])

    def _datos(self, **extra):
        datos = {
            "asignado_a": self.agente.pk,
            "fecha_vencimiento": self.vence.isoformat(),
            "indicaciones": "",
        }
        datos.update(extra)
        return datos

    def test_desde_p4_el_formulario_es_el_del_tipo_de_la_institucion(self):
        respuesta = self.client.post(self.url_parador, self._datos(edificio=self.predio.pk), **AJAX)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(InspeccionEdificio.objects.get(estado=Estado.ASIGNADA).diseno_id, self.diseno.pk)

    def test_desde_p21_con_un_solo_tipo_no_pide_elegir_y_toma_su_formulario(self):
        respuesta = self.client.post(self.url_edificio, self._datos(), **AJAX)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(InspeccionEdificio.objects.get(estado=Estado.ASIGNADA).diseno_id, self.diseno.pk)

    def test_con_varios_tipos_el_modal_pide_el_tipo_y_lo_valida(self):
        otro_tipo = TipoDispositivo.objects.create(codigo="GER", nombre="Geriátrico tipo")
        residencia = self._dispositivo("RES-9", "Residencia")
        residencia.tipo = otro_tipo
        residencia.save(update_fields=["tipo"])
        self.predio.dispositivos.add(residencia)
        url = reverse("dispositivos:relevamiento_asignar", args=[self.predio.pk])

        sin_tipo = self.client.post(url, self._datos(), **AJAX)
        ajeno = self.client.post(url, self._datos(tipo=999999), **AJAX)
        bueno = self.client.post(url, self._datos(tipo=self.tipo.pk), **AJAX)

        self.assertEqual(sin_tipo.status_code, 400)
        self.assertIn("tipo", sin_tipo.json()["errors"])
        self.assertEqual(ajeno.status_code, 400)
        self.assertEqual(bueno.status_code, 200, bueno.content)
        self.assertEqual(InspeccionEdificio.objects.get(estado=Estado.ASIGNADA).diseno_id, self.diseno.pk)

    def test_el_modal_avisa_cuando_el_tipo_no_tiene_formulario(self):
        eliminar_formulario(self.diseno)  # sin respuestas: se borra
        detalle = self.client.get(reverse("dispositivos:detalle", args=[self.parador.pk]), {"tab": "infraestructura"})

        self.assertContains(detalle, "no tiene un formulario «Relevamiento»")


# ── A4 · lo que la app lee ───────────────────────────────────────────────────


class LecturaTests(BaseFormulario):
    def test_el_listado_trae_la_version_del_formulario(self):
        listado = self._como(self.agente).get(_lista()).data

        self.assertEqual([i["formulario_version"] for i in listado], [self.diseno.version])

    def test_el_detalle_trae_la_definicion_vigente_con_el_mismo_motor_que_los_formularios_por_tipo(self):
        detalle = self._como(self.agente).get(_detalle(self.inspeccion.pk)).data

        self.assertEqual(detalle["formulario"]["version"], self.diseno.version)
        self.assertEqual(detalle["formulario"]["definicion"], foto_vigente(self.diseno))
        self.assertEqual(detalle["formulario_version"], self.diseno.version)

    def test_sin_formulario_el_detalle_trae_null(self):
        cancelar_inspeccion(self._fresco(self.coordinador), self.inspeccion, "Prueba")
        self.diseno.dado_de_baja_en = self.diseno.modificado
        self.diseno.save(update_fields=["dado_de_baja_en"])
        nueva = self._crear()

        detalle = self._como(self.agente).get(_detalle(nueva.pk)).data

        self.assertIsNone(detalle["formulario"])
        self.assertIsNone(detalle["formulario_version"])

    def test_el_detalle_sirve_la_version_vigente_aunque_el_diseno_cambie_despues_de_asignar(self):
        version_antes = self.diseno.version
        self._campo("Campo nuevo", "STRING")

        detalle = self._como(self.agente).get(_detalle(self.inspeccion.pk)).data

        self.assertGreater(detalle["formulario"]["version"], version_antes)
        self.assertEqual(detalle["formulario"]["definicion"], foto_vigente(self.diseno))


# ── A4 · resultado con respuestas ────────────────────────────────────────────


class ResultadoConRespuestasTests(BaseFormulario):
    def test_las_respuestas_validas_se_guardan_con_la_foto_vigente(self):
        respuesta = self._resultado_con(
            self._completas(
                **{
                    self.servicios.clave: ["Agua", "Gas"],
                    self.ultima.clave: "2026-09-01",
                    self.tecnica.clave: "Sin novedades",
                }
            ),
            version_capturada=self.diseno.version,
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        guardadas = RespuestasRelevamiento.objects.get(inspeccion=self.inspeccion)
        self.assertEqual(guardadas.version, self.diseno.version)
        self.assertEqual(guardadas.definicion, foto_vigente(self.diseno))
        self.assertEqual(guardadas.respuestas[self.banos.clave], 3)
        self.assertEqual(guardadas.respuestas[self.servicios.clave], ["Agua", "Gas"])
        self.assertEqual(guardadas.observaciones_carga, "")

    def test_un_obligatorio_sin_responder_es_400_y_no_cierra_el_relevamiento(self):
        respuesta = self._resultado_con({self.techo.clave: "Bueno"})

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn(self.banos.clave, respuesta.data["claves"])
        self.assertTrue(respuesta.data["detail"])
        self.inspeccion.refresh_from_db()
        self.assertEqual(self.inspeccion.estado, Estado.ASIGNADA)
        self.assertFalse(RespuestasRelevamiento.objects.exists())

    def test_sin_el_cuerpo_de_respuestas_un_formulario_con_obligatorios_es_400(self):
        respuesta = self._enviar_resultado(self.agente, self.inspeccion.pk)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(set(respuesta.data["claves"]), {self.techo.clave, self.banos.clave})

    def test_un_valor_de_tipo_invalido_es_400_por_cada_tipo(self):
        malos = {
            self.banos.clave: "muchos",
            self.techo.clave: "Regular",
            self.servicios.clave: "Agua",
            self.ultima.clave: "01/09/2026",
            self.tecnica.clave: "x" * 501,
        }
        respuesta = self._resultado_con(malos)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(set(respuesta.data["claves"]), set(malos))

    def test_un_entero_numerico_en_string_se_acepta(self):
        respuesta = self._resultado_con(self._completas(**{self.banos.clave: "4"}))

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_la_condicion_oculta_no_se_exige_y_visible_si(self):
        malo = self._resultado_con({self.techo.clave: "Malo", self.banos.clave: 1})
        self.assertEqual(malo.status_code, 400)
        self.assertEqual(set(malo.data["claves"]), {self.detalle_dano.clave})

        bueno = self._resultado_con({self.techo.clave: "Bueno", self.banos.clave: 1, self.detalle_dano.clave: "Fisura"})
        self.assertEqual(bueno.status_code, 200, bueno.data)
        # Lo oculto por su condición se descarta.
        self.assertNotIn(self.detalle_dano.clave, RespuestasRelevamiento.objects.get().respuestas)

    def test_el_archivo_obligatorio_no_bloquea_el_resultado_y_su_valor_no_se_valida(self):
        respuesta = self._resultado_con(self._completas(**{self.plano.clave: "plano.pdf"}))

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        # Solo cuenta como «adjuntado» para las condiciones: no se valida su forma.
        self.assertEqual(RespuestasRelevamiento.objects.get().respuestas[self.plano.clave], "plano.pdf")


class SinFormularioTests(BaseApiInspecciones):
    """Lo fijo no cambia cuando el tipo no tiene formulario (D3)."""

    def test_el_resultado_sin_formulario_se_cierra_y_no_crea_respuestas(self):
        respuesta = self._enviar_resultado(
            self.agente, self.inspeccion.pk, respuestas={"cualquiera": "valor"}, version_capturada=3
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertFalse(RespuestasRelevamiento.objects.exists())
        self.assertIsNone(self.inspeccion.diseno_id)

    def test_un_adjunto_sin_formulario_es_400(self):
        respuesta = self._como(self.agente).post(
            _adjuntos(self.inspeccion.pk),
            {"clave": "x", "archivo": _pdf(), "uuid_cliente": str(uuid.uuid4())},
            format="multipart",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(AdjuntoRespuestaRelevamiento.objects.exists())


# ── D4 · la versión vigente ──────────────────────────────────────────────────


class VersionTests(BaseFormulario):
    def test_si_el_diseno_cambio_se_guarda_con_la_vigente_y_se_marca_la_capturada(self):
        capturada = self.diseno.version
        self._campo("Campo agregado después", "STRING")
        vigente = self.diseno.version
        self.assertGreater(vigente, capturada)

        respuesta = self._resultado_con(self._completas(), version_capturada=capturada)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        guardadas = RespuestasRelevamiento.objects.get()
        self.assertEqual(guardadas.version, vigente)
        self.assertEqual(guardadas.version_capturada, capturada)
        self.assertIn(f"versión {capturada}", guardadas.observaciones_carga)
        self.assertIn(f"versión {vigente}", guardadas.observaciones_carga)

    def test_sin_version_capturada_no_hay_observacion(self):
        self._campo("Campo agregado después", "STRING")

        self._resultado_con(self._completas())

        self.assertEqual(RespuestasRelevamiento.objects.get().observaciones_carga, "")

    def test_una_clave_que_ya_no_esta_en_el_diseno_va_a_anteriores(self):
        respuesta = self._resultado_con(
            self._completas(clave_vieja="lo que pidió una versión anterior"), version_capturada=1
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        guardadas = RespuestasRelevamiento.objects.get()
        self.assertIn("clave_vieja", guardadas.anteriores)
        self.assertIn("clave_vieja", guardadas.observaciones_carga)


# ── idempotencia y conflictos del resultado ──────────────────────────────────


class IdempotenciaTests(BaseFormulario):
    def test_el_mismo_uuid_devuelve_200_y_deja_una_sola_fila_de_respuestas(self):
        identificador = uuid.uuid4()

        primero = self._resultado_con(self._completas(), uuid_cliente=identificador)
        segundo = self._resultado_con(self._completas(), uuid_cliente=identificador)

        self.assertEqual((primero.status_code, segundo.status_code), (200, 200))
        self.assertEqual(RespuestasRelevamiento.objects.count(), 1)

    def test_otro_uuid_sobre_un_realizado_es_409_ya_realizada(self):
        self._resultado_con(self._completas())

        otro = self._resultado_con(self._completas())

        self.assertEqual(otro.status_code, 409)
        self.assertEqual(otro.data["code"], "YA_REALIZADA")

    def test_un_cancelado_es_409_cancelada(self):
        cancelar_inspeccion(self._fresco(self.coordinador), self.inspeccion, "Ya no hace falta")

        respuesta = self._resultado_con(self._completas())

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["code"], "CANCELADA")

    def test_un_reasignado_es_409_reasignada_para_el_anterior(self):
        reasignar_inspeccion(self._fresco(self.coordinador), self.inspeccion, self._fresco(self.otro_agente))

        respuesta = self._resultado_con(self._completas())

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["code"], "REASIGNADA")
        self.assertFalse(RespuestasRelevamiento.objects.exists())


# ── adjuntos ─────────────────────────────────────────────────────────────────


class AdjuntosTests(BaseFormulario):
    def test_el_adjunto_se_guarda_y_responde_201(self):
        respuesta = self._enviar_adjunto(self.agente, self.inspeccion.pk)

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(set(respuesta.data), {"id", "clave", "uuid_cliente", "creado"})
        adjunto = AdjuntoRespuestaRelevamiento.objects.get()
        self.assertEqual(adjunto.clave, self.plano.clave)
        self.assertTrue(adjunto.archivo.name.startswith("dispositivos/formularios/"))

    def test_el_reenvio_con_el_mismo_uuid_es_200_y_no_duplica(self):
        identificador = uuid.uuid4()

        primero = self._enviar_adjunto(self.agente, self.inspeccion.pk, uuid_cliente=identificador)
        segundo = self._enviar_adjunto(
            self.agente, self.inspeccion.pk, uuid_cliente=identificador, archivo=_pdf("otro.pdf")
        )

        self.assertEqual((primero.status_code, segundo.status_code), (201, 200))
        self.assertEqual(primero.data["id"], segundo.data["id"])
        self.assertEqual(AdjuntoRespuestaRelevamiento.objects.count(), 1)

    def test_el_uuid_de_otro_adjunto_es_409_uuid_en_uso(self):
        otra = crear_inspeccion(
            self._usuario("coordinador_cis3", ("inspeccion.asignar",), [self.cis]),
            edificio=self.edificio_cis,
            asignado_a=self._fresco(self.agente),
            fecha_vencimiento=self.vence,
        )
        identificador = uuid.uuid4()
        self._enviar_adjunto(self.agente, self.inspeccion.pk, uuid_cliente=identificador)

        respuesta = self._enviar_adjunto(self.agente, otra.pk, uuid_cliente=identificador)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["code"], "UUID_EN_USO")
        self.assertEqual(AdjuntoRespuestaRelevamiento.objects.count(), 1)

    def test_una_clave_que_no_es_un_campo_archivo_es_400_y_no_guarda(self):
        for clave in (self.techo.clave, "no_existe"):
            with self.subTest(clave=clave):
                respuesta = self._enviar_adjunto(self.agente, self.inspeccion.pk, clave=clave)
                self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(AdjuntoRespuestaRelevamiento.objects.exists())

    def test_se_acepta_despues_de_realizado_el_resultado(self):
        self._resultado_con(self._completas())

        respuesta = self._enviar_adjunto(self.agente, self.inspeccion.pk)

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_extension_y_tamano_se_validan(self):
        exe = SimpleUploadedFile("plano.exe", b"MZ", content_type="application/octet-stream")
        disfrazado = SimpleUploadedFile("plano.pdf", b"<html></html>", content_type="application/pdf")
        grande = SimpleUploadedFile("plano.pdf", PDF + b"0" * (5 * 1024 * 1024), content_type="application/pdf")

        for archivo in (exe, disfrazado, grande):
            with self.subTest(archivo=archivo.name):
                respuesta = self._enviar_adjunto(self.agente, self.inspeccion.pk, archivo=archivo)
                self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(AdjuntoRespuestaRelevamiento.objects.exists())

    def test_cancelado_y_reasignado_son_409(self):
        reasignar_inspeccion(self._fresco(self.coordinador), self.inspeccion, self._fresco(self.otro_agente))
        reasignado = self._enviar_adjunto(self.agente, self.inspeccion.pk)
        self.assertEqual((reasignado.status_code, reasignado.data["code"]), (409, "REASIGNADA"))

        cancelar_inspeccion(self._fresco(self.coordinador), self.inspeccion, "Ya no hace falta")
        cancelado = self._enviar_adjunto(self.otro_agente, self.inspeccion.pk)
        self.assertEqual((cancelado.status_code, cancelado.data["code"]), (409, "CANCELADA"))

    def test_lo_ajeno_es_404(self):
        ajeno = self._enviar_adjunto(self.otro_agente, self.inspeccion.pk)
        intruso = self._enviar_adjunto(self.intruso, self.inspeccion.pk)

        self.assertEqual((ajeno.status_code, intruso.status_code), (404, 404))
        self.assertFalse(AdjuntoRespuestaRelevamiento.objects.exists())


# ── aislamiento entre módulos ────────────────────────────────────────────────


class AislamientoTests(BaseFormulario):
    def test_el_territorial_de_becas_recibe_403_sin_modulo_en_dispositivos(self):
        call_command("seed_becas", stdout=StringIO())
        territorial = User.objects.create_user("terri2", password="x")
        territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))

        respuestas = (
            self._como(territorial).get(_lista()),
            self._como(territorial).get(_detalle(self.inspeccion.pk)),
            self._como(territorial).post(_resultado(self.inspeccion.pk), {}, format="json"),
            self._como(territorial).post(_adjuntos(self.inspeccion.pk), {}, format="multipart"),
        )

        for respuesta in respuestas:
            self.assertEqual(respuesta.status_code, 403)
            self.assertEqual(respuesta.data["code"], "SIN_MODULO")
            self.assertTrue(respuesta.data["detail"])

    def test_el_agente_de_dispositivos_recibe_403_sin_modulo_en_becas(self):
        call_command("seed_becas", stdout=StringIO())

        respuesta = self._como(self.agente).get("/api/becas/relevamientos/")

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["code"], "SIN_MODULO")
        self.assertTrue(respuesta.json()["detail"])

    def test_el_adjunto_de_otro_agente_no_se_ve_y_el_404_es_igual_al_de_un_id_inexistente(self):
        ajeno = self._enviar_adjunto(self.otro_agente, self.inspeccion.pk)
        inexistente = self._enviar_adjunto(self.otro_agente, 999999)

        self.assertEqual(ajeno.json(), inexistente.json())


# ── /media/ de los adjuntos ──────────────────────────────────────────────────


class MediaTests(BaseFormulario):
    def test_el_archivo_lo_baja_quien_ve_el_relevamiento_y_lo_ajeno_es_404(self):
        """Mutación: sin el alcance de `inspecciones_visibles` en `_archivo_de_formulario_dispositivo`,
        el operador del geriátrico —que no ve el predio de este relevamiento— lo baja."""
        self._enviar_adjunto(self.agente, self.inspeccion.pk)
        url = AdjuntoRespuestaRelevamiento.objects.get().archivo.url

        self.client.force_login(self.coordinador)
        self.assertEqual(self.client.get(url).status_code, 200)
        sin_alcance = self._usuario("sin_alcance_media", ("inspeccion.asignar", "dispositivo.ver"), [self.cis])
        self.client.force_login(sin_alcance)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url.replace(".pdf", "x.pdf")).status_code, 404)


# ── A5 · el informe del backoffice ───────────────────────────────────────────


class InformeTests(BaseFormulario):
    def _informe(self):
        self.client.force_login(self.coordinador)
        return self.client.get(reverse("dispositivos:relevamiento_informe", args=[self.inspeccion.pk]))

    def test_el_informe_muestra_lo_respondido_y_el_enlace_al_archivo(self):
        self._resultado_con(self._completas(**{self.tecnica.clave: "Sin novedades"}))
        self._enviar_adjunto(self.agente, self.inspeccion.pk)

        respuesta = self._informe()

        self.assertContains(respuesta, "Formulario del relevamiento")
        self.assertContains(respuesta, "Estado del techo")
        self.assertContains(respuesta, "Sin novedades")
        self.assertContains(respuesta, "Ver archivo")
        self.assertNotContains(respuesta, "Falta un archivo obligatorio")

    def test_un_archivo_obligatorio_que_no_llego_se_marca(self):
        self._resultado_con(self._completas())

        respuesta = self._informe()

        self.assertContains(respuesta, "Falta un archivo obligatorio")
        self.assertContains(respuesta, "Falta el archivo")

    def test_la_observacion_de_version_se_ve_en_el_informe(self):
        capturada = self.diseno.version
        self._campo("Campo agregado después", "STRING")
        self._resultado_con(self._completas(), version_capturada=capturada)

        respuesta = self._informe()

        self.assertContains(respuesta, f"versión {capturada}")


class InformeSinFormularioTests(BaseApiInspecciones):
    def test_un_relevamiento_sin_formulario_no_trae_la_seccion(self):
        self._enviar_resultado(self.agente, self.inspeccion.pk)
        self.client.force_login(self.coordinador)

        respuesta = self.client.get(reverse("dispositivos:relevamiento_informe", args=[self.inspeccion.pk]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "Formulario del relevamiento")


# ── el borrado del formulario cuenta las respuestas ──────────────────────────


class BajaDelFormularioTests(BaseFormulario):
    def test_un_formulario_asignado_se_da_de_baja_en_vez_de_borrarse(self):
        # Asignado a un relevamiento en curso (sin respuestas todavía): el diseño está PROTEGIDO.
        self.assertEqual(eliminar_formulario(self.diseno), "baja")
        self.assertTrue(DisenoFormulario.objects.filter(pk=self.diseno.pk).exists())

    def test_un_formulario_respondido_se_da_de_baja(self):
        self._resultado_con(self._completas())

        self.assertEqual(eliminar_formulario(self.diseno), "baja")
        self.assertEqual(RespuestasRelevamiento.objects.count(), 1)

    def test_un_formulario_sin_uso_se_borra(self):
        libre = TipoDispositivo.objects.create(codigo="LIBRE", nombre="Libre")
        formulario = crear_formulario(libre, MomentoFormulario.RELEVAMIENTO, self.admin)

        self.assertEqual(eliminar_formulario(formulario), "borrado")


# ── condiciones sobre un campo ARCHIVO (adjuntado / no_adjuntado) ────────────

MARCADOR = {"archivo_adjunto": True, "nombre": "plano.pdf"}


class CondicionesDeArchivoTests(BaseFormulario):
    """El plano es ARCHIVO; «Detalle del plano» se ve si fue adjuntado y «Motivo sin plano» es
    obligatorio si no. La presencia del archivo cuenta aunque el archivo llegue después."""

    def setUp(self):
        super().setUp()
        self.detalle_plano = self._campo("Detalle del plano", "STRING")
        self._mutar(
            lambda: constructor.poner_condicion(
                self.detalle_plano,
                {"modo": "todas", "reglas": [{"fuente": self.plano.clave, "op": "adjuntado"}]},
            )
        )
        self.motivo = self._campo("Motivo sin plano", "STRING", obligatorio=True)
        self._mutar(
            lambda: constructor.poner_condicion(
                self.motivo,
                {"modo": "todas", "reglas": [{"fuente": self.plano.clave, "op": "no_adjuntado"}]},
            )
        )

    def test_con_el_marcador_el_detalle_se_ve_y_el_motivo_no_se_exige(self):
        respuesta = self._resultado_con(
            self._completas(**{self.plano.clave: MARCADOR, self.detalle_plano.clave: "Escala 1:50"})
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        guardadas = RespuestasRelevamiento.objects.get().respuestas
        self.assertEqual(guardadas[self.detalle_plano.clave], "Escala 1:50")
        self.assertEqual(guardadas[self.plano.clave], MARCADOR)

    def test_cualquier_valor_no_vacio_cuenta_como_adjuntado(self):
        respuesta = self._resultado_con(self._completas(**{self.plano.clave: "plano.pdf"}))

        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_sin_el_marcador_se_exige_el_motivo_y_el_detalle_se_descarta(self):
        sin_motivo = self._resultado_con(self._completas())
        self.assertEqual(sin_motivo.status_code, 400)
        self.assertEqual(set(sin_motivo.data["claves"]), {self.motivo.clave})

        con_motivo = self._resultado_con(
            self._completas(**{self.motivo.clave: "No hay plano", self.detalle_plano.clave: "Oculto"})
        )
        self.assertEqual(con_motivo.status_code, 200, con_motivo.data)
        guardadas = RespuestasRelevamiento.objects.get().respuestas
        self.assertEqual(guardadas[self.motivo.clave], "No hay plano")
        self.assertNotIn(self.detalle_plano.clave, guardadas)

    def test_el_informe_evalua_las_condiciones_con_los_adjuntos_recibidos(self):
        self._resultado_con(self._completas(**{self.motivo.clave: "Todavía no hay plano"}))
        self.client.force_login(self.coordinador)
        url = reverse("dispositivos:relevamiento_informe", args=[self.inspeccion.pk])

        antes = self.client.get(url)
        self.assertContains(antes, "Motivo sin plano")
        self.assertNotContains(antes, "Detalle del plano")

        self._enviar_adjunto(self.agente, self.inspeccion.pk)
        despues = self.client.get(url)
        self.assertContains(despues, "Detalle del plano")
        self.assertNotContains(despues, "Motivo sin plano")


class TrazaDeAdjuntoTests(BaseFormulario):
    def test_el_adjunto_deja_una_traza_y_el_reenvio_no_duplica(self):
        from programas.models import TrazaInspeccion

        identificador = uuid.uuid4()
        self._enviar_adjunto(self.agente, self.inspeccion.pk, uuid_cliente=identificador)
        self._enviar_adjunto(self.agente, self.inspeccion.pk, uuid_cliente=identificador)

        trazas = TrazaInspeccion.objects.filter(inspeccion=self.inspeccion, accion=TrazaInspeccion.Accion.ADJUNTO)
        self.assertEqual(trazas.count(), 1)
        self.assertIn(self.plano.clave, trazas.get().detalle)


class BajaPosteriorALaAsignacionTests(BaseFormulario):
    def test_si_el_formulario_se_da_de_baja_despues_de_asignar_se_trata_como_sin_formulario(self):
        eliminar_formulario(self.diseno)  # asignado: se da de baja, no se borra
        self.diseno.refresh_from_db()
        self.assertIsNotNone(self.diseno.dado_de_baja_en)

        detalle = self._como(self.agente).get(_detalle(self.inspeccion.pk)).data
        self.assertIsNone(detalle["formulario"])
        self.assertIsNone(detalle["formulario_version"])

        respuesta = self._resultado_con({"cualquiera": "valor"})
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertFalse(RespuestasRelevamiento.objects.exists())
        self.assertEqual(self._enviar_adjunto(self.agente, self.inspeccion.pk).status_code, 400)
