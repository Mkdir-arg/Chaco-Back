"""Deja a todos los casos ya cargados con el formulario completo y les completa,
desde la tabla ``ciudadanos_renaper``, el CUIT del alumno, el CUIL del apoderado
y el lugar de nacimiento.

**Por qué hace falta.** Los cinco campos del segmento —Celular Apoderado,
Provincia Nacimiento, Cuit Alumno, Localidad de nacimiento y Cuil Apoderado— se
sumaron al catálogo el 16/09/2026, así que los casos anteriores no los tienen.
Además el CUIT y el CUIL nunca se le pidieron a casi nadie.

**Qué hace con cada caso.** Dos cosas, en una sola pasada:

1. Le pone la **foto** de la definición vigente (Cambio 58) y traduce sus
   respuestas a la forma nueva, igual que ``sincronizar_desde_legacy``. La
   revisión recorre todos los ítems de la foto, no solo las claves cargadas, así
   que los cinco campos pasan a verse en todos los casos, con valor o vacíos. No
   se inventa ninguna respuesta.
2. Completa cuatro campos cruzando por DNI contra ``ciudadanos_renaper``:

   ========================  ==========================  =====================
   Campo del catálogo        Columna de RENAPER          Por qué DNI
   ========================  ==========================  =====================
   Cuit Alumno               ``cuil``                    el del ciudadano del caso
   Cuil Apoderado            ``cuil``                    ``apoderado_dni``
   Provincia Nacimiento      ``provincia_api``           el del ciudadano del caso
   Localidad de nacimiento   ``localidad_api``           el del ciudadano del caso
   ========================  ==========================  =====================

**Cómo escribe.** Por **lotes** (50 casos por defecto, ``--lote``), cada lote en
su propia transacción y con un único ``bulk_update``. Así una corrida contra una
base remota tarda segundos y no minutos, no deja una transacción abierta sobre
la tabla de casos, y se ve avanzar en el log lote a lote. Si se corta, lo ya
confirmado queda y volver a correrlo es seguro: reconoce lo hecho.

**Sobre el lugar de nacimiento.** ``provincia_api`` y ``localidad_api`` son el
**domicilio que figura en el documento**, no el lugar de nacimiento: se comprobó
cruzando la calle contra lo que la persona declaró. El PM decidió el 19/09/2026
usarlos igual para esos dos campos. ``--sin-lugar-nacimiento`` los deja afuera.

Provincia Nacimiento es un selector: el valor se escribe **solo si coincide con
una de sus opciones** (comparando sin acentos ni mayúsculas). Lo que no coincide
se informa al final. La localidad se normaliza de ``PRESIDENCIA_ROQUE_SÁENZ_PEÑA``
a ``Presidencia Roque Sáenz Peña``.

Corre en seco por defecto: sin ``--aplicar`` no escribe nada y solo informa.

    python manage.py completar_casos_renaper                  # ensayo
    python manage.py completar_casos_renaper --aplicar        # de verdad
    python manage.py completar_casos_renaper --aplicar --pisar-existentes

``--pisar-existentes`` reemplaza lo cargado a mano cuando difiere de RENAPER.
Sobre los 287 casos que ya tenían el dato se vieron CUIT truncados, un dígito
verificador equivocado y un caso con el CUIL del alumno en el campo del
apoderado, así que RENAPER es la fuente más confiable; aun así no se pisa nada
salvo que se pida explícitamente.
"""

import time
import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from programas.models import Convocatoria, Formulario, RequisitoNativo
from programas.services.diseno import clave_requisito, obtener_o_crear_diseno
from programas.services.respuestas import (
    COLUMNAS_FIJAS,
    _identidad_de,
    campos_de,
    foto_definicion,
    respuestas_desde_legacy,
)

TABLA_RENAPER = "ciudadanos_renaper"

# Los campos del catálogo que se completan, buscados por su texto normalizado
# para no depender del id. En el catálogo de hoy son rn-26, rn-29, rn-25 y rn-28.
CAMPOS = {
    "cuit": ("Cuit Alumno", "cuit alumno"),
    "cuil": ("Cuil Apoderado", "cuil apoderado"),
    "provincia": ("Provincia Nacimiento", "provincia nacimiento"),
    "localidad": ("Localidad de nacimiento", "localidad de nacimiento"),
}
NUMERICOS = {"cuit", "cuil"}
LUGAR = {"provincia", "localidad"}

