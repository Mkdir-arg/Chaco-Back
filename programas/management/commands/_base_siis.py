"""Base común de los comandos que hablan con SIIS caso por caso (RED-53).

Los cuatro —``validar_casos_siis``, ``enviar_casos_siis``, ``procesar_casos_siis``
y ``reenviar_siis_pendientes``— hacían lo mismo copiado: los mismos flags, el
mismo `_solicitante`, el mismo troceado en lotes, el mismo freno por errores
seguidos y el mismo resumen. El riesgo no es la duplicación en sí: es que una
guarda nueva (el candado de corrida viva de SIIS-03, por ejemplo) se agregue en
dos de ellos y el tercero quede como una puerta abierta, que es exactamente cómo
apareció la séptima vía de alta de SIIS-01.

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
    "Resultados de resultado desconocido seguidos que detienen la corrida. Por defecto {}: el tope es "
    "más bajo que el de errores porque cada uno deja un caso tomado hasta conciliarlo con ECOM."
)
AYUDA_USUARIO = "Nombre de usuario que queda como responsable en los registros y en la traza."


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

        Uno solo para las tres vías (las dos de acá y el hilo del masivo): si el
        criterio de corte vive en tres lados, el día que cambie va a cambiar en
        dos — que es exactamente lo que RED-53 mide.
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
