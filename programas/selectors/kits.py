"""Lo que se **lee** de las entregas de kits de Emergencia (etapa 4). Nada de acá escribe.

Las reglas —quién puede, en qué estado, qué queda en la traza— están en
``programas.services.kits``. Acá viven el listado de la mesa (E4), el detalle (E5), las
pendientes de un dispositivo (recepción web y M3) y el resumen de un destino (paso 1 del
asistente).

**Alcance (RN-4.8).** La mesa ve todas las entregas; la guardia, solo las de los
dispositivos donde tiene ``emergencia.recibir_kit`` (``dispositivos_en_alcance``). Las
funciones de la mesa no filtran —las autoriza la vista con ``MesaPermissionMixin``— y las
de la guardia reciben al usuario y recortan ellas.

Presupuestos de consultas (los fija ``programas.tests.test_emergencia_kits`` con
``@tag("performance")``; el ``read_timeout`` de ECOM es de 10 s):

=================================  ==========================================================
``listado_de_entregas`` (página)   2: las entregas con dispositivo y usuarios, y sus líneas.
``conteos_de_solapas``             1: un ``COUNT`` con filtro por solapa sobre la misma tabla.
``detalle_de_entrega``             3: líneas, traza y reposiciones (la entrega la trae la vista).
``entregas_pendientes_de``         2: las entregas abiertas del dispositivo y sus líneas.
``resumenes_de_destino``           5 fijas, haya 5 dispositivos o 500: alojadas, las tres de
                                   ``ocupacion_de_plazas`` y la última entrega de cada uno.
``mis_dispositivos``               2: los dispositivos en alcance y sus pendientes agrupadas.
=================================  ==========================================================

«Hoy» y el filtro por fecha son un rango calculado en Python (``__gte`` / ``__lt``): la
base de ECOM no tiene tablas de zona horaria y un ``Trunc*`` rompería solo en producción.
"""

from datetime import datetime, time, timedelta

from django.db.models import Count, Exists, Max, Min, OuterRef, Prefetch, Q
from django.utils import timezone

from programas.models import Dispositivo, Edificio, EntregaKit, Estadia, LineaEntrega, TrazaEntrega
from programas.services.dispositivos import (
    dispositivos_en_alcance,
    puede_operar_dispositivo,
    q_edificios_en_alcance,
)
from programas.services.emergencia_programa import CAP_ADMITIR, CAP_RECIBIR_KIT
from programas.services.ocupacion import ocupacion_de_plazas

Estado = EntregaKit.Estado

SOLAPA_ABIERTAS = "abiertas"
SOLAPA_DEMORADAS = "demoradas"
SOLAPA_CON_DIFERENCIAS = "con_diferencias"
SOLAPA_RECIBIDAS = "recibidas"
SOLAPA_CANCELADAS = "canceladas"

#: Las solapas de E4, en el orden en que se dibujan: clave y rótulo.
SOLAPAS = (
    (SOLAPA_ABIERTAS, "Abiertas"),
    (SOLAPA_DEMORADAS, "Demoradas (más de 48 h)"),
    (SOLAPA_CON_DIFERENCIAS, "Con diferencia sin cerrar"),
    (SOLAPA_RECIBIDAS, "Recibidas"),
    (SOLAPA_CANCELADAS, "Canceladas"),
)


def q_demorada(ahora=None):
    """En camino y sin recibir hace más de :attr:`EntregaKit.HORAS_PARA_DEMORADA` horas (Cambio 586).

    No se cancela sola: se avisa a la mesa y se la separa de lo «en camino» en el cálculo de faltante. Una sin
    marca de salida (``PREPARADA``) no entra: todavía no salió.
    """

    corte = (ahora or timezone.now()) - timedelta(hours=EntregaKit.HORAS_PARA_DEMORADA)
    return Q(estado=Estado.EN_CAMINO, despachada_en__lt=corte)