# RENAPER nombra distinto a alguna jurisdicción que el selector del catálogo.
ALIAS_PROVINCIA = {
    "ciudad de buenos aires": "ciudad autonoma de buenos aires",
    "caba": "ciudad autonoma de buenos aires",
    "capital federal": "ciudad autonoma de buenos aires",
}
# Palabras que van en minúscula al normalizar una localidad, salvo al inicio.
MINUSCULAS = {"de", "del", "la", "las", "los", "el", "y", "e"}
CAMPOS_A_GUARDAR = ["definicion", "respuestas", "data", "modificado"]


def _norm(texto):
    """Minúsculas, sin acentos, guiones bajos como espacios y espacios colapsados:
    el catálogo tiene «Cuil  Apoderado» con dos espacios y RENAPER manda
    ``LAS_BREÑAS_``."""
    limpio = "".join(
        c for c in unicodedata.normalize("NFD", str(texto or "").replace("_", " ")) if unicodedata.category(c) != "Mn"
    )
    return " ".join(limpio.lower().split())


def _solo_digitos(valor):
    return "".join(c for c in str(valor or "") if c.isdigit())


def _localidad_legible(crudo):
    """``PRESIDENCIA_ROQUE_SÁENZ_PEÑA`` → ``Presidencia Roque Sáenz Peña``."""
    palabras = [p for p in str(crudo or "").replace("_", " ").split() if p]
    salida = []
    for i, palabra in enumerate(palabras):
        baja = palabra.lower()
        salida.append(baja if (i and baja in MINUSCULAS) else baja.capitalize())
    return " ".join(salida)


def _lotes(lista, tamano):
    for inicio in range(0, len(lista), tamano):
        yield inicio // tamano + 1, lista[inicio : inicio + tamano]


