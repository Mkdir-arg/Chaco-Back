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

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from programas.models import Dispositivo, Estadia, Plaza, Sector, TrazaDispositivo
from programas.services.dispositivos import puede_operar_dispositivo
from programas.services.estadias import reservas_abiertas

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


def _exigir_alcance(dispositivo, usuario):
    """La capacidad con alcance al dispositivo, y que el dispositivo siga abierto.

    En ese orden: quien no tiene alcance no se entera de en qué estado está el legajo.
    """

    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para configurar las plazas de este dispositivo.")
    if dispositivo.estado == Dispositivo.Estado.CERRADO:
        raise ValidationError({"__all__": DISPOSITIVO_CERRADO})


def _normalizar(texto):
    return " ".join((texto or "").split())


def _exigir_nombre_libre(dispositivo, nombre, *, excepto=None):
    """El `UniqueConstraint` de (dispositivo, nombre) dicho como error de campo.

    Se pregunta además de dejar que el constraint hable: un `IntegrityError` dentro de una
    transacción la aborta, y el modal necesita volver con el error puesto en su campo.
    """

    repetidos = Sector.objects.filter(dispositivo=dispositivo, nombre=nombre)
    if excepto is not None:
        repetidos = repetidos.exclude(pk=excepto.pk)
    if repetidos.exists():
        raise ValidationError({"nombre": "Ya hay un sector con ese nombre en este dispositivo."})


def _exigir_tipo_de_plaza_admitido(dispositivo, tipo):
    """El tipo de plaza lo declara el tipo de dispositivo (`tipos_plaza_admitidos`).

    Una lista vacía quiere decir «sin restricción declarada», no «no admite ninguna»:
    es lo que ya dice `TipoDispositivo.admite_tipo_de_plaza`, y acá no se vuelve a decidir.
    """

    if not dispositivo.tipo.admite_tipo_de_plaza(tipo):
        admitidos = ", ".join(Plaza.Tipo(valor).label for valor in dispositivo.tipo.tipos_de_plaza)
        raise ValidationError({"tipo": f"{dispositivo.tipo.nombre} solo admite plazas de tipo: {admitidos}."})


def plazas_tomadas_del_sector(sector):
    """Cuántas plazas del sector están tomadas: estadía activa, reserva o préstamo sin liberar.

    Dos consultas fijas, no una por plaza. «Sin liberar» y no «vigente» a propósito: la
    reserva vencida que nadie liberó sigue atada a la plaza (es la que enciende la alerta
    de P4), y dar de baja el sector la dejaría colgando de una plaza que ya no se dibuja.
    """

    plazas = Plaza.objects.filter(sector=sector).values("pk")
    con_estadia = set(Estadia.objects.activas().filter(plaza__sector=sector).values_list("plaza_id", flat=True))
    con_reserva = set(reservas_abiertas(plazas).values_list("plaza_id", flat=True))
    return len(con_estadia | con_reserva)


@transaction.atomic
def crear_sector(*, dispositivo, usuario, nombre, tipo, perfil="", capacidad=0, condiciones_uso=""):
    """Da de alta un sector del dispositivo. Nace activo y sin plazas: las agrega el lote."""

    _exigir_alcance(dispositivo, usuario)
    nombre = _normalizar(nombre)
    if not nombre:
        raise ValidationError({"nombre": "El sector necesita un nombre."})
    _exigir_nombre_libre(dispositivo, nombre)

    sector = Sector.objects.create(
        dispositivo=dispositivo,
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
        detalle=f"Sector {sector.nombre} · {Sector.Tipo(sector.tipo).label} · capacidad declarada {sector.capacidad}",
    )
    return sector


@transaction.atomic
def editar_sector(*, sector, usuario, nombre, tipo, perfil="", capacidad=0, condiciones_uso="", activo=True):
    """Cambia los datos del sector y, si `activo` pasa a falso, lo da de baja.

    La baja va por acá y no por un botón propio porque es un estado del sector, no una
    acción distinta: el sector dado de baja deja de dibujarse en el mapa y de ofrecerse
    para ingresar, y sus plazas siguen existiendo para la historia que ya tienen.

    La fila se relee bloqueada: entre que la pantalla se dibujó y el envío, alguien pudo
    alojar a una persona en una plaza del sector que se está dando de baja.
    """

    _exigir_alcance(sector.dispositivo, usuario)
    nombre = _normalizar(nombre)
    if not nombre:
        raise ValidationError({"nombre": "El sector necesita un nombre."})

    sector = Sector.objects.select_for_update().select_related("dispositivo__tipo").get(pk=sector.pk)
    dispositivo = sector.dispositivo
    _exigir_nombre_libre(dispositivo, nombre, excepto=sector)

    daba_de_baja = sector.activo and not activo
    if daba_de_baja:
        tomadas = plazas_tomadas_del_sector(sector)
        if tomadas:
            raise ValidationError(
                {"activo": SECTOR_CON_PLAZAS_TOMADAS.format(cuantas=tomadas, plural="s" if tomadas > 1 else "")}
            )

    sector.nombre = nombre
    sector.tipo = tipo
    sector.perfil = _normalizar(perfil)
    sector.capacidad = capacidad or 0
    sector.condiciones_uso = (condiciones_uso or "").strip()
    sector.activo = bool(activo)
    sector.save(update_fields=["nombre", "tipo", "perfil", "capacidad", "condiciones_uso", "activo", "modificado"])

    _trazar(
        dispositivo,
        usuario,
        "SECTOR_BAJA" if daba_de_baja else "SECTOR_EDITADO",
        detalle=f"Sector {sector.nombre} · {Sector.Tipo(sector.tipo).label} · capacidad declarada {sector.capacidad}",
    )
    return sector


