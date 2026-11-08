"""Alta y edición de la **capacidad instalada**: sectores y plazas (MVP v2, carril C5 · P5).

Hasta este cambio no había ninguna forma de crear un `Sector` ni una `Plaza`: ni ruta, ni
formulario, ni admin. Fuera de los tests nadie los creaba, así que el mapa de plazas, el
asistente de ingreso y los indicadores del detalle nacían vacíos y prometían «cuando se
carguen los sectores…» sin que hubiera dónde. Esto es ese «dónde».

Qué vive acá y qué no
---------------------

Acá va **configuración**: cuántas plazas hay y cómo se llaman. Lo que decide si una plaza
está tomada —estadías, reservas y préstamos— vive en `programas.services.estadias`, y este
módulo se lo **pregunta**; nunca lo deriva de vuelta. Por eso sacar y reponer una plaza de
servicio siguen allá: la condición que las gobierna es la estadía.

Las cifras tampoco se tocan: `Sector.capacidad` es la cifra **declarada** (la del legajo) y
la operativa la cuenta `programas.services.ocupacion` desde las plazas. El modelo las tiene
separadas a propósito, y P5 ya muestra cuándo difieren; forzar que coincidan borraría
justamente el dato que sirve para ver dónde el papel y el mapa no se parecen.

Nada se borra
-------------

Un sector con historia **se da de baja** (`activo=False`), no se elimina: sus plazas
siguen colgando de estadías cerradas y de movimientos, que son inmutables. Y no se da de
baja si alguna de sus plazas está tomada —estadía activa, reserva o préstamo sin
liberar—: primero se reubica a la persona, que es exactamente lo que ya exige
`estadias.sacar_plaza_de_servicio`. Las plazas no tienen baja propia: la forma de retirar
una de la capacidad operativa es sacarla de servicio, con su motivo.
"""

import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from programas.models import Dispositivo, Plaza, Sector, TrazaDispositivo
from programas.selectors.capacidad_dispositivo import codigos_del_sector, plazas_tomadas_del_sector
from programas.services.dispositivos import puede_operar_dispositivo
from programas.services.estadias import _plaza_tomada_por
from programas.services.nombre_plaza import plaza_con_sector

#: Configurar la capacidad instalada es edición del legajo, no operación diaria. La misma
#: capacidad con la que se saca una plaza de servicio.
CAP_EDITAR = "dispositivo.editar"

#: Tope de un lote de «Agregar plazas». No es una regla de negocio: es el tamaño a partir
#: del cual un error de tipeo deja de ser corregible a mano. El mapa, además, dibuja hasta
#: 200 plazas por sector (`sectores_plazas.TOPE_PLAZAS_POR_SECTOR`).
TOPE_POR_LOTE = 200

#: Por qué no se puede dar de baja un sector. El mismo texto que el bloqueo de la plaza
#: ocupada de P5: la salida es la misma, reubicar.
SECTOR_CON_PLAZAS_TOMADAS = (
    "El sector tiene {cuantas} plaza{plural} tomada{plural}: reubicá a esas personas o "
    "liberá sus reservas antes de darlo de baja."
)

#: Un dispositivo cerrado conserva su legajo y no admite operaciones nuevas. Es la misma
#: regla que ya aplica `DispositivoUpdateView` sobre los datos del legajo.
DISPOSITIVO_CERRADO = "El dispositivo está cerrado: no se puede cambiar su capacidad instalada."


#: Un dispositivo rechazado nunca se habilitó: no tiene capacidad que configurar.
DISPOSITIVO_RECHAZADO = "El dispositivo está rechazado: no se puede cambiar su capacidad instalada."

#: El tipo no asigna plaza al ingresar ni declara tipos de plaza: no tiene sectores ni plazas.
TIPO_SIN_PLAZAS = "Este tipo de dispositivo no maneja sectores ni plazas."

_ESTADOS_SIN_CAPACIDAD = {
    Dispositivo.Estado.CERRADO: DISPOSITIVO_CERRADO,
    Dispositivo.Estado.RECHAZADO: DISPOSITIVO_RECHAZADO,
}


