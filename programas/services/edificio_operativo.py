"""Página operativa del edificio, en el contexto de una institución (Cambio 563, PR 0 del lote «el edificio como unidad operativa»).

La página siempre se abre **desde una institución**: ``dispositivos/<pk>/edificios/<edificio_pk>/``. Eso saca la
ambigüedad del predio compartido: todo lo que se cuenta o se lista se filtra por institución **y** por edificio, y
lo de la otra institución del predio no aparece (decisión 2 del PM, 22/11/2026), ni siquiera su nombre.

Este módulo arma el encabezado: la franja de datos, el aviso del predio compartido, los indicadores, los contadores
de las seis solapas y las acciones que cada quien puede hacer. El contenido de cada solapa lo llenan los PR 1 a 7;
mientras tanto cada panel es un estado vacío con un enlace a donde se opera hoy.

Autorización
------------

Una sola puerta, :func:`edificio_de_la_institucion`: el edificio tiene que estar vinculado a la institución **y** en el
alcance de lectura de quien mira (``alcance_de_edificios``). Un edificio ajeno, desvinculado o fuera de alcance da el
mismo ``None`` (404 en la vista) que un id que no existe. Cada acción se ofrece solo con su capacidad y su alcance
sobre **este** edificio; el servidor las vuelve a exigir en su propia ruta.

Costo
-----

Constante: no hay consultas por sector, por estadía, por miembro ni por kit. El censo son tres consultas, y cada
contador, una.
"""

from django.db.models import Exists, OuterRef, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.utils.text import Truncator

from programas.models import Edificio, EntregaKit, InspeccionEdificio
from programas.services.bitacora import turno_vigente
from programas.services.detalle_dispositivo import contar_alojadas, estado_edilicio, indicadores_de_plazas
from programas.services.dispositivos import (
    CAP_EDITAR,
    CAP_VER,
    alcance_de_edificios,
    puede_editar_legajo,
    puede_operar_edificio,
)
from programas.services.edificios import admite_editar_edificio
from programas.services.emergencia_programa import CAP_RECIBIR_KIT
from programas.services.equipo_dispositivo import (
    edificios_donde_agregar_persona,
    equipo_del_edificio,
    permisos_del_equipo,
)
from programas.services.estadias import CAP_ADMITIR, puede_ingresar_persona
from programas.services.ingreso import maneja_plazas
from programas.services.inspecciones import edificios_para_asignar, inspecciones_visibles
from programas.services.ocupacion import ocupacion_de_plazas

#: Las solapas de la página, en el orden en que se dibujan.
SOLAPAS = ("sectores", "estadias", "kits", "equipo", "edilicio", "historial")
SOLAPA_POR_DEFECTO = "sectores"

#: Cuántos nombres del Equipo caben en la franja de datos antes de «y N más».
_NOMBRES_EN_LA_FRANJA = 2
_LARGO_OBSERVACION = 60


def edificio_de_la_institucion(user, dispositivo, edificio_pk):
    """El edificio, o ``None``: vinculado a ``dispositivo`` y en el alcance de lectura de ``user``.

    ``None`` es el 404 de la vista, igual para un edificio que no existe, que no es de la institución o que queda
    fuera del alcance de quien mira (alcance Edificios: solo los suyos).
    """

    edificio = Edificio.objects.filter(pk=edificio_pk, dispositivos=dispositivo).first()
    if edificio is None:
        return None
    if not alcance_de_edificios(user, dispositivo, CAP_VER).permite(edificio.pk):
        return None
    return edificio


def solapas_disponibles(*, con_plazas, puede_kits):
    """Las solapas que existen para **esta** institución y **este** usuario.

    «Sectores y plazas» solo si el tipo maneja plazas (como P4); «Kits» solo con ``emergencia.recibir_kit`` sobre el
    edificio: las entregas se ven con esa capacidad.
    """

    return tuple(
        solapa for solapa in SOLAPAS if (solapa != "sectores" or con_plazas) and (solapa != "kits" or puede_kits)
    )


def normalizar_solapa(pedida, disponibles):
    """La solapa de ``?tab=`` si existe para este usuario; si no, la primera disponible (nunca un panel en blanco)."""

    if pedida in disponibles:
        return pedida
    return SOLAPA_POR_DEFECTO if SOLAPA_POR_DEFECTO in disponibles else disponibles[0]


def _domicilio(edificio):
    """El domicilio en hasta dos líneas: calle y número, y localidad y provincia."""

    calle = " ".join(parte for parte in (edificio.calle, edificio.numero) if parte)
    if edificio.piso_departamento:
        calle = f"{calle}, {edificio.piso_departamento}" if calle else edificio.piso_departamento
    zona = ", ".join(parte for parte in (edificio.localidad, edificio.provincia) if parte)
    return [linea for linea in (calle, zona) if linea]


def _fecha(momento):
    return timezone.localtime(momento).strftime("%d/%m/%Y")


