"""Los edificios a la vista en la ficha de la institución (Cambio 570, PR 6 del lote «el edificio como unidad operativa»).

La ficha ya no opera: muestra sus edificios y lleva a la página de cada uno (``dispositivos/<pk>/edificios/<id>/``), que es
donde viven las plazas, los ingresos, los kits y la Emergencia. Este módulo completa las filas que arma
``detalle_dispositivo.infraestructura_del_dispositivo`` con lo que dibuja ``components/_tarjeta_edificio.html``:

* la **ocupación** del edificio, del mismo censo que la franja de indicadores (``OcupacionDispositivo.conteo_del_edificio``:
  no hay otra cuenta de plazas);
* **disponibles**, **kits pendientes**, **equipo** y los **movimientos de hoy**;
* el aviso de un edificio **sin plazas disponibles** (la alerta de advertencia de arriba de los indicadores).

Costo
-----

Constante en la cantidad de edificios: el censo ya lo pagó la ficha; los kits son una consulta agrupada, el equipo dos y los
movimientos de hoy una. Ninguna es por edificio. Las capacidades se resuelven una vez para toda la ficha.
"""

from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from programas.models import EntregaKit, Estadia
from programas.services.bitacora_detalle import plural as _plural
from programas.services.dispositivos import (
    alcance_de_edificios,
    contar_miembros_por_edificio,
    entero_de_parametro,
)
from programas.services.emergencia_programa import CAP_RECIBIR_KIT
from programas.services.ocupacion import tension_de_ocupacion

#: Cuántos edificios con lugar nombra el aviso antes de dejar de enumerarlos.
_EDIFICIOS_CON_LUGAR_EN_EL_AVISO = 3


def _kits_pendientes(dispositivo, edificio_ids):
    """``{edificio_id: por_recibir}`` de las entregas abiertas (en camino o preparadas) de cada edificio. Una consulta."""

    filas = (
        EntregaKit.objects.filter(
            dispositivo=dispositivo, edificio_id__in=edificio_ids, estado__in=EntregaKit.ESTADOS_ABIERTOS
        )
        .values("edificio_id")
        .annotate(por_recibir=Count("pk"))
    )
    return {fila["edificio_id"]: fila["por_recibir"] for fila in filas}


def _texto_de_kits(por_recibir):
    """«0 por recibir» o «3 por recibir», más su tono de texto.

    Nunca un número suelto: el 0 de «por recibir» se leía como «no se recibió nada» (#1365).
    """

    return f"{por_recibir} por recibir", "text-fg-warning" if por_recibir else "text-heading"


def _movimientos_de_hoy(dispositivo, edificio_ids, hoy):
    """``{edificio_id: (ingresos, egresos)}`` del día de ``hoy``. Una consulta.

    El edificio de una estadía es el de su plaza (``plaza → sector → edificio``), que el egreso conserva. El día se
    acota con un rango y no con ``__date``: en ECOM (MariaDB sin tablas de timezone) eso es ``CONVERT_TZ`` y da NULL.
    """

    desde = timezone.make_aware(datetime.combine(hoy, time.min))
    hasta = desde + timedelta(days=1)
    filas = (
        Estadia.objects.filter(dispositivo=dispositivo, plaza__sector__edificio_id__in=edificio_ids)
        .filter(
            Q(fecha_ingreso__gte=desde, fecha_ingreso__lt=hasta) | Q(fecha_egreso__gte=desde, fecha_egreso__lt=hasta)
        )
        .values("plaza__sector__edificio_id")
        .annotate(
            ingresos=Count("pk", filter=Q(fecha_ingreso__gte=desde, fecha_ingreso__lt=hasta)),
            egresos=Count("pk", filter=Q(fecha_egreso__gte=desde, fecha_egreso__lt=hasta)),
        )
    )
    return {fila["plaza__sector__edificio_id"]: (fila["ingresos"], fila["egresos"]) for fila in filas}


def _texto_de_movimientos(ingresos, egresos):
    partes = []
    if ingresos:
        partes.append(_plural(ingresos, "ingreso", "ingresos"))
    if egresos:
        partes.append(_plural(egresos, "egreso", "egresos"))
    return "Hoy: " + " · ".join(partes) if partes else "Hoy: sin movimientos"


