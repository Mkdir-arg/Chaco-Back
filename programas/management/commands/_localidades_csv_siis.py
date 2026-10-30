"""El CSV de localidades que no cruzan el catálogo de SIIS, en las dos direcciones.

Ida: ``corregir_datos_siis --exportar-sin-cruce`` arma una fila por caso para que el
organismo complete ``localidad_siis``. Vuelta: ``--cargar-localidades`` lee el archivo
completado y arma el *plan* de lo que va a la tabla ``localidades_corregidas``.

Acá viven las piezas sin efectos (armar la fila, leer el archivo, decidir qué se carga);
el comando conserva la orquestación: el log, la transacción y el INSERT/UPDATE.

El guión bajo del nombre no es decorativo: Django no lo toma como un comando
(``find_commands`` saltea lo que empieza con ``_``).
"""

import collections
import csv
from dataclasses import dataclass, field

from django.core.management.base import CommandError
from django.db.models import Count

from core.exportacion import celda_segura
from programas.models import AliasLocalidadSiis, LocalidadSiis
from programas.services.padron import normalizar_dni
from programas.services.siis_envio import clave_nombre

#: Columnas del CSV que se le pasa al organismo. ``localidad_siis`` sale vacía.
COLUMNAS_SIN_CRUCE = (
    "caso_pk",
    "caso_numero",
    "relevamiento_id",
    "dni",
    "localidad_declarada",
    "provincia_declarada",
    "texto_planilla",
    "motivo",
    "localidad_siis",
)


def _limpio(texto):
    return " ".join(str(texto or "").split())


# ── Ida: la exportación ─────────────────────────────────────────────────────


def fila_sin_cruce(caso, dni, respuestas, texto_planilla, motivo):
    """La fila del CSV para un caso (una por caso, no por DNI ni por texto)."""
    return {
        "caso_pk": caso.pk,
        "caso_numero": caso.numero,
        "relevamiento_id": caso.relevamiento_id,
        "dni": dni,
        # Texto libre del ciudadano: una celda «=HYPERLINK(...)» se ejecutaría en Excel (RED-70).
        "localidad_declarada": celda_segura(_limpio(respuestas.get("loc_actual", ""))),
        "provincia_declarada": celda_segura(_limpio(respuestas.get("prov_actual", ""))),
        "texto_planilla": celda_segura(texto_planilla),
        "motivo": motivo,
        "localidad_siis": "",
    }


def ordenar_sin_cruce(filas):
    """Por localidad declarada, para que el cliente vea juntos los que se parecen."""
    return sorted(filas, key=lambda f: (f["localidad_declarada"].lower(), f["texto_planilla"].lower(), f["caso_pk"]))


def escribir_sin_cruce(filas, salida):
    """Encabezado y filas en ``salida``, un objeto con ``write`` (archivo o stdout)."""
    escritor = csv.DictWriter(salida, fieldnames=COLUMNAS_SIN_CRUCE, lineterminator="\n")
    escritor.writeheader()
    escritor.writerows(filas)


# ── Vuelta: la lectura y el plan de carga ───────────────────────────────────


def leer_csv_completado(ruta):
    """Las filas del CSV que devolvió el cliente, venga de Excel en es-AR o no.

    Excel en español guarda con ``;`` y, según «Guardar como», en cp1252 y no
    en UTF-8: el separador se detecta en la primera línea y, si el archivo no
    es UTF-8, se reintenta en cp1252.
    """
    try:
        with open(ruta, "rb") as archivo:
            crudo = archivo.read()
    except OSError as exc:
        raise CommandError(f"No se pudo leer {ruta}: {exc}") from exc
    try:
        texto = crudo.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            texto = crudo.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise CommandError(
                f"No se pudo leer {ruta}: ni UTF-8 ni Windows-1252. En Excel, Guardar como «CSV UTF-8 "
                "(delimitado por comas)» y volver a cargarlo."
            ) from exc
    primera = texto.splitlines()[0] if texto.strip() else ""
    try:
        delimitador = csv.Sniffer().sniff(primera, delimiters=",;").delimiter
    except csv.Error:
        delimitador = ","
    filas = list(csv.DictReader(texto.splitlines(), delimiter=delimitador))
    if not filas or "dni" not in filas[0] or "localidad_siis" not in filas[0]:
        raise CommandError("El CSV necesita las columnas «dni» y «localidad_siis» (las trae --exportar-sin-cruce).")
    return filas


def claves_del_catalogo():
    """``({clave: cantidad en el catálogo}, {claves con una equivalencia con destino})``.

    Se calcula una vez: una consulta por fila son miles de idas a la base. Es el
    mismo criterio que la corrección (``Catalogos._resolver_localidad``): una
    equivalencia con destino gana; si no, el nombre del catálogo propio.
    """
    cantidad = {f["clave"]: f["n"] for f in LocalidadSiis.objects.values("clave").annotate(n=Count("id")).order_by()}
    con_alias = set(AliasLocalidadSiis.objects.filter(localidad__isnull=False).values_list("clave", flat=True))
    return cantidad, con_alias


@dataclass
class PlanDeCarga:
    """Lo que la carga va a hacer, sin haber tocado nada."""

    filas: int = 0
    sin_completar: int = 0
    conflicto: set = field(default_factory=set)
    no_existe: collections.Counter = field(default_factory=collections.Counter)
    #: Se cargan, pero solo cruzan si la provincia del caso es la correcta.
    no_unicas: collections.Counter = field(default_factory=collections.Counter)
    nuevos: dict = field(default_factory=dict)
    cambian: dict = field(default_factory=dict)
    iguales: int = 0


def armar_plan(filas, cantidad, con_alias, existentes):
    """Decide qué DNI se cargan, cuáles se actualizan y cuáles quedan afuera.

    ``existentes`` es ``{dni: (dni_tal_cual_en_la_tabla, localidad)}``. Quedan afuera
    las filas sin completar, los nombres que no están ni en el catálogo ni como
    equivalencia, y los DNI con dos localidades distintas (no hay a cuál creerle).
    """
    plan = PlanDeCarga(filas=len(filas))
    pedidos = {}
    for fila in filas:
        dni = normalizar_dni(fila.get("dni"))
        texto = _limpio(fila.get("localidad_siis"))
        if not dni or not texto:
            plan.sin_completar += 1
            continue
        clave = clave_nombre(texto)
        if clave not in con_alias and not cantidad.get(clave):
            plan.no_existe[texto] += 1
            continue
        # Con equivalencia, el alias se busca acotado a la provincia del caso y
        # ``_localidad_unica`` no lo mira: un nombre que no es único en el
        # catálogo depende de la provincia declarada, tenga o no alias.
        if cantidad.get(clave, 0) != 1:
            plan.no_unicas[texto] += 1
        if dni in pedidos and pedidos[dni] != texto:
            plan.conflicto.add(dni)
        pedidos[dni] = texto
    for dni in plan.conflicto:
        pedidos.pop(dni, None)
    plan.nuevos = {d: t for d, t in pedidos.items() if d not in existentes}
    plan.cambian = {d: t for d, t in pedidos.items() if d in existentes and existentes[d][1] != t}
    plan.iguales = len(pedidos) - len(plan.nuevos) - len(plan.cambian)
    return plan
