"""Reservas de derivación, bitácora automática sin movimiento y señal de egreso (Emergencia, PR 6).

Son los tres puntos de extensión que Emergencia necesita dentro de Dispositivos, y lo que
se prueba acá es sobre todo **lo que no cambió**:

1. **Las N camas de una familia** se reservan a nombre del mismo responsable, sin que eso
   afloje «una reserva por persona» para las reservas comunes ni la decisión D2 del PM
   (Cambio 409: el ingreso cierra las reservas de la persona).
2. **Consumir** una de esas reservas con otra persona funciona solo para una reserva de
   derivación: el MAJOR 1 de #802 (la reserva ajena no se usa) sigue en pie.
3. Las lecturas de Dispositivos —ocupación, mapa, alertas, baja de sector— tratan a la
   reserva de derivación como a cualquiera.
4. La **bitácora automática** sin movimiento respeta «sin turno no se escribe».
5. La **señal de egreso** corre dentro de la transacción: un receptor que falla lo deshace.

Las carreras de verdad están en `test_emergencia_reservas_concurrencia`, contra el motor real.
"""

from datetime import datetime, time, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.test import SimpleTestCase
from django.utils import timezone

from core.tests.candados import orden_de_candados
from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Dispositivo,
    EntradaBitacora,
    Estadia,
    GrupoFamiliar,
    MovimientoEstadia,
    Plaza,
    ReservaPlaza,
    Sector,
    TrazaDispositivo,
    Turno,
)
from programas.selectors.capacidad_dispositivo import plazas_tomadas_del_sector
from programas.senales import estadia_egresada
from programas.services import alertas_dispositivos
from programas.services import reservas_derivacion as servicio_reservas_derivacion
from programas.services.bitacora import (
    anotar_novedad_automatica,
    corregir_entrada,
)
from programas.services.bitacora_detalle import detalle_entrada
from programas.services.bitacora_pantalla import pantalla_bitacora
from programas.services.emergencia_alojar import al_egresar_estadia
from programas.services.estadias import (
    PERSONA_CON_RESERVA,
    PLAZA_FUERA_DEL_DISPOSITIVO,
    AlojamientoEnLaRed,
    egresar_persona,
    ingresar_persona,
    liberar_reserva,
    reserva_abierta_de,
    reserva_propia_vigente,
    reservar_plaza,
    sacar_plaza_de_servicio,
)
from programas.services.ingreso import (
    MOTIVO_RESERVA_CERRADA_POR_INGRESO,
    RESERVA_NUEVA_DURANTE_EL_INGRESO,
    confirmar_ingreso,
    plaza_reservada_de,
    plazas_para_ingresar,
    reservas_en_otros_dispositivos,
)
from programas.services.ocupacion import (
    ESTADO_DISPONIBLE,
    ESTADO_RESERVADA,
    estado_de_plazas,
    ocupacion_de_plazas,
)
from programas.services.reservas_derivacion import (
    RESERVA_NO_ES_DE_DERIVACION,
    RESERVA_YA_NO_VIGENTE,
    consumir_reserva_de_derivacion,
    liberar_reservas_de_derivacion,
    reservar_plazas_de_derivacion,
)
from programas.tests.test_dispositivos_estadias import CAPACIDADES_OPERATIVAS, BaseEstadias

#: Un lunes a las 10 de la mañana: el reloj fijo de `OrdenDeLosCandadosTests`.
RELOJ = timezone.make_aware(datetime(2026, 9, 7, 10))


class BaseDerivacion(BaseEstadias):
    """El terreno de `BaseEstadias` más una familia de Emergencia derivada al CIS.

    El caso y la derivación se crean **por el modelo**, no por `services.emergencia`: lo que se
    prueba es Dispositivos, y aceptar una derivación es de otro PR. `self.persona` (Ana) es la
    responsable del grupo; `self.otra_persona` (Juan), un integrante cualquiera.
    """

    def setUp(self):
        super().setUp()
        reloj = mock.patch("django.utils.timezone.now", return_value=RELOJ)
        reloj.start()
        self.addCleanup(reloj.stop)
        # Siete camas en total en el CIS: las dos de la base y cinco más.
        self.plazas = [
            self.plaza,
            self.otra_plaza,
            *(Plaza.objects.create(sector=self.sector, codigo=f"P{numero}") for numero in range(3, 8)),
        ]
        self.derivacion = self._derivacion()

    def _derivacion(self, *, responsable=None, dispositivo=None, estado=Derivacion.Estado.ACEPTADA, plazas_pedidas=7):
        correlativo = CasoEmergencia.objects.count() + 1
        grupo = GrupoFamiliar.objects.create(
            responsable=responsable or self.persona,
            traslado=GrupoFamiliar.Traslado.BOMBEROS,
            adultos_f=1,
            total_declarado=plazas_pedidas,
        )
        caso = CasoEmergencia.objects.create(
            numero=CasoEmergencia.formatear_numero(2026, correlativo),
            grupo=grupo,
            origen=CasoEmergencia.Origen.MESA,
            estado=CasoEmergencia.Estado.INGRESO_EN_CURSO,
            prioridad=CasoEmergencia.Prioridad.MEDIA,
            direccion="Av. Sarmiento 100",
            relevado_por=self.operador_cis,
            relevado_en=RELOJ,
        )
        return Derivacion.objects.create(
            caso=caso,
            dispositivo=dispositivo or self.cis,
            estado=estado,
            plazas_pedidas=plazas_pedidas,
            vence_en=RELOJ + timedelta(hours=2),
            derivada_por=self.operador_cis,
        )

    def _reservar(self, plazas=None, *, derivacion=None, usuario=None):
        return reservar_plazas_de_derivacion(
            derivacion=derivacion or self.derivacion,
            plazas=self.plazas if plazas is None else plazas,
            usuario=usuario or self.operador_cis,
        )

    def _de_derivacion(self, derivacion=None):
        return ReservaPlaza.objects.filter(derivacion=derivacion or self.derivacion)

    def _guardia_24h(self, dispositivo=None):
        """Un turno que contiene cualquier hora: la novedad automática tiene dónde caer."""

        return Turno.objects.create(
            dispositivo=dispositivo or self.cis, nombre="Guardia", hora_desde=time(0), hora_hasta=time(0)
        )


