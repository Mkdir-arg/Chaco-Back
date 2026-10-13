"""Datos y escritura del asistente de ingreso (MVP v2, etapa 2 · #690).

La vista del asistente solo orquesta pasos y sesión: lo que decide este módulo es qué
plazas se pueden ofrecer, cómo se encuentra a la persona y cómo se escribe el ingreso.

Dos reglas que no se pueden perder:

1. **Lo elegido en el paso 2 es una intención, no una reserva.** Entre el paso de la
   plaza y el de confirmar pasan minutos, y otro operador puede tomarla. Por eso el
   mapa se arma sin bloquear nada y la garantía está en
   :func:`programas.services.estadias.ingresar_persona`, que toma la fila de la plaza con
   ``select_for_update()`` dentro de ``transaction.atomic()``. :func:`confirmar_ingreso`
   envuelve esa llamada y deja que su ``ValidationError`` llegue a la vista, que vuelve
   al paso de la plaza en vez de reventar.
2. **La persona que no está en el legajo se da de alta recién al confirmar**, en la misma
   transacción que la estadía: un paso intermedio nunca escribe, y si el ingreso falla
   no queda un legajo huérfano.
"""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.dni import normalizar_dni
from legajos.forms import CiudadanoConfirmarForm
from legajos.models import Ciudadano
from legajos.services import CiudadanosService
from programas.models import Estadia, Plaza, ReservaPlaza, Sector
from programas.services.estadias import ingresar_persona

#: Mismo tope por sector que el mapa de «Sectores y plazas».
TOPE_PLAZAS_POR_SECTOR = 200

ESTADO_DISPONIBLE = "Disponible"
ESTADO_OCUPADA = "Ocupada"
ESTADO_RESERVADA = "Reservada"
ESTADO_PRESTADA = "Prestada"
ESTADO_FUERA_SERVICIO = "Fuera de serv."

#: Los estados del mapa con el tono con que se dibujan. La leyenda sale de acá, así no se
#: desincroniza de las plazas.
LEYENDA = [
    {"estado": ESTADO_DISPONIBLE, "tono": "success"},
    {"estado": ESTADO_OCUPADA, "tono": "info"},
    {"estado": ESTADO_RESERVADA, "tono": "warning"},
    {"estado": ESTADO_PRESTADA, "tono": "brand"},
    {"estado": ESTADO_FUERA_SERVICIO, "tono": "danger"},
]
_TONO = {item["estado"]: item["tono"] for item in LEYENDA}

#: Los campos de RENAPER que viajan por la sesión hasta la confirmación.
CAMPOS_RENAPER = ("dni", "nombre", "apellido", "fecha_nacimiento", "genero", "domicilio", "provincia")


def maneja_plazas(dispositivo):
    """¿Este dispositivo asigna plaza al ingresar?

    Lo dice el tipo: o la exige (`plaza_obligatoria_al_ingresar`) o declara qué tipos de
    plaza admite (`tipos_plaza_admitidos`). Un tipo sin ninguna de las dos no maneja
    plazas identificables y el asistente se acorta un paso.
    """

    tipo = dispositivo.tipo
    return bool(tipo.plaza_obligatoria_al_ingresar or tipo.tipos_de_plaza)


def buscar_ciudadano_por_dni(dni):
    """El legajo de esa persona, escrito el DNI como esté en la base, o `None`.

    El DNI exacto primero; si no, las fichas cargadas con separadores, que la regla de
    `CiudadanosService.existe_con_dni` también cuenta como la misma persona.
    """

    dni = normalizar_dni(dni)
    if not dni:
        return None
    ciudadano = Ciudadano.objects.filter(dni=dni).first()
    if ciudadano is not None:
        return ciudadano
    for candidato in Ciudadano.objects.exclude(dni=dni).filter(dni__regex=r"[^0-9]"):
        if normalizar_dni(candidato.dni) == dni:
            return candidato
    return None


def consultar_registro_de_personas(dni, sexo):
    """Pide los datos a RENAPER por el servicio que ya usa Legajos.

    Devuelve `(datos, error)`: `datos` es el recorte que viaja por la sesión, y `error` el
    texto para la persona que opera. Nunca los dos.
    """

    resultado = CiudadanosService.consultar_renaper(dni, sexo)
    if resultado.get("fallecido"):
        return None, "La persona consultada figura como fallecida en el Registro de Personas."
    if not resultado.get("success"):
        return (
            None,
            f"No se encontraron datos en el Registro de Personas: {resultado.get('error', 'error desconocido')}.",
        )
    datos = {campo: resultado["data"].get(campo) for campo in CAMPOS_RENAPER}
    datos["dni"] = normalizar_dni(datos["dni"] or dni)
    return datos, ""


