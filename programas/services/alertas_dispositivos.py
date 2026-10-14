"""Alertas del dispositivo (MVP v2, etapa 3 · #699): lo que alguien tiene que resolver.

Son reglas de aviso del registro genérico de ``core.services.vencimientos``
(:class:`~core.services.vencimientos.ReglaAviso`), ámbito :data:`AMBITO`. No hay un motor
propio ni una tabla de alertas:

* **Se derivan del dato cada vez que se piden.** Una alerta existe mientras su origen
  cumple la condición —el préstamo sigue vigente con el vencimiento pasado, el último
  relevamiento del edificio sigue siendo crítico— y deja de existir sola cuando alguien lo
  resuelve **en el origen**. No se cierran a mano y no hay nada que limpiar.
* **Avisan y nunca bloquean.** Ningún servicio las consulta: las lee el detalle del
  dispositivo (P4). Un dispositivo con todas las alertas encendidas admite ingresos,
  egresos, cambios de plaza y reservas igual que uno sin ninguna.
* **Consultas fijas.** Cada regla hace una o dos consultas, sin importar cuántas plazas,
  reservas o edificios tenga el dispositivo.

Las reglas, con los datos que existen hoy
-----------------------------------------

=============================  =========  ==============================================
Regla                          Severidad  Se resuelve
=============================  =========  ==============================================
Préstamo o reserva vencidos    alta       liberando la reserva o el préstamo
Edificio que requiere          alta       con un relevamiento nuevo que no sea crítico
intervención
Relevamiento vencido sin       media      registrando el resultado, o cancelándolo
realizar
Dispositivo activo sin turnos  media      configurando al menos un turno
Plazas fuera de servicio       baja       volviendo las plazas a servicio
=============================  =========  ==============================================

Las del mockup que no tienen datos todavía —tránsito vencido, permanencia mayor al
límite, turno sin cerrar, documentación vencida, fichas incompletas— quedan para cuando
existan sus modelos (ver el Cambio de esta task en ``docs/internal/requerimientos.md``).

Todo en hora local y comparando instantes: nada de ``Trunc*`` sobre un ``DateTimeField``.

Dónde se resuelve cada una, y para quién
----------------------------------------

Cada alerta lleva el enlace de la pantalla donde su origen se arregla. El enlace **depende
de quién mira**, y por una razón concreta: la pantalla de destino tiene su propia
capacidad, así que un enlace ofrecido a quien no la tiene es un 403 anunciado. Se ofrece
solo a quien va a poder entrar:

* préstamo o reserva vencida y plazas fuera de servicio → el **mapa de plazas** (P5), que
  desde el Cambio de esta entrada tiene las acciones que las resuelven. Lo ve quien ve el
  dispositivo, que es quien ya está leyendo estas alertas: sin condición;
* edificio crítico y relevamiento vencido → **Relevamientos** (P21), solo con
  ``inspeccion.asignar`` en el programa;
* dispositivo sin turnos → la **bitácora con el modal de turnos abierto**
  (``?turnos=1``), solo con ``dispositivo.editar`` sobre *ese* dispositivo, que es lo que
  la bitácora exige para abrirlo.

Sin la capacidad, la alerta sigue apareciendo **sin enlace**: avisar es de todos,
resolver no. Y ninguna bloquea nada, con enlace o sin él.
"""

from django.urls import reverse
from django.utils import timezone

from core.services.vencimientos import Aviso, ReglaAviso, registrar_aviso
from programas.models import Dispositivo, Edificio, InspeccionEdificio, Plaza, ReservaPlaza, TrazaDispositivo, Turno
from programas.services.dispositivos import puede_en_programa_dispositivos, puede_operar_dispositivo
from programas.services.inspecciones import CAP_ASIGNAR, subconsulta_ultima_realizada

AMBITO = "dispositivos"

#: La capacidad que la bitácora exige para abrir el modal de turnos (`CAP_EDITAR` de
#: `programas.services.bitacora`, escrita acá para no importar ese módulo por una cadena).
CAP_EDITAR = "dispositivo.editar"

#: Cómo se dibuja cada severidad con la pieza `_alerta.html`: tono e ícono.
TONOS = {"alta": "danger", "media": "warning", "baja": "info"}
ICONOS = {"alta": "triangle-exclamation", "media": "circle-exclamation", "baja": "circle-info"}

#: Cuántas plazas fuera de servicio se nombran en el texto antes de resumir el resto.
MAX_PLAZAS_NOMBRADAS = 5


def _url_mapa(dispositivo):
    return reverse("dispositivos:sectores", args=[dispositivo.pk])


