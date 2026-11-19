"""La foto de situación de Emergencia (E8, análisis 009): lo que leen el Resumen y el Mapa.

Nada de acá escribe ni decide una regla de negocio: las lecturas se hacen una vez en
:func:`foto_de_situacion` y los derivados (:func:`resumen`, :func:`presion_por_localidad`,
:func:`evolucion`, :func:`capacidad`, :func:`embudo`, :func:`perfil`, :func:`logistica` y
:func:`puntos_del_mapa`) agregan sobre ella **sin consultas**. Las reglas (presión, horas hasta
saturar, camas cercanas, qué del perfil se muestra) están en
``programas.services.situacion_emergencia``; las alertas, en
``programas.services.alertas_situacion_emergencia``.

Reglas que cruzan el módulo:

* **Puras respecto de ``ahora``** (RNF-009-07): llega por parámetro; nada llama a ``now()``.
* **Sin ``Trunc*`` ni ``CONVERT_TZ``** (RN-009-02, RNF-009-05): los días operativos y los bloques
  de 6 h se arman en Python con ``emergencia_tablero.dia_operativo`` y se filtra por rango.
* **El filtro no va en el ``WHERE``** (auditoría del PR #1193): se aplica en Python por la
  ``localidad_id`` del caso, sobre la misma foto. Así AE-1, AE-5, AE-6 y AE-7 salen de la foto
  provincial, y filtrar no agrega consultas.
* **Capacidad siempre provincial** (RN-009-12): ``Dispositivo.localidad`` es texto libre.
* **No nominal** (RNF-009-01): la foto no lee nombres, DNI, direcciones, números de caso ni
  coordenadas de familias. Los puntos del mapa son centroides de localidad y dispositivos no
  reservados (``services.ubicacion_reservada``).

Presupuesto (``programas.tests.test_emergencia_situacion``, ``@tag("performance")``, con 5.000
casos, 3.000 alojados, 50 dispositivos y 500 entregas; ≤ 15, RNF-009-03):

====================================  ======================================================
Casos de la ventana ampliada          1 (abiertos, o alojados o cerrados desde el inicio de
                                      la lectura; sin JSON salvo ``necesidades``)
Red de dispositivos (camas)           4 (``emergencia_tablero.red_de_dispositivos``)
Personas alojadas por la emergencia   1 (solo la sección ``avisos_salud`` de la ficha)
Ritmo de camas de las últimas 6 h     1 (agregado sobre ``Estadia``)
Derivaciones                          1 (pendientes, y rechazadas o vencidas de la cohorte)
Logística                             3 (entregas de la ventana, líneas por ítem, última
                                      recepción de los dispositivos con gente)
Localidades del Chaco con centroide   1
**Foto**                              **12**; los derivados y las alertas, 0
====================================  ======================================================
"""

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from django.db.models import BooleanField, Count, ExpressionWrapper, Max, Q, Sum

from core.edad import edad_en_anios
from core.selectors.geografia import localidades_operativas
from core.services.ubicaciones_localidades import clave
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Dispositivo,
    EntregaKit,
    Estadia,
    IntegranteGrupo,
    LineaEntrega,
    Plaza,
)
from programas.selectors.emergencia import SLA_FUERA, TRAMOS, estado_sla
from programas.selectors.emergencia_tablero import (
    ZONA_OPERATIVA,
    DispositivoDeLaRed,
    Red,
    dia_operativo,
    percentil,
    red_de_dispositivos,
)
from programas.services.emergencia_ficha import sin_dosis
from programas.services.ocupacion import Conteo, tension_de_ocupacion
from programas.services.situacion_emergencia import (
    HORAS_DEL_RITMO,
    ORDEN_DE_PRESION,
    camas_cercanas,
    horas_hasta_saturar,
    nivel_de_presion,
    sin_datos_de_saturacion,
    ubicacion_valida,
)
from programas.services.ubicacion_reservada import separar_por_ubicacion_reservada

Estado = CasoEmergencia.Estado

# ---------------------------------------------------------------------------
# Filtros y ventana
# ---------------------------------------------------------------------------

VENTANA_72H = "72h"
VENTANA_7D = "7d"
#: Por defecto, 72 h (decisión del PM, RF-009-04).
VENTANA_POR_DEFECTO = VENTANA_72H

#: Los bloques de la ventana de 72 h: 6 h alineados a las 06:00 (06, 12, 18 y 00 h).
HORAS_DEL_BLOQUE = 6
BLOQUES_EN_72H = 12
DIAS_EN_7D = 7

#: AE-3 compara las últimas 24 h con las tres 24 h anteriores: la lectura de casos creados
#: cubre siempre 96 h, sea cual sea la ventana elegida (RN-009-09).
VENTANA_DE_ALZA = timedelta(hours=24)
VENTANAS_ANTERIORES_DE_ALZA = 3

#: «Sin entrega recibida en 48 h» (B12, AE-6).
HORAS_SIN_ENTREGA = 48

#: Los abiertos sin alojar: lo que espera lugar (§5.1).
ESTADOS_ESPERANDO = (Estado.NUEVO, Estado.EN_GESTION, Estado.DERIVADO, Estado.INGRESO_EN_CURSO)

#: Las cinco etapas del embudo, por la marca que las alcanza (RN-2.9: el embudo es monótono).
PASOS_DEL_EMBUDO = (
    ("relevados", "creado"),
    ("tomados", "tomado_en"),
    ("derivados", "derivado_en"),
    ("aceptados", "aceptado_en"),
    ("alojados", "alojado_en"),
)

