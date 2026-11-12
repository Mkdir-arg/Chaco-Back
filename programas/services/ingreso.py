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

from typing import NamedTuple

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.dni import normalizar_dni
from legajos.forms import CiudadanoConfirmarForm, CiudadanoManualForm
from legajos.models import Ciudadano
from legajos.services import CiudadanosService
from programas.models import Plaza, ReservaPlaza, Sector
from programas.services.dispositivos import dispositivos_en_alcance
from programas.services.estadias import (
    CAP_ADMITIR,
    ingresar_persona,
    liberar_reserva,
    reserva_propia_vigente,
)
from programas.services.nombre_plaza import clave_natural
from programas.services.ocupacion import ESTADO_PRESTADA, ESTADO_RESERVADA, estado_de_plazas

#: Los estados en los que una plaza puede ser la que la persona tiene guardada.
ESTADOS_GUARDADOS = (ESTADO_RESERVADA, ESTADO_PRESTADA)

#: Mismo tope por sector que el mapa de «Sectores y plazas».
TOPE_PLAZAS_POR_SECTOR = 200

#: Los campos de RENAPER que viajan por la sesión hasta la confirmación.
CAMPOS_RENAPER = ("dni", "nombre", "apellido", "fecha_nacimiento", "genero", "domicilio", "provincia")


def maneja_plazas(dispositivo):
    """¿Este dispositivo asigna plaza al ingresar?

    Lo dice el tipo: o la exige (`plaza_obligatoria_al_ingresar`) o declara qué tipos de
    plaza admite (`tipos_plaza_admitidos`). Un tipo sin ninguna de las dos no maneja
    plazas identificables y el asistente se acorta un paso.
    """

    return dispositivo.tipo.maneja_plazas


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
    candidatos = Ciudadano.objects.exclude(dni=dni).filter(dni__regex=r"[^0-9]").values_list("id", "dni")
    for candidato_id, candidato_dni in candidatos:
        if normalizar_dni(candidato_dni) == dni:
            return Ciudadano.objects.get(pk=candidato_id)
    return None


class RespuestaRegistro(NamedTuple):
    """Lo que respondió el Registro de Personas, con el motivo de la falla por separado."""

    datos: dict | None
    motivo: str
    fallecido: bool


def buscar_en_registro_de_personas(dni, sexo):
    """Pide los datos a RENAPER y devuelve `RespuestaRegistro(datos, motivo, fallecido)`.

    `motivo` es el texto de la falla, sin prefijo ni punto final (vacío si hubo datos);
    `fallecido` distingue a la persona que figura fallecida, que nunca se aloja.
    """

    resultado = CiudadanosService.consultar_renaper(dni, sexo)
    if resultado.get("fallecido"):
        return RespuestaRegistro(None, "La persona consultada figura como fallecida en el Registro de Personas.", True)
    if not resultado.get("success"):
        motivo = str(resultado.get("error") or "error desconocido").strip().rstrip(".")
        return RespuestaRegistro(None, motivo, False)
    datos = {campo: resultado["data"].get(campo) for campo in CAMPOS_RENAPER}
    datos["dni"] = normalizar_dni(datos["dni"] or dni)
    return RespuestaRegistro(datos, "", False)


#: Qué dice la celda de la plaza que la persona tiene guardada: es suya, así que se puede elegir.
DETALLE_PLAZA_PROPIA = "Guardada para esta persona"


def plaza_reservada_de(ciudadano_id, dispositivo):
    """El id de la plaza que la persona tiene reservada o prestada en el dispositivo, o `None`.

    Esa plaza el mapa la cuenta como tomada, pero para **esta** persona es la suya: el ingreso
    la consume (`confirmar_ingreso`). Sin bloquear nada: es una lectura para dibujar el paso.
    """

    if not ciudadano_id:
        return None
    reserva = reserva_propia_vigente(ciudadano_id, dispositivo)
    return reserva.plaza_id if reserva is not None else None