class ReservarPlazasDeDerivacionTests(BaseDerivacion):
    def test_siete_reservas_a_nombre_del_mismo_responsable(self):
        """H1 (b): lo que `reservar_plaza` no deja hacer, y Emergencia necesita."""

        reservas = self._reservar()

        self.assertEqual(len(reservas), 7)
        self.assertEqual([reserva.plaza_id for reserva in reservas], sorted(plaza.pk for plaza in self.plazas))
        for reserva in ReservaPlaza.objects.filter(pk__in=[reserva.pk for reserva in reservas]):
            self.assertEqual(reserva.derivacion_id, self.derivacion.pk)
            self.assertEqual(reserva.ciudadano_id, self.persona.pk)
            self.assertEqual(reserva.tipo, ReservaPlaza.Tipo.RESERVA)
            self.assertEqual(reserva.estado, ReservaPlaza.Estado.VIGENTE)
            self.assertIsNone(reserva.hasta)
            self.assertEqual(reserva.desde, RELOJ)
            self.assertEqual(reserva.motivo, f"Emergencia caso N.° {self.derivacion.caso.numero}")
            self.assertEqual(reserva.creada_por_id, self.operador_cis.pk)
        trazas = TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="PLAZA_RESERVADA")
        self.assertEqual(trazas.count(), 7)
        self.assertTrue(all(f"derivación {self.derivacion.pk}" in traza.detalle for traza in trazas))
        # Sin nombres propios en el historial del dispositivo.
        self.assertFalse(any(self.persona.apellido in traza.detalle for traza in trazas))

    def test_acepta_ids_de_plaza_ademas_de_instancias(self):
        reservas = self._reservar([self.plaza.pk, self.otra_plaza.pk])

        self.assertEqual({reserva.plaza_id for reserva in reservas}, {self.plaza.pk, self.otra_plaza.pk})

    def test_la_reserva_normal_del_responsable_no_impide_las_de_la_familia_ni_al_reves(self):
        """«Una por persona» vale para las comunes, y las de derivación no entran en la cuenta."""

        normal = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        self._reservar(self.plazas[1:4])

        self.assertEqual(self._de_derivacion().count(), 3)
        # La regla de siempre, intacta: una segunda reserva **común** de la misma persona se rechaza,
        # y el mensaje nombra la reserva común que ya tiene, no una de las de la familia.
        with self.assertRaises(ValidationError) as error:
            reservar_plaza(plaza=self.plazas[4], ciudadano=self.persona, usuario=self.operador_cis)
        esperado = PERSONA_CON_RESERVA.format(que="una reserva", plaza=f"{self.plaza.codigo} ({self.sector.nombre})")
        self.assertEqual(error.exception.message_dict, {"ciudadano": [esperado]})
        self.assertEqual(reserva_propia_vigente(self.persona.pk, self.cis).pk, normal.pk)

    def test_con_solo_reservas_de_derivacion_el_responsable_puede_tener_su_reserva_normal(self):
        self._reservar(self.plazas[:3])

        self.assertIsNone(reserva_propia_vigente(self.persona.pk, self.cis))
        normal = reservar_plaza(plaza=self.plazas[3], ciudadano=self.persona, usuario=self.operador_cis)

        self.assertIsNone(normal.derivacion_id)
        self.assertEqual(reserva_propia_vigente(self.persona.pk, self.cis).pk, normal.pk)

    def test_el_responsable_ya_alojado_en_otro_dispositivo_no_impide_reservar(self):
        """H1 (c) y RN-2.15: es un dato para la mesa, no un freno."""

        ingresar_persona(
            ciudadano=self.persona, dispositivo=self.parador, usuario=self.operador_parador, plaza=self.plaza_parador
        )

        reservas = self._reservar(self.plazas[:2])

        self.assertEqual(len(reservas), 2)
        # Y la reserva común sigue rechazando a quien ya está alojado.
        with self.assertRaises(ValidationError):
            reservar_plaza(plaza=self.plazas[2], ciudadano=self.persona, usuario=self.operador_cis)

    def _no_reserva_nada(self, plazas, *, fragmento=None, campo="plaza"):
        with self.assertRaises(ValidationError) as error:
            self._reservar(plazas)
        self.assertIn(campo, error.exception.message_dict)
        if fragmento is not None:
            self.assertIn(fragmento, " ".join(error.exception.messages))
        self.assertFalse(self._de_derivacion().exists(), "todo o nada: quedó alguna reserva de la familia")
        return error.exception

    def test_todo_o_nada_si_una_plaza_ya_esta_reservada(self):
        reservar_plaza(plaza=self.plazas[2], ciudadano=self.otra_persona, usuario=self.operador_cis)

        error = self._no_reserva_nada(self.plazas[:4], fragmento="La plaza ya tiene una reserva vigente.")

        # El error nombra la cama que hay que cambiar.
        self.assertIn(f"{self.plazas[2].codigo} ({self.sector.nombre})", error.messages[0])

    def test_todo_o_nada_si_una_plaza_esta_ocupada(self):
        ingresar_persona(
            ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plazas[1]
        )

        self._no_reserva_nada(self.plazas[:3], fragmento="La plaza ya tiene una estadía activa.")

    def test_todo_o_nada_si_una_plaza_esta_fuera_de_servicio(self):
        sacar_plaza_de_servicio(plaza=self.plazas[3], usuario=self.operador_cis, motivo="Colchón roto")

        self._no_reserva_nada(self.plazas[:5], fragmento="La plaza está fuera de servicio.")

    def test_todo_o_nada_si_el_sector_de_una_plaza_esta_dado_de_baja(self):
        otro = Sector.objects.create(dispositivo=self.cis, nombre="Anexo", capacidad=1, activo=False)
        del_anexo = Plaza.objects.create(sector=otro, codigo="X1")

        self._no_reserva_nada([self.plaza, del_anexo], fragmento="El sector de la plaza está dado de baja.")

    def test_la_plaza_de_otro_dispositivo_y_la_inexistente_dan_el_mismo_error(self):
        """El mismo oráculo que cierra `_bloquear_plaza`: no se enumeran plazas ajenas."""

        ajena = self._no_reserva_nada([self.plaza, self.plaza_parador])
        inexistente = self._no_reserva_nada([self.plaza, 999_999])

        self.assertEqual(ajena.message_dict, {"plaza": [PLAZA_FUERA_DEL_DISPOSITIVO]})
        self.assertEqual(inexistente.message_dict, ajena.message_dict)

    def test_la_lista_vacia_o_con_repetidas_se_rechaza(self):
        self._no_reserva_nada([])
        self._no_reserva_nada([self.plaza, self.plaza.pk])

    def test_sin_admitir_en_ese_dispositivo_no_reserva(self):
        with self.assertRaises(PermissionDenied):
            self._reservar(self.plazas[:2], usuario=self.operador_parador)

        self.assertFalse(ReservaPlaza.objects.exists())

    def test_con_alcance_pero_sin_la_capacidad_de_admitir_tampoco(self):
        solo_ver = self._operador("Solo ver CIS", self.cis, ("dispositivo.ver", "dispositivo.egresar"))

        with self.assertRaises(PermissionDenied):
            self._reservar(self.plazas[:2], usuario=solo_ver)

    def test_no_se_reserva_en_un_dispositivo_que_no_esta_activo(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.INACTIVO)
        self.derivacion.refresh_from_db()

        self._no_reserva_nada(self.plazas[:2], campo="dispositivo")

    def test_no_se_reserva_para_una_derivacion_que_ya_no_esta_vigente(self):
        for estado in (Derivacion.Estado.RECHAZADA, Derivacion.Estado.VENCIDA, Derivacion.Estado.CANCELADA):
            self.derivacion.estado = estado
            self.derivacion.save(update_fields=["estado"])
            self._no_reserva_nada(self.plazas[:2], campo="derivacion")

    def test_la_derivacion_pendiente_tambien_reserva(self):
        """`aceptar` puede reservar antes de cambiar el estado: las dos vigentes sirven."""

        self.derivacion.estado = Derivacion.Estado.PENDIENTE
        self.derivacion.save(update_fields=["estado"])

        self.assertEqual(len(self._reservar(self.plazas[:2])), 2)

    def test_la_reserva_no_puede_empezar_en_el_futuro(self):
        with self.assertRaises(ValidationError) as error:
            reservar_plazas_de_derivacion(
                derivacion=self.derivacion,
                plazas=self.plazas[:2],
                usuario=self.operador_cis,
                momento=RELOJ + timedelta(minutes=1),
            )

        self.assertIn("desde", error.exception.message_dict)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_dos_familias_no_se_pisan_las_camas(self):
        otra = self._derivacion(responsable=self.otra_persona, plazas_pedidas=2)
        self._reservar(self.plazas[:3])

        with self.assertRaises(ValidationError):
            self._reservar(self.plazas[2:5], derivacion=otra)

        self.assertFalse(self._de_derivacion(otra).exists())
        self.assertEqual(len(self._reservar(self.plazas[3:5], derivacion=otra)), 2)