SIN_LOCALIDAD = "Sin localidad"

#: Edades del perfil de alojados (B11): menores de 16, mayores de 60 o más.
EDAD_MENOR = 16
EDAD_MAYOR = 60


@dataclass(frozen=True)
class FiltrosSituacion:
    """Lo que eligió el usuario en la barra de filtros. Lo valida el form de E-5."""

    departamento: str = ""
    localidad_id: int | None = None
    ventana: str = VENTANA_POR_DEFECTO

    @property
    def activos(self):
        return bool((self.departamento or "").strip() or self.localidad_id)


def periodos_de_la_ventana(ahora: datetime, ventana: str = VENTANA_POR_DEFECTO):
    """Los períodos de la evolución, ``[(desde, hasta), …]`` del más viejo al actual. Sin consultas.

    * ``72h``: 12 bloques de 6 h alineados a las 06:00 hora Argentina; el último contiene ``ahora``.
    * ``7d``: 7 días operativos (06:00 a 06:00); el último es el de ``ahora``.

    Se arman en Python (RN-009-02). El inicio del primero es el inicio de la ventana.
    """

    dia_desde, _dia_hasta = dia_operativo(ahora)
    if ventana == VENTANA_7D:
        paso, cantidad, actual = timedelta(days=1), DIAS_EN_7D, dia_desde
    else:
        paso, cantidad = timedelta(hours=HORAS_DEL_BLOQUE), BLOQUES_EN_72H
        actual = dia_desde + paso * int((ahora - dia_desde) // paso)
    primero = actual - paso * (cantidad - 1)
    return tuple((primero + paso * n, primero + paso * (n + 1)) for n in range(cantidad))


# ---------------------------------------------------------------------------
# La foto
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CasoDeLaSituacion:
    """Lo que E8 lee de un caso: marcas, localidad y lo declarado. Nada nominal."""

    id: int
    estado: str
    localidad_id: int | None
    localidad: str
    creado: datetime
    tomado_en: datetime | None
    derivado_en: datetime | None
    aceptado_en: datetime | None
    alojado_en: datetime | None
    cerrado_en: datetime | None
    motivo_cierre: str
    ingreso_directo: bool
    total_declarado: int
    menores: int
    mayores: int
    lactantes: int
    dependientes: int
    mayores_dependientes: int
    necesidades: dict

    @property
    def esperando(self):
        return self.estado in ESTADOS_ESPERANDO


class PersonaAlojada(NamedTuple):
    """Un integrante con estadía: alojado ahora (``egresado_en`` nulo) o egresado en la ventana."""

    confirmada_en: datetime | None
    egresado_en: datetime | None
    fecha_nacimiento: Any
    localidad_id: int | None
    localidad: str
    dispositivo_id: int | None
    avisos_salud: dict


class DerivacionDeLaSituacion(NamedTuple):
    caso_id: int
    dispositivo_id: int
    estado: str
    motivo: str


class EntregaDeLaSituacion(NamedTuple):
    estado: str
    despachada_en: datetime | None
    recibida_en: datetime | None


class ItemEntregado(NamedTuple):
    item: str
    unidad: str
    enviado: int
    recibido: int

    @property
    def diferencia(self):
        return self.recibido - self.enviado


class DispositivoConGente(NamedTuple):
    id: int
    nombre: str
    localidad: str
    reservado: bool
    ultima_recepcion: datetime | None


class LocalidadDelChaco(NamedTuple):
    id: int
    nombre: str
    latitud: Any
    longitud: Any
    departamento: str

    @property
    def con_ubicacion(self):
        return self.latitud is not None and self.longitud is not None


@dataclass(frozen=True)
class FotoSituacion:
    """Lo que leen juntas las funciones de E8 y sus alertas, en :func:`foto_de_situacion`."""

    sla: Any
    ahora: datetime
    filtros: FiltrosSituacion
    periodos: tuple
    #: Todos los casos leídos (provinciales); los de la demanda filtrada, en :attr:`casos_filtrados`.
    casos: tuple[CasoDeLaSituacion, ...]
    red: Red
    alojados: tuple[PersonaAlojada, ...]
    ingresos_6h: int
    egresos_6h: int
    derivaciones: tuple[DerivacionDeLaSituacion, ...]
    entregas: tuple[EntregaDeLaSituacion, ...]
    items_recibidos: tuple[ItemEntregado, ...]
    con_gente: tuple[DispositivoConGente, ...]
    localidades: dict[int, LocalidadDelChaco]
    #: Claves de nombre de más de una ``core.Localidad`` del Chaco (RN-009-05).
    ambiguos: frozenset
    #: ``None`` sin filtro; con filtro, las ``localidad_id`` que entran.
    localidades_del_filtro: frozenset | None
    #: La localidad elegida no es del departamento elegido: se ignora y se avisa (§7).
    localidad_ignorada: bool = False
    semaforos: dict = field(default_factory=dict)

    @property
    def desde(self):
        """Inicio de la ventana elegida (el del primer período)."""

        return self.periodos[0][0]

    @property
    def filtrado(self):
        return self.localidades_del_filtro is not None

    def entra(self, localidad_id):
        return self.localidades_del_filtro is None or localidad_id in self.localidades_del_filtro

    @property
    def casos_filtrados(self):
        return [caso for caso in self.casos if self.entra(caso.localidad_id)]

    @property
    def alojados_ahora(self):
        """Las personas alojadas ahora, de toda la provincia (B1 sin filtro, AE-7)."""

        return [persona for persona in self.alojados if persona.egresado_en is None]

    @property
    def alojados_filtrados(self):
        return [persona for persona in self.alojados if self.entra(persona.localidad_id)]

    @property
    def semaforos_filtrados(self):
        ids = {caso.id for caso in self.casos_filtrados}
        return {pk: semaforo for pk, semaforo in self.semaforos.items() if pk in ids}


def _avisos(valor):
    """La sección ``avisos_salud`` como dict: un motor la puede devolver como texto JSON."""

    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError:
            return {}
    return valor if isinstance(valor, dict) else {}


def _casos(desde_lectura):
    """Una consulta: abiertos, o alojados o cerrados desde ``desde_lectura``. Solo ``necesidades`` de JSON.

    «Creado desde ``desde_lectura``» no va en el ``WHERE``: está implicado. Un caso creado desde
    ahí está abierto o se cerró después de crearse, así que entra por ``cerrado_en``. Así la
    consulta es la misma forma que la ventana de E1 y usa los índices de ``alojado_en`` y
    ``cerrado_en`` (``programas.0128``) con *index merge*.
    """

    filas = (
        CasoEmergencia.objects.filter(
            ~Q(estado=Estado.CERRADO) | Q(alojado_en__gte=desde_lectura) | Q(cerrado_en__gte=desde_lectura)
        )
        .annotate(ingreso_directo=ExpressionWrapper(CasoEmergencia.q_ingreso_directo(), output_field=BooleanField()))
        .order_by("creado", "id")
        .values_list(
            "id",
            "estado",
            "localidad_id",
            "localidad__nombre",
            "creado",
            "tomado_en",
            "derivado_en",
            "aceptado_en",
            "alojado_en",
            "cerrado_en",
            "motivo_cierre",
            "ingreso_directo",
            "grupo__total_declarado",
            "grupo__menores_f",
            "grupo__menores_m",
            "grupo__mayores_f",
            "grupo__mayores_m",
            "grupo__lactantes",
            "grupo__dependientes",
            "grupo__mayores_dependientes",
            "necesidades",
        )
    )
    casos = []
    for fila in filas:
        (pk, estado, localidad_id, localidad, creado, tomado, derivado, aceptado, alojado, cerrado, motivo) = fila[:11]
        (directo, total, menores_f, menores_m, mayores_f, mayores_m, lactantes, dependientes, mayores_dep) = fila[11:20]
        casos.append(
            CasoDeLaSituacion(
                id=pk,
                estado=estado,
                localidad_id=localidad_id,
                localidad=localidad or "",
                creado=creado,
                tomado_en=tomado,
                derivado_en=derivado,
                aceptado_en=aceptado,
                alojado_en=alojado,
                cerrado_en=cerrado,
                motivo_cierre=motivo or "",
                ingreso_directo=bool(directo),
                total_declarado=total or 0,
                menores=(menores_f or 0) + (menores_m or 0),
                mayores=(mayores_f or 0) + (mayores_m or 0),
                lactantes=lactantes or 0,
                dependientes=dependientes or 0,
                mayores_dependientes=mayores_dep or 0,
                necesidades=_avisos(fila[20]),
            )
        )
    return tuple(casos)


def _alojados(desde):
    """Una consulta: integrantes con estadía, alojados ahora o egresados desde ``desde``.

    De la ficha trae **solo** la sección ``avisos_salud`` (transformación de clave: ``JSON_EXTRACT``
    en MySQL y MariaDB, probada en los dos motores por el test ``@tag("mysql")``).
    """

    filas = (
        IntegranteGrupo.objects.filter(estadia__isnull=False)
        .filter(Q(egresado_en__isnull=True) | Q(egresado_en__gte=desde))
        .values_list(
            "confirmada_en",
            "egresado_en",
            "ciudadano__fecha_nacimiento",
            "grupo__caso__localidad_id",
            "grupo__caso__localidad__nombre",
            "estadia__dispositivo_id",
            "ficha__avisos_salud",
        )
    )
    return tuple(
        PersonaAlojada(confirmada, egresado, nacimiento, localidad_id, localidad or "", dispositivo_id, _avisos(avisos))
        for confirmada, egresado, nacimiento, localidad_id, localidad, dispositivo_id, avisos in filas
    )


def _ritmo(red, ahora):
    """Una consulta: estadías en **camas** de los elegibles que ingresaron o egresaron en las últimas 6 h."""

    ids = [dispositivo.id for dispositivo in red.dispositivos]
    if not ids:
        return 0, 0
    desde = ahora - timedelta(hours=HORAS_DEL_RITMO)
    ingreso = Q(fecha_ingreso__gte=desde, fecha_ingreso__lte=ahora)
    egreso = Q(fecha_egreso__gte=desde, fecha_egreso__lte=ahora)
    totales = Estadia.objects.filter(dispositivo_id__in=ids, plaza__tipo=Plaza.Tipo.CAMA).filter(ingreso | egreso)
    totales = totales.aggregate(ingresos=Count("id", filter=ingreso), egresos=Count("id", filter=egreso))
    return totales["ingresos"] or 0, totales["egresos"] or 0


def _derivaciones(desde):
    """Una consulta: las pendientes (provinciales) y las rechazadas o vencidas de la cohorte."""

    Est = Derivacion.Estado
    filas = Derivacion.objects.filter(
        Q(estado=Est.PENDIENTE) | Q(estado__in=(Est.RECHAZADA, Est.VENCIDA), caso__creado__gte=desde)
    ).values_list("caso_id", "dispositivo_id", "estado", "motivo")
    return tuple(DerivacionDeLaSituacion(*fila) for fila in filas)


def _entregas(desde):
    """Una consulta: las despachadas en la ventana y las que siguen en camino."""

    filas = EntregaKit.objects.filter(Q(despachada_en__gte=desde) | Q(estado=EntregaKit.Estado.EN_CAMINO)).values_list(
        "estado", "despachada_en", "recibida_en"
    )
    return tuple(EntregaDeLaSituacion(*fila) for fila in filas)


def _items_recibidos(desde):
    """Una consulta: enviado y recibido por ítem, sobre las entregas recibidas despachadas en la ventana."""

    filas = (
        LineaEntrega.objects.filter(entrega__estado__in=EntregaKit.ESTADOS_RECIBIDOS, entrega__despachada_en__gte=desde)
        .values("item_id", "item__nombre", "item__unidad", "item__orden")
        .annotate(enviado=Sum("cantidad_enviada"), recibido=Sum("cantidad_recibida"))
        .order_by("item__orden", "item__nombre")
    )
    return tuple(
        ItemEntregado(fila["item__nombre"], fila["item__unidad"], fila["enviado"] or 0, fila["recibido"] or 0)
        for fila in filas
    )


def _con_gente(ids, inicio_evento):
    """Una consulta: nombre y última recepción de los dispositivos con gente alojada.

    La última recepción cuenta desde ``SLAEmergencia.inicio_evento`` si está cargado (la regla de
    «nunca recibió» de Abastecimiento, RN-009-19); para «sin entrega en 48 h» da lo mismo.
    """

    if not ids:
        return ()
    recibida = Q(entregas_de_kits__estado__in=EntregaKit.ESTADOS_RECIBIDOS)
    if inicio_evento is not None:
        recibida &= Q(entregas_de_kits__recibida_en__gte=inicio_evento)
    filas = (
        Dispositivo.objects.filter(pk__in=ids)
        .annotate(ultima=Max("entregas_de_kits__recibida_en", filter=recibida))
        .order_by("nombre", "id")
        .values_list("id", "nombre", "localidad", "tipo__ubicacion_reservada", "ultima")
    )
    return tuple(
        DispositivoConGente(pk, nombre, localidad or "", bool(reservado), ultima)
        for pk, nombre, localidad, reservado, ultima in filas
    )


def _localidades():
    """Una consulta: las localidades del Chaco con su centroide y departamento (si tienen)."""

    filas = localidades_operativas().values_list(
        "id", "nombre", "ubicacion__latitud", "ubicacion__longitud", "ubicacion__departamento"
    )
    return {
        pk: LocalidadDelChaco(pk, nombre, lat, lon, departamento or "") for pk, nombre, lat, lon, departamento in filas
    }


def _ambiguos(localidades):
    cuantas = Counter(clave(localidad.nombre) for localidad in localidades.values())
    return frozenset(nombre for nombre, veces in cuantas.items() if veces > 1)


def _filtro(filtros, localidades):
    """``(localidades del filtro o None, localidad ignorada)``. Sin consultas.

    Con departamento, las localidades con centroide de ese departamento (``UbicacionLocalidad``).
    Con localidad, esa sola; si además hay departamento y la localidad no es de él, se ignora la
    localidad y se avisa (§7).
    """

    if not filtros.activos:
        return None, False
    departamento = clave(filtros.departamento)
    del_departamento = frozenset(
        pk for pk, localidad in localidades.items() if departamento and clave(localidad.departamento) == departamento
    )
    if filtros.localidad_id:
        if not departamento or filtros.localidad_id in del_departamento:
            return frozenset({filtros.localidad_id}), False
        return del_departamento, True
    return del_departamento, False


def foto_de_situacion(sla, ahora: datetime, filtros: FiltrosSituacion | None = None) -> FotoSituacion:
    """Todo lo que leen el Resumen, el Mapa y las alertas de E8. **12 consultas fijas.**

    ``sla`` es el ``SLAEmergencia`` vigente (objetivos de los tramos e ``inicio_evento``);
    ``filtros`` no cambia ninguna consulta: se aplica en Python sobre la foto.
    """

    filtros = filtros or FiltrosSituacion()
    periodos = periodos_de_la_ventana(ahora, filtros.ventana)
    desde = periodos[0][0]
    desde_lectura = min(desde, ahora - VENTANA_DE_ALZA * (VENTANAS_ANTERIORES_DE_ALZA + 1))

    casos = _casos(desde_lectura)
    red = red_de_dispositivos(ahora)
    alojados = _alojados(desde)
    ingresos, egresos = _ritmo(red, ahora)
    derivaciones = _derivaciones(desde)
    entregas = _entregas(desde)
    items = _items_recibidos(desde)
    ids_con_gente = sorted({p.dispositivo_id for p in alojados if p.egresado_en is None and p.dispositivo_id})
    con_gente = _con_gente(ids_con_gente, getattr(sla, "inicio_evento", None))
    localidades = _localidades()
    del_filtro, ignorada = _filtro(filtros, localidades)

    semaforos = {}
    for caso in casos:
        semaforo = estado_sla(caso, sla, ahora)
        if semaforo is not None:
            semaforos[caso.id] = semaforo
    return FotoSituacion(
        sla=sla,
        ahora=ahora,
        filtros=filtros,
        periodos=periodos,
        casos=casos,
        red=red,
        alojados=alojados,
        ingresos_6h=ingresos,
        egresos_6h=egresos,
        derivaciones=derivaciones,
        entregas=entregas,
        items_recibidos=items,
        con_gente=con_gente,
        localidades=localidades,
        ambiguos=_ambiguos(localidades),
        localidades_del_filtro=del_filtro,
        localidad_ignorada=ignorada,
        semaforos=semaforos,
    )


# ---------------------------------------------------------------------------
# Derivados (0 consultas)
# ---------------------------------------------------------------------------


def _esperando(foto):
    return [caso for caso in foto.casos_filtrados if caso.esperando]


def _fuera_de_sla(foto, casos):
    return sum(1 for caso in casos if (semaforo := foto.semaforos.get(caso.id)) and semaforo.estado == SLA_FUERA)


def _alojada_en(persona, momento):
    """¿Estaba alojada en ``momento``? Confirmada antes (o en) y sin egreso hasta entonces."""

    return (
        persona.confirmada_en is not None
        and persona.confirmada_en <= momento
        and (persona.egresado_en is None or persona.egresado_en > momento)
    )


def total_de_la_red(foto) -> Conteo:
    """El ``Conteo`` de camas de toda la red (B3, B9): incluye los de ubicación reservada."""

    return foto.red.total


def saturacion(foto):
    """Horas hasta saturar (B4, RN-009-07) con la red provincial; «—» si no hay casos."""

    libres = foto.red.libres
    if not foto.casos:
        return sin_datos_de_saturacion(libres, foto.ingresos_6h, foto.egresos_6h)
    return horas_hasta_saturar(libres, foto.ingresos_6h, foto.egresos_6h)


def resumen(foto):
    """Los cuatro indicadores (B1 a B4), en números. El texto lo escribe la pantalla (E-5).

    B1 y B2 siguen el filtro (por la localidad del caso); B3 y B4 son provinciales.
    """

    ahora = foto.ahora
    dia_desde, _hasta = dia_operativo(ahora)
    alojados = foto.alojados_filtrados
    ahora_alojadas = [persona for persona in alojados if persona.egresado_en is None]
    al_empezar_el_dia = sum(1 for persona in alojados if _alojada_en(persona, dia_desde))
    esperando = _esperando(foto)
    total = total_de_la_red(foto)
    return {
        "hay_casos": bool(foto.casos),
        "filtrado": foto.filtrado,
        "localidad_ignorada": foto.localidad_ignorada,
        "personas_alojadas": {
            "valor": len(ahora_alojadas),
            "dispositivos": len({persona.dispositivo_id for persona in ahora_alojadas}),
            "variacion_del_dia": len(ahora_alojadas) - al_empezar_el_dia,
            "desde": dia_desde,
        },
        "personas_esperando": {
            "valor": sum(caso.total_declarado for caso in esperando),
            "familias": len(esperando),
            "fuera_de_sla": _fuera_de_sla(foto, esperando),
        },
        "camas_libres": {
            "valor": foto.red.libres,
            "reservadas": foto.red.reservadas,
            "conteo": total,
            "tension": tension_de_ocupacion(total),
        },
        "saturacion": saturacion(foto),
    }


def _cercanas_de(foto, localidad_id, nombre):
    localidad = foto.localidades.get(localidad_id)
    latitud = localidad.latitud if localidad else None
    longitud = localidad.longitud if localidad else None
    return camas_cercanas(
        latitud, longitud, clave(localidad.nombre if localidad else nombre), foto.red.dispositivos, foto.ambiguos
    )


def presion_por_localidad(foto):
    """Una fila por localidad con demanda o con personas alojadas (B7, RN-009-04 a 06).

    Por ``localidad_id`` del caso, nunca por nombre. Cada fila: ``localidad_id``, ``localidad``,
    ``departamento``, ``con_ubicacion``, ``familias``, ``personas`` (esperando), ``fuera_de_sla``,
    ``alojadas`` (personas de esa localidad alojadas ahora), ``cercanas``
    (``services.situacion_emergencia.CamasCercanas``) y ``presion`` (``Presion``). Los casos sin
    localidad van a una fila «Sin localidad» sin cercanas ni presión.

    Orden: Crítica, Exigida, Normal, Sin demanda; dentro de cada nivel, el cociente más alto
    primero y las críticas «sin camas a 25 km» después de las que tienen cociente; después, más
    personas esperando.
    """

    filas = {}

    def fila(localidad_id, nombre):
        if localidad_id not in filas:
            localidad = foto.localidades.get(localidad_id)
            filas[localidad_id] = {
                "localidad_id": localidad_id,
                "localidad": nombre or (localidad.nombre if localidad else ""),
                "departamento": localidad.departamento if localidad else "",
                "con_ubicacion": bool(localidad and localidad.con_ubicacion),
                "familias": 0,
                "personas": 0,
                "fuera_de_sla": 0,
                "alojadas": 0,
            }
        return filas[localidad_id]

    for caso in _esperando(foto):
        actual = fila(caso.localidad_id, caso.localidad if caso.localidad_id else SIN_LOCALIDAD)
        actual["familias"] += 1
        actual["personas"] += caso.total_declarado
        if (semaforo := foto.semaforos.get(caso.id)) and semaforo.estado == SLA_FUERA:
            actual["fuera_de_sla"] += 1
    for persona in foto.alojados_filtrados:
        if persona.egresado_en is None:
            pk = persona.localidad_id
            fila(pk, persona.localidad if pk else SIN_LOCALIDAD)["alojadas"] += 1

    resultado = []
    for pk, actual in filas.items():
        if pk is None:
            actual["cercanas"], actual["presion"] = None, None
        else:
            actual["cercanas"] = _cercanas_de(foto, pk, actual["localidad"])
            actual["presion"] = nivel_de_presion(actual["personas"], actual["cercanas"].total)
        resultado.append(actual)

    def orden(actual):
        presion = actual["presion"]
        if presion is None:
            return (len(ORDEN_DE_PRESION), True, 0.0, -actual["personas"], "")
        return (
            ORDEN_DE_PRESION.index(presion.nivel),
            presion.cociente is None,
            -(presion.cociente or 0.0),
            -actual["personas"],
            actual["localidad"].casefold(),
        )

    resultado.sort(key=orden)
    return resultado


def evolucion(foto):
    """Por período de la ventana (B8): casos nuevos, familias alojadas, cerrados sin alojar y
    personas alojadas al cierre (o a ``ahora`` en el período en curso). Con el filtro de demanda.

    ``camas_operativas_hoy`` es la referencia rotulada: la capacidad no tiene historia (§4.1).
    """

    casos = foto.casos_filtrados
    alojados = foto.alojados_filtrados
    periodos = []
    for desde, hasta in foto.periodos:
        corte = min(hasta, foto.ahora)
        periodos.append(
            {
                "desde": desde,
                "hasta": hasta,
                "en_curso": hasta > foto.ahora,
                "casos_nuevos": sum(1 for caso in casos if desde <= caso.creado < hasta),
                "familias_alojadas": sum(
                    1 for caso in casos if caso.alojado_en is not None and desde <= caso.alojado_en < hasta
                ),
                "cerrados_sin_alojar": sum(
                    1
                    for caso in casos
                    if caso.alojado_en is None and caso.cerrado_en is not None and desde <= caso.cerrado_en < hasta
                ),
                "personas_alojadas_al_cierre": sum(1 for persona in alojados if _alojada_en(persona, corte)),
            }
        )
    return {
        "por_bloques": foto.filtros.ventana != VENTANA_7D,
        "periodos": periodos,
        "camas_operativas_hoy": total_de_la_red(foto).operativas,
    }


def _pendientes_por_dispositivo(foto):
    return Counter(d.dispositivo_id for d in foto.derivaciones if d.estado == Derivacion.Estado.PENDIENTE)


def _sin_ubicacion(dispositivos):
    return sum(1 for d in dispositivos if not ubicacion_valida(d.latitud, d.longitud))


class Tensionado(NamedTuple):
    """Un dispositivo publicable con su tensión **de su tipo** (B9 y AE-5)."""

    dispositivo: DispositivoDeLaRed
    tension: Any
    derivaciones_pendientes: int

    @property
    def exceso(self):
        """``porcentaje − umbral rojo`` del tipo: el orden de «más tensionados» (como Dispositivos)."""

        return self.tension.porcentaje - self.dispositivo.tipo.umbral_ocupacion_rojo


def tensionados(foto):
    """Los dispositivos publicables con cifra, del más al menos tensionado. Sin reservados (RN-009-13)."""

    pendientes = _pendientes_por_dispositivo(foto)
    publicables, _reservados = separar_por_ubicacion_reservada(foto.red.dispositivos)
    filas = [
        Tensionado(d, tension_de_ocupacion(d.conteo, tipo=d.tipo), pendientes.get(d.id, 0))
        for d in publicables
        if d.conteo is not None
    ]
    filas = [fila for fila in filas if fila.tension.hay_cifra]
    filas.sort(key=lambda f: (-f.exceso, -f.tension.porcentaje, f.dispositivo.nombre, f.dispositivo.id))
    return filas


#: Cuántos «más tensionados» muestra B9.
TOPE_TENSIONADOS = 5


def capacidad(foto):
    """Capacidad de la red en camas (B9), siempre provincial (RN-009-12).

    ``total`` (``Conteo``) y ``tension`` (corte general 60/80) incluyen los dispositivos de
    ubicación reservada; ``mas_tensionados`` no los nombra.
    """

    total = total_de_la_red(foto)
    return {
        "total": total,
        "tension": tension_de_ocupacion(total),
        "libres": foto.red.libres,
        "reservadas": foto.red.reservadas,
        "fuera_de_servicio": total.fuera_de_servicio,
        "dispositivos": len(foto.red.dispositivos),
        "sin_ubicacion": _sin_ubicacion(foto.red.dispositivos),
        "mas_tensionados": tensionados(foto)[:TOPE_TENSIONADOS],
    }


def _mediana(valores):
    return statistics.median(valores) if valores else None


def embudo(foto):
    """El embudo de la cohorte (B10, RN-009-08): casos **creados en la ventana**, sin ingresos directos.

    ``pasos``: relevados, tomados, derivados, aceptados y alojados, cada uno con ``casos`` y la
    ``conversion`` (% sobre el paso anterior, ``None`` si el anterior es 0). ``tramos``: por
    tramo, cuántos casos de la cohorte lo completaron, mediana y p90 en minutos y el objetivo de
    E7. Salidas: cerrados sin alojar por motivo, derivaciones rechazadas (por motivo) y vencidas
    de la cohorte, e ingresos directos aparte. Con el filtro de demanda.
    """

    creados = [caso for caso in foto.casos_filtrados if foto.desde <= caso.creado < foto.ahora]
    cohorte = [caso for caso in creados if not caso.ingreso_directo]
    pasos, anterior = [], None
    for paso, marca in PASOS_DEL_EMBUDO:
        cantidad = sum(1 for caso in cohorte if getattr(caso, marca) is not None)
        conversion = int(round(cantidad * 100 / anterior)) if anterior else None
        pasos.append({"paso": paso, "casos": cantidad, "conversion": conversion})
        anterior = cantidad
    tramos = []
    for tramo, abre, cierra, campo in TRAMOS:
        valores = sorted(
            max((getattr(c, cierra) - getattr(c, abre)).total_seconds(), 0) / 60
            for c in cohorte
            if getattr(c, abre) is not None and getattr(c, cierra) is not None
        )
        tramos.append(
            {
                "tramo": tramo,
                "casos": len(valores),
                "mediana_min": _mediana(valores),
                "p90_min": percentil(valores),
                "objetivo_min": getattr(foto.sla, campo),
            }
        )
    ids = {caso.id for caso in cohorte}
    cerrados = Counter(
        CasoEmergencia.MotivoCierre(c.motivo_cierre).label
        if c.motivo_cierre in CasoEmergencia.MotivoCierre.values
        else "Otro"
        for c in cohorte
        if c.estado == Estado.CERRADO and c.alojado_en is None
    )
    rechazadas = Counter(
        d.motivo or "Otro" for d in foto.derivaciones if d.caso_id in ids and d.estado == Derivacion.Estado.RECHAZADA
    )
    return {
        "hay_casos": bool(cohorte),
        "pasos": pasos,
        "tramos": tramos,
        "cerrados_sin_alojar": {"total": sum(cerrados.values()), "por_motivo": dict(cerrados.most_common())},
        "rechazadas": {"total": sum(rechazadas.values()), "por_motivo": dict(rechazadas.most_common())},
        "vencidas": sum(1 for d in foto.derivaciones if d.caso_id in ids and d.estado == Derivacion.Estado.VENCIDA),
        "ingresos_directos": sum(1 for caso in creados if caso.ingreso_directo),
    }


def _contar_alojados(personas, ahora):
    hoy = ahora.astimezone(ZONA_OPERATIVA).date()
    conteo = defaultdict(int)
    for persona in personas:
        conteo["personas"] += 1
        edad = edad_en_anios(persona.fecha_nacimiento, hoy)
        if edad is None:
            conteo["edad_sin_dato"] += 1
        elif edad < EDAD_MENOR:
            conteo["menores"] += 1
        elif edad >= EDAD_MAYOR:
            conteo["mayores"] += 1
        avisos = persona.avisos_salud
        for clave_aviso in ("embarazo", "discapacidad", "electrodependiente", "medicacion_critica"):
            if avisos.get(clave_aviso) is True:
                conteo[clave_aviso] += 1
        if sin_dosis(avisos):
            conteo["sin_dosis"] += 1
    return conteo


def _contar_esperando(casos):
    conteo = defaultdict(int)
    for caso in casos:
        conteo["personas"] += caso.total_declarado
        conteo["familias"] += 1
        for clave_grupo in ("menores", "mayores", "lactantes", "dependientes", "mayores_dependientes"):
            conteo[clave_grupo] += getattr(caso, clave_grupo)
        for necesidad, clave_familias in (
            ("embarazo", "familias_embarazo"),
            ("electrodependiente", "familias_electrodependencia"),
            ("medicacion_critica", "familias_medicacion_critica"),
            ("mascotas", "familias_mascotas"),
        ):
            if caso.necesidades.get(necesidad):
                conteo[clave_familias] += 1
    return conteo


_CLAVES_DE_ALOJADOS = (
    "personas",
    "menores",
    "mayores",
    "edad_sin_dato",
    "embarazo",
    "discapacidad",
    "electrodependiente",
    "medicacion_critica",
    "sin_dosis",
)
_CLAVES_DE_ESPERANDO = (
    "personas",
    "familias",
    "menores",
    "mayores",
    "lactantes",
    "dependientes",
    "mayores_dependientes",
    "familias_embarazo",
    "familias_electrodependencia",
    "familias_medicacion_critica",
    "familias_mascotas",
)


def perfil(foto):
    """El perfil agregado (B11), **exacto**, con el filtro de demanda.

    ``{"alojados": {...}, "esperando": {...}}``. Alojados (Formulario 2): personas, menores de 16,
    mayores de 60, edad sin dato y, de ``avisos_salud``, embarazo, discapacidad,
    electrodependiente, medicación crítica y sin dosis (``emergencia_ficha.sin_dosis``). Esperando
    (Formulario 1, declarado): personas, familias, menores, mayores, lactantes, dependientes,
    mayores dependientes y familias con embarazo, electrodependencia, medicación crítica y
    mascotas. **Lo que se muestra** lo decide ``services.situacion_emergencia.presentar_perfil``
    (RN-009-11): este dict no va al template.
    """

    alojados = _contar_alojados([p for p in foto.alojados_filtrados if p.egresado_en is None], foto.ahora)
    esperando = _contar_esperando(_esperando(foto))
    return {
        "alojados": {clave_: alojados.get(clave_, 0) for clave_ in _CLAVES_DE_ALOJADOS},
        "esperando": {clave_: esperando.get(clave_, 0) for clave_ in _CLAVES_DE_ESPERANDO},
    }


def sin_dosis_provincial(foto):
    """Personas alojadas ahora con medicación crítica sin dosis, **sin filtro** (AE-7, RN-009-11)."""

    return sum(1 for persona in foto.alojados_ahora if sin_dosis(persona.avisos_salud))


def sin_entrega_reciente(foto):
    """Dispositivos con gente alojada y sin entrega recibida en 48 h (B12, AE-6), provincial.

    Cada fila: ``id``, ``nombre`` y ``localidad`` (vacíos si es de ubicación reservada),
    ``reservado``, ``personas``, ``ultima_recepcion`` y ``horas`` desde ella (``None`` si nunca).
    Primero los que nunca recibieron, después la recepción más vieja.
    """

    limite = foto.ahora - timedelta(hours=HORAS_SIN_ENTREGA)
    personas = Counter(p.dispositivo_id for p in foto.alojados_ahora)
    filas = []
    for dispositivo in foto.con_gente:
        ultima = dispositivo.ultima_recepcion
        if ultima is not None and ultima >= limite:
            continue
        filas.append(
            {
                "id": dispositivo.id,
                "nombre": "" if dispositivo.reservado else dispositivo.nombre,
                "localidad": "" if dispositivo.reservado else dispositivo.localidad,
                "reservado": dispositivo.reservado,
                "personas": personas.get(dispositivo.id, 0),
                "ultima_recepcion": ultima,
                "horas": None if ultima is None else int((foto.ahora - ultima).total_seconds() // 3600),
            }
        )
    filas.sort(key=lambda f: (f["ultima_recepcion"] is not None, f["ultima_recepcion"] or foto.ahora, f["id"]))
    return filas


def logistica(foto):
    """Logística de kits de la ventana (B12), provincial.

    Entregas despachadas en la ventana por estado; recibidas y con diferencias; en camino (todas,
    ahora); tránsito mediano en minutos de las recibidas; enviado y recibido por ítem; y los
    dispositivos con gente sin entrega recibida en 48 h.
    """

    Est = EntregaKit.Estado
    de_la_ventana = [e for e in foto.entregas if e.despachada_en is not None and e.despachada_en >= foto.desde]
    recibidas = [e for e in de_la_ventana if e.estado in EntregaKit.ESTADOS_RECIBIDOS]
    transitos = sorted(
        max((e.recibida_en - e.despachada_en).total_seconds(), 0) / 60 for e in recibidas if e.recibida_en is not None
    )
    return {
        "despachadas": len(de_la_ventana),
        "por_estado": dict(Counter(e.estado for e in de_la_ventana)),
        "recibidas": len(recibidas),
        "con_diferencias": sum(1 for e in recibidas if e.estado == Est.RECIBIDA_CON_DIFERENCIAS),
        "en_camino": sum(1 for e in foto.entregas if e.estado == Est.EN_CAMINO),
        "transito_mediano_min": _mediana(transitos),
        "por_item": list(foto.items_recibidos),
        "sin_entrega_48h": sin_entrega_reciente(foto),
    }


def puntos_del_mapa(foto):
    """Lo que viaja al mapa (B6): **centroides de localidad** y **dispositivos no reservados**.

    Nunca una coordenada de un caso (RNF-009-01) ni un dispositivo de ubicación reservada
    (RN-009-13): se filtran acá, no en el template. ``localidades``: las filas de presión con
    centroide (con el filtro de demanda). ``dispositivos``: los publicables con ubicación válida,
    con su nivel de tensión **de su tipo**. Y los contadores del pie: dispositivos sin ubicación,
    reservados y casos (familias esperando) de localidades sin ubicación o sin localidad.
    """

    localidades = []
    casos_sin_ubicacion = 0
    for fila in presion_por_localidad(foto):
        localidad = foto.localidades.get(fila["localidad_id"]) if fila["localidad_id"] else None
        if localidad is None or not localidad.con_ubicacion:
            casos_sin_ubicacion += fila["familias"]
            continue
        localidades.append(
            {
                "localidad_id": localidad.id,
                "nombre": fila["localidad"],
                "latitud": float(localidad.latitud),
                "longitud": float(localidad.longitud),
                "personas": fila["personas"],
                "familias": fila["familias"],
                "nivel": fila["presion"].nivel,
                "cociente": fila["presion"].cociente,
            }
        )
    publicables, reservados = separar_por_ubicacion_reservada(foto.red.dispositivos)
    dispositivos = []
    for d in publicables:
        if not ubicacion_valida(d.latitud, d.longitud):
            continue
        tension = tension_de_ocupacion(d.conteo, tipo=d.tipo) if d.conteo is not None else None
        dispositivos.append(
            {
                "id": d.id,
                "nombre": d.nombre,
                "latitud": float(d.latitud),
                "longitud": float(d.longitud),
                "libres": d.libres,
                "nivel": tension.nivel if tension else None,
                "porcentaje": tension.porcentaje if tension else None,
            }
        )
    return {
        "localidades": localidades,
        "dispositivos": dispositivos,
        "dispositivos_sin_ubicacion": _sin_ubicacion(publicables),
        "dispositivos_reservados": len(reservados),
        "casos_sin_ubicacion": casos_sin_ubicacion,
    }