def _codigos_del_dispositivo(dispositivo):
    """Todos los códigos de plaza de la institución, en una consulta.

    Dispositivo y no sector: el modelo exige el código único **por sector**, así que dos
    pabellones podrían tener los dos una «01». El lote autogenerado no las crea igual de
    todos modos —un código se lee solo, sin su sector, en los mensajes y en la bitácora—,
    pero tampoco rechaza la que ya exista: lo que hace es saltearla al numerar.
    """

    return set(Plaza.objects.filter(sector__dispositivo=dispositivo).values_list("codigo", flat=True))


def codigos_en_lote(*, cantidad, prefijo, tomados):
    """Los `cantidad` códigos del lote: `prefijo` + número, salteando los que ya existen.

    Numera desde 1 y rellena a dos dígitos (`A-01`, como el mockup), así que el orden
    alfabético del mapa coincide con el numérico hasta 99. Es una función pura para poder
    probarla sin base.
    """

    codigos = []
    numero = 1
    while len(codigos) < cantidad:
        codigo = f"{prefijo}{numero:02d}"
        if codigo not in tomados:
            codigos.append(codigo)
            tomados.add(codigo)
        numero += 1
    return codigos


@transaction.atomic
def agregar_plazas(*, sector, usuario, cantidad, tipo=Plaza.Tipo.CAMA, prefijo=""):
    """Agrega un lote de plazas al sector, con el código autogenerado o con prefijo.

    Las plazas nacen operativas: una plaza que todavía no se puede usar se saca de servicio
    con su motivo, que es lo que el mapa sabe mostrar.

    La fila del sector se bloquea mientras se numera: dos lotes simultáneos sobre el mismo
    sector elegirían los mismos números y el segundo moriría contra el `UniqueConstraint`.
    """

    _exigir_alcance(sector.dispositivo, usuario)

    sector = Sector.objects.select_for_update().select_related("dispositivo__tipo").get(pk=sector.pk)
    dispositivo = sector.dispositivo
    if not sector.activo:
        raise ValidationError({"sector": "El sector está dado de baja: reactivalo antes de agregarle plazas."})

    cantidad = int(cantidad or 0)
    if cantidad < 1:
        raise ValidationError({"cantidad": "Indicá cuántas plazas agregar."})
    if cantidad > TOPE_POR_LOTE:
        raise ValidationError({"cantidad": f"Se agregan hasta {TOPE_POR_LOTE} plazas por vez."})
    _exigir_tipo_de_plaza_admitido(dispositivo, tipo)

    prefijo = (prefijo or "").strip()
    codigos = codigos_en_lote(cantidad=cantidad, prefijo=prefijo, tomados=_codigos_del_dispositivo(dispositivo))
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

    El estado operativo es de `estadias.sacar_plaza_de_servicio` y
    `estadias.volver_plaza_a_servicio`: tienen su propia regla (la plaza tomada no sale) y
    su propio modal en P5.
    """

    dispositivo = plaza.sector.dispositivo
    _exigir_alcance(dispositivo, usuario)

    codigo = _normalizar(codigo)
    if not codigo:
        raise ValidationError({"codigo": "La plaza necesita un código."})
    _exigir_tipo_de_plaza_admitido(dispositivo, tipo)

    plaza = Plaza.objects.select_for_update().get(pk=plaza.pk)
    if Plaza.objects.filter(sector_id=plaza.sector_id, codigo=codigo).exclude(pk=plaza.pk).exists():
        raise ValidationError({"codigo": "Ya hay una plaza con ese código en el sector."})

    anterior = plaza.codigo
    plaza.codigo = codigo
    plaza.tipo = tipo
    plaza.save(update_fields=["codigo", "tipo", "modificado"])

    _trazar(
        dispositivo,
        usuario,
        "PLAZA_EDITADA",
        detalle=f"Plaza {anterior} → {plaza.codigo} · {Plaza.Tipo(plaza.tipo).label}",
    )
    return plaza