def plazas_para_ingresar(dispositivo, *, puede_ver_personas=False, plaza_propia_id=None):
    """El mapa del paso 2: sectores activos con cada plaza y su estado, sin bloquear nada.

    El estado de cada plaza lo deriva `ocupacion.estado_de_plazas`, el mismo que usa
    «Sectores y plazas»: acá no se decide qué es «ocupada». Se ofrecen solo las plazas de
    un tipo que el dispositivo admite. Devuelve
    `([{"sector", "plazas", "total", "disponibles"}], {pk de plaza elegible})`.

    `plaza_propia_id` es la plaza que la persona que ingresa tiene reservada o prestada
    (:func:`plaza_reservada_de`): es elegible **solo para ella**, y no suma a los
    `disponibles` del sector, que cuentan lo que le queda a cualquier otra persona.
    """

    tipo = dispositivo.tipo
    sectores = list(Sector.objects.filter(dispositivo=dispositivo, activo=True).order_by("nombre"))
    plazas = Plaza.objects.filter(sector__in=sectores).only(
        "id", "sector_id", "codigo", "tipo", "estado", "motivo_fuera_servicio"
    )
    plazas = [plaza for plaza in plazas if tipo.admite_tipo_de_plaza(plaza.tipo)]
    estados = estado_de_plazas(plazas, puede_ver_personas=puede_ver_personas)

    por_sector = {sector.pk: [] for sector in sectores}
    for plaza in sorted(plazas, key=lambda p: clave_natural(p.codigo)):
        derivado = estados[plaza.pk]
        propia = plaza.pk == plaza_propia_id and not derivado.disponible and derivado.estado in ESTADOS_GUARDADOS
        por_sector[plaza.sector_id].append(
            {
                "pk": plaza.pk,
                "codigo": plaza.codigo,
                "estado": derivado.estado,
                "tono": derivado.tono,
                "detalle": DETALLE_PLAZA_PROPIA if propia else derivado.detalle,
                "detalle_completo": DETALLE_PLAZA_PROPIA if propia else derivado.detalle_completo,
                "disponible": derivado.disponible,
                "propia": propia,
            }
        )

    armados, elegibles = [], set()
    for sector in sectores:
        del_sector = por_sector[sector.pk]
        libres = [plaza for plaza in del_sector if plaza["disponible"]]
        elegibles.update(plaza["pk"] for plaza in libres)
        elegibles.update(plaza["pk"] for plaza in del_sector if plaza["propia"])
        armados.append(
            {
                "sector": sector,
                "plazas": del_sector[:TOPE_PLAZAS_POR_SECTOR],
                "total": len(del_sector),
                "disponibles": len(libres),
            }
        )
    return armados, elegibles


def confirmar_ingreso(
    *, dispositivo, usuario, ciudadano_id, datos_renaper, plaza_id, fecha_ingreso=None, datos_manual=None
):
    """El paso final: alta de la persona si hace falta y estadía, en una sola transacción.

    La plaza se **revalida y se toma** dentro de `ingresar_persona` (bloqueando su fila).
    Si ya no está disponible, o la persona ya está alojada, lanza `ValidationError` y la
    transacción entera —incluida el alta del legajo— se deshace. Si el legajo o la plaza
    se borraron entre pasos, deja pasar `Ciudadano.DoesNotExist` o `Plaza.DoesNotExist`:
    la vista decide a qué paso se vuelve.

    Si no hay legajo, la persona sale de `datos_renaper` (lo que respondió el Registro de
    Personas) o de `datos_manual` (el alta mínima, cuando el Registro no la encontró).
    """

    with transaction.atomic():
        if ciudadano_id:
            ciudadano = Ciudadano.objects.get(pk=ciudadano_id)
        elif datos_manual:
            ciudadano = _alta_manual(datos_manual)
        else:
            ciudadano = _alta_desde_registro(datos_renaper)
        plaza = Plaza.objects.get(pk=plaza_id) if plaza_id else None
        # Lo que la persona tenía guardado: si es la plaza donde entra, el ingreso la consume;
        # el resto se cierra, **en este dispositivo y en cualquier otro** (decisión del PM,
        # 02/11/2026), porque una persona que ya está adentro no puede seguir bloqueando
        # plazas. Todo en esta transacción y, para no cruzar candados, en el orden
        # plaza → reserva → persona: primero se toman de una vez, ordenadas por pk, todas las
        # plazas involucradas (las de las reservas a cerrar y la del ingreso), después se
        # cierran las reservas y recién entonces se toma la persona.
        propia = reserva_propia_vigente(ciudadano.pk, dispositivo)
        if propia is not None and (plaza is None or propia.plaza_id != plaza.pk):
            propia = None
        a_liberar = [
            reserva for reserva in _reservas_abiertas_de(ciudadano.pk) if propia is None or reserva.pk != propia.pk
        ]
        plazas_a_bloquear = {reserva.plaza_id for reserva in a_liberar}
        if plaza is not None:
            plazas_a_bloquear.add(plaza.pk)
        if plazas_a_bloquear:
            # Solo el candado: `liberar_reserva` e `ingresar_persona` vuelven a tomar la plaza y a validarla.
            list(
                Plaza.objects.select_for_update()
                .filter(pk__in=plazas_a_bloquear)
                .order_by("pk")
                .values_list("pk", flat=True)
            )
        for reserva in a_liberar:
            try:
                liberar_reserva(
                    reserva=reserva,
                    usuario=usuario,
                    motivo=MOTIVO_RESERVA_CERRADA_POR_INGRESO,
                    verificar_alcance=False,
                )
            except ValidationError:
                continue  # ya la resolvió otro: lo que importa es que no quede bloqueando
        _bloquear_persona(ciudadano)
        # Con la persona bloqueada nadie le puede guardar otra plaza: si apareció una entre la
        # lectura y el bloqueo, quedaría bloqueando una plaza de alguien que ya está adentro.
        if any(propia is None or reserva.pk != propia.pk for reserva in _reservas_abiertas_de(ciudadano.pk)):
            raise ValidationError(RESERVA_NUEVA_DURANTE_EL_INGRESO)
        return ingresar_persona(
            ciudadano=ciudadano,
            dispositivo=dispositivo,
            usuario=usuario,
            plaza=plaza,
            fecha_ingreso=fecha_ingreso,
            reserva=propia,
        )