class Command(BaseCommand):
    help = (
        "Da a cada caso la foto de su formulario y completa Cuit Alumno, Cuil Apoderado, "
        "Provincia Nacimiento y Localidad de nacimiento desde ciudadanos_renaper."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar", action="store_true", help="Escribe en la base. Sin esto solo informa qué haría."
        )
        parser.add_argument(
            "--pisar-existentes",
            action="store_true",
            help="Reemplaza lo cargado a mano cuando difiere de lo que trae RENAPER.",
        )
        parser.add_argument(
            "--sin-lugar-nacimiento",
            action="store_true",
            help="No toca Provincia Nacimiento ni Localidad de nacimiento.",
        )
        parser.add_argument("--lote", type=int, default=50, help="Casos por transacción. Por defecto 50.")
        parser.add_argument("--limite", type=int, default=0, help="Procesa como mucho N casos. 0 = todos.")
        parser.add_argument("--convocatoria", type=int, default=None, help="Acota a una convocatoria por id.")

    def _log(self, texto="", estilo=None):
        self.stdout.write(estilo(texto) if estilo else texto)
        self.stdout.flush()  # que el avance se vea aunque la salida vaya a un archivo o a un pipe

    # ── Lectura de la tabla de RENAPER y del catálogo ───────────────────────

    def _renaper_por_dni(self):
        """``{dni: {cuil, provincia, localidad}}`` de las consultas que salieron bien.

        Se lee a memoria y se cruza en Python a propósito: la tabla la crea un
        script aparte y puede quedar con otra intercalación que la de la
        aplicación, y ahí un JOIN falla con «Illegal mix of collations»."""
        with connection.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
                [TABLA_RENAPER],
            )
            if not cur.fetchone()[0]:
                raise CommandError(
                    f"No existe la tabla `{TABLA_RENAPER}`. Cargala primero con scripts/DatosPersonas.sql."
                )
            cur.execute(
                f"SELECT dni_consultado, cuil, provincia_api, localidad_api FROM `{TABLA_RENAPER}` WHERE `_ok` = 1"
            )
            filas = {}
            for dni, cuil, provincia, localidad in cur.fetchall():
                dni = _solo_digitos(dni)
                if dni:
                    filas[dni] = {
                        "cuil": (cuil or "").strip(),
                        "provincia": (provincia or "").strip(),
                        "localidad": (localidad or "").strip(),
                    }
            return filas

    def _campos_del_catalogo(self):
        """``{clave_interna: RequisitoNativo}`` para los cuatro campos, por texto."""
        por_norma = {norma: clave for clave, (_, norma) in CAMPOS.items()}
        encontrados = {}
        for requisito in RequisitoNativo.objects.all():
            clave = por_norma.get(_norm(requisito.texto))
            if clave and clave not in encontrados:
                encontrados[clave] = requisito
        faltan = set(CAMPOS) - set(encontrados)
        if faltan:
            raise CommandError("No están en el catálogo: " + ", ".join(sorted(CAMPOS[f][0] for f in faltan)))
        return encontrados

    def _preparar_conversores(self, campos):
        opciones = campos["provincia"].opciones or []
        por_norma = {_norm(o): o for o in opciones}

        def provincia(crudo):
            norma = _norm(crudo)
            norma = ALIAS_PROVINCIA.get(norma, norma)
            return por_norma.get(norma)  # None ⇒ no hay opción para ese valor

        def numero(crudo):
            digitos = _solo_digitos(crudo)
            return int(digitos) if digitos else None

        def localidad(crudo):
            return _localidad_legible(crudo) or None

        return {"cuit": numero, "cuil": numero, "provincia": provincia, "localidad": localidad}

    @staticmethod
    def _mismo_valor(clave, actual, nuevo):
        if clave in NUMERICOS:
            return _solo_digitos(actual) == _solo_digitos(nuevo)
        return _norm(actual) == _norm(nuevo)

    # ── Fase 1: diseños ─────────────────────────────────────────────────────

    def _asegurar_disenos(self, convocatorias, aplicar):
        """Cada convocatoria necesita su diseño: es lo que define la foto."""
        self._log("1. Diseño de cada convocatoria", self.style.MIGRATE_HEADING)
        for convocatoria in convocatorias:
            if not aplicar:
                estado = (
                    "ya tiene diseño" if hasattr(convocatoria, "diseno") else "se le generaría el diseño por defecto"
                )
                self._log(f"   {convocatoria} — {estado}")
                continue
            with transaction.atomic():
                diseno, cambios = obtener_o_crear_diseno(convocatoria)
            detalle = f"v{diseno.version}" + (f" · reconciliado {cambios}" if cambios else "")
            self._log(f"   {convocatoria} — {detalle}")

    # ── Fase 2: un caso ─────────────────────────────────────────────────────

    def _poner_foto(self, caso, fotos):
        """Lo mismo que ``sincronizar_desde_legacy`` pero sin guardar: el guardado
        lo hace el lote. Devuelve si el caso cambió."""
        if caso.definicion:
            return False
        rel_id = caso.relevamiento_id
        if rel_id not in fotos:
            fotos[rel_id] = foto_definicion(caso.relevamiento)
        caso.definicion = fotos[rel_id]
        fijos = {columna: getattr(caso, columna) for columna in COLUMNAS_FIJAS}
        nuevas = respuestas_desde_legacy(caso.data, fijos, _identidad_de(caso), caso.definicion)
        expresables = {c["clave"] for c in campos_de(caso.definicion) if not c["clave"].startswith("cp-")}
        respuestas = {k: v for k, v in (caso.respuestas or {}).items() if k not in expresables}
        respuestas.update(nuevas)
        caso.respuestas = respuestas
        return True

    def _cruzar(self, caso, renaper, campos, conversores, activos, pisar, cuenta, sin_opcion):
        """Completa los campos del caso desde RENAPER. Devuelve si el caso cambió."""
        respuestas = dict(caso.respuestas or {})
        data = dict(caso.data or {})
        requisitos = dict(data.get("requisitos") or {})
        cambio = False

        dni_alumno = _solo_digitos(getattr(caso.ciudadano, "dni", ""))
        dni_apoderado = _solo_digitos(caso.apoderado_dni)
        fila_alumno = renaper.get(dni_alumno)
        fila_apoderado = renaper.get(dni_apoderado) if dni_apoderado else None

        for clave in activos:
            if clave == "cuil":
                if not dni_apoderado:
                    cuenta["sin_apoderado"] += 1
                    continue
                fila = fila_apoderado
            else:
                fila = fila_alumno
            crudo = (fila or {}).get("cuil" if clave in NUMERICOS else clave)
            if not crudo:
                cuenta[f"{clave}_sin_match"] += 1
                continue
            nuevo = conversores[clave](crudo)
            if nuevo is None:
                if clave == "provincia":
                    sin_opcion[crudo] = sin_opcion.get(crudo, 0) + 1
                cuenta[f"{clave}_sin_match"] += 1
                continue

            requisito = campos[clave]
            clave_item = clave_requisito(requisito)
            actual = respuestas.get(clave_item, requisitos.get(str(requisito.pk)))
            if actual not in (None, "", []):
                if self._mismo_valor(clave, actual, nuevo) or not pisar:
                    cuenta[f"{clave}_ya_estaba"] += 1
                    continue
                cuenta[f"{clave}_pisado"] += 1
            else:
                cuenta[f"{clave}_completado"] += 1
            # Los INT van como número, que es como se guardan hoy; los demás como
            # texto. Se escribe en las dos formas del caso: la nueva (respuestas
            # por clave) y la anterior (data por pk).
            respuestas[clave_item] = nuevo
            requisitos[str(requisito.pk)] = nuevo
            cambio = True

        if cambio:
            data["requisitos"] = requisitos
            caso.respuestas = respuestas
            caso.data = data
        return cambio

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        pisar = options["pisar_existentes"]
        con_lugar = not options["sin_lugar_nacimiento"]
        tamano = max(1, options["lote"])
        arranque = time.monotonic()

        if not aplicar:
            self._log("ENSAYO: no se escribe nada. Agregá --aplicar para hacerlo de verdad.\n", self.style.WARNING)

        renaper = self._renaper_por_dni()
        campos = self._campos_del_catalogo()
        conversores = self._preparar_conversores(campos)
        activos = [c for c in CAMPOS if con_lugar or c not in LUGAR]
        self._log(f"RENAPER: {len(renaper)} personas con respuesta")
        self._log(
            "Campos del catálogo: " + ", ".join(f"{clave_requisito(campos[c])} ({CAMPOS[c][0]})" for c in activos)
        )
        if not con_lugar:
            self._log("Lugar de nacimiento: se omite por --sin-lugar-nacimiento")

        casos = Formulario.objects.select_related("ciudadano", "relevamiento__convocatoria__segmento").order_by("pk")
        if options["convocatoria"]:
            casos = casos.filter(relevamiento__convocatoria_id=options["convocatoria"])
        if options["limite"]:
            casos = casos[: options["limite"]]
        casos = list(casos)
        if not casos:
            self._log("No hay casos que procesar.")
            return
        total_lotes = (len(casos) + tamano - 1) // tamano
        self._log(f"Casos a procesar: {len(casos)} en {total_lotes} lotes de {tamano}\n")

        convocatorias = Convocatoria.objects.filter(pk__in={c.relevamiento.convocatoria_id for c in casos})
        self._asegurar_disenos(convocatorias, aplicar)

        self._log("")
        self._log("2. Foto y cruce con RENAPER, lote a lote", self.style.MIGRATE_HEADING)
        fotos = {}
        cuenta = {f"{c}_{e}": 0 for c in activos for e in ("completado", "pisado", "ya_estaba", "sin_match")}
        cuenta.update(sin_apoderado=0, fotos=0, guardados=0)
        sin_opcion = {}

        for numero, lote in _lotes(casos, tamano):
            cambiados = []
            for caso in lote:
                con_foto = self._poner_foto(caso, fotos)
                cuenta["fotos"] += int(con_foto)
                con_cruce = self._cruzar(caso, renaper, campos, conversores, activos, pisar, cuenta, sin_opcion)
                if con_foto or con_cruce:
                    caso.modificado = timezone.now()
                    cambiados.append(caso)
            if aplicar and cambiados:
                with transaction.atomic():
                    Formulario.objects.bulk_update(cambiados, CAMPOS_A_GUARDAR)
            cuenta["guardados"] += len(cambiados)
            verbo = "guardados" if aplicar else "a guardar"
            self._log(
                f"   lote {numero:>4}/{total_lotes} · casos {lote[0].pk}-{lote[-1].pk} · "
                f"{verbo} {len(cambiados):>3} · acumulado {cuenta['guardados']:>5} · {time.monotonic() - arranque:5.1f} s"
            )

        self._log("")
        self._log("3. Resumen", self.style.MIGRATE_HEADING)
        self._log(f"   {'casos que recibieron la foto del formulario':52} {cuenta['fotos']:6}")
        detalles = {
            "completado": "completado",
            "pisado": "reemplazado",
            "ya_estaba": "ya estaba y se respeta",
            "sin_match": "sin dato utilizable en RENAPER",
        }
        for clave in activos:
            for estado, texto in detalles.items():
                self._log(f"   {CAMPOS[clave][0] + ' ' + texto:52} {cuenta[f'{clave}_{estado}']:6}")
        self._log(f"   {'casos sin apoderado cargado':52} {cuenta['sin_apoderado']:6}")
        self._log(f"   {'casos guardados':52} {cuenta['guardados']:6}")
        if sin_opcion:
            self._log("   Provincias de RENAPER sin opción en el selector (no se escribieron):", self.style.WARNING)
            for valor, n in sorted(sin_opcion.items(), key=lambda x: -x[1]):
                self._log(f"      {valor:32} {n:5} casos")

        self._log("")
        segundos = time.monotonic() - arranque
        if aplicar:
            self._log(f"Listo en {segundos:.0f} s. Revisá un caso en la pantalla de revisión.", self.style.SUCCESS)
        else:
            self._log(f"Ensayo terminado en {segundos:.0f} s, la base quedó intacta.", self.style.WARNING)