def motivo_sin_ampliar_capacidad(dispositivo):
    """Por qué **no se pueden dar de alta sectores ni plazas** en el dispositivo, o ``""``.

    Es la misma pregunta para el servicio y para la pantalla: el botón «Nuevo sector» y el
    rechazo del servicio no pueden discrepar. Dos motivos: el estado del legajo (cerrado o
    rechazado no admiten capacidad nueva) y el tipo, que si no maneja plazas
    (`TipoDispositivo.maneja_plazas`) no tiene qué ordenar en sectores.
    """

    motivo = _ESTADOS_SIN_CAPACIDAD.get(dispositivo.estado, "")
    if motivo:
        return motivo
    if not dispositivo.tipo.maneja_plazas:
        return TIPO_SIN_PLAZAS
    return ""


def _trazar(dispositivo, usuario, accion, *, detalle=""):
    """Traza sobre el patrón de `TrazaDispositivo`: aditiva, inmutable, sin nombres propios.

    Igual que la de `programas.services.estadias`: el historial del legajo institucional lo
    lee todo el que opera el dispositivo, así que el detalle va con códigos y cantidades.
    """

    TrazaDispositivo.objects.create(
        dispositivo=dispositivo,
        usuario=usuario,
        accion=accion,
        detalle=detalle,
    )


def puede_configurar_plazas(usuario, dispositivo, puede_editar=None):
    """¿Se pueden editar sectores y plazas existentes (o sacarlas de servicio)? Capacidad con alcance y no cerrado.

    La misma regla que `_exigir_alcance` aplica al escribir: la pantalla de «Sectores y plazas» lee esta
    bandera y no ofrece lo que el servidor va a rechazar (Cambio 409, N-01). ``puede_editar`` es el
    resultado ya calculado de `puede_operar_dispositivo(..., CAP_EDITAR)`: si viene, no se repite la consulta.
    """

    if dispositivo.estado == Dispositivo.Estado.CERRADO:
        return False
    if puede_editar is not None:
        return puede_editar
    return puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR)


def _exigir_alcance(dispositivo, usuario):
    """La capacidad con alcance al dispositivo, y que el dispositivo no esté cerrado.

    Editar lo que ya existe solo lo frena el cierre; que un dispositivo rechazado no admita capacidad
    **nueva** lo dice `motivo_sin_ampliar_capacidad`, que usan las altas.

    En ese orden: quien no tiene alcance no se entera de en qué estado está el legajo.
    """

    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para configurar las plazas de este dispositivo.")
    if dispositivo.estado == Dispositivo.Estado.CERRADO:
        raise ValidationError({"__all__": DISPOSITIVO_CERRADO})


def _exigir_que_se_pueda_ampliar(dispositivo):
    """Las altas (sector nuevo, lote de plazas) piden además que el tipo maneje plazas."""

    motivo = motivo_sin_ampliar_capacidad(dispositivo)
    if motivo:
        raise ValidationError({"__all__": motivo})


def _normalizar(texto):
    return " ".join((texto or "").split())


def _exigir_nombre_libre(dispositivo, nombre, *, excepto=None, mensaje=None):
    """El nombre es único entre los sectores ACTIVOS del dispositivo; uno dado de baja libera el suyo.

    No hay UNIQUE en la base (MySQL/MariaDB no tienen índice único condicional): la regla es esta
    y la sostiene el bloqueo de la fila del dispositivo (`_bloquear_dispositivo`), que tienen que
    tomar el alta, la edición y la reactivación antes de llamarla. `mensaje` reemplaza el aviso
    estándar (la reactivación explica qué hacer).
    """

    repetidos = Sector.objects.filter(dispositivo=dispositivo, nombre=nombre, activo=True)
    if excepto is not None:
        repetidos = repetidos.exclude(pk=excepto.pk)
    if repetidos.exists():
        raise ValidationError({"nombre": mensaje or "Ya hay un sector activo con ese nombre en este dispositivo."})


