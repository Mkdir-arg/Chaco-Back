"""Lo que muestra el detalle de la estadía (P7 · MVP v2, etapa 3 · #698).

Lectura pura: no mira permisos ni decide nada del negocio. La vista resuelve quién puede
ver la pantalla y qué acciones se ofrecen; acá se arma, en **cuatro consultas fijas** más
las dos de la solapa Novedades, lo que se dibuja.

`detalle_de_estadia` arma las cuatro fijas:

1. Los movimientos de la estadía, de `programas.services.movimientos.linea_de_tiempo`
   —la única fuente de la línea de tiempo— con las plazas y sus sectores ya traídos. De
   esa misma lista salen la línea de tiempo (las últimas `TOPE_EVENTOS`), la tabla de la
   solapa Movimientos, el contador y el tramo en la plaza actual
   (`tramos_por_plaza`, que reparte la permanencia leyendo solo los movimientos).
2. El total de las otras estadías de la persona y cuántas son anteriores a esta (el
   «Reingreso»), en un `aggregate`.
3. Las últimas `TOPE_OTRAS` de esas otras estadías, solo si hay alguna.
4. Los turnos activos del dispositivo, **una vez**: el turno de cada movimiento —el
   «turno Tarde» del «cuándo» del mockup— lo resuelve `turno_vigente` en Python sobre
   esa lista, sin una consulta por evento.

Los movimientos se traen enteros a propósito: los de una estadía son operaciones
(ingreso, cambios de plaza, egreso), no la bitácora, y el tramo en la plaza actual
necesita la lista completa.

Las **novedades de la bitácora** no entran en esas tres: crecen todos los días, así que
se piden aparte y paginadas, en `novedades_de_estadia`, con su propio presupuesto
(`dispositivos_estadia_novedades`). Abrir la pantalla las cuesta igual —la solapa se
dibuja siempre—, pero el costo no crece con la historia de la persona.

Sin niveles de sensibilidad (los trae la ficha configurable de la Versión 2): las
secciones muestran solo datos que no son sensibles. Por eso no van las observaciones del
egreso —texto libre— ni los datos de contacto o de salud del legajo, que piden
`ciudadano.sensible`; la misma regla que `programas.selectors.trayectoria`.

**La bitácora es la excepción a esa regla, y es deliberada** (decisión de esta entrega,
MVP v2 etapa 3): el texto de una novedad es libre y puede contar un incidente o una
cuestión de salud, y aun así se muestra con lo que ya abre esta pantalla —`dispositivo.ver`
con alcance al dispositivo, más `ciudadano.ver`—, sin pedir `ciudadano.sensible`. Los
motivos:

* **Es el mismo dato, con una puerta más estrecha.** La novedad ya se lee entera en la
  bitácora del turno (P10) con `dispositivo.ver`, que es menos que lo que pide esta
  pantalla; esta solapa no agrega información, solo la ordena por persona. Esconderla acá
  no la protegería: la escondería de quien la necesita.
* **La audiencia es operativa, no analítica.** Quien abre el detalle de una estadía es el
  operador del dispositivo donde esa persona está alojada —el alcance lo exige el mixin
  de la vista—, y lo que pasó en los turnos anteriores es justamente lo que tiene que
  saber para recibir el turno. Las observaciones del egreso, en cambio, son una lectura
  de legajo, y por eso siguen afuera.
* **Nada se edita desde acá.** La solapa es de lectura y lleva a la bitácora: cargar y
  corregir piden `dispositivo.bitacora` y pasan por `services.bitacora`.

Cuando lleguen los niveles de sensibilidad de la Versión 2, la novedad es el candidato
natural a llevar uno: la decisión de hoy es que **mientras no existan**, la bitácora se
muestra, no que no deba clasificarse nunca.
"""

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils import timezone

from programas.models import EntradaBitacora, Estadia, MovimientoEstadia
from programas.services.bitacora import turno_vigente, turnos_activos
from programas.services.estadias import estado_visible
from programas.services.movimientos import linea_de_tiempo, tramos_por_plaza

