"""La mesa de Emergencia en el backoffice: bandeja (E2), ficha del caso (E3) y «Nuevo caso».

Las vistas **no tienen reglas del caso**. Cada acción llama a la función de
``programas/services/emergencia.py`` —la misma que usa la API de la app (RU-2)— y traduce
lo que esa función contesta:

* ``PermissionDenied`` → 403. No se atrapa: quien no tiene tomado el caso ni supervisa
  recibe el 403 del servicio y nada cambia (RU-12).
* :class:`EstadoCambio` (y ``CasoTomadoPorOtro``) → la pantalla quedó vieja: otra pestaña,
  otro operador, el dispositivo o el cron se adelantaron. Es el 409 de la API; acá se
  vuelve a la ficha —que es recargarla— con el mensaje del servicio, que dice qué pasó
  y qué hacer (RU-20).
* :class:`FaltanPlazas` → se vuelve a abrir la confirmación de derivar con la pregunta.
* ``ValidationError`` → el mensaje del servicio, sin escribir nada.

Los avisos salen por ``messages``, que el shell muestra como toast.
"""

from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from programas.forms_emergencia import (
    CancelarDerivacionForm,
    CierreCasoForm,
    ContactoCasoForm,
    DerivarCasoForm,
    FiltrosBandejaForm,
    NuevoCasoMesaForm,
    PanelDerivarForm,
    PrioridadCasoForm,
    ReasignarCasoForm,
)
from programas.mixins_emergencia import MesaPermissionMixin
from programas.models import CasoEmergencia
from programas.selectors import emergencia as selectores
from programas.selectors import emergencia_mesa as mesa
from programas.services import emergencia as servicio
from programas.services.configuracion_emergencia import sla_vigente
from programas.services.emergencia import EstadoCambio, FaltanPlazas
from programas.services.emergencia_programa import puede_supervisar_la_mesa

TEMPLATE_BANDEJA = "programas/emergencia/casos/list.html"
TEMPLATE_FICHA = "programas/emergencia/casos/detail.html"
TEMPLATE_NUEVO = "programas/emergencia/casos/form.html"

CASOS_POR_PAGINA = 50

#: Parámetros de la bandeja que no son un filtro que el usuario eligió.
NO_SON_FILTRO = ("page", "solapa")
#: Parámetros de la ficha que arman el panel «Derivar» y se conservan al elegir un dispositivo.
PARAMETROS_DEL_PANEL = ("plazas", "q", "localidad_dispositivo")


def _url(nombre, *args, **parametros):
    """``reverse`` más un querystring con los parámetros que traen valor."""

    url = reverse(nombre, args=args)
    consulta = urlencode({clave: valor for clave, valor in parametros.items() if valor not in (None, "")})
    return f"{url}?{consulta}" if consulta else url


def _url_ficha(caso, **parametros):
    return _url("emergencia:caso_detalle", caso.pk, **parametros)


def _errores_de(form):
    """Los errores de un formulario chico en una línea, para el aviso."""

    return " ".join(dict.fromkeys(error for errores in form.errors.values() for error in errores))


# ---------------------------------------------------------------------------
# E2 · Bandeja
# ---------------------------------------------------------------------------


class BandejaCasosView(MesaPermissionMixin, View):
    """E2: los casos de la mesa, por solapa, filtrados y paginados de a 50."""

    def _chips(self, solapas, actual, conteos, filtros_de_usuario):
        return [
            {
                "texto": texto,
                "url": _url("emergencia:bandeja", solapa=solapa, **filtros_de_usuario),
                "activo": solapa == actual,
                "n": conteos.get(solapa, 0),
            }
            for solapa, texto in solapas
        ]

    def get(self, request):
        form = FiltrosBandejaForm(request.GET)
        filtros = form.filtros(request.user)
        sla, ahora = sla_vigente(), timezone.now()
        pagina = Paginator(selectores.bandeja(filtros, sla=sla, ahora=ahora), CASOS_POR_PAGINA).get_page(
            request.GET.get("page")
        )
        elegidos = {campo: valor for campo, valor in form.limpios().items() if campo not in NO_SON_FILTRO}
        conteos = mesa.conteos_de_solapas(sla, ahora)
        solapa = filtros["solapa"]
        contexto = {
            "page_obj": pagina,
            "filas": mesa.filas_de_bandeja(pagina.object_list, request.user, sla, ahora),
            "solapa": solapa,
            "solapas_por_estado": self._chips(mesa.SOLAPAS_POR_ESTADO, solapa, conteos, elegidos),
            "solapas_de_atencion": self._chips(mesa.SOLAPAS_DE_ATENCION, solapa, conteos, elegidos),
            "filtro": elegidos,
            "estados": CasoEmergencia.Estado.choices,
            "prioridades": CasoEmergencia.Prioridad.choices,
            "semaforos": (
                (selectores.SLA_EN_TERMINO, "En término"),
                (selectores.SLA_POR_VENCER, "Por vencer"),
                (selectores.SLA_FUERA, "Fuera de SLA"),
            ),
            "localidades": mesa.localidades_con_casos(),
            "operadores": [(str(operador.pk), mesa.nombre_de(operador)) for operador in mesa.operadores_de_la_mesa()],
            "operador_mios": mesa.OPERADOR_MIOS,
            "hay_casos": conteos["total"] > 0,
            "url_sin_filtros": _url("emergencia:bandeja", solapa=solapa),
            "url_nuevo": reverse("emergencia:caso_nuevo"),
        }
        return render(request, TEMPLATE_BANDEJA, contexto)


