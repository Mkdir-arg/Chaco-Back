"""Propone a qué localidad de SIIS equivale cada localidad del catálogo core que no cruza.

El selector de Localidad guarda nombres del catálogo core (778 en Chaco) y el padrón de
SIIS tiene 165: la mayoría cruza por ``clave_nombre`` y el resto termina en «La localidad
no coincide con el catálogo de SIIS». Este comando arma la **propuesta** para que el
organismo la revise. No decide nada: no escribe en la base ni toca
``siis_alias_localidades.csv`` (ver el docstring de ``AliasLocalidadSiis``: elegir
equivalencias es una decisión del organismo, no del código).

    python manage.py proponer_alias_siis                       # CSV a stdout
    python manage.py proponer_alias_siis --salida propuesta.csv

Cada localidad core de la provincia operativa queda en uno de tres estados:

- ``CRUZA``: su ``clave_nombre`` ya es la de una localidad de SIIS, o ya tiene una
  equivalencia cargada con destino. No hace falta nada.
- ``PROPUESTA``: no cruza, pero hay **un único** candidato en SIIS por una de dos vías, y
  el ``motivo`` dice cuál: (1) el mismo nombre una vez expandidas las abreviaturas
  habituales («Pcia.», «Gral.») y sin artículos; (2) el nombre de su **municipio** (lo
  mismo con la misma normalización). La vía 2 es la más débil —un paraje del municipio no
  es la cabecera— y por eso el organismo tiene que mirarla.
- ``SIN_CANDIDATO``: nada cruza, hay más de un candidato, ya se revisó y se dejó sin
  destino, o dos localidades con el mismo nombre darían propuestas distintas (el alias
  se busca por nombre, no por municipio).
"""

import csv
from collections import Counter, defaultdict

from django.core.management.base import BaseCommand, CommandError

from core.exportacion import celda_segura
from core.models import Localidad
from core.selectors.geografia import PROVINCIA_OPERATIVA
from programas.models import AliasLocalidadSiis, LocalidadSiis, ProvinciaSiis
from programas.services.siis_envio import clave_nombre

CRUZA = "CRUZA"
PROPUESTA = "PROPUESTA"
SIN_CANDIDATO = "SIN_CANDIDATO"

COLUMNAS = ("localidad_core", "municipio_core", "estado", "localidad_siis_propuesta", "siis_id", "motivo")

#: Abreviaturas que el padrón de SIIS usa («PCIA. DE LA PLAZA») y el catálogo core escribe entero.
_ABREVIATURAS = {
    "pcia": "presidencia",
    "gral": "general",
    "cnel": "coronel",
    "cap": "capitan",
    "tte": "teniente",
    "dr": "doctor",
    "gdor": "gobernador",
    "pto": "puerto",
    "sta": "santa",
    "sto": "santo",
}
_ARTICULOS = frozenset({"de", "del", "la", "las", "los", "el"})


def clave_laxa(texto):
    """``clave_nombre`` más abreviaturas expandidas y sin artículos. Solo para proponer, nunca para cruzar."""
    tokens = [_ABREVIATURAS.get(t, t) for t in clave_nombre(texto).split()]
    # Solo los del medio: «El Pastoril» y «La Pastoril» son dos lugares, y el artículo inicial los distingue.
    return " ".join(t for i, t in enumerate(tokens) if i == 0 or t not in _ARTICULOS)


def _numero(items):
    return f"{len(items)} candidatos: " + ", ".join(sorted(i.nombre for i in items))


