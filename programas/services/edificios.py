"""Alta, edición y vinculación del **edificio** de una institución (MVP v2, carril C5 · P19).

`Edificio` existía desde la etapa 1 y lo leían la sección «Edificios», el semáforo
edilicio y los relevamientos del coordinador, pero **no había forma de crear uno**: el
estado vacío decía «aparecen cuando se le asigne uno» y no había dónde asignarlo. Esto es
ese dónde.

El predio compartido
--------------------

La relación con `Dispositivo` es de varios a varios porque un mismo inmueble aloja a más
de una institución (decisión del PM del 08/10/2026, y la tabla «Institución en este
predio» de P19 es su cara visible). De ahí que haya **dos** acciones distintas:

* **crear** un edificio, que nace vinculado a la institución desde la que se lo carga;
* **vincular** un edificio que ya existe, que es como se declara que dos instituciones
  ocupan el mismo predio. A partir de ahí el relevamiento edilicio es uno solo y las dos
  lo ven.

Qué se puede vincular
---------------------

Solo lo que el usuario ya alcanza: `inspecciones.edificios_en_alcance` con
`dispositivo.editar` devuelve los edificios de las instituciones que opera (y todos, para
el administrador del programa). Un responsable institucional no puede, así, enumerar los
edificios de instituciones ajenas probando ids; declarar un predio compartido entre dos
instituciones que no comparte lo hace quien tiene alcance sobre las dos.
"""

from contextlib import contextmanager

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from programas.models import (
    Dispositivo,
    Edificio,
    EntregaKit,
    InspeccionEdificio,
    SaldoStock,
    Sector,
    TrazaDispositivo,
)
from programas.selectors.capacidad_dispositivo import edificios_vinculables
from programas.services.dispositivos import puede_configurar_dispositivos, puede_editar_legajo
from programas.services.equipo_dispositivo import soltar_edificio_del_equipo

#: La misma capacidad con la que se edita el legajo: el edificio es dato del legajo.
CAP_EDITAR = "dispositivo.editar"

#: Campos que el MVP carga del edificio: identidad y domicilio normalizado. Tenencia,
#: servicios, estado físico y plano son de la Versión 2 completa y no están ni en el
#: modelo. Las **coordenadas** van aparte (`COORDENADAS`): no son texto y no se normalizan.
CAMPOS = (
    "nombre",
    "calle",
    "numero",
    "piso_departamento",
    "localidad",
    "provincia",
    "codigo_postal",
)

#: El punto del inmueble (Cambio 493/520), del mapa del formulario. Es lo que lee la distancia de «Derivar».
COORDENADAS = ("latitud", "longitud")

DISPOSITIVO_CERRADO = "El dispositivo está cerrado: no se puede cambiar su edificio."
RELEVAMIENTO_EN_CURSO = "El edificio tiene un relevamiento en curso: no puede quedar sin dispositivos."
SECTORES_ACTIVOS_EN_EL_EDIFICIO = (
    "El edificio tiene {cuantos} sector{plural_sector} activo{plural_activo} de esta institución: "
    "asignales otro edificio o dalos de baja antes de desvincularlo."
)
#: RN-010-15 / decisión 6: el stock es de (institución, edificio); soltar el vínculo lo dejaría huérfano.
STOCK_EN_EL_EDIFICIO = (
    "La institución tiene stock en el edificio ({cuantos}): traspasalo a otro edificio o ajustalo a cero "
    "antes de desvincularlo."
)


# Textos de las confirmaciones de inactivar y reactivar: los comparten la ficha y la página operativa del edificio.
TEXTO_INACTIVAR = "El edificio deja de ofrecerse para relevamientos, sectores y vínculos. No se borra nada y se puede volver a activar."
TEXTO_ACTIVAR = "El edificio vuelve a ofrecerse para relevamientos, sectores y vínculos, con sus datos, relevamientos y equipo como estaban."
EDIFICIO_INACTIVO = "El edificio está inactivo: reactivalo antes de cambiarlo."


def _trazar(dispositivo, usuario, accion, *, detalle="", edificio_id=None):
    """Traza aditiva del legajo institucional, igual que la de sectores y plazas."""

    TrazaDispositivo.objects.registrar(dispositivo, usuario, accion, detalle=detalle, edificio_id=edificio_id)


