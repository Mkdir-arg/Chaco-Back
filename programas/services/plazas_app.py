"""«Plazas y estadías» para la app de campo (Cambio 596): los edificios que el usuario ve, el mapa de camas de uno y sus estadías.

Es la lectura de lo que la web muestra en la página operativa del edificio (``EdificioOperativoView``) con el mismo alcance
y las mismas reglas: nada de reglas nuevas, solo otra forma de entregarlas. Quién ve qué sale de
``q_edificios_en_alcance`` / ``edificio_de_la_institucion`` (``dispositivo.ver``), y qué puede hacer con cada cama, de
``acciones_de_plaza`` con las capacidades ``dispositivo.admitir|egresar|editar`` y ``ciudadano.ver`` **sobre este edificio**.

``mapa_del_edificio`` es la pieza reutilizable: la leen el endpoint ``.../mapa/`` y, para devolver el mapa ya
actualizado, las acciones de la app (egreso, cambio de plaza, reservar, liberar…).

Costo
-----

Constante respecto de la cantidad de camas: el censo (3 consultas), las plazas (1), sus estados (2), las reservas
abiertas (1) y las estadías de las camas ocupadas (1), más lo que cuestan las capacidades. Nada por cama ni por sector.
"""

from django.db.models import Q
from django.utils import timezone

from core.rbac import puede
from programas.models import Edificio, Estadia, ReservaPlaza
from programas.selectors.estadia_origen_emergencia import marcas_de_emergencia
from programas.services.detalle_dispositivo import FILTRO_ALOJADAS, FILTRO_EGRESADAS
from programas.services.dispositivos import (
    CAP_EDITAR,
    CAP_VER,
    dispositivos_en_alcance,
    puede_operar_edificio,
    q_edificios_en_alcance,
)
from programas.services.edificio_operativo import _domicilio, estadias_del_edificio
from programas.services.estadias import CAP_ADMITIR, CAP_EGRESAR, CAP_VER_CIUDADANO
from programas.services.ingreso import maneja_plazas
from programas.services.ocupacion import (
    ESTADO_DISPONIBLE,
    ESTADO_FUERA_SERVICIO,
    ESTADO_OCUPADA,
    ESTADO_PRESTADA,
    ESTADO_RESERVADA,
    estado_de_plazas,
    ocupacion_de_plazas,
)
from programas.services.plazas import puede_configurar_plazas
from programas.services.sectores_plazas import (
    ACCION_EGRESAR,
    ACCION_FUERA_SERVICIO,
    ACCION_LIBERAR,
    ACCION_PRESTAR,
    ACCION_RESERVAR,
    ACCION_REUBICAR,
    ACCION_VOLVER,
    acciones_de_plaza,
    bloqueo_de_plaza,
    plazas_por_sector,
    se_puede_cambiar_plaza,
)

#: El estado de la plaza en la API: un código estable, no el texto que dibuja la web.
ESTADO_DE_LA_APP = {
    ESTADO_DISPONIBLE: "disponible",
    ESTADO_OCUPADA: "ocupada",
    ESTADO_RESERVADA: "reservada",
    ESTADO_PRESTADA: "prestada",
    ESTADO_FUERA_SERVICIO: "fuera_servicio",
}

#: Las acciones sobre una cama que la app ofrece. Quedan afuera ``ingresar``, ``ver_estadia``, ``ver_legajo`` y ``baja``.
ACCIONES_DE_LA_APP = (
    ACCION_EGRESAR,
    ACCION_REUBICAR,
    ACCION_LIBERAR,
    ACCION_RESERVAR,
    ACCION_PRESTAR,
    ACCION_FUERA_SERVICIO,
    ACCION_VOLVER,
)

ESTADO_ESTADIA_ACTIVA = "activa"
ESTADO_ESTADIA_EGRESADA = "egresada"


def _iso(momento):
    return timezone.localtime(momento).isoformat() if momento else None


def _nombre(apellido, nombre):
    """«Apellido, Nombre» sin dejar la coma suelta si falta una de las dos partes."""

    return f"{apellido}, {nombre}".strip(", ")


def _resumen(conteo):
    """Las cifras de un ``Conteo`` con las claves de la app."""

    return {
        "total": conteo.totales,
        "libres": conteo.disponibles,
        "ocupadas": conteo.ocupadas,
        "reservadas": conteo.reservadas_sin_prestamo,
        "prestadas": conteo.prestadas,
        "fuera_servicio": conteo.fuera_de_servicio,
    }


# ---------------------------------------------------------------------------------------
# Qué edificios ve el usuario
# ---------------------------------------------------------------------------------------


def _pares_en_alcance(user):
    """Los vínculos institución-edificio que ``user`` alcanza leyendo (``dispositivo.ver``), como filas del vínculo."""

    vinculo = Edificio.dispositivos.through
    return vinculo.objects.filter(
        dispositivo_id__in=dispositivos_en_alcance(user, CAP_VER).values("pk"),
    ).filter(q_edificios_en_alcance(user, CAP_VER, "dispositivo_id", "edificio_id"))


