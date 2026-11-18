"""Los edificios que un usuario puede ver, para la sección «Edificios» de Dispositivos (#1166).

Es la base del listado (#1167) y de la ficha (#1168), y es solo lectura: alta, edición, vínculo e
inactivación siguen en la solapa Infraestructura de cada institución (`services/edificios.py`).

Alcance (análisis #1164, R2 y R3)
---------------------------------

* Se ve con ``edificio.ver``: el admin del programa ve todos; con ``dispositivo.ver_todos``, los de
  toda la red; el resto, los de las instituciones donde integra el Equipo con un rol que la tiene
  (`inspecciones.edificios_en_alcance`).
* Por defecto, solo los **vigentes**: activos y con al menos una institución. Los inactivos y los
  que no tienen institución existen solo para el admin del programa, detrás de ``situacion``; para
  el resto no existen, ni en el listado ni en la ficha (404, Cambio 432).

El estado edilicio es el de la tarjeta de Infraestructura (Cambio 439): la criticidad de la
**última realizada**, o «Sin relevar». El filtro lo resuelve en SQL, no en Python, porque el
listado pagina la red entera.
"""

from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.urls import reverse
from django.utils import timezone

from programas.models import Edificio, InspeccionEdificio
from programas.selectors.capacidad_dispositivo import instituciones_del_predio
from programas.selectors.vencimiento_inspecciones import tiene_relevamiento_vencido
from programas.services.detalle_dispositivo import (
    ESTADOS_EDILICIOS,
    aviso_de_vencimiento,
    clave_estado_edilicio,
)
from programas.services.dispositivos import (
    CAP_VER_EDIFICIOS,
    dispositivos_en_alcance,
    dispositivos_visibles,
    puede_configurar_dispositivos,
)
from programas.services.inspecciones import (
    edificios_en_alcance,
    edificios_para_asignar,
    semaforo_de_inspeccion,
    subconsulta_ultima_realizada,
)

#: Situaciones del filtro que solo ve el admin del programa. ``""`` es la de siempre: vigentes.
SITUACION_VIGENTES = ""
SITUACION_SIN_INSTITUCION = "sin_institucion"
SITUACION_INACTIVOS = "inactivos"
SITUACION_TODOS = "todos"
SITUACIONES = (
    (SITUACION_VIGENTES, "Vigentes"),
    (SITUACION_SIN_INSTITUCION, "Sin institución"),
    (SITUACION_INACTIVOS, "Inactivos"),
    (SITUACION_TODOS, "Todos"),
)
_CLAVES_SITUACION = {clave for clave, _texto in SITUACIONES}

COMPARTIDO_SI = "si"
COMPARTIDO_NO = "no"

#: La criticidad que define cada estado del filtro (``None`` = sin ninguna realizada).
_CRITICIDAD_DE_ESTADO = {clave: criticidad for clave, _texto, criticidad in ESTADOS_EDILICIOS}

_VINCULOS = Edificio.dispositivos.through


def _con_institucion():
    return Exists(_VINCULOS.objects.filter(edificio_id=OuterRef("pk")))


def ve_situaciones(user):
    """Si ``user`` puede pedir inactivos y edificios sin institución: solo el admin del programa."""

    return puede_configurar_dispositivos(user)


def edificios_visibles(user, situacion=SITUACION_VIGENTES):
    """Queryset de los edificios que ``user`` ve, según la ``situacion`` pedida.

    Para quien no es admin del programa ``situacion`` se ignora: siempre vigentes. Un valor que no
    está en :data:`SITUACIONES` también vale como vigentes.
    """

    base = edificios_en_alcance(user, CAP_VER_EDIFICIOS)
    if not ve_situaciones(user) or situacion not in _CLAVES_SITUACION:
        situacion = SITUACION_VIGENTES
    if situacion == SITUACION_SIN_INSTITUCION:
        return base.filter(~_con_institucion())
    if situacion == SITUACION_INACTIVOS:
        return base.filter(activo=False)
    if situacion == SITUACION_TODOS:
        return base
    return base.filter(_con_institucion(), activo=True)


def _criticidad_de(campo_ultima):
    """La criticidad de la inspección cuyo id anotó ``campo_ultima`` en la fila."""

    return Subquery(InspeccionEdificio.objects.filter(pk=OuterRef(campo_ultima)).values("criticidad")[:1])


def filtrar_edificios(queryset, *, q="", localidad="", estado="", compartido=""):
    """Aplica los filtros del listado. Un valor vacío o desconocido no filtra."""

    texto = (q or "").strip()
    if texto:
        queryset = queryset.filter(Q(codigo__icontains=texto) | Q(nombre__icontains=texto) | Q(calle__icontains=texto))
    localidad = (localidad or "").strip()
    if localidad:
        queryset = queryset.filter(localidad=localidad)
    if estado in _CRITICIDAD_DE_ESTADO:
        criticidad = _CRITICIDAD_DE_ESTADO[estado]
        queryset = queryset.annotate(_ultima_para_filtro=subconsulta_ultima_realizada())
        if criticidad is None:
            queryset = queryset.filter(_ultima_para_filtro__isnull=True)
        else:
            queryset = queryset.annotate(_criticidad_para_filtro=_criticidad_de("_ultima_para_filtro")).filter(
                _criticidad_para_filtro=criticidad
            )
    if compartido in (COMPARTIDO_SI, COMPARTIDO_NO):
        queryset = queryset.annotate(_n_para_filtro=Count("dispositivos", distinct=True))
        queryset = (
            queryset.filter(_n_para_filtro__gte=2)
            if compartido == COMPARTIDO_SI
            else queryset.filter(_n_para_filtro__lt=2)
        )
    return queryset


