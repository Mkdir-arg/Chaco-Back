"""Módulo Emergencia, PR 7: la etapa 3 (alojar) — servicios y selectores de la guardia.

Qué fija este archivo, regla por regla (03-alojar):

* **RN-3.1 / 3.2** — ``buscar_por_dni``: los tres resultados y el alcance.
* **RN-3.3 / 3.4** — ``aceptar_derivacion``: vale vencida si el cron no pasó; reserva hasta lo
  pedido, parcial con aviso, 0 libres no acepta; elige las camas sola.
* **RN-3.5 a 3.7** — ``confirmar_integrante``: consume la reserva por la vía del PR 6, valida
  el mínimo y es atómica (si el ingreso falla no queda nada huérfano).
* **RN-3.8 a 3.10, 3.12 a 3.14** — agregar, cerrar con diferencia, ingreso directo, egreso,
  rechazo y bitácora automática.
* **Bordes de 03 §10.**
* **RU §6 n.° 2** y la mutación nueva del PR («`admitir` en A no acepta una derivación de B»).
  Las dos se vieron en rojo contra la regla rota; el detalle está en el docstring de cada una.
* **El orden de los candados**, por la secuencia de llamadas (en SQLite ``select_for_update``
  es un no-op). Las carreras de verdad están en ``test_emergencia_alojar_concurrencia``.
* **Presupuestos** de ``integrantes_de`` y ``plazas_para_caso`` con 300 camas.
"""

import uuid
from datetime import date, time, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import SimpleTestCase, tag
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from core.models import Localidad
from core.tests.candados import orden_de_candados
from legajos.models import Ciudadano
from legajos.models.contactos import TipoVinculo, VinculoFamiliar
from programas.models import (
    CasoEmergencia,
    Derivacion,
    EntradaBitacora,
    Estadia,
    IntegranteGrupo,
    MiembroEquipoDispositivo,
    MotivoEgreso,
    NumeradorEmergencia,
    Plaza,
    ReservaPlaza,
    Sector,
    TrazaCaso,
    Turno,
)
from programas.selectors import emergencia_alojar as selectores
from programas.selectors import emergencia_llegadas as pantalla
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services import emergencia_confirmacion as servicio_confirmacion
from programas.services import ingreso as servicio_ingreso
from programas.services.emergencia import EstadoCambio
from programas.services.estadias import egresar_persona, liberar_reserva, reservar_plaza
from programas.services.ingreso import MOTIVO_RESERVA_CERRADA_POR_INGRESO, RESERVA_NUEVA_DURANTE_EL_INGRESO
from programas.tests.test_emergencia_casos import T0, BaseCasos

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion

GUARDIA = ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar")


def ficha_minima(dni, **cambios):
    """Una ficha con el mínimo: hija de 20 años, las cinco preguntas en «no»."""

    ficha = {
        "parentesco": {"parentesco": "HIJO"},
        "datos_personales": {
            "dni": dni,
            "nombre": "Juan",
            "apellido": "Pérez",
            "sexo": "M",
            "fecha_nacimiento": "2006-03-10",
        },
        "avisos_salud": {
            "embarazo": False,
            "discapacidad": False,
            "electrodependiente": False,
            "medicacion_critica": False,
            "alergias_graves": False,
        },
    }
    for seccion, datos in cambios.items():
        ficha.setdefault(seccion, {}).update(datos)
    return ficha


class BaseAlojar(BaseCasos):
    """La mesa de ``BaseCasos`` más dos dispositivos con guardia propia y una familia de 7."""

    def setUp(self):
        super().setUp()
        self.club = self._dispositivo("Club Sarmiento", camas=9, localidad="Resistencia")
        self.escuela = self._dispositivo("Escuela 12", camas=5)
        self.guardia = self._guardia("guardia_club", self.club)
        self.guardia_escuela = self._guardia("guardia_escuela", self.escuela)
        self.motivo_alta, _ = MotivoEgreso.objects.get_or_create(codigo="alta", defaults={"nombre": "Alta", "orden": 1})

    def _guardia(self, nombre, *dispositivos, capacidades=GUARDIA):
        usuario = self._usuario(nombre, capacidades, programa=self.dispositivos)
        rol = usuario.groups.get()
        for dispositivo in dispositivos:
            MiembroEquipoDispositivo.objects.create(dispositivo=dispositivo, usuario=usuario, rol=rol)
        return User.objects.get(pk=usuario.pk)

    def _turno(self, dispositivo):
        """Un turno que cubre las 10 de la mañana de ``T0``: con él la bitácora se escribe."""

        return Turno.objects.create(dispositivo=dispositivo, nombre="Mañana", hora_desde=time(6), hora_hasta=time(14))

    def _derivado(self, dispositivo=None, plazas=None, **datos):
        """Un caso de 7 personas tomado y derivado. Devuelve ``(caso, derivacion)``."""

        datos = {"menores_f": 2, "menores_m": 3, "dni": "30111222", "nombre": "Rosa", "apellido": "Benítez", **datos}
        caso = self._caso_tomado(**datos)
        derivacion = mesa.derivar_caso(
            caso, self.operador, dispositivo or self.club, plazas or caso.grupo.total_declarado, True
        )
        return CasoEmergencia.objects.get(pk=caso.pk), derivacion

    def _aceptado(self, **kwargs):
        caso, derivacion = self._derivado(**kwargs)
        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        return resultado.caso, resultado.derivacion

    def _reservas(self, derivacion, estado=ReservaPlaza.Estado.VIGENTE):
        return list(ReservaPlaza.objects.filter(derivacion=derivacion, estado=estado).order_by("plaza_id"))

    def _confirmar(self, caso, orden, dni, plaza=None, usuario=None, **cambios):
        if plaza is None:
            plaza = self._reservas(Derivacion.objects.get(clave_vigente=caso.pk))[0].plaza
        return servicio.confirmar_integrante(
            caso=caso, orden=orden, usuario=usuario or self.guardia, ficha=ficha_minima(dni, **cambios), plaza=plaza
        )

    def _cama_libre(self, dispositivo=None):
        return selectores.camas_libres(dispositivo or self.club)[0]

    def _estado(self, caso):
        return CasoEmergencia.objects.values_list("estado", flat=True).get(pk=caso.pk)


# ---------------------------------------------------------------------------
# La ficha (Formulario 2)
# ---------------------------------------------------------------------------


class FichaTests(SimpleTestCase):
    HOY = date(2026, 11, 12)

    def test_el_esquema_tiene_las_ocho_secciones_en_orden(self):
        self.assertEqual(
            list(servicio.ESQUEMA_FICHA),
            [
                "parentesco",
                "datos_personales",
                "avisos_salud",
                "educacion",
                "vacunacion",
                "salud",
                "trabajo",
                "observaciones",
            ],
        )
        self.assertEqual(servicio.SECCIONES_MINIMAS + servicio.SECCIONES_OPCIONALES, tuple(servicio.ESQUEMA_FICHA))

    def test_los_campos_no_se_repiten_entre_secciones(self):
        """Es lo que deja aplanar la ficha a un formulario y volver a armarla."""

        campos = [campo for seccion in servicio.ESQUEMA_FICHA.values() for campo in seccion]
        self.assertEqual(len(campos), len(set(campos)))

    def test_normalizar_guarda_solo_lo_respondido_y_lleva_la_version(self):
        ficha = servicio.normalizar_ficha(
            {
                "datos_personales": {"dni": "30.111.222", "nombre": "  Juan ", "telefono": "", "cualquiera": 1},
                "avisos_salud": {"embarazo": "no", "discapacidad": True, "electrodependiente": None},
                "educacion": {"sin_datos": "si"},
                "otra_seccion": {"x": 1},
            }
        )

        self.assertEqual(ficha["version"], servicio.FICHA_VERSION)
        self.assertEqual(ficha["datos_personales"], {"dni": "30111222", "nombre": "Juan"})
        self.assertEqual(ficha["avisos_salud"], {"embarazo": False, "discapacidad": True})
        self.assertEqual(ficha["educacion"], {"sin_datos": True})
        self.assertNotIn("otra_seccion", ficha)
        self.assertEqual(servicio.normalizar_ficha(ficha), ficha, "normalizar no es idempotente")

    def test_normalizar_rechaza_lo_que_no_es_del_tipo(self):
        with self.assertRaises(ValidationError) as error:
            servicio.normalizar_ficha(
                {
                    "parentesco": {"parentesco": "PRIMO"},
                    "datos_personales": {"fecha_nacimiento": "ayer", "telefono": "1" * 41},
                }
            )
        self.assertEqual(set(error.exception.error_dict), {"parentesco", "fecha_nacimiento", "telefono"})

    def test_el_minimo_completo_pasa(self):
        ficha = servicio.ficha_minima_valida(ficha_minima("30111222"), hoy=self.HOY)
        self.assertEqual(ficha["datos_personales"]["fecha_nacimiento"], "2006-03-10")

    def test_sin_avisos_de_salud_falta_cada_pregunta(self):
        """HU-3.3: «Falta: avisos de salud». Las cinco tienen que estar **respondidas**."""

        ficha = ficha_minima("30111222")
        ficha["avisos_salud"] = {"embarazo": False}

        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida(ficha, hoy=self.HOY)

        errores = error.exception.message_dict
        self.assertEqual(set(errores), {"discapacidad", "electrodependiente", "medicacion_critica", "alergias_graves"})
        self.assertTrue(all("Falta: avisos de salud" in mensajes[0] for mensajes in errores.values()))

    def test_la_medicacion_critica_pide_nombre_y_dosis(self):
        ficha = ficha_minima("30111222", avisos_salud={"medicacion_critica": True})
        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida(ficha, hoy=self.HOY)
        self.assertEqual(
            set(error.exception.error_dict), {"medicacion_critica_nombre", "medicacion_critica_tiene_dosis"}
        )

        ficha["avisos_salud"].update(medicacion_critica_nombre="Insulina", medicacion_critica_tiene_dosis=False)
        servicio.ficha_minima_valida(ficha, hoy=self.HOY)

    def test_falta_todo_lo_demas_del_minimo(self):
        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida({"parentesco": {"parentesco": "OTRO"}}, hoy=self.HOY)
        self.assertTrue(
            {"parentesco_otro", "dni", "nombre", "apellido", "sexo", "fecha_nacimiento", "embarazo"}
            <= set(error.exception.error_dict)
        )

    def test_sin_numero_de_dni_no_se_confirma(self):
        """Decisión del PM (D-10): no se inventan DNI; se cierra con diferencia."""

        for dni in ("", "no sabe", "123"):
            with self.subTest(dni=dni), self.assertRaises(ValidationError) as error:
                servicio.ficha_minima_valida(ficha_minima(dni), hoy=self.HOY)
            self.assertEqual(error.exception.message_dict["dni"], [servicio.SIN_NUMERO_DE_DOCUMENTO])

    def test_un_menor_de_16_necesita_adulto_responsable(self):
        """03 §10. 15 años y 364 días es menor; el día que cumple 16, no."""

        menor = ficha_minima("50111222", datos_personales={"fecha_nacimiento": "2010-11-13"})
        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida(menor, hoy=self.HOY)
        self.assertEqual(set(error.exception.error_dict), {"adulto_responsable"})

        menor["observaciones"] = {"adulto_responsable": "Rosa Benítez, la madre"}
        servicio.ficha_minima_valida(menor, hoy=self.HOY)
        cumple_16 = ficha_minima("50111222", datos_personales={"fecha_nacimiento": "2010-11-12"})
        servicio.ficha_minima_valida(cumple_16, hoy=self.HOY)

    def test_una_fecha_de_nacimiento_futura_no_vale(self):
        with self.assertRaises(ValidationError) as error:
            servicio.ficha_minima_valida(
                ficha_minima("30111222", datos_personales={"fecha_nacimiento": "2027-01-01"}), hoy=self.HOY
            )
        self.assertEqual(set(error.exception.error_dict), {"fecha_nacimiento"})

    def test_la_ficha_esta_completa_con_un_dato_o_sin_datos_en_cada_seccion(self):
        ficha = servicio.normalizar_ficha(ficha_minima("30111222"))
        self.assertFalse(servicio.ficha_esta_completa(ficha))
        self.assertEqual(len(servicio.secciones_incompletas(ficha)), 5)

        ficha = servicio.normalizar_ficha(
            ficha_minima(
                "30111222",
                educacion={"nivel_educativo": "PRIMARIO"},
                vacunacion={"sin_datos": True},
                salud={"obra_social": "No tiene"},
                trabajo={"sin_datos": True},
                observaciones={"mascotas": False},
            )
        )
        self.assertTrue(servicio.ficha_esta_completa(ficha))

    def test_la_ficha_se_aplana_y_se_vuelve_a_armar(self):
        ficha = servicio.normalizar_ficha(
            ficha_minima("30111222", salud={"sin_datos": True}, trabajo={"ocupacion": "Albañil"})
        )
        plano = servicio.ficha_a_plano(ficha)

        self.assertEqual(plano["dni"], "30111222")
        self.assertIs(plano["salud_sin_datos"], True)
        self.assertEqual(plano["ocupacion"], "Albañil")
        self.assertEqual(servicio.normalizar_ficha(servicio.ficha_desde_plano(plano)), ficha)