#: Por qué se cierra la reserva o el préstamo que la persona tenía cuando ingresa en otra plaza o sin plaza.
MOTIVO_RESERVA_CERRADA_POR_INGRESO = "La persona ingresó a un dispositivo."

RESERVA_NUEVA_DURANTE_EL_INGRESO = (
    "Mientras se registraba el ingreso se le guardó una plaza a esta persona; volvé a confirmar."
)


def _reservas_abiertas_de(ciudadano_id):
    """Las reservas sin resolver de la persona en **cualquier** dispositivo, vencidas o no, por plaza.

    **Sin las reservas de derivación** (`derivacion__isnull=True`): las camas guardadas para la
    familia de un caso de Emergencia llevan al responsable en `ciudadano`, pero son de la familia.
    Si entraran acá, el ingreso del responsable por este asistente liberaría de un golpe las camas
    de todos los demás. La decisión del PM del 02/11/2026 (cerrar todas las reservas de quien
    ingresa) vale igual que antes para toda otra reserva. Ver «Reservas de derivación» en
    `programas.services.estadias`.
    """

    return list(
        ReservaPlaza.objects.abiertas()
        .filter(ciudadano_id=ciudadano_id, derivacion__isnull=True)
        .select_related("plaza__sector__dispositivo")
        .order_by("plaza_id")
    )


def reservas_en_otros_dispositivos(ciudadano_id, dispositivo, usuario):
    """Las reservas o préstamos abiertos de la persona en **otros** dispositivos, que el ingreso va a liberar.

    Solo lectura, para avisarlo en el paso «Confirmar» (Cambio 412). Devuelve
    ``(nombres, fuera_de_alcance)``: los nombres de los dispositivos que ``usuario`` puede ver, sin repetir y
    por orden alfabético, y cuántos más quedan fuera de su alcance (de esos solo se sabe que existen).
    """

    if not ciudadano_id:
        return [], 0
    destinos = {
        reserva.plaza.sector.dispositivo
        for reserva in _reservas_abiertas_de(ciudadano_id)
        if reserva.plaza.sector.dispositivo_id != dispositivo.pk
    }
    if not destinos:
        return [], 0
    visibles = set(
        dispositivos_en_alcance(usuario, CAP_ADMITIR)
        .filter(pk__in=[d.pk for d in destinos])
        .values_list("pk", flat=True)
    )
    nombres = sorted({d.nombre for d in destinos if d.pk in visibles})
    return nombres, sum(1 for d in destinos if d.pk not in visibles)


def _bloquear_persona(ciudadano):
    """La fila de la persona, con `FOR UPDATE`: serializa lo que se le guarda o se le aloja."""

    Ciudadano.objects.select_for_update().only("pk").get(pk=ciudadano.pk)


def _alta_desde_registro(datos):
    """Crea el legajo con lo que respondió el Registro de Personas, como lo hace Legajos."""

    return _crear_legajo(
        datos["dni"],
        CiudadanoConfirmarForm(data=datos, initial=datos),
        Ciudadano.EstadoRenaper.REGISTRADO,
        "Los datos del Registro de Personas no alcanzan para dar de alta a la persona.",
    )


def _alta_manual(datos):
    """Crea el legajo con el alta mínima, como la carga manual de Legajos.

    `estado_renaper` queda vacío: los datos no se validaron contra el Registro de Personas.
    """

    return _crear_legajo(
        datos["dni"],
        CiudadanoManualForm(data=datos),
        "",
        "Los datos cargados no alcanzan para dar de alta a la persona.",
    )


def alta_minima_de_persona(datos):
    """El alta mínima del legajo (DNI, nombre y apellido) para quien no es el asistente de ingreso.

    Es :func:`_alta_manual` con nombre público: la usa Emergencia para dar de alta al
    responsable de una familia (RN-1.5) con la misma regla, el mismo formulario y la misma
    tolerancia a la carrera por el DNI. Si la persona ya existe, devuelve su legajo. Corre
    dentro de la transacción de quien la llama.
    """

    return _alta_manual(datos)


def _crear_legajo(dni, form, estado_renaper, mensaje_invalido):
    """El alta del legajo dentro de la transacción del ingreso, tolerante a la carrera por el DNI."""

    existente = buscar_ciudadano_por_dni(dni)
    if existente is not None:
        return existente  # lo dio de alta otro mientras tanto: es la misma persona
    if not form.is_valid():
        raise ValidationError(mensaje_invalido)
    if estado_renaper:
        form.instance.estado_renaper = estado_renaper
    try:
        with transaction.atomic():
            ciudadano = form.save()
    except IntegrityError:
        existente = buscar_ciudadano_por_dni(dni)
        if existente is None:
            raise
        return existente
    # Después del commit y no ahora: adentro de la transacción, otra petición podría volver
    # a llenar la caché con el listado viejo antes de que el alta se vea.
    transaction.on_commit(CiudadanosService.invalidate_ciudadanos_cache)
    return ciudadano