class IngresoNormalDelResponsableTests(BaseDerivacion):
    """C1 del plan: la D2 del PM (Cambio 409) no se lleva puestas las camas de la familia."""

    def _confirmar(self, plaza, ciudadano=None):
        return confirmar_ingreso(
            dispositivo=self.cis,
            usuario=self.operador_cis,
            ciudadano_id=(ciudadano or self.persona).pk,
            datos_renaper=None,
            plaza_id=plaza.pk if plaza is not None else None,
        )

    def test_el_ingreso_del_responsable_no_libera_las_reservas_de_derivacion_y_si_las_normales(self):
        self._reservar(self.plazas[:4])
        # Dos reservas comunes del responsable: una acá y otra en el Parador. D2 las cierra.
        aca = reservar_plaza(plaza=self.plazas[4], ciudadano=self.persona, usuario=self.operador_cis)
        alla = reservar_plaza(plaza=self.plaza_parador, ciudadano=self.persona, usuario=self.operador_parador)

        estadia = self._confirmar(self.plazas[5])

        self.assertEqual(estadia.plaza_id, self.plazas[5].pk)
        self.assertEqual(
            list(self._de_derivacion().values_list("estado", flat=True)),
            [ReservaPlaza.Estado.VIGENTE] * 4,
            "el ingreso del responsable liberó camas de su familia",
        )
        for normal in (aca, alla):
            normal.refresh_from_db()
            self.assertEqual(normal.estado, ReservaPlaza.Estado.LIBERADA, "la D2 del Cambio 409 dejó de aplicarse")

    def test_el_ingreso_del_responsable_sin_plaza_tampoco_las_libera(self):
        self._reservar(self.plazas[:2])

        self._confirmar(None)

        self.assertEqual(self._de_derivacion().filter(estado=ReservaPlaza.Estado.VIGENTE).count(), 2)

    def test_el_ingreso_del_responsable_que_consume_su_reserva_normal_no_toca_las_de_la_familia(self):
        self._reservar(self.plazas[:2])
        normal = reservar_plaza(plaza=self.plazas[2], ciudadano=self.persona, usuario=self.operador_cis)

        estadia = self._confirmar(self.plazas[2])

        normal.refresh_from_db()
        self.assertEqual(normal.estado, ReservaPlaza.Estado.CONSUMIDA)
        self.assertEqual(estadia.plaza_id, self.plazas[2].pk)
        self.assertEqual(self._de_derivacion().filter(estado=ReservaPlaza.Estado.VIGENTE).count(), 2)

    def test_el_asistente_normal_no_ofrece_una_cama_de_la_familia_como_la_plaza_del_responsable(self):
        self._reservar(self.plazas[:2])

        # Lo que hace la vista del asistente: la plaza «propia» sale de `plaza_reservada_de`.
        propia = plaza_reservada_de(self.persona.pk, self.cis)
        self.assertIsNone(propia)
        armados, elegibles = plazas_para_ingresar(self.cis, plaza_propia_id=propia)

        celdas = {celda["pk"]: celda for sector in armados for celda in sector["plazas"]}
        for plaza in self.plazas[:2]:
            self.assertNotIn(plaza.pk, elegibles)
            self.assertEqual(celdas[plaza.pk]["estado"], ESTADO_RESERVADA)
            self.assertFalse(celdas[plaza.pk]["disponible"])
            self.assertFalse(celdas[plaza.pk]["propia"])
        self.assertEqual(elegibles, {plaza.pk for plaza in self.plazas[2:]})
        self.assertEqual(armados[0]["disponibles"], 5)

    def test_el_ingreso_normal_en_una_cama_de_la_familia_se_rechaza_tambien_para_el_responsable(self):
        self._reservar(self.plazas[:2])

        for persona in (self.persona, self.otra_persona):
            with self.assertRaises(ValidationError) as error:
                self._confirmar(self.plazas[0], persona)
            self.assertIn("La plaza ya tiene una reserva vigente.", error.exception.messages)

        self.assertFalse(Estadia.objects.exists())
        self.assertEqual(self._de_derivacion().filter(estado=ReservaPlaza.Estado.VIGENTE).count(), 2)

    def test_el_aviso_de_reservas_en_otros_dispositivos_no_cuenta_las_de_derivacion(self):
        """El paso «Confirmar» avisa lo que el ingreso **va a liberar**: estas no."""

        en_parador = self._derivacion(responsable=self.persona, dispositivo=self.parador, plazas_pedidas=1)
        reservar_plazas_de_derivacion(derivacion=en_parador, plazas=[self.plaza_parador], usuario=self.operador_parador)

        self.assertEqual(reservas_en_otros_dispositivos(self.persona.pk, self.cis, self.operador_cis), ([], 0))


