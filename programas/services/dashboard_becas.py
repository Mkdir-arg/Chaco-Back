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
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Exists, F, Func, JSONField, OuterRef, Q, Sum, Value
from django.utils import timezone

from programas.models import (
    AdjuntoFormulario,
    Convocatoria,
    Formulario,
    ItemDiseno,
    ListaEspera,
    OrigenRequisito,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
    ValidacionSIS,
)
from programas.services import condiciones
from programas.services.autorizacion import (
    convocatorias_visibles,
    es_coordinador_regional_becas,
    segmentos_visibles,
    subsegmentos_a_cargo,
    subsegmentos_visibles,
)
from programas.services.becas import get_campos_formulario
from programas.services.reportes import Reporte
from programas.services.respuestas import campos_de, huella_definicion, legible, planos_de

logger = logging.getLogger(__name__)

CACHE_TIMEOUT = 300  # RN-17: hasta 5 minutos de antigüedad
CACHE_PREFIX = "becas:dashboard"
TOP_TERRITORIALES = 8
TOP_LOCALIDADES = 7
SIN_LOCALIDAD = "Sin localidad"
OTRAS_LOCALIDADES = "Otras"

RELEVAMIENTOS_EN_CURSO = (Relevamiento.Estado.EN_CURSO, Relevamiento.Estado.FINALIZANDO)

#: Clave de un campo propio del constructor (``nueva_clave("cp")`` = ``cp-`` + hex).
#: Se valida antes de armar la ruta JSON y antes de decidir de qué columna se lee.
_CLAVE_PROPIA = re.compile(r"^cp-[0-9A-Za-z_-]{1,48}$")
#: El resto del espacio de claves del diseño: catálogo (``pg-``/``rn-``), grupos y textos.
_CLAVE_DISENO = re.compile(r"^(?:pg|rn|g|t)-[0-9A-Za-z_-]{1,48}$")
#: Tamaño del lote de la segunda pasada del Excel por persona (``respuestas`` y la
#: foto son las dos columnas pesadas de la fila: de a 500 la consulta sigue siendo
#: chica para el ``read_timeout`` de 10 s de ECOM).
LOTE_RESPUESTAS = 500


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
    #: Solo para un campo propio cuya visibilidad depende de una condición: los
    #: ítems del diseño donde vive (``{clave, tipo, padre, condicion}``), para
    #: descartar las respuestas que el motor de condiciones oculta. Vacío = la
    #: pregunta se ve siempre y la cuenta agrupada en SQL ya es la correcta.
    plan: tuple = ()


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


def _convocatorias(alcance):
    """Las convocatorias del alcance con su segmento y subsegmento, en el orden de la
    tabla: una sola lectura que comparten los indicadores y :func:`_tabla_convocatorias`."""
    return list(
        Convocatoria.objects.filter(pk__in=alcance.convocatoria_ids)
        .select_related("segmento", "subsegmento")
        .order_by("-fecha_inicio", "nombre")
    )