def plazas_para_ingresar(dispositivo):
    """El mapa del paso 2: sectores activos con cada plaza y su estado, sin bloquear nada.

    Cuatro consultas fijas (sectores, plazas, ocupadas, reservadas). Se ofrecen solo las
    plazas de un tipo que el dispositivo admite. Devuelve
    `([{"sector", "plazas", "total", "disponibles"}], {pk de plaza elegible})`.
    """

    tipo = dispositivo.tipo
    ahora = timezone.now()
    sectores = list(Sector.objects.filter(dispositivo=dispositivo, activo=True).order_by("nombre"))
    plazas = list(
        Plaza.objects.filter(sector__in=sectores).only(
            "id", "sector_id", "codigo", "tipo", "estado", "motivo_fuera_servicio"
        )
    )
    plazas = [plaza for plaza in plazas if tipo.admite_tipo_de_plaza(plaza.tipo)]
    ids = [plaza.pk for plaza in plazas]
    ocupadas = set(Estadia.objects.activas().filter(plaza_id__in=ids).values_list("plaza_id", flat=True))
    reservas = {
        reserva.plaza_id: reserva.tipo for reserva in ReservaPlaza.objects.vigentes(ahora).filter(plaza_id__in=ids)
    }

    por_sector = {sector.pk: [] for sector in sectores}
    for plaza in sorted(plazas, key=lambda p: p.codigo):
        if plaza.estado == Plaza.Estado.FUERA_SERVICIO:
            estado, detalle = ESTADO_FUERA_SERVICIO, plaza.motivo_fuera_servicio
        elif plaza.pk in ocupadas:
            estado, detalle = ESTADO_OCUPADA, ""
        elif plaza.pk in reservas:
            prestada = reservas[plaza.pk] == ReservaPlaza.Tipo.PRESTAMO
            estado, detalle = (ESTADO_PRESTADA if prestada else ESTADO_RESERVADA), ""
        else:
            estado, detalle = ESTADO_DISPONIBLE, ""
        por_sector[plaza.sector_id].append(
            {"pk": plaza.pk, "codigo": plaza.codigo, "estado": estado, "tono": _TONO[estado], "detalle": detalle}
        )

    armados, elegibles = [], set()
    for sector in sectores:
        del_sector = por_sector[sector.pk]
        libres = [plaza for plaza in del_sector if plaza["estado"] == ESTADO_DISPONIBLE]
        elegibles.update(plaza["pk"] for plaza in libres)
        armados.append(
            {
                "sector": sector,
                "plazas": del_sector[:TOPE_PLAZAS_POR_SECTOR],
                "total": len(del_sector),
                "disponibles": len(libres),
            }
        )
    return armados, elegibles


def confirmar_ingreso(*, dispositivo, usuario, ciudadano_id, datos_renaper, plaza_id, fecha_ingreso=None):
    """El paso final: alta de la persona si hace falta y estadía, en una sola transacción.

    La plaza se **revalida y se toma** dentro de `ingresar_persona` (bloqueando su fila).
    Si ya no está disponible, o la persona ya está alojada, lanza `ValidationError` y la
    transacción entera —incluida el alta del legajo— se deshace.
    """

    with transaction.atomic():
        if ciudadano_id:
            ciudadano = Ciudadano.objects.get(pk=ciudadano_id)
        else:
            ciudadano = _alta_desde_registro(datos_renaper)
        plaza = Plaza.objects.get(pk=plaza_id) if plaza_id else None
        return ingresar_persona(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            usuario=usuario,
            plaza=plaza,
            fecha_ingreso=fecha_ingreso,
        )


def _alta_desde_registro(datos):
    """Crea el legajo con lo que respondió el Registro de Personas, como lo hace Legajos."""

    existente = buscar_ciudadano_por_dni(datos["dni"])
    if existente is not None:
        return existente  # lo dio de alta otro mientras tanto: es la misma persona
    form = CiudadanoConfirmarForm(data=datos, initial=datos)
    if not form.is_valid():
        raise ValidationError("Los datos del Registro de Personas no alcanzan para dar de alta a la persona.")
    form.instance.estado_renaper = Ciudadano.EstadoRenaper.REGISTRADO
    try:
        with transaction.atomic():
            ciudadano = form.save()
    except IntegrityError:
        existente = buscar_ciudadano_por_dni(datos["dni"])
        if existente is None:
            raise
        return existente
    CiudadanosService.invalidate_ciudadanos_cache()
    return ciudadano
