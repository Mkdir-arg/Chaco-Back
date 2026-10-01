"""Carga en la base el catálogo geográfico de SIIS y las equivalencias de nombre.

Los datos viajan en el repo (``programas/data/``), no se le piden a la API:
medido contra los 6.395 casos de testing, el servicio no devolvía localidades que
el organismo sí tiene en su padrón —«Juan José Castelli», provincia 1, localidad
64, daba sin coincidencia—, así que depender de él dejaba casos sin poder
informar por un problema que no era del dato.

Idempotente: identifica por el id de SIIS y solo escribe lo que cambió. Correrlo
de nuevo después de actualizar los CSV sincroniza los nombres sin duplicar nada.
**No borra**: una fila que desaparece del CSV queda en la base, porque puede
estar referenciada por una equivalencia ya usada.

    python manage.py seed_catalogo_siis
    python manage.py seed_catalogo_siis --revisar        # qué localidades cargadas no cruzan
    python manage.py seed_catalogo_siis --verificar-api  # si la API dice otros ids

``--revisar`` recorre los casos y lista los nombres de localidad que hoy no
resuelven, con cuántos casos pesa cada uno: es la lista de la que salen las
equivalencias nuevas. No modifica nada.

``--verificar-api`` contrasta estos CSV con lo que devuelve la API y avisa de los
ids que no coinciden. El 01/10/2026 la API devolvió **posiciones de una lista**
en vez de ids —Fontana como 3, que en el padrón del organismo es Puerto Vilelas—
y 4.139 personas quedaron registradas en otra localidad, sin un solo error de
SIIS. Tampoco modifica nada.

**El id de localidad es por provincia, no global**: el padrón del organismo tiene
277 filas pero solo 166 ids distintos, porque el mismo número se repite entre
provincias. Por eso la clave de ``LocalidadSiis`` es (provincia, siis_id) y el
payload manda ``prov_actual`` y ``loc_actual`` juntos.
"""

import collections
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from programas.models import AliasLocalidadSiis, Formulario, LocalidadSiis, ProvinciaSiis, RequisitoNativo
from programas.services.siis_envio import clave_nombre

DATOS = Path(__file__).resolve().parents[2] / "data"


def _filas(nombre):
    """Lee un CSV del repo salteando los comentarios de encabezado."""
    ruta = DATOS / nombre
    if not ruta.exists():
        raise CommandError(f"Falta el archivo de datos {ruta}.")
    with ruta.open(encoding="utf-8") as archivo:
        limpio = (linea for linea in archivo if not linea.lstrip().startswith("#"))
        yield from csv.DictReader(limpio)