def _exigir_nombre_libre_al_reactivar(dispositivo, sector):
    """La regla del nombre al volver a activo un sector: la misma para «Reactivar» y para «Editar».

    La baja liberó el nombre y otro sector activo pudo haberlo tomado. Con la regla en un solo
    lugar, las dos entradas dan el mismo mensaje y no pueden divergir.
    """

    _exigir_nombre_libre(
        dispositivo,
        sector.nombre,
        excepto=sector,
        mensaje=(
            f"No se puede reactivar: ya hay un sector activo llamado «{sector.nombre}». "
            "Renombrá uno de los dos y volvé a intentar."
        ),
    )


def _bloquear_dispositivo(dispositivo):
    """Serializa las altas, ediciones y reactivaciones de sectores del mismo dispositivo.

    Devuelve el dispositivo ya bloqueado y fresco.
    """

    return Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)


def _etiqueta_edificio(edificio):
    return edificio.codigo if edificio is not None else "sin edificio"


def _detalle_sector(sector, *, edificio_anterior=False):
    """El detalle de la traza: con el edificio, y con de dónde venía si el edificio cambió.

    `edificio_anterior` es ``False`` cuando no cambió (un `None` es un valor válido: «sin edificio»).
    """

    detalle = (
        f"Sector {sector.nombre} · {Sector.Tipo(sector.tipo).label} · capacidad declarada {sector.capacidad}"
        f" · edificio {_etiqueta_edificio(sector.edificio)}"
    )
    if edificio_anterior is not False:
        detalle += f" (antes: {_etiqueta_edificio(edificio_anterior)})"
    return detalle


def _exigir_edificio_del_dispositivo(dispositivo, edificio):
    """El edificio tiene que estar vinculado al dispositivo: no se puede ubicar un sector en un inmueble ajeno.

    Se valida acá y no solo en el formulario: el selector ya ofrece solo esos edificios, pero un POST
    armado a mano no pasa por el selector. Va bajo el bloqueo del dispositivo, el mismo que toma
    `edificios.desvincular_edificio`, así que no se puede desvincular entre esta consulta y el guardado.
    """

    if edificio is None:
        raise ValidationError({"edificio": "Elegí el edificio del sector."})
    if not dispositivo.edificios.filter(pk=edificio.pk).exists():
        raise ValidationError({"edificio": "Ese edificio no está vinculado a este dispositivo."})


def _exigir_tipo_de_plaza_admitido(dispositivo, tipo):
    """El tipo de plaza lo declara el tipo de dispositivo (`tipos_plaza_admitidos`).

    Una lista vacía quiere decir «sin restricción declarada», no «no admite ninguna»:
    es lo que ya dice `TipoDispositivo.admite_tipo_de_plaza`, y acá no se vuelve a decidir.
    """

    if tipo not in Plaza.Tipo.values:
        raise ValidationError({"tipo": "Elegí un tipo de plaza válido."})
    if not dispositivo.tipo.admite_tipo_de_plaza(tipo):
        admitidos = ", ".join(Plaza.Tipo(valor).label for valor in dispositivo.tipo.tipos_de_plaza)
        raise ValidationError({"tipo": f"{dispositivo.tipo.nombre} solo admite plazas de tipo: {admitidos}."})


#: Tope de la capacidad **declarada** de un sector. Es un dato del legajo, no se relaciona con las plazas.
CAPACIDAD_DECLARADA_MAXIMA = 9999


def _exigir_capacidad_declarada(capacidad):
    if capacidad is not None and not 0 <= capacidad <= CAPACIDAD_DECLARADA_MAXIMA:
        raise ValidationError({"capacidad": f"La capacidad declarada va de 0 a {CAPACIDAD_DECLARADA_MAXIMA}."})


