"""Identificación de la persona en cascada (Cambio 57).

Antes la identidad salía solo de Base de Personas del Chaco («Gran Base»). Con
la fuente caída todo entraba sin validar y nada se podía aprobar. Ahora el
orden es **padrón de la convocatoria → Base de Personas (si está activa) →
manual**, el mismo para el link público y para la app de campo, y siempre en
el servidor.

El padrón se consulta **primero, siempre**: no es un plan B que se activa
cuando la Gran Base se cae. Si la persona figura con nombre y apellido queda
validada por padrón y la Gran Base solo suma: la confirma y, si difiere,
manda ella (RN-6). ``PERSONAS_API_ACTIVA=false`` no cambia el resultado de
quien está en el padrón; le saca la espera del timeout a una API que no
responde y evita el error en el log.

«Fallecido» solo puede venir de la Gran Base (RN-9): el padrón no lo sabe.
"""

from __future__ import annotations

from django.conf import settings

from programas.services.padron import datos_de_fila, fila_padron, normalizar_dni, normalizar_sexo
from programas.services.personas import consultar_persona

ORIGEN_PADRON = "padron"
ORIGEN_PERSONAS = "personas"
ORIGEN_MANUAL = "manual"

_CAMPOS_COMPARADOS = ("nombre", "apellido", "fecha_nacimiento")


def gran_base_activa():
    """¿Se consulta Base de Personas? Apagada por configuración cuando el
    servicio no responde (``PERSONAS_API_ACTIVA``)."""
    return bool(getattr(settings, "PERSONAS_API_ACTIVA", True))


def identificar(convocatoria, dni, sexo):
    """Resuelve la identidad de ``dni`` + ``sexo`` para ``convocatoria``.

    Devuelve un dict con:

    - ``origen``: ``"padron"`` | ``"personas"`` | ``"manual"``.
    - ``validado``: True si hay nombre y apellido de una fuente confiable.
    - ``datos``: ``{nombre, apellido, fecha_nacimiento (ISO), localidad_id,
      localidad_texto}`` o ``None``.
    - ``fallecido``: True si la Gran Base informó fallecimiento (corta el flujo).
    - ``error``: mensaje de la Gran Base cuando no pudo responder.
    - ``diferencias``: ``{campo: (padron, gran_base)}`` cuando ambas fuentes
      tenían datos y no coinciden (para la traza).

    ``convocatoria`` puede ser ``None`` (consulta sin padrón: solo Gran Base).
    """
    dni, sexo = normalizar_dni(dni), normalizar_sexo(sexo)
    resultado = {
        "origen": ORIGEN_MANUAL,
        "validado": False,
        "datos": None,
        "fallecido": False,
        "error": "",
        # True cuando la Gran Base respondió bien pero el DNI no está en la
        # fuente: no es una falla del servicio, es una persona que no figura.
        "no_encontrado": False,
        "diferencias": {},
    }
    if not dni or not sexo:
        return resultado

    if convocatoria is not None:
        fila = fila_padron(convocatoria, dni, sexo)
        if fila is not None and fila.tiene_identidad:
            resultado.update(origen=ORIGEN_PADRON, validado=True, datos=datos_de_fila(fila))

    if not gran_base_activa():
        return resultado

    respuesta = consultar_persona(dni, sexo)
    if respuesta.get("fallecido"):
        resultado["fallecido"] = True
        return resultado
    if not respuesta.get("success"):
        # Con padrón, la persona ya quedó validada: el error solo se informa.
        resultado["error"] = respuesta.get("error") or ""
        resultado["no_encontrado"] = bool(respuesta.get("not_found"))
        return resultado

    datos = respuesta.get("data") or {}
    if not (datos.get("nombre") and datos.get("apellido")):
        return resultado

    oficiales = {
        "nombre": datos.get("nombre") or "",
        "apellido": datos.get("apellido") or "",
        "fecha_nacimiento": datos.get("fecha_nacimiento") or "",
        "localidad_id": None,
        "localidad_texto": "",
    }
    if resultado["datos"]:
        del_padron = resultado["datos"]
        resultado["diferencias"] = {
            campo: (del_padron.get(campo) or "", oficiales[campo])
            for campo in _CAMPOS_COMPARADOS
            if oficiales[campo] and str(del_padron.get(campo) or "") != str(oficiales[campo])
        }
        # La Gran Base no trae localidad: se conserva la del padrón.
        oficiales["localidad_id"] = del_padron.get("localidad_id")
        oficiales["localidad_texto"] = del_padron.get("localidad_texto") or ""
        if not oficiales["fecha_nacimiento"]:
            oficiales["fecha_nacimiento"] = del_padron.get("fecha_nacimiento") or ""
    resultado.update(origen=ORIGEN_PERSONAS, validado=True, datos=oficiales)
    return resultado