#: Las solapas de P7 y la que abre la pantalla. La normalización es la misma que la de P4
#: (`services.detalle_dispositivo.normalizar_solapa`) y por el mismo motivo: un `?tab=`
#: que no existe dejaba la tarjeta entera en blanco.
SOLAPAS = ("ficha", "movimientos", "novedades")
SOLAPA_POR_DEFECTO = "ficha"


def normalizar_solapa(pedida):
    """La solapa de `?tab=` si existe; cualquier otra cosa, la de siempre."""

    return pedida if pedida in SOLAPAS else SOLAPA_POR_DEFECTO


#: La línea de tiempo llega recortada: la lista completa está en la solapa Movimientos.
TOPE_EVENTOS = 10
#: Otras estadías de la persona en la red; la trayectoria completa está en el legajo.
TOPE_OTRAS = 5

Tipo = MovimientoEstadia.Tipo

#: Tono del punto de la línea de tiempo: refuerza lo que dice el título, no lo reemplaza.
_TONO_MOVIMIENTO = {
    Tipo.INGRESO: "success",
    Tipo.CAMBIO_SECTOR: "warning",
    Tipo.CAMBIO_PLAZA: "warning",
    Tipo.EGRESO: "danger",
}

SIN_DATO = "—"


def _fecha_hora(momento):
    return timezone.localtime(momento).strftime("%d/%m/%Y %H:%M") if momento else SIN_DATO


def _nombre_de(usuario):
    if usuario is None:
        return ""
    return usuario.get_full_name() or usuario.username


def _plaza(plaza, *, con_sector=False):
    if plaza is None:
        return "sin plaza"
    return f"{plaza.sector.nombre} · {plaza.codigo}" if con_sector else plaza.codigo


