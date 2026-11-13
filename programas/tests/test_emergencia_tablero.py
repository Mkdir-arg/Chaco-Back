"""Módulo Emergencia, PR 10: el tablero del supervisor (E1) y los avisos de la mesa.

* **Números** — cada número del hero y de las seis tarjetas, la tabla por localidad y la de
  tiempos contra un escenario sembrado con **momentos fijos** (tabla de casos abajo). El
  reloj está detenido en ``T0`` (12/11/2026 10:00, hora Argentina): nada depende de la hora
  a la que corre el test.
* **Avisos** — cada ``ReglaAviso`` aparece cuando se cumple y desaparece cuando deja de
  cumplirse (RN-5.4). Visto en rojo con la condición rota: con
  ``q_entrega_sin_revisar`` sin el ``~Exists`` de la traza ``OBSERVADA``,
  ``test_entrega_con_diferencias_se_apaga_con_la_observacion_de_e5`` falla porque el aviso
  sigue después de observar la entrega en E5.
* **RN-5.2** — el SQL del tablero no tiene ``CONVERT_TZ`` ni ``Trunc``.
* **RN-5.6** — presupuesto de consultas con 500 casos abiertos, 50 dispositivos y 200
  entregas (``--tag performance``).
* **Acceso** — sin login, al login; con solo ``operar``, 403; con ``supervisar``, 200.
"""

from datetime import datetime, timedelta

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import Localidad
from core.services import vencimientos
from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Dispositivo,
    EntregaKit,
    GrupoFamiliar,
    LineaEntrega,
    Plaza,
    ReservaPlaza,
    Sector,
    TipoKit,
    TrazaCaso,
    TrazaEntrega,
)
from programas.selectors import emergencia_tablero as tablero
from programas.services import avisos_emergencia
from programas.services import emergencia as servicio
from programas.services.configuracion_emergencia import sla_vigente
from programas.services.emergencia_programa import puede_operar_la_mesa
from programas.tests.test_emergencia_base import OPERAR, SUPERVISAR, urls_de_emergencia
from programas.tests.test_emergencia_casos import T0, BaseCasos

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Accion = TrazaCaso.Accion

URL_TABLERO = "/emergencia/tablero/"


def _hora(hh, mm=0, dias=0):
    """Un momento del 12/11/2026 (hora Argentina), ``dias`` antes."""
    return T0.replace(hour=hh, minute=mm) - timedelta(days=dias)


#: El escenario. Reloj en T0 = 10:00. Objetivos de fábrica: tomar 15, derivar 30, aceptar 120,
#: alojar 60; «por vencer» al 80 %. Día operativo: [12/11 06:00, 13/11 06:00).
#:
#: ===  =================  ======  ======  =====  =====  =====  =====  =====  ==============
#: N.°  estado             origen  local.  creado tomado deriv. acept. aloj.  semáforo / nota
#: ===  =================  ======  ======  =====  =====  =====  =====  =====  ==============
#: C1   NUEVO              TERR    Resis.  09:50                              tomar, en término
#: C2   NUEVO              TERR    Resis.  09:30                              tomar, FUERA 15
#: C3   NUEVO              DISP    Barr.   09:52                              en la puerta
#: C4   EN_GESTION         TERR    Resis.  08:00  08:10                       derivar, FUERA 80
#: C5   EN_GESTION         TERR    Barr.   09:00  09:05  09:20                aceptar 40, rechazada
#: C6   DERIVADO           TERR    Resis.  07:00  07:05  07:20                aceptar, FUERA 40
#: C7   INGRESO_EN_CURSO   TERR    Barr.   08:00  08:05  08:15  09:30         alojar 30
#: C8   ALOJADO (3 de 3)   TERR    Resis.  06:30  06:40  07:00  07:30  08:30  hoy
#: C9   ALOJADO (2 de 4)   TERR    Barr.   07:00  07:10  07:30  08:00  09:00  hoy, parcial
#: C10  ALOJADO (2 de 2)   DISP    Resis.  08:00  08:00  08:00  08:00  08:45  hoy, ingreso directo
#: C11  ALOJADO (1 de 1)   TERR    Resis.  04:00  04:10  04:30  05:00  05:30  día operativo anterior
#: C12  CERRADO hace 2 d   TERR    Resis.  −3 d                               fuera de la ventana
#: C13  CERRADO 09:00      TERR    Resis.  08:30  08:40                       tomar 10, cerrado
#: ===  =================  ======  ======  =====  =====  =====  =====  =====  ==============
#:
#: Red: Club Sarmiento (Resistencia, 10 camas, 3 ocupadas, 1 reservada → 6 libres) y Escuela 12
#: (Barranqueras, 4 camas, todas ocupadas → 0 libres). C6 tiene la derivación pendiente a la
#: Escuela 12, que vence a las 10:30. Un tercer dispositivo inactivo no cuenta.
#: Entregas: dos en camino, una recibida con diferencias sin revisar, una observada y una preparada.
ESCENARIO = (
    # (clave, estado, origen, localidad, creado, tomado, derivado, aceptado, alojado, cerrado, declarado, alojado)
    ("C1", Estado.NUEVO, Origen.TERRITORIO, "R", _hora(9, 50), None, None, None, None, None, 2, None),
    ("C2", Estado.NUEVO, Origen.TERRITORIO, "R", _hora(9, 30), None, None, None, None, None, 2, None),
    ("C3", Estado.NUEVO, Origen.DISPOSITIVO, "B", _hora(9, 52), None, None, None, None, None, 2, None),
    ("C4", Estado.EN_GESTION, Origen.TERRITORIO, "R", _hora(8), _hora(8, 10), None, None, None, None, 2, None),
    ("C5", Estado.EN_GESTION, Origen.TERRITORIO, "B", _hora(9), _hora(9, 5), _hora(9, 20), None, None, None, 2, None),
    ("C6", Estado.DERIVADO, Origen.TERRITORIO, "R", _hora(7), _hora(7, 5), _hora(7, 20), None, None, None, 2, None),
    (
        "C7",
        Estado.INGRESO_EN_CURSO,
        Origen.TERRITORIO,
        "B",
        _hora(8),
        _hora(8, 5),
        _hora(8, 15),
        _hora(9, 30),
        None,
        None,
        2,
        None,
    ),
    (
        "C8",
        Estado.ALOJADO,
        Origen.TERRITORIO,
        "R",
        _hora(6, 30),
        _hora(6, 40),
        _hora(7),
        _hora(7, 30),
        _hora(8, 30),
        None,
        3,
        3,
    ),
    (
        "C9",
        Estado.ALOJADO,
        Origen.TERRITORIO,
        "B",
        _hora(7),
        _hora(7, 10),
        _hora(7, 30),
        _hora(8),
        _hora(9),
        None,
        4,
        2,
    ),
    ("C10", Estado.ALOJADO, Origen.DISPOSITIVO, "R", _hora(8), _hora(8), _hora(8), _hora(8), _hora(8, 45), None, 2, 2),
    (
        "C11",
        Estado.ALOJADO,
        Origen.TERRITORIO,
        "R",
        _hora(4),
        _hora(4, 10),
        _hora(4, 30),
        _hora(5),
        _hora(5, 30),
        None,
        1,
        1,
    ),
    (
        "C12",
        Estado.CERRADO,
        Origen.TERRITORIO,
        "R",
        _hora(10, dias=3),
        None,
        None,
        None,
        None,
        _hora(10, dias=2),
        2,
        None,
    ),
    ("C13", Estado.CERRADO, Origen.TERRITORIO, "R", _hora(8, 30), _hora(8, 40), None, None, None, _hora(9), 2, None),
)


