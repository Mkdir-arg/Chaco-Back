"""Deja a todos los casos ya cargados con el formulario completo y les completa
el CUIT del alumno y el CUIL del apoderado desde la tabla ``ciudadanos_renaper``.

**Por qué hace falta.** Los cinco campos del segmento —Celular Apoderado,
Provincia Nacimiento, Cuit Alumno, Localidad de nacimiento y Cuil Apoderado— se
sumaron al catálogo el 16/09/2026, así que los casos anteriores no los tienen.
Además el CUIT y el CUIL nunca se le pidieron a casi nadie.

**Cómo lo resuelve.** En dos tiempos:

1. Cada caso recibe la **foto** de la definición vigente (Cambio 58). La revisión
   recorre todos los ítems de esa foto, no solo las claves que el caso traiga
   cargadas, así que a partir de ahí los cinco campos se ven en todos los casos,
   con valor o vacíos. No se inventa ninguna respuesta.
2. El CUIT y el CUIL se completan cruzando por DNI contra ``ciudadanos_renaper``:
   el del alumno por el DNI del ciudadano del caso, el del apoderado por
   ``apoderado_dni``.

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
# Los dos campos del catálogo que se completan, buscados por su texto para no
# depender del id. En el catálogo de hoy son rn-26 y rn-29.
TEXTO_CUIT_ALUMNO = "cuit alumno"
TEXTO_CUIL_APODERADO = "cuil apoderado"


def _norm(texto):
    """Minúsculas, sin acentos y con los espacios colapsados: el catálogo tiene
    «Cuil  Apoderado» con dos espacios."""
    limpio = "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn")
    return " ".join(limpio.lower().split())


def _solo_digitos(valor):
    return "".join(c for c in str(valor or "") if c.isdigit())


class Command(BaseCommand):
    help = "Da a cada caso la foto de su formulario y completa Cuit Alumno y Cuil Apoderado desde ciudadanos_renaper."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribe en la base. Sin esto solo informa qué haría.",
        )
        parser.add_argument(
            "--pisar-existentes",
            action="store_true",
            help="Reemplaza el CUIT/CUIL cargado a mano cuando difiere del de RENAPER.",
        )
        parser.add_argument(
            "--limite",
            type=int,
            default=0,
            help="Procesa como mucho N casos. 0 = todos. Útil para una prueba corta.",
        )
        parser.add_argument(
            "--convocatoria",
            type=int,
            default=None,
            help="Acota a una convocatoria por id. Por defecto, todas.",
        )

    # ── Lectura de la tabla de RENAPER ──────────────────────────────────────

    def _cuiles_por_dni(self):
        """``{dni: cuil}`` de las consultas que salieron bien.

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
                f"SELECT dni_consultado, cuil FROM `{TABLA_RENAPER}` "
                "WHERE `_ok` = 1 AND cuil IS NOT NULL AND cuil <> ''"
            )
            return {_solo_digitos(dni): cuil.strip() for dni, cuil in cur.fetchall() if dni}

    def _claves_de_los_campos(self):
        """``(clave_cuit_alumno, clave_cuil_apoderado)`` buscadas por texto."""
        encontrados = {}
        for requisito in RequisitoNativo.objects.all():
            norma = _norm(requisito.texto)
            if norma == TEXTO_CUIT_ALUMNO:
                encontrados["cuit"] = requisito
            elif norma == TEXTO_CUIL_APODERADO:
                encontrados["cuil"] = requisito
        faltan = {"cuit", "cuil"} - set(encontrados)
        if faltan:
            nombres = {"cuit": "Cuit Alumno", "cuil": "Cuil Apoderado"}
            raise CommandError("No están en el catálogo: " + ", ".join(sorted(nombres[f] for f in faltan)))
        return (
            clave_requisito(encontrados["cuit"]),
            clave_requisito(encontrados["cuil"]),
            encontrados["cuit"].pk,
            encontrados["cuil"].pk,
        )

    # ── Fases ───────────────────────────────────────────────────────────────

    def _asegurar_disenos(self, convocatorias, aplicar):
        """Cada convocatoria necesita su diseño: es lo que define la foto."""
        self.stdout.write(self.style.MIGRATE_HEADING("1. Diseño de cada convocatoria"))
        for convocatoria in convocatorias:
            if not aplicar:
                tiene = hasattr(convocatoria, "diseno")
                estado = "ya tiene diseño" if tiene else "se le generaría el diseño por defecto"
                self.stdout.write(f"   {convocatoria} — {estado}")
                continue
            diseno, cambios = obtener_o_crear_diseno(convocatoria)
            detalle = f"v{diseno.version}"
            if cambios:
                detalle += f" · reconciliado {cambios}"
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
                campos = sum(len(g.get("items") or []) for g in foto.get("items") or [])
                self.stdout.write(
                    f"   relevamiento {rel_id}: v{foto.get('version')} · "
                    f"{len(foto.get('items') or [])} grupos · {campos} ítems"
                )
        return puestas

    def _completar_cuiles(self, casos, cuiles, claves, aplicar, pisar):
        clave_cuit, clave_cuil, pk_cuit, pk_cuil = claves
        self.stdout.write(self.style.MIGRATE_HEADING("3. Cuit Alumno y Cuil Apoderado desde RENAPER"))
        cuenta = {
            "cuit_completado": 0,
            "cuit_sin_match": 0,
            "cuit_ya_estaba": 0,
            "cuit_pisado": 0,
            "cuil_completado": 0,
            "cuil_sin_match": 0,
            "cuil_ya_estaba": 0,
            "cuil_pisado": 0,
            "sin_apoderado": 0,
        }
        for caso in casos:
            respuestas = dict(caso.respuestas or {})
            data = dict(caso.data or {})
            requisitos = dict(data.get("requisitos") or {})
            cambio = False

            pares = [
                ("cuit", clave_cuit, pk_cuit, _solo_digitos(getattr(caso.ciudadano, "dni", ""))),
                ("cuil", clave_cuil, pk_cuil, _solo_digitos(caso.apoderado_dni)),
            ]
            for etiqueta, clave, pk, dni in pares:
                if etiqueta == "cuil" and not dni:
                    cuenta["sin_apoderado"] += 1
                    continue
                nuevo = cuiles.get(dni)
                if not nuevo:
                    cuenta[f"{etiqueta}_sin_match"] += 1
                    continue
                actual = respuestas.get(clave, requisitos.get(str(pk)))
                if actual not in (None, "", []):
                    if _solo_digitos(actual) == nuevo:
                        cuenta[f"{etiqueta}_ya_estaba"] += 1
                        continue
                    if not pisar:
                        cuenta[f"{etiqueta}_ya_estaba"] += 1
                        continue
                    cuenta[f"{etiqueta}_pisado"] += 1
                else:
                    cuenta[f"{etiqueta}_completado"] += 1
                # El valor va como número entero, que es como se guardan hoy las
                # demás respuestas de tipo INT. Los CUIL no llevan ceros delante.
                respuestas[clave] = int(nuevo)
                requisitos[str(pk)] = int(nuevo)
                cambio = True

            if cambio and aplicar:
                data["requisitos"] = requisitos
                caso.respuestas = respuestas
                caso.data = data
                caso.save(update_fields=["respuestas", "data", "modificado"])

        etiquetas = {
            "cuit_completado": "Cuit Alumno completado",
            "cuit_pisado": "Cuit Alumno reemplazado",
            "cuit_ya_estaba": "Cuit Alumno que ya estaba y se respeta",
            "cuit_sin_match": "Cuit Alumno sin dato en RENAPER",
            "cuil_completado": "Cuil Apoderado completado",
            "cuil_pisado": "Cuil Apoderado reemplazado",
            "cuil_ya_estaba": "Cuil Apoderado que ya estaba y se respeta",
            "cuil_sin_match": "Cuil Apoderado sin dato en RENAPER",
            "sin_apoderado": "casos sin apoderado cargado",
        }
        for llave, texto in etiquetas.items():
            self.stdout.write(f"   {texto:44} {cuenta[llave]:6}")
        return cuenta

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        pisar = options["pisar_existentes"]

        if not aplicar:
            self.stdout.write(
                self.style.WARNING("ENSAYO: no se escribe nada. Agregá --aplicar para hacerlo de verdad.\n")
            )

        cuiles = self._cuiles_por_dni()
        claves = self._claves_de_los_campos()
        self.stdout.write(f"RENAPER: {len(cuiles)} CUIL disponibles")
        self.stdout.write(f"Campos del catálogo: {claves[0]} (Cuit Alumno) y {claves[1]} (Cuil Apoderado)\n")

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
            self._completar_cuiles(casos, cuiles, claves, aplicar, pisar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("Listo. Revisá un caso en la pantalla de revisión."))
        else:
            self.stdout.write(self.style.WARNING("Ensayo terminado, la base quedó intacta."))