def _duracion(delta):
    """«3 días y 4 h», «5 h» o «menos de 1 h»: la duración de un tramo, sin redondear para arriba."""

    horas = int(delta.total_seconds() // 3600)
    dias, horas = divmod(max(horas, 0), 24)
    if dias and horas:
        return f"{dias} día{'s' if dias != 1 else ''} y {horas} h"
    if dias:
        return f"{dias} día{'s' if dias != 1 else ''}"
    return f"{horas} h" if horas else "menos de 1 h"


def _turno_de(dispositivo, momento, turnos):
    """El nombre del turno en el que pasó algo, o cadena vacía si no hay ninguno.

    Sobre la lista de turnos ya cargada y en hora local, que es lo que `turno_vigente`
    resuelve: sin consulta por evento y sin un segundo lugar que calcule el turno.
    """

    situado = turno_vigente(dispositivo, momento, turnos=turnos)
    return situado.turno.nombre if situado is not None else ""


def _motivo_del_movimiento(movimiento, estadia):
    """El motivo que se puede mostrar.

    En el egreso, **el del catálogo de la estadía y nada más**: `MovimientoEstadia.motivo`
    puede traer las observaciones del egreso —texto libre— porque así lo guardaba
    `egresar_persona` sin motivo del catálogo y así reconstruyó la migración 0089 los
    egresos viejos. En los cambios de plaza el motivo es el que se pidió para el cambio.
    """

    if movimiento.tipo == Tipo.EGRESO:
        return estadia.motivo.nombre if estadia.motivo_id else ""
    return movimiento.motivo


def _detalle_del_movimiento(movimiento, estadia):
    """La línea que sigue al título: de qué plaza a cuál y por qué."""

    partes = []
    if movimiento.tipo == Tipo.INGRESO:
        partes.append(f"plaza {_plaza(movimiento.plaza_destino, con_sector=True)}")
    elif movimiento.tipo == Tipo.CAMBIO_SECTOR:
        origen = _plaza(movimiento.plaza_origen, con_sector=True)
        partes.append(f"{origen} → {_plaza(movimiento.plaza_destino, con_sector=True)}")
    elif movimiento.tipo == Tipo.CAMBIO_PLAZA:
        partes.append(f"{_plaza(movimiento.plaza_origen)} → {_plaza(movimiento.plaza_destino)}")
    motivo = _motivo_del_movimiento(movimiento, estadia)
    if motivo:
        partes.append(f"motivo: {motivo}")
    return " · ".join(partes)


def _evento(movimiento, estadia, turno=""):
    """Un movimiento en la forma de `components/_linea_tiempo.html`.

    El «cuándo» del mockup es «08/09 · 16:48 · turno Tarde · L. Méndez»: la fecha, la
    hora, el turno en el que pasó y quién lo registró. Sin turno para ese momento —un
    hueco entre turnos, o un dispositivo que todavía no los configuró— la línea va sin
    turno, no con uno inventado.
    """

    partes = [timezone.localtime(movimiento.momento).strftime("%d/%m/%Y · %H:%M")]
    if turno:
        partes.append(f"turno {turno}")
    responsable = _nombre_de(movimiento.responsable)
    if responsable:
        partes.append(responsable)
    return {
        "cuando": " · ".join(partes),
        "titulo": movimiento.get_tipo_display(),
        "detalle": _detalle_del_movimiento(movimiento, estadia),
        "tono": _TONO_MOVIMIENTO.get(movimiento.tipo, ""),
    }


def _fila_de_movimiento(movimiento, estadia, turno=""):
    """Un movimiento como fila de la tabla de la solapa Movimientos."""

    if movimiento.tipo == Tipo.CAMBIO_SECTOR:
        plaza = (
            f"{_plaza(movimiento.plaza_origen, con_sector=True)} → {_plaza(movimiento.plaza_destino, con_sector=True)}"
        )
    elif movimiento.tipo == Tipo.CAMBIO_PLAZA:
        # Dentro del mismo sector, como en la línea de tiempo: el sector no cambió.
        plaza = f"{_plaza(movimiento.plaza_origen)} → {_plaza(movimiento.plaza_destino)}"
    elif movimiento.tipo == Tipo.EGRESO:
        plaza = _plaza(movimiento.plaza_origen, con_sector=True)
    else:
        plaza = _plaza(movimiento.plaza_destino, con_sector=True)
    return {
        "cuando": _fecha_hora(movimiento.momento),
        "turno": turno or SIN_DATO,
        "tipo": movimiento.get_tipo_display(),
        "plaza": plaza,
        "motivo": _motivo_del_movimiento(movimiento, estadia) or SIN_DATO,
        "responsable": _nombre_de(movimiento.responsable) or SIN_DATO,
    }


def _seccion_persona(ciudadano):
    nacimiento = ciudadano.fecha_nacimiento.strftime("%d/%m/%Y") if ciudadano.fecha_nacimiento else SIN_DATO
    edad = ciudadano.edad
    return {
        "codigo": "persona",
        "titulo": "Datos personales",
        "campos": [
            {"etiqueta": "DNI", "valor": ciudadano.dni},
            {"etiqueta": "Fecha de nacimiento", "valor": nacimiento},
            {
                "etiqueta": "Edad",
                "valor": f"{edad} años" if edad is not None else SIN_DATO,
                "estado": "calculado",
            },
            {"etiqueta": "Género", "valor": ciudadano.get_genero_display() or SIN_DATO},
        ],
    }


def _seccion_plaza(estadia, tramos, momento):
    titulo = "Plaza actual" if estadia.activa else "Última plaza"
    if estadia.plaza_id is None:
        return {
            "codigo": "plaza",
            "titulo": titulo,
            "campos": [],
            "vacio_texto": "La estadía no tiene una plaza asignada.",
        }
    # El tramo en la plaza sale de los movimientos, igual que la línea de tiempo: si la
    # estadía no tiene movimiento de ingreso (cargada por fuera de los servicios) no se
    # inventa desde cuándo está ahí.
    tramo = tramos[-1] if tramos and tramos[-1].plaza_id == estadia.plaza_id else None
    campos = [
        {"etiqueta": "Sector", "valor": estadia.plaza.sector.nombre},
        {"etiqueta": "Plaza", "valor": estadia.plaza.codigo},
        {"etiqueta": "Desde", "valor": _fecha_hora(tramo.desde) if tramo else SIN_DATO},
        {
            "etiqueta": "Tiempo en la plaza",
            "valor": _duracion(tramo.duracion) if tramo else SIN_DATO,
            "estado": "calculado",
        },
    ]
    return {"codigo": "plaza", "titulo": titulo, "campos": campos}


def _seccion_estadia(estadia, dias):
    return {
        "codigo": "estadia",
        "titulo": "Estadía",
        "campos": [
            {"etiqueta": "Dispositivo", "valor": estadia.dispositivo.nombre},
            {"etiqueta": "Ingreso", "valor": _fecha_hora(estadia.fecha_ingreso)},
            {
                "etiqueta": "Permanencia",
                "valor": f"{dias} día{'s' if dias != 1 else ''}",
                "estado": "calculado",
            },
            {"etiqueta": "Registró el ingreso", "valor": _nombre_de(estadia.ingresada_por) or SIN_DATO},
        ],
    }


def _seccion_egreso(estadia):
    return {
        "codigo": "egreso",
        "titulo": "Egreso",
        "campos": [
            {"etiqueta": "Fecha y hora", "valor": _fecha_hora(estadia.fecha_egreso)},
            {"etiqueta": "Motivo", "valor": estadia.motivo.nombre if estadia.motivo_id else SIN_DATO},
            {"etiqueta": "Destino", "valor": estadia.destino_egreso or SIN_DATO},
            {
                "etiqueta": "Pertenencias devueltas y firmadas",
                "valor": "Sí" if estadia.pertenencias_devueltas else "No",
            },
            {"etiqueta": "Registró el egreso", "valor": _nombre_de(estadia.egresada_por) or SIN_DATO},
        ],
    }


def _otra_estadia(estadia):
    estado, tono = estado_visible(estadia)
    donde = estadia.dispositivo.nombre
    if estadia.plaza_id:
        donde = f"{donde} · {_plaza(estadia.plaza, con_sector=True)}"
    ingreso = timezone.localtime(estadia.fecha_ingreso).strftime("%d/%m/%Y")
    if estadia.fecha_egreso:
        periodo = f"del {ingreso} al {timezone.localtime(estadia.fecha_egreso):%d/%m/%Y}"
    else:
        periodo = f"desde el {ingreso}"
    return {"estado": estado, "tono": tono, "detalle": f"{donde} · {periodo}"}


def detalle_de_estadia(estadia, momento=None):
    """El contexto de P7 para `estadia`, que llega con `ciudadano`, `dispositivo`,
    `plaza__sector`, `motivo`, `ingresada_por` y `egresada_por` ya traídos.

    Tres consultas fijas (ver el docstring del módulo), sin importar cuántos movimientos
    ni cuántas otras estadías tenga la persona.
    """

    momento = momento or timezone.now()
    ciudadano = estadia.ciudadano

    movimientos = list(linea_de_tiempo(estadia).select_related("plaza_origen__sector", "plaza_destino__sector"))
    tramos = tramos_por_plaza(estadia, movimientos, momento)
    recientes = movimientos[::-1]
    dias = estadia.dias_de_permanencia(momento)
    # Los turnos del dispositivo **una sola vez**, y el turno de cada movimiento resuelto
    # en Python sobre esa lista: `turno_vigente` acepta los turnos ya cargados justamente
    # para que nadie haga una consulta por evento.
    turnos = turnos_activos(estadia.dispositivo)

    otras = Estadia.objects.filter(ciudadano_id=estadia.ciudadano_id).exclude(pk=estadia.pk)
    cuentas = otras.aggregate(
        total=Count("pk"),
        anteriores=Count("pk", filter=Q(fecha_ingreso__lt=estadia.fecha_ingreso)),
    )
    otras_estadias = []
    if cuentas["total"]:
        otras_estadias = [
            _otra_estadia(otra) for otra in otras.select_related("dispositivo", "plaza__sector")[:TOPE_OTRAS]
        ]

    ubicacion = estadia.dispositivo.nombre
    if estadia.plaza_id:
        ubicacion = f"{ubicacion} · {estadia.plaza.sector.nombre} · plaza {estadia.plaza.codigo}"

    secciones = [
        _seccion_persona(ciudadano),
        _seccion_plaza(estadia, tramos, momento),
        _seccion_estadia(estadia, dias),
    ]
    egreso = None
    if not estadia.activa:
        secciones.append(_seccion_egreso(estadia))
        motivo = estadia.motivo.nombre if estadia.motivo_id else ""
        egreso = {
            "titulo": "Estadía cerrada",
            "texto": f"Egresó el {_fecha_hora(estadia.fecha_egreso)}" + (f" · motivo: {motivo}." if motivo else "."),
        }

    estado, tono = estado_visible(estadia)
    # La línea que acompaña al nombre en el modal de egreso, como en la solapa Estadías del dispositivo (P9).
    resumen = f"Ingreso {_fecha_hora(estadia.fecha_ingreso)}"
    if estadia.plaza_id:
        resumen = f"{resumen} · plaza {estadia.plaza.codigo}"
    resumen = f"{resumen} · {dias} día{'s' if dias != 1 else ''} de permanencia"
    return {
        "persona": {"nombre_completo": ciudadano.nombre_completo, "dni": ciudadano.dni, "edad": ciudadano.edad},
        "ubicacion": ubicacion,
        "estadia": {
            "estado": estado,
            "tono": tono,
            "activa": estadia.activa,
            "reingreso": bool(cuentas["anteriores"]),
            "ingreso": _fecha_hora(estadia.fecha_ingreso),
            "dias": dias,
            "resumen": resumen,
        },
        "egreso": egreso,
        "secciones": secciones,
        "eventos": [
            _evento(movimiento, estadia, _turno_de(estadia.dispositivo, movimiento.momento, turnos))
            for movimiento in recientes[:TOPE_EVENTOS]
        ],
        "movimientos": [
            _fila_de_movimiento(movimiento, estadia, _turno_de(estadia.dispositivo, movimiento.momento, turnos))
            for movimiento in recientes
        ],
        "n_movimientos": len(movimientos),
        "hay_mas_eventos": len(movimientos) > TOPE_EVENTOS,
        "otras_estadias": otras_estadias,
        "n_otras_estadias": cuentas["total"],
    }


# --------------------------------------------------------------------------- #
# Solapa «Novedades» (P7 · #697)
# --------------------------------------------------------------------------- #

#: Las novedades sí crecen todos los días: se paginan, y no entran en las tres consultas
#: fijas de `detalle_de_estadia`.
NOVEDADES_POR_PAGINA = 20


def novedades_de_estadia(estadia, pagina=None):
    """Las novedades de la bitácora en las que la persona está involucrada, paginadas.

    Solo la versión vigente de cada novedad (`EntradaBitacora.objects.vigentes()`): las
    reemplazadas se miran en la bitácora del turno. De lectura. **Dos consultas fijas**
    —el ``COUNT`` del paginador y la página, con el responsable traído—, sin importar
    cuántas novedades tenga la persona. Devuelve el ``Page`` con filas ya armadas: al
    template no llega ningún modelo.
    """

    entradas = (
        EntradaBitacora.objects.vigentes()
        .filter(personas=estadia)
        .select_related("responsable")
        .only(
            "id",
            "momento",
            "tipo",
            "texto",
            "version",
            "responsable__username",
            "responsable__first_name",
            "responsable__last_name",
        )
        .order_by("-momento", "-id")
    )
    page = Paginator(entradas, NOVEDADES_POR_PAGINA).get_page(pagina)
    page.object_list = [
        {
            "cuando": _fecha_hora(entrada.momento),
            "categoria": entrada.get_tipo_display(),
            "tono": EntradaBitacora.TONO_POR_TIPO.get(entrada.tipo, "") or "gray",
            "texto": entrada.texto,
            "version": entrada.version,
            "autor": _nombre_de(entrada.responsable) or SIN_DATO,
        }
        for entrada in page.object_list
    ]
    return page