class BaseTablero(BaseCasos):
    """La mesa con un supervisor y los atajos para sembrar casos con las marcas que se quieran."""

    def setUp(self):
        super().setUp()
        self.sla = sla_vigente()
        self._numeros = iter(range(1, 100_000))

    def _localidad(self, nombre):
        return Localidad.objects.get_or_create(nombre=nombre, municipio=None)[0]

    def _sembrar(
        self,
        estado,
        *,
        origen=Origen.TERRITORIO,
        localidad=None,
        creado=T0,
        tomado_en=None,
        derivado_en=None,
        aceptado_en=None,
        alojado_en=None,
        cerrado_en=None,
        declarado=2,
        alojado=None,
        situacion=None,
        apellido="Benítez",
    ):
        """Un caso escrito directo en la base, con las marcas exactas (sin pasar por el servicio)."""

        persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Rosa", apellido=apellido)
        grupo = GrupoFamiliar.objects.create(
            responsable=persona,
            traslado=GrupoFamiliar.Traslado.BOMBEROS,
            adultos_f=declarado,
            total_declarado=declarado,
        )
        caso = CasoEmergencia.objects.create(
            numero=f"2026-{next(self._numeros):06d}",
            grupo=grupo,
            origen=origen,
            estado=estado,
            prioridad=CasoEmergencia.Prioridad.MEDIA,
            localidad=localidad,
            direccion="Av. Sarmiento 1200",
            relevado_por=self.agente,
            relevado_en=creado,
            tomado_en=tomado_en,
            derivado_en=derivado_en,
            aceptado_en=aceptado_en,
            alojado_en=alojado_en,
            cerrado_en=cerrado_en,
            total_alojado=alojado,
            situacion=situacion or {},
        )
        CasoEmergencia.objects.filter(pk=caso.pk).update(creado=creado)
        caso.refresh_from_db()
        return caso

    def _traza(self, caso, accion, detalle="", momento=None):
        self.reloj.ahora, antes = momento or self.reloj.ahora, self.reloj.ahora
        traza = TrazaCaso.objects.create(caso=caso, usuario=self.operador, accion=accion, detalle=detalle)
        self.reloj.ahora = antes
        return traza

    def _derivar(self, caso, dispositivo, vence_en):
        derivacion = Derivacion(
            caso=caso, dispositivo=dispositivo, plazas_pedidas=2, vence_en=vence_en, derivada_por=self.operador
        )
        derivacion.save()
        return derivacion

    def _reservar(self, dispositivo):
        plaza = Plaza.objects.filter(sector__dispositivo=dispositivo, estadias__isnull=True).order_by("codigo").first()
        persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Persona", apellido="Reservada")
        return ReservaPlaza.objects.create(plaza=plaza, ciudadano=persona, desde=T0 - timedelta(hours=1))

    def _entrega(self, dispositivo, estado, *, despachada_en=None, recibida_en=None, items=1):
        entrega = EntregaKit.objects.create(
            numero=f"2026-K-{next(self._numeros):06d}",
            dispositivo=dispositivo,
            estado=estado,
            armada_por=self.operador,
            despachada_en=despachada_en,
        )
        if recibida_en is not None:
            EntregaKit.objects.filter(pk=entrega.pk).update(recibida_en=recibida_en)
        for n in range(items):
            item, _creado = TipoKit.objects.get_or_create(nombre=f"Ítem {n}", defaults={"unidad": "unidad"})
            LineaEntrega.objects.create(entrega=entrega, item=item, unidad="unidad", cantidad_enviada=n + 1)
        return entrega

    def _foto(self):
        return tablero.foto_del_tablero(sla_vigente(), self.reloj.ahora)

    def _avisos(self, usuario=None):
        return avisos_emergencia.avisos_del_tablero(sla_vigente(), self.reloj.ahora, usuario=usuario or self.supervisor)

    def _reglas(self, usuario=None):
        return [aviso["regla"] for aviso in self._avisos(usuario)]


