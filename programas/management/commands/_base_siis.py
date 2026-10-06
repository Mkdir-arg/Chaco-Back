"""Base común de los comandos que hablan con SIIS caso por caso (RED-53).

Los cuatro —``validar_casos_siis``, ``enviar_casos_siis``, ``procesar_casos_siis``
y ``reenviar_siis_pendientes``— hacían lo mismo copiado: los mismos flags, el
mismo `_solicitante`, el mismo troceado en lotes, el mismo freno por errores
seguidos y el mismo resumen. El riesgo no es la duplicación en sí: es que una
guarda nueva se agregue en dos de ellos y el tercero quede como una puerta
abierta, que es exactamente cómo apareció la séptima vía de alta de SIIS-01. El
candado de corrida viva de SIIS-03 —que era el ejemplo— ya vive acá:
:meth:`ComandoSiisBase.exigir_sin_corrida_viva`.

``correr_alta_siis`` no hereda: no habla con SIIS, encadena a estos.
"""

import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from programas.services import proceso_masivo

# Lo que comparten los cuatro. Si un flag nuevo tiene sentido para más de uno,
# va acá: así nadie se entera tarde de que en un comando no existe.
LOTE_POR_DEFECTO = 50
MAX_ERRORES_POR_DEFECTO = proceso_masivo.MAX_ERRORES
MAX_INCIERTOS_POR_DEFECTO = proceso_masivo.MAX_INCIERTOS

AYUDA_APLICAR = "Ejecuta de verdad. Sin esto solo cuenta e informa, sin llamar a SIIS."
AYUDA_MAX_ERRORES = "Errores técnicos seguidos que detienen la corrida. Por defecto {}."
AYUDA_MAX_INCIERTOS = (
    "Envíos seguidos sin saber si el alta llegó que detienen la corrida. Por defecto {}: el tope es "
    "más bajo que el de errores porque cada uno deja un caso tomado hasta conciliarlo con ECOM."
)
AYUDA_USUARIO = "Nombre de usuario que queda como responsable en los registros y en la traza."
AYUDA_IGNORAR_CORRIDA = (
    "Corre aunque la pantalla del proceso masivo tenga una corrida en curso. Solo para emergencias: "
    "los dos caminos procesan los mismos casos y el alta en SIIS no tiene baja. Exige --motivo."
)
AYUDA_MOTIVO = (
    "Por qué se ignora la corrida en curso. Obligatorio con --ignorar-corrida; queda en el log y en la corrida."
)
FALTA_MOTIVO = (
    "--ignorar-corrida necesita --motivo: es la única guarda del circuito que se puede saltear a mano, "
    "así que tiene que quedar escrito quién lo hizo y por qué."
)


