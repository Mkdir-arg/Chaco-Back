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
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta

from django.core.cache import cache
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone

from programas.models import (
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


# ---------------------------------------------------------------------------
# Helpers de recorte
# ---------------------------------------------------------------------------
def _aware_start(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.min), timezone.get_current_timezone())


def _pct(parte, total, decimales=1):
    if not total:
        return 0.0
    return round(parte * 100 / total, decimales)


def _segmentos_alcance(user, programa, filtros):
    """Segmentos visibles del programa; con filtro de segmento o de convocatoria se acota (RN-3)."""
    qs = segmentos_visibles(user).filter(programa=programa)
    if filtros.segmento_id:
        qs = qs.filter(pk=filtros.segmento_id)
    if filtros.convocatoria_id:
        qs = qs.filter(convocatorias__pk=filtros.convocatoria_id)
    return qs.distinct()


def _convocatorias_alcance(user, programa, filtros):
    qs = convocatorias_visibles(user).filter(segmento__programa=programa)
    if filtros.segmento_id:
        qs = qs.filter(segmento_id=filtros.segmento_id)
    if filtros.convocatoria_id:
        qs = qs.filter(pk=filtros.convocatoria_id)
    if filtros.relevamiento_id:
        qs = qs.filter(relevamientos__pk=filtros.relevamiento_id)
    return qs.distinct()


def _relevamientos_alcance(convocatorias, filtros):
    """Los relevamientos cuentan por estructura: la ventana de fechas no los recorta."""
    qs = Relevamiento.objects.filter(convocatoria__in=convocatorias)
    if filtros.relevamiento_id:
        qs = qs.filter(pk=filtros.relevamiento_id)
    if filtros.canal:
        qs = qs.filter(tipo=filtros.canal)
    return qs


def _formularios_de(relevamientos, desde=None, hasta=None):
    qs = Formulario.objects.filter(relevamiento__in=relevamientos)
    if desde:
        qs = qs.filter(creado__gte=_aware_start(desde))
    if hasta:
        qs = qs.filter(creado__lt=_aware_start(hasta + timedelta(days=1)))
    return qs


def _fecha_local(valor):
    if isinstance(valor, datetime):
        return timezone.localtime(valor).date()
    return valor


def _lunes(fecha):
    return fecha - timedelta(days=fecha.weekday())


# ---------------------------------------------------------------------------
# Bloques
# ---------------------------------------------------------------------------
def _serie_semanal(formularios, filtros):
    """Formularios por semana (lunes a domingo). Rellena las semanas vacías para que
    el gráfico no salte fechas (RN-7)."""
    filas = formularios.annotate(semana=TruncWeek("creado")).values("semana").annotate(total=Count("pk"))
    por_semana = {_lunes(_fecha_local(f["semana"])): f["total"] for f in filas if f["semana"] is not None}
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


def _conteo_por(qs, campo, choices):
    """Conteo por un campo con choices, con todos los valores presentes (aunque valgan 0)."""
    conteo = dict(qs.values_list(campo).annotate(total=Count("pk")).values_list(campo, "total"))
    return [{"clave": valor, "etiqueta": str(etiqueta), "total": conteo.get(valor, 0)} for valor, etiqueta in choices]


def _variacion(relevamientos, filtros, total_actual):
    """RN-8: contra el período inmediatamente anterior de la misma longitud."""
    if not filtros.con_ventana:
        return None
    longitud = (filtros.hasta - filtros.desde).days + 1
    anterior_hasta = filtros.desde - timedelta(days=1)
    anterior_desde = anterior_hasta - timedelta(days=longitud - 1)
    total_anterior = _formularios_de(relevamientos, anterior_desde, anterior_hasta).count()
    if not total_anterior:
        return None
    return round((total_actual - total_anterior) * 100 / total_anterior)


def _cupo(user, programa, segmentos):
    """RN-9: cupo del segmento contra aprobados históricos, sin ventana. El
    coordinador regional mide contra lo distribuido en sus subsegmentos, como
    ``reporte_cupos``. Devuelve ``{segmento_id: (cupo, ocupado)}``."""
    ids = list(segmentos.values_list("pk", flat=True))
    if not ids:
        return {}
    if es_coordinador_regional_becas(user):
        cupos = dict(
            subsegmentos_a_cargo(user)
            .filter(segmento_id__in=ids)
            .values("segmento_id")
            .annotate(total=Sum("cupo_maximo"))
            .values_list("segmento_id", "total")
        )
    else:
        cupos = dict(Segmento.objects.filter(pk__in=ids).values_list("pk", "cupo_maximo"))
    convs = convocatorias_visibles(user).filter(segmento_id__in=ids)
    ocupados = dict(
        Formulario.objects.filter(relevamiento__convocatoria__in=convs, estado=Formulario.Estado.APROBADO)
        .values("relevamiento__convocatoria__segmento_id")
        .annotate(total=Count("pk"))
        .values_list("relevamiento__convocatoria__segmento_id", "total")
    )
    return {pk: (cupos.get(pk) or 0, ocupados.get(pk, 0)) for pk in ids}


