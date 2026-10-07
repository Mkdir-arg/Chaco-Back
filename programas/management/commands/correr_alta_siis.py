"""Corre el alta masiva en SIIS de punta a punta, en el orden correcto.

Encadena los cinco comandos del circuito y, antes de empezar, verifica que estén
las cosas que ninguno de ellos puede resolver solo. Existe porque el orden
importa y saltearse un paso sale caro: el 01/10/2026 se corrió el envío con el
catálogo geográfico vacío y 4.139 personas quedaron registradas en SIIS con la
localidad equivocada —la API de SIIS devuelve posiciones de una lista, no ids—,
sin que apareciera un solo error.

Lo que hace, en orden:

1. **Precondiciones.** Corta si falta algo, y dice exactamente qué.
2. **Insumos.** Ejecuta los ``.sql`` que carga el organismo (``aprobados_materias``,
   ``localidades_corregidas``, ``ciudadanos_renaper``) desde el propio pod, que no
   tiene cliente de base. Los lee del directorio que apunta ``DATOS_SIIS_DIR``
   —un volumen montado—, no de la imagen: son datos personales de 10.321 personas
   y no pueden viajar con el código (RED-01). Ver ``scripts/README-datos-siis.md``.
3. **Catálogo geográfico** (``seed_catalogo_siis``).
4. **RENAPER** (``completar_casos_renaper``).
5. **Corrección de datos** (``corregir_datos_siis``).
6. **Un caso de prueba, y para.** Muestra con qué localidad salió para que una
   persona lo verifique en SIIS. Sin ``--continuar`` no sigue.
7. **La corrida completa**, con el total calculado de los candidatos que haya.

Lo único que no hace es la configuración de pantalla —marcar el destino SIIS de
las preguntas y cargar los identificadores del programa—, porque son decisiones
del organismo. Si falta, el comando corta en el paso 1 y dice cuál.

    python manage.py correr_alta_siis                              # ensayo
    python manage.py correr_alta_siis --aplicar --usuario coord    # para en el paso 6
    python manage.py correr_alta_siis --aplicar --usuario coord --continuar

Cada paso de a uno es reentrante: si el comando se corta, volver a lanzarlo
retoma donde iba y **no duplica**. Lo que sí deja un corte a mitad es un caso
cuyo POST estaba en vuelo: queda ``EN_PROCESO`` y, pasados cinco minutos, se ve
como **incierto** —no se sabe si SIIS lo registró—. Relanzar el comando lo
saltea; ese caso se resuelve a mano con ``conciliar_envios_siis`` después de
preguntarle a ECOM (``docs/internal/procedimiento-alta-siis.md``).
"""

import time
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from programas.management.commands._base_siis import AYUDA_MOTIVO, FALTA_MOTIVO
from programas.management.commands._insumos_siis import FALTA_DIRECTORIO, INSUMOS
from programas.models import EnvioSIIS, LocalidadSiis, ProgramaSiis, ProvinciaSiis, RequisitoNativo
from programas.services import proceso_masivo
from programas.services.siis_envio import DESTINO_SIIS, DESTINO_TABLA
from programas.services.siis_envio import DESTINOS as DESTINOS_DEL_ALTA

# Los siete destinos que tiene que tener marcado alguna pregunta para que el
# payload se pueda armar. Sin esto el sistema no ve ninguna respuesta del
# formulario y "corrige" datos que en realidad estaban bien.
DESTINOS = (
    "prov_actual",
    "loc_actual",
    "barrio_actual",
    "calle_altura",
    "est_civil",
    "prov_nacim",
    "loc_nacim",
)
LOTE = 40
PAUSA = 2.0
# Casos por invocación del comando que manda. El comando arma el payload de
# todos los candidatos antes de empezar, y cada caso arrastra la foto del
# formulario --27 KB--: con 7.434 de una, el pod se queda sin memoria y muere
# con exit 137. Pasó el 01/10/2026.
TANDA = 500
FECHA_APODERADO = "1990-01-01"
BARRIO_GENERICO = "Sin especificar"
# SIIS no tiene «Separado/a» y el campo es obligatorio: sin reemplazo esos
# casos ni se intentan. Decisión del organismo del 01/10/2026.
ESTADO_CIVIL_SIN_EQUIVALENTE = "Soltero/a"