# ---------------------------------------------------------------------------
# Buscar (RN-3.1, RN-3.2)
# ---------------------------------------------------------------------------


class BuscarPorDniTests(BaseAlojar):
    def test_el_dni_del_responsable_encuentra_la_derivacion_de_mi_dispositivo(self):
        caso, derivacion = self._derivado()

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30.111.222", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_DERIVACION)
        self.assertEqual(resultado.derivacion, derivacion)
        self.assertEqual(resultado.caso, caso)
        self.assertEqual(resultado.plazas_libres, 9)
        self.assertEqual(resultado.dni, "30111222")

    def test_el_dni_de_un_integrante_ya_confirmado_tambien_la_encuentra(self):
        caso, derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="45000111", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_DERIVACION)
        self.assertEqual(resultado.derivacion, derivacion)

    def test_derivada_a_otro_dispositivo_es_sin_derivacion_y_no_lo_nombra(self):
        """**Mutación RU §6 n.° 2.** La guardia de A busca a una familia derivada a B.

        Visto en rojo sacando ``dispositivo=dispositivo`` del filtro de ``buscar_por_dni``:
        el resultado pasa a ``DERIVACION`` con la derivación de la Escuela adentro, y este
        test falla en la primera afirmación.
        """

        self._derivado(dispositivo=self.escuela)

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
        self.assertIsNone(resultado.derivacion)
        self.assertIsNone(resultado.caso)
        self.assertNotIn("Escuela", repr(resultado))
        self.assertEqual(resultado.mensaje, servicio.SIN_DERIVACION)

    def test_sin_alcance_sobre_el_dispositivo_no_se_busca(self):
        self._derivado()
        with self.assertRaises(PermissionDenied):
            servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia_escuela)
        with self.assertRaises(PermissionDenied):
            servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.operador)

    def test_un_dni_que_nadie_conoce_es_sin_derivacion(self):
        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="39999999", usuario=self.guardia)
        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
        self.assertEqual(resultado.plazas_libres, 9)

    def test_un_dni_que_no_es_un_dni_es_un_error(self):
        with self.assertRaises(ValidationError):
            servicio.buscar_por_dni(dispositivo=self.club, dni="abc", usuario=self.guardia)

    def test_una_persona_alojada_aca_se_informa_con_el_lugar(self):
        self._ocupar(self.club, 1)
        alojada = Estadia.objects.get().ciudadano

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni=alojada.dni, usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_ALOJADA)
        self.assertIs(resultado.alojada_aca, True)
        self.assertEqual(resultado.alojada_en, "Club Sarmiento")
        self.assertEqual(resultado.mensaje, "Alojada en Club Sarmiento desde el 11/11.")

    def test_una_persona_alojada_en_otro_dispositivo_no_dice_donde(self):
        """RN-3.2, RU-9: quien no opera la Escuela solo se entera de que está alojada."""

        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni=alojada.dni, usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_ALOJADA)
        self.assertIs(resultado.alojada_aca, False)
        self.assertEqual(resultado.alojada_en, "")
        self.assertIsNone(resultado.alojada_desde)
        self.assertNotIn("Escuela", repr(resultado))

    def test_quien_opera_los_dos_dispositivos_si_ve_donde_esta(self):
        de_los_dos = self._guardia("guardia_doble", self.club, self.escuela)
        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni=alojada.dni, usuario=de_los_dos)

        self.assertIs(resultado.alojada_aca, False)
        self.assertEqual(resultado.alojada_en, "Escuela 12")

    def test_el_responsable_alojado_con_un_ingreso_en_curso_lleva_a_seguir_con_su_familia(self):
        caso, derivacion = self._aceptado()
        self._confirmar(caso, 1, "30111222", parentesco={"parentesco": "JEFE"})

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_DERIVACION)

    def test_una_derivacion_vencida_no_se_ofrece_y_se_explica(self):
        """RN-3.3: una ``VENCIDA`` no se acepta; RU-20: se dice qué pasó y qué hacer."""

        _caso, derivacion = self._derivado()
        self.reloj.avanzar(hours=13)
        mesa.vencer_derivacion(derivacion)

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
        self.assertIn("La derivación venció a las 22:00", resultado.mensaje)
        self.assertIn("ingresala igual", resultado.mensaje)


# ---------------------------------------------------------------------------
# Aceptar (RN-3.3, RN-3.4) y rechazar (RN-3.13)
# ---------------------------------------------------------------------------


class AceptarDerivacionTests(BaseAlojar):
    def test_aceptar_reserva_las_camas_y_abre_el_ingreso(self):
        """HU-3.2: 7 pedidas y 9 libres."""

        self._turno(self.club)
        caso, derivacion = self._derivado()

        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.INGRESO_EN_CURSO)
        self.assertEqual(fila["aceptado_en"], T0)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.ACEPTADA)
        self.assertEqual(derivacion.respondida_por, self.guardia)
        reservas = self._reservas(derivacion)
        self.assertEqual(len(reservas), 7)
        self.assertEqual({reserva.ciudadano_id for reserva in reservas}, {caso.grupo.responsable_id})
        self.assertTrue(all(reserva.hasta is None for reserva in reservas))
        self.assertEqual((resultado.reservadas, resultado.faltantes), (7, 0))
        self.assertEqual(resultado.mensaje, "Reservé 7 de 7 camas")
        self.assertEqual([fila.orden for fila in resultado.integrantes], [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo, confirmada_en__isnull=True).count(), 7)
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.DERIVACION_ACEPTADA)
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), (Estado.DERIVADO, Estado.INGRESO_EN_CURSO))
        self.assertEqual(traza.usuario, self.guardia)
        # RN-3.14: la novedad GENERAL automática, sin nombres de personas.
        entrada = EntradaBitacora.objects.get(dispositivo=self.club)
        self.assertEqual((entrada.tipo, entrada.origen), ("GENERAL", EntradaBitacora.Origen.AUTOMATICA))
        self.assertIn(f"caso N.° {caso.numero}", entrada.texto)
        self.assertNotIn("Benítez", entrada.texto)

    def test_con_menos_camas_que_las_pedidas_reserva_las_que_hay_y_avisa(self):
        """HU-3.2: 7 pedidas, 5 libres → «Reservé 5 de 7 · faltan 2 camas», y se puede seguir."""

        caso, derivacion = self._derivado()
        self._ocupar(self.club, 4)

        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertEqual((resultado.reservadas, resultado.faltantes), (5, 2))
        self.assertEqual(resultado.mensaje, "Reservé 5 de 7 · faltan 2 camas")
        self.assertEqual(len(self._reservas(derivacion)), 5)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(resultado.integrantes), 7, "las filas son las declaradas, no las camas")

    def test_sin_ninguna_cama_libre_no_se_acepta(self):
        caso, derivacion = self._derivado()
        self._ocupar(self.club, 9)

        with self.assertRaises(ValidationError) as error:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertEqual(error.exception.message_dict["plazas"], [servicio.SIN_PLAZAS_PARA_ACEPTAR])
        self.assertEqual(self._estado(caso), Estado.DERIVADO)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.PENDIENTE)
        self.assertFalse(IntegranteGrupo.objects.exists())

    def test_reserva_hasta_las_plazas_pedidas_aunque_haya_mas_libres(self):
        _caso, derivacion = self._derivado(plazas=3)
        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertEqual((resultado.reservadas, resultado.faltantes), (3, 0))
        self.assertEqual(len(resultado.integrantes), 7)

    def test_una_pendiente_con_el_plazo_cumplido_se_acepta_si_el_cron_no_paso(self):
        """RN-3.3: la familia está en la puerta."""

        caso, derivacion = self._derivado()
        self.reloj.avanzar(hours=12, minutes=10)
        self.assertLess(derivacion.vence_en, self.reloj.ahora)

        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_aceptar_y_vencer_se_excluyen(self):
        """Los dos bloquean caso → derivación y deciden con la fila bloqueada: gana el primero."""

        caso, derivacion = self._derivado()
        self.reloj.avanzar(hours=13)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertIsNone(mesa.vencer_derivacion(derivacion), "el cron venció una derivación aceptada")
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

        otro, otra = self._derivado(dni="30222333")
        self.reloj.avanzar(hours=13)
        self.assertIsNotNone(mesa.vencer_derivacion(otra))
        with self.assertRaises(EstadoCambio) as cambio:
            servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)
        self.assertIn("La derivación venció", cambio.exception.mensaje)
        self.assertEqual(cambio.exception.estado_actual, Estado.EN_GESTION)
        self.assertFalse(ReservaPlaza.objects.filter(derivacion=otra).exists())

    def test_la_segunda_aceptacion_recibe_el_aviso_y_no_reserva_de_nuevo(self):
        caso, derivacion = self._derivado()
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        with self.assertRaises(EstadoCambio) as cambio:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertIn("ya la aceptó", cambio.exception.mensaje)
        self.assertEqual(cambio.exception.estado_actual, Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), 7)

    def test_una_derivacion_cancelada_por_la_mesa_no_se_acepta(self):
        _caso, derivacion = self._derivado()
        mesa.cancelar_derivacion(derivacion, self.operador, "Error de carga")
        with self.assertRaises(EstadoCambio) as cambio:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertIn("canceló", cambio.exception.mensaje)

    def test_elige_el_sector_con_mas_camas_libres_y_por_codigo_natural(self):
        """RN-3.4: la familia queda junta; `B-9` va antes que `B-10`."""

        ala = Sector.objects.create(dispositivo=self.escuela, nombre="Ala B", capacidad=12)
        Plaza.objects.bulk_create([Plaza(sector=ala, codigo=f"B-{n}") for n in range(1, 13)])
        _caso, derivacion = self._derivado(dispositivo=self.escuela, plazas=7)

        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_escuela)

        codigos = [(r.plaza.sector.nombre, r.plaza.codigo) for r in self._reservas(derivacion)]
        self.assertEqual({sector for sector, _codigo in codigos}, {"Ala B"})
        self.assertEqual(sorted(codigo for _s, codigo in codigos), sorted(f"B-{n}" for n in range(1, 8)))

    def test_sin_turno_no_hay_novedad_de_bitacora_y_no_es_un_error(self):
        """Plan R8: es el comportamiento de Dispositivos. La traza del caso queda igual."""

        caso, derivacion = self._derivado()
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertFalse(EntradaBitacora.objects.exists())
        self.assertEqual(self._trazas(caso)[-1].accion, Accion.DERIVACION_ACEPTADA)

    def test_quien_admite_en_otro_dispositivo_no_acepta_esta_derivacion(self):
        """**Mutación nueva del PR 7:** `admitir` en A no acepta una derivación de B aunque conozca el id.

        Visto en rojo sacando ``_exigir_alcance`` de ``_dispositivo_de``: ``rechazar_derivacion``
        —que no pasa por ``estadias``— deja que la guardia de la Escuela rechace la derivación
        del Club y este test falla en el segundo ``assertRaises`` («PermissionDenied not
        raised»). A ``aceptar_derivacion`` la sigue frenando, ya con los candados tomados, la
        guarda de ``reservar_plazas_de_derivacion`` (PR 6): son dos guardas y esta es la primera.
        """

        caso, derivacion = self._derivado()

        with self.assertRaises(PermissionDenied):
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_escuela)
        with self.assertRaises(PermissionDenied):
            servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia_escuela, motivo="SIN_PLAZAS")

        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._estado(caso), Estado.DERIVADO)
        self.assertFalse(ReservaPlaza.objects.exists())
        self.assertEqual(len(self._trazas(caso)), 3, "quedó una traza de algo que no pasó")

    def test_la_mesa_no_acepta_derivaciones(self):
        _caso, derivacion = self._derivado()
        with self.assertRaises(PermissionDenied):
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.supervisor)