def _estado_convocatoria(conv):
    if conv.activo:
        return "Activa"
    return "Cerrada por vencimiento" if conv.cerrada_automaticamente else "Cerrada"


def _convocatorias(convocatorias, relevamientos, formularios, cupos):
    rel_stats = relevamientos.values("convocatoria_id", "estado").annotate(total=Count("pk"))
    form_stats = formularios.values("relevamiento__convocatoria_id", "estado").annotate(total=Count("pk"))
    rels_por_conv, forms_por_conv = {}, {}
    for fila in rel_stats:
        rels_por_conv.setdefault(fila["convocatoria_id"], Counter())[fila["estado"]] = fila["total"]
    for fila in form_stats:
        forms_por_conv.setdefault(fila["relevamiento__convocatoria_id"], Counter())[fila["estado"]] = fila["total"]
    filas = []
    for conv in convocatorias.select_related("segmento", "subsegmento").order_by("-fecha_inicio", "nombre"):
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
                "segmento": conv.segmento.nombre,
                "subsegmento": conv.subsegmento.nombre if conv.subsegmento_id else "",
                "estado": _estado_convocatoria(conv),
                "activa": conv.activo,
                "fecha_inicio": conv.fecha_inicio.isoformat(),
                "fecha_fin": conv.fecha_fin.isoformat(),
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


def _embudo(formularios, total, aprobados, rechazados, lista_espera):
    """Etapas ordenadas del circuito; «Beneficiarios» no se repite porque es el mismo
    número que «Aprobados» (inconsistencia 2 del análisis)."""
    ultima = ValidacionSIS.objects.filter(formulario_id=OuterRef("pk")).order_by("-creado", "-pk")
    siis_ok = (
        formularios.annotate(ultimo_siis=Subquery(ultima.values("estado")[:1]))
        .filter(ultimo_siis=ValidacionSIS.Estado.OK)
        .count()
    )
    identidad = formularios.filter(Q(validado_renaper=True) | Q(identidad_forzada=True)).count()
    etapas = (
        ("Formularios recibidos", total),
        ("Identidad validada", identidad),
        ("Aprobados", aprobados),
        ("Validación SIIS OK", siis_ok),
        ("En lista de espera", lista_espera),
        ("Rechazados", rechazados),
    )
    return [{"etapa": etapa, "total": cantidad, "pct": _pct(cantidad, total)} for etapa, cantidad in etapas]


def _territoriales(relevamientos, formularios):
    """RN-12: solo canal territorial; un público no tiene territorial."""
    rels = dict(
        relevamientos.filter(tipo=Relevamiento.Tipo.TERRITORIAL, territorial__isnull=False)
        .values_list("territorial_id")
        .annotate(total=Count("pk"))
        .values_list("territorial_id", "total")
    )
    filas = (
        formularios.filter(relevamiento__tipo=Relevamiento.Tipo.TERRITORIAL, relevamiento__territorial__isnull=False)
        .values(
            "relevamiento__territorial_id",
            "relevamiento__territorial__first_name",
            "relevamiento__territorial__last_name",
            "relevamiento__territorial__username",
        )
        .annotate(total=Count("pk"), aprobados=Count("pk", filter=Q(estado=Formulario.Estado.APROBADO)))
    )
    resultado = []
    vistos = set()
    for fila in filas:
        pk = fila["relevamiento__territorial_id"]
        vistos.add(pk)
        nombre = (
            f"{fila['relevamiento__territorial__first_name']} {fila['relevamiento__territorial__last_name']}".strip()
        )
        resultado.append(
            {
                "nombre": nombre or fila["relevamiento__territorial__username"],
                "formularios": fila["total"],
                "aprobados": fila["aprobados"],
                "relevamientos": rels.get(pk, 0),
            }
        )
    # Territoriales con relevamiento asignado y sin carga todavía: cuentan con 0.
    faltantes = [pk for pk in rels if pk not in vistos]
    if faltantes:
        from django.contrib.auth.models import User

        for usuario in User.objects.filter(pk__in=faltantes).order_by("last_name", "first_name"):
            nombre = usuario.get_full_name().strip() or usuario.username
            resultado.append({"nombre": nombre, "formularios": 0, "aprobados": 0, "relevamientos": rels[usuario.pk]})
    resultado.sort(key=lambda fila: (-fila["formularios"], fila["nombre"]))
    return resultado[:TOP_TERRITORIALES]


def _localidades(formularios, total):
    filas = formularios.values("ciudadano__localidad__nombre").annotate(total=Count("pk")).order_by("-total")
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