def admite_editar_edificio(estado):
    """Un dispositivo cerrado no cambia su edificio: la regla única de `_exigir_alcance` y del botón de la ficha."""

    return estado != Dispositivo.Estado.CERRADO


def _exigir_alcance(dispositivo, usuario):
    # Sumar, editar o soltar un edificio de la institución es del legajo (RN5): con alcance Edificios, no.
    if not puede_editar_legajo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para cambiar el edificio de este dispositivo.")
    if not admite_editar_edificio(dispositivo.estado):
        raise ValidationError({"__all__": DISPOSITIVO_CERRADO})


def _normalizar(texto):
    return " ".join((texto or "").split())


MENSAJE_CODIGO_REPETIDO = "Ya hay un edificio con ese código."


def _exigir_codigo_libre(codigo, *, excepto=None):
    """El `unique` del código dicho como error de campo: un `IntegrityError` aborta la transacción."""

    repetidos = Edificio.objects.filter(codigo=codigo)
    if excepto is not None:
        repetidos = repetidos.exclude(pk=excepto.pk)
    if repetidos.exists():
        raise ValidationError({"codigo": MENSAJE_CODIGO_REPETIDO})


@contextmanager
def _codigo_unico():
    """Un `UNIQUE` del código que gana otra petición entre el chequeo y el guardado, como error de campo.

    `_exigir_codigo_libre` mira antes, pero dos envíos casi simultáneos (el doble clic) pasan
    los dos ese chequeo y el segundo choca contra el `UNIQUE`: sin esto es un `IntegrityError`
    que sale como 500. Se lo traduce al mismo error que da el chequeo; el `atomic` de la función
    que lo usa deshace el alta entera al salir con la excepción.
    """

    try:
        yield
    except IntegrityError:
        raise ValidationError({"codigo": MENSAJE_CODIGO_REPETIDO}) from None


@transaction.atomic
def crear_edificio(*, dispositivo, usuario, codigo, **datos):
    """Da de alta el inmueble y lo vincula a la institución desde la que se lo carga.

    El alta y el vínculo van juntos a propósito: un edificio sin ninguna institución no lo
    ve nadie —ni la sección «Edificios», que filtra por dispositivo, ni el coordinador,
    cuyo alcance sale de los dispositivos— y quedaría huérfano apenas se crea.
    """

    _exigir_alcance(dispositivo, usuario)
    codigo = _normalizar(codigo).upper()
    if not codigo:
        raise ValidationError({"codigo": "El edificio necesita un código."})
    nombre = _normalizar(datos.get("nombre"))
    if not nombre:
        raise ValidationError({"nombre": "El edificio necesita un nombre."})
    _exigir_codigo_libre(codigo)

    with _codigo_unico():
        edificio = Edificio.objects.create(
            codigo=codigo,
            **{campo: _normalizar(datos.get(campo)) for campo in CAMPOS},
            **{campo: datos.get(campo) for campo in COORDENADAS},
        )
    edificio.dispositivos.add(dispositivo)
    _trazar(dispositivo, usuario, "EDIFICIO_CREADO", detalle=f"Edificio {edificio.codigo} · {edificio.nombre}")
    return edificio


