"""El campo «Firma» de los formularios del constructor (Cambio 480).

Una firma son dos cosas que viajan por caminos distintos, como ya viajan los archivos:

* **La imagen del trazo**, un PNG que se sube y se guarda en la misma tabla de adjuntos que un
  campo ``ARCHIVO`` de esa pantalla (``TipoCampo.con_adjunto``). Se reemplaza mientras el caso
  no esté resuelto, igual que un archivo.
* **Quién firmó**, en la respuesta del campo: ``{"nombre", "dni", "firmado"}``. El nombre y el
  DNI los carga quien firma; la fecha la pone **el servidor** al recibirla, nunca el cliente.

Es una firma *electrónica* (la imagen de un trazo con los datos de quien dice haberlo hecho), no
una firma *digital* con certificado: sirve como constancia, no prueba autoría por sí sola.
"""

from datetime import datetime
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils import timezone

from core.dni import dni_valido, normalizar_dni
from core.validators import validar_firma

#: La imagen del trazo: PNG y chica. Un canvas de 600x200 en blanco y negro pesa unos KB.
FIRMA_EXTENSION = ".png"
FIRMA_MAX_BYTES = 1024 * 1024

MENSAJE_FIRMA_FORMATO = "La firma tiene que llegar como imagen PNG."
MENSAJE_FIRMA_TAMANIO = "La imagen de la firma no puede superar 1 MB."
MENSAJE_SIN_NOMBRE = "Escribí el nombre y apellido de quien firma."
MENSAJE_DNI = "El DNI de quien firma tiene que tener 7 u 8 números."
MENSAJE_SIN_TRAZO = "Falta la firma: firmá en el recuadro."

_LARGO_NOMBRE = 120


def validar_imagen_de_firma(archivo):
    """Extensión, tamaño y contenido del PNG de la firma (lo que se está subiendo)."""

    if archivo is None or getattr(archivo, "_committed", False):
        return archivo
    nombre = (getattr(archivo, "name", "") or "").lower()
    if Path(nombre).suffix != FIRMA_EXTENSION:
        raise ValidationError(MENSAJE_FIRMA_FORMATO)
    if (archivo.size or 0) > FIRMA_MAX_BYTES:
        raise ValidationError(MENSAJE_FIRMA_TAMANIO)
    validar_firma(archivo, FIRMA_EXTENSION, MENSAJE_FIRMA_FORMATO)
    return archivo


def errores_del_firmante(valor):
    """Los problemas de ``{"nombre", "dni"}`` como textos para el usuario; lista vacía si está bien."""

    if not isinstance(valor, dict):
        return [MENSAJE_SIN_NOMBRE, MENSAJE_DNI]
    errores = []
    nombre = " ".join(str(valor.get("nombre") or "").split())
    if not nombre or len(nombre) > _LARGO_NOMBRE:
        errores.append(MENSAJE_SIN_NOMBRE)
    if not dni_valido(valor.get("dni")):
        errores.append(MENSAJE_DNI)
    return errores


def _solo_digitos(dni):
    # Se aceptan puntos y espacios («30.111.222»): se guarda solo el número (la regla única de `core.dni`).
    return normalizar_dni(dni)


def normalizar_firmante(valor, *, momento=None, anterior=None):
    """``{"nombre", "dni", "firmado"}`` limpio, o ``ValidationError`` con los textos de :func:`errores_del_firmante`.

    ``firmado`` lo pone el servidor. Si quien firmó es el mismo que ya estaba guardado
    (``anterior``) y no llegó una imagen nueva, se conserva la fecha original: volver a guardar
    un borrador no «re-firma».
    """

    errores = errores_del_firmante(valor)
    if errores:
        raise ValidationError(errores)
    limpio = {"nombre": " ".join(str(valor["nombre"]).split()), "dni": _solo_digitos(valor["dni"])}
    if isinstance(anterior, dict) and anterior.get("firmado") and _mismo_firmante(anterior, limpio):
        limpio["firmado"] = anterior["firmado"]
    else:
        limpio["firmado"] = (momento or timezone.now()).isoformat()
    return limpio


def _mismo_firmante(a, b):
    return str(a.get("nombre")) == b["nombre"] and _solo_digitos(a.get("dni")) == b["dni"]


def es_firmante(valor):
    """¿El valor guardado de un campo FIRMA tiene la forma de un firmante?"""

    return isinstance(valor, dict) and bool(valor.get("nombre")) and bool(valor.get("dni"))


def texto_del_firmante(valor):
    """«Ana Gómez · DNI 30111222 · 17/11/2026 15:20» para mostrar debajo de la imagen."""

    if not es_firmante(valor):
        return ""
    partes = [str(valor["nombre"]), f"DNI {valor['dni']}"]
    firmado = valor.get("firmado")
    if firmado:
        try:
            momento = timezone.localtime(datetime.fromisoformat(firmado))
            partes.append(momento.strftime("%d/%m/%Y %H:%M"))
        except (TypeError, ValueError):
            pass
    return " · ".join(partes)
