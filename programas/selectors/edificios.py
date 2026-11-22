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

from programas.models import Dispositivo, Edificio, InspeccionEdificio, Sector
from programas.selectors.capacidad_dispositivo import instituciones_del_predio
from programas.selectors.vencimiento_inspecciones import tiene_relevamiento_vencido
from programas.services.detalle_dispositivo import (
    ESTADOS_EDILICIOS,
    aviso_de_vencimiento,
    estado_edilicio,
    registro_de_relevamientos,
)
from programas.services.dispositivos import (
    CAP_EDITAR,
    CAP_VER_EDIFICIOS,
    dispositivos_de_institucion,
    dispositivos_en_alcance,
    dispositivos_visibles,
    puede_configurar_dispositivos,
)
from programas.services.inspecciones import (
    edificios_en_alcance,
    edificios_para_asignar,
    inspecciones_visibles,
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


def _instituciones_por_edificio(user, ids):
    """Las instituciones que el usuario alcanza en cada edificio de ``ids``, con su enlace (dos consultas).

    Se **nombran** si están en el alcance de ``edificio.ver`` o de ``dispositivo.ver``; llevan ``url`` solo
    si además puede abrir su detalle. Las demás no aparecen: el llamador las cuenta (``otras``).
    """

    del_predio = instituciones_del_predio(user, ids, tambien=dispositivos_en_alcance(user, CAP_VER_EDIFICIOS))
    pks = {institucion["pk"] for lista in del_predio.values() for institucion in lista}
    abribles = set(dispositivos_visibles(user).filter(pk__in=pks).values_list("pk", flat=True) if pks else ())
    return {
        edificio_id: [
            {
                **institucion,
                "url": reverse("dispositivos:detalle", args=[institucion["pk"]])
                if institucion["pk"] in abribles
                else "",
            }
            for institucion in lista
        ]
        for edificio_id, lista in del_predio.items()
    }


def _quien(usuario):
    return (usuario.get_full_name() or usuario.username) if usuario else "sin responsable"


def _url_asignar(edificio_pk):
    return f"{reverse('dispositivos:relevamientos')}?asignar={edificio_pk}"


def _base_de_fila(edificio, ultima, instituciones, *, hoy, asignable):
    """Lo que la fila del listado y el encabezado de la ficha dicen igual de un edificio."""

    return {
        "pk": edificio.pk,
        "codigo": edificio.codigo,
        "nombre": edificio.nombre,
        "domicilio": edificio.domicilio_completo,
        "localidad": edificio.localidad,
        "activo": edificio.activo,
        "estado": estado_edilicio(ultima),
        "aviso": aviso_de_vencimiento(edificio.vencido, edificio.vence_el, hoy),
        "ultima_fecha": ultima.realizada_en if ultima else None,
        "instituciones": instituciones,
        "n_instituciones": edificio.n_instituciones,
        "otras": max(edificio.n_instituciones - len(instituciones), 0),
        "compartido": edificio.n_instituciones >= 2,
        "url_ver": reverse("dispositivos:edificio_detalle", args=[edificio.pk]),
        "url_asignar": _url_asignar(edificio.pk) if asignable else "",
    }


def filas_del_listado(user, edificios):
    """Las filas de una página del listado, en consultas fijas.

    ``edificios`` es la página de :func:`para_el_listado`. Cuatro consultas, no una por fila: las
    últimas realizadas (1), las instituciones del predio que el usuario alcanza (1), cuáles de ellas
    puede abrir (1) y los edificios donde puede crear un relevamiento (1).

    ``url_asignar`` es el modal de asignar de Relevamientos (P21) y va vacía si el edificio no admite
    un relevamiento nuevo o el usuario no lo coordina (R8).
    """

    edificios = list(edificios)
    if not edificios:
        return []
    ids = [edificio.pk for edificio in edificios]
    hoy = timezone.localdate()

    # Solo el estado y la fecha de la última: el Cambio 428 los deja ver sin alcance de inspección.
    ultimas = InspeccionEdificio.objects.in_bulk([edificio.ultima_id for edificio in edificios if edificio.ultima_id])
    instituciones = _instituciones_por_edificio(user, ids)
    asignables = set(edificios_para_asignar(user).filter(pk__in=ids).values_list("pk", flat=True))
    return [
        _base_de_fila(
            edificio,
            ultimas.get(edificio.ultima_id),
            instituciones.get(edificio.pk, []),
            hoy=hoy,
            asignable=edificio.pk in asignables,
        )
        for edificio in edificios
    ]


def _url_editar(user, edificio, instituciones):
    """El enlace al modal «Editar edificio» de la solapa Infraestructura de una institución del predio, o ``""``.

    La edición es del legajo (`dispositivo.editar` con alcance **institución**, RN5) y siempre se hace *desde* una
    institución que ocupa el edificio: es la regla de `services.edificios.editar_edificio`, que vuelve a exigirla
    al guardar. Acá solo se decide si se ofrece el botón: la primera institución del predio que el usuario puede
    abrir, que no está cerrada y sobre la que alcanza toda la institución (una consulta, sin importar cuántas).
    Si el predio es compartido, lo que se edita lo ven todas las instituciones: la solapa ya lo avisa.
    """

    candidatas = [
        institucion
        for institucion in instituciones
        if institucion["url"] and institucion["estado"] != Dispositivo.Estado.CERRADO
    ]
    if not candidatas:
        return ""
    editables = set(
        dispositivos_de_institucion(user, CAP_EDITAR)
        .filter(pk__in=[institucion["pk"] for institucion in candidatas])
        .values_list("pk", flat=True)
    )
    for institucion in candidatas:
        if institucion["pk"] in editables:
            return f"{reverse('dispositivos:detalle', args=[institucion['pk']])}?tab=infraestructura&edificio={edificio.pk}"
    return ""


def ficha_de_edificio(user, edificio, pagina=1):
    """Lo que dibuja la ficha propia del edificio (#1168): la de Infraestructura, a nivel edificio.

    ``edificio`` viene de :func:`para_el_listado` sobre :func:`edificios_visibles` (la vista ya resolvió
    el 404). Trae el encabezado de la fila, los datos, las instituciones del predio, los sectores
    activos de las instituciones que el usuario alcanza (con su cantidad de plazas, agrupados por
    institución), el último relevamiento y el registro fotográfico paginado.

    Cambio 428: la criticidad, las observaciones, quién relevó y el registro son del informe, que se
    abre solo por `inspecciones_visibles`. Sin ese alcance quedan el estado y la fecha.

    Costo fijo, sin importar instituciones, sectores, relevamientos ni fotos: la última con su alcance
    (1), instituciones y cuáles abre (2), si admite un relevamiento nuevo (1), sectores con plazas (1),
    COUNT y página del registro (2), fotos de la página (1) y, solo si la página trae uno en curso,
    quién puede ver su asignación (1).
    """

    hoy = timezone.localdate()
    visibles = inspecciones_visibles(user)
    ultima = (
        InspeccionEdificio.objects.select_related("realizada_por")
        .annotate(con_detalle=Exists(visibles.filter(pk=OuterRef("pk"))))
        .filter(pk=edificio.ultima_id)
        .first()
        if edificio.ultima_id
        else None
    )
    ve_detalle = ultima is not None and ultima.con_detalle
    instituciones = _instituciones_por_edificio(user, [edificio.pk]).get(edificio.pk, [])
    asignable = edificios_para_asignar(user).filter(pk=edificio.pk).exists()
    url_editar = _url_editar(user, edificio, instituciones)

    nombres = {institucion["pk"]: institucion["nombre"] for institucion in instituciones}
    sectores_por_institucion = {}
    for sector in (
        Sector.objects.filter(edificio=edificio, activo=True, dispositivo_id__in=list(nombres))
        .annotate(cantidad_plazas=Count("plazas", filter=Q(plazas__activa=True)))
        .order_by("nombre", "pk")
        .values("pk", "nombre", "tipo", "dispositivo_id", "cantidad_plazas")
    ):
        sectores_por_institucion.setdefault(sector["dispositivo_id"], []).append(
            {
                "pk": sector["pk"],
                "nombre": sector["nombre"],
                "tipo": Sector.Tipo(sector["tipo"]).label if sector["tipo"] in Sector.Tipo.values else sector["tipo"],
                "plazas": sector["cantidad_plazas"],
            }
        )
    sectores = [
        {"institucion": nombres[pk], "sectores": lista, "n_plazas": sum(item["plazas"] for item in lista)}
        for pk, lista in sorted(sectores_por_institucion.items(), key=lambda par: nombres[par[0]].lower())
    ]

    # El registro: el mismo que la ficha de Infraestructura, con la misma regla de alcance (Cambio 422).
    relevamientos, eventos = registro_de_relevamientos(
        user,
        InspeccionEdificio.objects.filter(edificio=edificio)
        .exclude(estado=InspeccionEdificio.Estado.CANCELADA)
        .select_related("edificio", "asignado_a", "realizada_por", "revisado_por"),
        pagina,
        # El informe vuelve a esta ficha (Cambio 487).
        sufijo_enlace=f"?edificio={edificio.pk}",
    )

    return {
        **_base_de_fila(edificio, ultima, instituciones, hoy=hoy, asignable=asignable),
        "latitud": edificio.latitud,
        "longitud": edificio.longitud,
        "ve_detalle": ve_detalle,
        "relevo": _quien(ultima.realizada_por) if ve_detalle else "",
        "observaciones": (ultima.observaciones or "").strip() if ve_detalle else "",
        "sectores": sectores,
        "n_sectores": sum(len(grupo["sectores"]) for grupo in sectores),
        "eventos": eventos,
        "relevamientos": relevamientos,
        "url_listado": reverse("dispositivos:edificios"),
        "url_editar": url_editar,
    }