@transaction.atomic
def editar_edificio(*, edificio, dispositivo, usuario, codigo, **datos):
    """Corrige los datos del inmueble. La traza queda en el legajo desde el que se editó.

    `dispositivo` no es decorativo: es desde dónde se está editando, y es lo que decide el
    alcance. El edificio no tiene capacidad propia —no es de nadie—, así que quien lo
    cambia tiene que poder editar **alguna** de las instituciones que lo ocupan, y la vista
    le pasa la que está mirando. Si el predio es compartido, el cambio lo ven todas: es un
    dato del inmueble, no del legajo.
    """

    _exigir_alcance(dispositivo, usuario)
    if not edificio.dispositivos.filter(pk=dispositivo.pk).exists():
        # Mismo resultado que un id inexistente: sin esto, probar ids desde una institución
        # propia diría cuáles de los edificios ajenos existen.
        raise PermissionDenied("Ese edificio no es de este dispositivo.")

    codigo = _normalizar(codigo).upper()
    if not codigo:
        raise ValidationError({"codigo": "El edificio necesita un código."})
    nombre = _normalizar(datos.get("nombre"))
    if not nombre:
        raise ValidationError({"nombre": "El edificio necesita un nombre."})
    _exigir_codigo_libre(codigo, excepto=edificio)

    edificio = Edificio.objects.select_for_update().get(pk=edificio.pk)
    if not edificio.activo:
        raise ValidationError({"__all__": EDIFICIO_INACTIVO})
    edificio.codigo = codigo
    for campo in CAMPOS:
        setattr(edificio, campo, _normalizar(datos.get(campo)))
    # El formulario manda siempre las dos: vaciarlas en el mapa borra el punto. Una llamada que no las trae no las toca.
    for campo in COORDENADAS:
        if campo in datos:
            setattr(edificio, campo, datos[campo])
    with _codigo_unico():
        edificio.save(update_fields=["codigo", *CAMPOS, *COORDENADAS, "modificado"])

    _trazar(dispositivo, usuario, "EDIFICIO_EDITADO", detalle=f"Edificio {edificio.codigo} · {edificio.nombre}")
    return edificio


@transaction.atomic
def vincular_edificio(*, edificio, dispositivo, usuario):
    """Declara que la institución ocupa ese inmueble (predio compartido).

    Idempotente: vincular dos veces no cambia nada y no traza de nuevo. El `add()` de un
    M2M ya lo es; la traza no, y repetirla ensuciaría el historial con un evento que no
    pasó.
    """

    _exigir_alcance(dispositivo, usuario)
    if not edificios_vinculables(usuario, dispositivo).filter(pk=edificio.pk).exists():
        if edificio.dispositivos.filter(pk=dispositivo.pk).exists():
            return edificio
        # El ajeno y el inexistente, lo mismo: el alcance ya los excluyó a los dos.
        raise PermissionDenied("Ese edificio no está en tu alcance.")

    # Mismo orden de candados que `desvincular_edificio` y `_bloquear_predio` (institución y después edificio): un
    # edificio que se está inactivando no se vincula, o quedaría una institución con uno inactivo que no puede soltar.
    Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
    if not Edificio.objects.select_for_update().filter(pk=edificio.pk, activo=True).exists():
        raise ValidationError({"__all__": EDIFICIO_INACTIVO})
    dispositivo.edificios.add(edificio)
    _trazar(dispositivo, usuario, "EDIFICIO_VINCULADO", detalle=f"Edificio {edificio.codigo} · {edificio.nombre}")
    return edificio