class RechazarDerivacionTests(BaseAlojar):
    def test_rechazar_devuelve_el_caso_a_quien_lo_tenia(self):
        caso, derivacion = self._derivado()

        rechazada = servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia, motivo="SIN_PLAZAS")

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.EN_GESTION)
        self.assertEqual(fila["tomado_por_id"], self.operador.pk)
        self.assertEqual(rechazada.estado, Derivacion.Estado.RECHAZADA)
        self.assertEqual(rechazada.motivo, "Sin plazas")
        self.assertIsNone(rechazada.clave_vigente)
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.DERIVACION_RECHAZADA)
        self.assertEqual(traza.detalle, "Rechazado por Club Sarmiento: sin plazas")
        # El caso se puede volver a derivar.
        mesa.derivar_caso(CasoEmergencia.objects.get(pk=caso.pk), self.operador, self.escuela, 5, True)

    def test_el_motivo_es_del_catalogo_y_otro_pide_observacion(self):
        _caso, derivacion = self._derivado()
        for motivo, observacion, campo in (
            ("", "", "motivo"),
            ("PORQUE_SI", "", "motivo"),
            ("OTRO", " ", "observacion"),
        ):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError) as error:
                servicio.rechazar_derivacion(
                    derivacion=derivacion, usuario=self.guardia, motivo=motivo, observacion=observacion
                )
            self.assertEqual(set(error.exception.error_dict), {campo})

        rechazada = servicio.rechazar_derivacion(
            derivacion=derivacion, usuario=self.guardia, motivo="OTRO", observacion="El edificio está sin luz"
        )
        self.assertEqual(rechazada.observacion, "El edificio está sin luz")

    def test_una_derivacion_ya_aceptada_no_se_rechaza(self):
        _caso, derivacion = self._aceptado()
        with self.assertRaises(EstadoCambio):
            servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertEqual(len(self._reservas(derivacion)), 7)


# ---------------------------------------------------------------------------
# Confirmar a una persona (RN-3.5 a 3.7)
# ---------------------------------------------------------------------------