class ConsumirReservaDeDerivacionTests(BaseDerivacion):
    def setUp(self):
        super().setUp()
        self._guardia_24h()
        self.reservas = self._reservar(self.plazas[:3])
        self.reserva = self.reservas[0]

    def _consumir(self, ciudadano, reserva=None, **extra):
        return consumir_reserva_de_derivacion(
            reserva=reserva or self.reserva, ciudadano=ciudadano, usuario=self.operador_cis, **extra
        )

    def _intacta(self, reserva=None, *, de=None):
        reserva = ReservaPlaza.objects.get(pk=(reserva or self.reserva).pk)
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.VIGENTE)
        self.assertEqual(reserva.ciudadano_id, (de or self.persona).pk)

    def test_un_integrante_que_no_es_el_responsable_entra_en_la_cama_reservada(self):
        """H1 (a): lo que `_bloquear_reserva_propia` impide para una reserva común."""

        estadia = self._consumir(self.otra_persona)

        self.assertEqual(estadia.ciudadano_id, self.otra_persona.pk)
        self.assertEqual(estadia.plaza_id, self.reserva.plaza_id)
        self.assertEqual(estadia.dispositivo_id, self.cis.pk)
        self.assertTrue(estadia.activa)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, ReservaPlaza.Estado.CONSUMIDA)
        self.assertEqual(self.reserva.ciudadano_id, self.otra_persona.pk)
        self.assertEqual(self.reserva.derivacion_id, self.derivacion.pk)
        # Como cualquier ingreso: su movimiento, su novedad automática y su traza.
        movimiento = MovimientoEstadia.objects.get(estadia=estadia)
        self.assertEqual(movimiento.tipo, MovimientoEstadia.Tipo.INGRESO)
        self.assertEqual(movimiento.plaza_destino_id, self.reserva.plaza_id)
        entrada = EntradaBitacora.objects.get(movimiento=movimiento)
        self.assertEqual(entrada.tipo, EntradaBitacora.Tipo.INGRESO)
        self.assertEqual(entrada.origen, EntradaBitacora.Origen.AUTOMATICA)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="ESTADIA_INGRESO").exists())
        # Las otras camas de la familia siguen guardadas a nombre del responsable.
        for otra in self.reservas[1:]:
            self._intacta(otra)

    def test_el_propio_responsable_tambien_entra(self):
        estadia = self._consumir(self.persona)

        self.assertEqual(estadia.ciudadano_id, self.persona.pk)
        self.reserva.refresh_from_db()
        self.assertEqual(self.reserva.estado, ReservaPlaza.Estado.CONSUMIDA)
        self.assertEqual(self.reserva.ciudadano_id, self.persona.pk)

    def test_acepta_el_id_de_la_reserva(self):
        estadia = consumir_reserva_de_derivacion(
            reserva=self.reserva.pk, ciudadano=self.otra_persona, usuario=self.operador_cis
        )

        self.assertEqual(estadia.plaza_id, self.reserva.plaza_id)

    def test_la_familia_entera_entra_de_a_uno(self):
        tercera = Ciudadano.objects.create(dni="30555666", nombre="Lía", apellido="Gómez")

        for reserva, persona in zip(self.reservas, (self.otra_persona, self.persona, tercera), strict=True):
            self._consumir(persona, reserva)

        self.assertEqual(Estadia.objects.activas().filter(dispositivo=self.cis).count(), 3)
        self.assertEqual(self._de_derivacion().filter(estado=ReservaPlaza.Estado.CONSUMIDA).count(), 3)

    def _liberada_por_el_ingreso(self, reserva):
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA, "la D2 del Cambio 409 no se aplicó")
        self.assertEqual(reserva.motivo, MOTIVO_RESERVA_CERRADA_POR_INGRESO)

    def test_libera_la_reserva_comun_de_quien_entra_en_el_mismo_dispositivo(self):
        """D2 del Cambio 409, como `confirmar_ingreso`: quien ya está adentro no bloquea otra plaza."""

        comun = reservar_plaza(plaza=self.plazas[4], ciudadano=self.otra_persona, usuario=self.operador_cis)

        estadia = self._consumir(self.otra_persona)

        self.assertEqual(estadia.plaza_id, self.reserva.plaza_id)
        self._liberada_por_el_ingreso(comun)
        # Las de la familia no son «de la persona»: siguen guardadas.
        for otra in self.reservas[1:]:
            self._intacta(otra)

    def test_libera_la_reserva_comun_de_quien_entra_en_otro_dispositivo(self):
        comun = reservar_plaza(plaza=self.plaza_parador, ciudadano=self.otra_persona, usuario=self.operador_parador)

        self._consumir(self.otra_persona)

        self._liberada_por_el_ingreso(comun)
        self.assertIsNone(reserva_abierta_de(self.plaza_parador))

    def test_el_responsable_que_entra_pierde_su_reserva_comun_y_no_las_de_su_familia(self):
        comun = reservar_plaza(plaza=self.plazas[4], ciudadano=self.persona, usuario=self.operador_cis)

        self._consumir(self.persona)

        self._liberada_por_el_ingreso(comun)
        for otra in self.reservas[1:]:
            self._intacta(otra)

    def test_una_reserva_comun_nueva_mientras_se_consume_frena_el_ingreso(self):
        original = servicio_reservas_derivacion._bloquear_persona

        def bloquear_y_que_aparezca(ciudadano):
            original(ciudadano)
            reservar_plaza(plaza=self.plaza_parador, ciudadano=ciudadano, usuario=self.operador_parador)

        with mock.patch.object(servicio_reservas_derivacion, "_bloquear_persona", side_effect=bloquear_y_que_aparezca):
            with self.assertRaises(ValidationError) as error:
                self._consumir(self.otra_persona)

        self.assertEqual(error.exception.messages, [RESERVA_NUEVA_DURANTE_EL_INGRESO])
        self.assertFalse(Estadia.objects.exists())

    def test_la_fecha_de_ingreso_viaja_al_ingreso(self):
        hace_una_hora = RELOJ - timedelta(hours=1)

        estadia = self._consumir(self.otra_persona, fecha_ingreso=hace_una_hora)

        self.assertEqual(estadia.fecha_ingreso, hace_una_hora)

    def test_la_persona_ya_alojada_en_la_red_no_entra_y_la_reserva_vuelve_a_quedar_como_estaba(self):
        ingresar_persona(
            ciudadano=self.otra_persona,
            dispositivo=self.parador,
            usuario=self.operador_parador,
            plaza=self.plaza_parador,
        )

        with self.assertRaises(AlojamientoEnLaRed):
            self._consumir(self.otra_persona)

        # La reasignación se deshizo con el savepoint de la función: sigue siendo del responsable.
        self._intacta()
        self.assertFalse(Estadia.objects.activas().filter(dispositivo=self.cis).exists())

    def test_la_cama_que_quedo_fuera_de_servicio_no_recibe_a_nadie_y_la_reserva_queda_intacta(self):
        """Caso borde de 03 §10: fuera de servicio entre aceptar y confirmar."""

        Plaza.objects.filter(pk=self.reserva.plaza_id).update(
            estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Colchón roto"
        )

        with self.assertRaises(ValidationError) as error:
            self._consumir(self.otra_persona)

        self.assertIn("La plaza está fuera de servicio.", error.exception.messages)
        self._intacta()

    def test_una_reserva_normal_no_se_consume_por_este_camino(self):
        """La guarda que sostiene el MAJOR 1: solo una reserva de derivación cambia de nombre."""

        normal = reservar_plaza(plaza=self.plazas[4], ciudadano=self.persona, usuario=self.operador_cis)

        for quien in (self.otra_persona, self.persona):
            with self.assertRaises(ValidationError) as error:
                self._consumir(quien, normal)
            self.assertEqual(error.exception.message_dict, {"reserva": [RESERVA_NO_ES_DE_DERIVACION]})

        self._intacta(normal)
        self.assertFalse(Estadia.objects.exists())

    def test_major_1_de_802_intacto_la_reserva_normal_ajena_sigue_rechazada(self):
        normal = reservar_plaza(plaza=self.plazas[4], ciudadano=self.persona, usuario=self.operador_cis)

        with self.assertRaises(ValidationError) as error:
            ingresar_persona(
                ciudadano=self.otra_persona,
                dispositivo=self.cis,
                usuario=self.operador_cis,
                plaza=self.plazas[4],
                reserva=normal,
            )

        self.assertEqual(error.exception.message_dict, {"reserva": ["La reserva es de otra persona."]})
        self._intacta(normal)

    def test_ingresar_persona_directo_no_usa_la_reserva_de_derivacion_con_otra_persona(self):
        """El cambio de nombre vive solo en `consumir_reserva_de_derivacion`."""

        with self.assertRaises(ValidationError) as error:
            ingresar_persona(
                ciudadano=self.otra_persona,
                dispositivo=self.cis,
                usuario=self.operador_cis,
                plaza=self.plazas[0],
                reserva=self.reserva,
            )

        self.assertEqual(error.exception.message_dict, {"reserva": ["La reserva es de otra persona."]})
        self._intacta()

    def test_la_reserva_ya_consumida_o_liberada_no_se_consume_de_nuevo(self):
        self._consumir(self.otra_persona)
        liberar_reserva(reserva=self.reservas[1], usuario=self.operador_cis, motivo="No llegó")

        for reserva in self.reservas[:2]:
            with self.assertRaises(ValidationError) as error:
                self._consumir(self.persona, reserva)
            self.assertEqual(error.exception.message_dict, {"reserva": [RESERVA_YA_NO_VIGENTE]})

        self.assertEqual(Estadia.objects.count(), 1)

    def test_sin_alcance_sobre_el_dispositivo_no_consume_y_la_inexistente_da_lo_mismo(self):
        with self.assertRaises(PermissionDenied) as ajena:
            consumir_reserva_de_derivacion(
                reserva=self.reserva, ciudadano=self.otra_persona, usuario=self.operador_parador
            )
        with self.assertRaises(PermissionDenied) as inexistente:
            consumir_reserva_de_derivacion(reserva=999_999, ciudadano=self.otra_persona, usuario=self.operador_cis)

        self.assertEqual(str(ajena.exception), str(inexistente.exception))
        self._intacta()