class EscenarioTablero(BaseTablero):
    """La tabla de :data:`ESCENARIO` sembrada."""

    def setUp(self):
        super().setUp()
        self.resistencia = self._localidad("Resistencia")
        self.barranqueras = self._localidad("Barranqueras")
        localidades = {"R": self.resistencia, "B": self.barranqueras}
        self.club = self._dispositivo("Club Sarmiento", camas=10, localidad="Resistencia")
        self.escuela = self._dispositivo("Escuela 12", camas=4, localidad=" barranqueras ")
        self._dispositivo("Cerrado", camas=8, localidad="Resistencia", estado=Dispositivo.Estado.INACTIVO)
        self._ocupar(self.club, 3)
        self._ocupar(self.escuela, 4)
        self._reservar(self.club)

        self.casos = {}
        for (
            clave,
            estado,
            origen,
            loc,
            creado,
            tomado,
            derivado,
            aceptado,
            alojado_en,
            cerrado,
            decl,
            aloj,
        ) in ESCENARIO:
            situacion = {"en_la_puerta_de": {"dispositivo_id": self.escuela.pk, "dispositivo": "Escuela 12"}}
            self.casos[clave] = self._sembrar(
                estado,
                origen=origen,
                localidad=localidades[loc],
                creado=creado,
                tomado_en=tomado,
                derivado_en=derivado,
                aceptado_en=aceptado,
                alojado_en=alojado_en,
                cerrado_en=cerrado,
                declarado=decl,
                alojado=aloj,
                situacion=situacion if clave == "C3" else None,
                apellido=f"Familia{clave}",
            )
        self._traza(self.casos["C5"], Accion.DERIVACION_RECHAZADA, "Rechazada por Escuela 12: sin lugar", _hora(9, 40))
        self.derivacion_c6 = self._derivar(self.casos["C6"], self.escuela, _hora(10, 30))

        self.en_camino_1 = self._entrega(self.club, EntregaKit.Estado.EN_CAMINO, despachada_en=_hora(7), items=4)
        self.en_camino_2 = self._entrega(self.escuela, EntregaKit.Estado.EN_CAMINO, despachada_en=_hora(9))
        self.con_diferencias = self._entrega(
            self.escuela, EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS, despachada_en=_hora(6), recibida_en=_hora(8)
        )
        observada = self._entrega(
            self.club, EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS, despachada_en=_hora(6), recibida_en=_hora(7)
        )
        TrazaEntrega.objects.create(entrega=observada, usuario=self.supervisor, accion=TrazaEntrega.Accion.OBSERVADA)
        self._entrega(self.club, EntregaKit.Estado.PREPARADA)


# ---------------------------------------------------------------------------
# Día operativo (RN-5.2, H8)
# ---------------------------------------------------------------------------


class DiaOperativoTests(BaseTablero):
    def test_empieza_a_las_seis_hora_argentina(self):
        desde, hasta = tablero.dia_operativo(T0)
        self.assertEqual((desde.hour, desde.minute, desde.day), (6, 0, 12))
        self.assertEqual(hasta - desde, timedelta(days=1))
        self.assertEqual(tablero.DIA_OPERATIVO_DESDE.hour, 6)

    def test_antes_de_las_seis_es_el_dia_anterior(self):
        desde, _hasta = tablero.dia_operativo(_hora(5, 59))
        self.assertEqual((desde.day, desde.hour), (11, 6))
        desde, _hasta = tablero.dia_operativo(_hora(6))
        self.assertEqual((desde.day, desde.hour), (12, 6))

    def test_no_depende_de_la_zona_del_instante_que_llega(self):
        """El mismo instante en UTC da el mismo día operativo: 09:30 UTC son 06:30 en Argentina."""
        from datetime import timezone as tz

        en_utc = datetime(2026, 11, 12, 9, 30, tzinfo=tz.utc)
        self.assertEqual(tablero.dia_operativo(en_utc)[0].day, 12)
        en_utc = datetime(2026, 11, 12, 8, 30, tzinfo=tz.utc)
        self.assertEqual(tablero.dia_operativo(en_utc)[0].day, 11)


# ---------------------------------------------------------------------------
# Hero, tarjetas, localidades, tiempos y entregas
# ---------------------------------------------------------------------------