def _estado_edilicio(user, edificio):
    """Estado de la franja y de la solapa: de la última relevada, con lo que el usuario puede ver de ella.

    Cambio 428: las observaciones y la criticidad son del informe, que se abre solo por ``inspecciones_visibles``;
    sin ese alcance quedan el estado y la fecha. Una consulta.
    """

    ultima = (
        InspeccionEdificio.objects.filter(edificio=edificio, estado=InspeccionEdificio.Estado.REALIZADA)
        .annotate(con_detalle=Exists(inspecciones_visibles(user).filter(pk=OuterRef("pk"))))
        .order_by("-realizada_en", "-pk")
        .first()
    )
    estado = estado_edilicio(ultima)
    if ultima is None:
        detalle = "Todavía no se relevó este edificio."
    else:
        fecha = _fecha(ultima.realizada_en)
        if ultima.con_detalle:
            observacion = Truncator((ultima.observaciones or "").strip()).chars(_LARGO_OBSERVACION)
            detalle = f"{observacion or 'Sin observaciones'} · {fecha}"
        else:
            detalle = f"Relevado el {fecha}"
    return {"texto": estado["texto"], "tono": estado["tono"], "detalle": detalle}


def _equipo_del_edificio(dispositivo, edificio, permisos):
    """Las personas activas del Equipo con alcance a este edificio: toda la institución o este edificio.

    Una fila sin alcance cargado vale «toda la institución». Los responsables van primero. Dos consultas, vengan 3
    o 300 miembros (las filas y el ``prefetch`` único de sus edificios).
    """

    return equipo_del_edificio(dispositivo, edificio.pk, permisos)


def _contexto_equipo(dispositivo, edificio, permisos, equipo, url_pagina):
    """Lo que la solapa Equipo necesita de las acciones: quién gestiona, adónde vuelve cada una y qué ofrece.

    Cada fila trae ``url_cambiar_alcance`` (modal por URL, como en la ficha de la institución). Las acciones con
    confirmación (baja, responsable) vuelven a esta solapa con ``?next=``; los modales, con ``next_url``.
    """

    volver = f"{url_pagina}?tab=equipo"
    if permisos.gestiona:
        for miembro in equipo:
            if miembro.puede_cambiar_alcance:
                consulta = urlencode({"tab": "equipo", "equipo": "alcance", "miembro": miembro.pk})
                miembro.url_cambiar_alcance = f"{url_pagina}?{consulta}"
    donde = edificios_donde_agregar_persona(None, dispositivo, permisos)
    puede_sumar = donde is None or edificio.pk in donde
    return {
        "permisos_equipo": permisos,
        "puede_gestionar_equipo": permisos.gestiona,
        "puede_sumar_persona": puede_sumar,
        "url_equipo_sumar_modal": f"{url_pagina}?tab=equipo&equipo=sumar",
        "next_url": volver,
        "query_volver": "?" + urlencode({"next": volver}),
    }


def _nombre(usuario):
    return usuario.get_full_name().strip() or usuario.get_username()


def _equipo_en_turno(dispositivo, equipo):
    """Los nombres para la franja y el turno que rige ahora: ``{"nombres", "turno"}``.

    El Equipo no está asignado a un turno (los turnos son de la institución): se nombra a quienes trabajan en este
    edificio y, aparte, el turno vigente.
    """

    nombres = []
    vistos = set()
    for miembro in equipo:
        if miembro.usuario_id in vistos:
            continue
        vistos.add(miembro.usuario_id)
        nombres.append(_nombre(miembro.usuario))
    visibles = nombres[:_NOMBRES_EN_LA_FRANJA]
    resto = len(nombres) - len(visibles)
    texto = " · ".join(visibles)
    if resto > 0:
        texto = f"{texto} y {resto} más"
    vigente = turno_vigente(dispositivo)
    return {
        "nombres": texto,
        "turno": f"Turno {vigente.turno.nombre.lower()}" if vigente else "Sin turno en curso",
    }