@transaction.atomic
def desvincular_edificio(*, edificio, dispositivo, usuario):
    """Deshace el vínculo. No borra el edificio ni sus relevamientos: son del inmueble.

    Lo que sí se pierde es que **esta** institución los vea, así que la solapa vuelve a su
    estado vacío. Si el edificio queda sin ninguna institución deja de verse en todas
    partes, pero sigue entero: volver a vincularlo lo repone con su historia. Con un
    relevamiento en curso debe conservar al menos una institución para poder gestionarlo.

    Se bloquea mientras la institución tenga **sectores activos** ubicados en ese edificio
    (Cambio 429): quedarían en un inmueble que ya no ocupa. Los dados de baja no cuentan.
    """

    _exigir_alcance(dispositivo, usuario)
    # Mismo bloqueo del dispositivo que toma el alta y la edición de sectores (`plazas`): sin él, un
    # sector podría crearse en este edificio entre la consulta de abajo y el `remove()`. Va ANTES
    # que el del edificio, en el mismo orden que `plazas` (dispositivo y después la FK al
    # edificio): en el orden inverso InnoDB arma un ciclo y corta una de las dos con 1213.
    Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
    edificio = Edificio.objects.select_for_update().get(pk=edificio.pk)
    if not edificio.dispositivos.filter(pk=dispositivo.pk).exists():
        raise PermissionDenied("Ese edificio no es de este dispositivo.")
    if not edificio.activo:
        raise ValidationError({"__all__": EDIFICIO_INACTIVO})

    sectores_activos = Sector.objects.filter(dispositivo=dispositivo, edificio=edificio, activo=True).count()
    if sectores_activos:
        raise ValidationError(
            {
                "__all__": SECTORES_ACTIVOS_EN_EL_EDIFICIO.format(
                    cuantos=sectores_activos,
                    plural_sector="es" if sectores_activos > 1 else "",
                    plural_activo="s" if sectores_activos > 1 else "",
                )
            }
        )

    # Rige en **toda** institución, lleve stock o no, igual que «Inactivar». Con stock es lo que evita que la
    # entrega quede trabada (recibirla exige un edificio vinculado, `stock._preparar`); sin stock, que se desvincule
    # un edificio al que todavía le llegan kits.
    motivo_entregas = _motivo_entregas_por_recibir(
        EntregaKit.objects.filter(
            dispositivo=dispositivo, edificio=edificio, estado__in=EntregaKit.ESTADOS_ABIERTOS
        ).count()
    )
    if motivo_entregas:
        raise ValidationError({"__all__": _mensaje_de_bloqueo(edificio, [motivo_entregas], accion="desvincular")})

    con_stock = SaldoStock.objects.filter(dispositivo=dispositivo, edificio=edificio, cantidad__gt=0).count()
    if con_stock:
        raise ValidationError({"__all__": STOCK_EN_EL_EDIFICIO.format(cuantos=_plural(con_stock, "insumo", "insumos"))})

    if (
        not edificio.dispositivos.exclude(pk=dispositivo.pk).exists()
        and InspeccionEdificio.objects.filter(edificio=edificio, estado=InspeccionEdificio.Estado.ASIGNADA).exists()
    ):
        raise ValidationError({"__all__": RELEVAMIENTO_EN_CURSO})

    # El Equipo, bajo el mismo bloqueo del dispositivo: `sumar_miembro` y `dar_de_baja` lo toman primero, así
    # que ninguna alta puede meter este edificio en un alcance entre esta lectura y el `remove()` (y si entra
    # antes, ya está en la lectura; si entra después, el edificio ya no está vinculado y se rechaza).
    soltar_edificio_del_equipo(dispositivo, edificio)

    dispositivo.edificios.remove(edificio)
    _trazar(dispositivo, usuario, "EDIFICIO_DESVINCULADO", detalle=f"Edificio {edificio.codigo} · {edificio.nombre}")
    return edificio


# --------------------------------------------------------------------------- #
# Inactivar y reactivar (Cambio 583)
# --------------------------------------------------------------------------- #


def _plural(cuantos, singular, plural):
    return f"{cuantos} {singular if cuantos == 1 else plural}"


def _motivos_de_bloqueo(edificio):
    """``[(que_tiene, que_hacer)]`` de lo que impide inactivar ``edificio``; vacío si nada lo impide.

    Cuatro cosas, de cualquier institución del predio: sectores activos ubicados en el edificio, un relevamiento en
    curso, entregas de kits por recibir hacia él (``EntregaKit.ESTADOS_ABIERTOS``: las mismas que cuenta el
    «N por recibir» de la página del edificio) y stock con saldo mayor que 0 (RN-010-15). El **Equipo no bloquea**: queda asignado y vuelve al reactivar.
    """

    motivos = []
    sectores = Sector.objects.filter(edificio=edificio, activo=True).count()
    if sectores:
        motivos.append(
            (
                _plural(sectores, "sector activo", "sectores activos"),
                "dalo de baja" if sectores == 1 else "dalos de baja",
            )
        )
    if InspeccionEdificio.objects.filter(edificio=edificio, estado=InspeccionEdificio.Estado.ASIGNADA).exists():
        motivos.append(("un relevamiento en curso", "cerrá o cancelá el relevamiento"))
    motivo_entregas = _motivo_entregas_por_recibir(
        EntregaKit.objects.filter(edificio=edificio, estado__in=EntregaKit.ESTADOS_ABIERTOS).count()
    )
    if motivo_entregas:
        motivos.append(motivo_entregas)
    con_stock = SaldoStock.objects.filter(edificio=edificio, cantidad__gt=0).count()
    if con_stock:
        motivos.append(
            (
                f"stock en {_plural(con_stock, 'insumo', 'insumos')}",
                "traspasalo a otro edificio o ajustalo a cero",
            )
        )
    return motivos


