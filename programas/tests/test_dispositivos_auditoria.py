"""Auditoría básica del dispositivo (MVP v2, etapa 3 · #699).

Lo que se fija acá, y por qué:

1. **No se pierden eventos**: cada acción de los servicios que mutan —ingreso, egreso,
   cambio de plaza, reservas, plazas fuera de servicio, turnos, correcciones de la
   bitácora, relevamientos edilicios y el ciclo del legajo— produce **exactamente una**
   línea en el historial. Ni cero (se perdió) ni dos (el ingreso que escribe su traza y su
   movimiento no se cuenta dos veces).
2. **Legible en idioma de operador**: ningún código de acción ni nombre de campo crudo, y
   nada de las observaciones libres del egreso, que pueden traer datos sensibles.
3. **Ordenado y paginado sin huecos**: de lo más nuevo a lo más viejo, y recorrer todas
   las páginas devuelve todos los eventos una sola vez.
4. **Alcance**: lo de otra institución no aparece; lo del predio compartido, sí.
5. **Consultas fijas**: ocho, sin importar el largo del historial.
"""

import json
import re
from collections import Counter
from datetime import time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import (
    EntradaBitacora,
    Estadia,
    MotivoEgreso,
    MovimientoEstadia,
    Plaza,
    TrazaDispositivo,
    TrazaInspeccion,
)
from programas.selectors.auditoria_dispositivo import TITULOS_TRAZA, auditoria_del_dispositivo
from programas.services.bitacora import corregir_entrada, crear_turno, editar_turno, registrar_entrada
from programas.services.detalle_dispositivo import POR_PAGINA_HISTORIAL, eventos_de_historial
from programas.services.dispositivos import inactivar_dispositivo, registrar_edicion_dispositivo
from programas.services.estadias import (
    cambiar_plaza,
    egresar_persona,
    ingresar_persona,
    liberar_reserva,
    reservar_plaza,
    sacar_plaza_de_servicio,
    volver_plaza_a_servicio,
)
from programas.services.inspecciones import (
    agregar_foto,
    cancelar_inspeccion,
    reasignar_inspeccion,
    registrar_resultado,
)
from programas.tests.test_dispositivos_alertas import PRESUPUESTOS, BaseAlertas, Criticidad

CLAVE_PRESUPUESTO = "dispositivos_auditoria"
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


def _todo(dispositivo):
    feed = auditoria_del_dispositivo(dispositivo)
    return feed[0 : feed.count()]


def _titulos(dispositivo):
    return [evento["titulo"] for evento in _todo(dispositivo)]


class BaseAuditoria(BaseAlertas):
    def setUp(self):
        super().setUp()
        self.bitacorista = self._usuario(
            "bitacorista", ("dispositivo.ver", "dispositivo.bitacora", "dispositivo.editar"), [self.cis]
        )
        self.otro_agente = self._usuario("otro_agente", ("inspeccion.relevar",))

    def assertUnaLinea(self, accion, titulo, dispositivo=None):
        """Corre `accion` y exige que el historial sume exactamente una línea, con ese título."""

        dispositivo = dispositivo or self.cis
        antes = Counter(_titulos(dispositivo))
        resultado = accion()
        despues = Counter(_titulos(dispositivo))
        self.assertEqual(despues - antes, Counter({titulo: 1}), f"{titulo}: tiene que sumar una línea y solo una")
        self.assertEqual(antes - despues, Counter(), "una acción no puede borrar líneas del historial")
        return resultado


