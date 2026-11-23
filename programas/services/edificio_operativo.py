"""Página operativa del edificio, en el contexto de una institución (Cambio 563, PR 0 del lote «el edificio como unidad operativa»).

La página siempre se abre **desde una institución**: ``dispositivos/<pk>/edificios/<edificio_pk>/``. Eso saca la
ambigüedad del predio compartido: todo lo que se cuenta o se lista se filtra por institución **y** por edificio, y
lo de la otra institución del predio no aparece (decisión 2 del PM, 22/11/2026), ni siquiera su nombre.

Este módulo arma el encabezado: la franja de datos, el aviso del predio compartido, los indicadores, los contadores
de las seis solapas y las acciones que cada quien puede hacer. El contenido de cada solapa lo llenan los PR 1 a 7;
el panel de Sectores y plazas lo llena el PR 1 (Cambio 565); los demás son estados vacíos con un enlace a donde se opera hoy.

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

from core.rbac import puede
from programas.models import Edificio, InspeccionEdificio, Sector
from programas.selectors.emergencia_alojar import pendientes_por_recibir
from programas.selectors.emergencia_llegadas import aviso_de_pendientes
from programas.selectors.kits import entregas_por_recibir_de
from programas.services.bitacora import turno_vigente
from programas.services.detalle_dispositivo import (
    FILTRO_ORIGEN_EMERGENCIA,
    contar_alojadas,
    estadias_del_dispositivo,
    estado_edilicio,
    indicadores_de_plazas,
    normalizar_filtros,
    pildoras_de_estadias,
)
from programas.services.dispositivos import (
    CAP_EDITAR,
    CAP_VER,
    alcance_de_edificios,
    fecha_corta,
    miembros_del_edificio,
    nombre_de_persona,
    puede_configurar_dispositivos,
    puede_editar_legajo,
    puede_operar_edificio,
)
from programas.services.edificio_historial import contar_eventos_del_edificio, rotulo_del_turno
from programas.services.edificios import TEXTO_ACTIVAR, TEXTO_INACTIVAR, admite_editar_edificio
from programas.services.emergencia_programa import CAP_RECIBIR_KIT
from programas.services.equipo_dispositivo import (
    edificios_donde_agregar_persona,
    equipo_del_edificio,
    permisos_del_equipo,
)
from programas.services.estadias import CAP_ADMITIR, CAP_EGRESAR, CAP_VER_CIUDADANO, puede_ingresar_persona
from programas.services.ingreso import maneja_plazas, plazas_para_ingresar
from programas.services.inspecciones import edificios_para_asignar, inspecciones_visibles
from programas.services.kits import aviso_de_kits_por_recibir
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
        fecha = fecha_corta(ultima.realizada_en)
        if ultima.con_detalle:
            observacion = Truncator((ultima.observaciones or "").strip()).chars(_LARGO_OBSERVACION)
            detalle = f"{observacion or 'Sin observaciones'} · {fecha}"
        else:
            detalle = f"Relevado el {fecha}"
    return {"texto": estado["texto"], "tono": estado["tono"], "detalle": detalle}


def _contexto_equipo(user, dispositivo, edificio, url_pagina):
    """Lo propio del panel Equipo (solo con su solapa abierta): filas, quién gestiona, adónde vuelve cada una y qué ofrece.

    Cada fila trae ``url_cambiar_alcance`` (modal por URL, como en la ficha de la institución). Las acciones con
    confirmación (baja, responsable) vuelven a esta solapa con ``?next=``; los modales, con ``next_url``.
    """

    permisos = permisos_del_equipo(user, dispositivo)
    equipo = equipo_del_edificio(dispositivo, edificio.pk, permisos)
    volver = f"{url_pagina}?tab=equipo"
    if permisos.gestiona:
        for miembro in equipo:
            if miembro.puede_cambiar_alcance:
                consulta = urlencode({"tab": "equipo", "equipo": "alcance", "miembro": miembro.pk})
                miembro.url_cambiar_alcance = f"{url_pagina}?{consulta}"
    donde = edificios_donde_agregar_persona(None, dispositivo, permisos)
    puede_sumar = donde is None or edificio.pk in donde
    return {
        "equipo": equipo,
        "permisos_equipo": permisos,
        "puede_gestionar_equipo": permisos.gestiona,
        "puede_sumar_persona": puede_sumar,
        "url_equipo_sumar_modal": f"{url_pagina}?tab=equipo&equipo=sumar",
        "next_url": volver,
        "query_volver": "?" + urlencode({"next": volver}),
    }


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
        nombres.append(nombre_de_persona(miembro.usuario))
    visibles = nombres[:_NOMBRES_EN_LA_FRANJA]
    resto = len(nombres) - len(visibles)
    texto = " · ".join(visibles)
    if resto > 0:
        texto = f"{texto} y {resto} más"
    vigente = turno_vigente(dispositivo)
    return {
        "nombres": texto,
        "turno": rotulo_del_turno(vigente.turno) if vigente else "Sin turno en curso",
    }


def _kits_por_recibir(dispositivo, edificio):
    """``(cantidad, primera)``: las entregas **por recibir** de este edificio (en camino o preparadas) y el id de la más vieja.

    Solo las de ``edificio`` exacto: una de otro edificio de la misma institución, o sin edificio, no cuenta. Una
    consulta. Con una sola entrega, ``primera`` es esa entrega.
    """

    cantidad, primera, _numero = entregas_por_recibir_de(dispositivo, edificio)
    return cantidad, primera


def _recibir_kit(url_pagina, cantidad, primera):
    """El ítem «Recibir kit» del menú: ``(url, texto)``; sin entregas por recibir, ``("", "")`` y no se dibuja.

    Con una, va al detalle de esa entrega en la solapa Kits (el formulario de recepción, que al confirmar vuelve a la
    solapa). Con varias, a la solapa Kits, que lista primero las por recibir.
    """

    if not cantidad:
        return "", ""
    if cantidad == 1:
        return f"{url_pagina}?tab=kits&entrega={primera}", "Recibir kit"
    return f"{url_pagina}?tab=kits", f"Recibir kit ({cantidad})"


def _avisos(user, dispositivo, edificio, acciones):
    """Los avisos de arriba de la página: derivaciones y kits por recibir **en este edificio** (#1362).

    Mismo criterio de quién los ve que los de la ficha de la institución: ``dispositivo.admitir`` para las
    derivaciones y ``emergencia.recibir_kit`` para los kits, los dos con alcance sobre **este** edificio (``_acciones``
    ya lo resolvió: ``url_llegadas`` y ``url_recibir_kit`` vienen vacías sin él). Sin pendientes no hay aviso.
    Una consulta por aviso y ninguna para quien no puede verlo.
    """

    avisos = []
    if not edificio.activo:
        # Cambio 583: lo primero que se lee de un edificio inactivo; no consulta nada.
        avisos.append(
            {
                "tono": "info",
                "titulo": "Este edificio está inactivo.",
                "texto": "No se ofrece para relevamientos, sectores ni vínculos. "
                "Sus datos, relevamientos y equipo se conservan.",
            }
        )
    if acciones["url_llegadas"]:
        derivaciones = aviso_de_pendientes(
            pendientes_por_recibir(dispositivo, user, edificio),
            acciones["url_llegadas"],
            timezone.now(),
            en_este_edificio=True,
        )
        if derivaciones:
            avisos.append(derivaciones)
    aviso_kits = aviso_de_kits_por_recibir(
        acciones["kits_por_recibir"], acciones["url_recibir_kit"], en_este_edificio=True
    )
    if aviso_kits:
        avisos.append(aviso_kits)
    return avisos


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
    # Un edificio inactivo (Cambio 583) no se edita ni se desvincula: primero se reactiva.
    puede_editar = (
        edificio.activo
        and puede_editar_legajo(user, dispositivo, CAP_EDITAR)
        and admite_editar_edificio(dispositivo.estado)
    )
    # Inactivar y reactivar son del administrador del programa, no de una institución: el servicio lo vuelve a exigir.
    es_admin = puede_configurar_dispositivos(user)
    url_pagina = reverse("dispositivos:edificio_operativo", args=[dispositivo.pk, pk])
    kits_por_recibir, primera_entrega = _kits_por_recibir(dispositivo, edificio) if puede_kits else (0, None)
    url_recibir_kit, texto_recibir_kit = _recibir_kit(url_pagina, kits_por_recibir, primera_entrega)
    acciones = {
        "puede_kits": puede_kits,
        "kits_por_recibir": kits_por_recibir,
        # Un edificio inactivo no ofrece las acciones operativas (ingresar, bitácora): ofrece «Activar edificio».
        "url_ingreso": (
            reverse("dispositivos:ingreso_persona", args=[dispositivo.pk]) + como_param
            if edificio.activo
            and dispositivo.estado == dispositivo.Estado.ACTIVO
            and puede_ingresar_persona(user, dispositivo, puede_admitir=puede_admitir)
            else ""
        ),
        "url_bitacora": reverse("dispositivos:bitacora", args=[dispositivo.pk]) + como_param if edificio.activo else "",
        "url_inactivar": _url_cambiar_situacion("edificio_inactivar", edificio, url_pagina)
        if es_admin and edificio.activo
        else "",
        "url_reactivar": (
            _url_cambiar_situacion("edificio_reactivar", edificio, url_pagina)
            if es_admin and not edificio.activo
            else ""
        ),
        "url_editar": f"{reverse('dispositivos:detalle', args=[dispositivo.pk])}?edificio={pk}" if puede_editar else "",
        "url_llegadas": reverse("dispositivos:emergencia_llegadas", args=[dispositivo.pk]) + como_param
        if puede_admitir
        else "",
        "url_kits": reverse("emergencia:dispositivo_kits", args=[dispositivo.pk]) + como_param if puede_kits else "",
        # «Recibir kit» solo existe si hay algo por recibir en este edificio (#1361): una entrega, a su recepción; varias,
        # a la solapa Kits con las por recibir primero.
        "url_recibir_kit": url_recibir_kit,
        "texto_recibir_kit": texto_recibir_kit,
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
            "url_inactivar",
        )
    )
    return acciones


def _url_cambiar_situacion(nombre_de_ruta, edificio, url_pagina):
    """La ruta de inactivar o reactivar, con vuelta a esta página (``?next=``; la vista descarta lo que no sea del sitio)."""

    return f"{reverse(f'dispositivos:{nombre_de_ruta}', args=[edificio.pk])}?{urlencode({'next': url_pagina})}"


def contexto_del_edificio(user, dispositivo, edificio, tab_pedida=""):
    """Todo lo que dibuja la página operativa del edificio (encabezado, franja, indicadores y barra de solapas)."""

    con_plazas = maneja_plazas(dispositivo)
    acciones = _acciones(user, dispositivo, edificio)

    conteo = None
    indicadores = []
    if con_plazas:
        # Solo los sectores de este edificio: el censo se acota en la misma consulta.
        conteo = ocupacion_de_plazas(dispositivo, q_sectores=Q(edificio_id=edificio.pk)).de(dispositivo).conteo
        indicadores = indicadores_de_plazas(conteo, tipo=dispositivo.tipo)

    # Una fila sin alcance cargado vale «toda la institución»; los responsables van primero. Alimenta el contador y la
    # franja «Equipo en turno», que se ven con cualquier solapa abierta.
    equipo = miembros_del_edificio(dispositivo, edificio.pk)
    estado = _estado_edilicio(user, edificio)
    disponibles = solapas_disponibles(con_plazas=con_plazas, puede_kits=acciones["puede_kits"])
    pendientes_de_kit = acciones["kits_por_recibir"]
    url_institucion = reverse("dispositivos:detalle", args=[dispositivo.pk])
    tab = normalizar_solapa(tab_pedida, disponibles)
    url_pagina = reverse("dispositivos:edificio_operativo", args=[dispositivo.pk, edificio.pk])
    contexto = {
        "dispositivo": dispositivo,
        "edificio": edificio,
        "maneja_plazas": con_plazas,
        "tab": tab,
        # El mapa de plazas se arma solo con su solapa abierta: si no vino, el botón de la solapa navega a ella.
        "sectores_cargados": con_plazas and tab == "sectores",
        "url_solapa_sectores": f"{url_pagina}?tab=sectores",
        # Lo propio del panel Equipo (permisos, edificios de las filas, modales) se arma solo con su solapa abierta:
        # si no vino, el botón de la solapa navega a ella. El contador y la franja usan la lista corta de arriba.
        "equipo_cargado": tab == "equipo",
        "url_solapa_equipo": f"{url_pagina}?tab=equipo",
        # El Historial (Cambio 571) también se arma solo con su solapa abierta.
        "historial_cargado": tab == "historial",
        "url_solapa_historial": f"{url_pagina}?tab=historial",
        "solapas": disponibles,
        "avisos": _avisos(user, dispositivo, edificio, acciones),
        "url_institucion": url_institucion,
        "texto_inactivar": TEXTO_INACTIVAR,
        "texto_activar": TEXTO_ACTIVAR,
        # La insignia «Inactivo» junto al título (`page_header`); vacía con el edificio activo.
        "estado_header": {"texto": "" if edificio.activo else "Inactivo", "tono": "gray"},
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
            "estadias": contar_alojadas(dispositivo, q_alcance=q_estadias_del_edificio(edificio)),
            "kits": pendientes_de_kit,
            "equipo": len(equipo),
            # Una consulta (UNION ALL). Con la solapa abierta lo pone la vista: es el total del paginador de la lista.
            "historial": None
            if tab == "historial"
            else contar_eventos_del_edificio(user, dispositivo, edificio, puede_kits=acciones["puede_kits"]),
        },
        **acciones,
    }
    if tab == "equipo":
        contexto.update(_contexto_equipo(user, dispositivo, edificio, url_pagina))
    return contexto


def q_estadias_del_edificio(edificio):
    """Las estadías de este edificio: se derivan de la plaza, así que una sin plaza no tiene edificio (Cambio 566)."""

    return Q(plaza__sector__edificio_id=edificio.pk)


def estadias_del_edificio(user, dispositivo, edificio, estado, sector, pagina, origen=""):
    """La solapa Estadías (Cambio 566): las personas alojadas **de esta institución en este edificio**.

    La estadía no guarda el edificio: se deriva de su plaza (``q_estadias_del_edificio``), el mismo criterio del
    contador de la solapa, así que una estadía sin plaza no aparece acá (queda en «Personas alojadas» de la
    institución). Devuelve la página, las píldoras de filtro, si hay filtros activos y lo que el usuario puede hacer
    sobre **este** edificio (cambiar plaza, egresar, ver a la persona). ``mapa_de_ingreso`` es una función que arma, una
    sola vez y solo si hace falta, el mapa de plazas libres. Constante en consultas: sectores (1), COUNT y página (2).
    """

    sectores = list(
        Sector.objects.filter(dispositivo=dispositivo, edificio_id=edificio.pk, activo=True)
        .order_by("nombre")
        .values("pk", "nombre")
    )
    estado, sector = normalizar_filtros(estado, sector, {s["pk"] for s in sectores})
    origen = origen if origen == FILTRO_ORIGEN_EMERGENCIA else ""
    memo = []

    def mapa_de_ingreso():
        if not memo:
            memo.append(plazas_para_ingresar(dispositivo, usuario=user))
        return memo[0]

    return {
        "estadias": estadias_del_dispositivo(
            dispositivo,
            estado=estado,
            sector=sector,
            pagina=pagina,
            q_alcance=q_estadias_del_edificio(edificio),
            origen=origen,
        ),
        "pildoras": pildoras_de_estadias(estado, sector, sectores, origen=origen),
        "hay_filtros": bool(estado or sector or origen),
        "puede_cambiar": puede_operar_edificio(user, dispositivo, edificio.pk, CAP_ADMITIR),
        "puede_egresar": puede_operar_edificio(user, dispositivo, edificio.pk, CAP_EGRESAR),
        "puede_ver_ciudadano": puede(user, CAP_VER_CIUDADANO),
        "mapa_de_ingreso": mapa_de_ingreso,
    }