@transaction.atomic
def crear_sector(*, dispositivo, usuario, nombre, tipo, edificio=None, perfil="", capacidad=0, condiciones_uso=""):
    """Da de alta un sector del dispositivo. Nace activo y sin plazas: las agrega el lote.

    El edificio es obligatorio y tiene que ser uno de los vinculados al dispositivo (Cambio 429).
    """

    _exigir_alcance(dispositivo, usuario)
    _exigir_capacidad_declarada(capacidad)
    _exigir_que_se_pueda_ampliar(dispositivo)
    nombre = _normalizar(nombre)
    if not nombre:
        raise ValidationError({"nombre": "El sector necesita un nombre."})
    _bloquear_dispositivo(dispositivo)
    _exigir_edificio_del_dispositivo(dispositivo, edificio)
    _exigir_nombre_libre(dispositivo, nombre)

    sector = Sector.objects.create(
        dispositivo=dispositivo,
        edificio=edificio,
        nombre=nombre,
        tipo=tipo,
        perfil=_normalizar(perfil),
        capacidad=capacidad or 0,
        condiciones_uso=(condiciones_uso or "").strip(),
    )
    _trazar(
        dispositivo,
        usuario,
        "SECTOR_CREADO",
        detalle=_detalle_sector(sector),
    )
    return sector


@transaction.atomic
def editar_sector(
    *, sector, usuario, nombre, tipo, edificio=None, perfil="", capacidad=0, condiciones_uso="", activo=True
):
    """Cambia los datos del sector y, si `activo` pasa a falso, lo da de baja.

    El edificio se puede cambiar (siempre a uno vinculado al dispositivo) y es obligatorio mientras el
    sector quede activo: un sector anterior al campo, sin edificio, no se puede guardar sin elegir uno.
    Dar de baja uno sin edificio no lo exige. El cambio queda en la traza `SECTOR_EDITADO` con el
    edificio de antes y el de ahora.

    La baja va por acá y no por un botón propio porque es un estado del sector, no una
    acción distinta: el sector dado de baja deja de dibujarse en el mapa y de ofrecerse
    para ingresar, y sus plazas siguen existiendo para la historia que ya tienen.

    Se bloquean también las plazas antes de comprobar la baja: el ingreso y la reserva
    toman ese mismo bloqueo, así que no pueden ocuparlas entre la consulta y el guardado.
    """

    _exigir_alcance(sector.dispositivo, usuario)
    nombre = _normalizar(nombre)
    if not nombre:
        raise ValidationError({"nombre": "El sector necesita un nombre."})

    _bloquear_dispositivo(sector.dispositivo)
    sector = Sector.objects.select_for_update().get(pk=sector.pk)
    # Un sector anterior al tope conserva su cifra: solo se exige el tope si la cifra cambia.
    if (capacidad or 0) != sector.capacidad:
        _exigir_capacidad_declarada(capacidad)
    dispositivo = sector.dispositivo
    edificio_anterior = sector.edificio
    reactiva = activo and not sector.activo
    # Un sector inactivo que sigue inactivo no compite por el nombre; si queda activo, sí. Al
    # reactivarlo desde «Editar» rige la misma regla (y el mismo mensaje) que en «Reactivar»,
    # con el nombre ya guardado: si el usuario lo renombra en el mismo guardado, el nuevo se
    # valida como en cualquier edición.
    if reactiva and nombre == sector.nombre:
        _exigir_nombre_libre_al_reactivar(dispositivo, sector)
    elif activo:
        _exigir_nombre_libre(dispositivo, nombre, excepto=sector)
    if edificio is None:
        if activo:
            raise ValidationError({"edificio": "Elegí el edificio del sector."})
        edificio = edificio_anterior
    elif activo or edificio.pk != sector.edificio_id:
        _exigir_edificio_del_dispositivo(dispositivo, edificio)

    daba_de_baja = sector.activo and not activo
    if daba_de_baja:
        list(Plaza.objects.select_for_update().filter(sector=sector).order_by("pk").values_list("pk", flat=True))
        tomadas = plazas_tomadas_del_sector(sector)
        if tomadas:
            raise ValidationError(
                {"activo": SECTOR_CON_PLAZAS_TOMADAS.format(cuantas=tomadas, plural="s" if tomadas > 1 else "")}
            )

    cambio_edificio = (edificio.pk if edificio else None) != sector.edificio_id
    sector.edificio = edificio
    sector.nombre = nombre
    sector.tipo = tipo
    sector.perfil = _normalizar(perfil)
    sector.capacidad = capacidad or 0
    sector.condiciones_uso = (condiciones_uso or "").strip()
    sector.activo = bool(activo)
    sector.save(
        update_fields=["edificio", "nombre", "tipo", "perfil", "capacidad", "condiciones_uso", "activo", "modificado"]
    )

    _trazar(
        dispositivo,
        usuario,
        "SECTOR_BAJA" if daba_de_baja else ("SECTOR_REACTIVADO" if reactiva else "SECTOR_EDITADO"),
        detalle=_detalle_sector(sector, edificio_anterior=edificio_anterior if cambio_edificio else False),
    )
    return sector