def _acciones(user, dispositivo, edificio):
    """Las acciones de la página y las URL de cada una, **solo** las que ``user`` puede hacer sobre este edificio.

    Una acción sin capacidad no se dibuja: queda en ``""``. Los destinos conservan sus rutas por institución y
    reciben ``?edificio=<id>``; las pantallas que todavía no lo leen lo ignoran.
    """

    pk = edificio.pk
    como_param = f"?edificio={pk}"
    puede_admitir = puede_operar_edificio(user, dispositivo, pk, CAP_ADMITIR)
    puede_kits = puede_operar_edificio(user, dispositivo, pk, CAP_RECIBIR_KIT)
    # Editar y desvincular son del legajo (RN5): alcance institución, y un dispositivo cerrado no cambia su edificio.
    puede_editar = puede_editar_legajo(user, dispositivo, CAP_EDITAR) and admite_editar_edificio(dispositivo.estado)
    url_pagina = reverse("dispositivos:edificio_operativo", args=[dispositivo.pk, pk])
    acciones = {
        "puede_kits": puede_kits,
        "url_ingreso": (
            reverse("dispositivos:ingreso_persona", args=[dispositivo.pk]) + como_param
            if dispositivo.estado == dispositivo.Estado.ACTIVO
            and puede_ingresar_persona(user, dispositivo, puede_admitir=puede_admitir)
            else ""
        ),
        "url_bitacora": reverse("dispositivos:bitacora", args=[dispositivo.pk]) + como_param,
        "url_editar": f"{reverse('dispositivos:detalle', args=[dispositivo.pk])}?tab=infraestructura&edificio={pk}"
        if puede_editar
        else "",
        "url_llegadas": reverse("dispositivos:emergencia_llegadas", args=[dispositivo.pk]) + como_param
        if puede_admitir
        else "",
        "url_kits": reverse("emergencia:dispositivo_kits", args=[dispositivo.pk]) + como_param if puede_kits else "",
        # «Recibir kit» lleva a la solapa Kits de esta página, donde cada entrega en camino se recibe (PR 3).
        "url_recibir_kit": f"{url_pagina}?tab=kits" if puede_kits else "",
        "url_relevamiento": (
            f"{reverse('dispositivos:relevamientos')}?asignar={pk}"
            if edificios_para_asignar(user).filter(pk=pk).exists()
            else ""
        ),
        "url_desvincular": (
            reverse("dispositivos:edificio_desvincular", args=[dispositivo.pk, pk]) if puede_editar else ""
        ),
    }
    acciones["hay_mas_acciones"] = any(
        acciones[clave]
        for clave in (
            "url_editar",
            "url_llegadas",
            "url_kits",
            "url_recibir_kit",
            "url_relevamiento",
            "url_desvincular",
        )
    )
    return acciones


def contexto_del_edificio(user, dispositivo, edificio, tab_pedida=""):
    """Todo lo que dibuja la página operativa del edificio (encabezado, franja, indicadores y barra de solapas)."""

    con_plazas = maneja_plazas(dispositivo)
    acciones = _acciones(user, dispositivo, edificio)

    conteo = None
    indicadores = []
    if con_plazas:
        # Solo los sectores de este edificio: el censo se acota en la misma consulta y, por si acaso, se lee el del edificio.
        censo = ocupacion_de_plazas(dispositivo, q_sectores=Q(edificio_id=edificio.pk)).de(dispositivo)
        conteo = censo.conteo_del_edificio(edificio.pk)
        indicadores = indicadores_de_plazas(conteo, tipo=dispositivo.tipo)

    url_pagina = reverse("dispositivos:edificio_operativo", args=[dispositivo.pk, edificio.pk])
    permisos = permisos_del_equipo(user, dispositivo)
    equipo = _equipo_del_edificio(dispositivo, edificio, permisos)
    estado = _estado_edilicio(user, edificio)
    disponibles = solapas_disponibles(con_plazas=con_plazas, puede_kits=acciones["puede_kits"])
    pendientes_de_kit = (
        EntregaKit.objects.filter(
            dispositivo=dispositivo, edificio=edificio, estado__in=EntregaKit.ESTADOS_ABIERTOS
        ).count()
        if acciones["puede_kits"]
        else 0
    )
    url_institucion = reverse("dispositivos:detalle", args=[dispositivo.pk])
    return {
        "dispositivo": dispositivo,
        "edificio": edificio,
        "maneja_plazas": con_plazas,
        "tab": normalizar_solapa(tab_pedida, disponibles),
        "solapas": disponibles,
        "url_institucion": url_institucion,
        "migas": [
            {"label": "Dispositivos", "url": ""},
            {"label": "Instituciones", "url": reverse("dispositivos:lista")},
            {"label": dispositivo.nombre, "url": url_institucion},
            {"label": edificio.nombre, "url": ""},
        ],
        "domicilio": _domicilio(edificio),
        "estado_edilicio": estado,
        "equipo_en_turno": _equipo_en_turno(dispositivo, equipo),
        # El aviso no nombra a la otra institución ni da ninguno de sus datos: solo dice que existe.
        "predio_compartido": edificio.dispositivos.exclude(pk=dispositivo.pk).exists(),
        "indicadores": indicadores,
        "contadores": {
            "sectores": conteo.totales if conteo is not None else 0,
            "estadias": contar_alojadas(dispositivo, q_alcance=Q(plaza__sector__edificio_id=edificio.pk)),
            "kits": pendientes_de_kit,
            "equipo": len(equipo),
        },
        "equipo": equipo,
        **_contexto_equipo(dispositivo, edificio, permisos, equipo, url_pagina),
        # Dónde se opera hoy cada solapa, hasta que los PR siguientes la llenen: el vacío no es un callejón sin salida.
        "enlaces_de_institucion": {
            "sectores": f"{url_institucion}?tab=sectores",
            "estadias": f"{url_institucion}?tab=estadias",
            "kits": acciones["url_kits"],
            "equipo": f"{url_institucion}?tab=equipo",
            "edilicio": f"{url_institucion}?tab=infraestructura&ver_edificio={edificio.pk}",
            "historial": f"{url_institucion}?tab=historial",
        },
        **acciones,
    }