def _q_de_solapas(ahora):
    """«Recibidas» son las completas **y** las con diferencia ya cerrada: la mesa mira «Con diferencia sin cerrar»
    para resolver, y ahí solo queda lo que falta decidir."""

    return {
        SOLAPA_ABIERTAS: Q(estado__in=EntregaKit.ESTADOS_ABIERTOS),
        SOLAPA_DEMORADAS: q_demorada(ahora),
        SOLAPA_CON_DIFERENCIAS: Q(estado=Estado.RECIBIDA_CON_DIFERENCIAS, cierre_diferencia__isnull=True),
        SOLAPA_RECIBIDAS: Q(estado=Estado.RECIBIDA)
        | Q(estado=Estado.RECIBIDA_CON_DIFERENCIAS, cierre_diferencia__isnull=False),
        SOLAPA_CANCELADAS: Q(estado=Estado.CANCELADA),
    }


def q_entrega_sin_revisar():
    """Recibida con diferencias, sin cerrar y sin la observación de la mesa **posterior a la recepción**.

    No alcanza con mirar ``observacion_mesa``: el campo nace con la nota que la mesa le deja al
    dispositivo al armar la entrega. Lo que dice «la mesa la revisó» es la traza ``OBSERVADA``,
    que solo se escribe sobre una entrega ya recibida (``kits.observar_recepcion``). Cerrar la diferencia
    (reponer o aceptar) también apaga el aviso (Cambio 586).
    """

    observada = TrazaEntrega.objects.filter(entrega=OuterRef("pk"), accion=TrazaEntrega.Accion.OBSERVADA)
    return Q(estado=Estado.RECIBIDA_CON_DIFERENCIAS, cierre_diferencia__isnull=True) & ~Q(Exists(observada))


#: Cuántos ítems nombra el resumen de una fila antes de cortar con «…».
ITEMS_EN_EL_RESUMEN = 3


def nombre_de(usuario):
    """Nombre y apellido de la persona; si no los cargó, su usuario."""

    if usuario is None:
        return ""
    return usuario.get_full_name().strip() or usuario.get_username()


def fecha_hora(momento):
    return f"{timezone.localtime(momento):%d/%m/%Y %H:%M}" if momento else ""


def rango_del_dia(fecha):
    """``[desde, hasta)`` del día local ``fecha``, en momentos con zona. Sin ``Trunc*``."""

    zona = timezone.get_current_timezone()
    desde = timezone.make_aware(datetime.combine(fecha, time.min), zona)
    return desde, desde + timedelta(days=1)


def _lineas_ordenadas():
    return Prefetch("lineas", queryset=LineaEntrega.objects.select_related("item").order_by("id"))


# ---------------------------------------------------------------------------
# E4 · Listado de la mesa
# ---------------------------------------------------------------------------


def listado_de_entregas(filtros=None, ahora=None):
    """Las entregas de la mesa, de la más nueva a la más vieja, para paginar.

    ``filtros`` (todos opcionales): ``solapa`` (una de :data:`SOLAPAS`; sin ella o con una
    desconocida, todas), ``estado``, ``dispositivo`` (id), ``localidad`` (el texto exacto de
    la del dispositivo) y ``fecha`` (un ``date``: las armadas ese día local).

    Trae el dispositivo, el edificio, los dos usuarios y la entrega que repone con ``select_related`` y las líneas con
    un ``prefetch``: **2 consultas por página**, tenga 5 entregas o 50.
    """

    filtros = filtros or {}
    entregas = EntregaKit.objects.select_related(
        "dispositivo", "edificio", "armada_por", "recibida_por"
    ).prefetch_related(_lineas_ordenadas())
    q_solapa = _q_de_solapas(ahora or timezone.now()).get(filtros.get("solapa"))
    if q_solapa is not None:
        entregas = entregas.filter(q_solapa)
    if filtros.get("estado"):
        entregas = entregas.filter(estado=filtros["estado"])
    if filtros.get("dispositivo"):
        entregas = entregas.filter(dispositivo_id=filtros["dispositivo"])
    if filtros.get("localidad"):
        entregas = entregas.filter(dispositivo__localidad=filtros["localidad"])
    if filtros.get("fecha"):
        desde, hasta = rango_del_dia(filtros["fecha"])
        entregas = entregas.filter(creado__gte=desde, creado__lt=hasta)
    return entregas.order_by("-creado", "-id")