@transaction.atomic
def reactivar_sector(*, sector, usuario):
    """Vuelve a dar de alta un sector dado de baja: recupera sus plazas y sus estadías no se tocan.

    Se bloquea si ya hay un sector activo con el mismo nombre (la baja liberó el nombre y
    pudo haberlo tomado otro). Va bajo el bloqueo del dispositivo, el mismo del alta.
    """

    _exigir_alcance(sector.dispositivo, usuario)
    dispositivo = _bloquear_dispositivo(sector.dispositivo)
    sector = Sector.objects.select_for_update().get(pk=sector.pk)
    if sector.activo:
        raise ValidationError({"__all__": "Ese sector ya está activo."})
    _exigir_nombre_libre_al_reactivar(dispositivo, sector)

    if sector.edificio_id is None:
        # El edificio es obligatorio mientras el sector quede activo (Cambio 429): uno anterior al
        # campo vuelve a activo solo desde «Editar», eligiendo el edificio.
        raise ValidationError(
            {
                "__all__": "No se puede reactivar: el sector no tiene edificio. Editá el sector, elegí un edificio y activalo."
            }
        )
    if not dispositivo.edificios.filter(pk=sector.edificio_id).exists():
        raise ValidationError(
            {
                "__all__": "No se puede reactivar: el edificio del sector ya no está vinculado a este dispositivo. "
                "Editá el sector, elegí un edificio y activalo."
            }
        )

    sector.activo = True
    sector.save(update_fields=["activo", "modificado"])
    _trazar(
        dispositivo,
        usuario,
        "SECTOR_REACTIVADO",
        detalle=_detalle_sector(sector),
    )
    return sector


def codigos_en_lote(*, cantidad, prefijo, tomados):
    """Los `cantidad` códigos del lote: `prefijo` + número, siguiendo al mayor que ya hay.

    `tomados` son los códigos de **todas** las plazas del sector, también las fuera de servicio:
    el siguiente es el mayor número con ese prefijo más uno, o 1 si no hay ninguno, así que el
    número de una plaza no se reusa nunca (Cambio 430). Se rellena a dos dígitos (`A-01`, como
    el mockup). Un código que no sigue el patrón no cuenta para el máximo; el generado no puede
    chocar con ninguno porque siempre es mayor. Es una función pura para poder probarla sin base.
    """

    # La comparación coincide con la collation de códigos de MySQL/MariaDB.
    patron = re.compile(rf"{re.escape(prefijo.casefold())}(\d+)")
    numeros = (int(m.group(1)) for m in map(patron.fullmatch, (codigo.casefold() for codigo in tomados)) if m)
    primero = 1 + max(numeros, default=0)
    return [f"{prefijo}{numero:02d}" for numero in range(primero, primero + cantidad)]


