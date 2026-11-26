"""La tabla de cantidades que comparten las pantallas de kits y de stock: un campo ``cantidad_<id>`` por insumo.

Está acá y no copiada en cada formulario porque la copia es la que pierde la guarda: ``claves_sin_campo`` es lo que
impide que una cantidad cargada de un insumo que **ya no tiene fila** se descarte en silencio y la operación salga
distinta de lo que mostraba la pantalla.
"""

from django import forms

from programas.forms import INPUT_CLASS
from programas.services.kits import CANTIDAD_MAXIMA

#: Prefijo de los campos de cantidad: ``cantidad_<id del insumo>``.
PREFIJO_CANTIDAD = "cantidad_"


def numero(minimo):
    return forms.NumberInput(attrs={"class": INPUT_CLASS, "min": minimo, "inputmode": "numeric"})


def campo_de(item_id):
    return f"{PREFIJO_CANTIDAD}{item_id}"


def campo_de_cantidad(item, *, minimo, mensaje):
    """El campo de cantidad de ``item``: vacío es «de este no va»; ``mensaje`` es el error de número inválido."""

    return forms.IntegerField(
        label=item.nombre,
        required=False,
        min_value=minimo,
        max_value=CANTIDAD_MAXIMA,
        help_text=f"En {item.unidad}.",
        error_messages={"invalid": mensaje, "min_value": mensaje, "max_value": mensaje},
        widget=numero(minimo),
    )


def ids_con_cantidad(datos):
    """Los ids de insumo que llegan con algo escrito en ``cantidad_<id>`` (``datos`` es el ``data`` del formulario)."""

    ids = []
    for clave, valor in datos.items():
        if clave.startswith(PREFIJO_CANTIDAD) and str(valor).strip():
            resto = clave[len(PREFIJO_CANTIDAD) :]
            # `isdigit` deja pasar «²» y `int()` lo rechaza: solo dígitos ASCII, para que un POST armado a mano no dé 500.
            if resto.isascii() and resto.isdecimal():
                ids.append(int(resto))
    return ids


def claves_sin_campo(datos, campos):
    """Las claves ``cantidad_*`` con valor que **no** tienen campo: un insumo que se fue mientras la pantalla estaba abierta."""

    return [
        clave
        for clave, valor in datos.items()
        if clave.startswith(PREFIJO_CANTIDAD) and clave not in campos and str(valor).strip()
    ]