class Command(BaseCommand):
    help = "Carga el catálogo geográfico de SIIS y las equivalencias de nombre de localidad."

    def add_arguments(self, parser):
        parser.add_argument(
            "--revisar",
            action="store_true",
            help="No carga nada: lista las localidades cargadas en los casos que hoy no cruzan.",
        )
        parser.add_argument(
            "--verificar-api",
            action="store_true",
            help=(
                "No carga nada: contrasta el catálogo propio con lo que devuelve la API de SIIS y avisa de los "
                "ids que no coinciden. Para detectar antes lo que el 01/10/2026 se detectó después."
            ),
        )

    def _log(self, texto="", estilo=None):
        self.stdout.write(estilo(texto) if estilo else texto)

    # ── Carga ───────────────────────────────────────────────────────────────

    @transaction.atomic
    def _cargar(self):
        nuevas = actualizadas = 0
        for fila in _filas("siis_provincias.csv"):
            nombre = fila["nombre"].strip()
            _, creada = ProvinciaSiis.objects.update_or_create(
                siis_id=int(fila["siis_id"]),
                defaults={"nombre": nombre, "clave": clave_nombre(nombre)},
            )
            nuevas += creada
            actualizadas += not creada
        self._log(f"Provincias: {nuevas} nuevas, {actualizadas} ya estaban")

        provincias = {p.siis_id: p for p in ProvinciaSiis.objects.all()}
        nuevas = actualizadas = 0
        for fila in _filas("siis_localidades.csv"):
            provincia = provincias.get(int(fila["provincia_siis_id"]))
            if provincia is None:
                raise CommandError(
                    f"La localidad {fila['nombre']!r} apunta a la provincia "
                    f"{fila['provincia_siis_id']}, que no está en el catálogo."
                )
            nombre = fila["nombre"].strip()
            _, creada = LocalidadSiis.objects.update_or_create(
                provincia=provincia,
                siis_id=int(fila["siis_id"]),
                defaults={"nombre": nombre, "clave": clave_nombre(nombre)},
            )
            nuevas += creada
            actualizadas += not creada
        self._log(f"Localidades: {nuevas} nuevas, {actualizadas} ya estaban")

        nuevas = actualizadas = sin_destino = 0
        for fila in _filas("siis_alias_localidades.csv"):
            provincia = provincias.get(int(fila["provincia_siis_id"]))
            if provincia is None:
                raise CommandError(f"La equivalencia {fila['texto']!r} apunta a una provincia inexistente.")
            destino = None
            if (fila.get("localidad_siis_id") or "").strip():
                destino = LocalidadSiis.objects.filter(
                    provincia=provincia, siis_id=int(fila["localidad_siis_id"])
                ).first()
                if destino is None:
                    raise CommandError(
                        f"La equivalencia {fila['texto']!r} apunta a la localidad "
                        f"{fila['localidad_siis_id']}, que no existe en {provincia.nombre}."
                    )
            else:
                sin_destino += 1
            texto = fila["texto"].strip()
            _, creada = AliasLocalidadSiis.objects.update_or_create(
                provincia=provincia,
                clave=clave_nombre(texto),
                defaults={"texto": texto, "localidad": destino, "nota": (fila.get("nota") or "").strip()},
            )
            nuevas += creada
            actualizadas += not creada
        self._log(f"Equivalencias: {nuevas} nuevas, {actualizadas} ya estaban ({sin_destino} sin destino a propósito)")

    # ── Revisión ────────────────────────────────────────────────────────────

    def _revisar(self):
        """Lista lo que hoy no cruza, para saber qué equivalencia falta."""
        destinos = {"prov_actual": None, "loc_actual": None, "prov_nacim": None, "loc_nacim": None}
        for pk, destino in RequisitoNativo.objects.exclude(destino_siis="").values_list("pk", "destino_siis"):
            if destino in destinos:
                destinos[destino] = pk
        faltan = [d for d, pk in destinos.items() if pk is None]
        if faltan:
            self._log(f"Sin requisito marcado para: {', '.join(faltan)}. Se omiten.", self.style.WARNING)

        provincias = {p.clave: p for p in ProvinciaSiis.objects.all()}
        localidades = collections.defaultdict(list)
        for loc in LocalidadSiis.objects.all():
            localidades[(loc.provincia_id, loc.clave)].append(loc)
        alias = {(a.provincia_id, a.clave): a for a in AliasLocalidadSiis.objects.all()}

        for etiqueta, clave_prov, clave_loc in (
            ("DOMICILIO", "prov_actual", "loc_actual"),
            ("NACIMIENTO", "prov_nacim", "loc_nacim"),
        ):
            pk_prov, pk_loc = destinos[clave_prov], destinos[clave_loc]
            if pk_prov is None or pk_loc is None:
                continue
            cuenta = collections.Counter()
            sin_cruce = collections.Counter()
            for datos in Formulario.objects.values_list("data", flat=True).iterator():
                requisitos = (datos or {}).get("requisitos") or {}
                texto_prov = str(requisitos.get(str(pk_prov)) or "")
                texto_loc = str(requisitos.get(str(pk_loc)) or "")
                if not texto_loc.strip():
                    cuenta["sin localidad cargada"] += 1
                    continue
                provincia = provincias.get(clave_nombre(texto_prov))
                if provincia is None:
                    cuenta["la provincia no cruza"] += 1
                    sin_cruce[f"[PROVINCIA] {texto_prov!r}"] += 1
                    continue
                equivalencia = alias.get((provincia.pk, clave_nombre(texto_loc)))
                if equivalencia is not None:
                    if equivalencia.localidad_id:
                        cuenta["cruza por equivalencia"] += 1
                    else:
                        cuenta["marcada sin equivalencia"] += 1
                    continue
                candidatas = localidades.get((provincia.pk, clave_nombre(texto_loc)), [])
                if len(candidatas) == 1:
                    cuenta["cruza"] += 1
                elif len(candidatas) > 1:
                    cuenta["ambigua"] += 1
                    sin_cruce[f"[AMBIGUA] {provincia.nombre} / {texto_loc}"] += 1
                else:
                    cuenta["no cruza"] += 1
                    sin_cruce[f"{provincia.nombre} / {texto_loc}"] += 1

            total = sum(cuenta.values())
            self._log("")
            self._log(f"{etiqueta} — {total} casos", self.style.MIGRATE_HEADING)
            for clave, n in cuenta.most_common():
                self._log(f"   {clave:28} {n:6}  {n * 100 / max(total, 1):5.1f}%")
            if sin_cruce:
                self._log(f"   {len(sin_cruce)} nombre(s) sin equivalencia; los 15 que más pesan:")
                for nombre, n in sin_cruce.most_common(15):
                    self._log(f"      {n:5}  {nombre}")

    # ── Contraste con la API ────────────────────────────────────────────────

    def _verificar_api(self):
        """Compara el catálogo propio con lo que devuelve la API de SIIS.

        El 01/10/2026 la API devolvió **posiciones de una lista** en lugar de los
        ids reales —Fontana como 3, que en el padrón del organismo es Puerto
        Vilelas— y 4.139 personas quedaron registradas en otra localidad, sin que
        SIIS devolviera un solo error. Esto existe para que esa discrepancia se
        vea antes y no después.

        No modifica nada: informa y devuelve cuántos choques encontró.
        """
        from programas.services.siis import SiisCatalogError, catalogo

        choques = 0
        for nombre_api, modelo, etiqueta in (
            ("provincias", ProvinciaSiis, "PROVINCIAS"),
            ("localidades", LocalidadSiis, "LOCALIDADES"),
        ):
            self._log("")
            self._log(f"{etiqueta} — catálogo propio contra la API", self.style.MIGRATE_HEADING)
            try:
                items = list(catalogo(nombre_api))
            except SiisCatalogError as exc:
                self._log(f"   La API no respondió: {exc}", self.style.WARNING)
                self._log("   El alta igual funciona: el catálogo propio es el que manda (Cambio 85).")
                continue

            propio = {c.clave: c for c in modelo.objects.all()}
            self._log(f"   la API devuelve {len(items)} · el catálogo propio tiene {len(propio)}")
            if len(items) < len(propio) / 2:
                self._log(
                    "   La API devuelve muchas menos de las que hay: tratar sus ids con desconfianza.",
                    self.style.WARNING,
                )

            distintos, ausentes = [], 0
            for item in items:
                propia = propio.get(clave_nombre(item.get("nombre", "")))
                if propia is None:
                    ausentes += 1
                elif propia.siis_id != item.get("id"):
                    distintos.append(
                        (propia.nombre, propia.siis_id, item.get("id"), getattr(propia, "provincia", None))
                    )

            if distintos:
                choques += len(distintos)
                self._log(f"   {len(distintos)} con el MISMO nombre y DISTINTO id. Las primeras:", self.style.ERROR)
                for nombre, id_propio, id_api, provincia in distintos[:12]:
                    # Dentro de su provincia: el id de localidad no es único a
                    # nivel país, así que buscarlo suelto señalaría a otra.
                    ocupantes = modelo.objects.filter(siis_id=id_api)
                    if provincia is not None:
                        ocupantes = ocupantes.filter(provincia=provincia)
                    quien = ocupantes.first()
                    ocupa = f" (el {id_api} es {quien.nombre})" if quien else ""
                    self._log(f"      {nombre:32} propio={id_propio:>4}  api={id_api}{ocupa}")
            else:
                self._log("   Ningún id en conflicto.", self.style.SUCCESS)
            if ausentes:
                self._log(f"   {ausentes} que la API trae y el catálogo propio no tiene.")
        return choques

    def handle(self, *args, **options):
        if options["revisar"]:
            self._revisar()
            self._log("\nRevisión terminada, no se modificó nada.", self.style.SUCCESS)
            return
        if options["verificar_api"]:
            choques = self._verificar_api()
            self._log("")
            if choques:
                self._log(
                    f"{choques} id(s) en conflicto. El catálogo propio es el que manda: el payload se arma con "
                    "sus ids y está verificado contra el padrón que entregó el organismo. Lo que hay que revisar "
                    "es la API, no el catálogo.",
                    self.style.WARNING,
                )
            else:
                self._log("El catálogo propio y la API coinciden.", self.style.SUCCESS)
            return
        self._cargar()
        self._log("\nListo. Corré --revisar para ver qué falta.", self.style.SUCCESS)