def _texto_alcance(filtros, segmentos, convocatorias, relevamientos):
    """Enunciado legible del recorte: encabeza la pantalla y las exportaciones (RN-16)."""
    if filtros.con_ventana:
        periodo = f"Del {filtros.desde:%d/%m/%Y} al {filtros.hasta:%d/%m/%Y}"
    else:
        periodo = "Todo el período"
    segmento = "Todos los segmentos"
    if filtros.segmento_id:
        seg = segmentos.filter(pk=filtros.segmento_id).first()
        segmento = f"Segmento {seg.nombre}" if seg else "Segmento sin acceso"
    convocatoria = "Todas las convocatorias"
    if filtros.convocatoria_id:
        conv = convocatorias.filter(pk=filtros.convocatoria_id).first()
        convocatoria = conv.nombre if conv else "Convocatoria sin acceso"
    relevamiento = "Todos los relevamientos"
    if filtros.relevamiento_id:
        rel = relevamientos.filter(pk=filtros.relevamiento_id).first()
        relevamiento = rel.nombre if rel else "Relevamiento sin acceso"
    canal = "Ambos canales"
    if filtros.canal:
        canal = "Link público" if filtros.canal == Relevamiento.Tipo.PUBLICO else "Territorial"
    return " · ".join((periodo, segmento, convocatoria, relevamiento, canal))


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------
def metricas(user, programa, filtros):
    """Todos los bloques del tablero para un programa, un usuario y un recorte.

    Los totales cierran entre sí por construcción: la serie semanal, los estados y
    la tabla de convocatorias salen del mismo queryset de formularios (CA-3).
    """
    segmentos = _segmentos_alcance(user, programa, filtros)
    convocatorias = _convocatorias_alcance(user, programa, filtros)
    relevamientos = _relevamientos_alcance(convocatorias, filtros)
    formularios = _formularios_de(relevamientos, filtros.desde, filtros.hasta)

    estados = _conteo_por(formularios, "estado", Formulario.Estado.choices)
    por_estado = {fila["clave"]: fila["total"] for fila in estados}
    total = sum(por_estado.values())
    aprobados = por_estado.get(Formulario.Estado.APROBADO, 0)
    rechazados = por_estado.get(Formulario.Estado.RECHAZADO, 0)
    lista_espera = ListaEspera.objects.filter(formulario__in=formularios, promovido=False).count()

    cupos = _cupo(user, programa, segmentos)
    conv_lista = list(convocatorias)
    rel_estados = _conteo_por(relevamientos, "estado", Relevamiento.Estado.choices)
    rel_por_estado = {fila["clave"]: fila["total"] for fila in rel_estados}

    indicadores = Indicadores(
        convocatorias_total=len(conv_lista),
        convocatorias_activas=sum(1 for c in conv_lista if c.activo),
        convocatorias_cerradas_vencimiento=sum(1 for c in conv_lista if not c.activo and c.cerrada_automaticamente),
        relevamientos_total=sum(rel_por_estado.values()),
        relevamientos_en_curso=sum(rel_por_estado.get(e, 0) for e in RELEVAMIENTOS_EN_CURSO),
        relevamientos_publicos=relevamientos.filter(tipo=Relevamiento.Tipo.PUBLICO).count(),
        formularios_recibidos=total,
        variacion_periodo_anterior=_variacion(relevamientos, filtros, total),
        aprobados=aprobados,
        tasa_aprobacion=_pct(aprobados, total),
        pendientes=por_estado.get(Formulario.Estado.ENVIADO, 0),
        cupo_total=sum(cupo for cupo, _ in cupos.values()),
        cupo_ocupado=sum(ocupado for _, ocupado in cupos.values()),
        lista_espera=lista_espera,
    )
    canales = _conteo_por(formularios, "relevamiento__tipo", Relevamiento.Tipo.choices)

    return Datos(
        programa_id=programa.pk,
        programa_nombre=programa.nombre,
        filtros=json.loads(filtros.clave()),
        alcance=_texto_alcance(filtros, segmentos, convocatorias, relevamientos),
        calculado_en=timezone.localtime().isoformat(timespec="seconds"),
        indicadores=indicadores,
        serie_semanal=_serie_semanal(formularios, filtros),
        estados=estados,
        canales=canales,
        convocatorias=_convocatorias(convocatorias, relevamientos, formularios, cupos),
        relevamientos_por_estado=rel_estados,
        embudo=_embudo(formularios, total, aprobados, rechazados, lista_espera),
        territoriales=_territoriales(relevamientos, formularios),
        localidades=_localidades(formularios, total),
    )