def conteos_de_solapas(ahora=None):
    """``{solapa: cantidad, "total": n}`` de todas las entregas. **1 consulta.**"""

    conteos = EntregaKit.objects.aggregate(
        total=Count("id"),
        **{solapa: Count("id", filter=q) for solapa, q in _q_de_solapas(ahora or timezone.now()).items()},
    )
    return {clave: valor or 0 for clave, valor in conteos.items()}


def destinos_con_entregas():
    """``(dispositivos, localidades)`` que tienen alguna entrega: las opciones de los filtros. **1 consulta.**"""

    filas = list(
        Dispositivo.objects.filter(entregas_de_kits__isnull=False)
        .distinct()
        .order_by("nombre", "id")
        .values_list("pk", "nombre", "localidad")
    )
    dispositivos = [(pk, nombre) for pk, nombre, _localidad in filas]
    localidades = sorted({localidad for _pk, _nombre, localidad in filas if localidad})
    return dispositivos, localidades


def resumen_de_items(lineas):
    """«3 Kit alimentario, 10 Colchón…»: lo enviado, en una línea. Sin consultas (líneas ya leídas)."""

    partes = [f"{linea.cantidad_enviada} {linea.nombre_visible}" for linea in lineas[:ITEMS_EN_EL_RESUMEN]]
    return ", ".join(partes) + ("…" if len(lineas) > ITEMS_EN_EL_RESUMEN else "")


def con_diferencias(entrega):
    return entrega.estado == Estado.RECIBIDA_CON_DIFERENCIAS


# ---------------------------------------------------------------------------
# E5 · Detalle
# ---------------------------------------------------------------------------


def entregas_para_detalle():
    """Las entregas con lo que el detalle muestra en la cabecera. Para un ``get_object_or_404``."""

    return EntregaKit.objects.select_related(
        "dispositivo", "edificio", "armada_por", "recibida_por", "repone_a", "cierre_diferencia_por"
    )


def lineas_de(entrega):
    """Las líneas con su ítem, en el orden en que se cargaron. **1 consulta.**"""

    return list(LineaEntrega.objects.filter(entrega=entrega).select_related("item").order_by("id"))


def traza_de(entrega):
    """La traza en el contrato de ``components/_linea_tiempo.html``, la más reciente arriba. **1 consulta.**"""

    eventos = []
    trazas = TrazaEntrega.objects.filter(entrega=entrega).select_related("usuario").order_by("-creado_en", "-id")
    for traza in trazas:
        cuando = fecha_hora(traza.creado_en)
        if traza.usuario_id:
            cuando = f"{cuando} · {nombre_de(traza.usuario)}"
        eventos.append({"cuando": cuando, "titulo": traza.accion_legible, "detalle": traza.detalle})
    return eventos


def diferencias_de(lineas):
    """Las líneas que llegaron distinto de lo enviado: ``[{"item", "nombre", "enviada", "recibida"}]``.

    Lo que muestra «Recibida · 2 ítems con diferencia» (M3-2 y el aviso de la recepción web).
    Sin consultas: las líneas ya traen su ítem.
    """

    return [
        {
            "item": linea.item_id,
            "nombre": linea.nombre_visible,
            "enviada": linea.cantidad_enviada,
            "recibida": linea.cantidad_recibida,
        }
        for linea in lineas
        if linea.cantidad_recibida is not None and linea.cantidad_recibida != linea.cantidad_enviada
    ]