class LiberarReservasDeDerivacionTests(BaseDerivacion):
    def test_el_operador_del_dispositivo_libera_una_reserva_de_derivacion_desde_el_mapa(self):
        """`liberar_reserva` y `reserva_abierta_de` —lo que usa «Liberar» en el mapa— sin cambios."""

        (reserva,) = self._reservar([self.plaza])

        self.assertEqual(reserva_abierta_de(self.plaza).pk, reserva.pk)
        liberar_reserva(reserva=reserva, usuario=self.operador_cis, motivo="La familia no viene")

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)
        self.assertEqual(reserva.motivo, "La familia no viene")
        self.assertEqual(reserva.derivacion_id, self.derivacion.pk)
        traza = TrazaDispositivo.objects.get(dispositivo=self.cis, accion="PLAZA_LIBERADA")
        self.assertEqual(traza.usuario_id, self.operador_cis.pk)
        self.assertIsNone(reserva_abierta_de(self.plaza))

    def test_libera_las_que_quedan_vigentes_y_no_toca_las_resueltas(self):
        reservas = self._reservar(self.plazas[:5])
        consumir_reserva_de_derivacion(reserva=reservas[0], ciudadano=self.otra_persona, usuario=self.operador_cis)
        liberar_reserva(reserva=reservas[1], usuario=self.operador_cis, motivo="Cama rota")

        liberadas = liberar_reservas_de_derivacion(
            derivacion=self.derivacion, usuario=self.operador_cis, motivo="Cierre con diferencia: no llegó al centro"
        )

        self.assertEqual(liberadas, 3)
        estados = dict(self._de_derivacion().values_list("plaza_id", "estado"))
        self.assertEqual(estados[reservas[0].plaza_id], ReservaPlaza.Estado.CONSUMIDA)
        self.assertEqual([estados[reserva.plaza_id] for reserva in reservas[1:]], [ReservaPlaza.Estado.LIBERADA] * 4)
        motivos = set(
            self._de_derivacion()
            .filter(pk__in=[reserva.pk for reserva in reservas[2:]])
            .values_list("motivo", flat=True)
        )
        self.assertEqual(motivos, {"Cierre con diferencia: no llegó al centro"})
        self.assertEqual(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="PLAZA_LIBERADA").count(), 4)
        # Idempotente: sin nada vigente no hay nada que soltar.
        self.assertEqual(
            liberar_reservas_de_derivacion(derivacion=self.derivacion, usuario=self.operador_cis, motivo="De nuevo"),
            0,
        )

    def test_un_motivo_mas_largo_que_la_columna_se_recorta(self):
        self._reservar(self.plazas[:1])

        liberar_reservas_de_derivacion(derivacion=self.derivacion, usuario=self.operador_cis, motivo="x" * 500)

        self.assertEqual(self._de_derivacion().get().motivo, "x" * 200)

    def test_no_toca_las_reservas_de_otra_familia_ni_las_normales(self):
        otra = self._derivacion(responsable=self.otra_persona, plazas_pedidas=2)
        self._reservar(self.plazas[:2])
        self._reservar(self.plazas[2:4], derivacion=otra)
        normal = reservar_plaza(plaza=self.plazas[4], ciudadano=self.persona, usuario=self.operador_cis)

        self.assertEqual(
            liberar_reservas_de_derivacion(derivacion=self.derivacion, usuario=self.operador_cis, motivo="Cancelado"),
            2,
        )

        self.assertEqual(self._de_derivacion(otra).filter(estado=ReservaPlaza.Estado.VIGENTE).count(), 2)
        normal.refresh_from_db()
        self.assertEqual(normal.estado, ReservaPlaza.Estado.VIGENTE)

    def test_exige_alcance_salvo_que_quien_llama_lo_levante(self):
        self._reservar(self.plazas[:2])

        with self.assertRaises(PermissionDenied):
            liberar_reservas_de_derivacion(derivacion=self.derivacion, usuario=self.operador_parador, motivo="Vencida")
        self.assertEqual(self._de_derivacion().filter(estado=ReservaPlaza.Estado.VIGENTE).count(), 2)

        # La mesa que cancela o el vencimiento: no operan el dispositivo.
        liberadas = liberar_reservas_de_derivacion(
            derivacion=self.derivacion, usuario=self.operador_parador, motivo="Vencida", verificar_alcance=False
        )
        self.assertEqual(liberadas, 2)


