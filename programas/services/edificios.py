"""Alta, edición y vinculación del **edificio** de una institución (MVP v2, carril C5 · P19).

`Edificio` existía desde la etapa 1 y lo leían la solapa Infraestructura, el semáforo
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

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from programas.models import Dispositivo, Edificio, TrazaDispositivo
from programas.services.dispositivos import puede_operar_dispositivo
from programas.services.inspecciones import edificios_en_alcance

#: La misma capacidad con la que se edita el legajo: el edificio es dato del legajo.
CAP_EDITAR = "dispositivo.editar"

#: Campos que el MVP carga del edificio: identidad y domicilio normalizado. Tenencia,
#: servicios, estado físico y plano son de la Versión 2 completa y no están ni en el
#: modelo. Las **coordenadas** sí están en el modelo y el MVP igual no las pide: la task 37
#: las dejó fuera de la solapa Infraestructura junto con el mapa (C-14), y
#: `FueraDelMvpTests` lo exige. Un campo que no se puede ver después es un campo que nadie
#: corrige.
CAMPOS = (
    "nombre",
    "calle",
    "numero",
    "piso_departamento",
    "localidad",
    "provincia",
    "codigo_postal",
)

DISPOSITIVO_CERRADO = "El dispositivo está cerrado: no se puede cambiar su edificio."


def _trazar(dispositivo, usuario, accion, *, detalle=""):
    """Traza aditiva del legajo institucional, igual que la de sectores y plazas."""

    TrazaDispositivo.objects.create(dispositivo=dispositivo, usuario=usuario, accion=accion, detalle=detalle)


def _exigir_alcance(dispositivo, usuario):
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR):
        raise PermissionDenied("No tenés alcance para cambiar el edificio de este dispositivo.")
    if dispositivo.estado == Dispositivo.Estado.CERRADO:
        raise ValidationError({"__all__": DISPOSITIVO_CERRADO})


def _normalizar(texto):
    return " ".join((texto or "").split())


def edificios_vinculables(usuario, dispositivo):
    """Los edificios que el usuario puede vincular a este dispositivo: los de su alcance, menos los ya vinculados."""

    return edificios_en_alcance(usuario, CAP_EDITAR).exclude(dispositivos=dispositivo).order_by("nombre", "pk")


def edificios_del_dispositivo(dispositivo):
    """Los edificios que ocupa la institución. La misma lectura que usa la solapa Infraestructura."""

    return Edificio.objects.filter(dispositivos=dispositivo).order_by("nombre", "pk")


def _exigir_codigo_libre(codigo, *, excepto=None):
    """El `unique` del código dicho como error de campo: un `IntegrityError` aborta la transacción."""

    repetidos = Edificio.objects.filter(codigo=codigo)
    if excepto is not None:
        repetidos = repetidos.exclude(pk=excepto.pk)
    if repetidos.exists():
        raise ValidationError({"codigo": "Ya hay un edificio con ese código."})


@transaction.atomic
def crear_edificio(*, dispositivo, usuario, codigo, **datos):
    """Da de alta el inmueble y lo vincula a la institución desde la que se lo carga.

    El alta y el vínculo van juntos a propósito: un edificio sin ninguna institución no lo
    ve nadie —ni la solapa Infraestructura, que filtra por dispositivo, ni el coordinador,
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

    edificio = Edificio.objects.create(
        codigo=codigo,
        **{campo: _normalizar(datos.get(campo)) for campo in CAMPOS},
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
    edificio.codigo = codigo
    for campo in CAMPOS:
        setattr(edificio, campo, _normalizar(datos.get(campo)))
    edificio.save(update_fields=["codigo", *CAMPOS, "modificado"])

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

    dispositivo.edificios.add(edificio)
    _trazar(dispositivo, usuario, "EDIFICIO_VINCULADO", detalle=f"Edificio {edificio.codigo} · {edificio.nombre}")
    return edificio


@transaction.atomic
def desvincular_edificio(*, edificio, dispositivo, usuario):
    """Deshace el vínculo. No borra el edificio ni sus relevamientos: son del inmueble.

    Lo que sí se pierde es que **esta** institución los vea, así que la solapa vuelve a su
    estado vacío. Si el edificio queda sin ninguna institución deja de verse en todas
    partes, pero sigue entero: volver a vincularlo lo repone con su historia.
    """

    _exigir_alcance(dispositivo, usuario)
    if not edificio.dispositivos.filter(pk=dispositivo.pk).exists():
        raise PermissionDenied("Ese edificio no es de este dispositivo.")

    dispositivo.edificios.remove(edificio)
    _trazar(dispositivo, usuario, "EDIFICIO_DESVINCULADO", detalle=f"Edificio {edificio.codigo} · {edificio.nombre}")
    return edificio