class ConfirmarIntegranteTests(BaseAlojar):
    def test_confirmar_a_otra_persona_consume_la_reserva_del_responsable(self):
        """RN-3.5, por la vía del PR 6: la reserva nació a nombre del responsable."""

        self._turno(self.club)
        caso, derivacion = self._aceptado()
        reserva = self._reservas(derivacion)[0]

        integrante = self._confirmar(caso, 2, "45000111", plaza=reserva.plaza)

        juan = Ciudadano.objects.get(dni="45000111")
        estadia = Estadia.objects.get(ciudadano=juan)
        self.assertTrue(estadia.activa)
        self.assertEqual((estadia.dispositivo, estadia.plaza), (self.club, reserva.plaza))
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.CONSUMIDA)
        self.assertEqual(reserva.ciudadano, juan)
        self.assertEqual(len(self._reservas(derivacion)), 6)
        integrante.refresh_from_db()
        self.assertEqual((integrante.ciudadano, integrante.estadia), (juan, estadia))
        self.assertEqual(integrante.confirmada_en, T0)
        self.assertEqual(integrante.parentesco, "HIJO")
        self.assertFalse(integrante.ficha_completa)
        self.assertEqual(integrante.ficha["version"], 1)
        self.assertEqual(integrante.ficha["datos_personales"]["dni"], "45000111")
        # El vínculo, visto desde el responsable.
        vinculo = VinculoFamiliar.objects.get()
        self.assertEqual(
            (vinculo.ciudadano_principal_id, vinculo.ciudadano_vinculado, vinculo.tipo_vinculo),
            (caso.grupo.responsable_id, juan, TipoVinculo.HIJO),
        )
        self.assertTrue(vinculo.convive)
        # HU-3.3: el INGRESO automático de la bitácora lo deja `ingresar_persona`.
        self.assertTrue(
            EntradaBitacora.objects.filter(
                dispositivo=self.club, tipo="INGRESO", origen=EntradaBitacora.Origen.AUTOMATICA
            ).exists()
        )
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.INTEGRANTE_CONFIRMADO)
        self.assertIn("1 de 7", traza.detalle)
        self.assertNotIn("Pérez", traza.detalle, "la traza nombra a la familia")
        self.assertEqual((integrante.confirmadas, integrante.total_declarado), (1, 7))

    def test_confirmar_al_responsable_no_crea_vinculo_y_completa_su_legajo(self):
        """El responsable se dio de alta en la etapa 1 sin sexo: lo completa esta ficha."""

        caso, derivacion = self._aceptado()
        responsable = caso.grupo.responsable
        self.assertEqual(responsable.genero, "")

        # Sin nombre ni apellido en la ficha: con la persona en el legajo, el DNI alcanza.
        ficha = ficha_minima("30111222", parentesco={"parentesco": "JEFE"}, datos_personales={"sexo": "F"})
        del ficha["datos_personales"]["nombre"], ficha["datos_personales"]["apellido"]
        integrante = servicio.confirmar_integrante(
            caso=caso, orden=1, usuario=self.guardia, ficha=ficha, plaza=self._reservas(derivacion)[0].plaza
        )

        self.assertEqual(integrante.ciudadano, responsable)
        self.assertFalse(VinculoFamiliar.objects.exists())
        responsable.refresh_from_db()
        self.assertEqual(responsable.genero, "F")
        self.assertEqual(responsable.fecha_nacimiento, date(2006, 3, 10))
        self.assertEqual((responsable.nombre, responsable.apellido), ("Rosa", "Benítez"), "pisó el legajo")
        self.assertEqual(integrante.ficha["datos_personales"]["nombre"], "Rosa")
        self.assertEqual(Ciudadano.objects.filter(dni="30111222").count(), 1)

    def test_sin_el_minimo_no_se_crea_nada(self):
        """HU-3.3: «Falta: avisos de salud» y no queda ni la persona."""

        caso, derivacion = self._aceptado()
        ficha = ficha_minima("45000111")
        del ficha["avisos_salud"]
        personas = Ciudadano.objects.count()

        with self.assertRaises(ValidationError) as error:
            servicio.confirmar_integrante(
                caso=caso, orden=2, usuario=self.guardia, ficha=ficha, plaza=self._reservas(derivacion)[0].plaza
            )

        self.assertIn("Falta: avisos de salud", error.exception.message_dict["embarazo"][0])
        self.assertEqual(Ciudadano.objects.count(), personas)
        self.assertFalse(Estadia.objects.exists())
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertFalse(IntegranteGrupo.objects.filter(confirmada_en__isnull=False).exists())

    def test_un_menor_sin_adulto_responsable_no_se_confirma(self):
        caso, _derivacion = self._aceptado()
        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 3, "55000111", datos_personales={"fecha_nacimiento": "2015-05-05"})
        self.assertEqual(set(error.exception.error_dict), {"adulto_responsable"})

        integrante = self._confirmar(
            caso,
            3,
            "55000111",
            datos_personales={"fecha_nacimiento": "2015-05-05"},
            observaciones={"adulto_responsable": "Rosa Benítez"},
        )
        self.assertTrue(integrante.confirmada)

    def test_quien_no_sabe_su_numero_de_dni_no_se_confirma_con_cama(self):
        caso, _derivacion = self._aceptado()
        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 2, "")
        self.assertEqual(error.exception.message_dict["dni"], [servicio.SIN_NUMERO_DE_DOCUMENTO])
        self.assertFalse(Estadia.objects.exists())

    def test_perdio_el_documento_pero_sabe_el_numero_queda_marcado_solo_en_el_alta(self):
        """Hallazgo H5: ``dni_fisico = NO_TIENE`` en quien se da de alta acá; al legajo previo no se le toca."""

        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000111", plaza=reservas[0].plaza, datos_personales={"documento_extraviado": True})
        previa = Ciudadano.objects.create(dni="45000222", nombre="Lía", apellido="Sosa", dni_fisico="TIENE")
        self._confirmar(caso, 3, "45000222", plaza=reservas[1].plaza, datos_personales={"documento_extraviado": True})

        self.assertEqual(Ciudadano.objects.get(dni="45000111").dni_fisico, Ciudadano.DniFisico.NO_TIENE)
        previa.refresh_from_db()
        self.assertEqual(previa.dni_fisico, "TIENE")

    def test_si_el_ingreso_falla_no_queda_nada_huerfano(self):
        """**RN-3.7, atomicidad.** Ni legajo, ni vínculo, ni fila confirmada, y la reserva como estaba."""

        caso, derivacion = self._aceptado()
        reserva = self._reservas(derivacion)[0]
        personas, trazas = Ciudadano.objects.count(), len(self._trazas(caso))

        with mock.patch(
            "programas.services.reservas_derivacion.ingresar_persona",
            side_effect=ValidationError({"fecha_ingreso": "El ingreso no puede ser futuro."}),
        ):
            with self.assertRaises(ValidationError):
                self._confirmar(caso, 2, "45000111", plaza=reserva.plaza)

        self.assertEqual(Ciudadano.objects.count(), personas, "quedó un legajo huérfano")
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())
        self.assertFalse(VinculoFamiliar.objects.exists())
        self.assertFalse(Estadia.objects.exists())
        self.assertFalse(IntegranteGrupo.objects.filter(confirmada_en__isnull=False).exists())
        self.assertFalse(IntegranteGrupo.objects.filter(ciudadano__isnull=False).exists())
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.VIGENTE)
        self.assertEqual(reserva.ciudadano_id, caso.grupo.responsable_id, "la reserva quedó a nombre de quien no entró")
        self.assertEqual(len(self._trazas(caso)), trazas)

    def test_si_falla_despues_del_ingreso_tampoco_queda_la_estadia(self):
        """El otro lado de la atomicidad: lo que se deshace incluye el ingreso ya hecho."""

        caso, derivacion = self._aceptado()
        with mock.patch.object(
            servicio_confirmacion, "_vincular_con_el_responsable", side_effect=RuntimeError("se cayó")
        ):
            with self.assertRaises(RuntimeError):
                self._confirmar(caso, 2, "45000111")

        self.assertFalse(Estadia.objects.exists())
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())
        self.assertEqual(len(self._reservas(derivacion)), 7)

    def test_una_persona_alojada_en_otro_dispositivo_no_se_confirma_y_no_se_dice_donde(self):
        """HU-3.3, RU-9: la guardia del Club no opera la Escuela."""

        caso, derivacion = self._aceptado()
        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        with self.assertRaises(servicio.PersonaYaAlojada) as error:
            self._confirmar(caso, 2, alojada.dni)

        mensaje = error.exception.message_dict["dni"][0]
        self.assertIn("figura alojado en otro dispositivo de la red", mensaje)
        self.assertIn("cerrá el ingreso con diferencia", mensaje)
        self.assertNotIn("Escuela", mensaje)
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertFalse(IntegranteGrupo.objects.filter(confirmada_en__isnull=False).exists())

    def test_quien_opera_el_otro_dispositivo_si_lee_donde_esta(self):
        de_los_dos = self._guardia("guardia_doble", self.club, self.escuela)
        caso, _derivacion = self._aceptado()
        self._ocupar(self.escuela, 1)
        alojada = Estadia.objects.get().ciudadano

        with self.assertRaises(servicio.PersonaYaAlojada) as error:
            self._confirmar(caso, 2, alojada.dni, usuario=de_los_dos)

        self.assertIn("figura alojado en Escuela 12 desde el 11/11", error.exception.message_dict["dni"][0])

    def test_el_mismo_dni_dos_veces_en_la_familia_dice_donde_esta(self):
        """03 §10: «Ya confirmaste a Juan Pérez en la cama B-12»."""

        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000111", plaza=reservas[0].plaza)

        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 3, "45.000.111", plaza=reservas[1].plaza)

        self.assertEqual(
            error.exception.message_dict["dni"],
            [f"Ya confirmaste a Juan Pérez en la cama {reservas[0].plaza.codigo} (General)."],
        )
        self.assertEqual(Estadia.objects.count(), 1)

    def test_una_cama_libre_sin_reserva_devuelve_una_de_las_guardadas(self):
        """La regla de la reserva sobrante: la derivación no retiene más camas que personas faltan.

        7 declaradas y 7 reservadas: quien entra en una cama libre devuelve **una** reserva
        —la de la plaza con id más alto—, y quedan 6 para las 6 personas que faltan.
        """

        caso, derivacion = self._aceptado()
        reservadas = [reserva.plaza_id for reserva in self._reservas(derivacion)]
        libre = self._cama_libre()
        self.assertNotIn(libre.pk, reservadas)

        integrante = self._confirmar(caso, 2, "45000111", plaza=libre)

        self.assertEqual(integrante.estadia.plaza, libre)
        self.assertTrue(integrante.reserva_liberada)
        vigentes = [reserva.plaza_id for reserva in self._reservas(derivacion)]
        self.assertEqual(vigentes, reservadas[:-1])
        liberada = ReservaPlaza.objects.get(derivacion=derivacion, estado=ReservaPlaza.Estado.LIBERADA)
        self.assertEqual(liberada.plaza_id, max(reservadas))
        self.assertEqual(liberada.motivo, servicio.MOTIVO_RESERVA_SOBRANTE)

    def test_si_todavia_hacen_falta_todas_las_reservas_no_se_libera_ninguna(self):
        """Reservó 5 de 7: una persona en una cama que se liberó después no devuelve nada."""

        caso, derivacion = self._derivado()
        self._ocupar(self.club, 4)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        ocupada = Estadia.objects.filter(dispositivo=self.club).first()
        egresar_persona(estadia=ocupada, usuario=self.guardia, motivo_egreso=self.motivo_alta, destino="Domicilio")

        integrante = self._confirmar(caso, 2, "45000111", plaza=ocupada.plaza)

        self.assertFalse(integrante.reserva_liberada)
        self.assertEqual(len(self._reservas(derivacion)), 5)

    def test_una_cama_reservada_para_otra_familia_no_se_puede_elegir(self):
        caso, _derivacion = self._aceptado(plazas=4)
        _otro, otra = self._derivado(dni="30222333", plazas=2)
        servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)
        ajena = self._reservas(otra)[0].plaza

        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 2, "45000111", plaza=ajena)

        self.assertIn("está reservada para otra persona · elegí otra", error.exception.message_dict["plaza"][0])
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())

    def _con_reserva_comun(self, dni, plaza, usuario):
        """Una persona con legajo y una reserva **común** (no de derivación) abierta en ``plaza``."""

        persona = Ciudadano.objects.create(dni=dni, nombre="Juan", apellido="Pérez")
        return persona, reservar_plaza(plaza=plaza, ciudadano=persona, usuario=usuario)

    def test_en_una_cama_libre_se_cierra_su_reserva_comun_de_otro_dispositivo(self):
        """D2 del Cambio 409: quien entra en una cama libre no sigue bloqueando la que tenía en otro lado.

        Visto en rojo: sin leer ``_reservas_abiertas_de`` en la rama de la cama libre, la
        persona quedaba alojada en el Club y su reserva de la Escuela seguía ``VIGENTE``.
        """

        caso, _derivacion = self._aceptado()
        escuela = Plaza.objects.filter(sector__dispositivo=self.escuela).order_by("pk").first()
        _persona, comun = self._con_reserva_comun("45000111", escuela, self.guardia_escuela)
        libre = self._cama_libre()

        integrante = self._confirmar(caso, 2, "45000111", plaza=libre)

        self.assertEqual(integrante.estadia.plaza, libre)
        comun.refresh_from_db()
        self.assertEqual(comun.estado, ReservaPlaza.Estado.LIBERADA, "la D2 del Cambio 409 no se aplicó")
        self.assertEqual(comun.motivo, MOTIVO_RESERVA_CERRADA_POR_INGRESO)

    def test_su_reserva_comun_en_la_cama_elegida_se_consume(self):
        """Una cama guardada para **la misma persona** no es «de otra persona»: el ingreso la consume.

        Visto en rojo: se rechazaba con «está reservada para otra persona».
        """

        caso, _derivacion = self._aceptado()
        libre = self._cama_libre()
        _persona, comun = self._con_reserva_comun("45000111", libre, self.guardia)

        integrante = self._confirmar(caso, 2, "45000111", plaza=libre)

        self.assertEqual(integrante.estadia.plaza, libre)
        comun.refresh_from_db()
        self.assertEqual(comun.estado, ReservaPlaza.Estado.CONSUMIDA)

    def test_una_reserva_comun_nueva_mientras_se_confirma_frena_el_ingreso(self):
        """Con la persona bloqueada se vuelve a mirar: una reserva que apareció en el medio frena."""

        caso, _derivacion = self._aceptado()
        Ciudadano.objects.create(dni="45000111", nombre="Juan", apellido="Pérez")
        escuela = Plaza.objects.filter(sector__dispositivo=self.escuela).order_by("pk").first()
        original = servicio_ingreso._bloquear_persona

        def bloquear_y_que_aparezca(ciudadano):
            original(ciudadano)
            reservar_plaza(plaza=escuela, ciudadano=ciudadano, usuario=self.guardia_escuela)

        with mock.patch.object(servicio_confirmacion, "_bloquear_persona", side_effect=bloquear_y_que_aparezca):
            with self.assertRaises(ValidationError) as error:
                self._confirmar(caso, 2, "45000111", plaza=self._cama_libre())

        self.assertEqual(error.exception.messages, [RESERVA_NUEVA_DURANTE_EL_INGRESO])
        self.assertFalse(Estadia.objects.exists())

    def test_una_cama_ocupada_se_rechaza_sin_pedir_su_candado(self):
        """Es lo que impide el ciclo con un egreso en curso (docstring del módulo)."""

        caso, _derivacion = self._aceptado(plazas=4)
        self._ocupar(self.club, 9)  # ocupa también las que no tienen reserva: `_ocupar` no mira
        ocupada = Estadia.objects.filter(dispositivo=self.club).order_by("-plaza_id").first().plaza

        with orden_de_candados(plaza=Plaza.objects, persona=Ciudadano.objects) as orden:
            with self.assertRaises(ValidationError) as error:
                self._confirmar(caso, 2, "45000111", plaza=ocupada)

        self.assertIn("ya está ocupada · elegí otra", error.exception.message_dict["plaza"][0])
        self.assertEqual(orden, [], "pidió un candado antes de rechazar la cama ocupada")

    def test_la_cama_reservada_que_quedo_fuera_de_servicio_se_rechaza_y_se_elige_otra(self):
        """03 §10: «La cama B-12 está fuera de servicio · elegí otra»."""

        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        rota = reservas[0].plaza
        # Para sacarla de servicio hay que soltarla primero (regla 1 de `estadias`): así llega a este estado.
        liberar_reserva(reserva=reservas[0], usuario=self.guardia, motivo="Se rompió el elástico")
        Plaza.objects.filter(pk=rota.pk).update(estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota")

        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 2, "45000111", plaza=rota)
        self.assertEqual(
            error.exception.message_dict["plaza"],
            [f"La cama {rota.codigo} (General) está fuera de servicio · elegí otra."],
        )
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())

        integrante = self._confirmar(caso, 2, "45000111", plaza=reservas[1].plaza)
        self.assertTrue(integrante.confirmada)

    def test_una_cama_de_otro_dispositivo_o_inexistente_da_el_mismo_error(self):
        caso, _derivacion = self._aceptado()
        ajena = Plaza.objects.filter(sector__dispositivo=self.escuela).first()
        for plaza in (ajena, ajena.pk, 999_999, "abc"):
            with self.subTest(plaza=plaza), self.assertRaises(ValidationError) as error:
                self._confirmar(caso, 2, "45000111", plaza=plaza)
            self.assertEqual(error.exception.message_dict["plaza"], [servicio.ELEGI_UNA_CAMA])

    def test_una_fila_ya_confirmada_no_se_confirma_de_nuevo(self):
        """03 §10: dos guardias confirman a la misma persona; la segunda recarga (409)."""

        caso, derivacion = self._aceptado()
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000111", plaza=reservas[0].plaza)

        with self.assertRaises(EstadoCambio) as cambio:
            self._confirmar(caso, 2, "45000111", plaza=reservas[1].plaza)

        self.assertEqual(cambio.exception.estado_actual, Estado.INGRESO_EN_CURSO)
        self.assertEqual(Estadia.objects.count(), 1)
        self.assertEqual(len(self._reservas(derivacion)), 6)

    def test_reenviar_la_misma_confirmacion_devuelve_la_misma_fila(self):
        """RU-16: el mismo ``uuid_cliente`` no duplica ni falla."""

        caso, derivacion = self._aceptado()
        envio = uuid.uuid4()
        argumentos = {
            "caso": caso,
            "orden": 2,
            "usuario": self.guardia,
            "ficha": ficha_minima("45000111"),
            "plaza": self._reservas(derivacion)[0].plaza,
            "uuid_cliente": envio,
        }
        primera = servicio.confirmar_integrante(**argumentos)
        segunda = servicio.confirmar_integrante(**argumentos)

        self.assertFalse(primera.ya_estaba)
        self.assertTrue(segunda.ya_estaba)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(Estadia.objects.count(), 1)

    def test_una_fila_que_no_es_de_la_familia_es_un_error(self):
        caso, _derivacion = self._aceptado()
        with self.assertRaises(ValidationError) as error:
            self._confirmar(caso, 99, "45000111")
        self.assertEqual(set(error.exception.error_dict), {"orden"})

    def test_sin_alcance_sobre_el_dispositivo_del_caso_no_se_confirma(self):
        caso, derivacion = self._aceptado()
        for usuario in (self.guardia_escuela, self.operador, self.supervisor):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                self._confirmar(caso, 2, "45000111", usuario=usuario)
        self.assertFalse(Estadia.objects.exists())
        self.assertFalse(Ciudadano.objects.filter(dni="45000111").exists())

    def test_un_caso_que_todavia_no_se_acepto_no_admite_confirmaciones(self):
        caso, _derivacion = self._derivado()
        with self.assertRaises(EstadoCambio):
            servicio.confirmar_integrante(
                caso=caso, orden=1, usuario=self.guardia, ficha=ficha_minima("45000111"), plaza=self._cama_libre()
            )

    def test_un_caso_sin_ninguna_derivacion_no_dice_que_existe(self):
        caso = self._caso_tomado()
        with self.assertRaises(PermissionDenied):
            servicio.confirmar_integrante(
                caso=caso, orden=1, usuario=self.guardia, ficha=ficha_minima("45000111"), plaza=self._cama_libre()
            )


