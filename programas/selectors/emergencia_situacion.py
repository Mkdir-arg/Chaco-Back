"""La foto de situación de Emergencia (E8, análisis 009): lo que leen el Resumen y el Mapa.

Solo lectura: nada de acá escribe, decide una regla ni agrega para mostrar. Las lecturas se hacen
una vez en :func:`foto_de_situacion` y quedan en una :class:`FotoSituacion`. Los indicadores
(resumen, presión por localidad, evolución, capacidad, embudo, perfil, logística y puntos del
mapa) y las reglas (presión, horas hasta saturar, camas cercanas, qué del perfil se muestra) están
en ``programas.services.situacion_emergencia``; las alertas, en
``programas.services.alertas_situacion_emergencia``. Los dos trabajan sobre la foto sin consultas.

Reglas que cruzan el módulo:

* **Puras respecto de ``ahora``** (RNF-009-07): llega por parámetro; nada llama a ``now()``.
* **Sin ``Trunc*`` ni ``CONVERT_TZ``** (RN-009-02, RNF-009-05): los días operativos y los bloques
  de 6 h se arman en Python con ``emergencia_tablero.dia_operativo`` y se filtra por rango.
* **El filtro no va en el ``WHERE``** (auditoría del PR #1193): se aplica en Python por la
  ``localidad_id`` del caso, sobre la misma foto. Así AE-1, AE-5, AE-6 y AE-7 salen de la foto
  provincial, y filtrar no agrega consultas.
* **Capacidad siempre provincial** (RN-009-12): ``Dispositivo.localidad`` es texto libre.
* **No nominal** (RNF-009-01): la foto no lee nombres, DNI, direcciones, números de caso ni
  coordenadas de familias.

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
**Foto**                              **12**; los indicadores y las alertas, 0
====================================  ======================================================
"""

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from django.db.models import BooleanField, Count, ExpressionWrapper, Max, Q, Sum

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
from programas.selectors.emergencia import estado_sla
from programas.selectors.emergencia_tablero import Red, dia_operativo, red_de_dispositivos

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

#: Las últimas horas sobre las que se lee el ritmo de ingresos y egresos en camas (RN-009-07).
HORAS_DEL_RITMO = 6

#: Los abiertos sin alojar: lo que espera lugar (§5.1).
ESTADOS_ESPERANDO = (Estado.NUEVO, Estado.EN_GESTION, Estado.DERIVADO, Estado.INGRESO_EN_CURSO)


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


def _como_dict(valor):
    """Un JSON leído como dict (``necesidades``, ``avisos_salud``): un motor lo puede devolver como texto."""

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
        CasoEmergencia.objects.filter(CasoEmergencia.q_en_la_ventana(desde_lectura))
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
                necesidades=_como_dict(fila[20]),
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
        PersonaAlojada(
            confirmada, egresado, nacimiento, localidad_id, localidad or "", dispositivo_id, _como_dict(avisos)
        )
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
    con_gente = _con_gente(ids_con_gente, sla.inicio_evento)
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