def texto_de_recepcion(diferencias):
    """«Recibida completa» o «Recibida · 2 ítems con diferencia» (M3-2)."""

    if not diferencias:
        return "Recibida completa"
    cuantos = "1 ítem" if len(diferencias) == 1 else f"{len(diferencias)} ítems"
    return f"Recibida · {cuantos} con diferencia"


def reposiciones_de(entrega):
    """Las entregas que reponen a esta, de la más vieja a la más nueva. **1 consulta.**"""

    return list(EntregaKit.objects.filter(repone_a=entrega).order_by("creado", "id"))


def faltantes_de(lineas):
    """HU-4.5: ``[(TipoKit, cuánto faltó)]`` de las líneas que llegaron con menos y cuyo ítem sigue activo.

    Es la precarga de «Reponer». Un ítem que se desactivó no entra: una entrega nueva solo
    lleva ítems activos (RN-4.1). Sin consultas: las líneas ya traen su ítem.
    """

    return [
        (linea.item, linea.cantidad_enviada - linea.cantidad_recibida)
        for linea in lineas
        if linea.cantidad_recibida is not None
        and linea.cantidad_recibida < linea.cantidad_enviada
        and linea.item.activo
    ]


def faltantes_sin_item_activo(lineas):
    """``[(nombre, cuánto faltó)]`` de lo que llegó de menos y cuyo ítem **ya no está activo** (Cambio 586).

    Es lo que «Reponer» no puede cargar: la pantalla lo avisa en vez de descartarlo en silencio. Sin consultas.
    """

    return [
        (linea.nombre_visible, linea.cantidad_enviada - linea.cantidad_recibida)
        for linea in lineas
        if linea.cantidad_recibida is not None
        and linea.cantidad_recibida < linea.cantidad_enviada
        and not linea.item.activo
    ]


# ---------------------------------------------------------------------------
# El dispositivo: pendientes y alcance
# ---------------------------------------------------------------------------


def entregas_al_alcance(usuario):
    """Las entregas de los dispositivos donde ``usuario`` recibe kits (RN-4.8). Queryset.

    Es por donde la API busca una entrega por id: la de otro dispositivo no está en este
    queryset, así que es un 404 igual que un id inexistente. Trae el dispositivo y las líneas
    con su ítem (una consulta más, no una por línea).
    """

    return (
        EntregaKit.objects.filter(dispositivo__in=dispositivos_en_alcance(usuario, CAP_RECIBIR_KIT))
        .filter(q_edificios_en_alcance(usuario, CAP_RECIBIR_KIT, "dispositivo_id", "edificio_id"))
        .select_related("dispositivo")
        .prefetch_related(_lineas_ordenadas())
    )


def entregas_pendientes_de(dispositivo, usuario):
    """Las entregas que ``dispositivo`` todavía puede recibir, de la más vieja a la más nueva.

    ``EN_CAMINO`` y también ``PREPARADA`` —por si llegó sin que la mesa la marcara—, con sus
    líneas. Sin ``emergencia.recibir_kit`` sobre **ese** dispositivo devuelve un queryset
    vacío: nunca las de otro. **2 consultas** (más la del alcance).
    """

    if not puede_operar_dispositivo(usuario, dispositivo, CAP_RECIBIR_KIT):
        return EntregaKit.objects.none()
    return (
        EntregaKit.objects.filter(dispositivo=dispositivo, estado__in=EntregaKit.ESTADOS_ABIERTOS)
        .filter(q_edificios_en_alcance(usuario, CAP_RECIBIR_KIT, "dispositivo_id", "edificio_id"))
        .select_related("dispositivo")
        .prefetch_related(_lineas_ordenadas())
        .order_by("creado", "id")
    )