class ResumenTests(EscenarioTablero):
    def setUp(self):
        super().setUp()
        self.resumen = tablero.resumen(self.sla, T0)
        self.tarjetas = {tarjeta["etiqueta"]: tarjeta for tarjeta in self.resumen["tarjetas"]}

    def _tarjeta(self, etiqueta):
        tarjeta = self.tarjetas[etiqueta]
        return tarjeta["valor"], tarjeta["nota"]

    def test_hero(self):
        self.assertEqual(self.resumen["titulo"], "Emergencia")
        self.assertEqual(self.resumen["hero"], {"abiertos": 11, "fuera": 3, "libres": 6, "dispositivos": 2})

    def test_las_seis_tarjetas_en_orden(self):
        self.assertEqual(
            list(self.tarjetas),
            [
                "Casos nuevos sin tomar",
                "En gestión",
                "Fuera de SLA",
                "Familias alojadas hoy",
                "Plazas libres en la red",
                "Entregas en camino",
            ],
        )

    def test_1_nuevos_sin_tomar_con_el_mas_viejo(self):
        self.assertEqual(self._tarjeta("Casos nuevos sin tomar"), (3, "el más viejo hace 30 min"))

    def test_2_en_gestion_con_derivados_e_ingresando(self):
        self.assertEqual(self._tarjeta("En gestión"), (4, "1 derivado · 1 ingresando"))

    def test_3_fuera_de_sla_por_tramo(self):
        self.assertEqual(self._tarjeta("Fuera de SLA"), (3, "tomar 1 · derivar 1 · aceptar 1 · alojar 0"))
        self.assertEqual(self.tarjetas["Fuera de SLA"]["tono"], "danger")

    def test_4_alojadas_hoy_en_el_dia_operativo(self):
        """C8, C9 y C10; C11 se alojó a las 05:30, que es del día operativo anterior."""
        self.assertEqual(self._tarjeta("Familias alojadas hoy"), (3, "7 personas · 1 ingreso directo · 1 parcial"))

    def test_5_plazas_libres_de_los_elegibles(self):
        self.assertEqual(self._tarjeta("Plazas libres en la red"), (6, "1 reservada"))

    def test_6_entregas_en_camino_con_diferencias_sin_revisar(self):
        self.assertEqual(self._tarjeta("Entregas en camino"), (2, "1 con diferencias sin revisar"))

    def test_hu_5_1_subir_el_objetivo_baja_el_conteo_sin_reprocesar(self):
        """RN-5.1: es un cálculo al leer. Con derivar en 90 min, C4 (110 min) sigue fuera; con 120, no."""
        self.sla.objetivo_derivar_min = 120
        self.sla.save()
        resumen = tablero.resumen(sla_vigente(), T0)
        self.assertEqual(resumen["hero"]["fuera"], 2)
        fuera = {t["etiqueta"]: t["nota"] for t in resumen["tarjetas"]}["Fuera de SLA"]
        self.assertEqual(fuera, "tomar 1 · derivar 0 · aceptar 1 · alojar 0")


class PorLocalidadTests(EscenarioTablero):
    def test_filas_ordenadas_por_fuera_de_sla(self):
        filas = tablero.por_localidad(self.sla, T0)
        sin_url = [{clave: fila[clave] for clave in fila if clave != "url"} for fila in filas]
        self.assertEqual(
            sin_url,
            [
                {
                    "localidad": "Resistencia",
                    "localidad_id": self.resistencia.pk,
                    "nuevos": 2,
                    "en_gestion": 2,
                    "fuera_de_sla": 3,
                    "alojadas_hoy": 2,
                    "plazas_libres": 6,
                },
                {
                    "localidad": "Barranqueras",
                    "localidad_id": self.barranqueras.pk,
                    "nuevos": 1,
                    "en_gestion": 2,
                    "fuera_de_sla": 0,
                    "alojadas_hoy": 1,
                    "plazas_libres": 0,
                },
            ],
        )

    def test_hu_5_2_la_fila_lleva_a_la_bandeja_filtrada(self):
        filas = {fila["localidad"]: fila for fila in tablero.por_localidad(self.sla, T0)}
        self.assertEqual(filas["Barranqueras"]["url"], f"/emergencia/casos/?localidad={self.barranqueras.pk}")
        self.client.force_login(self.supervisor)
        self.assertEqual(self.client.get(filas["Barranqueras"]["url"]).status_code, 200)

    def test_una_localidad_solo_con_dispositivos_aparece_sin_enlace(self):
        self._dispositivo("Polideportivo", camas=5, localidad="Fontana")
        filas = {fila["localidad"]: fila for fila in tablero.por_localidad(self.sla, T0)}
        self.assertEqual((filas["Fontana"]["plazas_libres"], filas["Fontana"]["url"]), (5, ""))