def localidades_visibles(user, situacion=SITUACION_VIGENTES):
    """Las localidades no vacías de los edificios que ``user`` ve en esa ``situacion``, para el selector.

    Sigue la misma ``situacion`` que el listado: el admin que mira los inactivos o los que no tienen
    institución recibe sus localidades. Para el resto la situación se ignora, igual que en el listado.
    """

    return list(
        edificios_visibles(user, situacion=situacion)
        .exclude(localidad="")
        .order_by("localidad")
        .values_list("localidad", flat=True)
        .distinct()
    )


def para_el_listado(queryset):
    """Anota lo que la fila necesita, para que viaje en la misma consulta de la página.

    La última realizada, la cantidad de instituciones (todas, también las fuera de alcance, como
    `_predio` de Infraestructura), si hay un relevamiento en curso vencido y el próximo vencimiento.
    """

    return queryset.annotate(
        ultima_id=subconsulta_ultima_realizada(),
        n_instituciones=Count("dispositivos", distinct=True),
        vencido=tiene_relevamiento_vencido(),
        vence_el=Subquery(
            InspeccionEdificio.objects.filter(edificio=OuterRef("pk"), estado=InspeccionEdificio.Estado.ASIGNADA)
            .order_by("fecha_vencimiento", "pk")
            .values("fecha_vencimiento")[:1]
        ),
    ).order_by("nombre", "pk")


def filas_del_listado(user, edificios):
    """Las filas de una página del listado, en consultas fijas.

    ``edificios`` es la página de :func:`para_el_listado`. Cuatro consultas, no una por fila: las
    últimas realizadas (1), las instituciones del predio que el usuario
    alcanza (1), cuáles de ellas puede abrir (1) y los edificios donde puede crear un relevamiento (1).

    Las instituciones se **nombran** si están en el alcance de ``edificio.ver`` o de ``dispositivo.ver``
    del usuario; llevan **enlace** solo si además puede ver su detalle. Las demás se cuentan sin
    nombre (``otras``). ``url_asignar`` es el modal de asignar de Relevamientos (P21) y va vacía si
    el edificio no admite un relevamiento nuevo o el usuario no lo coordina (R8).
    """

    edificios = list(edificios)
    if not edificios:
        return []
    ids = [edificio.pk for edificio in edificios]
    hoy = timezone.localdate()

    # Solo el estado y la fecha de la última: el Cambio 428 los deja ver sin alcance de inspección.
    ultimas = InspeccionEdificio.objects.in_bulk([edificio.ultima_id for edificio in edificios if edificio.ultima_id])
    del_predio = instituciones_del_predio(user, ids, tambien=dispositivos_en_alcance(user, CAP_VER_EDIFICIOS))
    pks_instituciones = {institucion["pk"] for lista in del_predio.values() for institucion in lista}
    abribles = set(
        dispositivos_visibles(user).filter(pk__in=pks_instituciones).values_list("pk", flat=True)
        if pks_instituciones
        else ()
    )
    asignables = set(edificios_para_asignar(user).filter(pk__in=ids).values_list("pk", flat=True))
    url_asignar = reverse("dispositivos:relevamientos")

    filas = []
    for edificio in edificios:
        ultima = ultimas.get(edificio.ultima_id)
        semaforo = semaforo_de_inspeccion(ultima)
        instituciones = [
            {
                **institucion,
                "url": reverse("dispositivos:detalle", args=[institucion["pk"]])
                if institucion["pk"] in abribles
                else "",
            }
            for institucion in del_predio.get(edificio.pk, [])
        ]
        filas.append(
            {
                "pk": edificio.pk,
                "codigo": edificio.codigo,
                "nombre": edificio.nombre,
                "domicilio": edificio.domicilio_completo,
                "localidad": edificio.localidad,
                "activo": edificio.activo,
                "estado": {
                    "clave": clave_estado_edilicio(ultima),
                    "texto": semaforo.texto,
                    "tono": semaforo.tono,
                },
                "aviso": aviso_de_vencimiento(edificio.vencido, edificio.vence_el, hoy),
                "ultima_fecha": ultima.realizada_en if ultima else None,
                "instituciones": instituciones,
                "n_instituciones": edificio.n_instituciones,
                "otras": max(edificio.n_instituciones - len(instituciones), 0),
                "compartido": edificio.n_instituciones >= 2,
                "url_asignar": f"{url_asignar}?asignar={edificio.pk}" if edificio.pk in asignables else "",
            }
        )
    return filas