def entregas_por_recibir_de(dispositivo, edificio=None):
    """``(cantidad, pk de la más vieja, número de la más vieja)`` de las entregas por recibir, en UNA consulta.

    «Por recibir» es ``EntregaKit.ESTADOS_ABIERTOS``. Sin ``edificio`` cuenta TODA la institución, con o sin edificio
    (el aviso de la ficha); con ``edificio`` solo las de ese edificio exacto: la de otro edificio o sin edificio no
    cuenta (el aviso y el «Recibir kit» de su página). **No comprueba permisos**: la llama quien ya resolvió que el
    usuario recibe kits con alcance sobre lo que cuenta. La más vieja es la de menor número: ``2026-K-000031`` lleva el
    correlativo con seis dígitos y crece con el tiempo, igual que el id. Sin entregas, ``(0, None, None)``.
    """

    entregas = EntregaKit.objects.filter(dispositivo=dispositivo, estado__in=EntregaKit.ESTADOS_ABIERTOS)
    if edificio is not None:
        entregas = entregas.filter(edificio=edificio)
    resumen = entregas.aggregate(cantidad=Count("pk"), primera=Min("pk"), numero=Min("numero"))
    return resumen["cantidad"], resumen["primera"], resumen["numero"]


def entregas_de(dispositivo, usuario=None):
    """Todas las entregas de ``dispositivo``, de la más nueva a la más vieja, con sus líneas. Queryset.

    **No recorta por alcance**: la llama quien ya comprobó que el usuario recibe kits ahí
    (la API busca el dispositivo dentro de ``dispositivos_en_alcance``). Con ``usuario`` recorta además por
    edificio: con alcance Edificios, solo las entregas de sus edificios. 2 consultas.
    """

    return (
        EntregaKit.objects.filter(dispositivo=dispositivo)
        .filter(
            q_edificios_en_alcance(usuario, CAP_RECIBIR_KIT, "dispositivo_id", "edificio_id")
            if usuario is not None
            else Q()
        )
        .select_related("dispositivo")
        .prefetch_related(_lineas_ordenadas())
        .order_by("-creado", "-id")
    )


def mis_dispositivos(usuario):
    """Los dispositivos donde ``usuario`` es de la guardia de Emergencia, con sus entregas pendientes.

    ``[{"id", "nombre", "admite", "recibe_kits", "entregas_pendientes"}]``, por nombre. Entran
    los dispositivos donde tiene ``dispositivo.admitir`` **o** ``emergencia.recibir_kit`` con
    alcance (el Equipo, o todo si administra el programa Dispositivos). ``admite`` y
    ``recibe_kits`` dicen cuál de las dos tiene en cada uno —la regla de
    ``puede_operar_dispositivo``, resuelta en lote—. ``entregas_pendientes`` cuenta solo donde
    puede recibir kits: en uno donde solo admite, es 0.

    **4 consultas fijas**, sin N+1: la lista, los ids donde admite y donde recibe (acotados a
    la lista; con una capacidad que no tiene en el programa, ese alcance es vacío y no va a la
    base) y las entregas agrupadas.
    """

    recibe = dispositivos_en_alcance(usuario, CAP_RECIBIR_KIT)
    admite = dispositivos_en_alcance(usuario, CAP_ADMITIR)
    dispositivos = list(
        Dispositivo.objects.filter(Q(pk__in=recibe.values("pk")) | Q(pk__in=admite.values("pk")))
        .order_by("nombre", "id")
        .values("id", "nombre")
    )
    if not dispositivos:
        return []
    ids = [dispositivo["id"] for dispositivo in dispositivos]
    ids_admite = set(admite.filter(pk__in=ids).values_list("pk", flat=True))
    ids_recibe = set(recibe.filter(pk__in=ids).values_list("pk", flat=True))
    pendientes = (
        dict(
            EntregaKit.objects.filter(dispositivo_id__in=ids_recibe, estado__in=EntregaKit.ESTADOS_ABIERTOS)
            .filter(q_edificios_en_alcance(usuario, CAP_RECIBIR_KIT, "dispositivo_id", "edificio_id"))
            .order_by()
            .values("dispositivo_id")
            .annotate(n=Count("id"))
            .values_list("dispositivo_id", "n")
        )
        if ids_recibe
        else {}
    )
    return [
        {
            **dispositivo,
            "admite": dispositivo["id"] in ids_admite,
            "recibe_kits": dispositivo["id"] in ids_recibe,
            "entregas_pendientes": pendientes.get(dispositivo["id"], 0),
        }
        for dispositivo in dispositivos
    ]