class OrdenDeLosCandadosDeDerivacionTests(BaseDerivacion):
    """El orden plaza → reserva → persona, por secuencia de llamadas (como `OrdenDeLosCandadosTests`).

    En SQLite `select_for_update()` es un no-op: el orden no se puede probar por su efecto.
    La carrera real está en `test_emergencia_reservas_concurrencia`, con `@tag("mysql")`.
    """

    def _orden(self):
        return orden_de_candados(plaza=Plaza.objects, reserva=ReservaPlaza.objects, persona=Ciudadano.objects)

    def test_reservar_toma_todas_las_plazas_de_una_vez_y_nada_mas(self):
        with self._orden() as orden:
            self._reservar(self.plazas[:4])

        # Un solo `FOR UPDATE` para las cuatro, y ni la reserva ni el responsable se bloquean.
        self.assertEqual(orden, ["plaza"])

    def test_reservar_pide_las_plazas_ordenadas_por_pk(self):
        consultas = []
        original = Plaza.objects.select_for_update

        def espiar(*args, **kwargs):
            queryset = original(*args, **kwargs)
            consultas.append(queryset)
            return queryset

        with mock.patch.object(Plaza.objects, "select_for_update", espiar):
            reservas = self._reservar(list(reversed(self.plazas[:4])))

        self.assertEqual([reserva.plaza_id for reserva in reservas], sorted(plaza.pk for plaza in self.plazas[:4]))
        self.assertEqual(len(consultas), 1)

    def test_consumir_toma_plaza_despues_reserva_y_despues_persona(self):
        (reserva,) = self._reservar([self.plaza])

        with self._orden() as orden:
            consumir_reserva_de_derivacion(reserva=reserva, ciudadano=self.otra_persona, usuario=self.operador_cis)

        # Los tres primeros son los de `consumir_…`; los tres siguientes, `ingresar_persona`
        # volviendo a pedir lo que la transacción ya tiene, en el mismo orden.
        self.assertEqual(orden, ["plaza", "reserva", "persona", "plaza", "reserva", "persona"])

    def test_consumir_con_reservas_comunes_toma_todas_las_plazas_antes_de_la_primera_reserva(self):
        (reserva,) = self._reservar([self.plaza])
        reservar_plaza(plaza=self.otra_plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)
        reservar_plaza(plaza=self.plaza_parador, ciudadano=self.otra_persona, usuario=self.operador_parador)

        with self._orden() as orden:
            consumir_reserva_de_derivacion(reserva=reserva, ciudadano=self.otra_persona, usuario=self.operador_cis)

        # Las tres plazas juntas y la de la cama; la reserva de la familia; por cada común,
        # `liberar_reserva` (plaza y reserva); la persona, y después `ingresar_persona`.
        self.assertEqual(
            orden,
            ["plaza", "plaza", "reserva", "plaza", "reserva", "plaza", "reserva", "persona"]
            + ["plaza", "reserva", "persona"],
        )

    def test_liberar_las_de_la_derivacion_toma_todas_las_plazas_antes_de_la_primera_reserva(self):
        self._reservar(self.plazas[:2])

        with self._orden() as orden:
            liberar_reservas_de_derivacion(derivacion=self.derivacion, usuario=self.operador_cis, motivo="Cancelado")

        # Primero las plazas juntas; después, por cada reserva, `liberar_reserva` (plaza y reserva).
        self.assertEqual(orden, ["plaza", "plaza", "reserva", "plaza", "reserva"])


class LecturasDeDispositivosTests(BaseDerivacion):
    """Para todo lo que lee reservas, la de derivación es una reserva más."""

    def test_la_ocupacion_cuenta_las_reservas_de_derivacion_como_reservadas(self):
        self._reservar(self.plazas[:3])

        with self.assertNumQueries(3):
            conteo = ocupacion_de_plazas(self.cis).de(self.cis).conteo

        self.assertEqual(conteo.totales, 7)
        self.assertEqual(conteo.reservadas, 3)
        self.assertEqual(conteo.prestadas, 0)
        self.assertEqual(conteo.reservadas_sin_prestamo, 3)
        self.assertEqual(conteo.ocupadas, 0)
        self.assertEqual(conteo.disponibles, 4)

    def test_al_consumirse_la_plaza_pasa_de_reservada_a_ocupada(self):
        reservas = self._reservar(self.plazas[:3])
        consumir_reserva_de_derivacion(reserva=reservas[0], ciudadano=self.otra_persona, usuario=self.operador_cis)

        conteo = ocupacion_de_plazas(self.cis).de(self.cis).conteo

        self.assertEqual((conteo.ocupadas, conteo.reservadas, conteo.disponibles), (1, 2, 4))

    def test_el_mapa_la_dibuja_reservada_y_dice_de_que_derivacion_es_sin_consultas_de_mas(self):
        self._reservar(self.plazas[:2])
        reservar_plaza(plaza=self.plazas[2], ciudadano=self.otra_persona, usuario=self.operador_cis)
        plazas = list(Plaza.objects.filter(sector=self.sector))

        with self.assertNumQueries(2):
            estados = estado_de_plazas(plazas)

        for plaza in self.plazas[:2]:
            self.assertEqual(estados[plaza.pk].estado, ESTADO_RESERVADA)
            self.assertEqual(estados[plaza.pk].derivacion_id, self.derivacion.pk)
            self.assertEqual(estados[plaza.pk].detalle, "sin vencimiento")
        # La reserva común y la plaza libre no traen derivación.
        self.assertEqual(estados[self.plazas[2].pk].estado, ESTADO_RESERVADA)
        self.assertIsNone(estados[self.plazas[2].pk].derivacion_id)
        self.assertEqual(estados[self.plazas[3].pk].estado, ESTADO_DISPONIBLE)
        self.assertIsNone(estados[self.plazas[3].pk].derivacion_id)

    def test_la_plaza_reservada_para_una_familia_no_se_saca_de_servicio(self):
        self._reservar([self.plaza])

        with self.assertRaises(ValidationError):
            sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Refacción")

    def test_cuenta_como_plaza_tomada_para_la_baja_del_sector(self):
        self._reservar(self.plazas[:3])

        self.assertEqual(plazas_tomadas_del_sector(self.sector), 3)

    def test_no_dispara_la_alerta_de_reserva_vencida(self):
        """No tiene `hasta`: no vence sola. El vencimiento es de la derivación, en Emergencia."""

        self._reservar(self.plazas[:3])

        despues = RELOJ + timedelta(days=30)
        self.assertEqual(list(alertas_dispositivos.reservas_vencidas(self.cis, momento=despues)), [])