class NoSePierdenEventosTests(BaseAuditoria):
    def test_cada_accion_sobre_estadias_y_plazas_es_una_linea(self):
        estadia = self.assertUnaLinea(
            lambda: ingresar_persona(
                ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
            ),
            "Ingreso de Gómez, Ana",
        )
        self.assertUnaLinea(
            lambda: cambiar_plaza(estadia=estadia, plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Ruido"),
            "Cambio de plaza de Gómez, Ana",
        )
        reserva = self.assertUnaLinea(
            lambda: reservar_plaza(plaza=self.plaza, ciudadano=self.otra_persona, usuario=self.operador_cis),
            "Plaza reservada",
        )
        self.assertUnaLinea(
            lambda: liberar_reserva(reserva=reserva, usuario=self.operador_cis), "Reserva de plaza liberada"
        )
        self.assertUnaLinea(
            lambda: sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Cama rota"),
            "Plaza fuera de servicio",
        )
        self.assertUnaLinea(
            lambda: volver_plaza_a_servicio(plaza=self.plaza, usuario=self.operador_cis), "Plaza de nuevo en servicio"
        )
        self.assertUnaLinea(
            lambda: egresar_persona(estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta),
            "Egreso de Gómez, Ana",
        )

    def test_cada_accion_del_legajo_y_de_los_turnos_es_una_linea(self):
        turno = self.assertUnaLinea(
            lambda: crear_turno(
                dispositivo=self.cis,
                usuario=self.operador_cis,
                nombre="Mañana",
                hora_desde=time(6),
                hora_hasta=time(14),
            ),
            "Alta de un turno",
        )
        self.assertUnaLinea(
            lambda: editar_turno(turno=turno, usuario=self.operador_cis, hora_hasta=time(15)), "Cambio en un turno"
        )
        self.assertUnaLinea(
            lambda: registrar_edicion_dispositivo(
                self.cis, self.operador_cis, {"localidad": {"anterior": "Resistencia", "nuevo": "Barranqueras"}}
            ),
            "Edición de los datos del dispositivo",
        )
        self.assertUnaLinea(lambda: inactivar_dispositivo(self.cis, self.operador_cis), "Inactivación del dispositivo")

    def test_la_correccion_de_la_bitacora_es_una_linea_y_la_novedad_ninguna(self):
        self._turno()
        antes = len(_titulos(self.cis))
        entrada = registrar_entrada(
            dispositivo=self.cis, usuario=self.bitacorista, tipo=EntradaBitacora.Tipo.GENERAL, texto="Sin novedad"
        )
        # La novedad no es un evento de auditoría: la bitácora ya es su propio registro.
        self.assertEqual(len(_titulos(self.cis)), antes)

        self.assertUnaLinea(
            lambda: corregir_entrada(entrada=entrada, usuario=self.bitacorista, texto="Corte de luz", motivo="Faltaba"),
            "Corrección de una novedad de la bitácora",
        )

    def test_cada_accion_del_relevamiento_edilicio_es_una_linea(self):
        inspeccion = self.assertUnaLinea(lambda: self._relevamiento(), "Relevamiento edilicio asignado")
        self.assertUnaLinea(
            lambda: reasignar_inspeccion(self.coordinador, inspeccion, self.otro_agente),
            "Relevamiento edilicio reasignado",
        )
        foto = SimpleUploadedFile("fachada.jpg", JPEG, content_type="image/jpeg")
        self.assertUnaLinea(
            lambda: registrar_resultado(self.otro_agente, inspeccion, criticidad=Criticidad.MEDIA, fotos=[foto]),
            "Resultado del relevamiento edilicio",
        )
        otra = SimpleUploadedFile("patio.jpg", JPEG, content_type="image/jpeg")
        self.assertUnaLinea(
            lambda: agregar_foto(self.otro_agente, inspeccion, otra), "Foto sumada a un relevamiento edilicio"
        )
        cancelable = self._relevamiento()
        self.assertUnaLinea(
            lambda: cancelar_inspeccion(self.coordinador, cancelable, "Se reprograma"),
            "Relevamiento edilicio cancelado",
        )

    def test_el_ingreso_escribe_traza_y_movimiento_pero_cuenta_una_vez(self):
        """La traza `ESTADIA_*` sigue escribiéndose; el historial muestra el movimiento."""

        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="ESTADIA_INGRESO").exists())
        self.assertTrue(MovimientoEstadia.objects.filter(dispositivo=self.cis, tipo="INGRESO").exists())
        self.assertEqual(_titulos(self.cis).count("Ingreso de Gómez, Ana"), 1)

    def test_las_trazas_del_relevamiento_son_inmutables(self):
        traza = TrazaInspeccion.objects.get(inspeccion=self._relevamiento())
        with self.assertRaises(Exception):
            traza.save()
        with self.assertRaises(Exception):
            TrazaInspeccion.objects.all().delete()