class TiemposTests(EscenarioTablero):
    def test_mediana_p90_y_fuera_de_objetivo_por_tramo(self):
        """Tomar: 5,5,5,8,10,10,10,10,10,10,30 · derivar: 10,15,15,20,20,20,110 ·
        aceptar: 30,30,30,40,75,160 · alojar: 30,30,45,60,60 (C10, ingreso directo, solo en alojar)."""
        filas = {fila["tramo"]: fila for fila in tablero.tiempos(self.sla, T0)}
        esperado = {
            "Tomar": ("15 min", 11, "10 min", "10 min", 1),
            "Derivar": ("30 min", 7, "20 min", "1 h", 1),
            "Aceptar": ("2 h", 6, "35 min", "2 h", 1),
            "Alojar": ("60 min", 5, "45 min", "60 min", 0),
        }
        for tramo, (objetivo, casos, mediana, p90, fuera) in esperado.items():
            with self.subTest(tramo=tramo):
                fila = filas[tramo]
                self.assertEqual(
                    (fila["objetivo"], fila["casos"], fila["mediana"], fila["p90"], fila["fuera_de_objetivo"]),
                    (objetivo, casos, mediana, p90, fuera),
                )


class EntregasEnCaminoTests(EscenarioTablero):
    def test_la_mas_vieja_primero_con_su_resumen(self):
        filas, total = tablero.entregas_en_camino(T0)
        self.assertEqual(total, 2)
        self.assertEqual([fila["numero"] for fila in filas], [self.en_camino_1.numero, self.en_camino_2.numero])
        primera = filas[0]
        self.assertEqual(primera["dispositivo"], "Club Sarmiento")
        self.assertEqual((primera["desde"], primera["hace"]), ("12/11 07:00", "hace 3 h"))
        self.assertEqual(primera["items"], "1 Ítem 0, 2 Ítem 1, 3 Ítem 2…")
        self.assertEqual(primera["url"], reverse("emergencia:entrega_detalle", args=[self.en_camino_1.pk]))

    def test_acotadas_al_tope(self):
        filas, total = tablero.entregas_en_camino(T0, tope=1)
        self.assertEqual((len(filas), total), (1, 2))


class ProgramaVacioTests(BaseTablero):
    def test_ceros_sin_divisiones_por_cero(self):
        resumen = tablero.resumen(self.sla, T0)
        self.assertFalse(resumen["hay_casos"])
        self.assertEqual(resumen["hero"], {"abiertos": 0, "fuera": 0, "libres": 0, "dispositivos": 0})
        self.assertEqual([tarjeta["valor"] for tarjeta in resumen["tarjetas"]], [0, 0, 0, 0, 0, 0])
        self.assertEqual(resumen["tarjetas"][0]["nota"], "ninguno esperando")
        self.assertEqual(tablero.por_localidad(self.sla, T0), [])
        for fila in tablero.tiempos(self.sla, T0):
            with self.subTest(tramo=fila["tramo"]):
                self.assertEqual(
                    (fila["casos"], fila["mediana"], fila["p90"], fila["fuera_de_objetivo"]), (0, "—", "—", 0)
                )
        self.assertEqual(tablero.entregas_en_camino(T0), ([], 0))
        self.assertEqual(self._avisos(), [])

    def test_la_pantalla_dice_que_todavia_no_hay_casos(self):
        self.client.force_login(self.supervisor)
        respuesta = self.client.get(URL_TABLERO)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Todavía no hay casos")
        self.assertContains(respuesta, "No hay entregas en camino")
        self.assertNotContains(respuesta, 'aria-label="Avisos que piden acción"')


# ---------------------------------------------------------------------------
# Avisos (RN-5.4)
# ---------------------------------------------------------------------------


