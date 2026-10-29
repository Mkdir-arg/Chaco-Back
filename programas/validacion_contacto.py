"""Validación de los datos de contacto del responsable (DNI/CUIT, teléfono, nombre).

Los forms de la solicitud de merendero y del legajo de dispositivo guardaban lo que
llegara (`3e1312321` pasó como DNI/CUIT). Cada función recibe el texto crudo y
devuelve el valor normalizado, o levanta `ValidationError`. Son puras: el form decide
cuándo llamarlas (un campo vacío no se valida: si era requerido ya lo marcó Django y
si no, es un borrador).

Vive aparte de `programas/validadores.py` porque ese módulo lo importa
`programas.models` y este importa `siis_envio`, que importa los modelos.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError

from core.dni import dni_valido, normalizar_dni
from programas.services.siis_envio import cuil_valido

AYUDA_DOCUMENTO_RESPONSABLE = "DNI de 7 u 8 dígitos o CUIT de 11"
MENSAJE_DOCUMENTO_INVALIDO = "Ingresá un DNI de 7 u 8 dígitos o un CUIT de 11."
MENSAJE_CUIT_INVALIDO = "El CUIT no es válido: revisá el dígito verificador."
MENSAJE_TELEFONO_INVALIDO = "Ingresá un teléfono de 8 a 15 dígitos."
MENSAJE_NOMBRE_INVALIDO = "El nombre tiene que tener al menos una letra."

LARGO_CUIT = 11
LARGOS_TELEFONO = (8, 15)

# Lo único que se tolera entre los dígitos de un documento.
_SEPARADORES_DOCUMENTO = re.compile(r"[.\-\s]")
_TELEFONO_PERMITIDO = re.compile(r"[0-9\s+\-()]+")


def normalizar_documento_responsable(valor):
    """DNI (7-8 dígitos) o CUIT (11) del responsable, solo con dígitos."""
    texto = _SEPARADORES_DOCUMENTO.sub("", str(valor or ""))
    if not (texto.isascii() and texto.isdigit()):
        raise ValidationError(MENSAJE_DOCUMENTO_INVALIDO)
    digitos = normalizar_dni(texto)
    if len(digitos) == LARGO_CUIT:
        if not cuil_valido(digitos):
            raise ValidationError(MENSAJE_CUIT_INVALIDO)
        return digitos
    # La regla de largo del DNI es la de core/dni.py (RED-48); cualquier otro largo
    # cae acá y recibe el mismo mensaje.
    if not dni_valido(digitos):
        raise ValidationError(MENSAJE_DOCUMENTO_INVALIDO)
    return digitos


def normalizar_telefono(valor):
    """Teléfono con solo dígitos, conservando un ``+`` inicial si lo tenía."""
    texto = str(valor or "").strip()
    if not _TELEFONO_PERMITIDO.fullmatch(texto):
        raise ValidationError(MENSAJE_TELEFONO_INVALIDO)
    digitos = "".join(ch for ch in texto if ch.isascii() and ch.isdigit())
    if not LARGOS_TELEFONO[0] <= len(digitos) <= LARGOS_TELEFONO[1]:
        raise ValidationError(MENSAJE_TELEFONO_INVALIDO)
    return ("+" if texto.startswith("+") else "") + digitos


def validar_nombre_responsable(valor):
    """El nombre tal cual vino, si tiene al menos una letra."""
    texto = str(valor or "").strip()
    if not any(ch.isalpha() for ch in texto):
        raise ValidationError(MENSAJE_NOMBRE_INVALIDO)
    return texto
