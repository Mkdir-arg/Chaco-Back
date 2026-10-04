"""Corrige los datos que hoy impiden informar un caso a SIIS.

Las dos correcciones se escriben en el ``datos_siis`` del caso —la misma
«corrección para SIIS» que carga el coordinador desde la pantalla—, así que
**no se toca lo que declaró el ciudadano ni su legajo**: la respuesta original
queda intacta y lo corregido viaja solo en el alta.

1. **Localidad del domicilio que no cruza el catálogo de SIIS.** El texto bueno
   sale de la tabla ``localidades_corregidas`` (``dni``, ``localidad``), que
   carga el organismo desde su planilla igual que ``ciudadanos_renaper``. Solo
   se toca el caso cuya localidad hoy **no** resuelve: si ya cruzaba, no se
   pisa. La corrección se guarda como el id de SIIS, que es lo que viaja.

2. **Fecha de nacimiento del apoderado que SIIS rechaza.** Su validación pide
   un apoderado mayor de 18 y sin fecha futura; en la corrida del 23/09 fue el
   único motivo de los 265 rechazos, casi siempre porque la persona se cargó a
   sí misma como apoderado. La fecha a usar se pasa con ``--fecha-apoderado``:
   es un dato que no está en ninguna fuente, así que el comando no elige uno
   por su cuenta.

3. **Estado civil que SIIS no tiene en su catálogo.** El relevamiento ofrece
   «Separado/a» y SIIS no: el campo es obligatorio, así que sin equivalencia el
   caso ni se intenta. Con qué reemplazarlo lo decide el organismo y se pasa en
   ``--estado-civil-sin-equivalente``; el 01/10/2026 se resolvió «Soltero/a».

Corre en seco por defecto: sin ``--aplicar`` no escribe nada y solo informa.

    python manage.py corregir_datos_siis                                  # ensayo
    python manage.py corregir_datos_siis --aplicar
    python manage.py corregir_datos_siis --aplicar --fecha-apoderado 1990-01-01
    python manage.py corregir_datos_siis --sin-apoderados --aplicar

Avanza por lotes, cada uno en su transacción: si se corta, lo confirmado queda
y volver a correrlo es seguro (reconoce lo ya corregido y no lo repite).
"""

import collections
import time
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from legajos.models import Ciudadano
from programas.management.commands._insumos_siis import falta_tabla
from programas.models import EnvioSIIS, Formulario, LocalidadSiis
from programas.services import proceso_masivo
from programas.services.padron import normalizar_dni
from programas.services.siis import catalogo
from programas.services.siis_envio import (
    CatalogoNoDisponible,
    Catalogos,
    clave_nombre,
    respuestas_por_destino,
)

TABLA_LOCALIDADES = "localidades_corregidas"
MAYORIA_DE_EDAD = 18
LOTE = 200
# SIIS exige al menos 4 caracteres de barrio.
BARRIO_MINIMO = 4
# Lo que la gente escribe para decir «no tengo barrio». Nada de esto es un
# nombre: son marcadores, y traducirlos a «Barrio -» sería peor que el genérico.
BARRIO_SIN_DATO = {"-", "--", "---", ".", "..", "...", "_", "__", "___", "no", "n/a", "na", "s/n", "sn", "x", "0", "âŒ"}


# Alias de la función canónica (RED-47): la copia propia agregaba un 0 al final
# con el Decimal que devuelve el driver para la columna de ``ciudadanos_renaper``.
_digitos = normalizar_dni


def _edad(nacimiento, hoy):
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def _lotes(lista, tamano):
    for inicio in range(0, len(lista), tamano):
        yield inicio // tamano + 1, lista[inicio : inicio + tamano]


def _catalogo_que_se_rinde():
    """``cargar`` para :class:`Catalogos` que deja de insistir con la API.

    Sin credenciales —o con SIIS caído— cada caso reintentaba la consulta y
    dejaba un traceback en el log: miles de llamadas inútiles que multiplicaban
    la duración del comando. Acá la corrección de localidad se apoya en el
    catálogo propio de la base (Cambio 85), que no necesita la API; el primer
    fallo se recuerda y el resto de los casos siguen sin volver a pedirla.
    """
    estado = {"caida": False}

    def cargar(nombre):
        if estado["caida"]:
            return []
        try:
            return catalogo(nombre)
        except Exception:  # noqa: BLE001 - cualquier falla de la API vale igual
            estado["caida"] = True
            return []

    return cargar