class CompletarFichaTests(BaseAlojar):
    def test_completar_las_secciones_que_faltan_deja_la_ficha_completa(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")

        parcial = servicio.completar_ficha(
            caso=caso, orden=2, usuario=self.guardia, ficha={"educacion": {"nivel_educativo": "SECUNDARIO"}}
        )
        self.assertFalse(parcial.ficha_completa)

        completa = servicio.completar_ficha(
            caso=caso,
            orden=2,
            usuario=self.guardia,
            ficha={
                "vacunacion": {"esquema_al_dia": True},
                "salud": {"sin_datos": True},
                "trabajo": {"ocupacion": "Estudiante"},
                "observaciones": {"mascotas": False},
                # La identidad no se cambia después de confirmar: esto se ignora.
                "datos_personales": {"dni": "11111111", "nombre": "Otro"},
            },
        )

        completa.refresh_from_db()
        self.assertTrue(completa.ficha_completa)
        self.assertEqual(completa.ficha["educacion"], {"nivel_educativo": "SECUNDARIO"})
        self.assertEqual(completa.ficha["datos_personales"]["dni"], "45000111")
        self.assertEqual(self._trazas(caso)[-1].accion, Accion.FICHA_ACTUALIZADA)

    def test_tambien_con_la_familia_ya_alojada(self):
        caso, _derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_m=0)
        self._confirmar(caso, 1, "30111222", parentesco={"parentesco": "JEFE"})
        servicio.alojar_familia(caso=caso, usuario=self.guardia)

        integrante = servicio.completar_ficha(
            caso=caso, orden=1, usuario=self.guardia, ficha={"trabajo": {"sin_datos": True}}
        )
        self.assertEqual(integrante.ficha["trabajo"], {"sin_datos": True})

    def test_una_persona_sin_confirmar_no_tiene_ficha_que_completar(self):
        caso, _derivacion = self._aceptado()
        with self.assertRaises(ValidationError):
            servicio.completar_ficha(caso=caso, orden=2, usuario=self.guardia, ficha={"trabajo": {"sin_datos": True}})

    def test_a_un_menor_no_se_le_puede_borrar_el_adulto_responsable(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(
            caso,
            3,
            "55000111",
            datos_personales={"fecha_nacimiento": "2015-05-05"},
            observaciones={"adulto_responsable": "Rosa Benítez"},
        )
        with self.assertRaises(ValidationError) as error:
            servicio.completar_ficha(
                caso=caso, orden=3, usuario=self.guardia, ficha={"observaciones": {"mascotas": True}}
            )
        self.assertEqual(set(error.exception.error_dict), {"adulto_responsable"})

    def test_sin_alcance_no_se_completa(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")
        with self.assertRaises(PermissionDenied):
            servicio.completar_ficha(
                caso=caso, orden=2, usuario=self.guardia_escuela, ficha={"trabajo": {"sin_datos": True}}
            )


# ---------------------------------------------------------------------------
# Agregar (RN-3.8), alojar, diferencia (RN-3.9) y cancelar
# ---------------------------------------------------------------------------


class AgregarIntegranteTests(BaseAlojar):
    def test_agregar_suma_una_fila_y_la_cama_sale_de_las_libres(self):
        """HU-3.5: 7 declaradas → 8; la persona nueva no tiene reserva."""

        caso, derivacion = self._aceptado()

        nuevo = servicio.agregar_integrante(caso=caso, usuario=self.guardia)

        self.assertEqual((nuevo.orden, nuevo.total_declarado), (8, 8))
        caso.grupo.refresh_from_db()
        self.assertEqual(caso.grupo.total_declarado, 8)
        self.assertEqual(caso.grupo.suma_de_cantidades(), 7, "lo declarado al relevar no se toca")
        self.assertEqual(len(self._reservas(derivacion)), 7)
        self.assertEqual(self._trazas(caso)[-1].detalle, "Agregada persona por el dispositivo · 8 sobre 7 declaradas")
        # Las 8 personas entran: 7 por su reserva y la octava por una cama libre, sin devolver ninguna.
        reservas = self._reservas(derivacion)
        for orden, reserva in enumerate(reservas, start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        octava = self._confirmar(caso, 8, "45000999", plaza=self._cama_libre())
        self.assertFalse(octava.reserva_liberada)
        self.assertEqual((octava.confirmadas, octava.total_declarado), (8, 8))

    def test_sin_cama_libre_la_fila_existe_pero_confirmar_avisa(self):
        """HU-3.5: «Sin cama libre · liberá una o cerrá con diferencia»."""

        caso, derivacion = self._aceptado()
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        self._ocupar_libres(self.club)
        servicio.agregar_integrante(caso=caso, usuario=self.guardia)

        with self.assertRaises(ValidationError) as error:
            servicio.confirmar_integrante(
                caso=caso, orden=8, usuario=self.guardia, ficha=ficha_minima("45000999"), plaza=None
            )

        self.assertEqual(error.exception.message_dict["plaza"], [servicio.SIN_CAMA_LIBRE])

    def _ocupar_libres(self, dispositivo):
        for plaza in selectores.camas_libres(dispositivo):
            persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Alojada")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=dispositivo,
                plaza=plaza,
                fecha_ingreso=T0 - timedelta(days=1),
                clave_alojamiento=Estadia.clave_para(persona),
            )

    def test_reenviar_el_mismo_alta_no_suma_dos_personas(self):
        caso, _derivacion = self._aceptado()
        envio = uuid.uuid4()

        primera = servicio.agregar_integrante(caso=caso, usuario=self.guardia, uuid_cliente=envio)
        self._confirmar(caso, 8, "45000999", plaza=self._cama_libre())
        segunda = servicio.agregar_integrante(caso=caso, usuario=self.guardia, uuid_cliente=envio)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertTrue(segunda.ya_estaba)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), 8)

    def test_solo_con_el_ingreso_en_curso_y_con_alcance(self):
        caso, _derivacion = self._derivado()
        with self.assertRaises(EstadoCambio):
            servicio.agregar_integrante(caso=caso, usuario=self.guardia)
        with self.assertRaises(PermissionDenied):
            servicio.agregar_integrante(caso=caso, usuario=self.guardia_escuela)