# ---------------------------------------------------------------------------
# «Nuevo caso» (Formulario 1 desde la mesa)
# ---------------------------------------------------------------------------


class NuevoCasoView(MesaPermissionMixin, View):
    """HU-1.4: la mesa carga lo que llega por teléfono. Nace en gestión, tomado por quien lo carga."""

    def _render(self, request, form, status=200):
        return render(request, TEMPLATE_NUEVO, {"form": form}, status=status)

    def get(self, request):
        return self._render(request, NuevoCasoMesaForm())

    def post(self, request):
        form = NuevoCasoMesaForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form, status=400)
        try:
            caso = servicio.crear_caso(
                usuario=request.user,
                origen=CasoEmergencia.Origen.MESA,
                datos_formulario1=form.datos_formulario1(),
            )
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._render(request, form, status=400)
        messages.success(request, f"Caso {caso.numero} cargado. Quedó en gestión, tomado por vos.")
        return redirect(_url_ficha(caso))


# ---------------------------------------------------------------------------
# E3 · Ficha del caso
# ---------------------------------------------------------------------------


class CasoDetalleView(MesaPermissionMixin, View):
    """E3: lo relevado, los contactos, la traza y, a la derecha, derivar o la derivación vigente."""

    def _panel(self, request, caso):
        """El panel «Derivar» y, si la URL lo pide, la confirmación de derivar a un dispositivo."""

        pedido = PanelDerivarForm(request.GET)
        conservados = {clave: pedido.valor(clave) for clave in PARAMETROS_DEL_PANEL}
        panel = mesa.panel_de_derivar(
            caso,
            request.user,
            plazas=pedido.valor("plazas"),
            texto=pedido.valor("q") or "",
            localidad=pedido.valor("localidad_dispositivo") or "",
            url_de_accion=lambda pk, plazas: _url_ficha(caso, **{**conservados, "plazas": plazas, "derivar": pk}),
        )
        # Para mostrar, un formulario sin enlazar: así «Plazas a reservar» arranca en el total del grupo.
        panel["form"] = PanelDerivarForm(initial={**conservados, "plazas": panel["plazas"]}, auto_id="panel_%s")
        panel["form"].ofrecer_localidades(panel["localidades"])
        elegido = panel["filas"].get(pedido.valor("derivar"))
        confirmacion = None
        if elegido is not None and elegido["marca"] != selectores.MARCA_SIN_PLAZAS:
            faltan = elegido["marca"] == selectores.MARCA_FALTAN
            confirmacion = {
                "titulo": f"Derivar a {elegido['nombre']}",
                "subtitulo": f"{elegido['libres']} plazas libres · {elegido['reservadas']} reservadas",
                "tono": "warning" if faltan else "brand",
                "faltan": faltan,
                "aviso": f"Vas a reservar {elegido['libres']} de {panel['plazas']} plazas. ¿Seguís?",
                "accion": "Sí, derivar igual" if faltan else "Sí, derivar",
                "form": DerivarCasoForm(
                    initial={"dispositivo": elegido["id"], "plazas": panel["plazas"], "confirmar_faltantes": faltan},
                    auto_id="derivar_%s",
                ),
            }
        return panel, confirmacion

    def get(self, request, pk):
        caso = get_object_or_404(mesa.casos_para_ficha(), pk=pk)
        contexto = mesa.ficha_de_caso(caso, request.user, sla_vigente(), timezone.now())
        contexto["url_ficha"] = _url_ficha(caso)
        if contexto["duplicado"]:
            contexto["duplicado"]["url"] = reverse("emergencia:caso_detalle", args=[contexto["duplicado"]["pk"]])
        if contexto["puede_derivar"]:
            contexto["panel"], contexto["confirmar_derivar"] = self._panel(request, caso)
        if contexto["puede_actuar"]:
            contexto["form_contacto"] = ContactoCasoForm(auto_id="contacto_%s")
            contexto["form_prioridad"] = PrioridadCasoForm(
                initial={"prioridad": caso.prioridad}, auto_id="prioridad_%s"
            )
        if contexto["puede_cerrar"]:
            contexto["form_cierre"] = CierreCasoForm(auto_id="cierre_%s")
        if contexto["puede_cancelar_derivacion"]:
            contexto["form_cancelar"] = CancelarDerivacionForm(auto_id="cancelar_%s")
        if contexto["puede_reasignar"]:
            contexto["form_reasignar"] = ReasignarCasoForm(auto_id="reasignar_%s")
        return render(request, TEMPLATE_FICHA, contexto)