def completar_tarjetas(filas, *, user, dispositivo, ocupacion, con_plazas, puede_recibir_kits):
    """Suma a cada fila de ``infraestructura_del_dispositivo`` lo que la tarjeta del edificio dibuja.

    ``ocupacion`` es la ``OcupacionDispositivo`` de la ficha (ya acotada al alcance de ``user``). Sin plazas en el tipo
    de la institución, la fila no lleva ocupación ni disponibles: la tarjeta no dibuja una barra vacía. Los kits solo se
    cuentan donde ``user`` puede recibirlos (``emergencia.recibir_kit`` sobre ese edificio), como en la página del edificio.
    ``puede_recibir_kits`` es lo que la vista ya resolvió para la institución: no se vuelve a preguntar.
    """

    if not filas:
        return filas
    ids = [fila["pk"] for fila in filas]
    hoy = timezone.localdate()

    alcance_kits = alcance_de_edificios(user, dispositivo, CAP_RECIBIR_KIT) if puede_recibir_kits else None
    ids_con_kits = [pk for pk in ids if alcance_kits is not None and alcance_kits.permite(pk)]
    kits = _kits_pendientes(dispositivo, ids_con_kits) if ids_con_kits else {}
    equipo = contar_miembros_por_edificio(dispositivo, ids)
    movimientos = _movimientos_de_hoy(dispositivo, ids, hoy) if con_plazas else {}

    for fila in filas:
        pk = fila["pk"]
        fila["predio_compartido"] = fila["otras_instituciones"] > 0
        if con_plazas:
            conteo = ocupacion.conteo_del_edificio(pk)
            tension = tension_de_ocupacion(conteo, tipo=dispositivo.tipo)
            fila["ocupacion"] = {
                "valor": conteo.ocupadas,
                "maximo": conteo.operativas,
                "porcentaje": tension.porcentaje,
                "tono": tension.tono,
                "etiqueta": tension.etiqueta,
                "texto": tension.texto if tension.hay_cifra else "",
                "nombre": f"Ocupación de {fila['nombre']}",
            }
            fila["disponibles"] = conteo.disponibles
            fila["tiene_plazas"] = conteo.totales > 0
            fila["movimientos"] = _texto_de_movimientos(*movimientos.get(pk, (0, 0)))
        else:
            fila["ocupacion"] = None
            fila["disponibles"] = None
            fila["tiene_plazas"] = False
            fila["movimientos"] = ""
        if pk in ids_con_kits:
            texto, clase = _texto_de_kits(kits.get(pk, 0))
            fila["kits"] = {"texto": texto, "clase": clase}
        else:
            fila["kits"] = None
        miembros = equipo.get(pk, 0)
        fila["equipo"] = (
            {"texto": _plural(miembros, "persona", "personas"), "clase": "text-heading"}
            if miembros
            else {"texto": "Sin nadie asignado", "clase": "text-fg-danger"}
        )
    return filas


def aviso_sin_plazas(filas, dispositivo):
    """La alerta de advertencia de un edificio sin plazas disponibles, o ``None``.

    Solo para una institución activa (si no, la alerta del encabezado ya dice por qué no admite ingresos) y para edificios
    que **tienen** plazas operativas y las tienen todas tomadas: un edificio sin plazas cargadas no es uno lleno. Uno
    solo se nombra y lleva su enlace; varios se resumen en una sola alerta. El texto sugiere a dónde ir: los edificios
    que sí tienen lugar.
    """

    if dispositivo.estado != dispositivo.Estado.ACTIVO:
        return None
    llenos = [fila for fila in filas if fila.get("tiene_plazas") and fila.get("disponibles") == 0]
    if not llenos:
        return None
    con_lugar = [fila["nombre"] for fila in filas if (fila.get("disponibles") or 0) > 0]
    if len(llenos) == 1:
        lleno = llenos[0]
        titulo = f"{lleno['nombre']} no tiene plazas disponibles"
        accion_url, accion_texto = lleno["url_abrir"], f"Ver {lleno['nombre']}"
    else:
        nombres_llenos = [fila["nombre"] for fila in llenos]
        nombres = ", ".join(nombres_llenos[:_EDIFICIOS_CON_LUGAR_EN_EL_AVISO])
        if len(nombres_llenos) > _EDIFICIOS_CON_LUGAR_EN_EL_AVISO:
            nombres += f" y {len(nombres_llenos) - _EDIFICIOS_CON_LUGAR_EN_EL_AVISO} más"
        titulo = f"{len(llenos)} edificios no tienen plazas disponibles"
        accion_url, accion_texto = "", ""
        con_lugar = [nombre for nombre in con_lugar if nombre not in nombres_llenos]
    if con_lugar:
        visibles = con_lugar[:_EDIFICIOS_CON_LUGAR_EN_EL_AVISO]
        listado = " o ".join(f"el {nombre}" for nombre in visibles)
        texto = f"Para ingresar a alguien hoy, abrí {listado}."
    elif len(llenos) == 1 and len(filas) == 1:
        texto = "Para ingresar a alguien hoy hace falta liberar una plaza."
    else:
        texto = "Ninguno de los edificios tiene lugar para ingresar a alguien hoy."
    if len(llenos) > 1:
        texto = f"{nombres}. {texto}"
    return {
        "tono": "warning",
        "icono": "triangle-exclamation",
        "titulo": titulo,
        "texto": texto,
        "accion_url": accion_url,
        "accion_texto": accion_texto,
    }


