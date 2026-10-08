"""Proceso masivo a SIIS: pantalla no listada para lanzar el circuito en lote.

No figura en ningún menú ni link, pero lo que la protege es la capacidad
``becas.programa.proceso_masivo``, no el hecho de estar escondida: esconder un
botón que aprueba mil casos y los registra en un sistema provincial es
prolijidad, no seguridad.
"""

from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic.detail import DetailView

from core import rbac
from core.rbac import CapacidadRequeridaMixin, requiere
from programas.models import CorridaSiis, ProgramaSiis

# Alias: este módulo ya se llama proceso_masivo; sin él, dentro del archivo
# ``proceso_masivo`` sería ambiguo para quien lo lea.
from programas.services import proceso_masivo as servicio
from programas.services.autorizacion import programa_becas

CAP_PROCESO_MASIVO = "becas.programa.proceso_masivo"
TOTAL_MAXIMO = 5000
MENSAJE_EN_CURSO = "Ya hay una corrida en curso. Esperá a que termine o frenala."
#: Segundos que valen los dos conteos de la pantalla (PERF-07). Un número **mayor que
#: cero** es informativo: se usa para decidir cuánto pedir, y quien lanza vuelve a
#: contar del otro lado, así que un minuto de desfasaje no cambia ninguna decisión y
#: saca el `count()` caro del camino.
#:
#: El cero, en cambio, **decide**: con 0 pendientes la plantilla esconde el formulario
#: y dice «si entran casos nuevos, aparecen acá al recargar». Cacheado, esa frase era
#: mentira hasta por un minuto —y la pantalla queda abierta justo cuando alguien espera
#: que entren—. Por eso el cero no se guarda (ver `_conteos`), y el fin de una corrida,
#: que es lo que lo vacía de golpe, invalida la clave (`servicio.invalidar_conteos`).
VIGENCIA_CONTEOS = 60


def _asegurar_alcance(user):
    """La capacidad se evalúa **contra el Programa Becas** (SEC-06).

    ``@requiere`` y ``CapacidadRequeridaMixin`` la pedían sin alcance, y
    ``becas.programa.proceso_masivo`` es de un módulo "de programa": un rol de
    **otro** programa con la capacidad tildada entraba acá y lanzaba altas en lote
    contra SIIS, que **no tienen baja**. El decorador sigue siendo la puerta (anónimo →
    login, sin la capacidad → redirect con mensaje); esto agrega el alcance.
    ``programa_becas()`` falla cerrado si el programa no está configurado (RED-56).
    """
    if not rbac.puede(user, CAP_PROCESO_MASIVO, programa=programa_becas(user)):
        raise PermissionDenied("No tiene el proceso masivo del programa Becas.")


class ProcesoMasivoView(CapacidadRequeridaMixin, LoginRequiredMixin, DetailView):
    model = ProgramaSiis
    # El mixin sigue siendo la puerta (anónimo → login, sin la capacidad → redirect con
    # mensaje); el alcance lo agrega ``dispatch``, que es donde ya hay ``request.user``.
    capacidades_requeridas = CAP_PROCESO_MASIVO
    template_name = "programas/becas/config/proceso_masivo.html"
    context_object_name = "programa"

    def get(self, request, *args, **kwargs):
        _asegurar_alcance(request.user)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["corrida"] = CorridaSiis.objects.filter(programa=self.object).order_by("-creado").first()
        en_curso = CorridaSiis.en_curso()
        ctx["en_curso"] = en_curso
        # A5-33: la corrida es una sola en todo el sistema (Cambio 88), pero puede
        # ser de otro programa. Esa no se frena desde acá, así que tampoco se
        # ofrece el botón: frenarla era el bug.
        ctx["en_curso_de_otro_programa"] = en_curso is not None and en_curso.programa_id != self.object.pk
        ctx["total_maximo"] = TOTAL_MAXIMO
        # RED-61: el alta en SIIS no tiene baja, así que el destino se ve antes
        # de lanzar. El host sale de SIIS_API_URL, que ya no tiene default.
        ctx["siis_host"] = urlparse(settings.SIIS_API_URL).netloc or settings.SIIS_API_URL
        # Cambio 90: sin la tabla que decide quién va, la pantalla no ofrece
        # lanzar nada. Se muestra el motivo en vez de un 500. La **existencia** se
        # pregunta al catálogo; leer los 15.531 DNI para enterarse era el primer
        # cuarto del costo de esta pantalla (PERF-07).
        ctx["pendientes"] = None
        ctx["incompatibles"] = None
        ctx["tabla_materias_faltante"] = not servicio.hay_aprobados_materias()
        if ctx["tabla_materias_faltante"]:
            ctx["motivo_bloqueo"] = str(servicio.TablaAprobadosMateriasFaltante())
            return ctx
        # PERF-07: con una corrida en curso la plantilla **no** muestra ninguno de los
        # dos números —muestra el progreso— y se relee sola cada 5 s, en el mismo
        # proceso que la corrida. Calcularlos era un `count()` de 188 KB de SQL (la
        # lista de DNI habilitados viaja como literales) cada cinco segundos.
        if en_curso is not None:
            return ctx
        # BEC-11: los que SIIS declaró incompatibles ya no son candidatos —si no, la
        # corrida los vuelve a consultar en cada vuelta—, pero tienen que verse: son
        # casos esperando que alguien decida, no casos resueltos. Los dos salen del
        # mismo cálculo porque comparten los insumos.
        ctx["pendientes"], ctx["incompatibles"] = _conteos(self.object)
        return ctx