class CerrarElIngresoTests(BaseAlojar):
    def _familia_de(self, personas, **kwargs):
        """Un ingreso aceptado de ``personas`` adultos (1 a 4)."""

        cantidades = {"menores_f": 0, "menores_m": 0, "adultos_f": 1, "adultos_m": personas - 1}
        return self._aceptado(**cantidades, **kwargs)

    def _confirmar_a_todos(self, caso, derivacion):
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

    def test_familia_alojada_con_todas_confirmadas(self):
        self._turno(self.club)
        caso, derivacion = self._familia_de(3)
        self._confirmar_a_todos(caso, derivacion)
        sector = Sector.objects.get(dispositivo=self.club)

        alojado = servicio.alojar_familia(
            caso=caso,
            usuario=self.guardia,
            sector=sector,
            aula="Aula 3",
            tarjeta_entregada=True,
            tarjeta_numero="0042",
            encargado="",
        )

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.ALOJADO)
        self.assertEqual(fila["alojado_en"], T0)
        self.assertEqual(fila["total_alojado"], 3)
        self.assertEqual(
            fila["situacion"]["alojamiento"],
            {
                "sector_id": sector.pk,
                "sector": "General",
                "aula": "Aula 3",
                "tarjeta_entregada": True,
                "tarjeta_numero": "0042",
                "encargado": "guardia_club",
            },
        )
        self.assertFalse(alojado.ingreso_parcial)
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.ALOJADO)
        self.assertIn("3 de 3", traza.detalle)
        self.assertIn("Aula 3", traza.detalle)
        self.assertTrue(
            EntradaBitacora.objects.filter(tipo="GENERAL", texto__contains="familia alojada 3 de 3").exists()
        )

    def test_con_una_sola_sin_confirmar_no_se_aloja(self):
        caso, derivacion = self._familia_de(3)
        self._confirmar(caso, 1, "45000101")

        with self.assertRaises(ValidationError) as error:
            servicio.alojar_familia(caso=caso, usuario=self.guardia)

        self.assertIn("Falta confirmar a 2 personas", error.exception.messages[0])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_la_tarjeta_entregada_pide_su_numero_y_el_sector_es_del_dispositivo(self):
        caso, derivacion = self._familia_de(1)
        self._confirmar_a_todos(caso, derivacion)
        ajeno = Sector.objects.get(dispositivo=self.escuela)

        with self.assertRaises(ValidationError) as error:
            servicio.alojar_familia(caso=caso, usuario=self.guardia, tarjeta_entregada=True)
        self.assertEqual(set(error.exception.error_dict), {"tarjeta_numero"})
        with self.assertRaises(ValidationError) as error:
            servicio.alojar_familia(caso=caso, usuario=self.guardia, sector=ajeno.pk)
        self.assertEqual(set(error.exception.error_dict), {"sector"})
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_al_alojar_se_sueltan_las_camas_que_la_mesa_pidio_de_mas(self):
        caso, derivacion = self._familia_de(2, plazas=4)
        for orden, reserva in enumerate(self._reservas(derivacion)[:2], start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

        alojado = servicio.alojar_familia(caso=caso, usuario=self.guardia)

        self.assertEqual(alojado.reservas_liberadas, 2)
        self.assertEqual(self._reservas(derivacion), [])

    def test_cerrar_con_diferencia_aloja_a_las_que_llegaron_y_suelta_el_resto(self):
        """HU-3.4: 5 de 7."""

        self._turno(self.club)
        caso, derivacion = self._aceptado()
        for orden, reserva in enumerate(self._reservas(derivacion)[:5], start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

        cerrado = servicio.cerrar_con_diferencia(
            caso=caso,
            usuario=self.guardia,
            motivo="OTRO",
            observacion="Uno quedó con familiares, otro derivado a salud",
        )

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.ALOJADO)
        self.assertEqual(fila["total_alojado"], 5)
        self.assertEqual(fila["alojado_en"], T0)
        self.assertTrue(cerrado.ingreso_parcial)
        self.assertEqual(cerrado.reservas_liberadas, 2)
        self.assertEqual(self._reservas(derivacion), [])
        self.assertEqual(len(self._reservas(derivacion, ReservaPlaza.Estado.LIBERADA)), 2)
        self.assertEqual(len(self._reservas(derivacion, ReservaPlaza.Estado.CONSUMIDA)), 5)
        self.assertEqual(
            fila["situacion"]["diferencia"],
            {
                "motivo": "OTRO",
                "motivo_texto": "Otro",
                "observacion": "Uno quedó con familiares, otro derivado a salud",
                "confirmadas": 5,
                "declaradas": 7,
            },
        )
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.ALOJADO_CON_DIFERENCIA)
        self.assertIn("5 de 7", traza.detalle)
        self.assertIn("otro derivado a salud", traza.detalle)
        entrada = EntradaBitacora.objects.filter(tipo="GENERAL").order_by("-id").first()
        self.assertIn("ingreso cerrado con diferencia 5 de 7 · otro", entrada.texto)
        self.assertNotIn("familiares", entrada.texto, "la observación libre no va a la bitácora")

    def test_el_responsable_que_no_llega_queda_sin_confirmar(self):
        """03 §10: se confirma a los demás y se cierra con «No llegó al centro»."""

        caso, derivacion = self._familia_de(3)
        reservas = self._reservas(derivacion)
        self._confirmar(caso, 2, "45000102", plaza=reservas[0].plaza)
        self._confirmar(caso, 3, "45000103", plaza=reservas[1].plaza)

        servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")

        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        self.assertFalse(IntegranteGrupo.objects.get(grupo=caso.grupo, orden=1).confirmada)
        self.assertFalse(Estadia.objects.filter(ciudadano=caso.grupo.responsable).exists())
        self.assertEqual(VinculoFamiliar.objects.filter(ciudadano_principal=caso.grupo.responsable).count(), 2)

    def test_la_diferencia_pide_motivo_al_menos_una_persona_y_que_falte_alguien(self):
        caso, derivacion = self._familia_de(2)
        for motivo, observacion, campo in (("", "", "motivo"), ("X", "", "motivo"), ("OTRO", "", "observacion")):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError) as error:
                servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo=motivo, observacion=observacion)
            self.assertEqual(set(error.exception.error_dict), {campo})

        with self.assertRaises(ValidationError) as error:
            servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertIn("Todavía no confirmaste a nadie", error.exception.messages[0])

        self._confirmar_a_todos(caso, derivacion)
        with self.assertRaises(ValidationError) as error:
            servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertIn("no hay diferencia", error.exception.messages[0])
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_cancelar_el_ingreso_sin_confirmadas_devuelve_el_caso_a_la_mesa(self):
        caso, derivacion = self._aceptado()

        cancelado = servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo="La familia no llegó")

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.EN_GESTION)
        self.assertEqual(fila["tomado_por_id"], self.operador.pk)
        self.assertEqual(cancelado.reservas_liberadas, 7)
        derivacion.refresh_from_db()
        self.assertEqual((derivacion.estado, derivacion.motivo), (Derivacion.Estado.RECHAZADA, "La familia no llegó"))
        self.assertEqual(self._reservas(derivacion), [])
        self.assertEqual(self._trazas(caso)[-1].accion, Accion.INGRESO_CANCELADO)
        # Las filas quedan, y una segunda aceptación no las duplica.
        nueva = mesa.derivar_caso(CasoEmergencia.objects.get(pk=caso.pk), self.operador, self.club, 7)
        servicio.aceptar_derivacion(derivacion=nueva, usuario=self.guardia)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), 7)

    def test_con_una_persona_confirmada_no_se_cancela(self):
        caso, derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")
        with self.assertRaises(ValidationError) as error:
            servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo="Me equivoqué")
        self.assertIn("cerrá el ingreso con diferencia", error.exception.messages[0])
        with self.assertRaises(ValidationError):
            servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo=" ")
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_ninguno_de_los_cierres_se_hace_sin_alcance(self):
        caso, derivacion = self._familia_de(2)
        self._confirmar(caso, 1, "45000101")
        acciones = (
            lambda: servicio.alojar_familia(caso=caso, usuario=self.guardia_escuela),
            lambda: servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia_escuela, motivo="NO_LLEGO"),
            lambda: servicio.cancelar_ingreso(caso=caso, usuario=self.guardia_escuela, motivo="x"),
        )
        for accion in acciones:
            with self.assertRaises(PermissionDenied):
                accion()
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)
        self.assertEqual(len(self._reservas(derivacion)), 1)


# ---------------------------------------------------------------------------
# Sin derivación: ingreso directo (RN-3.10) y aviso a la mesa
# ---------------------------------------------------------------------------


class IngresoDirectoTests(BaseAlojar):
    def _formulario(self, **cambios):
        datos = self._datos(dni="33444555", nombre="Marta", apellido="Ríos", adultos_f=1, adultos_m=1, menores_f=1)
        del datos["direccion"]
        datos.update(cambios)
        return datos

    def test_el_ingreso_directo_nace_con_el_ingreso_en_curso_sin_pasar_por_la_mesa(self):
        """HU-3.6, RN-3.10."""

        self._turno(self.club)
        resistencia = Localidad.objects.create(nombre="Resistencia")

        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )

        fila = self._fila(caso)
        self.assertEqual(fila["origen"], CasoEmergencia.Origen.DISPOSITIVO)
        self.assertEqual(fila["estado"], Estado.INGRESO_EN_CURSO)
        self.assertIsNone(fila["tomado_por_id"])
        self.assertEqual(fila["relevado_por_id"], self.guardia.pk)
        self.assertEqual(fila["tomado_en"], fila["creado"])
        self.assertEqual(fila["derivado_en"], fila["creado"])
        self.assertEqual(fila["aceptado_en"], fila["creado"])
        self.assertEqual(fila["localidad_id"], resistencia.pk, "no tomó la localidad del dispositivo")
        self.assertEqual(fila["direccion"], "Se presentó en Club Sarmiento")
        derivacion = Derivacion.objects.get(caso=caso)
        self.assertEqual((derivacion.estado, derivacion.dispositivo), (Derivacion.Estado.ACEPTADA, self.club))
        self.assertEqual(derivacion.plazas_pedidas, 3)
        self.assertEqual(len(self._reservas(derivacion)), 3)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), 3)
        self.assertEqual((caso.reservadas, caso.faltantes), (3, 0))
        self.assertTrue(servicio.es_ingreso_directo(caso))
        self.assertEqual([t.accion for t in self._trazas(caso)], [Accion.CREADO, Accion.INGRESO_DIRECTO])
        self.assertTrue(EntradaBitacora.objects.filter(tipo="GENERAL", texto__contains="ingreso directo").exists())

    def test_despues_sigue_el_mismo_camino_hasta_alojado(self):
        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario(menores_f=0)
        )
        derivacion = Derivacion.objects.get(caso=caso)
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)

        servicio.alojar_familia(caso=caso, usuario=self.guardia)

        self.assertEqual(self._estado(caso), Estado.ALOJADO)

    def test_reserva_hasta_donde_alcance(self):
        self._ocupar(self.club, 7)
        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )
        self.assertEqual((caso.reservadas, caso.faltantes), (2, 1))

    def test_sin_camas_libres_no_hay_ingreso_directo_y_no_queda_el_caso(self):
        self._ocupar(self.club, 9)
        with self.assertRaises(ValidationError) as error:
            servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario())
        self.assertEqual(error.exception.message_dict["plazas"], [servicio.SIN_CAMAS_PARA_INGRESO_DIRECTO])
        self.assertFalse(CasoEmergencia.objects.exists())
        self.assertFalse(Ciudadano.objects.filter(dni="33444555").exists())

    def test_exige_alcance_sobre_ese_dispositivo(self):
        for usuario in (self.guardia_escuela, self.operador):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                servicio.ingreso_directo(dispositivo=self.club, usuario=usuario, datos_formulario1=self._formulario())
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_el_formulario_1_se_valida_igual_que_en_la_mesa(self):
        with self.assertRaises(ValidationError) as error:
            servicio.ingreso_directo(
                dispositivo=self.club,
                usuario=self.guardia,
                datos_formulario1=self._formulario(adultos_f=0, adultos_m=0, menores_f=0),
            )
        self.assertIn("total", error.exception.error_dict)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_reenviar_el_mismo_envio_devuelve_el_mismo_caso_aunque_ya_no_haya_camas(self):
        """RU-16: es lo único de la etapa que la app encola sin conexión."""

        envio = uuid.uuid4()
        primero = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario(), uuid_cliente=envio
        )
        self._ocupar_todo()

        segundo = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario(), uuid_cliente=str(envio)
        )

        self.assertEqual(primero.pk, segundo.pk)
        self.assertTrue(segundo.ya_existia)
        self.assertEqual((segundo.reservadas, segundo.faltantes), (primero.reservadas, primero.faltantes))
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        self.assertEqual(ReservaPlaza.objects.filter(derivacion__caso=primero).count(), 3)

    def _ocupar_todo(self):
        for plaza in selectores.camas_libres(self.club):
            persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Alojada")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=self.club,
                plaza=plaza,
                fecha_ingreso=T0 - timedelta(days=1),
                clave_alojamiento=Estadia.clave_para(persona),
            )

    def test_cancelar_un_ingreso_directo_lo_deja_en_la_bandeja(self):
        """No tiene dueño en la mesa: «en gestión» sin operador no lo vería nadie."""

        caso = servicio.ingreso_directo(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )
        servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo="Se fueron")
        self.assertEqual(self._estado(caso), Estado.NUEVO)


