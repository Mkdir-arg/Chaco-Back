"""Etapa 3 de Emergencia, paso 2: confirmar a cada persona con su ficha y su cama (M2-3, M2-4).

``confirmar_integrante``, ``completar_ficha`` y ``agregar_integrante``. Se importan desde
``programas.services.emergencia_alojar``, que tiene el contrato de la etapa (alcance, orden
de candados, traza). La ficha (Formulario 2) es de ``emergencia_ficha``.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.dni import dni_valido, normalizar_dni
from core.edad import fecha_o_none
from legajos.models import Ciudadano
from legajos.models.contactos import TipoVinculo, VinculoFamiliar
from programas.models import (
    Estadia,
    IntegranteGrupo,
    Plaza,
    ReservaPlaza,
)
from programas.selectors.emergencia_alojar import camas_libres
from programas.services.emergencia import EstadoCambio
from programas.services.emergencia_alta import _como_uuid
from programas.services.emergencia_comun import _trazar
from programas.services.emergencia_ficha import (
    SECCION_DATOS,
    SECCION_PARENTESCO,
    SECCIONES_OPCIONALES,
    SIN_NUMERO_DE_DOCUMENTO,
    Parentesco,
    _claves_de_envio,
    ficha_esta_completa,
    ficha_minima_valida,
    normalizar_ficha,
)
from programas.services.emergencia_ingreso_comun import (
    Accion,
    Estado,
    _abrir_ingreso,
    _confirmadas,
    _dia_y_mes,
    _filas_de,
)
from programas.services.estadias import AlojamientoEnLaRed, ingresar_persona, liberar_reserva
from programas.services.ingreso import (
    MOTIVO_RESERVA_CERRADA_POR_INGRESO,
    RESERVA_NUEVA_DURANTE_EL_INGRESO,
    _bloquear_persona,
    _reservas_abiertas_de,
    alta_minima_de_persona,
    buscar_ciudadano_por_dni,
)
from programas.services.nombre_plaza import plaza_con_sector
from programas.services.reservas_derivacion import consumir_reserva_de_derivacion

SIN_CAMA_LIBRE = "Sin cama libre · liberá una o cerrá con diferencia."

ELEGI_UNA_CAMA = "Elegí una cama del mapa de este dispositivo."

MOTIVO_RESERVA_SOBRANTE = "Emergencia: la persona ingresó en otra cama."


class PersonaYaAlojada(ValidationError):
    """La persona que se quiso confirmar ya tiene una estadía abierta en la red (HU-3.3).

    Es un ``ValidationError`` (400) sobre el campo ``dni``. El mensaje nombra el otro
    dispositivo **solo si quien confirma lo puede ver** (``verificacion.dentro_del_alcance``):
    si no, dice que está alojada en otro dispositivo y a quién pedirle el egreso (RU-9).
    ``verificacion`` es la ``VerificacionAlojamiento`` de ``estadias``.
    """

    def __init__(self, ciudadano, verificacion):
        self.ciudadano = ciudadano
        self.verificacion = verificacion
        nombre = ciudadano.nombre_completo
        if verificacion.dentro_del_alcance:
            cuando = f" desde el {_dia_y_mes(verificacion.desde)}" if verificacion.desde else ""
            mensaje = (
                f"{nombre} figura alojado en {verificacion.dispositivo}{cuando}. "
                f"Pedí que lo egresen de {verificacion.dispositivo} o cerrá el ingreso con diferencia."
            )
        else:
            mensaje = (
                f"{nombre} figura alojado en otro dispositivo de la red. Pedí a la coordinación del "
                f"Programa Dispositivos que registre el egreso (clave {verificacion.clave}) "
                "o cerrá el ingreso con diferencia."
            )
        super().__init__({"dni": mensaje})


# ---------------------------------------------------------------------------
# Piezas internas
# ---------------------------------------------------------------------------

#: Parentesco de la ficha → tipo de vínculo del legajo, visto **desde el responsable**.
#: Quien figura como jefe/a de hogar y no es el responsable del caso queda como «Otro».
VINCULO_DE_PARENTESCO = {
    Parentesco.CONYUGE: TipoVinculo.PAREJA,
    Parentesco.HIJO: TipoVinculo.HIJO,
    Parentesco.OTRO: TipoVinculo.OTRO,
    Parentesco.JEFE: TipoVinculo.OTRO,
}


def _con_lo_del_legajo(ficha, ciudadano):
    """La ficha completada con lo que el legajo ya sabe: nombre, apellido, sexo y nacimiento.

    Solo llena lo que la guardia **no** cargó. Con la persona en el legajo, el DNI alcanza
    para identificarla: el mínimo no obliga a retipear lo que ya está.
    """

    if ciudadano is None:
        return ficha
    datos = ficha[SECCION_DATOS]
    del_legajo = {
        "nombre": ciudadano.nombre,
        "apellido": ciudadano.apellido,
        "sexo": ciudadano.genero,
        "fecha_nacimiento": ciudadano.fecha_nacimiento.isoformat() if ciudadano.fecha_nacimiento else "",
    }
    for campo, valor in del_legajo.items():
        if valor and not datos.get(campo):
            datos[campo] = valor
    return ficha


def _dar_de_alta(ficha):
    """El alta mínima del legajo, la misma del asistente de ingreso (``ingreso.alta_minima_de_persona``).

    «Perdió el documento pero sabe el número» queda como ``dni_fisico = NO_TIENE`` **solo en
    quien se da de alta acá** (hallazgo H5): a quien ya tenía legajo no se le toca.
    """

    datos = ficha[SECCION_DATOS]
    try:
        ciudadano = alta_minima_de_persona(
            {
                "dni": datos["dni"],
                "nombre": datos["nombre"],
                "apellido": datos["apellido"],
                "fecha_nacimiento": datos["fecha_nacimiento"],
                "genero": datos["sexo"],
                "telefono": datos.get("telefono", ""),
            }
        )
    except ValidationError as error:
        raise ValidationError({"nombre": error.messages}) from error
    if datos.get("documento_extraviado") and not ciudadano.dni_fisico:
        ciudadano.dni_fisico = Ciudadano.DniFisico.NO_TIENE
        ciudadano.save(update_fields=["dni_fisico", "modificado"])
    return ciudadano


def _completar_legajo(ciudadano, ficha):
    """Llena en el legajo el sexo, el nacimiento y el teléfono **que estaban vacíos**. Nunca pisa.

    El responsable se dio de alta en la etapa 1 sin sexo («lo completa la ficha de la etapa
    3»): acá se completa. Se llama con la persona ya bloqueada por el ingreso.
    """

    datos = ficha[SECCION_DATOS]
    campos = []
    if not ciudadano.genero and datos.get("sexo"):
        ciudadano.genero = datos["sexo"]
        campos.append("genero")
    if ciudadano.fecha_nacimiento is None and datos.get("fecha_nacimiento"):
        ciudadano.fecha_nacimiento = fecha_o_none(datos["fecha_nacimiento"])
        campos.append("fecha_nacimiento")
    if not ciudadano.telefono and datos.get("telefono"):
        ciudadano.telefono = datos["telefono"]
        campos.append("telefono")
    if campos:
        ciudadano.save(update_fields=[*campos, "modificado"])


def _cama_del_dispositivo(plaza, dispositivo, derivacion):
    """La cama elegida, **de este dispositivo**, con su sector. Sin candado.

    El mismo error para la que no existe y para la de otra institución, como
    ``estadias._bloquear_plaza``. Y los dos rechazos que se pueden dar sin esperar a nadie:
    fuera de servicio (03 §10) y ocupada. El de «ocupada» es además lo que impide el ciclo
    con un egreso en curso (ver el docstring del módulo): se mira **antes** de pedir el
    candado de la plaza.
    """

    pk = plaza.pk if isinstance(plaza, Plaza) else plaza
    cama = None
    if pk not in (None, ""):
        try:
            cama = (
                Plaza.objects.filter(pk=int(pk), sector__dispositivo_id=dispositivo.pk, tipo=Plaza.Tipo.CAMA)
                .select_related("sector")
                .first()
            )
        except (TypeError, ValueError):
            cama = None
    if cama is None:
        if pk in (None, "") and not _hay_cama_para_elegir(dispositivo, derivacion):
            # HU-3.5: la fila existe, pero no hay dónde alojar a la persona.
            raise ValidationError({"plaza": SIN_CAMA_LIBRE})
        raise ValidationError({"plaza": ELEGI_UNA_CAMA})
    nombre = plaza_con_sector(cama, cama.sector.nombre)
    if cama.estado == Plaza.Estado.FUERA_SERVICIO:
        raise ValidationError({"plaza": f"La cama {nombre} está fuera de servicio · elegí otra."})
    if not cama.sector.activo:
        raise ValidationError({"plaza": f"El sector de la cama {nombre} está dado de baja · elegí otra."})
    if Estadia.objects.activas().filter(plaza_id=cama.pk).exists():
        raise ValidationError({"plaza": f"La cama {nombre} ya está ocupada · elegí otra."})
    return cama


def _hay_cama_para_elegir(dispositivo, derivacion):
    """¿Queda alguna cama guardada para la familia, o alguna libre?"""

    return ReservaPlaza.objects.abiertas().filter(derivacion_id=derivacion.pk).exists() or bool(
        camas_libres(dispositivo)
    )


def _vincular_con_el_responsable(grupo, ciudadano, parentesco, caso):
    """El ``VinculoFamiliar`` entre el responsable y quien se confirma, según el parentesco (RN-3.7).

    Visto desde el responsable («su hijo/a es…»), marcado como conviviente. Si el vínculo ya
    existía en el legajo no se duplica ni se modifica.
    """

    VinculoFamiliar.objects.get_or_create(
        ciudadano_principal_id=grupo.responsable_id,
        ciudadano_vinculado=ciudadano,
        tipo_vinculo=VINCULO_DE_PARENTESCO[parentesco],
        defaults={"convive": True, "observaciones": f"Declarado al alojar · Emergencia caso N.° {caso.numero}"},
    )


def _ya_confirmada_en(filas, integrante, dni):
    """Si otra fila de la familia ya tiene a esa persona, el error que lo dice (03 §10)."""

    for otra in filas:
        if otra.pk == integrante.pk or not otra.ciudadano_id or normalizar_dni(otra.ciudadano.dni) != dni:
            continue
        nombre = otra.ciudadano.nombre_completo
        if otra.estadia_id and otra.estadia.plaza_id and otra.egresado_en is None:
            cama = plaza_con_sector(otra.estadia.plaza, otra.estadia.plaza.sector.nombre)
            return ValidationError({"dni": f"Ya confirmaste a {nombre} en la cama {cama}."})
        return ValidationError({"dni": f"Ya confirmaste a {nombre} en esta familia (persona {otra.orden})."})
    return None


def _error_de_cama(error, cama):
    """El rechazo de ``estadias`` sobre la plaza, dicho con el nombre de la cama y qué hacer."""

    detalle = getattr(error, "error_dict", {})
    if not ({"plaza", "reserva"} & set(detalle)):
        return error
    nombre = plaza_con_sector(cama, cama.sector.nombre)
    mensajes = " ".join(error.messages)
    return ValidationError({"plaza": f"Cama {nombre}: {mensajes} Recargá el mapa y elegí otra."})


def _ingresar_en_cama_libre(*, ciudadano, cama, propia, derivacion, por_confirmar_despues, usuario):
    """El ingreso en una cama que no es de la familia. Devuelve ``(estadia, reserva_liberada)``.

    Dos cosas se cierran antes de ingresar, en esta transacción:

    * la **reserva sobrante** de la familia: la derivación nunca retiene más camas que personas
      faltan confirmar, así que si quedarían de más se libera la de la plaza con id más alto;
    * las **reservas comunes** de la persona, en cualquier dispositivo (D2 del Cambio 409), salvo
      ``propia`` —la suya en esta misma cama—, que el ingreso consume.

    Candados: todas las plazas de una vez y por pk (la cama, la sobrante y las de las comunes),
    después las reservas, y la persona al final; con ella bloqueada se vuelve a mirar que no le
    hayan guardado otra plaza en el medio (``RESERVA_NUEVA_DURANTE_EL_INGRESO``).
    """

    comunes = [comun for comun in _reservas_abiertas_de(ciudadano.pk) if propia is None or comun.pk != propia.pk]
    vigentes = list(ReservaPlaza.objects.abiertas().filter(derivacion_id=derivacion.pk).order_by("plaza_id"))
    sobrante = vigentes[-1] if len(vigentes) > por_confirmar_despues else None
    # La sobrante es de este dispositivo (el alcance ya se exigió); las comunes pueden ser de
    # otro donde quien confirma no opera: no es una decisión suya, es que la persona ya entró.
    a_liberar = ([(sobrante, MOTIVO_RESERVA_SOBRANTE, True)] if sobrante is not None else []) + [
        (comun, MOTIVO_RESERVA_CERRADA_POR_INGRESO, False) for comun in comunes
    ]
    # Solo el candado: `liberar_reserva` e `ingresar_persona` vuelven a tomar cada plaza. Va
    # siempre, aunque no haya nada que liberar: la cama tiene que quedar tomada antes que la
    # persona, como en `ingresar_persona` y `reservar_plaza` (plaza → persona).
    list(
        Plaza.objects.select_for_update()
        .filter(pk__in={cama.pk} | {reserva.plaza_id for reserva, _motivo, _alcance in a_liberar})
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    reserva_liberada = False
    for reserva, motivo, verificar_alcance in a_liberar:
        try:
            liberar_reserva(reserva=reserva, usuario=usuario, motivo=motivo, verificar_alcance=verificar_alcance)
        except ValidationError:
            continue  # ya la resolvió otro (la liberaron desde el mapa): no retiene nada
        reserva_liberada = reserva_liberada or reserva is sobrante
    _bloquear_persona(ciudadano)
    if any(propia is None or otra.pk != propia.pk for otra in _reservas_abiertas_de(ciudadano.pk)):
        raise ValidationError(RESERVA_NUEVA_DURANTE_EL_INGRESO)
    estadia = ingresar_persona(
        ciudadano=ciudadano, dispositivo=derivacion.dispositivo, usuario=usuario, plaza=cama, reserva=propia
    )
    return estadia, reserva_liberada


# ---------------------------------------------------------------------------
# Confirmar, completar y agregar
# ---------------------------------------------------------------------------


@transaction.atomic
def confirmar_integrante(*, caso, orden, usuario, ficha, plaza, uuid_cliente=None):
    """Confirma a la persona ``orden`` de la familia con su ficha mínima y su cama (HU-3.3, RN-3.5 a 3.7).

    **Una sola transacción**: si cualquier paso falla —en particular el ingreso— no queda ni
    el legajo recién dado de alta, ni el vínculo familiar, ni la fila confirmada.

    1. Bloquea caso → derivación; el caso tiene que estar en ``INGRESO_EN_CURSO``.
    2. Valida el **mínimo** (:func:`ficha_minima_valida`), completando antes con lo que el
       legajo sabe si la persona ya existe. Sin número de DNI no se confirma (D-10): se
       cierra con diferencia.
    3. La misma persona dos veces en la familia es un error que dice dónde está.
    4. Resuelve el ``Ciudadano`` por DNI, o le da el alta mínima.
    5. La cama (``plaza``: instancia o id, del dispositivo de la derivación):

       * **reservada para esta familia** → ``reservas_derivacion.consumir_reserva_de_derivacion``: la
         reserva pasa a nombre de quien entra y queda ``CONSUMIDA``;
       * **libre, sin reserva** (la familia creció o la guardia cambió la cama) →
         ``estadias.ingresar_persona`` directo. Regla de la reserva sobrante: **la
         derivación nunca retiene más camas que personas faltan confirmar**. Si después de
         esta confirmación quedarían más reservas vigentes que personas sin confirmar, se
         libera **una** —la de la plaza con id más alto— en esta misma transacción, antes
         del ingreso. Si todavía hacen falta todas (reservó 5 de 7), no se libera ninguna.
         Las **reservas comunes** de la persona, en cualquier dispositivo, se cierran (D2
         del Cambio 409), como en ``ingreso.confirmar_ingreso``;
       * con una reserva común **de la misma persona** → el ingreso la consume;
       * reservada para otra persona, ocupada o fuera de servicio → ``ValidationError``
         sobre ``plaza`` diciendo cuál y que elija otra.

    6. Una persona con estadía abierta en la red → :class:`PersonaYaAlojada`.
    7. Crea el ``VinculoFamiliar`` con el responsable según el parentesco (si quien se
       confirma **es** el responsable, no), completa en el legajo lo que estaba vacío y
       guarda en la fila ``ciudadano``, ``estadia``, ``ficha``, ``ficha_completa`` y
       ``confirmada_en``. El ``INGRESO`` de la bitácora lo deja ``ingresar_persona``.

    ``uuid_cliente`` (opcional, RU-16) queda en la ficha: reenviar la misma confirmación
    devuelve la fila tal cual, con ``integrante.ya_estaba = True``. Una fila ya confirmada
    por otro envío es :class:`EstadoCambio` (otra guardia se adelantó: recargar).

    Devuelve el ``IntegranteGrupo`` con ``ya_estaba``, ``confirmadas``, ``total_declarado`` y
    ``reserva_liberada`` (si devolvió una cama sobrante) como atributos.
    """

    caso, derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO)
    dispositivo = derivacion.dispositivo
    grupo = caso.grupo
    filas = _filas_de(grupo)
    integrante = next((fila for fila in filas if fila.orden == orden), None)
    if integrante is None:
        raise ValidationError({"orden": "Esa persona no es de esta familia. Recargá la lista."})
    uuid_cliente = _como_uuid(uuid_cliente)

    if integrante.confirmada:
        if uuid_cliente is not None and integrante.ficha.get("uuid_cliente") == str(uuid_cliente):
            integrante.ya_estaba = True
            integrante.confirmadas, integrante.total_declarado = _confirmadas(filas), grupo.total_declarado
            integrante.reserva_liberada = False
            return integrante
        raise EstadoCambio(
            f"La persona {orden} ya fue confirmada. Recargá la lista.", estado_actual=caso.estado, caso=caso
        )

    ficha = normalizar_ficha(ficha)
    dni = ficha[SECCION_DATOS].get("dni")
    if not dni_valido(dni):
        raise ValidationError({"dni": SIN_NUMERO_DE_DOCUMENTO})
    repetida = _ya_confirmada_en(filas, integrante, dni)
    if repetida is not None:
        raise repetida
    existente = buscar_ciudadano_por_dni(dni)
    ficha = ficha_minima_valida(_con_lo_del_legajo(ficha, existente))
    cama = _cama_del_dispositivo(plaza, dispositivo, derivacion)

    # La reserva que toma esa cama, leída sin candado: decide el camino. `reservas_derivacion` la
    # vuelve a leer bloqueada, y si cambió en el medio falla con su propio error. Que sea de
    # **esta** derivación se mira acá: `consumir_reserva_de_derivacion` no recibe la derivación y
    # acepta la de cualquiera (`derivacion_id` no cambia nunca, así que leerlo sin candado alcanza).
    # Una reserva **común de la misma persona** en esa cama es suya: el ingreso la consume
    # (`propia`), como en `ingreso.confirmar_ingreso`.
    reserva = ReservaPlaza.objects.que_toman().filter(plaza_id=cama.pk).order_by("id").first()
    propia = None
    if reserva is not None and reserva.derivacion_id != derivacion.pk:
        if reserva.derivacion_id is None and existente is not None and reserva.ciudadano_id == existente.pk:
            propia, reserva = reserva, None
        else:
            raise ValidationError(
                {
                    "plaza": f"La cama {plaza_con_sector(cama, cama.sector.nombre)} "
                    "está reservada para otra persona · elegí otra."
                }
            )

    # El alta, antes de las plazas (ver el orden de candados del módulo).
    ciudadano = existente if existente is not None else _dar_de_alta(ficha)

    reserva_liberada = False
    try:
        if reserva is not None:
            estadia = consumir_reserva_de_derivacion(reserva=reserva, ciudadano=ciudadano, usuario=usuario)
        else:
            estadia, reserva_liberada = _ingresar_en_cama_libre(
                ciudadano=ciudadano,
                cama=cama,
                propia=propia,
                derivacion=derivacion,
                por_confirmar_despues=max(grupo.total_declarado - _confirmadas(filas) - 1, 0),
                usuario=usuario,
            )
    except AlojamientoEnLaRed as error:
        raise PersonaYaAlojada(ciudadano, error.verificacion) from error
    except ValidationError as error:
        raise _error_de_cama(error, cama) from error

    parentesco = ficha[SECCION_PARENTESCO]["parentesco"]
    if ciudadano.pk != grupo.responsable_id:
        _vincular_con_el_responsable(grupo, ciudadano, parentesco, caso)
    _completar_legajo(ciudadano, ficha)

    ficha.update(_claves_de_envio(integrante.ficha))
    if uuid_cliente is not None:
        ficha["uuid_cliente"] = str(uuid_cliente)
    ahora = timezone.now()
    integrante.ciudadano = ciudadano
    integrante.parentesco = parentesco
    integrante.parentesco_otro = ficha[SECCION_PARENTESCO].get("parentesco_otro", "")
    integrante.estadia = estadia
    integrante.ficha = ficha
    integrante.ficha_completa = ficha_esta_completa(ficha)
    integrante.confirmada_en = ahora
    integrante.save(
        update_fields=[
            "ciudadano",
            "parentesco",
            "parentesco_otro",
            "estadia",
            "ficha",
            "ficha_completa",
            "confirmada_en",
            "modificado",
        ]
    )

    confirmadas = _confirmadas(filas)  # la fila es la misma instancia que está en `filas`
    _trazar(
        caso,
        usuario,
        Accion.INTEGRANTE_CONFIRMADO,
        estado_anterior=caso.estado,
        detalle=(
            f"Persona {orden} confirmada · cama {plaza_con_sector(cama, cama.sector.nombre)} · "
            f"{confirmadas} de {grupo.total_declarado}"
        ),
    )
    integrante.ya_estaba = False
    integrante.confirmadas, integrante.total_declarado = confirmadas, grupo.total_declarado
    integrante.reserva_liberada = reserva_liberada
    return integrante


@transaction.atomic
def completar_ficha(*, caso, orden, usuario, ficha):
    """Completa las secciones 4 a 8 de una persona **ya confirmada** (M2-3, E6-integrantes).

    Vale con el ingreso en curso y con la familia ya alojada. ``ficha`` trae las secciones
    que se cargan (anidadas, como en :data:`ESQUEMA_FICHA`): cada sección **que viene**
    reemplaza a la guardada; las que no vienen, y las tres del mínimo —la identidad no se
    cambia después de confirmar—, quedan como estaban. Recalcula ``ficha_completa``.

    Un menor de 16 no puede quedar sin adulto responsable: se revalida el mínimo.

    Devuelve el ``IntegranteGrupo``.
    """

    caso, _derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO, Estado.ALOJADO)
    integrante = IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, orden=orden).first()
    if integrante is None:
        raise ValidationError({"orden": "Esa persona no es de esta familia. Recargá la lista."})
    if not integrante.confirmada:
        raise ValidationError({"orden": f"Primero confirmá a la persona {orden} con su cama."})

    ficha = ficha if isinstance(ficha, dict) else {}
    nueva = dict(integrante.ficha)
    for seccion in SECCIONES_OPCIONALES:
        if seccion in ficha:
            nueva[seccion] = ficha[seccion]
    nueva = ficha_minima_valida(nueva)
    nueva.update(_claves_de_envio(integrante.ficha))
    integrante.ficha = nueva
    integrante.ficha_completa = ficha_esta_completa(nueva)
    integrante.save(update_fields=["ficha", "ficha_completa", "modificado"])
    _trazar(
        caso,
        usuario,
        Accion.FICHA_ACTUALIZADA,
        estado_anterior=caso.estado,
        detalle=f"Ficha de la persona {orden} · {'completa' if integrante.ficha_completa else 'incompleta'}",
    )
    return integrante


@transaction.atomic
def agregar_integrante(*, caso, usuario, uuid_cliente=None):
    """Suma una persona que no estaba declarada (HU-3.5, RN-3.8).

    ``total_declarado`` crece en uno y aparece una fila nueva, sin confirmar. No reserva
    cama: al confirmarla se elige entre las libres, y si no hay ninguna la confirmación lo
    dice («Sin cama libre · liberá una o cerrá con diferencia»). La traza cuenta «N sobre M
    declaradas», con M lo que dijo el Formulario 1.

    ``uuid_cliente`` (opcional, RU-16) queda en la ficha de la fila nueva: reenviarlo
    devuelve esa misma fila, con ``integrante.ya_estaba = True``, sin sumar otra.

    Devuelve el ``IntegranteGrupo`` nuevo, con ``ya_estaba`` y ``total_declarado``.
    """

    caso, _derivacion = _abrir_ingreso(caso, usuario, Estado.INGRESO_EN_CURSO)
    grupo = caso.grupo
    uuid_cliente = _como_uuid(uuid_cliente)
    filas = _filas_de(grupo)
    if uuid_cliente is not None:
        for fila in filas:
            if fila.ficha.get("uuid_cliente_alta") == str(uuid_cliente):
                fila.ya_estaba, fila.total_declarado = True, grupo.total_declarado
                return fila

    grupo.total_declarado += 1
    grupo.save(update_fields=["total_declarado", "modificado"])
    integrante = IntegranteGrupo.objects.create(
        grupo=grupo,
        orden=max((fila.orden for fila in filas), default=0) + 1,
        ficha={"uuid_cliente_alta": str(uuid_cliente)} if uuid_cliente is not None else {},
    )
    _trazar(
        caso,
        usuario,
        Accion.INTEGRANTE_AGREGADO,
        estado_anterior=caso.estado,
        detalle=(
            f"Agregada persona por el dispositivo · {grupo.total_declarado} sobre "
            f"{grupo.suma_de_cantidades()} declaradas"
        ),
    )
    integrante.ya_estaba, integrante.total_declarado = False, grupo.total_declarado
    return integrante
