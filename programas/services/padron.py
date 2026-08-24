"""Padrón de habilitados por Excel para relevamientos públicos (RN-P14, #299).

El operador sube un .xlsx de dos columnas —documento y sexo— al configurar el
relevamiento público (o lo reemplaza desde el detalle). Acá viven el parser,
la carga (reemplazo total, transaccional) y el chequeo ``esta_habilitado`` que
consume el paso 1 del link **antes** de consultar RENAPER/Gran Base.

Normalización en ambos sentidos: el DNI se reduce a dígitos y el sexo a F/M
(acepta "f", "Femenino", "MASCULINO", etc.), tanto al cargar el Excel como al
chequear lo tipeado en el paso 1.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction

from programas.models import PadronHabilitado

# Tamaño máximo del Excel (los padrones reales son de cientos de filas).
PADRON_MAX_BYTES = 2 * 1024 * 1024

_SEXOS = {
    "F": "F",
    "FEMENINO": "F",
    "MUJER": "F",
    "M": "M",
    "MASCULINO": "M",
    "HOMBRE": "M",
    "VARON": "M",
    "VARÓN": "M",
}

_ENCABEZADOS_DNI = {"DOCUMENTO", "DNI", "NRO DOCUMENTO", "NUMERO DE DOCUMENTO", "NÚMERO DE DOCUMENTO"}


def normalizar_dni(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def normalizar_sexo(valor):
    return _SEXOS.get(str(valor or "").strip().upper(), "")


def parsear_padron(archivo):
    """Lee el Excel y devuelve ``(entradas, rechazadas)``.

    ``entradas``: lista de ``(dni, sexo)`` normalizados y sin duplicados (gana
    la primera aparición de cada DNI). ``rechazadas``: cantidad de filas con
    datos que no se pudieron interpretar (se informan, no rompen la carga).

    Levanta ``ValidationError`` si el archivo no es un .xlsx legible, pesa de
    más o no aporta ninguna fila válida.
    """
    nombre = getattr(archivo, "name", "") or ""
    if not nombre.lower().endswith(".xlsx"):
        raise ValidationError("El padrón debe ser un archivo Excel (.xlsx) de dos columnas: documento y sexo.")
    if getattr(archivo, "size", 0) > PADRON_MAX_BYTES:
        raise ValidationError("El padrón no puede superar los 2 MB.")

    from openpyxl import load_workbook

    try:
        libro = load_workbook(archivo, read_only=True, data_only=True)
    except Exception as exc:  # openpyxl levanta variantes según el archivo
        raise ValidationError("No se pudo leer el archivo: no es un Excel .xlsx válido.") from exc

    try:
        hoja = libro.active
        entradas = []
        vistos = set()
        rechazadas = 0
        for indice, fila in enumerate(hoja.iter_rows(min_col=1, max_col=2, values_only=True)):
            crudo_dni, crudo_sexo = (fila + (None, None))[:2]
            dni = normalizar_dni(crudo_dni)
            sexo = normalizar_sexo(crudo_sexo)
            if not dni and not str(crudo_dni or "").strip() and not str(crudo_sexo or "").strip():
                continue  # fila totalmente vacía
            if indice == 0 and not dni and str(crudo_dni or "").strip().upper() in _ENCABEZADOS_DNI:
                continue  # fila de encabezado
            if not dni or not sexo:
                rechazadas += 1
                continue
            if dni in vistos:
                rechazadas += 1
                continue
            vistos.add(dni)
            entradas.append((dni, sexo))
    finally:
        libro.close()

    if not entradas:
        raise ValidationError(
            "El padrón no tiene filas válidas. Se espera un .xlsx con dos columnas: documento y sexo (F/M)."
        )
    return entradas, rechazadas


@transaction.atomic
def cargar_padron(relevamiento, archivo, entradas):
    """Reemplaza el padrón del relevamiento por ``entradas`` (reemplazo total,
    no merge) y guarda el Excel original para trazabilidad. Devuelve la
    cantidad de habilitados cargados."""
    relevamiento.padron.all().delete()
    PadronHabilitado.objects.bulk_create(
        PadronHabilitado(relevamiento=relevamiento, dni=dni, sexo=sexo) for dni, sexo in entradas
    )
    if archivo is not None:
        # El parser ya consumió el stream: rebobinar antes de persistirlo.
        if hasattr(archivo, "seek"):
            archivo.seek(0)
        relevamiento.padron_archivo = archivo
        relevamiento.save(update_fields=["padron_archivo", "modificado"])
    return len(entradas)


def esta_habilitado(relevamiento, dni, sexo):
    """¿DNI+sexo pueden inscribirse? Sin padrón el link es abierto (RN-P14)."""
    if not relevamiento.padron.exists():
        return True
    return relevamiento.padron.filter(dni=normalizar_dni(dni), sexo=normalizar_sexo(sexo)).exists()