def _sin_comentarios(texto):
    """Saca los comentarios ``--`` que no estén dentro de una cadena.

    Hace falta antes de partir por ``;``: ``DatosPersonas.sql`` tiene un punto y
    coma adentro de un comentario de cabecera, y sin esto la primera «sentencia»
    queda hecha solo de comentarios («Query was empty») y la siguiente arranca
    con texto suelto.
    """
    salida = []
    for linea in texto.splitlines():
        limpia, comilla, i = [], None, 0
        while i < len(linea):
            caracter = linea[i]
            if comilla:
                if caracter == "\\" and i + 1 < len(linea):
                    limpia.append(linea[i : i + 2])
                    i += 2
                    continue
                if caracter == comilla:
                    comilla = None
            elif caracter in ("'", '"'):
                comilla = caracter
            elif caracter == "-" and linea[i : i + 2] == "--":
                break
            limpia.append(caracter)
            i += 1
        salida.append("".join(limpia))
    return "\n".join(salida)


def _sentencias(texto):
    """Parte un ``.sql`` en sentencias, respetando las comillas.

    Un ``split(";")`` a secas rompe en cuanto un valor —o un comentario— trae un
    punto y coma; acá se sacan primero los comentarios y después se recorre el
    texto llevando cuenta de si está dentro de comillas.
    """
    sentencia = []
    comilla = None
    anterior = ""
    for caracter in _sin_comentarios(texto):
        if comilla:
            if caracter == comilla and anterior != "\\":
                comilla = None
        elif caracter in ("'", '"'):
            comilla = caracter
        elif caracter == ";":
            entera = "".join(sentencia).strip()
            if entera:
                yield entera
            sentencia = []
            anterior = caracter
            continue
        sentencia.append(caracter)
        anterior = caracter
    entera = "".join(sentencia).strip()
    if entera:
        yield entera