def ve_plazas(user):
    """¿``user`` ve al menos un edificio con ``dispositivo.ver``? Es la clave ``plazas`` del perfil de la app."""

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return _pares_en_alcance(user).exists()


def edificios_de_la_app(user):
    """Un ítem por par institución-edificio en alcance, por nombre de edificio, con las cifras de sus camas.

    Cuatro consultas fijas: los pares, y el censo de plazas de todas las instituciones juntas (3).
    """

    pares = list(
        _pares_en_alcance(user)
        .select_related("edificio", "dispositivo")
        .only(
            "dispositivo_id",
            "edificio_id",
            "dispositivo__nombre",
            "edificio__nombre",
            "edificio__calle",
            "edificio__numero",
            "edificio__piso_departamento",
            "edificio__localidad",
            "edificio__provincia",
        )
        .order_by("edificio__nombre", "edificio_id", "dispositivo__nombre", "dispositivo_id")
    )
    if not pares:
        return []
    censo = ocupacion_de_plazas(
        sorted({par.dispositivo_id for par in pares}),
        q_sectores=q_edificios_en_alcance(user, CAP_VER, "dispositivo_id", "edificio_id"),
    )
    return [
        {
            "dispositivo": {"id": par.dispositivo_id, "nombre": par.dispositivo.nombre},
            "edificio": {
                "id": par.edificio_id,
                "nombre": par.edificio.nombre,
                "direccion": ", ".join(_domicilio(par.edificio)),
            },
            "resumen": _resumen(censo.por_dispositivo[par.dispositivo_id].conteo_del_edificio(par.edificio_id)),
        }
        for par in pares
    ]


# ---------------------------------------------------------------------------------------
# El mapa de un edificio
# ---------------------------------------------------------------------------------------


def _reservas_abiertas(plaza_ids):
    """``{plaza_id: (id, desde, hasta, nombre, dni)}`` de las reservas sin resolver. Una consulta.

    Con el orden descendente por id queda la más vieja, la misma que ``estadias.reserva_abierta_de`` libera.
    """

    if not plaza_ids:
        return {}
    filas = (
        ReservaPlaza.objects.abiertas()
        .filter(plaza_id__in=plaza_ids)
        .order_by("-id")
        .values_list("plaza_id", "id", "desde", "hasta", "ciudadano__apellido", "ciudadano__nombre", "ciudadano__dni")
    )
    return {
        plaza_id: (pk, desde, hasta, _nombre(apellido, nombre), dni)
        for plaza_id, pk, desde, hasta, apellido, nombre, dni in filas
    }


def _estadias_de_las_camas(estadia_ids):
    """``{estadia_id: (fecha_ingreso, dni)}`` de las estadías de las camas ocupadas. Una consulta."""

    if not estadia_ids:
        return {}
    filas = Estadia.objects.filter(pk__in=estadia_ids).values_list("pk", "fecha_ingreso", "ciudadano__dni")
    return {pk: (ingreso, dni) for pk, ingreso, dni in filas}


