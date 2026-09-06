"""Métricas del dashboard del Programa Becas (análisis #366, Cambio 64).

Una sola fuente para la solapa, el endpoint JSON y las exportaciones: todo lo que
se muestra sale de :func:`metricas` (o de :func:`metricas_cacheadas`) y de
:func:`distribucion_respuestas`. El módulo no inventa reglas de dominio: lee lo que
el sistema ya guarda, con el mismo alcance por rol que el resto de Becas
(`programas/services/autorizacion.py`), y nunca parte de ``Formulario.objects.all()``.

Reglas del análisis que gobiernan cada bloque (RN-N) están citadas en su función.

Ojo con la palabra ``programa``: acá es siempre el **ProgramaSiis** de la pantalla
(``/becas/config/programas/<pk>/``). Las funciones de ``autorizacion`` reciben otro
``programa`` —el ``Programa`` del RBAC que ancla los roles de Becas— y resuelven el
suyo solas; pasarles el ProgramaSiis vacía el alcance. Por eso se las llama sin ese
argumento y el recorte por ProgramaSiis se hace después, con ``filter``.

Estrategia de consultas (Cambio 64, corrección de performance): el alcance se
resuelve **una sola vez** a listas de ids (segmentos, convocatorias, relevamientos)
y todo lo demás filtra por ``relevamiento_id IN (...)`` plano, sin subconsultas
anidadas. Una única consulta agrupada por (relevamiento, estado) alimenta los
estados, los canales, la tabla de convocatorias y la producción territorial. Las
respuestas se extraen en SQL por clave del JSON (``JSON_EXTRACT``) en vez de
decodificar cada documento en Python, y también se cachean. En producción el driver
corta cualquier consulta que pase los 10 s (``read_timeout``): cada consulta de acá
tiene que ser trivial para el motor.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Exists, F, Func, JSONField, OuterRef, Q, Sum, Value
from django.utils import timezone

from programas.models import (
    Convocatoria,
    Formulario,
    ListaEspera,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
    ValidacionSIS,
)
from programas.services.autorizacion import (
    convocatorias_visibles,
    es_coordinador_regional_becas,
    segmentos_visibles,
    subsegmentos_a_cargo,
    subsegmentos_visibles,
)
from programas.services.reportes import Reporte

logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 300  # RN-17: hasta 5 minutos de antigüedad
CACHE_PREFIX = "becas:dashboard"
TOP_TERRITORIALES = 8
TOP_LOCALIDADES = 7
SIN_LOCALIDAD = "Sin localidad"
OTRAS_LOCALIDADES = "Otras"

RELEVAMIENTOS_EN_CURSO = (Relevamiento.Estado.EN_CURSO, Relevamiento.Estado.FINALIZANDO)


# ---------------------------------------------------------------------------
# Filtros y resultado
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Filtros:
    """Recorte único que gobierna toda la solapa (RN-4).

    ``desde``/``hasta`` acotan por ``Formulario.creado`` (RN-7); los demás campos
    son estructurales. ``canal`` es un valor de ``Relevamiento.Tipo`` o ``None``.
    """

    desde: date | None = None
    hasta: date | None = None
    segmento_id: int | None = None
    convocatoria_id: int | None = None
    relevamiento_id: int | None = None
    canal: str | None = None

    @property
    def con_ventana(self):
        return self.desde is not None and self.hasta is not None

    def clave(self):
        return json.dumps(asdict(self), default=str, sort_keys=True)


@dataclass
class Indicadores:
    convocatorias_total: int = 0
    convocatorias_activas: int = 0
    convocatorias_cerradas_vencimiento: int = 0
    relevamientos_total: int = 0
    relevamientos_en_curso: int = 0
    relevamientos_publicos: int = 0
    formularios_recibidos: int = 0
    variacion_periodo_anterior: int | None = None  # RN-8: porcentaje entero o None
    aprobados: int = 0
    tasa_aprobacion: float = 0.0
    pendientes: int = 0
    cupo_total: int = 0  # RN-9: del segmento, sin ventana
    cupo_ocupado: int = 0
    lista_espera: int = 0  # RN-11: no promovidos


@dataclass
class Datos:
    programa_id: int
    programa_nombre: str
    filtros: dict
    alcance: str
    calculado_en: str
    indicadores: Indicadores = field(default_factory=Indicadores)
    serie_semanal: list = field(default_factory=list)
    estados: list = field(default_factory=list)
    canales: list = field(default_factory=list)
    convocatorias: list = field(default_factory=list)
    relevamientos_por_estado: list = field(default_factory=list)
    embudo: list = field(default_factory=list)
    territoriales: list = field(default_factory=list)
    localidades: dict = field(default_factory=lambda: {"top": [], "detalle": []})

    def to_dict(self):
        return asdict(self)


@dataclass
class Pregunta:
    clave: str
    texto: str
    tipo: str
    origen: str
    opciones: list
    multiple: bool


@dataclass
class Distribucion:
    clave: str
    texto: str
    tipo: str
    origen: str
    multiple: bool
    base: int
    opciones: list  # [{"opcion", "total", "pct"}]

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Alcance:
    """El recorte ya resuelto a ids: se calcula una vez por petición y lo comparten
    la clave de caché, las métricas y las respuestas.

    ``relevamientos`` es una tupla de dicts ``{id, convocatoria_id, tipo,
    territorial_id, estado}``: la estructura es chica (decenas o cientos de filas) y
    con ella se derivan en Python los cortes por convocatoria, canal y territorial
    sin volver a consultar.
    """

    segmento_ids: tuple
    convocatoria_ids: tuple
    relevamientos: tuple
    regional: bool
    huella: str

    @property
    def relevamiento_ids(self):
        return tuple(r["id"] for r in self.relevamientos)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _aware_start(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min), timezone.get_current_timezone())


def _pct(parte, total, decimales=1):
    if not total:
        return 0.0
    return round(parte * 100 / total, decimales)


def _fecha_local(valor):
    if isinstance(valor, datetime):
        return timezone.localtime(valor).date()
    return valor


def _lunes(fecha):
    return fecha - timedelta(days=fecha.weekday())


def _iso(fecha):
    """Una fecha cero de MySQL (``0000-00-00``, admitida por el sql_mode de prod)
    llega como None: no puede tirar el tablero."""
    return fecha.isoformat() if fecha else ""


# ---------------------------------------------------------------------------
# Alcance (RN-3): una vez por petición
# ---------------------------------------------------------------------------
def resolver_alcance(user, programa, filtros):
    """Segmentos, convocatorias y relevamientos del recorte, como ids.

    Reusa las funciones de ``autorizacion`` (nunca se redefine quién ve qué) pero
    materializa el resultado: de acá en adelante todas las consultas filtran por
    listas planas de ids en vez de subconsultas anidadas.
    """
    visibles = tuple(segmentos_visibles(user).filter(programa=programa).order_by("pk").values_list("pk", flat=True))
    regional = es_coordinador_regional_becas(user)
    subsegmentos = tuple(subsegmentos_a_cargo(user).order_by("pk").values_list("pk", flat=True)) if regional else ()
    huella = f"s{list(visibles)}|ss{list(subsegmentos)}"

    convs = convocatorias_visibles(user).filter(segmento__programa=programa)
    if filtros.segmento_id:
        convs = convs.filter(segmento_id=filtros.segmento_id)
    if filtros.convocatoria_id:
        convs = convs.filter(pk=filtros.convocatoria_id)
    conv_rows = list(convs.order_by().values_list("pk", "segmento_id"))
    conv_ids = [pk for pk, _ in conv_rows]

    rels = Relevamiento.objects.filter(convocatoria_id__in=conv_ids)
    if filtros.relevamiento_id:
        rels = rels.filter(pk=filtros.relevamiento_id)
    if filtros.canal:
        rels = rels.filter(tipo=filtros.canal)
    rel_rows = tuple(rels.order_by().values("id", "convocatoria_id", "tipo", "territorial_id", "estado"))

    # Con filtro de relevamiento, la convocatoria en alcance es solo la de ese relevamiento.
    if filtros.relevamiento_id:
        conv_ids = sorted({r["convocatoria_id"] for r in rel_rows})
    segmento_ids = tuple(sorted({seg for pk, seg in conv_rows if pk in set(conv_ids)} & set(visibles)))
    if filtros.segmento_id and not filtros.convocatoria_id and not filtros.relevamiento_id:
        # Un segmento sin convocatorias todavía sigue estando en el alcance (cupo, tabla vacía).
        segmento_ids = tuple(s for s in visibles if s == filtros.segmento_id)
    elif not filtros.segmento_id and not filtros.convocatoria_id and not filtros.relevamiento_id:
        segmento_ids = visibles
    return Alcance(
        segmento_ids=segmento_ids,
        convocatoria_ids=tuple(conv_ids),
        relevamientos=rel_rows,
        regional=regional,
        huella=huella,
    )


def _formularios(alcance, desde=None, hasta=None):
    """Queryset base de formularios del recorte: un IN plano de relevamientos."""
    ids = alcance.relevamiento_ids
    if not ids:
        return Formulario.objects.none()
    qs = Formulario.objects.filter(relevamiento_id__in=ids)
    if desde:
        qs = qs.filter(creado__gte=_aware_start(desde))
    if hasta:
        qs = qs.filter(creado__lt=_aware_start(hasta + timedelta(days=1)))
    return qs.order_by()  # sin el ORDER BY -creado del Meta.ordering: acá solo se agrega


# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------
def _serie_semanal(formularios, filtros):
    """Formularios por semana (lunes a domingo). Rellena las semanas vacías para que
    el gráfico no salte fechas (RN-7).

    Se agrupa en Python y no con ``TruncWeek``: sobre un ``DateTimeField`` con
    ``USE_TZ`` Django traduce el truncado a ``CONVERT_TZ`` en MySQL, y si el servidor
    no tiene cargadas las tablas de zona horaria devuelve NULL y Django corta con
    «Database returned an invalid datetime value» solo en producción. Traer las
    fechas del recorte (ya acotado por filtros) y contar acá no depende de nada.
    """
    por_semana = Counter()
    for creado in formularios.values_list("creado", flat=True).iterator(chunk_size=5000):
        if creado is not None:
            por_semana[_lunes(_fecha_local(creado))] += 1
    if filtros.con_ventana:
        inicio, fin = _lunes(filtros.desde), _lunes(filtros.hasta)
    elif por_semana:
        inicio, fin = min(por_semana), max(por_semana)
    else:
        return []
    serie = []
    lunes = inicio
    while lunes <= fin:
        serie.append(
            {
                "semana": lunes.isoformat(),
                "hasta": (lunes + timedelta(days=6)).isoformat(),
                "total": por_semana.get(lunes, 0),
            }
        )
        lunes += timedelta(days=7)
    return serie


def _con_choices(conteo, choices):
    """Lista ordenada según los choices del modelo, con todos los valores presentes (aunque valgan 0)."""
    return [{"clave": valor, "etiqueta": str(etiqueta), "total": conteo.get(valor, 0)} for valor, etiqueta in choices]


def _variacion(alcance, filtros, total_actual):
    """RN-8: contra el período inmediatamente anterior de la misma longitud."""
    if not filtros.con_ventana:
        return None
    longitud = (filtros.hasta - filtros.desde).days + 1
    anterior_hasta = filtros.desde - timedelta(days=1)
    anterior_desde = anterior_hasta - timedelta(days=longitud - 1)
    total_anterior = _formularios(alcance, anterior_desde, anterior_hasta).count()
    if not total_anterior:
        return None
    return round((total_actual - total_anterior) * 100 / total_anterior)


def _cupo(user, alcance):
    """RN-9: cupo del segmento contra aprobados históricos, sin ventana. El
    coordinador regional mide contra lo distribuido en sus subsegmentos, como
    ``reporte_cupos``. Devuelve ``{segmento_id: (cupo, ocupado)}``."""
    ids = list(alcance.segmento_ids)
    if not ids:
        return {}
    if alcance.regional:
        cupos = dict(
            subsegmentos_a_cargo(user)
            .filter(segmento_id__in=ids)
            .values("segmento_id")
            .annotate(total=Sum("cupo_maximo"))
            .order_by()
            .values_list("segmento_id", "total")
        )
    else:
        cupos = dict(Segmento.objects.filter(pk__in=ids).order_by().values_list("pk", "cupo_maximo"))
    # Todas las convocatorias visibles de esos segmentos, sin filtro de convocatoria ni de período: el cupo es del segmento.
    conv_ids = list(convocatorias_visibles(user).filter(segmento_id__in=ids).order_by().values_list("pk", flat=True))
    ocupados = {}
    if conv_ids:
        ocupados = dict(
            Formulario.objects.filter(relevamiento__convocatoria_id__in=conv_ids, estado=Formulario.Estado.APROBADO)
            .order_by()
            .values("relevamiento__convocatoria__segmento_id")
            .annotate(total=Count("pk"))
            .values_list("relevamiento__convocatoria__segmento_id", "total")
        )
    return {pk: (cupos.get(pk) or 0, ocupados.get(pk, 0)) for pk in ids}


def _estado_convocatoria(conv):
    if conv.activo:
        return "Activa"
    return "Cerrada por vencimiento" if conv.cerrada_automaticamente else "Cerrada"


def _tabla_convocatorias(alcance, forms_por_conv, cupos):
    rels_por_conv = defaultdict(Counter)
    for r in alcance.relevamientos:
        rels_por_conv[r["convocatoria_id"]][r["estado"]] += 1
    filas = []
    convocatorias = (
        Convocatoria.objects.filter(pk__in=alcance.convocatoria_ids)
        .select_related("segmento", "subsegmento")
        .order_by("-fecha_inicio", "nombre")
    )
    for conv in convocatorias:
        rels = rels_por_conv.get(conv.pk, Counter())
        forms = forms_por_conv.get(conv.pk, Counter())
        recibidos = sum(forms.values())
        aprobados = forms.get(Formulario.Estado.APROBADO, 0)
        rechazados = forms.get(Formulario.Estado.RECHAZADO, 0)
        bajas = forms.get(Formulario.Estado.BAJA, 0)
        revisados = aprobados + rechazados + bajas
        cupo, ocupado = cupos.get(conv.segmento_id, (0, 0))
        filas.append(
            {
                "id": conv.pk,
                "nombre": conv.nombre,
                "segmento": getattr(conv.segmento, "nombre", ""),
                "subsegmento": getattr(conv.subsegmento, "nombre", "") if conv.subsegmento_id else "",
                "estado": _estado_convocatoria(conv),
                "activa": conv.activo,
                "fecha_inicio": _iso(conv.fecha_inicio),
                "fecha_fin": _iso(conv.fecha_fin),
                "relevamientos": sum(rels.values()),
                "en_curso": sum(rels.get(e, 0) for e in RELEVAMIENTOS_EN_CURSO),
                "recibidos": recibidos,
                "aprobados": aprobados,
                "rechazados": rechazados,
                "bajas": bajas,
                "pendientes": forms.get(Formulario.Estado.ENVIADO, 0),
                "revisado_pct": _pct(revisados, recibidos),
                "cupo_segmento": cupo,
                "cupo_ocupado": ocupado,
            }
        )
    return filas


def _siis_ok(formularios):
    """Formularios cuya **última** validación SIIS es OK. Un anti-join sobre
    ValidacionSIS (no hay otra validación posterior del mismo formulario) en vez de
    una subconsulta correlacionada por cada formulario del recorte."""
    posterior = ValidacionSIS.objects.filter(formulario_id=OuterRef("formulario_id")).filter(
        Q(creado__gt=OuterRef("creado")) | Q(creado=OuterRef("creado"), pk__gt=OuterRef("pk"))
    )
    return (
        ValidacionSIS.objects.filter(formulario__in=formularios.values("pk"), estado=ValidacionSIS.Estado.OK)
        .annotate(hay_posterior=Exists(posterior))
        .filter(hay_posterior=False)
        .count()
    )


def _embudo(formularios, total, aprobados, rechazados, lista_espera, identidad):
    """Etapas ordenadas del circuito; «Beneficiarios» no se repite porque es el mismo
    número que «Aprobados» (inconsistencia 2 del análisis)."""
    siis_ok = _siis_ok(formularios) if total else 0
    etapas = (
        ("Formularios recibidos", total),
        ("Identidad validada", identidad),
        ("Aprobados", aprobados),
        ("Validación SIIS OK", siis_ok),
        ("En lista de espera", lista_espera),
        ("Rechazados", rechazados),
    )
    return [{"etapa": etapa, "total": cantidad, "pct": _pct(cantidad, total)} for etapa, cantidad in etapas]


def _territoriales(alcance, forms_por_rel):
    """RN-12: solo canal territorial; un público no tiene territorial. Se deriva del
    agrupado por relevamiento: una sola consulta extra, la de los nombres."""
    por_terr = defaultdict(lambda: {"formularios": 0, "aprobados": 0, "relevamientos": 0})
    for r in alcance.relevamientos:
        if r["tipo"] != Relevamiento.Tipo.TERRITORIAL or not r["territorial_id"]:
            continue
        acumulado = por_terr[r["territorial_id"]]
        acumulado["relevamientos"] += 1
        conteo = forms_por_rel.get(r["id"], Counter())
        acumulado["formularios"] += sum(conteo.values())
        acumulado["aprobados"] += conteo.get(Formulario.Estado.APROBADO, 0)
    if not por_terr:
        return []
    nombres = {
        u.pk: (u.get_full_name().strip() or u.username)
        for u in User.objects.filter(pk__in=list(por_terr)).only("first_name", "last_name", "username")
    }
    resultado = [{"nombre": nombres.get(pk, f"Usuario {pk}"), **v} for pk, v in por_terr.items()]
    resultado.sort(key=lambda fila: (-fila["formularios"], fila["nombre"]))
    return resultado[:TOP_TERRITORIALES]


def _localidades(formularios, total):
    filas = formularios.values("ciudadano__localidad__nombre").annotate(total=Count("pk"))
    detalle = [
        {
            "localidad": fila["ciudadano__localidad__nombre"] or SIN_LOCALIDAD,
            "total": fila["total"],
            "pct": _pct(fila["total"], total),
        }
        for fila in filas
    ]
    detalle.sort(key=lambda fila: (-fila["total"], fila["localidad"]))
    top = detalle[:TOP_LOCALIDADES]
    resto = sum(fila["total"] for fila in detalle[TOP_LOCALIDADES:])
    if resto:
        top = top + [{"localidad": OTRAS_LOCALIDADES, "total": resto, "pct": _pct(resto, total)}]
    return {"top": top, "detalle": detalle}


def _texto_alcance(filtros, alcance):
    """Enunciado legible del recorte: encabeza la pantalla y las exportaciones (RN-16)."""
    if filtros.con_ventana:
        periodo = f"Del {filtros.desde:%d/%m/%Y} al {filtros.hasta:%d/%m/%Y}"
    else:
        periodo = "Todo el período"
    segmento = "Todos los segmentos"
    if filtros.segmento_id:
        nombre = Segmento.objects.filter(pk=filtros.segmento_id).values_list("nombre", flat=True).first()
        segmento = (
            f"Segmento {nombre}" if nombre and filtros.segmento_id in alcance.segmento_ids else "Segmento sin acceso"
        )
    convocatoria = "Todas las convocatorias"
    if filtros.convocatoria_id:
        nombre = Convocatoria.objects.filter(pk=filtros.convocatoria_id).values_list("nombre", flat=True).first()
        convocatoria = (
            nombre if nombre and filtros.convocatoria_id in alcance.convocatoria_ids else "Convocatoria sin acceso"
        )
    relevamiento = "Todos los relevamientos"
    if filtros.relevamiento_id:
        nombre = Relevamiento.objects.filter(pk=filtros.relevamiento_id).values_list("nombre", flat=True).first()
        relevamiento = (
            nombre if nombre and filtros.relevamiento_id in alcance.relevamiento_ids else "Relevamiento sin acceso"
        )
    canal = "Ambos canales"
    if filtros.canal:
        canal = "Link público" if filtros.canal == Relevamiento.Tipo.PUBLICO else "Territorial"
    return " · ".join((periodo, segmento, convocatoria, relevamiento, canal))


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def metricas(user, programa, filtros, alcance=None):
    """Todos los bloques del tablero para un programa, un usuario y un recorte.

    Los totales cierran entre sí por construcción: la serie semanal, los estados,
    los canales, la tabla de convocatorias y los territoriales salen del mismo
    agrupado (relevamiento, estado) del mismo queryset de formularios (CA-3).
    """
    alcance = alcance or resolver_alcance(user, programa, filtros)
    formularios = _formularios(alcance, filtros.desde, filtros.hasta)
    rel_info = {r["id"]: r for r in alcance.relevamientos}

    # Una sola consulta agrupada alimenta estados, canales, convocatorias y territoriales.
    forms_por_rel = defaultdict(Counter)
    for fila in formularios.values("relevamiento_id", "estado").annotate(total=Count("pk")):
        forms_por_rel[fila["relevamiento_id"]][fila["estado"]] += fila["total"]
    por_estado, por_canal, forms_por_conv = Counter(), Counter(), defaultdict(Counter)
    for rel_id, conteo in forms_por_rel.items():
        info = rel_info.get(rel_id) or {}
        for estado, n in conteo.items():
            por_estado[estado] += n
            por_canal[info.get("tipo")] += n
            forms_por_conv[info.get("convocatoria_id")][estado] += n
    total = sum(por_estado.values())
    aprobados = por_estado.get(Formulario.Estado.APROBADO, 0)
    rechazados = por_estado.get(Formulario.Estado.RECHAZADO, 0)

    identidad = 0
    lista_espera = 0
    if total:
        identidad = formularios.filter(Q(validado_renaper=True) | Q(identidad_forzada=True)).count()
        lista_espera = ListaEspera.objects.filter(formulario__in=formularios.values("pk"), promovido=False).count()

    rel_por_estado = Counter(r["estado"] for r in alcance.relevamientos)
    cupos = _cupo(user, alcance)
    convocatorias = list(
        Convocatoria.objects.filter(pk__in=alcance.convocatoria_ids)
        .order_by()
        .values_list("activo", "cerrada_automaticamente")
    )

    indicadores = Indicadores(
        convocatorias_total=len(convocatorias),
        convocatorias_activas=sum(1 for activo, _ in convocatorias if activo),
        convocatorias_cerradas_vencimiento=sum(1 for activo, cerrada in convocatorias if not activo and cerrada),
        relevamientos_total=len(alcance.relevamientos),
        relevamientos_en_curso=sum(rel_por_estado.get(e, 0) for e in RELEVAMIENTOS_EN_CURSO),
        relevamientos_publicos=sum(1 for r in alcance.relevamientos if r["tipo"] == Relevamiento.Tipo.PUBLICO),
        formularios_recibidos=total,
        variacion_periodo_anterior=_variacion(alcance, filtros, total),
        aprobados=aprobados,
        tasa_aprobacion=_pct(aprobados, total),
        pendientes=por_estado.get(Formulario.Estado.ENVIADO, 0),
        cupo_total=sum(cupo for cupo, _ in cupos.values()),
        cupo_ocupado=sum(ocupado for _, ocupado in cupos.values()),
        lista_espera=lista_espera,
    )

    return Datos(
        programa_id=programa.pk,
        programa_nombre=programa.nombre,
        filtros=json.loads(filtros.clave()),
        alcance=_texto_alcance(filtros, alcance),
        calculado_en=timezone.localtime().isoformat(timespec="seconds"),
        indicadores=indicadores,
        serie_semanal=_serie_semanal(formularios, filtros) if total else [],
        estados=_con_choices(por_estado, Formulario.Estado.choices),
        canales=_con_choices(por_canal, Relevamiento.Tipo.choices),
        convocatorias=_tabla_convocatorias(alcance, forms_por_conv, cupos),
        relevamientos_por_estado=_con_choices(rel_por_estado, Relevamiento.Estado.choices),
        embudo=_embudo(formularios, total, aprobados, rechazados, lista_espera, identidad),
        territoriales=_territoriales(alcance, forms_por_rel),
        localidades=_localidades(formularios, total) if total else {"top": [], "detalle": []},
    )


# ---------------------------------------------------------------------------
# Caché (RN-17, RN-18)
# ---------------------------------------------------------------------------
def _cache_get(clave):
    """Redis puede fallar solo en producción (timeout, OOM, réplica de solo lectura):
    el tablero se calcula igual, sin caché, y queda un aviso en el log."""
    try:
        return cache.get(clave)
    except Exception:  # noqa: BLE001 — degradar a sin caché, nunca romper el tablero
        logger.warning("dashboard becas: la caché no respondió al leer %s; se calcula sin caché", clave, exc_info=True)
        return None


def _cache_set(clave, valor):
    try:
        cache.set(clave, valor, CACHE_TIMEOUT)
    except Exception:  # noqa: BLE001
        logger.warning("dashboard becas: la caché no aceptó la escritura de %s", clave, exc_info=True)


def _cache_delete(clave):
    try:
        cache.delete(clave)
    except Exception:  # noqa: BLE001
        logger.warning("dashboard becas: la caché no aceptó borrar %s", clave, exc_info=True)


def _huella_alcance(user, programa):
    """Lo que hace distinto el alcance de dos usuarios: sus segmentos visibles y, para
    el regional, sus subsegmentos a cargo. Va en la clave para no compartir caché."""
    segmentos = list(segmentos_visibles(user).filter(programa=programa).order_by("pk").values_list("pk", flat=True))
    subsegmentos = []
    if es_coordinador_regional_becas(user):
        subsegmentos = list(subsegmentos_a_cargo(user).order_by("pk").values_list("pk", flat=True))
    return f"s{segmentos}|ss{subsegmentos}"


def _clave(programa, filtros, huella, sufijo=""):
    # sha256 y no sha1: no es criptografía (es una clave de caché), pero Bandit B324 marca sha1 igual.
    resumen = hashlib.sha256(f"{filtros.clave()}|{huella}|{sufijo}".encode("utf-8")).hexdigest()[:40]
    return f"{CACHE_PREFIX}:{programa.pk}:{resumen}"


def clave_cache(user, programa, filtros, alcance=None):
    huella = alcance.huella if alcance is not None else _huella_alcance(user, programa)
    return _clave(programa, filtros, huella)


def metricas_cacheadas(user, programa, filtros, recalcular=False, alcance=None):
    """``(datos, desde_cache)``. Con ``recalcular`` borra la entrada y recomputa."""
    alcance = alcance or resolver_alcance(user, programa, filtros)
    clave = clave_cache(user, programa, filtros, alcance)
    if recalcular:
        _cache_delete(clave)
    else:
        datos = _cache_get(clave)
        if datos is not None:
            return datos, True
    datos = metricas(user, programa, filtros, alcance)
    _cache_set(clave, datos)
    return datos, False


# ---------------------------------------------------------------------------
# Respuestas de los formularios (RN-13 a RN-15)
# ---------------------------------------------------------------------------
def _origen_requisito(requisito):
    if requisito.subsegmento_id:
        return f"Requisito del subsegmento {getattr(requisito.subsegmento, 'nombre', '')}".strip()
    if requisito.segmento_id:
        return f"Requisito del segmento {getattr(requisito.segmento, 'nombre', '')}".strip()
    return "Requisito del programa"


def preguntas_graficables(user, programa):
    """Catálogo de preguntas de opciones cerradas del programa (RN-13): generales
    activas y requisitos del programa, de sus segmentos y subsegmentos en alcance.
    El sistema no tiene tipo sí/no: es un selector de dos opciones."""
    selectores = TipoCampo.selectores()
    segmentos = segmentos_visibles(user).filter(programa=programa)
    subsegmentos = subsegmentos_visibles(user).filter(segmento__in=segmentos)
    preguntas = [
        Pregunta(
            clave=f"global:{p.pk}",
            texto=p.texto,
            tipo=p.get_tipo_display(),
            origen="Pregunta general",
            opciones=_opciones_texto(p.opciones),
            multiple=p.tipo == TipoCampo.SELECTOR_MULTIPLE,
        )
        for p in PreguntaGlobal.objects.filter(activo=True, tipo__in=selectores).order_by("orden", "id")
    ]
    requisitos = (
        RequisitoNativo.objects.filter(tipo__in=selectores)
        .filter(
            Q(programa=programa) | Q(segmento__in=segmentos, subsegmento__isnull=True) | Q(subsegmento__in=subsegmentos)
        )
        .select_related("segmento", "subsegmento")
        .order_by("programa_id", "segmento_id", "subsegmento_id", "orden", "id")
    )
    preguntas.extend(
        Pregunta(
            clave=f"requisito:{r.pk}",
            texto=r.texto,
            tipo=r.get_tipo_display(),
            origen=_origen_requisito(r),
            opciones=_opciones_texto(r.opciones),
            multiple=r.tipo == TipoCampo.SELECTOR_MULTIPLE,
        )
        for r in requisitos
    )
    return preguntas


def _como_dict(valor):
    """Un JSON que debería ser dict pero puede venir como string (doble codificado) o
    con otra forma en filas viejas: nunca hay que romper por eso."""
    if isinstance(valor, (str, bytes)):
        try:
            valor = json.loads(valor)
        except (TypeError, ValueError):
            return {}
    return valor if isinstance(valor, dict) else {}


def _opciones_texto(opciones):
    """Las opciones de una pregunta como lista de strings, sea cual sea la forma
    guardada: lista de strings (la actual), string JSON o con saltos de línea,
    dict, o lista de objetos ``{valor, etiqueta}`` de versiones anteriores."""
    if isinstance(opciones, (str, bytes)):
        try:
            opciones = json.loads(opciones)
        except (TypeError, ValueError):
            opciones = [linea.strip() for linea in str(opciones).splitlines() if linea.strip()]
    if isinstance(opciones, dict):
        opciones = list(opciones.values())
    if not isinstance(opciones, (list, tuple)):
        return []
    salida = []
    for opcion in opciones:
        if isinstance(opcion, dict):
            opcion = next((opcion[k] for k in ("etiqueta", "label", "texto", "valor", "value") if opcion.get(k)), "")
        texto = str(opcion).strip()
        if texto and texto not in salida:
            salida.append(texto)
    return salida


def _valores_de(valor):
    """Normaliza el valor de una respuesta ya extraído del JSON: lista de strings,
    vacía si no respondió. Tolera ``{valor, etiqueta}``, listas con objetos y
    escalares de cualquier tipo."""
    valores = valor if isinstance(valor, (list, tuple)) else [valor]
    salida = []
    for v in valores:
        if isinstance(v, dict):
            v = next((v[k] for k in ("valor", "value", "etiqueta", "label") if v.get(k)), "")
        if v in (None, "", [], {}):
            continue
        salida.append(str(v))
    return salida


def _ambito_y_pk(clave):
    ambito, _, pk = clave.partition(":")
    return ("globales" if ambito == "global" else "requisitos"), str(pk)


def respuesta_de(data, clave):
    """**Única** lectura de la respuesta de un formulario a una pregunta a partir del
    documento completo (``Formulario.data``). La pasada masiva usa
    :func:`_expresion_respuesta`, que extrae la misma clave en SQL; las dos deben
    coincidir. Cuando entre el constructor (#326) y las respuestas pasen a
    ``respuestas`` + ``definicion``, estos dos puntos son los únicos a tocar."""
    bolsa, pk = _ambito_y_pk(clave)
    return _valores_de(_como_dict(_como_dict(data).get(bolsa)).get(pk))


class _ValorJson(Func):
    """``JSON_EXTRACT(data, '$."globales"."13"')``: existe con ese nombre en MySQL y en
    SQLite. No se usa ``KeyTransform`` porque Django interpreta una clave numérica
    como índice de arreglo (``$."globales"[13]``) y devolvería NULL; entre comillas
    es un miembro del objeto. ``output_field=JSONField`` hace que Django decodifique
    el valor (MySQL devuelve JSON textual; SQLite, el escalar o el JSON del arreglo)."""

    function = "JSON_EXTRACT"
    arity = 2
    output_field = JSONField()


def _expresion_respuesta(clave):
    """``data -> 'globales'|'requisitos' -> '<pk>'`` como expresión SQL: el motor
    devuelve solo el valor de la pregunta en vez del documento entero."""
    bolsa, pk = _ambito_y_pk(clave)
    return _ValorJson(F("data"), Value(f'$."{bolsa}"."{int(pk)}"'))


def _armar_distribucion(pregunta, conteo, base):
    orden_catalogo = {opcion: i for i, opcion in enumerate(pregunta.opciones)}
    etiquetas = list(pregunta.opciones) + [opcion for opcion in conteo if opcion not in orden_catalogo]
    opciones = [
        {"opcion": opcion, "total": conteo.get(opcion, 0), "pct": _pct(conteo.get(opcion, 0), base)}
        for opcion in etiquetas
    ]
    opciones.sort(
        key=lambda fila: (-fila["total"], orden_catalogo.get(fila["opcion"], len(orden_catalogo)), fila["opcion"])
    )
    return Distribucion(
        clave=pregunta.clave,
        texto=pregunta.texto,
        tipo=pregunta.tipo,
        origen=pregunta.origen,
        multiple=pregunta.multiple,
        base=base,
        opciones=opciones,
    )


def distribuciones_respuestas(user, programa, filtros, claves=None, alcance=None, catalogo=None):
    """Distribución de una o varias preguntas en **una sola pasada** por los formularios.

    - La base de cada pregunta son los formularios que **tienen** esa pregunta
      respondida (RN-15); un formulario anterior al alta no cuenta como «sin respuesta».
    - En múltiple cada opción marcada suma una vez y los porcentajes pueden superar
      el 100 % (RN-14).
    - Una opción respondida que ya no está en el catálogo se lista igual, con el
      texto guardado (caso límite del análisis).

    La extracción se hace en SQL por clave del JSON: una fila devuelve solo los
    valores pedidos, no el documento. Una fila con ``data`` guardado como texto (doble
    codificado) no tiene claves para el motor y cuenta como sin respuesta: no rompe.

    ``claves=None`` calcula todas las del catálogo (exportación). Devuelve la lista en
    el orden del catálogo; las claves fuera del alcance se ignoran.
    """
    catalogo = list(catalogo) if catalogo is not None else preguntas_graficables(user, programa)
    if claves is not None:
        pedidas = set(claves)
        catalogo = [p for p in catalogo if p.clave in pedidas]
    if not catalogo:
        return []
    alcance = alcance or resolver_alcance(user, programa, filtros)
    formularios = _formularios(alcance, filtros.desde, filtros.hasta)

    conteos = {p.clave: Counter() for p in catalogo}
    bases = {p.clave: 0 for p in catalogo}
    alias = [f"r{i}" for i in range(len(catalogo))]
    filas = formularios.annotate(**{a: _expresion_respuesta(p.clave) for a, p in zip(alias, catalogo)}).values_list(
        *alias
    )
    for fila in filas.iterator(chunk_size=5000):
        for pregunta, valor in zip(catalogo, fila):
            valores = _valores_de(valor)
            if not valores:
                continue
            bases[pregunta.clave] += 1
            for v in valores if pregunta.multiple else valores[:1]:
                conteos[pregunta.clave][v] += 1
    return [_armar_distribucion(p, conteos[p.clave], bases[p.clave]) for p in catalogo]


def distribucion_respuestas(user, programa, filtros, clave, alcance=None, catalogo=None):
    """Una sola pregunta. Levanta ``ValueError`` si no existe o está fuera del alcance."""
    resultado = distribuciones_respuestas(user, programa, filtros, claves=[clave], alcance=alcance, catalogo=catalogo)
    if not resultado:
        raise ValueError("La pregunta no existe o no está en el alcance del usuario.")
    return resultado[0]


def distribucion_cacheada(user, programa, filtros, clave, recalcular=False, alcance=None, catalogo=None):
    """``(distribucion, desde_cache)`` con la misma política que las métricas: 5
    minutos por (programa, filtros, alcance, pregunta)."""
    alcance = alcance or resolver_alcance(user, programa, filtros)
    clave_c = _clave(programa, filtros, alcance.huella, sufijo=f"resp:{clave}")
    if recalcular:
        _cache_delete(clave_c)
    else:
        valor = _cache_get(clave_c)
        if valor is not None:
            return valor, True
    valor = distribucion_respuestas(user, programa, filtros, clave, alcance=alcance, catalogo=catalogo)
    _cache_set(clave_c, valor)
    return valor, False


# ---------------------------------------------------------------------------
# Exportación (RN-16): un Reporte por bloque
# ---------------------------------------------------------------------------
def _reporte_resumen(datos):
    i = datos.indicadores
    filas = (
        ("Programa", datos.programa_nombre),
        ("Alcance", datos.alcance),
        ("Calculado", datos.calculado_en),
        ("Convocatorias activas", i.convocatorias_activas),
        ("Convocatorias en el alcance", i.convocatorias_total),
        ("Convocatorias cerradas por vencimiento", i.convocatorias_cerradas_vencimiento),
        ("Relevamientos en curso", i.relevamientos_en_curso),
        ("Relevamientos en el alcance", i.relevamientos_total),
        ("Relevamientos con link público", i.relevamientos_publicos),
        ("Formularios recibidos", i.formularios_recibidos),
        (
            "Variación vs. período anterior (%)",
            i.variacion_periodo_anterior if i.variacion_periodo_anterior is not None else "—",
        ),
        ("Aprobados", i.aprobados),
        ("Tasa de aprobación (%)", i.tasa_aprobacion),
        ("Pendientes de revisión", i.pendientes),
        ("Cupo total", i.cupo_total),
        ("Cupo ocupado", i.cupo_ocupado),
        ("Lista de espera", i.lista_espera),
    )
    return Reporte(("Indicador", "Valor"), tuple(filas))


def bloques_exportacion(datos, distribuciones=()):
    """``{codigo: (nombre_hoja, Reporte)}``; el mismo diccionario sirve para las hojas
    del XLSX y para el CSV de un bloque."""
    estados = tuple(
        (fila["etiqueta"], fila["total"], _pct(fila["total"], datos.indicadores.formularios_recibidos))
        for fila in datos.estados
    )
    canales = tuple(
        (fila["etiqueta"], fila["total"], _pct(fila["total"], datos.indicadores.formularios_recibidos))
        for fila in datos.canales
    )
    bloques = {
        "resumen": ("Resumen", _reporte_resumen(datos)),
        "semanas": (
            "Semanas",
            Reporte(
                ("Semana desde", "Semana hasta", "Formularios"),
                tuple((f["semana"], f["hasta"], f["total"]) for f in datos.serie_semanal),
            ),
        ),
        "estados": ("Estados", Reporte(("Estado", "Formularios", "%"), estados)),
        "canales": ("Canales", Reporte(("Canal", "Formularios", "%"), canales)),
        "convocatorias": (
            "Convocatorias",
            Reporte(
                (
                    "Convocatoria",
                    "Segmento",
                    "Subsegmento",
                    "Estado",
                    "Inicio",
                    "Fin",
                    "Relevamientos",
                    "En curso",
                    "Formularios",
                    "Aprobados",
                    "Rechazados",
                    "Bajas",
                    "Pendientes",
                    "% revisado",
                    "Cupo del segmento",
                    "Cupo ocupado",
                ),
                tuple(
                    (
                        c["nombre"],
                        c["segmento"],
                        c["subsegmento"],
                        c["estado"],
                        c["fecha_inicio"],
                        c["fecha_fin"],
                        c["relevamientos"],
                        c["en_curso"],
                        c["recibidos"],
                        c["aprobados"],
                        c["rechazados"],
                        c["bajas"],
                        c["pendientes"],
                        c["revisado_pct"],
                        c["cupo_segmento"],
                        c["cupo_ocupado"],
                    )
                    for c in datos.convocatorias
                ),
            ),
        ),
        "relevamientos": (
            "Relevamientos",
            Reporte(
                ("Estado", "Relevamientos"), tuple((f["etiqueta"], f["total"]) for f in datos.relevamientos_por_estado)
            ),
        ),
        "embudo": (
            "Embudo",
            Reporte(
                ("Etapa", "Cantidad", "% sobre recibidos"),
                tuple((f["etapa"], f["total"], f["pct"]) for f in datos.embudo),
            ),
        ),
        "territoriales": (
            "Territoriales",
            Reporte(
                ("Territorial", "Relevamientos", "Formularios", "Aprobados"),
                tuple((f["nombre"], f["relevamientos"], f["formularios"], f["aprobados"]) for f in datos.territoriales),
            ),
        ),
        "localidades": (
            "Localidades",
            Reporte(
                ("Localidad", "Formularios", "%"),
                tuple((f["localidad"], f["total"], f["pct"]) for f in datos.localidades["detalle"]),
            ),
        ),
    }
    if distribuciones:
        filas = tuple(
            (d.texto, d.origen, d.tipo, o["opcion"], o["total"], o["pct"], d.base)
            for d in distribuciones
            for o in d.opciones
        )
        bloques["respuestas"] = (
            "Respuestas",
            Reporte(
                ("Pregunta", "Origen", "Tipo", "Opción", "Respuestas", "% de la base", "Formularios con respuesta"),
                filas,
            ),
        )
    return bloques