class IndiceDeLaDerivacionTests(SimpleTestCase):
    """`ReservaPlaza` no puede tener un índice compuesto que empiece por `derivacion`.

    No es una preferencia de rendimiento: es el orden de candados. Con `derivacion_id` a la
    izquierda de un índice que además tenga `estado`, InnoDB lo adopta como índice de la FK,
    y cada `UPDATE` de `estado` (liberar o consumir la reserva) revalida la FK con un lock
    compartido sobre la fila de la **derivación**, después de la plaza y la reserva. El
    orden global de Emergencia es el inverso —derivación → plazas → reservas—, así que
    liberar una cama de una familia desde el mapa se cruzaría con la mesa que cancela esa
    derivación (`ERROR 1213`). Es lo que ya pasa con `(plaza, estado)` y obliga a
    `liberar_reserva` a bloquear la plaza primero; acá no hay forma de «bloquear la
    derivación primero» desde Dispositivos, así que el índice no existe.
    """

    def test_ningun_indice_ni_unique_de_reserva_plaza_empieza_por_la_derivacion(self):
        meta = ReservaPlaza._meta
        compuestos = [tuple(indice.fields) for indice in meta.indexes]
        compuestos += [tuple(c.fields) for c in meta.constraints if isinstance(c, models.UniqueConstraint)]
        compuestos += [tuple(campos) for campos in meta.unique_together]

        culpables = [campos for campos in compuestos if campos and campos[0].lstrip("-") == "derivacion"]

        self.assertEqual(culpables, [], "un índice con `derivacion` a la izquierda cambia el orden de candados")
        self.assertFalse(meta.get_field("derivacion").unique)

    def test_la_columna_es_anulable_y_no_borra_en_cascada(self):
        campo = ReservaPlaza._meta.get_field("derivacion")

        self.assertTrue(campo.null)
        self.assertIs(campo.remote_field.on_delete, models.PROTECT)
        self.assertEqual(campo.remote_field.related_name, "reservas")


class BitacoraAutomaticaSinMovimientoTests(BaseDerivacion):
    """H7 del plan: una `GENERAL` automática que no cuelga de ningún movimiento."""

    def _anotar(self, **cambios):
        datos = {
            "dispositivo": self.cis,
            "tipo": EntradaBitacora.Tipo.GENERAL,
            "texto": "Derivación aceptada · caso 2026-000001 · 7 plazas",
            "usuario": self.operador_cis,
        }
        datos.update(cambios)
        return anotar_novedad_automatica(**datos)

    def test_con_turno_escribe_una_entrada_automatica(self):
        turno = self._guardia_24h()

        entrada = self._anotar()

        entrada = EntradaBitacora.objects.get(pk=entrada.pk)
        self.assertEqual(entrada.origen, EntradaBitacora.Origen.AUTOMATICA)
        self.assertEqual(entrada.tipo, EntradaBitacora.Tipo.GENERAL)
        self.assertEqual(entrada.texto, "Derivación aceptada · caso 2026-000001 · 7 plazas")
        self.assertIsNone(entrada.movimiento_id)
        self.assertEqual(entrada.turno_id, turno.pk)
        self.assertEqual(entrada.fecha_operativa, timezone.localtime(RELOJ).date())
        self.assertEqual(entrada.momento, RELOJ)
        self.assertEqual(entrada.responsable_id, self.operador_cis.pk)
        self.assertEqual(entrada.version, 1)
        self.assertFalse(entrada.personas.exists())

    def test_sin_turno_vigente_devuelve_none_y_no_escribe(self):
        # Sin turnos configurados.
        self.assertIsNone(self._anotar())
        # Y con turnos, pero el momento cae en un hueco: son las 10 y el turno es de 14 a 22.
        Turno.objects.create(dispositivo=self.cis, nombre="Tarde", hora_desde=time(14), hora_hasta=time(22))
        self.assertIsNone(self._anotar())

        self.assertFalse(EntradaBitacora.objects.exists())

    def test_el_turno_es_el_del_momento_del_hecho_no_el_que_corre(self):
        """Como `anotar_en_bitacora`: no pasa por la ventana del turno en curso."""

        tarde = Turno.objects.create(dispositivo=self.cis, nombre="Tarde", hora_desde=time(14), hora_hasta=time(22))
        ayer_a_las_15 = timezone.make_aware(datetime(2026, 9, 6, 15))

        entrada = self._anotar(momento=ayer_a_las_15)

        self.assertEqual(entrada.turno_id, tarde.pk)
        self.assertEqual(entrada.fecha_operativa, ayer_a_las_15.date())

    def test_no_exige_la_capacidad_de_bitacora(self):
        """Quien llega acá ya pasó el control del servicio que genera el hecho."""

        self._guardia_24h()
        self.assertNotIn("dispositivo.bitacora", CAPACIDADES_OPERATIVAS)
        sin_nada = User.objects.create_user(username="mesa_de_emergencia")

        for usuario in (self.operador_cis, self.operador_parador, sin_nada):
            self.assertEqual(self._anotar(usuario=usuario).responsable_id, usuario.pk)

        self.assertEqual(EntradaBitacora.objects.filter(origen=EntradaBitacora.Origen.AUTOMATICA).count(), 3)

    def test_sin_usuario_no_escribe(self):
        self._guardia_24h()

        self.assertIsNone(self._anotar(usuario=None))
        self.assertFalse(EntradaBitacora.objects.exists())

    def test_los_tipos_que_cuelgan_de_un_movimiento_o_de_un_pase_se_rechazan(self):
        self._guardia_24h()

        for tipo in (*sorted(EntradaBitacora.TIPOS_AUTOMATICOS), "INVENTADO", ""):
            with self.assertRaises(ValidationError) as error:
                self._anotar(tipo=tipo)
            self.assertIn("tipo", error.exception.message_dict)
        with self.assertRaises(ValidationError) as error:
            self._anotar(texto="   ")
        self.assertIn("texto", error.exception.message_dict)

        self.assertFalse(EntradaBitacora.objects.exists())

    def test_los_demas_tipos_del_operador_tambien_sirven(self):
        self._guardia_24h()

        entrada = self._anotar(tipo=EntradaBitacora.Tipo.ALIMENTOS, texto="Kit recibido · 12 bultos")

        self.assertEqual(entrada.tipo, EntradaBitacora.Tipo.ALIMENTOS)
        self.assertEqual(entrada.origen, EntradaBitacora.Origen.AUTOMATICA)

    def test_la_pantalla_la_muestra_como_automatica_y_no_la_ofrece_para_corregir(self):
        self._guardia_24h()
        entrada = self._anotar()

        pantalla = pantalla_bitacora(self.cis, puede_cargar=True)

        (dibujada,) = pantalla["entradas"]
        self.assertTrue(dibujada["automatica"])
        self.assertIn("Derivación aceptada", dibujada["texto"])
        self.assertEqual(dibujada["categoria"], "General")
        self.assertEqual(pantalla["corregibles"], [])
        self.assertNotIn("url_corregir", dibujada)
        detalle = detalle_entrada(entrada, nombrar_personas=False)
        self.assertTrue(detalle["automatica"])
        self.assertEqual(detalle["cantidad_personas"], 0)

    def test_no_se_corrige_a_mano(self):
        """La regla que ya regía para las automáticas de un movimiento."""

        self._guardia_24h()
        entrada = self._anotar()
        con_bitacora = self._operador("Guardia CIS", self.cis, (*CAPACIDADES_OPERATIVAS, "dispositivo.bitacora"))

        with self.assertRaises(ValidationError) as error:
            corregir_entrada(entrada=entrada, usuario=con_bitacora, texto="Otra cosa")

        self.assertIn("entrada", error.exception.message_dict)
        self.assertEqual(EntradaBitacora.objects.count(), 1)