class AvisosTests(EscenarioTablero):
    def test_las_siete_reglas_estan_registradas_en_el_ambito(self):
        self.assertEqual(
            {regla.slug for regla in vencimientos.AVISOS if regla.ambito == "emergencia"},
            {slug for slug, *_resto in avisos_emergencia.REGLAS},
        )
        self.assertEqual(len(avisos_emergencia.REGLAS), 7)

    def test_el_escenario_enciende_las_siete_de_la_alta_a_la_media(self):
        self.assertEqual(
            self._reglas(),
            [
                "emergencia.caso_fuera_de_sla",
                "emergencia.caso_fuera_de_sla",
                "emergencia.caso_fuera_de_sla",
                "emergencia.derivacion_rechazada",
                "emergencia.sin_plazas_con_pendiente",
                "emergencia.familia_en_la_puerta",
                "emergencia.derivacion_por_vencer",
                "emergencia.ingreso_parcial",
                "emergencia.entrega_con_diferencias",
            ],
        )

    def test_cada_aviso_lleva_tono_icono_y_su_pantalla(self):
        avisos = self._avisos()
        fuera = [aviso for aviso in avisos if aviso["regla"] == "emergencia.caso_fuera_de_sla"]
        # Del más excedido al menos: C4 (80 min), C6 (40), C2 (15).
        self.assertEqual(
            [aviso["titulo"] for aviso in fuera],
            [f"Caso {self.casos[c].numero} fuera de SLA" for c in ("C4", "C6", "C2")],
        )
        self.assertEqual(fuera[0]["enlace"], reverse("emergencia:caso_detalle", args=[self.casos["C4"].pk]))
        self.assertEqual((fuera[0]["tono"], fuera[0]["icono"]), ("danger", "triangle-exclamation"))
        entrega = next(aviso for aviso in avisos if aviso["regla"] == "emergencia.entrega_con_diferencias")
        self.assertEqual(entrega["enlace"], reverse("emergencia:entrega_detalle", args=[self.con_diferencias.pk]))
        self.assertEqual(entrega["tono"], "warning")
        puerta = next(aviso for aviso in avisos if aviso["regla"] == "emergencia.familia_en_la_puerta")
        self.assertEqual(puerta["titulo"], "Familia en la puerta de Escuela 12")
        vencer = next(aviso for aviso in avisos if aviso["regla"] == "emergencia.derivacion_por_vencer")
        self.assertIn("vence en 30 min", vencer["texto"])

    def test_sin_capacidad_de_mesa_el_aviso_aparece_sin_enlace(self):
        ajeno = self._usuario("ajeno", [OPERAR], programa=self.becas)
        avisos = self._avisos(ajeno)
        self.assertEqual(len(avisos), 9)
        self.assertEqual({(aviso["enlace"], aviso["accion"]) for aviso in avisos}, {("", "")})

    def test_fuera_de_sla_se_apaga_al_avanzar_el_caso(self):
        servicio.tomar_caso(self.casos["C2"], self.operador)
        titulos = [a["titulo"] for a in self._avisos() if a["regla"] == "emergencia.caso_fuera_de_sla"]
        self.assertNotIn(f"Caso {self.casos['C2'].numero} fuera de SLA", titulos)
        self.assertEqual(len(titulos), 2)

    def test_derivacion_rechazada_se_apaga_con_una_nueva_accion(self):
        servicio.registrar_contacto(self.casos["C5"], self.supervisor, canal="LLAMADA", resultado="ATENDIO")
        self.assertNotIn("emergencia.derivacion_rechazada", self._reglas())

    def test_sin_plazas_y_por_vencer_se_apagan_al_cancelar_la_derivacion(self):
        servicio.cancelar_derivacion(self.derivacion_c6, self.supervisor, "La Escuela 12 se llenó")
        reglas = self._reglas()
        self.assertNotIn("emergencia.sin_plazas_con_pendiente", reglas)
        self.assertNotIn("emergencia.derivacion_por_vencer", reglas)

    def test_sin_plazas_se_apaga_cuando_se_libera_una_plaza(self):
        Plaza.objects.create(sector=Sector.objects.get(dispositivo=self.escuela), codigo="C099")
        self.assertNotIn("emergencia.sin_plazas_con_pendiente", self._reglas())
        self.assertIn("emergencia.derivacion_por_vencer", self._reglas())

    def test_por_vencer_no_aparece_con_mas_de_una_hora(self):
        Derivacion.objects.filter(pk=self.derivacion_c6.pk).update(vence_en=_hora(11, 1))
        self.assertNotIn("emergencia.derivacion_por_vencer", self._reglas())

    def test_en_la_puerta_se_apaga_al_tomar_el_caso(self):
        servicio.tomar_caso(self.casos["C3"], self.operador)
        self.assertNotIn("emergencia.familia_en_la_puerta", self._reglas())

    def test_ingreso_parcial_se_apaga_con_un_contacto_posterior(self):
        servicio.registrar_contacto(
            self.casos["C9"], self.supervisor, canal="LLAMADA", resultado="ATENDIO", momento=_hora(8, 59)
        )
        self.assertIn("emergencia.ingreso_parcial", self._reglas(), "un contacto anterior al alojamiento no revisa")
        servicio.registrar_contacto(self.casos["C9"], self.supervisor, canal="LLAMADA", resultado="ATENDIO")
        self.assertNotIn("emergencia.ingreso_parcial", self._reglas())

    def test_entrega_con_diferencias_se_apaga_con_la_observacion_de_e5(self):
        """HU-5.3: el aviso lleva a E5; al escribir la observación de la mesa, desaparece."""
        self.client.force_login(self.supervisor)
        aviso = next(a for a in self._avisos() if a["regla"] == "emergencia.entrega_con_diferencias")
        self.assertEqual(self.client.get(aviso["enlace"]).status_code, 200)
        respuesta = self.client.post(
            reverse("emergencia:entrega_observar", args=[self.con_diferencias.pk]), {"texto": "Se repone el faltante."}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertNotIn("emergencia.entrega_con_diferencias", self._reglas())
        resumen = tablero.resumen(sla_vigente(), T0)
        self.assertEqual(resumen["tarjetas"][5]["nota"], "0 con diferencias sin revisar")

    def test_mas_de_cinco_se_resumen_en_uno_que_lleva_a_la_bandeja(self):
        for minuto in range(6):
            self._sembrar(Estado.NUEVO, creado=_hora(8, minuto))
        fuera = [a for a in self._avisos() if a["regla"] == "emergencia.caso_fuera_de_sla"]
        self.assertEqual(len(fuera), avisos_emergencia.TOPE_POR_REGLA + 1)
        self.assertEqual(fuera[-1]["titulo"], "Y 4 casos fuera de SLA más")
        self.assertEqual(fuera[-1]["enlace"], "/emergencia/casos/?solapa=fuera_sla")

    def test_avisar_nunca_bloquea(self):
        """Con todos los avisos encendidos, la mesa sigue operando igual (RN-5.4)."""
        self.assertTrue(self._avisos())
        caso = servicio.tomar_caso(self.casos["C1"], self.operador)
        self.assertEqual(caso.estado, Estado.EN_GESTION)


# ---------------------------------------------------------------------------
# RN-5.2: sin CONVERT_TZ ni Trunc
# ---------------------------------------------------------------------------


class SinZonaHorariaEnLaBaseTests(EscenarioTablero):
    def test_el_sql_del_tablero_no_trunca_ni_convierte_zonas(self):
        with CaptureQueriesContext(connection) as capturadas:
            foto = tablero.foto_del_tablero(self.sla, T0)
            tablero.resumen(self.sla, T0, foto=foto)
            tablero.por_localidad(self.sla, T0, foto=foto)
            tablero.tiempos(self.sla, T0, foto=foto)
            tablero.entregas_en_camino(T0)
            avisos_emergencia.avisos_del_tablero(self.sla, T0, usuario=self.supervisor, foto=foto)
        sql = " ".join(consulta["sql"] for consulta in capturadas.captured_queries).lower()
        self.assertTrue(sql)
        self.assertNotIn("convert_tz", sql)
        self.assertNotIn("trunc", sql)


# ---------------------------------------------------------------------------
# La pantalla
# ---------------------------------------------------------------------------


class TableroVistaTests(EscenarioTablero):
    def test_la_url_es_la_del_namespace_y_entra_al_barrido(self):
        self.assertEqual(reverse("emergencia:tablero"), URL_TABLERO)
        self.assertIn(URL_TABLERO, urls_de_emergencia())

    def test_sin_login_va_al_login(self):
        respuesta = self.client.get(URL_TABLERO)
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(f"?next={URL_TABLERO}", respuesta["Location"])

    def test_con_solo_operar_403(self):
        """Decisión del PM (RU §4): el operador no ve el tablero."""
        self.client.force_login(self.operador)
        self.assertEqual(self.client.get(URL_TABLERO).status_code, 403)

    def test_supervisar_en_otro_programa_403(self):
        self.client.force_login(self._usuario("sup_becas", [SUPERVISAR], programa=self.becas))
        self.assertEqual(self.client.get(URL_TABLERO).status_code, 403)

    def test_con_supervisar_200_con_los_numeros_y_los_avisos(self):
        self.client.force_login(self.supervisor)
        respuesta = self.client.get(URL_TABLERO)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/emergencia/tablero.html")
        html = respuesta.content.decode()
        self.assertIn('<h1 class="nodo-hero__titulo">Emergencia</h1>', html)
        self.assertIn("<strong>11</strong> casos abiertos", html)
        self.assertIn("<strong>6</strong> plazas libres en 2 dispositivos", html)
        self.assertIn(f'href="{URL_TABLERO}" class="nodo-hero__accion"', html)
        self.assertIn('aria-label="Avisos que piden acción"', html)
        self.assertIn("Familia en la puerta de Escuela 12", html)
        self.assertIn(f'href="/emergencia/casos/?localidad={self.resistencia.pk}"', html)
        self.assertIn(self.en_camino_1.numero, html)
        self.assertEqual(html.count("nodo-stat-tablero "), 6)

    def test_el_sidebar_ofrece_el_tablero_solo_a_quien_supervisa(self):
        self.client.force_login(self.supervisor)
        self.assertContains(self.client.get(URL_TABLERO), "Tablero de Emergencia")
        self.client.force_login(self.operador)
        self.assertNotContains(self.client.get("/emergencia/casos/"), "Tablero de Emergencia")

    def test_el_nombre_del_evento_sale_de_e7(self):
        self.sla.nombre_evento = "Crecida del río"
        self.sla.save()
        self.client.force_login(self.supervisor)
        self.assertContains(self.client.get(URL_TABLERO), '<h1 class="nodo-hero__titulo">Crecida del río</h1>')


# ---------------------------------------------------------------------------
# RN-5.6: presupuesto
# ---------------------------------------------------------------------------


@tag("performance")
class PresupuestoTableroTests(BaseTablero):
    """500 casos abiertos, 50 dispositivos y 200 entregas."""

    CASOS = 500
    DISPOSITIVOS = 50
    ENTREGAS = 200

    def setUp(self):
        super().setUp()
        localidades = [self._localidad(f"Localidad {n}") for n in range(10)]
        dispositivos = Dispositivo.objects.bulk_create(
            [
                Dispositivo(
                    tipo=self.tipo,
                    codigo=f"P-{n:03d}",
                    nombre=f"Dispositivo {n}",
                    estado=Dispositivo.Estado.ACTIVO,
                    localidad=f"Localidad {n % 10}",
                )
                for n in range(self.DISPOSITIVOS)
            ]
        )
        sectores = Sector.objects.bulk_create(
            [Sector(dispositivo=d, nombre="General", capacidad=10) for d in dispositivos]
        )
        Plaza.objects.bulk_create([Plaza(sector=s, codigo=f"C{n:03d}") for s in sectores for n in range(10)])

        personas = Ciudadano.objects.bulk_create(
            [Ciudadano(dni=str(40_000_000 + n), nombre="Rosa", apellido=f"Apellido{n}") for n in range(self.CASOS)]
        )
        grupos = GrupoFamiliar.objects.bulk_create(
            [
                GrupoFamiliar(responsable=p, traslado=GrupoFamiliar.Traslado.BOMBEROS, adultos_f=3, total_declarado=3)
                for p in personas
            ]
        )
        estados = (Estado.NUEVO, Estado.EN_GESTION, Estado.DERIVADO, Estado.INGRESO_EN_CURSO, Estado.ALOJADO)
        casos = []
        for n, grupo in enumerate(grupos):
            estado = estados[n % len(estados)]
            marca = T0 - timedelta(minutes=30 + n)
            casos.append(
                CasoEmergencia(
                    numero=f"2026-{n + 1:06d}",
                    grupo=grupo,
                    origen=Origen.DISPOSITIVO if n % 50 == 0 else Origen.TERRITORIO,
                    estado=estado,
                    prioridad=CasoEmergencia.Prioridad.MEDIA,
                    localidad=localidades[n % 10],
                    direccion="Calle 1",
                    relevado_por=self.agente,
                    relevado_en=marca,
                    tomado_en=marca if estado != Estado.NUEVO else None,
                    derivado_en=marca if estado in (Estado.DERIVADO, Estado.INGRESO_EN_CURSO, Estado.ALOJADO) else None,
                    aceptado_en=marca if estado in (Estado.INGRESO_EN_CURSO, Estado.ALOJADO) else None,
                    alojado_en=marca if estado == Estado.ALOJADO else None,
                    total_alojado=2 if estado == Estado.ALOJADO else None,
                )
            )
        casos = CasoEmergencia.objects.bulk_create(casos)
        derivados = [caso for caso in casos if caso.estado == Estado.DERIVADO]
        Derivacion.objects.bulk_create(
            [
                Derivacion(
                    caso=caso,
                    dispositivo=dispositivos[n % self.DISPOSITIVOS],
                    plazas_pedidas=3,
                    vence_en=T0 + timedelta(minutes=n),
                    derivada_por=self.operador,
                    clave_vigente=caso.pk,
                )
                for n, caso in enumerate(derivados)
            ]
        )
        TrazaCaso.objects.bulk_create(
            [
                TrazaCaso(caso=caso, usuario=self.operador, accion=Accion.DERIVACION_RECHAZADA, detalle="Sin lugar")
                for caso in casos
                if caso.estado == Estado.EN_GESTION
            ]
        )
        item, _creado = TipoKit.objects.get_or_create(nombre="Kit", defaults={"unidad": "kit"})
        entregas = EntregaKit.objects.bulk_create(
            [
                EntregaKit(
                    numero=f"2026-K-{n + 1:06d}",
                    dispositivo=dispositivos[n % self.DISPOSITIVOS],
                    estado=EntregaKit.Estado.EN_CAMINO if n % 2 else EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS,
                    armada_por=self.operador,
                    despachada_en=T0 - timedelta(minutes=n),
                )
                for n in range(self.ENTREGAS)
            ]
        )
        LineaEntrega.objects.bulk_create(
            [LineaEntrega(entrega=e, item=item, unidad="kit", cantidad_enviada=5) for e in entregas]
        )

    def test_rn_5_6_selectores_del_tablero_en_9_consultas(self):
        sla = sla_vigente()
        with self.assertNumQueries(9):
            foto = tablero.foto_del_tablero(sla, T0)
            resumen = tablero.resumen(sla, T0, foto=foto)
            tablero.por_localidad(sla, T0, foto=foto)
            tablero.tiempos(sla, T0, foto=foto)
            entregas, total = tablero.entregas_en_camino(T0)
        self.assertEqual(resumen["hero"]["abiertos"], self.CASOS)
        self.assertEqual(len(foto.red.dispositivos), self.DISPOSITIVOS)
        self.assertEqual((len(entregas), total), (tablero.TOPE_ENTREGAS, self.ENTREGAS // 2))

    def test_rn_5_6_selectores_y_avisos_en_12_o_menos(self):
        """Con los siete avisos encendidos, «en la puerta» suma la única consulta propia."""
        sla = sla_vigente()
        # La capacidad del que mira ya está resuelta en la request (rbac la memoiza en el usuario).
        self.assertTrue(puede_operar_la_mesa(self.supervisor))
        with CaptureQueriesContext(connection) as capturadas:
            foto = tablero.foto_del_tablero(sla, T0)
            tablero.resumen(sla, T0, foto=foto)
            tablero.por_localidad(sla, T0, foto=foto)
            tablero.tiempos(sla, T0, foto=foto)
            tablero.entregas_en_camino(T0)
            avisos = avisos_emergencia.avisos_del_tablero(sla, T0, usuario=self.supervisor, foto=foto)
        self.assertEqual(len(capturadas), 10)
        self.assertLessEqual(len(capturadas), 12)
        self.assertGreaterEqual(len({aviso["regla"] for aviso in avisos}), 5)

    def test_la_vista_completa(self):
        """Presupuesto de E1 entera, con sesión, usuario, permisos, sidebar y el SLA vigente."""
        self.client.force_login(self.supervisor)
        self.client.get(URL_TABLERO)  # calienta la caché de proceso del programa
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(URL_TABLERO)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(capturadas), PRESUPUESTO_VISTA, [q["sql"] for q in capturadas.captured_queries])


#: Lo que cuesta E1 entera con 500 casos abiertos: los 10 del tablero y sus avisos (9 de los
#: selectores y la de «en la puerta»), 1 del SLA vigente y 5 del shell (sesión, usuario, sus
#: grupos, su perfil y sus capacidades, que el sidebar y el mixin comparten memoizadas).
PRESUPUESTO_VISTA = 16
