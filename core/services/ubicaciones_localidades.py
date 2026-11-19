"""Carga de centroides de localidades (``core.UbicacionLocalidad``) desde el CSV de BAHRA/Georef.

La conciliación es por **nombre y municipio normalizados**: el catálogo ``core.Localidad``
del Chaco repite 63 nombres entre municipios («La Esperanza», «Lote 5»…), así que el
nombre solo no identifica un lugar. Cada localidad del catálogo queda en uno de tres
estados:

- **conciliada**: exactamente una fila del CSV tiene su nombre y su municipio. Recibe punto.
- **ambigua**: el nombre está en el CSV pero no se puede decir cuál es el suyo (más de una
  fila con el mismo nombre y municipio, o el nombre solo aparece en otro municipio). No se
  asigna a ciegas: queda sin punto y en el reporte, con los candidatos.
- **no conciliada**: el nombre no está en el CSV. Queda sin punto y en el reporte
  (pregunta 9 del análisis 009).
"""

import csv
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.db import transaction

from core.models import UbicacionLocalidad

RUTA_CSV = Path(__file__).resolve().parents[1] / "data" / "localidades_chaco_georef.csv"
COLUMNAS = ("id_fuente", "nombre", "municipio", "departamento", "latitud", "longitud")
CAMPOS_ACTUALIZABLES = ("latitud", "longitud", "departamento", "fuente", "id_fuente")


def clave(texto):
    """Nombre comparable: sin acentos ni eñe, minúsculas, sin signos, un solo espacio."""
    t = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join("".join(c if c.isalnum() else " " for c in t).split())


@dataclass(frozen=True)
class FilaFuente:
    id_fuente: str
    nombre: str
    municipio: str
    departamento: str
    latitud: Decimal
    longitud: Decimal


@dataclass
class Conciliacion:
    asignadas: list = field(default_factory=list)  # [(localidad, FilaFuente)]
    ambiguas: list = field(default_factory=list)  # [(localidad, [FilaFuente, ...])]
    no_conciliadas: list = field(default_factory=list)  # [localidad]


@dataclass
class ResultadoCarga:
    conciliacion: Conciliacion
    creadas: int = 0
    actualizadas: int = 0
    sin_cambios: int = 0


def _coordenada(valor, minimo, maximo, numero_linea, columna):
    try:
        numero = Decimal(str(valor).strip()).quantize(Decimal("0.000001"))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Línea {numero_linea}: {columna} «{valor}» no es un número.") from None
    if not minimo <= numero <= maximo:
        raise ValueError(f"Línea {numero_linea}: {columna} {numero} fuera de rango.")
    return numero


def leer_csv(ruta=RUTA_CSV):
    """Filas del CSV versionado, salteando el encabezado de comentarios (``#``)."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"Falta el archivo de datos {ruta}.")
    with ruta.open(encoding="utf-8", newline="") as archivo:
        lineas = [linea for linea in archivo if not linea.lstrip().startswith("#")]
    lector = csv.DictReader(lineas)
    faltan = [c for c in COLUMNAS if c not in (lector.fieldnames or [])]
    if faltan:
        raise ValueError(f"Al CSV le faltan las columnas: {', '.join(faltan)}.")
    filas = []
    for numero, fila in enumerate(lector, start=2):
        if not (fila["id_fuente"] or "").strip() or not (fila["nombre"] or "").strip():
            raise ValueError(f"Línea {numero}: id_fuente y nombre son obligatorios.")
        filas.append(
            FilaFuente(
                id_fuente=fila["id_fuente"].strip(),
                nombre=fila["nombre"].strip(),
                municipio=(fila["municipio"] or "").strip(),
                departamento=(fila["departamento"] or "").strip(),
                latitud=_coordenada(fila["latitud"], -90, 90, numero, "latitud"),
                longitud=_coordenada(fila["longitud"], -180, 180, numero, "longitud"),
            )
        )
    return filas


def conciliar(localidades, filas):
    """Clasifica cada localidad del catálogo. Función pura: no consulta la base.

    ``localidades`` son objetos con ``nombre`` y ``municipio`` (con ``nombre``).
    """
    por_nombre_y_municipio = defaultdict(list)
    por_nombre = defaultdict(list)
    for fila in filas:
        por_nombre_y_municipio[(clave(fila.nombre), clave(fila.municipio))].append(fila)
        por_nombre[clave(fila.nombre)].append(fila)

    resultado = Conciliacion()
    for localidad in localidades:
        nombre = clave(localidad.nombre)
        municipio = clave(localidad.municipio.nombre if localidad.municipio else "")
        candidatas = por_nombre_y_municipio.get((nombre, municipio), [])
        if len(candidatas) == 1:
            resultado.asignadas.append((localidad, candidatas[0]))
        elif candidatas:
            resultado.ambiguas.append((localidad, candidatas))
        elif por_nombre.get(nombre):
            resultado.ambiguas.append((localidad, por_nombre[nombre]))
        else:
            resultado.no_conciliadas.append(localidad)
    return resultado


def _valores(fila, fuente):
    return {
        "latitud": fila.latitud,
        "longitud": fila.longitud,
        "departamento": fila.departamento,
        "fuente": fuente,
        "id_fuente": fila.id_fuente,
    }


@transaction.atomic
def cargar_ubicaciones(localidades, filas, fuente=UbicacionLocalidad.FUENTE_BAHRA_GEOREF):
    """Crea o actualiza una ``UbicacionLocalidad`` por localidad conciliada. Idempotente.

    No borra nada: una localidad que deja de conciliar conserva la fila que tuviera.
    """
    conciliacion = conciliar(localidades, filas)
    resultado = ResultadoCarga(conciliacion=conciliacion)
    existentes = {
        u.localidad_id: u
        for u in UbicacionLocalidad.objects.filter(localidad__in=[loc for loc, _ in conciliacion.asignadas])
    }
    nuevas = []
    for localidad, fila in conciliacion.asignadas:
        valores = _valores(fila, fuente)
        actual = existentes.get(localidad.pk)
        if actual is None:
            nuevas.append(UbicacionLocalidad(localidad=localidad, **valores))
        elif any(getattr(actual, campo) != valor for campo, valor in valores.items()):
            for campo, valor in valores.items():
                setattr(actual, campo, valor)
            actual.save(update_fields=[*CAMPOS_ACTUALIZABLES, "modificado"])
            resultado.actualizadas += 1
        else:
            resultado.sin_cambios += 1
    UbicacionLocalidad.objects.bulk_create(nuevas)
    resultado.creadas = len(nuevas)
    return resultado