class SenalDeEgresoTests(BaseDerivacion):
    """H9 del plan: `estadia_egresada`, dentro de la transacción del egreso."""

    def setUp(self):
        super().setUp()
        self.estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )

    def _egresar(self):
        return egresar_persona(
            estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta, destino="Domicilio"
        )

    def _conectar(self, receptor):
        estadia_egresada.connect(receptor, dispatch_uid="test.receptor_de_egreso")
        self.addCleanup(estadia_egresada.disconnect, dispatch_uid="test.receptor_de_egreso")

    def test_sin_receptores_el_egreso_es_el_de_siempre(self):
        # Desde la etapa 3 de Emergencia escucha su receptor (`emergencia_alojar.al_egresar_estadia`),
        # y solo él. Para una estadía que no es de Emergencia hace una consulta y no cambia nada.
        escuchan, _asincronicos = estadia_egresada._live_receivers(Estadia)
        self.assertEqual(escuchan, [al_egresar_estadia])

        egresada = self._egresar()

        self.assertEqual(egresada.estado, Estadia.Estado.EGRESADA)

    def test_se_emite_una_vez_por_egreso_con_la_estadia_ya_cerrada_y_el_usuario(self):
        recibidas = []

        def receptor(sender, estadia, usuario, **kwargs):
            # Lo que el receptor ve al correr: adentro de la transacción y con todo escrito.
            recibidas.append(
                {
                    "sender": sender,
                    "estadia": estadia.pk,
                    "estado": estadia.estado,
                    "clave": estadia.clave_alojamiento,
                    "usuario": usuario.pk,
                    "en_transaccion": transaction.get_connection().in_atomic_block,
                    "movimiento": MovimientoEstadia.objects.filter(
                        estadia=estadia, tipo=MovimientoEstadia.Tipo.EGRESO
                    ).exists(),
                    "traza": TrazaDispositivo.objects.filter(accion="ESTADIA_EGRESO").exists(),
                }
            )

        self._conectar(receptor)

        self._egresar()

        self.assertEqual(
            recibidas,
            [
                {
                    "sender": Estadia,
                    "estadia": self.estadia.pk,
                    "estado": Estadia.Estado.EGRESADA,
                    "clave": None,
                    "usuario": self.operador_cis.pk,
                    "en_transaccion": True,
                    "movimiento": True,
                    "traza": True,
                }
            ],
        )

    def test_un_egreso_rechazado_no_emite_nada(self):
        recibidas = []
        self._conectar(lambda sender, **kwargs: recibidas.append(kwargs))

        with self.assertRaises(ValidationError):
            egresar_persona(estadia=self.estadia, usuario=self.operador_cis, motivo_egreso=None, destino="Domicilio")

        self.assertEqual(recibidas, [])

    def test_un_receptor_que_falla_deshace_el_egreso(self):
        """Es intencional: `send`, no `send_robust`. El egreso y lo que escucha son un solo hecho."""

        def receptor(sender, **kwargs):
            raise RuntimeError("Emergencia no pudo cerrar el caso")

        self._conectar(receptor)

        with self.assertRaisesMessage(RuntimeError, "Emergencia no pudo cerrar el caso"):
            self._egresar()

        self.estadia.refresh_from_db()
        self.assertEqual(self.estadia.estado, Estadia.Estado.ACTIVA)
        self.assertIsNone(self.estadia.fecha_egreso)
        self.assertEqual(self.estadia.clave_alojamiento, Estadia.clave_para(self.persona))
        self.assertFalse(MovimientoEstadia.objects.filter(tipo=MovimientoEstadia.Tipo.EGRESO).exists())
        self.assertFalse(TrazaDispositivo.objects.filter(accion="ESTADIA_EGRESO").exists())
        # Desconectado el receptor, el mismo egreso entra.
        estadia_egresada.disconnect(dispatch_uid="test.receptor_de_egreso")
        self.assertEqual(self._egresar().estado, Estadia.Estado.EGRESADA)