class AvisarALaMesaTests(BaseAlojar):
    def _formulario(self):
        return self._datos(dni="33444555", nombre="Marta", apellido="Ríos")

    def test_avisar_crea_un_caso_nuevo_en_la_puerta_del_dispositivo(self):
        """M2-6: no reserva nada; la mesa lo ve en la bandeja."""

        self._ocupar(self.club, 9)  # se usa justo cuando no hay lugar

        caso = servicio.avisar_a_la_mesa(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )

        fila = self._fila(caso)
        self.assertEqual((fila["estado"], fila["origen"]), (Estado.NUEVO, CasoEmergencia.Origen.DISPOSITIVO))
        self.assertEqual(
            fila["situacion"]["en_la_puerta_de"], {"dispositivo_id": self.club.pk, "dispositivo": "Club Sarmiento"}
        )
        self.assertFalse(Derivacion.objects.exists())
        self.assertFalse(ReservaPlaza.objects.exists())
        self.assertFalse(servicio.es_ingreso_directo(caso))
        self.assertEqual(self._trazas(caso)[-1].detalle, "En la puerta de Club Sarmiento · esperando derivación")

    def test_la_mesa_deriva_y_la_guardia_busca_de_nuevo(self):
        """03 §10: llega una persona antes de que la mesa derive."""

        caso = servicio.avisar_a_la_mesa(
            dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._formulario()
        )
        sin_derivar = servicio.buscar_por_dni(dispositivo=self.club, dni="33444555", usuario=self.guardia)
        self.assertEqual(sin_derivar.resultado, servicio.BUSQUEDA_SIN_DERIVACION)

        mesa.derivar_caso(mesa.tomar_caso(caso, self.operador), self.operador, self.club, 2)
        derivada = servicio.buscar_por_dni(dispositivo=self.club, dni="33444555", usuario=self.guardia)

        self.assertEqual(derivada.resultado, servicio.BUSQUEDA_DERIVACION)
        self.assertEqual(derivada.caso.pk, caso.pk)

    def test_es_idempotente_y_exige_alcance(self):
        envio = uuid.uuid4()
        argumentos = {"dispositivo": self.club, "usuario": self.guardia, "datos_formulario1": self._formulario()}
        primero = servicio.avisar_a_la_mesa(**argumentos, uuid_cliente=envio)
        segundo = servicio.avisar_a_la_mesa(**argumentos, uuid_cliente=envio)
        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(TrazaCaso.objects.filter(accion=Accion.AVISO_A_LA_MESA).count(), 1)

        with self.assertRaises(PermissionDenied):
            servicio.avisar_a_la_mesa(
                dispositivo=self.club, usuario=self.guardia_escuela, datos_formulario1=self._formulario()
            )


# ---------------------------------------------------------------------------
# Egreso (RN-3.12)
# ---------------------------------------------------------------------------


class EgresoTests(BaseAlojar):
    def _alojada(self, personas=2):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_f=1, adultos_m=personas - 1)
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        return servicio.alojar_familia(caso=caso, usuario=self.guardia)

    def _egresar(self, caso, orden):
        estadia = IntegranteGrupo.objects.get(grupo=caso.grupo, orden=orden).estadia
        self.reloj.avanzar(hours=1)
        return egresar_persona(
            estadia=estadia, usuario=self.guardia, motivo_egreso=self.motivo_alta, destino="Domicilio"
        )

    def test_el_egreso_de_uno_marca_al_integrante_y_el_caso_sigue_alojado(self):
        """HU-3.7."""

        caso = self._alojada(2)

        self._egresar(caso, 1)

        integrante = IntegranteGrupo.objects.get(grupo=caso.grupo, orden=1)
        self.assertEqual(integrante.egresado_en, T0 + timedelta(hours=1))
        self.assertIsNone(IntegranteGrupo.objects.get(grupo=caso.grupo, orden=2).egresado_en)
        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        traza = self._trazas(caso)[-1]
        self.assertEqual(
            (traza.accion, traza.detalle), (Accion.INTEGRANTE_EGRESADO, "Egresó la persona 1 de la familia")
        )

    def test_el_egreso_del_ultimo_cierra_el_caso(self):
        caso = self._alojada(2)
        self._egresar(caso, 1)

        self._egresar(caso, 2)

        fila = self._fila(caso)
        self.assertEqual(fila["estado"], Estado.CERRADO)
        self.assertEqual(fila["motivo_cierre"], CasoEmergencia.MotivoCierre.TODOS_EGRESADOS)
        self.assertEqual(fila["cerrado_en"], T0 + timedelta(hours=2))
        traza = self._trazas(caso)[-1]
        self.assertEqual(traza.accion, Accion.CERRADO_POR_EGRESO)
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), (Estado.ALOJADO, Estado.CERRADO))
        self.assertEqual(traza.usuario, self.guardia)

    def test_un_egreso_con_el_ingreso_en_curso_no_cierra_el_caso(self):
        """Lo cierra la guardia; al cerrar con diferencia se vuelve a mirar si quedó alguien."""

        caso, derivacion = self._aceptado(menores_f=0, menores_m=0)
        self._confirmar(caso, 1, "45000101")
        self._egresar(caso, 1)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

        servicio.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")

        self.assertEqual(self._estado(caso), Estado.CERRADO)

    def test_el_egreso_de_una_estadia_ajena_a_emergencia_cuesta_una_consulta_y_no_hace_nada(self):
        """El receptor está en el camino de **todos** los egresos de Dispositivos."""

        self._ocupar(self.club, 1)
        estadia = Estadia.objects.get()
        trazas = TrazaCaso.objects.count()

        with self.assertNumQueries(1):
            servicio.al_egresar_estadia(sender=Estadia, estadia=estadia, usuario=self.guardia)
        with orden_de_candados(caso=CasoEmergencia.objects) as orden:
            egresar_persona(estadia=estadia, usuario=self.guardia, motivo_egreso=self.motivo_alta, destino="Domicilio")

        self.assertEqual(orden, [])
        self.assertEqual(TrazaCaso.objects.count(), trazas)
        self.assertFalse(Estadia.objects.get().activa)

    def test_el_receptor_esta_conectado_una_sola_vez(self):
        from programas.senales import estadia_egresada

        servicio.conectar_receptores()
        servicio.conectar_receptores()
        receptores = [r for r in estadia_egresada._live_receivers(Estadia)[0] if r is servicio.al_egresar_estadia]
        self.assertEqual(len(receptores), 1)


# ---------------------------------------------------------------------------
# El orden de los candados
# ---------------------------------------------------------------------------


class OrdenDeLosCandadosDeAlojarTests(BaseAlojar):
    """**caso → derivación → plazas (por pk) → reservas → persona**, en cada camino de la etapa.

    Por la secuencia de llamadas y no por su efecto: en SQLite ``select_for_update()`` es un
    no-op y no hay deadlock que reproducir. La carrera de verdad es
    ``test_emergencia_alojar_concurrencia``, con ``@tag("mysql")``.
    """

    def _orden(self):
        return orden_de_candados(
            caso=CasoEmergencia.objects,
            derivacion=Derivacion.objects,
            plaza=Plaza.objects,
            reserva=ReservaPlaza.objects,
            persona=Ciudadano.objects,
            estadia=Estadia.objects,
            numerador=NumeradorEmergencia.objects,
        )

    def _sin_repetir(self, orden):
        """El orden en que cada tipo de fila se pide **por primera vez**."""

        return list(dict.fromkeys(orden))

    def test_aceptar(self):
        _caso, derivacion = self._derivado(plazas=2)
        with self._orden() as orden:
            servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        self.assertEqual(orden, ["caso", "derivacion", "plaza"])

    def test_rechazar(self):
        _caso, derivacion = self._derivado()
        with self._orden() as orden:
            servicio.rechazar_derivacion(derivacion=derivacion, usuario=self.guardia, motivo="SIN_PLAZAS")
        self.assertEqual(orden, ["caso", "derivacion"])

    def test_confirmar_consumiendo_una_reserva(self):
        caso, _derivacion = self._aceptado(plazas=2)
        with self._orden() as orden:
            self._confirmar(caso, 2, "45000111")
        self.assertEqual(orden[:2], ["caso", "derivacion"])
        self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "reserva", "persona"])

    def test_confirmar_en_una_cama_libre_devolviendo_la_sobrante(self):
        """Las dos plazas de una vez, después la reserva que se libera y la persona al final."""

        caso, _derivacion = self._aceptado()
        libre = self._cama_libre()
        with self._orden() as orden:
            integrante = self._confirmar(caso, 2, "45000111", plaza=libre)
        self.assertTrue(integrante.reserva_liberada)
        self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "reserva", "persona"])
        self._nada_nuevo_despues_de_la_persona(orden)

    def _nada_nuevo_despues_de_la_persona(self, orden):
        """Después de la persona solo se vuelve a pedir lo que ya estaba tomado (``ingresar_persona`` relee)."""

        persona = orden.index("persona")
        nuevas = [tipo for tipo in orden[persona + 1 :] if tipo not in orden[: persona + 1]]
        self.assertEqual(nuevas, [], "pidió algo nuevo después de bloquear a la persona")

    def test_confirmar_en_una_cama_libre_cerrando_su_reserva_comun_de_otro_dispositivo(self):
        """D2 del Cambio 409: la plaza de la reserva común entra en el mismo bloqueo único por pk."""

        caso, _derivacion = self._aceptado()
        persona = Ciudadano.objects.create(dni="45000111", nombre="Juan", apellido="Pérez")
        escuela = Plaza.objects.filter(sector__dispositivo=self.escuela).order_by("pk").first()
        reservar_plaza(plaza=escuela, ciudadano=persona, usuario=self.guardia_escuela)
        libre = self._cama_libre()
        with self._orden() as orden:
            self._confirmar(caso, 2, "45000111", plaza=libre)
        self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "reserva", "persona"])
        self._nada_nuevo_despues_de_la_persona(orden)

    def test_cerrar_con_diferencia_cancelar_y_alojar(self):
        acciones = {
            "diferencia": lambda caso: servicio.cerrar_con_diferencia(
                caso=caso, usuario=self.guardia, motivo="NO_LLEGO"
            ),
            "alojar": None,
            "cancelar": lambda caso: servicio.cancelar_ingreso(caso=caso, usuario=self.guardia, motivo="No llegaron"),
        }
        for nombre, accion in acciones.items():
            with self.subTest(accion=nombre):
                caso, derivacion = self._aceptado(
                    dni=str(next(self._dnis)), menores_f=0, menores_m=0, plazas=3 if nombre == "alojar" else 2
                )
                if nombre == "alojar":
                    for orden_fila, reserva in enumerate(self._reservas(derivacion)[:2], start=1):
                        self._confirmar(caso, orden_fila, str(next(self._dnis)), plaza=reserva.plaza)
                    accion = lambda caso: servicio.alojar_familia(caso=caso, usuario=self.guardia)  # noqa: E731
                elif nombre == "diferencia":
                    self._confirmar(caso, 1, str(next(self._dnis)))
                with self._orden() as orden:
                    accion(caso)
                self.assertEqual(self._sin_repetir(orden), ["caso", "derivacion", "plaza", "reserva"])

    def test_completar_ficha_y_agregar_no_pasan_de_la_derivacion(self):
        caso, _derivacion = self._aceptado()
        self._confirmar(caso, 2, "45000111")
        with self._orden() as orden:
            servicio.completar_ficha(caso=caso, orden=2, usuario=self.guardia, ficha={"trabajo": {"sin_datos": True}})
            servicio.agregar_integrante(caso=caso, usuario=self.guardia)
        self.assertEqual(orden, ["caso", "derivacion", "caso", "derivacion"])

    def test_ingreso_directo(self):
        datos = self._datos(dni="33444555", nombre="Marta", apellido="Ríos")
        with self._orden() as orden:
            servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia, datos_formulario1=datos)
        self.assertEqual(orden, ["numerador", "caso", "plaza"])

    def test_el_egreso_bloquea_la_estadia_y_despues_el_caso(self):
        """El orden propio del egreso (ver el docstring del servicio): estadía → caso, y nada más."""

        caso, derivacion = self._aceptado(menores_f=0, menores_m=0)
        self._confirmar(caso, 1, "45000101")
        estadia = Estadia.objects.get()
        self.reloj.avanzar(hours=1)

        with self._orden() as orden:
            egresar_persona(estadia=estadia, usuario=self.guardia, motivo_egreso=self.motivo_alta, destino="Casa")

        self.assertEqual(orden, ["estadia", "caso"])