class LegibleTests(BaseAuditoria):
    def test_quien_cuando_y_que_en_idioma_de_operador(self):
        motivo = MotivoEgreso.objects.create(codigo="alta-voluntaria", nombre="Alta voluntaria")
        estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )
        egresar_persona(
            estadia=estadia,
            usuario=self.operador_cis,
            motivo="Refiere violencia en el domicilio",
            motivo_egreso=motivo,
        )
        registrar_edicion_dispositivo(
            self.cis, self.operador_cis, {"responsable_nombre": {"anterior": "", "nuevo": "Marta"}}
        )
        sacar_plaza_de_servicio(plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Cama rota")

        _pagina, eventos = eventos_de_historial(self.cis)
        textos = " ".join(f"{e['cuando']} {e['titulo']} {e['detalle']}" for e in eventos)

        egreso = next(e for e in eventos if e["titulo"] == "Egreso de Gómez, Ana")
        self.assertEqual(egreso["detalle"], "Liberó la plaza P1 (Varones) · Motivo: Alta voluntaria")
        self.assertRegex(egreso["cuando"], r"^\d{2}/\d{2}/\d{4} \d{2}:\d{2} · operador_cis$")
        ingreso = next(e for e in eventos if e["titulo"] == "Ingreso de Gómez, Ana")
        self.assertEqual(ingreso["detalle"], "Plaza P1 (Varones)")
        edicion = next(e for e in eventos if e["titulo"] == "Edición de los datos del dispositivo")
        self.assertEqual(edicion["detalle"], "Responsable: — → Marta")
        self.assertIn("Plaza P2 · motivo: Cama rota", textos)

        # Ni códigos de acción ni nombres de campo crudos, ni las observaciones libres del egreso.
        self.assertIsNone(re.search(r"\b[A-Z]{3,}_[A-Z_]+\b", textos), textos)
        self.assertNotIn("responsable_nombre", textos)
        self.assertNotIn("violencia", textos)

    def test_sin_motivo_de_catalogo_las_observaciones_libres_no_llegan_al_historial(self):
        """Los egresos **viejos**, de antes del catálogo, guardan el texto libre en el
        movimiento: es lo que dejó la migración 0089, y no se muestra.

        Desde el carril C3 el servicio exige el motivo del catálogo, así que esta forma ya
        no se puede producir egresando: se arma la fila como quedó en la base.
        """

        estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )
        estadia.fecha_egreso = timezone.now()
        estadia.estado = Estadia.Estado.EGRESADA
        estadia.clave_alojamiento = None
        estadia.save(update_fields=["fecha_egreso", "estado", "clave_alojamiento", "modificado"])
        MovimientoEstadia.objects.create(
            estadia=estadia,
            dispositivo=self.cis,
            tipo=MovimientoEstadia.Tipo.EGRESO,
            momento=estadia.fecha_egreso,
            responsable=self.operador_cis,
            motivo="Refiere consumo problemático",
            plaza_origen=self.plaza,
        )

        egreso = next(e for e in _todo(self.cis) if e["titulo"] == "Egreso de Gómez, Ana")
        self.assertEqual(egreso["detalle"], "Liberó la plaza P1 (Varones)")

    def test_toda_accion_conocida_tiene_titulo_de_operador(self):
        acciones = {"CREADO", "EDITADO", "ENVIADO_VALIDACION", "VALIDADO", "OBSERVADO", "RECHAZADO", "INACTIVADO"}
        acciones |= {"CERRADO", "PLAZA_RESERVADA", "PLAZA_LIBERADA", "PLAZA_FUERA_SERVICIO", "PLAZA_EN_SERVICIO"}
        acciones |= {"TURNO_CREADO", "TURNO_EDITADO"}
        self.assertEqual(set(TITULOS_TRAZA), acciones)

    def test_un_valor_cero_no_se_dibuja_como_un_campo_vacio(self):
        """El guion es para el campo vacío: 0, 0,00 y una casilla destildada son cambios reales."""

        registrar_edicion_dispositivo(self.cis, self.operador_cis, {"camas_totales": {"anterior": 0, "nuevo": 10}})

        [evento] = _todo(self.cis)
        self.assertEqual(evento["detalle"], "Camas/plazas totales: 0 → 10")

    def test_la_reserva_no_muestra_el_id_del_ciudadano(self):
        """El servicio traza «· ciudadano 34»: un id crudo no va a la pantalla."""

        reservar_plaza(plaza=self.plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)

        [evento] = _todo(self.cis)
        self.assertEqual(evento["titulo"], "Plaza reservada")
        self.assertEqual(evento["detalle"], "Plaza P1 · Reserva")
        self.assertNotIn(str(self.otra_persona.pk), evento["detalle"])

    def test_un_relevamiento_con_criticidad_alta_no_sale_en_verde(self):
        registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.ALTA)

        resultado = next(e for e in _todo(self.cis) if e["titulo"] == "Resultado del relevamiento edilicio")
        self.assertEqual(resultado["tono"], "danger")

    def test_un_relevamiento_sin_criticidad_alta_si(self):
        registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.MEDIA)

        resultado = next(e for e in _todo(self.cis) if e["titulo"] == "Resultado del relevamiento edilicio")
        self.assertEqual(resultado["tono"], "success")

    def test_la_observacion_del_dispositivo_lleva_su_motivo(self):
        TrazaDispositivo.objects.create(
            dispositivo=self.cis,
            usuario=self.operador_cis,
            accion="OBSERVADO",
            estado_anterior="PENDIENTE_VALIDACION",
            estado_nuevo="OBSERVADO",
            detalle="Falta el teléfono",
        )
        [evento] = _todo(self.cis)
        self.assertEqual(evento["titulo"], "Observación del dispositivo")
        self.assertEqual(evento["detalle"], "Pendiente de validación → Observado · Motivo: Falta el teléfono")
        self.assertEqual(evento["tono"], "warning")