def _url_relevamientos(usuario):
    """P21, solo para quien tiene ``inspeccion.asignar`` en el programa. Al resto le da 403."""

    if not puede_en_programa_dispositivos(usuario, CAP_ASIGNAR):
        return "", ""
    return reverse("dispositivos:relevamientos"), "Ver relevamientos"


def _url_turnos(dispositivo, usuario):
    """La bitácora con el modal de turnos abierto, solo con ``dispositivo.editar`` acá.

    El modal lo abre `BitacoraTurnoView` únicamente con esa capacidad sobre este
    dispositivo: sin ella el enlace llevaría a la bitácora con el modal cerrado y sin
    explicación.
    """

    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        return "", ""
    return f"{reverse('dispositivos:bitacora', args=[dispositivo.pk])}?turnos=1", "Configurar turnos"


# --- Préstamo o reserva vencidos sin liberar ----------------------------------------


def reservas_vencidas(dispositivo, momento=None, usuario=None):
    """Reservas y préstamos con el vencimiento pasado que nadie liberó ni consumió.

    La plaza ya cuenta como disponible —la vigencia es por tiempo
    (`ReservaPlaza.objects.vigentes`)—, pero la reserva sigue abierta: la persona no llegó
    o el préstamo no se devolvió, y nadie lo registró. Se resuelve liberándola.
    """

    momento = momento or timezone.now()
    reservas = (
        ReservaPlaza.objects.filter(
            plaza__sector__dispositivo=dispositivo,
            estado=ReservaPlaza.Estado.VIGENTE,
            hasta__lt=momento,
        )
        .select_related("plaza__sector")
        .order_by("hasta", "id")
    )
    for reserva in reservas:
        prestamo = reserva.tipo == ReservaPlaza.Tipo.PRESTAMO
        # La plaza y la fecha las dice el pie («origen · desde el …»): el texto no las repite.
        que, abierto, liberar = (
            ("el préstamo", "abierto", "liberarlo") if prestamo else ("la reserva", "abierta", "liberarla")
        )
        yield Aviso(
            titulo="Préstamo vencido sin liberar" if prestamo else "Reserva vencida sin liberar",
            texto=f"La plaza ya cuenta como disponible, pero {que} sigue {abierto}: falta {liberar}.",
            origen=f"Plaza {reserva.plaza.codigo} · {reserva.plaza.sector.nombre}",
            fecha=reserva.hasta,
            enlace=_url_mapa(dispositivo),
            accion="Liberar la plaza",
        )


# --- Plazas fuera de servicio --------------------------------------------------------


def plazas_fuera_de_servicio(dispositivo, momento=None, usuario=None):
    """Una sola alerta por dispositivo que nombra las plazas fuera de servicio y su motivo."""

    plazas = list(
        Plaza.objects.filter(
            sector__dispositivo=dispositivo,
            sector__activo=True,
            estado=Plaza.Estado.FUERA_SERVICIO,
        )
        .order_by("-modificado", "-id")
        .values_list("codigo", "motivo_fuera_servicio", "modificado")
    )
    if not plazas:
        return
    nombradas = ", ".join(f"{codigo} ({motivo})" for codigo, motivo, _m in plazas[:MAX_PLAZAS_NOMBRADAS])
    resto = len(plazas) - MAX_PLAZAS_NOMBRADAS
    if resto > 0:
        nombradas += f" y {resto} más"
    cantidad = len(plazas)
    yield Aviso(
        titulo=f"{cantidad} plaza{'s' if cantidad != 1 else ''} fuera de servicio",
        texto=f"{nombradas}. No cuentan como capacidad operativa hasta que vuelvan a servicio.",
        origen="Sectores y plazas",
        # La más vieja, no la última: el pie dice «desde cuándo pasa», y la alerta está
        # encendida desde que salió de servicio la primera de las plazas que nombra.
        fecha=min(modificado for _codigo, _motivo, modificado in plazas),
        enlace=_url_mapa(dispositivo),
        accion="Ver plazas",
    )


# --- Relevamiento edilicio -----------------------------------------------------------


def edificios_criticos(dispositivo, momento=None, usuario=None):
    """Edificios del dispositivo cuyo **último** relevamiento realizado es de criticidad alta.

    Mira la última realizada y no cualquiera: un relevamiento posterior que no sea
    crítico apaga la alerta. Dos consultas: los edificios con la última anotada (la misma
    definición que el semáforo) y esas inspecciones si son críticas.
    """

    edificios = dict(
        Edificio.objects.filter(dispositivos=dispositivo)
        .annotate(ultima_id=subconsulta_ultima_realizada())
        .order_by()
        .values_list("ultima_id", "nombre")
    )
    edificios.pop(None, None)
    if not edificios:
        return
    criticas = InspeccionEdificio.objects.filter(
        pk__in=edificios, criticidad=InspeccionEdificio.Criticidad.ALTA
    ).order_by("-realizada_en", "-pk")
    # Una sola vez para todas las críticas: la capacidad no cambia entre dos edificios.
    enlace, accion = _url_relevamientos(usuario)
    for inspeccion in criticas:
        yield Aviso(
            titulo="El edificio requiere intervención",
            # El edificio y la fecha van en el pie («Relevamiento edilicio · X · desde el …»).
            texto="El último relevamiento lo marcó con criticidad alta. No bloquea la operación del dispositivo.",
            origen=f"Relevamiento edilicio · {edificios[inspeccion.pk]}",
            fecha=inspeccion.realizada_en,
            enlace=enlace,
            accion=accion,
        )