# ---------------------------------------------------------------------------
# Acciones sobre un caso (POST)
# ---------------------------------------------------------------------------


class _AccionDeCasoView(MesaPermissionMixin, View):
    """Una acción POST sobre un caso: llama al servicio y vuelve a la ficha con lo que contestó.

    Las subclases definen ``ejecutar(request, caso)``, que devuelve el aviso de éxito, y, si
    la acción lleva datos, ``form_class``. Lo que el servicio rechace se traduce acá, una
    sola vez (ver el encabezado del módulo).
    """

    http_method_names = ["post"]
    form_class = None

    def destino(self, caso):
        return _url_ficha(caso)

    def post(self, request, pk):
        caso = get_object_or_404(CasoEmergencia, pk=pk)
        form = None
        if self.form_class is not None:
            form = self.form_class(request.POST)
            if not form.is_valid():
                messages.error(request, _errores_de(form))
                return redirect(_url_ficha(caso))
        try:
            aviso = self.ejecutar(request, caso, form)
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return redirect(_url_ficha(caso))
        except FaltanPlazas as faltan:
            return self.faltan_plazas(request, caso, form, faltan)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect(_url_ficha(caso))
        messages.success(request, aviso)
        return redirect(self.destino(caso))

    def faltan_plazas(self, request, caso, form, faltan):
        messages.error(request, " ".join(faltan.messages))
        return redirect(_url_ficha(caso))


class TomarCasoView(_AccionDeCasoView):
    def ejecutar(self, request, caso, form):
        servicio.tomar_caso(caso, request.user)
        return f"Tomaste el caso {caso.numero}."


class SoltarCasoView(_AccionDeCasoView):
    def destino(self, caso):
        return reverse("emergencia:bandeja")

    def ejecutar(self, request, caso, form):
        servicio.soltar_caso(caso, request.user)
        return f"El caso {caso.numero} volvió a la bandeja."


class ReasignarCasoView(_AccionDeCasoView):
    """Solo quien supervisa (HU-2.6, RU §6 n.° 1). El servicio lo vuelve a exigir."""

    form_class = ReasignarCasoForm

    def tiene_permiso(self, user):
        return puede_supervisar_la_mesa(user)

    def ejecutar(self, request, caso, form):
        operador = form.cleaned_data["operador"]
        servicio.reasignar_caso(caso, request.user, operador)
        return f"El caso {caso.numero} pasó a {mesa.nombre_de(operador)}."


class CambiarPrioridadView(_AccionDeCasoView):
    form_class = PrioridadCasoForm

    def ejecutar(self, request, caso, form):
        actualizado = servicio.cambiar_prioridad(caso, request.user, form.cleaned_data["prioridad"])
        return f"Prioridad del caso {caso.numero}: {actualizado.get_prioridad_display().lower()}."


class ContactoCasoView(_AccionDeCasoView):
    form_class = ContactoCasoForm

    def ejecutar(self, request, caso, form):
        servicio.registrar_contacto(caso, request.user, **form.cleaned_data)
        return "Contacto registrado."


class DerivarCasoView(_AccionDeCasoView):
    form_class = DerivarCasoForm

    def ejecutar(self, request, caso, form):
        derivacion = servicio.derivar_caso(
            caso,
            request.user,
            form.cleaned_data["dispositivo"],
            form.cleaned_data["plazas"],
            confirmar_faltantes=form.cleaned_data["confirmar_faltantes"],
        )
        return f"Caso {caso.numero} derivado a {derivacion.dispositivo.nombre}. Queda esperando que lo acepten."

    def faltan_plazas(self, request, caso, form, faltan):
        """RN-2.5: no se derivó. Se vuelve a abrir la confirmación, ahora con la pregunta."""

        messages.warning(request, " ".join(faltan.messages))
        return redirect(
            _url_ficha(caso, plazas=form.cleaned_data["plazas"], derivar=form.cleaned_data["dispositivo"].pk)
        )


class CancelarDerivacionView(_AccionDeCasoView):
    form_class = CancelarDerivacionForm

    def ejecutar(self, request, caso, form):
        derivacion = mesa.derivacion_pendiente_de(caso)
        if derivacion is None:
            raise EstadoCambio(
                f"El caso {caso.numero} ya no tiene una derivación pendiente. Recargá la ficha.",
                estado_actual=caso.estado,
                caso=caso,
            )
        servicio.cancelar_derivacion(derivacion, request.user, form.cleaned_data["motivo"])
        return f"Derivación a {derivacion.dispositivo.nombre} cancelada. El caso volvió a gestión."


class CerrarCasoView(_AccionDeCasoView):
    form_class = CierreCasoForm

    def ejecutar(self, request, caso, form):
        servicio.cerrar_sin_alojamiento(
            caso, request.user, form.cleaned_data["motivo"], form.cleaned_data["observacion"]
        )
        return f"Caso {caso.numero} cerrado sin alojamiento."