@transaction.atomic
def agregar_plazas(*, sector, usuario, cantidad, tipo=Plaza.Tipo.CAMA, prefijo=""):
    """Agrega un lote de plazas al sector, con el código autogenerado o con prefijo.

    Las plazas nacen operativas: una plaza que todavía no se puede usar se saca de servicio
    con su motivo, que es lo que el mapa sabe mostrar.

    La numeración es por sector y arranca en 1 (Cambio 430). Se bloquea el dispositivo antes
    del sector, y los códigos se leen ya con ambos bloqueados: dos lotes simultáneos sobre el
    mismo sector no toman el mismo número.
    """

    _exigir_alcance(sector.dispositivo, usuario)
    _bloquear_dispositivo(sector.dispositivo)
    sector = Sector.objects.select_for_update().get(pk=sector.pk)
    dispositivo = sector.dispositivo
    _exigir_que_se_pueda_ampliar(dispositivo)
    if not sector.activo:
        raise ValidationError({"sector": "El sector está dado de baja: reactivalo antes de agregarle plazas."})

    cantidad = int(cantidad or 0)
    if cantidad < 1:
        raise ValidationError({"cantidad": "Indicá cuántas plazas agregar."})
    if cantidad > TOPE_POR_LOTE:
        raise ValidationError({"cantidad": f"Se agregan hasta {TOPE_POR_LOTE} plazas por vez."})
    _exigir_tipo_de_plaza_admitido(dispositivo, tipo)

    prefijo = (prefijo or "").strip()
    codigos = codigos_en_lote(cantidad=cantidad, prefijo=prefijo, tomados=codigos_del_sector(sector))
    largo = max(len(codigo) for codigo in codigos)
    if largo > Plaza._meta.get_field("codigo").max_length:
        raise ValidationError({"prefijo": "El prefijo es demasiado largo para el código de la plaza."})

    plazas = Plaza.objects.bulk_create([Plaza(sector=sector, codigo=codigo, tipo=tipo) for codigo in codigos])
    _trazar(
        dispositivo,
        usuario,
        "PLAZAS_AGREGADAS",
        detalle=(
            f"Sector {sector.nombre} · {cantidad} plaza{'s' if cantidad > 1 else ''} "
            f"{Plaza.Tipo(tipo).label.lower()} · {codigos[0]} a {codigos[-1]}"
        ),
    )
    return plazas


@transaction.atomic
def editar_plaza(*, plaza, usuario, codigo, tipo):
    """Corrige el código o el tipo de una plaza. No la mueve de sector ni toca su estado.

    Una plaza con estadía, reserva o préstamo vigente primero se reubica o libera.
    Se consulta la misma guarda de estadías con la fila de la plaza bloqueada.
    El dispositivo se bloquea antes: la unicidad del código es por sector (Cambio 430) y se
    revalida dentro de esta transacción, también frente a altas en lote.

    El estado operativo es de `estadias.sacar_plaza_de_servicio` y
    `estadias.volver_plaza_a_servicio`: tienen su propia regla (la plaza tomada no sale) y
    su propio modal en P5.
    """

    dispositivo = plaza.sector.dispositivo
    sector_nombre = plaza.sector.nombre
    _exigir_alcance(dispositivo, usuario)

    codigo = _normalizar(codigo)
    if not codigo:
        raise ValidationError({"codigo": "La plaza necesita un código."})
    _exigir_tipo_de_plaza_admitido(dispositivo, tipo)

    _bloquear_dispositivo(dispositivo)
    plaza = Plaza.objects.select_for_update().get(pk=plaza.pk)
    tomada = _plaza_tomada_por(plaza)
    if tomada:
        raise ValidationError({"__all__": f"La plaza tiene {tomada}: reubicá o liberá antes de editarla."})
    if Plaza.objects.filter(sector=plaza.sector_id, codigo__iexact=codigo).exclude(pk=plaza.pk).exists():
        raise ValidationError({"codigo": "Ya hay una plaza con ese código en el sector."})

    anterior = plaza.codigo
    plaza.codigo = codigo
    plaza.tipo = tipo
    plaza.save(update_fields=["codigo", "tipo", "modificado"])

    _trazar(
        dispositivo,
        usuario,
        "PLAZA_EDITADA",
        detalle=f"Plaza {anterior} → {plaza_con_sector(plaza, sector_nombre)} · {Plaza.Tipo(plaza.tipo).label}",
    )
    return plaza