class ComandoSiisBase(BaseCommand):
    """Flags, lotes, resumen y frenos compartidos por los comandos de SIIS."""

    #: Lo pisan los comandos cuyo lote natural es otro (el masivo usa 40).
    lote_por_defecto = LOTE_POR_DEFECTO

    def add_arguments(self, parser):
        self.agregar_flags_comunes(parser)

    def agregar_flags_comunes(self, parser):
        parser.add_argument("--aplicar", action="store_true", help=AYUDA_APLICAR)
        parser.add_argument(
            "--lote",
            type=int,
            default=self.lote_por_defecto,
            help=f"Casos por lote. Por defecto {self.lote_por_defecto}.",
        )
        parser.add_argument("--pausa", type=float, default=0.0, help="Segundos de espera entre lotes. Por defecto 0.")
        parser.add_argument(
            "--max-errores",
            type=int,
            default=MAX_ERRORES_POR_DEFECTO,
            help=AYUDA_MAX_ERRORES.format(MAX_ERRORES_POR_DEFECTO),
        )
        parser.add_argument(
            "--max-inciertos",
            type=int,
            default=MAX_INCIERTOS_POR_DEFECTO,
            help=AYUDA_MAX_INCIERTOS.format(MAX_INCIERTOS_POR_DEFECTO),
        )
        parser.add_argument("--usuario", default=None, help=AYUDA_USUARIO)
        parser.add_argument("--ignorar-corrida", action="store_true", help=AYUDA_IGNORAR_CORRIDA)
        parser.add_argument("--motivo", default="", help=AYUDA_MOTIVO)

    # ── Guardas ─────────────────────────────────────────────────────────────

    def exigir_sin_corrida_viva(self, options):
        """Corta si la pantalla del proceso masivo está corriendo (SIIS-03).

        Va al principio del ``handle()`` de los cuatro, y por eso vive acá: el
        día que esta guarda cambie, cambia en los cuatro. Lo que la hace
        necesaria es que el hilo del masivo y un comando a mano toman los mismos
        casos y llevan **su propio** freno por errores seguidos, así que con SIIS
        lento ninguno de los dos corta a tiempo; y un alta de más no se deshace.

        Solo con ``--aplicar``: mirar qué haría no toca nada, y durante una
        corrida es justo cuando alguien quiere mirar.

        ``--ignorar-corrida`` es la salida de emergencia y **no es gratis**: pide
        ``--motivo`` y deja rastro en el log y en la corrida que pisa
        (``proceso_masivo.registrar_corrida_ignorada``). Una guarda que se puede
        saltear en silencio no es una guarda.
        """
        if not options.get("aplicar"):
            return
        if options.get("ignorar_corrida"):
            motivo = (options.get("motivo") or "").strip()
            if not motivo:
                raise CommandError(FALTA_MOTIVO)
            self._log(
                "--ignorar-corrida: se corre aunque haya una corrida en curso. Los dos caminos toman los mismos casos.",
                self.style.WARNING,
            )
            proceso_masivo.registrar_corrida_ignorada(
                self.__module__.rsplit(".", 1)[-1], motivo, usuario=options.get("usuario")
            )
            return
        try:
            proceso_masivo.exigir_sin_corrida_viva()
        except proceso_masivo.CorridaEnCurso as exc:
            raise CommandError(str(exc)) from exc

    # ── Salida ──────────────────────────────────────────────────────────────

    def _log(self, texto="", estilo=None):
        self.stdout.write(estilo(texto) if estilo else texto)
        self.stdout.flush()

    def _resumen(self, filas, ancho=40):
        """Imprime el bloque «Resumen» con una fila ``(etiqueta, número)`` por línea."""
        self._log("")
        self._log("Resumen", self.style.MIGRATE_HEADING)
        for etiqueta, numero in filas:
            self._log(f"   {etiqueta:{ancho}} {numero:6}")

    def _avisar_ensayo(self, aplicar, texto):
        if not aplicar:
            self._log(f"ENSAYO: {texto}\n", self.style.WARNING)
        self._log(f"SIIS: {settings.SIIS_API_URL}")

    def _crear_freno(self, options):
        """El freno de la corrida, con los topes que pidió el operador.

        Uno solo para las cuatro vías —los tres comandos que heredan de acá y el
        hilo del masivo—: si el criterio de corte vive en cuatro lados, el día
        que cambie va a cambiar en tres. **Tenerlo no alcanza: hay que usarlo.**
        `reenviar_siis_pendientes` aceptaba los dos flags y los ignoraba, así que
        con SIIS contestando ambiguo se comía los 200 casos de su `--limite`; por
        eso `FrenoConSiisCaidoTests` ejercita las cuatro con SIIS caído y no solo
        mira que el flag exista (RED-53).
        """
        return proceso_masivo.Freno(
            max_errores=max(1, options["max_errores"]), max_inciertos=max(1, options["max_inciertos"])
        )

    def _cortado_por_fallas(self, freno, segundos, cola):
        """El mensaje del freno, igual en los cuatro. Nunca vuelve: corta con 1."""
        self._log(f"\nDETENIDO en {segundos:.0f} s tras {freno.motivo}. {cola}", self.style.ERROR)
        raise SystemExit(1)

    # ── Insumos ─────────────────────────────────────────────────────────────

    def _solicitante(self, nombre):
        if not nombre:
            return None
        usuario = get_user_model().objects.filter(username=nombre).first()
        if usuario is None:
            raise CommandError(f"No existe el usuario «{nombre}».")
        return usuario

    # Nombre histórico del mismo método en ``procesar_casos_siis``.
    _responsable = _solicitante

    def _exigir_credenciales(self):
        if not (settings.SIIS_API_CLIENT_ID and settings.SIIS_API_CLIENT_SECRET):
            raise CommandError("Faltan SIIS_API_CLIENT_ID / SIIS_API_CLIENT_SECRET en el entorno.")

    # ── Troceado ────────────────────────────────────────────────────────────

    @staticmethod
    def _lotes(lista, tamano):
        """``(numero_de_lote, lote)``, numerando desde 1."""
        for inicio in range(0, len(lista), tamano):
            yield inicio // tamano + 1, lista[inicio : inicio + tamano]

    @staticmethod
    def _reloj():
        return time.monotonic()