# ---------------------------------------------------------------------------
# Selectores
# ---------------------------------------------------------------------------


class SelectoresTests(BaseAlojar):
    def test_el_mapa_distingue_las_camas_de_esta_familia_de_las_de_otra(self):
        caso, derivacion = self._aceptado(plazas=3)
        _otro, otra = self._derivado(dni="30222333", plazas=2)
        servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)
        self._ocupar_una_libre()
        rota = self._cama_libre()
        Plaza.objects.filter(pk=rota.pk).update(estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota")

        (sector,) = selectores.plazas_para_caso(self.club, caso, self.guardia)

        estados = [plaza["estado"] for plaza in sector["plazas"]]
        self.assertEqual(estados.count(selectores.PLAZA_RESERVADA_FAMILIA), 3)
        self.assertEqual(estados.count(selectores.PLAZA_RESERVADA), 2)
        self.assertEqual(estados.count(selectores.PLAZA_OCUPADA), 1)
        self.assertEqual(estados.count(selectores.PLAZA_FUERA_SERVICIO), 1)
        self.assertEqual(estados.count(selectores.PLAZA_LIBRE), 2)
        self.assertEqual((sector["total"], sector["libres"], sector["reservadas_familia"]), (9, 2, 3))
        de_la_familia = {reserva.plaza_id for reserva in self._reservas(derivacion)}
        for plaza in sector["plazas"]:
            self.assertEqual(plaza["elegible"], plaza["estado"] in ("LIBRE", "RESERVADA_FAMILIA"))
            if plaza["estado"] == selectores.PLAZA_RESERVADA_FAMILIA:
                self.assertIn(plaza["id"], de_la_familia)
                self.assertEqual((plaza["texto"], plaza["tono"]), ("Reservada para esta familia", "warning"))
            if plaza["estado"] == selectores.PLAZA_RESERVADA:
                self.assertEqual((plaza["texto"], plaza["detalle"]), ("Reservada", ""))

    def _ocupar_una_libre(self):
        plaza = self._cama_libre()
        persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Alojada")
        Estadia.objects.create(
            ciudadano=persona,
            dispositivo=self.club,
            plaza=plaza,
            fecha_ingreso=T0 - timedelta(days=1),
            clave_alojamiento=Estadia.clave_para(persona),
        )

    def test_el_mapa_no_nombra_al_responsable_de_otra_familia_ni_con_permiso_de_ver_personas(self):
        """RU-9: la cama guardada para otro caso es «Reservada» y nada más."""

        caso, _derivacion = self._aceptado(plazas=1)
        _otro, otra = self._derivado(dni="30222333", apellido="Zalazar", plazas=1)
        servicio.aceptar_derivacion(derivacion=otra, usuario=self.guardia)

        (sector,) = selectores.plazas_para_caso(self.club, caso, self.guardia, puede_ver_personas=True)

        self.assertNotIn("Zalazar", repr(sector))

    def test_sin_caso_ninguna_cama_es_de_la_familia(self):
        self._aceptado(plazas=2)
        (sector,) = selectores.plazas_para_caso(self.club, None, self.guardia)
        self.assertEqual(sector["reservadas_familia"], 0)

    def test_el_mapa_y_las_llegadas_exigen_alcance(self):
        caso, _derivacion = self._aceptado()
        for usuario in (self.guardia_escuela, self.operador):
            with self.subTest(usuario=usuario.username):
                with self.assertRaises(PermissionDenied):
                    selectores.plazas_para_caso(self.club, caso, usuario)
                with self.assertRaises(PermissionDenied):
                    selectores.llegadas_del_dispositivo(self.club, usuario)

    def test_integrantes_de_cuenta_y_describe_cada_fila(self):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0)
        plaza = self._reservas(derivacion)[0].plaza
        self._confirmar(caso, 2, "45000111", plaza=plaza)
        servicio.agregar_integrante(caso=caso, usuario=self.guardia)
        caso = CasoEmergencia.objects.select_related("grupo").get(pk=caso.pk)

        datos = selectores.integrantes_de(caso)

        self.assertEqual((datos["confirmadas"], datos["total_declarado"], datos["declaradas_al_relevar"]), (1, 3, 2))
        self.assertEqual(datos["con_ficha_incompleta"], 1)
        sin_confirmar, confirmada, agregada = datos["integrantes"]
        self.assertEqual(
            (sin_confirmar["n"], sin_confirmar["estado"], sin_confirmar["persona"]), (1, "SIN_CONFIRMAR", None)
        )
        self.assertEqual(confirmada["estado"], "CONFIRMADA")
        self.assertEqual(confirmada["persona"]["nombre"], "Pérez, Juan")
        self.assertEqual(
            confirmada["plaza"],
            {
                "id": plaza.pk,
                "codigo": plaza.codigo,
                "nombre": f"{plaza.codigo} (General)",
                "sector_id": plaza.sector_id,
            },
        )
        self.assertEqual(confirmada["parentesco"], "Hijo/a")
        self.assertFalse(confirmada["ficha_completa"])
        self.assertEqual(agregada["n"], 3)

    def test_las_llegadas_son_solo_las_de_ese_dispositivo(self):
        """RU-9."""

        pendiente_caso, pendiente = self._derivado()
        en_curso_caso, en_curso = self._aceptado(dni="30222333", plazas=2)
        self._confirmar(en_curso_caso, 2, "45000111")
        self._derivado(dispositivo=self.escuela, dni="30333444")
        _alojado_caso, alojada = self._aceptado(dni="30444555", menores_f=0, menores_m=0, adultos_m=0)
        self._confirmar(CasoEmergencia.objects.get(pk=alojada.caso_id), 1, "45000222")
        servicio.alojar_familia(caso=alojada.caso_id, usuario=self.guardia)

        llegadas = selectores.llegadas_del_dispositivo(self.club, self.guardia)

        self.assertEqual([d.pk for d in llegadas["pendientes"]], [pendiente.pk])
        self.assertEqual([d.pk for d in llegadas["en_curso"]], [en_curso.pk])
        self.assertEqual(llegadas["en_curso"][0].confirmadas, 1)
        self.assertEqual(llegadas["pendientes"][0].confirmadas, 0)


@tag("performance")
class PresupuestoDeConsultasDeAlojarTests(BaseAlojar):
    """Las dos lecturas de M2-3 / M2-4 cuestan lo mismo con 9 camas que con 300: sin N+1."""

    #: Las dos del alcance con un usuario recién leído (sus capacidades, que `rbac` memoiza en
    #: el objeto, y si integra el Equipo con un rol que admite), las camas con su sector, las
    #: dos de `estado_de_plazas` y la derivación vigente del caso.
    CONSULTAS_PLAZAS = 6
    #: Los integrantes con persona, estadía, plaza y sector.
    CONSULTAS_INTEGRANTES = 1

    def setUp(self):
        super().setUp()
        self.grande = self._dispositivo("Polideportivo", camas=0)
        for letra in "ABC":
            sector = Sector.objects.create(dispositivo=self.grande, nombre=f"Pabellón {letra}", capacidad=100)
            Plaza.objects.bulk_create([Plaza(sector=sector, codigo=f"{letra}-{n}") for n in range(1, 101)])
        self.guardia_grande = self._guardia("guardia_grande", self.grande)

    def test_plazas_para_caso_con_300_camas(self):
        caso, derivacion = self._derivado(dispositivo=self.grande)
        self._ocupar(self.grande, 120)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_grande)
        usuario = User.objects.get(pk=self.guardia_grande.pk)

        with self.assertNumQueries(self.CONSULTAS_PLAZAS):
            sectores = selectores.plazas_para_caso(self.grande, caso, usuario)

        self.assertEqual(sum(sector["total"] for sector in sectores), 300)
        self.assertEqual(sum(sector["reservadas_familia"] for sector in sectores), 7)
        self.assertEqual(sum(len(sector["plazas"]) for sector in sectores), 300)

    def test_integrantes_de_una_familia_grande(self):
        caso, derivacion = self._derivado(dispositivo=self.grande, menores_f=20, menores_m=18)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_grande)
        for orden, reserva in enumerate(self._reservas(derivacion)[:30], start=1):
            servicio.confirmar_integrante(
                caso=caso,
                orden=orden,
                usuario=self.guardia_grande,
                ficha=ficha_minima(str(46_000_000 + orden)),
                plaza=reserva.plaza,
            )
        caso = CasoEmergencia.objects.select_related("grupo").get(pk=caso.pk)

        with self.assertNumQueries(self.CONSULTAS_INTEGRANTES):
            datos = selectores.integrantes_de(caso)

        self.assertEqual((datos["confirmadas"], datos["total_declarado"]), (30, 40))

    def _llegadas_cuestan(self):
        """Cuántas consultas cuesta la lista de llegadas, con el usuario recién leído.

        Cuenta también el armado de las filas y de las tarjetas (familia, responsable, quién
        derivó): es lo que lee la pantalla, y donde aparecería un N+1 si el selector dejara de
        traer algo.
        """

        usuario = User.objects.get(pk=self.guardia_grande.pk)
        ahora = timezone.now()
        with CaptureQueriesContext(connection) as consultas:
            llegadas = selectores.llegadas_del_dispositivo(self.grande, usuario)
            for derivaciones in llegadas.values():
                pantalla.filas_de_llegadas(derivaciones, ahora, lambda derivacion: "")
                for derivacion in derivaciones:
                    pantalla.tarjeta_de_derivacion(derivacion, ahora)
        return len(consultas), llegadas

    def _familias_derivadas(self, desde, cuantas):
        """``cuantas`` familias de 2 derivadas al Polideportivo: la mitad aceptadas, la otra pendientes."""

        for n in range(desde, desde + cuantas):
            _caso, derivacion = self._derivado(
                dispositivo=self.grande, dni=str(31_000_000 + n), menores_f=0, menores_m=1, plazas=2
            )
            if n % 2:
                servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia_grande)

    def test_llegadas_cuestan_lo_mismo_con_2_que_con_20_derivaciones(self):
        """Sin N+1: la lista de llegadas trae caso, grupo, responsable y quién derivó en la misma consulta."""

        self._familias_derivadas(0, 2)
        con_2, llegadas = self._llegadas_cuestan()
        self.assertEqual((len(llegadas["pendientes"]), len(llegadas["en_curso"])), (1, 1))

        self._familias_derivadas(2, 18)
        con_20, llegadas = self._llegadas_cuestan()
        self.assertEqual((len(llegadas["pendientes"]), len(llegadas["en_curso"])), (10, 10))

        self.assertEqual(con_20, con_2, "las consultas de llegadas crecen con las derivaciones")