class Command(BaseCommand):
    help = "Corrige localidad del domicilio y fecha del apoderado para que el caso pueda informarse a SIIS."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Escribe. Sin esto solo informa qué haría.")
        parser.add_argument(
            "--tabla",
            default=TABLA_LOCALIDADES,
            help=f"Tabla con las localidades corregidas (dni, localidad). Por defecto {TABLA_LOCALIDADES}.",
        )
        parser.add_argument(
            "--fecha-apoderado",
            default=None,
            help="Fecha AAAA-MM-DD a poner donde SIIS rechaza la del apoderado. Sin esto, no se corrige ninguna.",
        )
        parser.add_argument("--sin-localidades", action="store_true", help="No toca la localidad del domicilio.")
        parser.add_argument("--sin-apoderados", action="store_true", help="No toca la fecha del apoderado.")
        parser.add_argument(
            "--barrio-generico",
            default=None,
            help=(
                "Texto a usar donde el barrio es un marcador de «no tengo» (-, ., S/N). "
                "Los barrios cortos con nombre real se prefijan con «Barrio» y no usan esto. "
                "Sin la opción, no se corrige ningún barrio."
            ),
        )
        parser.add_argument(
            "--estado-civil-sin-equivalente",
            default=None,
            help=(
                "Estado civil a usar donde el declarado no existe en el catálogo de SIIS "
                "(«Separado/a»). Va el nombre, no el id: se resuelve contra el catálogo y "
                "el comando corta si tampoco ese existe. Sin la opción, no se corrige ninguno."
            ),
        )
        parser.add_argument(
            "--heredar-nacimiento",
            action="store_true",
            help="Donde la localidad de nacimiento no resuelve, usa la del domicilio (decisión del 19/09/2026).",
        )
        parser.add_argument(
            "--fecha-nacimiento-renaper",
            action="store_true",
            help=(
                "Corrige en el legajo la fecha de nacimiento del titular cuando está vacía o es futura, "
                "tomándola de ciudadanos_renaper. Es la única corrección que toca el legajo."
            ),
        )
        parser.add_argument("--lote", type=int, default=LOTE, help=f"Casos por transacción. Por defecto {LOTE}.")
        parser.add_argument("--limite", type=int, default=0, help="Procesa como mucho N casos. 0 = todos.")
        parser.add_argument("--convocatoria", type=int, default=None, help="Acota a una convocatoria por id.")

    def _log(self, texto="", estilo=None):
        self.stdout.write(estilo(texto) if estilo else texto)
        self.stdout.flush()

    # ── Insumos ─────────────────────────────────────────────────────────────

    def _fechas_de_renaper(self):
        """``{dni: fecha_nacimiento}`` de las consultas que salieron bien.

        Se cruza en Python, no con un JOIN: la tabla la crea un script aparte y
        puede quedar con otra intercalación (mismo motivo que en
        ``completar_casos_renaper``).
        """
        tabla = "ciudadanos_renaper"
        if tabla not in connection.introspection.table_names():
            raise CommandError(falta_tabla(tabla, "DatosPersonas.sql"))
        filas = {}
        with connection.cursor() as cur:
            cur.execute(f"SELECT dni_consultado, fecha_nacimiento FROM `{tabla}` WHERE `_ok` = 1")  # nosec B608
            for dni, fecha in cur.fetchall():
                dni = _digitos(dni)
                if dni and fecha:
                    filas[dni] = fecha
        return filas

    def _localidades_corregidas(self, tabla):
        """``{dni: localidad}`` de la planilla del organismo.

        Se lee a memoria y se cruza en Python, como en ``completar_casos_renaper``:
        la tabla la crea un script aparte y puede quedar con otra intercalación,
        y ahí un JOIN falla con «Illegal mix of collations».
        """
        if tabla not in connection.introspection.table_names():
            raise CommandError(f"No existe la tabla `{tabla}`. Cargala primero con dos columnas: `dni` y `localidad`.")
        columnas = {c.name for c in connection.introspection.get_table_description(connection.cursor(), tabla)}
        col_dni = "dni" if "dni" in columnas else ("dni_extraido" if "dni_extraido" in columnas else None)
        if col_dni is None or "localidad" not in columnas:
            raise CommandError(f"La tabla `{tabla}` necesita las columnas `dni` (o `dni_extraido`) y `localidad`.")
        filas = {}
        with connection.cursor() as cur:
            # Nombres validados contra la introspección, no entrada externa.
            cur.execute(f"SELECT `{col_dni}`, `localidad` FROM `{tabla}`")  # nosec B608
            for dni, localidad in cur.fetchall():
                dni = _digitos(dni)
                localidad = " ".join(str(localidad or "").split())
                if dni and localidad:
                    filas[dni] = localidad
        return filas

    # ── Una corrección ──────────────────────────────────────────────────────

    def _con_provincia(self, campo_loc, campo_prov, encontrada, corrigio_provincia):
        """La corrección de una localidad, más su provincia si hubo que cambiarla.

        Cuando se resolvió sin acotar la provincia, ``encontrada`` es la
        ``LocalidadSiis`` entera: el id solo no alcanza para saber de qué
        provincia es, porque se repite entre ellas.
        """
        if not corrigio_provincia:
            return {campo_loc: int(encontrada)}
        if encontrada is None or not encontrada.provincia_id:
            return None
        return {campo_loc: int(encontrada.siis_id), campo_prov: encontrada.provincia.siis_id}

    def _variantes(self, texto, provincia_texto):
        """El mismo nombre, sin lo que la gente le agrega y el catálogo no tiene.

        «Barranqueras chaco», «Fontana chaco», «Quitilipi-chaco»: el nombre de
        la provincia pegado al de la localidad. Se prueban las variantes en
        orden, de la más conservadora a la más agresiva, y la primera que
        resuelve gana. No se inventa nada: solo se saca texto de más.
        """
        limpio = " ".join(str(texto or "").split())
        if not limpio:
            return []
        variantes = [limpio]
        provincia = " ".join(str(provincia_texto or "").split())
        sufijos = [provincia] if provincia else []
        sufijos.append("chaco")
        for sufijo in sufijos:
            if not sufijo:
                continue
            for separador in (" ", "-", ", ", " - "):
                cola = f"{separador}{sufijo}"
                if limpio.lower().endswith(cola.lower()):
                    recortado = limpio[: -len(cola)].strip(" -,")
                    if recortado and recortado not in variantes:
                        variantes.append(recortado)
        return variantes

    def _resolver_con_variantes(self, catalogos, texto, provincia_id, provincia_texto):
        """``(id, corrigio_provincia)`` probando las variantes y, al final, sin
        acotar a la provincia declarada: «Ezeiza» u «Oberá» son localidades
        reales que solo fallan porque la provincia del caso está equivocada."""
        for variante in self._variantes(texto, provincia_texto):
            encontrado = self._resolver(catalogos, variante, provincia_id)
            if encontrado is not None:
                return encontrado, False
        for variante in self._variantes(texto, provincia_texto):
            encontrada = self._localidad_unica(variante)
            if encontrada is not None:
                return encontrada, True
        return None, False

    def _resolver(self, catalogos, texto, provincia_id):
        """El id de localidad de SIIS, o ``None``. Sin credenciales de la API el
        catálogo propio igual resuelve (Cambio 85); lo que no, queda en None."""
        if not texto:
            return None
        try:
            return catalogos.localidad_id(texto, provincia_id)
        except CatalogoNoDisponible:
            return None

    @staticmethod
    def _localidad_unica(texto):
        """La ``LocalidadSiis`` cuando el nombre es único en todo el catálogo.

        Devuelve el **objeto**, no el id, porque el id de localidad se repite
        entre provincias: el 1 son 28 localidades distintas. Quedarse con el id
        y buscar después su provincia con ``filter(siis_id=...)`` señala a otra
        —para el 1, Asunción (Paraguay)— y el par resultante existe en el
        padrón, así que SIIS lo acepta sin devolver error. Es la misma clase de
        fallo silencioso que dejó 4.139 personas en la localidad equivocada el
        01/10/2026.

        Solo mira el catálogo propio: para geografía, la API no es una fuente
        confiable (Cambio 85).
        """
        clave = clave_nombre(texto or "")
        if not clave:
            return None
        candidatas = list(LocalidadSiis.objects.filter(clave=clave).select_related("provincia")[:2])
        return candidatas[0] if len(candidatas) == 1 else None

    def _provincia(self, catalogos, correcciones, respuestas):
        valor = correcciones.get("prov_actual")
        if valor not in (None, ""):
            return int(valor)
        try:
            return catalogos.provincia_id(respuestas.get("prov_actual", ""))
        except CatalogoNoDisponible:
            return None

    def _corregir_localidad(self, caso, catalogos, planilla, cuenta):
        correcciones = caso.datos_siis if isinstance(caso.datos_siis, dict) else {}
        if correcciones.get("loc_actual") not in (None, ""):
            cuenta["loc_ya_corregida"] += 1
            return None
        respuestas = respuestas_por_destino(caso)
        provincia_id = self._provincia(catalogos, correcciones, respuestas)
        declarado = respuestas.get("loc_actual", "")
        provincia_texto = respuestas.get("prov_actual", "")
        if self._resolver(catalogos, declarado, provincia_id) is not None:
            cuenta["loc_ya_cruzaba"] += 1
            return None

        # Antes de ir a la planilla: lo declarado puede estar bien y fallar solo
        # por el nombre de la provincia pegado atrás, o porque la provincia
        # cargada no es la de esa localidad.
        propio, corrigio_provincia = self._resolver_con_variantes(catalogos, declarado, provincia_id, provincia_texto)
        if propio is not None:
            correccion = self._con_provincia("loc_actual", "prov_actual", propio, corrigio_provincia)
            if correccion is not None:
                cuenta["loc_limpiada_del_texto" if not corrigio_provincia else "loc_resuelta_sin_provincia"] += 1
                return correccion

        dni = _digitos(getattr(caso.ciudadano, "dni", ""))
        texto = planilla.get(dni) or planilla.get(dni.lstrip("0")) or planilla.get(dni.zfill(8))
        if not texto:
            cuenta["loc_sin_dato_en_planilla"] += 1
            etiqueta = declarado.strip() or "(vacío)"
            self.sin_planilla[etiqueta] = self.sin_planilla.get(etiqueta, 0) + 1
            return None
        nuevo = self._resolver(catalogos, texto, provincia_id)
        if nuevo is not None:
            cuenta["loc_corregida"] += 1
            return {"loc_actual": nuevo}

        # La provincia declarada puede ser la equivocada: un chico de Quitilipi
        # con «Ciudad Autónoma de Buenos Aires» cargada. Se reintenta sin acotar
        # y, si el nombre es único en todo el catálogo, se corrige también la
        # provincia: la localidad que da el organismo manda sobre lo tipeado.
        suelta = self._localidad_unica(texto)
        if suelta is None or not suelta.provincia_id:
            cuenta["loc_planilla_no_cruza"] += 1
            self.sin_cruce[texto] = self.sin_cruce.get(texto, 0) + 1
            return None
        cuenta["loc_corregida"] += 1
        cuenta["prov_corregida"] += 1
        return {"loc_actual": int(suelta.siis_id), "prov_actual": suelta.provincia.siis_id}

    def _fecha_de_renaper(self, caso, renaper, cuenta):
        """La fecha de nacimiento del titular cuando la cargada es imposible.

        A diferencia del resto, esto **sí corrige el legajo**: una fecha futura
        no es una discrepancia opinable, es un dato equivocado —casi siempre el
        año actual en lugar del de nacimiento, «2026-10-02» por «2007-10-02»— y
        arrastra la edad, que es la que decide si la persona necesita apoderado.
        RENAPER es la fuente oficial. Solo se toca lo vacío o lo futuro: una
        fecha plausible no se pisa nunca.
        """
        ciudadano = caso.ciudadano if caso.ciudadano_id else None
        if ciudadano is None:
            return None
        actual = ciudadano.fecha_nacimiento
        if actual is not None and actual <= timezone.localdate():
            return None
        fecha = renaper.get(_digitos(ciudadano.dni))
        if fecha is None:
            cuenta["fecha_sin_dato_en_renaper"] += 1
            return None
        cuenta["fecha_vacia_completada" if actual is None else "fecha_futura_corregida"] += 1
        ciudadano.fecha_nacimiento = fecha
        return ciudadano

    def _corregir_barrio(self, caso, generico, cuenta):
        """El barrio que SIIS rechaza por corto.

        No todo lo corto es basura: «Sur», «UOM», «CIC» y «PPI» son barrios de
        verdad. A esos se les antepone «Barrio», que es lo que el propio payload
        ya hace con los barrios numéricos, y así se conserva el dato. El
        genérico queda solo para los marcadores de «no tengo barrio».
        """
        correcciones = caso.datos_siis if isinstance(caso.datos_siis, dict) else {}
        if correcciones.get("barrio_actual"):
            cuenta["barrio_ya_corregido"] += 1
            return None
        actual = " ".join(str(respuestas_por_destino(caso).get("barrio_actual", "")).split())
        if len(actual) >= BARRIO_MINIMO or (actual.isdigit() and len(f"Barrio {actual}") >= BARRIO_MINIMO):
            # El payload ya resuelve estos dos: no hay nada que corregir.
            return None
        if actual and actual.lower() not in BARRIO_SIN_DATO and any(c.isalnum() for c in actual):
            cuenta["barrio_es_un_nombre_corto"] += 1
            return {"barrio_actual": f"Barrio {actual}"}
        cuenta["barrio_sin_dato"] += 1
        return {"barrio_actual": generico}

    def _corregir_nacimiento(self, caso, catalogos, cuenta):
        """La localidad de nacimiento que no resuelve.

        Dos salidas, en orden. Primero se reintenta sin acotar a la provincia
        declarada: «Córdoba» o «Moreno» son localidades reales que fallan solo
        porque la provincia de nacimiento está mal cargada. Si no hay dato
        utilizable —«Sin Informar», vacío—, se hereda la localidad del
        domicilio: es la misma decisión que tomó el programa el 19/09/2026 al
        completar el lugar de nacimiento con el domicilio que figura en el
        documento, y es un dato real de la persona, no uno inventado.
        """
        correcciones = caso.datos_siis if isinstance(caso.datos_siis, dict) else {}
        if correcciones.get("loc_nacim"):
            cuenta["nacim_ya_corregida"] += 1
            return None
        respuestas = respuestas_por_destino(caso)
        prov_nacim = correcciones.get("prov_nacim")
        if prov_nacim in (None, ""):
            try:
                prov_nacim = catalogos.provincia_id(respuestas.get("prov_nacim", ""))
            except CatalogoNoDisponible:
                prov_nacim = None
        texto = respuestas.get("loc_nacim", "")
        if self._resolver(catalogos, texto, prov_nacim) is not None:
            return None

        suelta = self._localidad_unica(texto)
        if suelta is not None and suelta.provincia_id:
            cuenta["nacim_resuelta_sin_provincia"] += 1
            return {"loc_nacim": int(suelta.siis_id), "prov_nacim": suelta.provincia.siis_id}

        # Heredar el domicilio: hace falta la localidad **y su provincia**, no el
        # id solo. El id se repite entre provincias —el 1 son 28 localidades— así
        # que buscar la provincia después daría Asunción para quien vive en
        # Resistencia, y el par existe en el padrón: SIIS lo aceptaría sin error.
        provincia_actual = correcciones.get("prov_actual")
        heredada = correcciones.get("loc_actual")
        if heredada in (None, "") or provincia_actual in (None, ""):
            provincia_actual = self._provincia(catalogos, correcciones, respuestas)
            heredada = self._resolver(catalogos, respuestas.get("loc_actual", ""), provincia_actual)
        if heredada in (None, "") or provincia_actual in (None, ""):
            cuenta["nacim_sin_salida"] += 1
            return None
        cuenta["nacim_heredada_del_domicilio"] += 1
        return {"loc_nacim": int(heredada), "prov_nacim": int(provincia_actual)}

    def _corregir_estado_civil(self, caso, catalogos, destino, cuenta):
        """El estado civil declarado que SIIS no tiene en su catálogo.

        Son los «Separado/a»: 11 casos al 01/10/2026. SIIS pide ``est_civil``
        obligatorio y su catálogo no lo incluye, así que el caso queda como
        faltante y **ni se intenta** —no aparece entre los rechazados, que es
        donde uno lo buscaría—.

        Solo se toca lo que no cruza. Un estado civil que la API sí reconoce no
        se pisa nunca, y la respuesta vacía tampoco se completa: ahí el dato no
        está, y ponerle uno sería inventarlo.
        """
        correcciones = caso.datos_siis if isinstance(caso.datos_siis, dict) else {}
        if correcciones.get("est_civil") not in (None, ""):
            cuenta["civil_ya_corregido"] += 1
            return None
        declarado = " ".join(str(respuestas_por_destino(caso).get("est_civil", "")).split())
        if not declarado:
            return None
        try:
            if catalogos.estado_civil_id(declarado) is not None:
                return None
        except CatalogoNoDisponible:
            return None
        cuenta["civil_sin_equivalente"] += 1
        self.sin_equivalente[declarado] = self.sin_equivalente.get(declarado, 0) + 1
        return {"est_civil": destino}

    def _corregir_apoderado(self, caso, fecha, hoy, cuenta):
        nacimiento = caso.ciudadano.fecha_nacimiento if caso.ciudadano_id else None
        if not nacimiento or _edad(nacimiento, hoy) >= MAYORIA_DE_EDAD:
            # Mayor de edad: el apoderado ni siquiera viaja en el payload.
            return None
        correcciones = caso.datos_siis if isinstance(caso.datos_siis, dict) else {}
        if correcciones.get("fecha_nacim_apoderado"):
            cuenta["apo_ya_corregido"] += 1
            return None
        if caso.apoderado_ciudadano_id:
            actual = caso.apoderado_ciudadano.fecha_nacimiento
        else:
            actual = caso.apoderado_fecha_nacimiento
        if actual is None:
            cuenta["apo_sin_fecha"] += 1
        elif actual > hoy:
            cuenta["apo_fecha_futura"] += 1
        elif _edad(actual, hoy) < MAYORIA_DE_EDAD:
            mismo = _digitos(caso.apoderado_dni) == _digitos(getattr(caso.ciudadano, "dni", ""))
            cuenta["apo_es_el_propio_alumno" if mismo else "apo_menor_de_18"] += 1
        else:
            cuenta["apo_ok"] += 1
            return None
        return {"fecha_nacim_apoderado": fecha.isoformat()}

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        tamano = max(1, options["lote"])
        hoy = timezone.localdate()
        arranque = time.monotonic()
        self.sin_cruce = {}
        self.sin_planilla = {}
        self.sin_equivalente = {}

        if not aplicar:
            self._log("ENSAYO: no se escribe nada. Agregá --aplicar para hacerlo de verdad.\n", self.style.WARNING)

        con_localidades = not options["sin_localidades"]
        fecha_apoderado = None
        if not options["sin_apoderados"] and options["fecha_apoderado"]:
            try:
                fecha_apoderado = date.fromisoformat(options["fecha_apoderado"])
            except ValueError as exc:
                raise CommandError("--fecha-apoderado va como AAAA-MM-DD, por ejemplo 1990-01-01.") from exc
            if _edad(fecha_apoderado, hoy) < MAYORIA_DE_EDAD:
                raise CommandError(
                    f"Con {fecha_apoderado.isoformat()} el apoderado no llega a 18 años: SIIS lo rechazaría igual."
                )
        elif not options["sin_apoderados"]:
            self._log("Sin --fecha-apoderado: no se corrige ninguna fecha de apoderado.", self.style.WARNING)

        barrio_generico = " ".join(str(options["barrio_generico"] or "").split())
        if barrio_generico and len(barrio_generico) < BARRIO_MINIMO:
            raise CommandError(f"--barrio-generico necesita al menos {BARRIO_MINIMO} caracteres: SIIS los exige.")

        planilla = {}
        if con_localidades:
            planilla = self._localidades_corregidas(options["tabla"])
            self._log(f"Localidades corregidas disponibles: {len(planilla)} DNI en `{options['tabla']}`")
        fechas_renaper = {}
        if options["fecha_nacimiento_renaper"]:
            fechas_renaper = self._fechas_de_renaper()
            self._log(f"Fechas de nacimiento disponibles en RENAPER: {len(fechas_renaper)} DNI")
        if fecha_apoderado:
            self._log(f"Fecha a usar donde SIIS rechaza al apoderado: {fecha_apoderado.isoformat()}")

        catalogos = Catalogos(cargar=_catalogo_que_se_rinde())

        # El reemplazo se resuelve una sola vez y acá: si el nombre elegido
        # tampoco está en el catálogo, mejor cortar antes de escribir nada que
        # descubrirlo caso por caso con el id en None.
        estado_civil_destino = None
        nombre_civil = " ".join(str(options["estado_civil_sin_equivalente"] or "").split())
        if nombre_civil:
            # El catálogo se pide aparte y sin red: ``_catalogo_que_se_rinde``
            # se traga el error de la API y devuelve una lista vacía, y ahí un
            # «no existe ese estado civil» mentiría sobre lo que pasó.
            try:
                disponibles = catalogo("estados-civiles")
            except Exception as exc:  # noqa: BLE001 - cualquier falla de la API vale igual
                raise CommandError(f"No se pudo leer el catálogo de estados civiles de SIIS: {exc}") from exc
            if not disponibles:
                raise CommandError("El catálogo de estados civiles de SIIS vino vacío: sin él no se puede corregir.")
            estado_civil_destino = catalogos.estado_civil_id(nombre_civil)
            if estado_civil_destino is None:
                nombres = ", ".join(str(i.get("nombre", "")) for i in disponibles)
                raise CommandError(f"«{nombre_civil}» no está en el catálogo de SIIS. Los que hay: {nombres}.")
            self._log(f"Estado civil para los que SIIS no tiene: {nombre_civil} (id {estado_civil_destino})")

        # Los pendientes: todo caso que todavía no tiene un alta ENVIADO.
        informados = EnvioSIIS.objects.filter(estado=EnvioSIIS.Estado.ENVIADO).values_list("formulario_id", flat=True)
        casos = Formulario.objects.exclude(pk__in=informados)
        if options["convocatoria"]:
            casos = casos.filter(relevamiento__convocatoria_id=options["convocatoria"])
        # Por rangos de pk (ver ``ids_de``): sin eso, pedir los ids de los 7.500
        # pendientes recorre los 283 MB de la tabla y muere por read_timeout.
        ids = proceso_masivo.ids_de(casos, limite=options["limite"] or None)
        if not ids:
            self._log("No hay casos pendientes que corregir.", self.style.SUCCESS)
            return
        total_lotes = (len(ids) + tamano - 1) // tamano
        self._log(f"Casos pendientes a revisar: {len(ids)} en {total_lotes} lotes de {tamano}\n")

        cuenta = collections.Counter()
        guardados = 0
        legajos = 0
        for numero, lote_ids in _lotes(ids, tamano):
            lote = list(
                Formulario.objects.select_related("ciudadano", "apoderado_ciudadano", "relevamiento__convocatoria")
                .filter(pk__in=lote_ids)
                .order_by("pk")
            )
            cambiados = []
            ciudadanos = []
            for caso in lote:
                nuevos = {}
                if fechas_renaper:
                    # Primero: la fecha del titular decide su edad, y la edad
                    # decide si el apoderado siquiera viaja en el payload.
                    ciudadano = self._fecha_de_renaper(caso, fechas_renaper, cuenta)
                    if ciudadano is not None:
                        ciudadanos.append(ciudadano)
                if con_localidades:
                    nuevos.update(self._corregir_localidad(caso, catalogos, planilla, cuenta) or {})
                if options["heredar_nacimiento"]:
                    # Después de la localidad del domicilio: si esta corrida la
                    # acaba de corregir, el nacimiento hereda la buena.
                    if nuevos.get("loc_actual"):
                        datos = dict(caso.datos_siis or {})
                        datos.update(nuevos)
                        caso.datos_siis = datos
                    nuevos.update(self._corregir_nacimiento(caso, catalogos, cuenta) or {})
                if barrio_generico:
                    nuevos.update(self._corregir_barrio(caso, barrio_generico, cuenta) or {})
                if estado_civil_destino is not None:
                    nuevos.update(self._corregir_estado_civil(caso, catalogos, estado_civil_destino, cuenta) or {})
                if fecha_apoderado:
                    nuevos.update(self._corregir_apoderado(caso, fecha_apoderado, hoy, cuenta) or {})
                if not nuevos:
                    continue
                datos = dict(caso.datos_siis or {})
                datos.update(nuevos)
                caso.datos_siis = datos
                caso.modificado = timezone.now()
                cambiados.append(caso)
            if aplicar and (cambiados or ciudadanos):
                with transaction.atomic():
                    if ciudadanos:
                        Ciudadano.objects.bulk_update(ciudadanos, ["fecha_nacimiento"])
                    if cambiados:
                        Formulario.objects.bulk_update(cambiados, ["datos_siis", "modificado"])
            guardados += len(cambiados)
            legajos += len(ciudadanos)
            verbo = "corregidos" if aplicar else "a corregir"
            self._log(
                f"   lote {numero:>3}/{total_lotes} · casos {lote[0].pk}-{lote[-1].pk} · "
                f"{verbo} {len(cambiados):>3} · acumulado {guardados:>5} · {time.monotonic() - arranque:5.1f} s"
            )

        self._log("")
        self._log("Resumen", self.style.MIGRATE_HEADING)
        etiquetas = {
            "loc_corregida": "localidad corregida desde la planilla",
            "prov_corregida": "   de esas, con la provincia también corregida",
            "loc_ya_cruzaba": "localidad que ya cruzaba (no se toca)",
            "loc_ya_corregida": "localidad ya corregida antes (no se toca)",
            "loc_sin_dato_en_planilla": "no cruza y su DNI no está en la planilla",
            "fecha_futura_corregida": "fecha de nacimiento futura corregida con RENAPER",
            "fecha_vacia_completada": "fecha de nacimiento vacía completada con RENAPER",
            "fecha_sin_dato_en_renaper": "fecha imposible que RENAPER no puede corregir",
            "loc_planilla_no_cruza": "la planilla tampoco cruza el catálogo",
            "nacim_resuelta_sin_provincia": "nacimiento resuelto (la provincia estaba mal)",
            "nacim_heredada_del_domicilio": "nacimiento heredado del domicilio",
            "nacim_sin_salida": "nacimiento sin dato ni domicilio del que heredar",
            "nacim_ya_corregida": "nacimiento ya corregido antes (no se toca)",
            "barrio_es_un_nombre_corto": "barrio corto con nombre real («Barrio Sur»)",
            "barrio_sin_dato": "barrio que era un marcador (va el genérico)",
            "barrio_ya_corregido": "barrio ya corregido antes (no se toca)",
            "civil_sin_equivalente": "estado civil que SIIS no tiene (va el de reemplazo)",
            "civil_ya_corregido": "estado civil ya corregido antes (no se toca)",
            "apo_es_el_propio_alumno": "apoderado con el DNI del propio alumno",
            "apo_menor_de_18": "apoderado distinto pero menor de 18",
            "apo_fecha_futura": "apoderado con fecha futura",
            "apo_sin_fecha": "apoderado sin fecha de nacimiento",
            "apo_ya_corregido": "apoderado ya corregido antes (no se toca)",
            "apo_ok": "apoderado correcto (no se toca)",
        }
        for clave, etiqueta in etiquetas.items():
            if cuenta[clave]:
                self._log(f"   {etiqueta:48} {cuenta[clave]:6}")
        self._log(f"   {'casos escritos':48} {guardados:6}")
        if legajos:
            self._log(f"   {'legajos con la fecha de nacimiento corregida':48} {legajos:6}")

        if self.sin_cruce:
            self._log("")
            self._log("Localidades de la planilla que NO están en el catálogo de SIIS:", self.style.WARNING)
            for texto, n in sorted(self.sin_cruce.items(), key=lambda kv: -kv[1])[:20]:
                self._log(f"      {texto:40} {n:5} casos")
            self._log("   Se resuelven agregando la equivalencia en programas/data/siis_alias_localidades.csv.")

        if self.sin_equivalente:
            self._log("")
            self._log("Estados civiles declarados que NO están en el catálogo de SIIS:", self.style.WARNING)
            for texto, n in sorted(self.sin_equivalente.items(), key=lambda kv: -kv[1]):
                self._log(f"      {texto:40} {n:5} casos")
            self._log(f"   A todos les quedó «{nombre_civil}» (id {estado_civil_destino}).")

        if self.sin_planilla:
            self._log("")
            self._log(
                "Casos que no cruzan y cuyo DNI no está en la planilla, por lo que declararon:", self.style.WARNING
            )
            for texto, n in sorted(self.sin_planilla.items(), key=lambda kv: -kv[1])[:20]:
                self._log(f"      {texto:40} {n:5} casos")
            self._log("   Se resuelven sumándolos a la planilla, o con una equivalencia si es un nombre repetido.")

        segundos = time.monotonic() - arranque
        if aplicar:
            self._log(f"\nListo en {segundos:.0f} s.", self.style.SUCCESS)
        else:
            self._log(f"\nEnsayo terminado en {segundos:.0f} s, la base quedó intacta.", self.style.WARNING)