class Command(BaseCommand):
    help = "Corre el alta masiva en SIIS de punta a punta: insumos, catálogo, correcciones y envío."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Ejecuta. Sin esto es un ensayo completo.")
        parser.add_argument("--usuario", default=None, help="Responsable de las aprobaciones y los envíos.")
        parser.add_argument(
            "--continuar",
            action="store_true",
            help="Saltea la pausa del caso de prueba y hace la corrida completa. Solo con la verificación hecha.",
        )
        parser.add_argument(
            "--sin-insumos",
            action="store_true",
            help="No ejecuta los .sql: usa las tablas tal como están.",
        )
        parser.add_argument(
            "--scripts",
            default=None,
            help="Directorio de los .sql del organismo. Por defecto el de DATOS_SIIS_DIR.",
        )
        parser.add_argument(
            "--destino",
            choices=list(DESTINOS_DEL_ALTA),
            default=DESTINO_SIIS,
            help=(
                "A dónde van las altas. «siis» a la API (por defecto). «tabla» a la tabla intermedia "
                "de este lado, para revisarlas antes: ahí no hay caso de prueba ni freno, porque "
                "SIIS no ve nada. Después se mandan corriendo lo mismo con --destino siis."
            ),
        )
        parser.add_argument("--fecha-apoderado", default=FECHA_APODERADO, help=f"Por defecto {FECHA_APODERADO}.")
        parser.add_argument("--barrio-generico", default=BARRIO_GENERICO, help=f"Por defecto «{BARRIO_GENERICO}».")
        parser.add_argument(
            "--estado-civil-sin-equivalente",
            default=ESTADO_CIVIL_SIN_EQUIVALENTE,
            help=f"Para los que SIIS no tiene («Separado/a»). Por defecto «{ESTADO_CIVIL_SIN_EQUIVALENTE}».",
        )
        parser.add_argument("--lote", type=int, default=LOTE, help=f"Casos por lote del envío. Por defecto {LOTE}.")
        parser.add_argument("--pausa", type=float, default=PAUSA, help=f"Segundos entre lotes. Por defecto {PAUSA}.")
        parser.add_argument(
            "--solo-precondiciones", action="store_true", help="Revisa que esté todo y sale, sin tocar nada."
        )
        parser.add_argument(
            "--ignorar-corrida",
            action="store_true",
            help=(
                "Arranca aunque la pantalla del proceso masivo tenga una corrida en curso. Solo para "
                "emergencias: los dos caminos procesan los mismos casos y el alta en SIIS no tiene baja. "
                "Exige --motivo."
            ),
        )
        parser.add_argument("--motivo", default="", help=AYUDA_MOTIVO)

    # ── Salida ──────────────────────────────────────────────────────────────

    def _log(self, texto="", estilo=None):
        self.stdout.write(estilo(texto) if estilo else texto)
        self.stdout.flush()

    def _paso(self, numero, titulo):
        self._log("")
        self._log(f"━━━ PASO {numero} · {titulo} ".ljust(78, "━"), self.style.MIGRATE_HEADING)

    def _correr(self, comando, *args, **opciones):
        """Lanza un comando hijo y reenvía su salida indentada."""
        salida = StringIO()
        call_command(comando, *args, stdout=salida, stderr=salida, **opciones)
        for linea in salida.getvalue().splitlines():
            self._log(f"   {linea}")
        return salida.getvalue()

    # ── Paso 1: precondiciones ──────────────────────────────────────────────

    @staticmethod
    def _tiene_identificadores(programa):
        return bool(programa.siis_id_plan_soc_efectivo and programa.siis_jurid_efectivo and programa.siis_funcion_id)

    def _precondiciones(self, aplicar, con_insumos, ignorar_corrida=False, motivo="", usuario=None):
        """Lo que ningún comando puede resolver solo. Corta con la lista entera."""
        faltan = []

        # SIIS-03: no hereda de ``ComandoSiisBase`` —no llama a SIIS, encadena a
        # los que sí—, así que la guarda la pide él. Va acá y no adentro de los
        # hijos para cortar en el paso 1, antes de cargar insumos y correr el
        # catálogo, y no a la mitad del circuito. Solo con ``--aplicar``, igual
        # que en la base: un ensayo no toca nada, y durante una corrida es justo
        # cuando alguien quiere mirar qué haría.
        if aplicar:
            if ignorar_corrida:
                if not motivo:
                    raise CommandError(FALTA_MOTIVO)
                proceso_masivo.registrar_corrida_ignorada("correr_alta_siis", motivo, usuario=usuario)
            else:
                try:
                    proceso_masivo.exigir_sin_corrida_viva()
                except proceso_masivo.CorridaEnCurso as exc:
                    raise CommandError(str(exc)) from exc

        if aplicar and not (settings.SIIS_API_CLIENT_ID and settings.SIIS_API_CLIENT_SECRET):
            faltan.append("Faltan SIIS_API_CLIENT_ID / SIIS_API_CLIENT_SECRET en el entorno.")

        marcados = set(
            RequisitoNativo.objects.exclude(destino_siis="")
            .exclude(destino_siis__isnull=True)
            .values_list("destino_siis", flat=True)
        )
        sin_marcar = [d for d in DESTINOS if d not in marcados]
        if sin_marcar:
            faltan.append(
                "Hay preguntas sin el destino SIIS marcado (se hace en el catálogo de requisitos, "
                f"desde la pantalla): {', '.join(sin_marcar)}."
            )

        # Los identificadores se exigen sobre los programas que tienen casos
        # esperando, no sobre todos: un programa viejo sin configurar no puede
        # frenar el alta de otro que sí está listo.
        programas = ProgramaSiis.objects.all()
        if not programas:
            faltan.append("No hay ningún programa SIIS configurado.")
        else:
            completos, incompletos = [], []
            for programa in programas:
                destino = completos if self._tiene_identificadores(programa) else incompletos
                destino.append(programa.nombre)
            if not completos:
                faltan.append(
                    "Ningún programa tiene los identificadores (id_plan_soc, jurid, id_fun_x_plan). "
                    "Se cargan en «Detalle SIIS», desde la pantalla."
                )
            elif incompletos:
                self._log(
                    f"   Programas sin identificadores (sus casos no van a salir): {', '.join(incompletos)}",
                    self.style.WARNING,
                )

        if not con_insumos:
            tablas = connection.introspection.table_names()
            for tabla, archivo, para_que in INSUMOS:
                if tabla not in tablas:
                    faltan.append(
                        f"Falta la tabla `{tabla}` ({para_que}). Cargala con {archivo} desde el directorio "
                        "que apunta DATOS_SIIS_DIR, o sacá --sin-insumos."
                    )

        if faltan:
            raise CommandError("No se puede arrancar:\n   - " + "\n   - ".join(faltan))

        # Lo ya informado no se reenvía: si una corrida anterior quedó mal y los
        # casos tienen que volver a salir, hay que borrarlos primero —y solo
        # después de que SIIS los haya borrado de su lado, porque su API no
        # deduplica—. Decirlo acá evita confundir «no se tocaron» con «entraron».
        # Cambio 127: «tomado» ya no es solo ENVIADO. Un caso con el POST en vuelo
        # o con un resultado incierto también está fuera de alcance.
        informados = EnvioSIIS.objects.filter(vigente=True).values("formulario_id").distinct().count()
        if informados:
            self._log(
                f"   {informados} caso(s) ya tomados por un envío vigente: NO se vuelven a mandar. Si tienen que "
                "salir de nuevo, hay que borrar sus EnvioSIIS, y solo después de que SIIS los haya purgado.",
                self.style.WARNING,
            )
        inciertos = EnvioSIIS.objects.filter(vigente=True, estado=EnvioSIIS.Estado.INCIERTO).count()
        if inciertos:
            self._log(
                f"   {inciertos} envío(s) de resultado desconocido esperan conciliación con ECOM: "
                "`manage.py conciliar_envios_siis --listar`.",
                self.style.WARNING,
            )

        self._log("   Destinos SIIS marcados: los 7")
        self._log(f"   Programas con identificadores: {programas.count()}")
        if aplicar:
            self._log(f"   SIIS: {settings.SIIS_API_URL}")

    # ── Paso 2: insumos ─────────────────────────────────────────────────────

    def _cargar_insumos(self, directorio, aplicar):
        base = Path(directorio or settings.DATOS_SIIS_DIR)
        if not base.is_dir():
            raise CommandError(FALTA_DIRECTORIO.format(base=base))
        for tabla, archivo, para_que in INSUMOS:
            ruta = base / archivo
            if not ruta.exists():
                self._log(f"   {archivo:22} no está en {base} — se saltea ({para_que})", self.style.WARNING)
                continue
            if not aplicar:
                self._log(f"   {archivo:22} se ejecutaría ({ruta.stat().st_size // 1024} KB)")
                continue
            arranque = time.monotonic()
            with connection.cursor() as cur:
                for sentencia in _sentencias(ruta.read_text(encoding="utf-8")):
                    cur.execute(sentencia)
                cur.execute(f"SELECT COUNT(*) FROM `{tabla}`")  # nosec B608 - nombre de una constante
                filas = cur.fetchone()[0]
            self._log(f"   {archivo:22} {filas:>7} filas en `{tabla}` · {time.monotonic() - arranque:.0f} s")

    # ── Paso 6: el caso de prueba ───────────────────────────────────────────

    def _verificacion(self, usuario, aplicar):
        """Manda un caso y muestra con qué localidad salió."""
        if not aplicar:
            self._log("   (ensayo: no se manda ningún caso)")
            return
        antes = set(EnvioSIIS.objects.values_list("pk", flat=True))
        self._correr(
            "procesar_casos_siis",
            "--solo-completos",
            "--total",
            "1",
            "--lote",
            "1",
            "--aplicar",
            # El orquestador ya tiene su propio freno --el caso de prueba y el
            # --continuar--, asi que preguntar de nuevo seria preguntar dos veces
            # por lo mismo.
            "--si",
            *(("--usuario", usuario) if usuario else ()),
        )
        envio = EnvioSIIS.objects.exclude(pk__in=antes).order_by("-pk").first()
        if envio is None:
            self._log("   No se mandó ningún caso: no quedan candidatos completos.", self.style.WARNING)
            return
        payload = envio.payload if isinstance(envio.payload, dict) else {}
        loc_id, prov_id = payload.get("loc_actual"), payload.get("prov_actual")
        provincia = ProvinciaSiis.objects.filter(siis_id=prov_id).first() if prov_id else None
        # Acotada a su provincia: el id de localidad se repite entre provincias
        # —el 1 son 28 localidades— y buscarlo suelto diría «ASUNCION» para quien
        # vive en Resistencia, que es una alarma falsa justo donde más importa.
        localidad = (
            LocalidadSiis.objects.filter(siis_id=loc_id, provincia=provincia).first() if loc_id and provincia else None
        )
        self._log("")
        self._log("   Caso de prueba enviado:", self.style.MIGRATE_HEADING)
        self._log(f"      caso          {envio.formulario_id}")
        self._log(f"      documento     {envio.documento}")
        self._log(f"      estado        {envio.estado}")
        self._log(f"      loc_actual    {loc_id} → {localidad.nombre if localidad else '??? NO ESTÁ EN EL CATÁLOGO'}")
        self._log(f"      prov_actual   {payload.get('prov_actual')} → {provincia.nombre if provincia else '???'}")

    def _cuantos_quedan(self, destino):
        return len(proceso_masivo.ids_de(proceso_masivo.candidatos(destino=destino)))

    def _por_tandas(self, pendientes, destino, aplicar, options):
        """Llama al comando que manda de a ``TANDA`` casos, no todos de una.

        Cada invocación es un proceso aparte --``call_command`` no, pero sí una
        pasada completa que suelta lo que armó--, y sobre todo le pide a la base
        solo los casos de esa tanda. Pasarle el total de una fue lo que mató al
        pod el 01/10 con 7.434 candidatos.

        Corta cuando no queda nadie, o cuando la cuenta deja de bajar: lo que
        queda no se puede mandar --error técnico persistente, rechazo-- y seguir
        insistiendo sería un lazo infinito.
        """
        vuelta = 0
        antes = None
        while pendientes:
            if antes is not None and pendientes >= antes:
                self._log(
                    f"   Quedan {pendientes} y no bajan: lo que falta no se puede mandar. Corto acá.",
                    self.style.WARNING,
                )
                return
            antes = pendientes
            vuelta += 1
            self._log(f"   tanda {vuelta} · {min(pendientes, TANDA)} de {pendientes} pendientes")
            self._correr(
                "procesar_casos_siis",
                "--solo-completos",
                "--total",
                str(min(pendientes, TANDA)),
                "--lote",
                str(options["lote"]),
                "--pausa",
                str(options["pausa"]),
                "--destino",
                destino,
                # Ver el comentario del paso 6: el freno de este comando es el
                # caso de prueba, no una pregunta por tanda.
                "--si",
                *(("--aplicar",) if aplicar else ()),
                *(("--usuario", options["usuario"]) if options["usuario"] else ()),
            )
            if not aplicar:
                # En ensayo nada cambia de estado: una vuelta alcanza para ver qué haría.
                return
            pendientes = self._cuantos_quedan(destino)
        self._log("   No queda ninguno pendiente.", self.style.SUCCESS)

    # ── Orquestación ────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        con_insumos = not options["sin_insumos"]
        arranque = time.monotonic()

        if not aplicar:
            self._log("ENSAYO: no se escribe ni se manda nada. Agregá --aplicar.\n", self.style.WARNING)

        self._paso(1, "Precondiciones")
        self._precondiciones(
            aplicar,
            con_insumos,
            ignorar_corrida=options["ignorar_corrida"],
            motivo=(options["motivo"] or "").strip(),
            usuario=options["usuario"],
        )
        if options["solo_precondiciones"]:
            self._log("\nEstá todo lo que hace falta para arrancar.", self.style.SUCCESS)
            return

        if con_insumos:
            self._paso(2, "Insumos del organismo")
            self._cargar_insumos(options["scripts"], aplicar)

        self._paso(3, "Catálogo geográfico de SIIS")
        self._correr("seed_catalogo_siis")
        provincias, localidades = ProvinciaSiis.objects.count(), LocalidadSiis.objects.count()
        if not provincias or not localidades:
            raise CommandError(
                "El catálogo quedó vacío. Sin él, las localidades se resuelven contra la API de SIIS, "
                "que devuelve posiciones de una lista en vez de ids: las altas entran con el domicilio "
                "equivocado y SIIS las acepta igual."
            )
        self._log(f"   Catálogo: {provincias} provincias · {localidades} localidades")

        self._paso(4, "Completar desde RENAPER")
        self._correr("completar_casos_renaper", *(("--aplicar",) if aplicar else ()), "--lote", "50")

        self._paso(5, "Corregir los datos")
        self._correr(
            "corregir_datos_siis",
            "--fecha-nacimiento-renaper",
            "--heredar-nacimiento",
            "--barrio-generico",
            options["barrio_generico"],
            "--fecha-apoderado",
            options["fecha_apoderado"],
            "--estado-civil-sin-equivalente",
            options["estado_civil_sin_equivalente"],
            "--limite",
            "999999",
            # G3-06: la traza por caso que deja el paso 5 tiene que decir quién
            # corrió el circuito, no quedar sin autor.
            *(("--usuario", options["usuario"]) if options["usuario"] else ()),
            *(("--aplicar",) if aplicar else ()),
        )

        destino = options["destino"]
        pendientes = self._cuantos_quedan(destino)
        if destino == DESTINO_TABLA:
            # Sin caso de prueba ni freno: no se llama a SIIS, así que no hay
            # nada que verificar del otro lado. La revisión es sobre la tabla.
            self._paso(6, f"A la tabla intermedia · {pendientes} casos")
        else:
            self._paso(6, f"Caso de prueba ({pendientes} candidatos esperando)")
            self._verificacion(options["usuario"], aplicar)

        if destino != DESTINO_TABLA and not options["continuar"]:
            self._log("")
            self._log(
                "FRENO. Antes de mandar el resto, alguien tiene que abrir ese caso en SIIS y verificar\n"
                "con qué localidad quedó registrado. Elegí uno del interior, no de Resistencia: una\n"
                "localidad mal mapeada puede coincidir igual si está primera en las dos listas.\n"
                "Verificado eso, volvé a correr con --continuar.",
                self.style.WARNING,
            )
            return

        if destino != DESTINO_TABLA:
            pendientes = self._cuantos_quedan(destino)
            self._paso(7, f"Corrida completa · {pendientes} casos")
        if not pendientes:
            self._log("   No queda ninguno por mandar.", self.style.SUCCESS)
        else:
            self._por_tandas(pendientes, destino, aplicar, options)

        self._log("")
        self._log("Resumen del alta", self.style.MIGRATE_HEADING)
        for estado, etiqueta in (
            (EnvioSIIS.Estado.ENVIADO, "altas hechas en SIIS"),
            (EnvioSIIS.Estado.INCOMPLETO, "les falta un dato"),
            (EnvioSIIS.Estado.RECHAZADO, "rechazadas por SIIS"),
            (EnvioSIIS.Estado.ERROR, "error técnico"),
            (EnvioSIIS.Estado.INCIERTO, "resultado desconocido"),
            (EnvioSIIS.Estado.EN_PROCESO, "todavía en vuelo"),
        ):
            total = EnvioSIIS.objects.filter(estado=estado).values("formulario_id").distinct().count()
            if total:
                self._log(f"   {etiqueta:28} {total:6}")
        quedan = len(proceso_masivo.ids_de(proceso_masivo.candidatos()))
        self._log(f"   {'candidatos que siguen sin alta':28} {quedan:6}")
        self._log(f"\nListo en {time.monotonic() - arranque:.0f} s.", self.style.SUCCESS)