def _conteos(programa):
    """Los dos números de la pantalla, cacheados **salvo cuando el primero es cero**.

    `cache.get_or_set` no sirve acá: guarda lo que devuelva el callable, y guardar el
    cero es justo lo que deja el formulario escondido un minuto después de que entre
    un caso nuevo. Con pendientes, el valor se cachea como siempre: ahí el `count()`
    caro es el que vale la pena ahorrar.
    """
    clave = servicio.clave_conteos(programa.pk)
    cacheado = cache.get(clave)
    if cacheado is not None:
        return cacheado
    conteos = servicio.conteos_de_la_pantalla(programa)
    if conteos[0]:
        cache.set(clave, conteos, VIGENCIA_CONTEOS)
    return conteos


@login_required
@requiere(CAP_PROCESO_MASIVO)
@require_POST
def proceso_masivo_lanzar(request, pk):
    """Crea la corrida y devuelve enseguida: el trabajo sigue en un hilo."""
    _asegurar_alcance(request.user)
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    destino = redirect("becas:proceso_masivo", pk=programa.pk)

    # Chequeo barato para no tomar el candado global en el caso común («ya hay
    # una»); el que decide es el del servicio, que corre con el candado tomado.
    if CorridaSiis.en_curso() is not None:
        messages.error(request, MENSAJE_EN_CURSO)
        return destino
    # Cambio 90: se comprueba antes de crear la corrida. Si faltara la tabla, el
    # hilo la detendría igual, pero mejor no dejar una corrida DETENIDA por algo
    # que se puede avisar de entrada.
    try:
        servicio.dnis_aprobados_materias()
    except servicio.TablaAprobadosMateriasFaltante as exc:
        messages.error(request, str(exc))
        return destino

    try:
        total = int(request.POST.get("total_pedido") or 0)
    except ValueError:
        total = 0
    if not 1 <= total <= TOTAL_MAXIMO:
        messages.error(request, f"La cantidad tiene que estar entre 1 y {TOTAL_MAXIMO}.")
        return destino

    corrida = servicio.crear_corrida(programa=programa, solicitada_por=request.user, total_pedido=total)
    if corrida is None:
        # Otro request ganó la carrera mientras esperábamos el candado.
        messages.error(request, MENSAJE_EN_CURSO)
        return destino
    servicio.lanzar(corrida, responsable=request.user)
    messages.success(request, f"Corrida lanzada por {total} casos.")
    return destino


@login_required
@requiere(CAP_PROCESO_MASIVO)
@require_POST
def proceso_masivo_frenar(request, pk):
    """Pide el freno. **No** cambia el estado: eso lo hace el proceso.

    El estado final lo escribe quien está corriendo, al terminar el caso que
    tiene entre manos. Si lo marcara este request, la pantalla diría «cancelada»
    mientras el hilo todavía está mandando un alta.

    Dos cosas que no son obvias y que costaron dos hallazgos (SIIS-03):

    * se marca **por programa**, no la corrida viva que haya. El botón está en la
      pantalla de un programa, y con el filtro global frenaba la corrida de otro
      (A5-33);
    * no se filtra por latido. ``en_curso()`` descarta las que no dan señales, y
      una corrida lenta —o un pod que tarda en escribir— aparecía «interrumpida»
      y entonces el botón decía «no hay ninguna corrida» mientras el hilo seguía
      informando altas (V2-NEW-01). Si de verdad está muerta, marcarla no hace
      nada; si no lo está, es justo la que hay que frenar.
    """
    _asegurar_alcance(request.user)
    programa = get_object_or_404(ProgramaSiis, pk=pk)
    frenadas = CorridaSiis.objects.filter(estado=CorridaSiis.Estado.EN_CURSO, programa=programa).update(
        cancelacion_pedida=True
    )
    if not frenadas:
        messages.info(request, "No hay ninguna corrida en curso de este programa.")
    else:
        messages.success(
            request,
            "Se pidió frenar. El proceso corta al terminar el caso que está procesando: "
            "puede tardar un par de minutos si SIIS está lento.",
        )
    return redirect("becas:proceso_masivo", pk=programa.pk)