def _unir(partes, conjuncion):
    return partes[0] if len(partes) == 1 else f"{', '.join(partes[:-1])} {conjuncion} {partes[-1]}"


def _motivo_entregas_por_recibir(cuantas):
    """El motivo ``(que_tiene, que_hacer)`` de ``cuantas`` entregas de kits por recibir, o ``None`` si no hay.

    Lo comparten «Inactivar» y «Desvincular»: el texto y el criterio de «por recibir» están en un solo lugar.
    """

    if not cuantas:
        return None
    return (
        _plural(cuantas, "entrega de kits por recibir", "entregas de kits por recibir"),
        "recibí la entrega" if cuantas == 1 else "recibí las entregas",
    )


def _mensaje_de_bloqueo(edificio, motivos, accion="inactivar"):
    que_tiene = _unir([tiene for tiene, _hacer in motivos], "y")
    que_hacer = _unir([hacer for _tiene, hacer in motivos], "o")
    return f"No se puede {accion} {edificio.nombre}: tiene {que_tiene}. {que_hacer[0].upper()}{que_hacer[1:]} antes."


def _exigir_admin_del_programa(usuario):
    # El edificio no es de una institución sola: inactivarlo es del administrador del programa Dispositivos.
    if not puede_configurar_dispositivos(usuario):
        raise PermissionDenied("Solo el administrador del programa puede inactivar o reactivar un edificio.")


def _bloquear_predio(edificio):
    """Toma los candados en el orden de `desvincular_edificio` y de `plazas`: las instituciones del predio y después el edificio.

    Las instituciones van por pk ascendente, para que dos operaciones sobre el mismo predio no se crucen. Devuelve
    las instituciones y el edificio ya bloqueado.
    """

    vinculos = Edificio.dispositivos.through.objects.filter(edificio_id=edificio.pk).values("dispositivo_id")
    dispositivos = list(Dispositivo.objects.select_for_update().filter(pk__in=vinculos).order_by("pk"))
    return dispositivos, Edificio.objects.select_for_update().get(pk=edificio.pk)


@transaction.atomic
def inactivar_edificio(*, edificio, usuario):
    """Saca el inmueble de circulación: deja de ofrecerse para relevamientos, sectores y vínculos. No borra nada.

    Solo el administrador del programa. Se rechaza si hay sectores activos, un relevamiento en curso o entregas de
    kits por recibir (el mensaje junta lo que haya). El Equipo asignado al edificio no cuenta: queda como está y
    vuelve tal cual al reactivar. La traza queda en **cada** institución vinculada.
    """

    _exigir_admin_del_programa(usuario)
    dispositivos, edificio = _bloquear_predio(edificio)
    if not edificio.activo:
        raise ValidationError({"__all__": f"{edificio.nombre} ya está inactivo."})
    motivos = _motivos_de_bloqueo(edificio)
    if motivos:
        raise ValidationError({"__all__": _mensaje_de_bloqueo(edificio, motivos)})

    edificio.activo = False
    edificio.save(update_fields=["activo", "modificado"])
    for dispositivo in dispositivos:
        _trazar(
            dispositivo,
            usuario,
            "EDIFICIO_INACTIVADO",
            detalle=f"Edificio {edificio.codigo} · {edificio.nombre}",
            edificio_id=edificio.pk,
        )
    return edificio


@transaction.atomic
def reactivar_edificio(*, edificio, usuario):
    """Vuelve a poner el inmueble en circulación, con sus vínculos, relevamientos y Equipo como estaban."""

    _exigir_admin_del_programa(usuario)
    dispositivos, edificio = _bloquear_predio(edificio)
    if edificio.activo:
        raise ValidationError({"__all__": f"{edificio.nombre} ya está activo."})

    edificio.activo = True
    edificio.save(update_fields=["activo", "modificado"])
    for dispositivo in dispositivos:
        _trazar(
            dispositivo,
            usuario,
            "EDIFICIO_REACTIVADO",
            detalle=f"Edificio {edificio.codigo} · {edificio.nombre}",
            edificio_id=edificio.pk,
        )
    return edificio