# ---------------------------------------------------------------------------
# Paso 1 del asistente: el destino
# ---------------------------------------------------------------------------


def edificios_a_elegir(dispositivo, original=None):
    """Los edificios entre los que se elige al armar una entrega (Cambio 523).

    Solo si el destino ocupa más de uno y no hay una entrega que reponer con edificio de la que sacarlo; con uno
    solo queda fijo y no se elige. Solo cuentan los edificios **activos**: uno inactivo no recibe entregas nuevas
    (Cambio 586). Una consulta.
    """

    if original is not None and original.edificio_id is not None:
        return []
    vinculados = list(Edificio.objects.filter(dispositivos=dispositivo, activo=True).order_by("nombre"))
    return vinculados if len(vinculados) > 1 else []


def destinos_posibles(texto=""):
    """Los dispositivos a los que se les puede enviar una entrega: ``ACTIVO``, de cualquier tipo (RN-4.2).

    ``texto`` busca en el nombre o en la localidad. Queryset ordenado, para paginar.
    """

    dispositivos = Dispositivo.objects.filter(estado=Dispositivo.Estado.ACTIVO)
    texto = (texto or "").strip()
    if texto:
        dispositivos = dispositivos.filter(Q(nombre__icontains=texto) | Q(localidad__icontains=texto))
    return dispositivos.order_by("nombre", "id")


def resumenes_de_destino(dispositivos, momento=None):
    """``{id: resumen}`` de cada dispositivo, para elegir a quién enviarle (E4, paso 1).

    Cada resumen: ``alojadas`` (personas con estadía activa hoy), ``plazas_ocupadas`` y
    ``plazas_operativas`` (de ``ocupacion_de_plazas``, la misma cuenta que ve el dispositivo),
    y ``ultima_entrega`` — ``None`` o ``{"numero", "fecha", "con_diferencias"}``.

    **5 consultas fijas**, haya 5 dispositivos o 500: las estadías activas agrupadas, las
    tres de ``ocupacion_de_plazas`` en lote y la última entrega de cada uno (el ``MAX(id)``
    por dispositivo va como subconsulta).
    """

    ids = [getattr(dispositivo, "pk", dispositivo) for dispositivo in dispositivos]
    if not ids:
        return {}
    alojadas = dict(
        Estadia.objects.activas()
        .filter(dispositivo_id__in=ids)
        .order_by()
        .values("dispositivo_id")
        .annotate(n=Count("id"))
        .values_list("dispositivo_id", "n")
    )
    censo = ocupacion_de_plazas(ids, momento)
    ultimas_ids = (
        EntregaKit.objects.filter(dispositivo_id__in=ids)
        .order_by()
        .values("dispositivo_id")
        .annotate(ultima=Max("id"))
        .values("ultima")
    )
    ultimas = {
        entrega.dispositivo_id: {
            "numero": entrega.numero,
            "fecha": entrega.creado,
            "con_diferencias": con_diferencias(entrega),
        }
        for entrega in EntregaKit.objects.filter(pk__in=ultimas_ids)
    }
    resumenes = {}
    for pk in ids:
        conteo = censo.de(pk).conteo
        resumenes[pk] = {
            "alojadas": alojadas.get(pk, 0),
            "plazas_ocupadas": conteo.ocupadas or 0,
            "plazas_operativas": conteo.operativas,
            "ultima_entrega": ultimas.get(pk),
        }
    return resumenes


def resumen_destino(dispositivo, momento=None):
    """El resumen de **un** dispositivo (ver :func:`resumenes_de_destino`). 5 consultas."""

    return resumenes_de_destino([dispositivo], momento)[getattr(dispositivo, "pk", dispositivo)]
