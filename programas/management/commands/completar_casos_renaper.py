"""Deja a todos los casos ya cargados con el formulario completo y les completa,
desde la tabla ``ciudadanos_renaper``, el CUIT del alumno, el CUIL del apoderado
y el lugar de nacimiento.

**Por qué hace falta.** Los cinco campos del segmento —Celular Apoderado,
Provincia Nacimiento, Cuit Alumno, Localidad de nacimiento y Cuil Apoderado— se
sumaron al catálogo el 16/09/2026, así que los casos anteriores no los tienen.
Además el CUIT y el CUIL nunca se le pidieron a casi nadie.

**Cómo lo resuelve.** En dos tiempos:

1. Cada caso recibe la **foto** de la definición vigente (Cambio 58). La revisión
   recorre todos los ítems de esa foto, no solo las claves que el caso traiga
   cargadas, así que a partir de ahí los cinco campos se ven en todos los casos,
   con valor o vacíos. No se inventa ninguna respuesta.
2. Se completan cuatro campos cruzando por DNI contra ``ciudadanos_renaper``:

   ========================  ==========================  =====================
   Campo del catálogo        Columna de RENAPER          Por qué DNI
   ========================  ==========================  =====================
   Cuit Alumno               ``cuil``                    el del ciudadano del caso
   Cuil Apoderado            ``cuil``                    ``apoderado_dni``
   Provincia Nacimiento      ``provincia_api``           el del ciudadano del caso
   Localidad de nacimiento   ``localidad_api``           el del ciudadano del caso
   ========================  ==========================  =====================

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

import unicodedata

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from programas.models import Convocatoria, Formulario, RequisitoNativo
from programas.services.diseno import clave_requisito, obtener_o_crear_diseno
from programas.services.respuestas import foto_definicion, sincronizar_desde_legacy

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
        parser.add_argument("--limite", type=int, default=0, help="Procesa como mucho N casos. 0 = todos.")
        parser.add_argument("--convocatoria", type=int, default=None, help="Acota a una convocatoria por id.")

    # ── Lectura de la tabla de RENAPER ──────────────────────────────────────

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

    # ── Conversión de lo que trae RENAPER a lo que guarda el caso ────────────

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

    # ── Fases ───────────────────────────────────────────────────────────────

    def _asegurar_disenos(self, convocatorias, aplicar):
        """Cada convocatoria necesita su diseño: es lo que define la foto."""
        self.stdout.write(self.style.MIGRATE_HEADING("1. Diseño de cada convocatoria"))
        for convocatoria in convocatorias:
            if not aplicar:
                estado = (
                    "ya tiene diseño" if hasattr(convocatoria, "diseno") else "se le generaría el diseño por defecto"
                )
                self.stdout.write(f"   {convocatoria} — {estado}")
                continue
            diseno, cambios = obtener_o_crear_diseno(convocatoria)
            detalle = f"v{diseno.version}" + (f" · reconciliado {cambios}" if cambios else "")
            self.stdout.write(f"   {convocatoria} — {detalle}")

    def _poner_fotos(self, casos, aplicar):
        """La foto de la definición vigente, una por relevamiento."""
        self.stdout.write(self.style.MIGRATE_HEADING("2. Foto del formulario en cada caso"))
        fotos = {}
        puestas = ya_tenian = 0
        for caso in casos:
            if caso.definicion:
                ya_tenian += 1
                continue
            puestas += 1
            if not aplicar:
                continue
            rel_id = caso.relevamiento_id
            if rel_id not in fotos:
                fotos[rel_id] = foto_definicion(caso.relevamiento)
            # Se asigna antes para que sincronizar_desde_legacy no recalcule la
            # foto caso por caso: con 6.395 casos esa diferencia se nota.
            caso.definicion = fotos[rel_id]
            sincronizar_desde_legacy(caso, caso.relevamiento)
        self.stdout.write(f"   casos que ya tenían foto: {ya_tenian}")
        self.stdout.write(f"   casos que {'recibieron' if aplicar else 'recibirían'} foto: {puestas}")
        if aplicar and fotos:
            for rel_id, foto in fotos.items():
                items = sum(len(g.get("items") or []) for g in foto.get("items") or [])
                self.stdout.write(
                    f"   relevamiento {rel_id}: v{foto.get('version')} · {len(foto.get('items') or [])} grupos · {items} ítems"
                )
        return puestas

    def _completar(self, casos, renaper, campos, conversores, aplicar, pisar, con_lugar):
        self.stdout.write(self.style.MIGRATE_HEADING("3. Cruce con RENAPER por DNI"))
        activos = [c for c in CAMPOS if con_lugar or c not in LUGAR]
        cuenta = {f"{c}_{e}": 0 for c in activos for e in ("completado", "pisado", "ya_estaba", "sin_match")}
        cuenta["sin_apoderado"] = 0
        sin_opcion = {}

        for caso in casos:
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
                # Los INT van como número, que es como se guardan hoy; los
                # demás como texto. Se escribe en las dos formas del caso: la
                # nueva (respuestas por clave) y la anterior (data por pk).
                respuestas[clave_item] = nuevo
                requisitos[str(requisito.pk)] = nuevo
                cambio = True

            if cambio and aplicar:
                data["requisitos"] = requisitos
                caso.respuestas = respuestas
                caso.data = data
                caso.save(update_fields=["respuestas", "data", "modificado"])

        detalles = {
            "completado": "completado",
            "pisado": "reemplazado",
            "ya_estaba": "ya estaba y se respeta",
            "sin_match": "sin dato utilizable en RENAPER",
        }
        for clave in activos:
            nombre = CAMPOS[clave][0]
            for estado, texto in detalles.items():
                self.stdout.write(f"   {nombre + ' ' + texto:52} {cuenta[f'{clave}_{estado}']:6}")
        self.stdout.write(f"   {'casos sin apoderado cargado':52} {cuenta['sin_apoderado']:6}")
        if sin_opcion:
            self.stdout.write(
                self.style.WARNING("   Provincias de RENAPER sin opción en el selector (no se escribieron):")
            )
            for valor, n in sorted(sin_opcion.items(), key=lambda x: -x[1]):
                self.stdout.write(f"      {valor:32} {n:5} casos")
        return cuenta

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        pisar = options["pisar_existentes"]
        con_lugar = not options["sin_lugar_nacimiento"]

        if not aplicar:
            self.stdout.write(
                self.style.WARNING("ENSAYO: no se escribe nada. Agregá --aplicar para hacerlo de verdad.\n")
            )

        renaper = self._renaper_por_dni()
        campos = self._campos_del_catalogo()
        conversores = self._preparar_conversores(campos)
        self.stdout.write(f"RENAPER: {len(renaper)} personas con respuesta")
        self.stdout.write(
            "Campos del catálogo: " + ", ".join(f"{clave_requisito(r)} ({CAMPOS[c][0]})" for c, r in campos.items())
        )
        if not con_lugar:
            self.stdout.write("Lugar de nacimiento: se omite por --sin-lugar-nacimiento")
        self.stdout.write("")

        casos = Formulario.objects.select_related("ciudadano", "relevamiento__convocatoria__segmento").order_by("pk")
        if options["convocatoria"]:
            casos = casos.filter(relevamiento__convocatoria_id=options["convocatoria"])
        if options["limite"]:
            casos = casos[: options["limite"]]
        casos = list(casos)
        if not casos:
            self.stdout.write("No hay casos que procesar.")
            return
        self.stdout.write(f"Casos a procesar: {len(casos)}\n")

        convocatorias = Convocatoria.objects.filter(pk__in={c.relevamiento.convocatoria_id for c in casos})

        with transaction.atomic():
            self._asegurar_disenos(convocatorias, aplicar)
            self.stdout.write("")
            self._poner_fotos(casos, aplicar)
            self.stdout.write("")
            if aplicar:
                # Las fotos recién escritas cambian lo que ve la fase 3.
                casos = list(
                    Formulario.objects.select_related("ciudadano").filter(pk__in=[c.pk for c in casos]).order_by("pk")
                )
            self._completar(casos, renaper, campos, conversores, aplicar, pisar, con_lugar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("Listo. Revisá un caso en la pantalla de revisión."))
        else:
            self.stdout.write(self.style.WARNING("Ensayo terminado, la base quedó intacta."))