def _tabla_convocatorias(alcance, forms_por_conv, cupos, convocatorias):
    rels_por_conv = defaultdict(Counter)
    for r in alcance.relevamientos:
        rels_por_conv[r["convocatoria_id"]][r["estado"]] += 1
    filas = []
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

    # Una sola consulta agrupada alimenta estados, canales, convocatorias, territoriales
    # y la identidad validada: el conteo condicional viaja en el mismo agrupado en vez
    # de recorrer el recorte entero otra vez.
    forms_por_rel = defaultdict(Counter)
    identidad = 0
    con_identidad = Q(validado_renaper=True) | Q(identidad_forzada=True)
    for fila in formularios.values("relevamiento_id", "estado").annotate(
        total=Count("pk"), identidad=Count("pk", filter=con_identidad)
    ):
        forms_por_rel[fila["relevamiento_id"]][fila["estado"]] += fila["total"]
        identidad += fila["identidad"]
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

    lista_espera = 0
    if total:
        lista_espera = ListaEspera.objects.filter(formulario__in=formularios.values("pk"), promovido=False).count()

    rel_por_estado = Counter(r["estado"] for r in alcance.relevamientos)
    cupos = _cupo(user, alcance)
    convocatorias = _convocatorias(alcance)

    indicadores = Indicadores(
        convocatorias_total=len(convocatorias),
        convocatorias_activas=sum(1 for c in convocatorias if c.activo),
        convocatorias_cerradas_vencimiento=sum(1 for c in convocatorias if not c.activo and c.cerrada_automaticamente),
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
        convocatorias=_tabla_convocatorias(alcance, forms_por_conv, cupos, convocatorias),
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
    El sistema no tiene tipo sí/no: es un selector de dos opciones.

    Solo entran las preguntas de origen *pregunta*: desde el Cambio 58 el
    catálogo también tiene campos vinculados al legajo y al apoderado (Sexo,
    por ejemplo), que son selectores pero cuya respuesta va a la ficha de la
    persona y no a las respuestas del caso. Graficarlos daría series vacías.
    """
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
        for p in PreguntaGlobal.objects.filter(
            activo=True, tipo__in=selectores, origen=OrigenRequisito.PREGUNTA
        ).order_by("orden", "id")
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
    preguntas.extend(_preguntas_propias(user, programa))
    return preguntas


def _planos_del_diseno(items):
    """``[{clave, tipo, padre, condicion}]`` en orden de pantalla, desde las filas
    planas de ``ItemDiseno``: es lo que come el motor de condiciones.

    Mismo contrato que :func:`programas.services.respuestas.planos_de`, que arma lo
    mismo desde la **foto** de un caso. Acá la fuente es el diseño vigente porque el
    catálogo del dashboard no mira caso por caso.
    """
    hijos = defaultdict(list)
    for item in items:
        if item.padre_id:
            hijos[item.padre_id].append(item)

    def orden(item):
        return (item.orden, item.pk)

    planos = []
    for grupo in sorted((i for i in items if i.tipo == ItemDiseno.Tipo.GRUPO), key=orden):
        planos.append({"clave": grupo.clave, "tipo": "grupo", "padre": None, "condicion": grupo.condicion})
        for hijo in sorted(hijos[grupo.pk], key=orden):
            tipo = "texto" if hijo.tipo == ItemDiseno.Tipo.TEXTO else "campo"
            planos.append({"clave": hijo.clave, "tipo": tipo, "padre": grupo.clave, "condicion": hijo.condicion})
    return planos


def _fuentes_de(condicion):
    """Las claves que lee una condición (``{modo, reglas: [{fuente, op, valor}]}``)."""
    reglas = (condicion or {}).get("reglas")
    if not isinstance(reglas, list):
        return []
    return [r["fuente"] for r in reglas if isinstance(r, dict) and isinstance(r.get("fuente"), str) and r["fuente"]]


def _claves_que_condicionan(plan, clave):
    """Cierre transitivo de las claves de las que depende que ``clave`` se vea.

    Son las fuentes de su propia condición y las del grupo que la contiene, más —
    recursivamente— las de los ítems que esas fuentes necesitan: una fuente oculta
    cuenta como vacía, así que su visibilidad también entra en la cuenta. Devuelve
    las claves en el orden del plan, sin la propia.
    """
    por_clave = {p["clave"]: p for p in plan}
    pendientes, vistas, necesarias = [clave], set(), set()
    while pendientes:
        actual = pendientes.pop()
        if actual in vistas:
            continue
        vistas.add(actual)
        item = por_clave.get(actual)
        if item is None:
            continue
        if item.get("padre"):
            pendientes.append(item["padre"])
        for fuente in _fuentes_de(item.get("condicion")):
            necesarias.add(fuente)
            pendientes.append(fuente)
    necesarias.discard(clave)
    return tuple(p["clave"] for p in plan if p["clave"] in necesarias)


def _preguntas_propias(user, programa):
    """Campos propios del constructor (``cp-…``) de opciones cerradas, de los diseños
    de las convocatorias en alcance (G2-01).

    No están en el catálogo (`PreguntaGlobal` / `RequisitoNativo`): viven en el
    diseño de **una** convocatoria y su respuesta no tiene lugar en ``data``, solo en
    ``Formulario.respuestas``. Por eso el dashboard los ignoraba enteros desde el
    Cambio 58 y una convocatoria con preguntas propias no tenía ninguna graficable.

    La clave (``cp-`` + hex de ``uuid4``) es única en todo el repo, así que dos
    convocatorias con la misma pregunta son dos entradas distintas; el origen lleva el
    nombre de la convocatoria para poder distinguirlas en el selector.
    """
    convocatorias = convocatorias_visibles(user).filter(segmento__programa=programa)
    items = list(
        ItemDiseno.objects.filter(diseno__convocatoria__in=convocatorias)
        .select_related("diseno__convocatoria")
        .order_by("diseno_id", "orden", "id")
    )
    por_diseno = defaultdict(list)
    for item in items:
        por_diseno[item.diseno_id].append(item)

    selectores = set(TipoCampo.selectores())
    preguntas = []
    for del_diseno in por_diseno.values():
        con_condicion = {i.pk for i in del_diseno if i.condicion}
        planos = None
        for item in del_diseno:
            propio = item.propio if isinstance(item.propio, dict) else None
            if item.tipo != ItemDiseno.Tipo.CAMPO or propio is None or not _CLAVE_PROPIA.match(item.clave):
                continue
            if propio.get("tipo") not in selectores:
                continue
            # Oculto solo puede estar si algo lo condiciona: su propia regla o la del
            # grupo que lo contiene (un hijo de un grupo oculto está oculto).
            condicionado = item.pk in con_condicion or item.padre_id in con_condicion
            if condicionado and planos is None:
                planos = tuple(_planos_del_diseno(del_diseno))
            preguntas.append(
                Pregunta(
                    clave=item.clave,
                    texto=item.titulo,
                    tipo=TipoCampo(propio["tipo"]).label,
                    origen=f"Campo propio · {item.diseno.convocatoria.nombre}",
                    opciones=_opciones_texto(propio.get("opciones")),
                    multiple=propio["tipo"] == TipoCampo.SELECTOR_MULTIPLE,
                    plan=planos if condicionado else (),
                )
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


def respuesta_de(documento, clave):
    """**Única** lectura de la respuesta de un formulario a una pregunta a partir del
    documento completo. La pasada masiva usa :func:`_expresion_respuesta`, que extrae
    la misma clave en SQL; las dos deben coincidir.

    Dos espacios de claves conviven (G2-01): una del catálogo (``global:<pk>`` /
    ``requisito:<pk>``) se lee de ``Formulario.data``, bajo ``globales`` o
    ``requisitos``; un campo propio del constructor (``cp-…``) no tiene lugar ahí y se
    lee de ``Formulario.respuestas``, donde la clave está en la raíz.
    """
    if _CLAVE_PROPIA.match(clave):
        return _valores_de(_como_dict(documento).get(clave))
    bolsa, pk = _ambito_y_pk(clave)
    return _valores_de(_como_dict(_como_dict(documento).get(bolsa)).get(pk))


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
    """La respuesta a ``clave`` como expresión SQL: el motor devuelve solo ese valor en
    vez del documento entero.

    - Catálogo (``global:<pk>`` / ``requisito:<pk>``): ``data -> globales|requisitos -> <pk>``.
    - Clave del constructor (``cp-…``, ``pg-<pk>``, ``rn-<pk>``): ``respuestas -> <clave>``,
      en la raíz del documento.

    La ruta va siempre **entre comillas**: ``KeyTransform`` trata una clave numérica
    como índice de arreglo y en MariaDB devolvería NULL (§0.2 de la auditoría). La ruta
    viaja como parámetro (``Value``), no concatenada al SQL, y la clave está validada
    contra un patrón antes de llegar acá.
    """
    if _CLAVE_PROPIA.match(clave) or _CLAVE_DISENO.match(clave):
        return _ValorJson(F("respuestas"), Value(f'$."{clave}"'))
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
    """Distribución de una o varias preguntas, **agrupada en SQL** pregunta por pregunta.

    - La base de cada pregunta son los formularios que **tienen** esa pregunta
      respondida (RN-15); un formulario anterior al alta no cuenta como «sin respuesta».
    - En múltiple cada opción marcada suma una vez y los porcentajes pueden superar
      el 100 % (RN-14).
    - Una opción respondida que ya no está en el catálogo se lista igual, con el
      texto guardado (caso límite del análisis).

    La extracción se hace en SQL por clave del JSON y el motor agrupa por el valor
    extraído: por pregunta vuelve una fila por respuesta distinta (cada opción del
    selector, o cada combinación marcada en múltiple) con su cantidad, no un valor por
    formulario. Traer y decodificar en Python 20.000 valores por pregunta costaba diez
    veces más que la consulta (banco MySQL, 25/09/2026). Una fila con ``data`` guardado
    como texto (doble codificado) no tiene claves para el motor y cuenta como sin
    respuesta: no rompe.

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

    resultado = []
    for pregunta in catalogo:
        conteo, base = Counter(), 0
        # Una pregunta que una condición puede ocultar se agrupa **también** por las
        # claves de las que depende, así el motor sigue devolviendo una fila por
        # combinación distinta (no una por caso) y la condición se evalúa en Python
        # una vez por combinación. Evaluarla caso por caso obligaría a traer la foto
        # de los 20.000 casos y se pasa del read_timeout.
        fuentes = _claves_que_condicionan(pregunta.plan, pregunta.clave) if pregunta.plan else ()
        anotaciones = {f"fuente_{i}": _expresion_respuesta(clave) for i, clave in enumerate(fuentes)}
        grupos = (
            formularios.annotate(valor=_expresion_respuesta(pregunta.clave), **anotaciones)
            .values("valor", *anotaciones)
            .annotate(total=Count("pk"))
            .values_list("valor", *anotaciones, "total")
        )
        for fila in grupos:
            valor, total = fila[0], fila[-1]
            valores = _valores_de(valor)
            if not valores:
                continue
            if fuentes and _la_condicion_la_oculta(pregunta, fuentes, valor, fila[1:-1]):
                continue
            base += total
            for v in valores if pregunta.multiple else valores[:1]:
                conteo[v] += total
        resultado.append(_armar_distribucion(pregunta, conteo, base))
    return resultado


def _la_condicion_la_oculta(pregunta, fuentes, valor, valores_fuente):
    """¿El motor de condiciones esconde esta pregunta con estas respuestas? (RN-6)

    Se corre el motor completo sobre el plan del diseño con las respuestas de las
    claves que importan: las que están fuera del cierre no cambian si la pregunta se
    ve o no. Una respuesta a un campo que la persona nunca vio no es una respuesta y
    no entra en la distribución.
    """
    respuestas = {clave: v for clave, v in zip(fuentes, valores_fuente) if v not in (None, "", [], {})}
    respuestas[pregunta.clave] = valor
    _, ocultos, _ = condiciones.aplicar(list(pregunta.plan), respuestas)
    return pregunta.clave in ocultos


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


# ---------------------------------------------------------------------------
# Respuestas por persona (Cambio 65): un registro por caso, una columna por pregunta
# ---------------------------------------------------------------------------
COLUMNAS_FIJAS = (
    "ID relevamiento",
    "Relevamiento",
    "Canal",
    "Territorial",
    "ID caso",
    "N.º en el relevamiento",
    "Estado del caso",
    "Fecha de envío",
    "ID ciudadano",
    "DNI",
    "Apellido y nombre",
    "Identidad validada",
    "Celular",
    "Correo electrónico",
    "Apoderado",
    "GPS",
)


def _nombre_archivo(ruta):
    return str(ruta).rsplit("/", 1)[-1] if ruta else ""


def _texto_columna(campo, prefijo):
    return f"{campo.texto}".strip() or f"{prefijo} #{campo.pk}"


def _identificacion(f):
    """(dni, «Apellido, Nombre») desde el legajo si existe; si no, de los datos de
    identificación offline. ``f`` es la fila del caso (ver ``_COLUMNAS_CASO``)."""
    if f["ciudadano_id"]:
        return f["ciudadano__dni"], f"{f['ciudadano__apellido']}, {f['ciudadano__nombre']}".strip(", ")
    ident = f["datos_identificacion"] if isinstance(f["datos_identificacion"], dict) else {}
    return str(ident.get("dni") or ""), f"{ident.get('apellido') or ''}, {ident.get('nombre') or ''}".strip(", ")


def _apoderado(f):
    if f["apoderado_ciudadano_id"]:
        return f"{f['apoderado_ciudadano__apellido']}, {f['apoderado_ciudadano__nombre']} ({f['apoderado_ciudadano__dni']})"
    if f["apoderado_dni"] or f["apoderado_apellido"] or f["apoderado_nombre"]:
        return f"{f['apoderado_apellido']}, {f['apoderado_nombre']} ({f['apoderado_dni']})".strip(", ")
    return ""


def _relevamientos_de(convocatoria):
    """``{id: (id, nombre, canal, territorial)}``: las columnas fijas del relevamiento se
    resuelven una vez por relevamiento y no por cada caso."""
    filas = {}
    for pk, nombre, tipo, territorial_id, first_name, last_name, username in (
        Relevamiento.objects.filter(convocatoria=convocatoria)
        .order_by()
        .values_list(
            "pk",
            "nombre",
            "tipo",
            "territorial_id",
            "territorial__first_name",
            "territorial__last_name",
            "territorial__username",
        )
    ):
        territorial = (f"{first_name} {last_name}".strip() or username) if territorial_id else ""
        canal = "Link público" if tipo == Relevamiento.Tipo.PUBLICO else "Territorial"
        filas[pk] = (pk, nombre, canal, territorial)
    return filas


# Lo único del caso que lee la planilla. Se pide con ``values`` y no como instancias:
# con 20.000 casos, armar el modelo con sus tres relaciones —y convertir nueve
# datetimes por fila que nadie mira— era la mitad del tiempo de Python del export
# (banco MySQL, 25/09/2026). ``respuestas``, ``definicion`` y ``datos_siis`` quedan
# afuera: eran lo más pesado de cada fila y pasaban el read_timeout (500, 24/09/2026).
# ``respuestas`` y ``definicion`` entran en una **segunda pasada por lotes de pk**
# (G2-01, :func:`_respuestas_de_los_casos`), que es lo que trae los campos propios.
_COLUMNAS_CASO = (
    "pk",
    "relevamiento_id",
    "numero",
    "estado",
    "creado",
    "ciudadano_id",
    "ciudadano__dni",
    "ciudadano__apellido",
    "ciudadano__nombre",
    "datos_identificacion",
    "validado_renaper",
    "identidad_forzada",
    "celular",
    "email_contacto",
    "apoderado_ciudadano_id",
    "apoderado_ciudadano__apellido",
    "apoderado_ciudadano__nombre",
    "apoderado_ciudadano__dni",
    "apoderado_apellido",
    "apoderado_nombre",
    "apoderado_dni",
    "gps_lat",
    "gps_lng",
    "data",
)


def _texto_legible(item, valor):
    """El valor de una respuesta como celda de la planilla: fechas en dd/mm/aaaa, el
    sexo con su nombre y la selección múltiple unida con « | » (misma lectura que la
    pantalla de revisión, :func:`programas.services.respuestas.legible`)."""
    texto = legible(item, valor)
    if isinstance(texto, list):
        return " | ".join(str(v) for v in texto if v not in (None, "", [], {}))
    return str(texto)


def _respuestas_de_los_casos(pks):
    """Segunda pasada del Excel por persona: ``{pk: {clave: celda}}``, ``{pk: ocultas}``
    y los campos de las fotos, en orden y deduplicados por clave (G2-01).

    ``respuestas`` y ``definicion`` son las dos columnas pesadas del caso (la foto son
    ~7 KB) y por eso no viajan en la consulta principal: se leen **por lotes de pk**,
    que es lo que mantiene cada consulta lejos del ``read_timeout`` de 10 s de ECOM.
    Para los encabezados alcanza con **una** foto por ``huella_definicion``: todos los
    casos que respondieron el mismo diseño traen exactamente los mismos campos.

    Lo que una condición ocultó no es una respuesta y no va a la planilla: sale de la
    celda y, si el contrato anterior lo había guardado en ``data``, también de ahí.
    """
    celdas, ocultas_por_caso, campos, orden = {}, {}, {}, []
    planos_por_huella, campos_por_huella = {}, {}
    for inicio in range(0, len(pks), LOTE_RESPUESTAS):
        lote = pks[inicio : inicio + LOTE_RESPUESTAS]
        for pk, respuestas, foto in (
            Formulario.objects.filter(pk__in=lote).order_by().values_list("pk", "respuestas", "definicion")
        ):
            respuestas = _como_dict(respuestas)
            foto = foto if isinstance(foto, dict) else {}
            huella = huella_definicion(foto) if foto else ""
            if huella and huella not in planos_por_huella:
                planos_por_huella[huella] = planos_de(foto)
                campos_por_huella[huella] = {c["clave"]: c for c in campos_de(foto)}
                for clave, campo in campos_por_huella[huella].items():
                    if clave not in campos:
                        campos[clave] = campo
                        orden.append(clave)
            if not respuestas:
                continue
            del_caso = campos_por_huella.get(huella, {})
            _, ocultos, _ = condiciones.aplicar(planos_por_huella.get(huella, []), respuestas)
            ocultas_por_caso[pk] = ocultos
            valores = {}
            for clave, valor in respuestas.items():
                if clave in ocultos:
                    continue
                texto = _texto_legible(del_caso.get(clave) or {}, valor)
                if texto:
                    valores[clave] = texto
            celdas[pk] = valores
    return celdas, ocultas_por_caso, campos, orden


def respuestas_por_persona(convocatoria):
    """Base cruda de una convocatoria: **un registro por caso** (formulario enviado,
    en cualquier estado) con los datos del relevamiento, de la persona y **una columna
    por cada pregunta** del formulario, más las preguntas que ya no están en el
    formulario pero fueron respondidas en su momento.

    Devuelve ``(Reporte, texto_de_alcance)``. Las columnas salen de las **fotos** de la
    definición que respondieron los casos (``Formulario.definicion``), que es lo que la
    persona tuvo delante, completadas con el catálogo vigente
    (:func:`get_campos_formulario`) para que una convocatoria sin casos siga
    exportando sus columnas. Los valores salen de ``Formulario.respuestas`` —la única
    fuente que tiene los **campos propios** del constructor (``cp-…``), que no caben en
    ``data``— y, para los casos anteriores al Cambio 58 que todavía no tienen foto, del
    ``data`` de siempre. Las respuestas de selección múltiple se unen con « | »; los
    adjuntos muestran el nombre del archivo. El alcance por rol lo controla la vista:
    acá la convocatoria ya está autorizada.
    """
    globales, requisitos = get_campos_formulario(convocatoria)
    definicion = [(f"pg-{p.pk}", p, "Pregunta general") for p in globales] + [
        (f"rn-{r.pk}", r, "Requisito") for r in requisitos
    ]
    en_definicion = {clave for clave, _, _ in definicion}

    # Adjuntos por caso y pregunta: en esa columna va el nombre del archivo.
    adjuntos = {}
    for form_id, pg_id, rn_id, archivo in (
        AdjuntoFormulario.objects.filter(formulario__relevamiento__convocatoria=convocatoria)
        .order_by()
        .values_list("formulario_id", "pregunta_global_id", "requisito_nativo_id", "archivo")
    ):
        clave = f"pg-{pg_id}" if pg_id else f"rn-{rn_id}"
        adjuntos.setdefault(form_id, {}).setdefault(clave, []).append(_nombre_archivo(archivo))

    relevamientos = _relevamientos_de(convocatoria)
    etiquetas_estado = {valor: str(etiqueta) for valor, etiqueta in Formulario.Estado.choices}
    # Filtrar por los ids de relevamiento (y no por el join a la convocatoria) deja que
    # el motor lea por el índice (relevamiento, numero), que ya es el orden pedido, sin
    # tabla temporal ni sort de las 20.000 filas.
    formularios = (
        Formulario.objects.filter(relevamiento_id__in=list(relevamientos))
        .order_by("relevamiento_id", "numero")
        .values(*_COLUMNAS_CASO)
    )
    casos, extra_claves = [], set()
    for f in formularios.iterator(chunk_size=2000):
        rel_id, rel_nombre, canal, territorial = relevamientos[f["relevamiento_id"]]
        dni, nombre = _identificacion(f)
        creado = f["creado"]
        base = [
            rel_id,
            rel_nombre,
            canal,
            territorial,
            f["pk"],
            f["numero"],
            etiquetas_estado.get(f["estado"], f["estado"]),
            timezone.localtime(creado).strftime("%d/%m/%Y %H:%M") if creado else "",
            f["ciudadano_id"] or "",
            dni,
            nombre,
            "Sí" if (f["validado_renaper"] or f["identidad_forzada"]) else "No",
            f["celular"] or "",
            f["email_contacto"] or "",
            _apoderado(f),
            f"{f['gps_lat']}, {f['gps_lng']}" if f["gps_lat"] is not None and f["gps_lng"] is not None else "",
        ]
        data = _como_dict(f["data"])
        contestadas = {}
        for bolsa, prefijo in (("globales", "pg"), ("requisitos", "rn")):
            for pk, valor in _como_dict(data.get(bolsa)).items():
                valores = _valores_de(valor)
                if valores:
                    contestadas[f"{prefijo}-{pk}"] = " | ".join(valores)
        casos.append((f["pk"], base, contestadas))

    # Segunda pasada: ``respuestas`` + la foto. Lo que dice la foto manda sobre lo que
    # el contrato anterior dejó en ``data`` (las dos se escriben juntas, pero solo la
    # primera tiene los campos propios y ya pasó por el motor de condiciones).
    celdas, ocultas, campos_foto, orden_foto = _respuestas_de_los_casos([pk for pk, _, _ in casos])
    for pk, _base, contestadas in casos:
        for clave in ocultas.get(pk, ()):
            contestadas.pop(clave, None)
        contestadas.update(celdas.get(pk, {}))
        extra_claves.update(clave for clave in contestadas if clave not in en_definicion and clave not in campos_foto)

    # Preguntas respondidas que ya no están en el formulario: se conservan como columnas propias.
    extras = []
    if extra_claves:

        def pks_de(prefijo):
            return [int(c[3:]) for c in extra_claves if c.startswith(f"{prefijo}-") and c[3:].isdigit()]

        textos = {f"pg-{p.pk}": p.texto for p in PreguntaGlobal.objects.filter(pk__in=pks_de("pg"))}
        textos.update({f"rn-{r.pk}": r.texto for r in RequisitoNativo.objects.filter(pk__in=pks_de("rn"))})
        for clave in sorted(extra_claves):
            extras.append((clave, f"{textos.get(clave, 'Pregunta ' + clave)} (ya no está en el formulario)"))

    # Columnas: el orden de la pantalla (las fotos de los casos, deduplicadas por
    # clave), después lo que el catálogo de hoy pide y nadie respondió todavía —una
    # convocatoria sin casos sigue exportando sus columnas— y al final los extras.
    del_catalogo = {clave: _texto_columna(campo, prefijo) for clave, campo, prefijo in definicion}
    columnas = [
        (clave, del_catalogo.get(clave) or campos_foto[clave].get("texto", "") or clave) for clave in orden_foto
    ]
    columnas += [(clave, texto) for clave, texto in del_catalogo.items() if clave not in campos_foto]
    columnas += extras
    # Dos preguntas con el mismo texto (una general y un requisito) no pueden confundirse en la planilla.
    repetidos = Counter(texto for _, texto in columnas)
    encabezados_preguntas = [f"{texto} [{clave}]" if repetidos[texto] > 1 else texto for clave, texto in columnas]

    claves = [clave for clave, _ in columnas]
    posicion = {clave: i for i, clave in enumerate(claves)}
    filas = []
    for form_id, base, contestadas in casos:
        celdas = [contestadas.get(clave, "") for clave in claves]
        # Un adjunto pisa lo guardado en su columna; sin columna (pregunta que ya no
        # está y nadie respondió) no hay dónde mostrarlo, igual que antes.
        for clave, nombres in adjuntos.get(form_id, {}).items():
            if clave in posicion:
                celdas[posicion[clave]] = " | ".join(nombres)
        filas.append(tuple(base + celdas))

    encabezados = COLUMNAS_FIJAS + tuple(encabezados_preguntas)
    alcance = (
        f"Convocatoria {convocatoria.nombre} · {convocatoria.segmento.nombre} · {len(filas)} casos, "
        f"todos los estados, sin filtro de período · generado el {timezone.localtime():%d/%m/%Y %H:%M}"
    )
    return Reporte(encabezados, tuple(filas)), alcance