def clasificar(localidades, siis_locs, alias_con_destino, alias_sin_destino):
    """Una fila por localidad core, en el orden recibido. Función pura: no consulta la base.

    ``localidades`` son objetos con ``nombre`` y ``municipio`` (o ``None``); ``siis_locs`` las
    ``LocalidadSiis`` de la provincia; ``alias_con_destino`` ``{clave: LocalidadSiis}`` y
    ``alias_sin_destino`` el conjunto de claves ya revisadas sin equivalencia.
    """
    por_clave = defaultdict(list)
    por_laxa = defaultdict(list)
    for s in siis_locs:
        por_clave[s.clave].append(s)
        por_laxa[clave_laxa(s.nombre)].append(s)

    filas = []
    for loc in localidades:
        municipio = loc.municipio.nombre if loc.municipio_id else ""
        clave = clave_nombre(loc.nombre)
        base = {"localidad_core": loc.nombre, "municipio_core": municipio}
        destino, motivo, estado = None, "", SIN_CANDIDATO

        if clave in alias_con_destino:
            destino, estado, motivo = alias_con_destino[clave], CRUZA, "ya tiene una equivalencia cargada"
        elif len(por_clave.get(clave, ())) == 1:
            destino, estado, motivo = por_clave[clave][0], CRUZA, "el nombre coincide con el catálogo de SIIS"
        elif len(por_clave.get(clave, ())) > 1:
            motivo = f"el nombre está repetido en el catálogo de SIIS ({_numero(por_clave[clave])})"
        elif clave in alias_sin_destino:
            motivo = "ya revisada por el organismo: se dejó sin equivalencia"
        else:
            vias = [
                (loc.nombre, "el nombre coincide con el de SIIS al expandir abreviaturas y quitar artículos"),
                (municipio, f"coincide el municipio «{municipio}» con una localidad de SIIS (vía débil: revisar)"),
            ]
            for texto, razon in vias:
                laxa = clave_laxa(texto)
                if not laxa or laxa not in por_laxa:
                    continue
                candidatos = por_laxa[laxa]
                if len(candidatos) == 1:
                    destino, estado, motivo = candidatos[0], PROPUESTA, razon
                else:
                    motivo = f"hay más de un candidato en SIIS ({_numero(candidatos)})"
                break
            else:
                motivo = "ni el nombre ni el municipio coinciden con una localidad de SIIS"

        base.update(
            estado=estado,
            localidad_siis_propuesta=destino.nombre if destino and estado == PROPUESTA else "",
            siis_id=destino.siis_id if destino and estado == PROPUESTA else "",
            motivo=motivo,
        )
        base["_clave"] = clave
        filas.append(base)

    # El alias se busca por nombre, sin municipio: dos localidades con el mismo nombre y
    # destinos distintos no se pueden resolver con una sola fila.
    destinos = defaultdict(set)
    for f in filas:
        if f["estado"] == PROPUESTA:
            destinos[f["_clave"]].add(f["siis_id"])
    for f in filas:
        if f["estado"] == PROPUESTA and len(destinos[f["_clave"]]) > 1:
            f.update(
                estado=SIN_CANDIDATO,
                localidad_siis_propuesta="",
                siis_id="",
                motivo="el mismo nombre en otro municipio daría otra propuesta; el alias no distingue municipios",
            )
    for f in filas:
        f.pop("_clave")
    return filas


class Command(BaseCommand):
    help = "Propone equivalencias de localidades core → SIIS (solo Chaco) para revisión del organismo. Solo lee."

    def add_arguments(self, parser):
        parser.add_argument("--salida", help="Ruta del CSV. Sin ella, el CSV va a stdout.")

    def handle(self, *args, **opciones):
        prov_siis = ProvinciaSiis.objects.filter(clave=clave_nombre(PROVINCIA_OPERATIVA)).first()
        if prov_siis is None:
            raise CommandError(
                f"No hay una provincia «{PROVINCIA_OPERATIVA}» en el catálogo de SIIS: correr seed_catalogo_siis."
            )
        siis_locs = list(LocalidadSiis.objects.filter(provincia=prov_siis))
        alias = list(AliasLocalidadSiis.objects.filter(provincia=prov_siis).select_related("localidad"))
        con_destino = {a.clave: a.localidad for a in alias if a.localidad_id}
        sin_destino = {a.clave for a in alias if not a.localidad_id}
        localidades = list(
            Localidad.objects.filter(municipio__provincia__nombre__iexact=PROVINCIA_OPERATIVA)
            .select_related("municipio")
            .order_by("municipio__nombre", "nombre", "pk")
        )
        filas = clasificar(localidades, siis_locs, con_destino, sin_destino)

        if opciones["salida"]:
            with open(opciones["salida"], "w", encoding="utf-8", newline="") as archivo:
                self._escribir(filas, archivo)
            destino = opciones["salida"]
        else:
            self._escribir(filas, self.stdout)
            destino = "stdout"

        cuenta = Counter(f["estado"] for f in filas)
        # El resumen va a stderr: con el CSV en stdout, mezclarlos lo rompería.
        self.stderr.write(
            f"{len(filas)} localidades de {PROVINCIA_OPERATIVA} → {destino}: "
            f"{cuenta[CRUZA]} {CRUZA}, {cuenta[PROPUESTA]} {PROPUESTA}, {cuenta[SIN_CANDIDATO]} {SIN_CANDIDATO}"
        )

    @staticmethod
    def _escribir(filas, salida):
        escritor = csv.DictWriter(salida, fieldnames=COLUMNAS, lineterminator="\n")
        escritor.writeheader()
        for f in filas:
            # Nombres que vienen de un catálogo cargable: una celda «=...» se ejecutaría en Excel (RED-70).
            escritor.writerow({k: celda_segura(v) if isinstance(v, str) else v for k, v in f.items()})