def mapa_del_edificio(user, dispositivo, edificio):
    """El mapa de camas de ``edificio`` en ``dispositivo`` para ``user``: la respuesta de ``.../mapa/``.

    Quien llama ya resolvió el alcance (``edificio_de_la_institucion``: ajeno o fuera de alcance es 404). Acá se
    deciden las capacidades **sobre este edificio** y, con ellas, las acciones de cada cama
    (:func:`~programas.services.sectores_plazas.acciones_de_plaza`, filtradas a las de la app). Sin ``ciudadano.ver``
    la cama no dice quién la ocupa: ``persona`` es ``None``, igual que el mapa de la web.
    """

    momento = timezone.now()
    puede_admitir = puede_operar_edificio(user, dispositivo, edificio.pk, CAP_ADMITIR)
    puede_egresar = puede_operar_edificio(user, dispositivo, edificio.pk, CAP_EGRESAR)
    puede_editar = puede_configurar_plazas(
        user, dispositivo, puede_editar=puede_operar_edificio(user, dispositivo, edificio.pk, CAP_EDITAR)
    )
    ver_personas = puede(user, CAP_VER_CIUDADANO)

    ocupacion = ocupacion_de_plazas(dispositivo, momento, q_sectores=Q(edificio_id=edificio.pk)).de(dispositivo)
    por_sector = plazas_por_sector([sector.sector_id for sector in ocupacion.sectores])
    dibujadas = [plaza for sector in ocupacion.sectores for plaza in por_sector.get(sector.sector_id, ())]
    estados = estado_de_plazas(dibujadas, momento, puede_ver_personas=ver_personas)
    reservas = _reservas_abiertas([plaza.pk for plaza in dibujadas])
    estadias = _estadias_de_las_camas([e.estadia_id for e in estados.values() if e.estadia_id])

    sectores = []
    for sector in ocupacion.sectores:
        plazas = []
        for plaza in por_sector.get(sector.sector_id, ()):
            estado = estados[plaza.pk]
            reserva = reservas.get(plaza.pk)
            acciones = [
                accion
                for accion in acciones_de_plaza(
                    estado,
                    reserva is not None,
                    puede_admitir=puede_admitir,
                    puede_editar=puede_editar,
                    puede_buscar_personas=ver_personas,
                    puede_egresar=puede_egresar,
                    estado_dispositivo=dispositivo.estado,
                )
                if accion in ACCIONES_DE_LA_APP
            ]
            persona = desde = hasta = None
            if estado.estadia_id:
                ingreso, dni = estadias[estado.estadia_id]
                desde = _iso(ingreso)
                persona = {"nombre": estado.ocupante, "dni": dni} if ver_personas else None
            elif reserva is not None and estado.estado in (ESTADO_RESERVADA, ESTADO_PRESTADA):
                _pk, reservada_desde, reservada_hasta, nombre, dni = reserva
                desde, hasta = _iso(reservada_desde), _iso(reservada_hasta)
                persona = {"nombre": nombre, "dni": dni} if ver_personas else None
            plazas.append(
                {
                    "id": plaza.pk,
                    "codigo": plaza.codigo,
                    "tipo": plaza.tipo,
                    "estado": ESTADO_DE_LA_APP[estado.estado],
                    "persona": persona,
                    "estadia_id": estado.estadia_id,
                    "reserva_id": reserva[0] if reserva is not None else None,
                    "desde": desde,
                    "hasta": hasta,
                    "acciones": acciones,
                    "bloqueo": bloqueo_de_plaza(estado, ACCION_FUERA_SERVICIO)
                    if ACCION_FUERA_SERVICIO in acciones
                    else "",
                }
            )
        sectores.append(
            {
                "id": sector.sector_id,
                "nombre": sector.nombre,
                "tipo": sector.tipo,
                "resumen": _resumen(sector.conteo),
                "plazas": plazas,
            }
        )
    return {
        "dispositivo": {"id": dispositivo.pk, "nombre": dispositivo.nombre, "estado": dispositivo.estado},
        "edificio": {"id": edificio.pk, "nombre": edificio.nombre},
        "resumen": _resumen(ocupacion.conteo),
        "puede": {
            "egresar": puede_egresar,
            "admitir": puede_admitir,
            "editar": puede_editar,
            "ver_personas": ver_personas,
        },
        "sectores": sectores,
    }


# ---------------------------------------------------------------------------------------
# Las estadías de un edificio
# ---------------------------------------------------------------------------------------


def estadias_de_la_app(user, dispositivo, edificio, estado, sector, pagina):
    """La página de estadías del edificio (``?estado=activa|egresada&sector=<id>``) y sus filas para la app.

    Reusa :func:`~programas.services.edificio_operativo.estadias_del_edificio`, la misma de la solapa de la web:
    ``estado`` desconocido es «activa» y un sector ajeno se ignora. Devuelve ``(página, filas)``; las filas ya
    traen la marca de Emergencia (una consulta fija) y las acciones que el usuario puede ejercer sobre cada una.
    """

    datos = estadias_del_edificio(
        user,
        dispositivo,
        edificio,
        FILTRO_EGRESADAS if estado == ESTADO_ESTADIA_EGRESADA else FILTRO_ALOJADAS,
        sector,
        pagina,
    )
    pagina_de_estadias = datos["estadias"]
    ver_personas = datos["puede_ver_ciudadano"]
    con_plazas = maneja_plazas(dispositivo)
    marcas = marcas_de_emergencia([e.pk for e in pagina_de_estadias], con_familia=False)
    filas = []
    for estadia in pagina_de_estadias:
        activa = estadia.estado == Estadia.Estado.ACTIVA
        acciones = []
        if activa and datos["puede_egresar"]:
            acciones.append(ACCION_EGRESAR)
        if activa and datos["puede_cambiar"] and se_puede_cambiar_plaza(estadia, dispositivo, con_plazas=con_plazas):
            acciones.append(ACCION_REUBICAR)
        marca = marcas.get(estadia.pk)
        plaza = estadia.plaza
        filas.append(
            {
                "id": estadia.pk,
                "persona": (
                    {"nombre": estadia.ciudadano.apellido_nombre, "dni": estadia.ciudadano.dni}
                    if ver_personas
                    else None
                ),
                "sector": {"id": plaza.sector.pk, "nombre": plaza.sector.nombre} if plaza else None,
                "plaza": {"id": plaza.pk, "codigo": plaza.codigo} if plaza else None,
                "fecha_ingreso": _iso(estadia.fecha_ingreso),
                "fecha_egreso": _iso(estadia.fecha_egreso),
                "estado": ESTADO_ESTADIA_ACTIVA if activa else ESTADO_ESTADIA_EGRESADA,
                "origen": "emergencia" if marca else "dispositivo",
                "emergencia": {"caso_numero": marca["numero"]} if marca else None,
                "acciones": acciones,
            }
        )
    return pagina_de_estadias, filas