def relevamientos_vencidos(dispositivo, momento=None, usuario=None):
    """Relevamientos en curso de los edificios del dispositivo con el vencimiento pasado.

    El mismo criterio que `InspeccionEdificio.vencida()`, en una consulta: «vencido» no es
    un estado, se deriva del vencimiento contra el día local.
    """

    hoy = timezone.localdate(momento) if momento else timezone.localdate()
    from programas.selectors.inspecciones import relevamientos_vencidos as consulta_vencidos

    inspecciones = (
        consulta_vencidos(hoy)
        .filter(edificio__dispositivos=dispositivo)
        .select_related("edificio")
        .order_by("fecha_vencimiento", "id")
    )
    enlace, accion = _url_relevamientos(usuario)
    for inspeccion in inspecciones:
        dias = (hoy - inspeccion.fecha_vencimiento).days
        yield Aviso(
            titulo="Relevamiento edilicio vencido",
            # El edificio y el día del vencimiento van en el pie: acá solo cuánto hace.
            texto=(
                f"Venció hace {dias} día{'s' if dias != 1 else ''} y todavía no se cargó. "
                "No bloquea la operación del dispositivo."
            ),
            origen=f"Relevamiento edilicio · {inspeccion.edificio.nombre}",
            fecha=inspeccion.fecha_vencimiento,
            enlace=enlace,
            accion=accion,
        )


# --- Turnos --------------------------------------------------------------------------


def sin_turnos(dispositivo, momento=None, usuario=None):
    """Un dispositivo activo sin turnos activos no puede cargar la bitácora.

    La fecha es la de su validación (la última traza `VALIDADO`): un dispositivo solo
    llega a activo validándose. Se filtra por la **acción** y no por `estado_nuevo`: la
    edición (`EDITADO`) guarda el estado de ese momento, así que un dispositivo activo
    editado después dejaría la alerta fechada en la última edición.
    """

    if dispositivo.estado != Dispositivo.Estado.ACTIVO:
        return
    if Turno.objects.filter(dispositivo=dispositivo, activo=True).exists():
        return
    desde = (
        TrazaDispositivo.objects.filter(dispositivo=dispositivo, accion="VALIDADO")
        .order_by("-creado_en", "-id")
        .values_list("creado_en", flat=True)
        .first()
    ) or dispositivo.creado
    # El alcance al dispositivo se pregunta **acá**, cuando la alerta se va a encender, y no
    # al principio: es una consulta, y un dispositivo con turnos no la tiene que pagar.
    enlace, accion = _url_turnos(dispositivo, usuario)
    yield Aviso(
        titulo="Sin turnos configurados",
        texto="No se puede cargar la bitácora hasta que la institución tenga al menos un turno activo.",
        origen="Turnos del dispositivo",
        fecha=desde,
        enlace=enlace,
        accion=accion,
    )


def registrar_reglas():
    for slug, descripcion, severidad, pendientes in (
        (
            "dispositivos.reserva_vencida",
            "Reserva o préstamo de plaza vencido que nadie liberó.",
            "alta",
            reservas_vencidas,
        ),
        (
            "dispositivos.edificio_critico",
            "El último relevamiento del edificio tiene criticidad alta.",
            "alta",
            edificios_criticos,
        ),
        (
            "dispositivos.relevamiento_vencido",
            "Relevamiento edilicio en curso con el vencimiento pasado.",
            "media",
            relevamientos_vencidos,
        ),
        (
            "dispositivos.sin_turnos",
            "Dispositivo activo sin turnos: no puede cargar la bitácora.",
            "media",
            sin_turnos,
        ),
        (
            "dispositivos.plazas_fuera_de_servicio",
            "Plazas fuera de servicio en sectores activos.",
            "baja",
            plazas_fuera_de_servicio,
        ),
    ):
        registrar_aviso(
            ReglaAviso(slug=slug, ambito=AMBITO, descripcion=descripcion, severidad=severidad, pendientes=pendientes)
        )


registrar_reglas()