# ---------------------------------------------------------------------------
# Caché (RN-17, RN-18)
# ---------------------------------------------------------------------------
def _huella_alcance(user, programa):
    """Lo que hace distinto el alcance de dos usuarios: sus segmentos visibles y, para
    el regional, sus subsegmentos a cargo. Va en la clave para no compartir caché."""
    segmentos = list(segmentos_visibles(user).filter(programa=programa).order_by("pk").values_list("pk", flat=True))
    subsegmentos = []
    if es_coordinador_regional_becas(user):
        subsegmentos = list(subsegmentos_a_cargo(user).order_by("pk").values_list("pk", flat=True))
    return f"s{segmentos}|ss{subsegmentos}"


def clave_cache(user, programa, filtros):
    huella = hashlib.sha1(f"{filtros.clave()}|{_huella_alcance(user, programa)}".encode("utf-8")).hexdigest()
    return f"{CACHE_PREFIX}:{programa.pk}:{huella}"


def metricas_cacheadas(user, programa, filtros, recalcular=False):
    """``(datos, desde_cache)``. Con ``recalcular`` borra la entrada y recomputa."""
    clave = clave_cache(user, programa, filtros)
    if recalcular:
        cache.delete(clave)
    else:
        datos = cache.get(clave)
        if datos is not None:
            return datos, True
    datos = metricas(user, programa, filtros)
    cache.set(clave, datos, CACHE_TIMEOUT)
    return datos, False


# ---------------------------------------------------------------------------
# Respuestas de los formularios (RN-13 a RN-15)
# ---------------------------------------------------------------------------
def _origen_requisito(requisito):
    if requisito.subsegmento_id:
        return f"Requisito del subsegmento {requisito.subsegmento.nombre}"
    if requisito.segmento_id:
        return f"Requisito del segmento {requisito.segmento.nombre}"
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
            opciones=list(p.opciones or []),
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
            opciones=list(r.opciones or []),
            multiple=r.tipo == TipoCampo.SELECTOR_MULTIPLE,
        )
        for r in requisitos
    )
    return preguntas


def respuesta_de(data, clave):
    """**Única** lectura de la respuesta de un formulario a una pregunta.

    Hoy el contrato es ``Formulario.data = {"globales": {pk: valor}, "requisitos":
    {pk: valor}}`` con las claves en string (app de campo y link público). Cuando
    entre el constructor (#326) y las respuestas pasen a ``respuestas`` +
    ``definicion``, este es el único punto a tocar. Devuelve siempre una lista de
    strings: vacía si no respondió, de un elemento en selector simple, de N en
    múltiple.
    """
    ambito, _, pk = clave.partition(":")
    bolsa = (data or {}).get("globales" if ambito == "global" else "requisitos") or {}
    valor = bolsa.get(str(pk))
    if valor in (None, "", []):
        return []
    if isinstance(valor, (list, tuple)):
        return [str(v) for v in valor if v not in (None, "")]
    return [str(valor)]


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


def distribuciones_respuestas(user, programa, filtros, claves=None):
    """Distribución de una o varias preguntas en **una sola pasada** por los formularios.

    - La base de cada pregunta son los formularios que **tienen** esa pregunta
      respondida (RN-15); un formulario anterior al alta no cuenta como «sin respuesta».
    - En múltiple cada opción marcada suma una vez y los porcentajes pueden superar
      el 100 % (RN-14).
    - Una opción respondida que ya no está en el catálogo se lista igual, con el
      texto guardado (caso límite del análisis).

    ``claves=None`` calcula todas las del catálogo (exportación). Devuelve la lista en
    el orden del catálogo; las claves fuera del alcance se ignoran.
    """
    catalogo = preguntas_graficables(user, programa)
    if claves is not None:
        pedidas = set(claves)
        catalogo = [p for p in catalogo if p.clave in pedidas]
    if not catalogo:
        return []
    convocatorias = _convocatorias_alcance(user, programa, filtros)
    relevamientos = _relevamientos_alcance(convocatorias, filtros)
    formularios = _formularios_de(relevamientos, filtros.desde, filtros.hasta)

    conteos = {p.clave: Counter() for p in catalogo}
    bases = {p.clave: 0 for p in catalogo}
    for data in formularios.values_list("data", flat=True).iterator(chunk_size=500):
        for pregunta in catalogo:
            valores = respuesta_de(data, pregunta.clave)
            if not valores:
                continue
            bases[pregunta.clave] += 1
            for valor in valores if pregunta.multiple else valores[:1]:
                conteos[pregunta.clave][valor] += 1
    return [_armar_distribucion(p, conteos[p.clave], bases[p.clave]) for p in catalogo]


def distribucion_respuestas(user, programa, filtros, clave):
    """Una sola pregunta. Levanta ``ValueError`` si no existe o está fuera del alcance."""
    resultado = distribuciones_respuestas(user, programa, filtros, claves=[clave])
    if not resultado:
        raise ValueError("La pregunta no existe o no está en el alcance del usuario.")
    return resultado[0]


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