def nota_de_indicadores(cantidad):
    """El subtítulo de «Indicadores operativos»: cuánto suman y dónde está el detalle de cada edificio."""

    if cantidad <= 0:
        return "Derivados de plazas y estadías; no admiten carga manual."
    if cantidad == 1:
        return "Las cifras del edificio. El detalle está en su tarjeta."
    return f"Suma de los {cantidad} edificios. El detalle de cada uno está en su tarjeta."


# --------------------------------------------------------------------------- #
# Los enlaces de siempre: la ficha ya no tiene Sectores y plazas ni Infraestructura
# --------------------------------------------------------------------------- #

#: Los parámetros que abrían un modal del mapa en la solapa que se fue; el edificio no sabe de qué plaza son.
_PARAMETROS_DE_MODAL_DE_SECTORES = ("plaza", "editar_plaza", "editar_sector")


def redireccion_de_solapa_vieja(user, dispositivo, get):
    """A dónde va un enlace viejo a una solapa que la ficha ya no tiene, o ``None`` si la ficha lo atiende sola.

    * ``?tab=infraestructura&ver_edificio=<id>`` → el Estado edilicio de ese edificio.
    * ``?tab=infraestructura&agregar_persona=<id>`` → «Agregar persona al edificio» en el Equipo de ese edificio.
    * ``?tab=infraestructura&edificio=nuevo|vincular|<id>`` y ``?tab=infraestructura`` a secas: la ficha (los modales del
      edificio se abren acá, y la sección «Edificios» está siempre a la vista). No redirige.
    * ``?tab=sectores``: la página del edificio si hay uno solo a la vista o el pedido trae su
      ``sectores_edificio``; la pantalla de siempre «Sectores y plazas» (todos los edificios, con su filtro) si no, o si el
      enlace abría un modal del mapa (``plaza``, ``editar_plaza``, ``editar_sector``), que no sabe de qué edificio es.

    Un edificio ajeno, desvinculado o fuera del alcance de ``user`` no redirige a su página (daría 404): cae a la ficha,
    como el id que no existe. El destino se arma con ``reverse``; nada del pedido se copia crudo a la URL.
    """

    from django.urls import reverse
    from django.utils.http import urlencode

    from programas.services.edificio_operativo import edificio_de_la_institucion
    from programas.services.sectores_plazas import PARAM_EDIFICIO_SECTORES, edificios_para_filtrar

    tab = get.get("tab", "")
    if tab not in ("sectores", "infraestructura"):
        return None

    def pagina(edificio_id, **consulta):
        url = reverse("dispositivos:edificio_operativo", args=[dispositivo.pk, edificio_id])
        return f"{url}?{urlencode(consulta)}"

    if tab == "infraestructura":
        if get.get("edificio"):
            return None
        for parametro, consulta in (
            ("ver_edificio", {"tab": "edilicio"}),
            ("agregar_persona", {"tab": "equipo", "equipo": "sumar"}),
        ):
            pk = entero_de_parametro(get.get(parametro))
            if pk is not None and edificio_de_la_institucion(user, dispositivo, pk) is not None:
                return pagina(pk, **consulta)
        return None

    # Sectores y plazas
    if not any(parametro in get for parametro in _PARAMETROS_DE_MODAL_DE_SECTORES):
        edificios = edificios_para_filtrar(user, dispositivo)
        pedido = next((pk for pk, _nombre in edificios if str(pk) == get.get(PARAM_EDIFICIO_SECTORES, "")), None)
        if pedido is None and len(edificios) == 1:
            pedido = edificios[0][0]
        if pedido is not None:
            consulta = {"tab": "sectores"}
            if get.get("inactivos") == "1":
                consulta["inactivos"] = "1"
            return pagina(pedido, **consulta)
    consulta = {}
    for parametro in ("plaza", "editar_plaza", PARAM_EDIFICIO_SECTORES, "inactivos"):
        if get.get(parametro):
            consulta[parametro] = get[parametro]
    if get.get("editar_sector"):
        # En la pantalla de siempre el sector a editar viaja como `sector`: `?sector=` ya es el filtro de Estadías en la ficha.
        consulta["sector"] = get["editar_sector"]
    url = reverse("dispositivos:sectores", args=[dispositivo.pk])
    return f"{url}?{urlencode(consulta)}" if consulta else url