class OrdenYPaginasTests(BaseAuditoria):
    def _historial_largo(self):
        estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )
        for n in range(POR_PAGINA_HISTORIAL):
            plaza = Plaza.objects.create(sector=self.sector, codigo=f"Q{n}")
            sacar_plaza_de_servicio(plaza=plaza, usuario=self.operador_cis, motivo=f"Obra {n}")
        inspeccion = self._relevamiento()
        registrar_resultado(self.agente, inspeccion, criticidad=Criticidad.BAJA)
        egresar_persona(estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

    def test_de_lo_mas_nuevo_a_lo_mas_viejo_entre_todas_las_fuentes(self):
        self._historial_largo()
        eventos = _todo(self.cis)
        fechas = [evento["fecha"] for evento in eventos]
        self.assertEqual(fechas, sorted(fechas, reverse=True))
        self.assertEqual(eventos[0]["titulo"], "Egreso de Gómez, Ana")
        self.assertEqual(eventos[-1]["titulo"], "Ingreso de Gómez, Ana")

    def test_las_paginas_recorren_todo_una_sola_vez(self):
        self._historial_largo()
        total = auditoria_del_dispositivo(self.cis).count()
        self.assertGreater(total, POR_PAGINA_HISTORIAL)

        vistos = []
        pagina, eventos = eventos_de_historial(self.cis, 1)
        vistos += eventos
        while pagina.has_next():
            pagina, eventos = eventos_de_historial(self.cis, pagina.next_page_number())
            vistos += eventos

        self.assertEqual(len(vistos), total)
        claves = [(e["cuando"], e["titulo"], e["detalle"]) for e in vistos]
        self.assertEqual(len(set(claves)), total, "ningún evento repetido entre páginas")
        self.assertEqual(Counter(e["titulo"] for e in vistos), Counter(_titulos(self.cis)))


class AlcanceTests(BaseAuditoria):
    def test_lo_de_otra_institucion_no_aparece(self):
        """Cada una de las cuatro fuentes se filtra por dispositivo, no solo la de estadías."""

        bitacorista = self._usuario(
            "bitacorista_parador",
            ("dispositivo.ver", "dispositivo.bitacora", "dispositivo.editar"),
            [self.parador],
        )
        ingresar_persona(
            ciudadano=self.persona, dispositivo=self.parador, usuario=self.operador_parador, plaza=self.plaza_parador
        )
        # `TrazaDispositivo`: las reservas, las plazas y los turnos del parador.
        reservada = Plaza.objects.create(sector=self.sector_parador, codigo="G2")
        reservar_plaza(plaza=reservada, ciudadano=self.otra_persona, usuario=self.operador_parador)
        rota = Plaza.objects.create(sector=self.sector_parador, codigo="G3")
        sacar_plaza_de_servicio(plaza=rota, usuario=self.operador_parador, motivo="Cama rota")
        crear_turno(
            dispositivo=self.parador,
            usuario=self.operador_parador,
            nombre="Guardia",
            hora_desde=time(8),
            hora_hasta=time(8),
        )
        # `EntradaBitacora` con versión mayor a 1: la corrección de una novedad del parador.
        entrada = registrar_entrada(
            dispositivo=self.parador, usuario=bitacorista, tipo=EntradaBitacora.Tipo.GENERAL, texto="Sin novedad"
        )
        corregir_entrada(entrada=entrada, usuario=bitacorista, texto="Corte de luz", motivo="Faltaba")

        self.assertEqual(_titulos(self.cis), [])
        self.assertEqual(
            Counter(_titulos(self.parador)),
            Counter(
                {
                    "Ingreso de Gómez, Ana": 1,
                    "Plaza reservada": 1,
                    "Plaza fuera de servicio": 1,
                    "Alta de un turno": 1,
                    "Corrección de una novedad de la bitácora": 1,
                }
            ),
        )

    def test_el_relevamiento_de_un_edificio_ajeno_no_aparece(self):
        self._relevamiento(edificio=self.edificio_parador, coordinador=self.coordinador_parador)
        self.assertEqual(_titulos(self.cis), [])
        self.assertEqual(_titulos(self.parador), ["Relevamiento edilicio asignado"])

    def test_el_relevamiento_del_predio_compartido_aparece_en_cada_institucion(self):
        self.edificio_cis.dispositivos.add(self.parador)
        self._relevamiento()
        self.assertEqual(_titulos(self.cis), ["Relevamiento edilicio asignado"])
        self.assertEqual(_titulos(self.parador), ["Relevamiento edilicio asignado"])

    def test_la_solapa_historial_muestra_el_feed_y_otra_institucion_no_entra(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)
        url = reverse("dispositivos:detalle", args=[self.cis.pk])

        self.client.force_login(self.operador_cis)
        self.assertContains(self.client.get(url, {"tab": "historial"}), "Ingreso de Gómez, Ana")

        self.client.force_login(self.operador_parador)
        self.assertEqual(self.client.get(url).status_code, 403)


@tag("performance")
class AuditoriaPresupuestoTests(BaseAuditoria):
    def _medir(self):
        with CaptureQueriesContext(connection) as medida:
            pagina, eventos = eventos_de_historial(self.cis, 1)
            pagina.paginator.count  # el contador de la solapa
        return len(medida), eventos

    def _una_vuelta(self, sufijo):
        persona = type(self.persona).objects.create(dni=f"5{sufijo:07d}", nombre=f"N{sufijo}", apellido=f"A{sufijo}")
        plaza = Plaza.objects.create(sector=self.sector, codigo=f"V{sufijo}")
        estadia = ingresar_persona(ciudadano=persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=plaza)
        egresar_persona(estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)
        sacar_plaza_de_servicio(plaza=plaza, usuario=self.operador_cis, motivo="Obra")
        entrada = registrar_entrada(
            dispositivo=self.cis, usuario=self.bitacorista, tipo=EntradaBitacora.Tipo.GENERAL, texto=f"Nota {sufijo}"
        )
        corregir_entrada(entrada=entrada, usuario=self.bitacorista, texto=f"Nota corregida {sufijo}")
        inspeccion = self._relevamiento()
        registrar_resultado(self.agente, inspeccion, criticidad=Criticidad.BAJA)

    def test_el_historial_respeta_el_presupuesto_y_no_crece_con_las_filas(self):
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]["consultas_fijas"]
        self._turno()
        self._una_vuelta(0)
        pocas, _eventos = self._medir()

        for sufijo in range(1, 15):
            self._una_vuelta(sufijo)
        muchas, eventos = self._medir()

        self.assertEqual(muchas, pocas, "una consulta por evento sería un N+1 en el historial")
        self.assertLessEqual(muchas, techo)
        self.assertEqual(len(eventos), POR_PAGINA_HISTORIAL)
