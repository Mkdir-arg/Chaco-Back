"""La mesa de Emergencia en el backoffice: bandeja (E2), ficha del caso (E3) y «Nuevo caso».

Las vistas **no tienen reglas del caso**. Cada acción llama a la función de
``programas/services/emergencia.py`` —la misma que usa la API de la app (RU-2)— y traduce
lo que esa función contesta:

* ``PermissionDenied`` → 403. No se atrapa: quien no opera la mesa recibe el 403 del
  servicio y nada cambia (RU-12). La excepción es :class:`CasoDeOtroOperador` (un
  ``PermissionDenied`` con el caso): otro operador tomó el caso después de abrir la
  pantalla, así que se vuelve a la ficha con el mensaje, igual que un ``EstadoCambio``.
* :class:`EstadoCambio` (y ``CasoTomadoPorOtro``) → la pantalla quedó vieja: otra pestaña,
  otro operador, el dispositivo o el cron se adelantaron. Es el 409 de la API; acá se
  vuelve a la ficha —que es recargarla— con el mensaje del servicio, que dice qué pasó
  y qué hacer (RU-20).
* :class:`FaltanPlazas` → se vuelve a abrir la confirmación de derivar con la pregunta.
* ``ValidationError`` → el mensaje del servicio, sin escribir nada.

Los avisos salen por ``messages``, que el shell muestra como toast.
"""

from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from core.rbac import puede
from programas.api.throttles import rechazo_para_mostrar
from programas.forms_emergencia import (
    CancelarDerivacionForm,
    CancelarIngresoMesaForm,
    CerrarAlojadoMesaForm,
    CierreCasoForm,
    ContactoCasoForm,
    DerivarCasoForm,
    FiltrosBandejaForm,
    NuevoCasoMesaForm,
    PanelDerivarForm,
    PrioridadCasoForm,
    ReasignarCasoForm,
    UbicarDomicilioForm,
    aviso_identidad_a_revisar,
)
from programas.mixins_emergencia import MesaPermissionMixin
from programas.models import CasoEmergencia
from programas.respuestas_personas import responder_personas_sugeridas
from programas.selectors import emergencia as selectores
from programas.selectors import emergencia_mesa as mesa
from programas.selectors.emergencia_derivar import clave_de_grupo, pedidas_pendientes
from programas.services import emergencia as servicio
from programas.services.configuracion_emergencia import sla_vigente
from programas.services.emergencia import CasoDeOtroOperador, EstadoCambio, FaltanPlazas
from programas.services.emergencia_cierre import cancelar_ingreso_por_la_mesa
from programas.services.emergencia_cierre_mesa import cerrar_alojado_por_la_mesa, personas_egresadas, reabrir_caso
from programas.services.emergencia_programa import puede_cerrar_y_reabrir, puede_supervisar_la_mesa
from programas.services.estadias import CAP_VER_CIUDADANO

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
        # Una sola vez: ordena la bandeja y cuenta la solapa «Fuera de SLA».
        semaforos = selectores.ids_por_estado_sla(sla, ahora)
        pagina = Paginator(
            selectores.bandeja(filtros, sla=sla, ahora=ahora, semaforos=semaforos), CASOS_POR_PAGINA
        ).get_page(request.GET.get("page"))
        elegidos = {campo: valor for campo, valor in form.limpios().items() if campo not in NO_SON_FILTRO}
        conteos = mesa.conteos_de_solapas(sla, ahora, semaforos=semaforos, usuario_id=request.user.pk)
        solapa = filtros["solapa"]
        contexto = {
            "page_obj": pagina,
            "filas": mesa.filas_de_bandeja(pagina.object_list, request.user, sla, ahora),
            "solapa": solapa,
            "solapa_explicita": form.solapa_explicita(),
            "solapas": self._chips(mesa.SOLAPAS_DE_LA_BANDEJA, solapa, conteos, elegidos),
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
            "url_sin_filtros": _url("emergencia:bandeja", solapa=form.solapa_explicita()),
            "url_nuevo": reverse("emergencia:caso_nuevo"),
        }
        return render(request, TEMPLATE_BANDEJA, contexto)


# ---------------------------------------------------------------------------
# «Nuevo caso» (Formulario 1 desde la mesa)
# ---------------------------------------------------------------------------


class NuevoCasoView(MesaPermissionMixin, View):
    """HU-1.4: la mesa carga lo que llega por teléfono. Nace en gestión, tomado por quien lo carga."""

    def _form(self, *args):
        # Con ``ciudadano.ver`` el DNI busca en el legajo (Hallazgo 15); sin él, el campo es el de siempre.
        url = reverse("emergencia:personas_sugeridas") if puede(self.request.user, CAP_VER_CIUDADANO) else None
        return NuevoCasoMesaForm(*args, url_sugerencias=url)

    def _render(self, request, form, status=200):
        abierto = getattr(form, "caso_abierto", None)
        contexto = {"form": form, "caso_abierto": abierto, "url_caso_abierto": _url_ficha(abierto) if abierto else ""}
        return render(request, TEMPLATE_NUEVO, contexto, status=status)

    def get(self, request):
        return self._render(request, self._form())

    def post(self, request):
        form = self._form(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form, status=400)
        try:
            caso = servicio.crear_caso(
                usuario=request.user,
                origen=CasoEmergencia.Origen.MESA,
                datos_formulario1=form.datos_formulario1(),
                forzar_nuevo_motivo=form.forzar_nuevo_motivo_de_la_mesa(),
            )
        except ValidationError as error:
            form.agregar_errores_del_servicio(rechazo_para_mostrar(request, error))
            return self._render(request, form, status=400)
        messages.success(
            request, f"Caso {caso.numero} cargado. Quedó en gestión, tomado por vos.{aviso_identidad_a_revisar(caso)}"
        )
        return redirect(_url_ficha(caso))


class PersonasSugeridasMesaView(MesaPermissionMixin, View):
    """Sugiere personas **del legajo** mientras la mesa escribe el DNI de «Nuevo caso» (Hallazgo 15).

    Solo lectura y solo JSON, sin RENAPER ni Personas API. Pide **lo mismo que el alta**
    (``emergencia.operar`` o ``supervisar`` en el programa, por el mixin) y la capacidad que ya exige el
    buscador de Dispositivos, ``ciudadano.ver``. Cada sugerencia lleva apellido, nombre y DNI, nada más. El
    servidor sigue validando el DNI al guardar: esto solo completa el campo.
    """

    http_method_names = ["get"]

    def get(self, request):
        return responder_personas_sugeridas(request)


# ---------------------------------------------------------------------------
# E3 · Ficha del caso
# ---------------------------------------------------------------------------


def _ya_pedidas(dispositivo_id, edificio_id):
    """«Ya hay 5 camas pedidas en 2 derivaciones pendientes…» para el modal de derivar, o ``""`` (Cambio 535)."""

    camas, derivaciones = pedidas_pendientes(dispositivo_id, edificio_id)
    if not derivaciones:
        return ""
    en = "1 derivación pendiente" if derivaciones == 1 else f"{derivaciones} derivaciones pendientes"
    pedidas = "1 cama pedida" if camas == 1 else f"{camas} camas pedidas"
    return (
        f"Ya hay {pedidas} en {en} de aceptar acá. No se descuentan de las libres: "
        "se reservan recién cuando la institución acepta."
    )


def _panel_de_la_ficha(request, caso):
    """El panel «Derivar» por edificio y, si la URL lo pide, la confirmación de derivar a una institución."""

    pedido = PanelDerivarForm(request.GET)
    conservados = {clave: pedido.valor(clave) for clave in PARAMETROS_DEL_PANEL}
    panel = mesa.panel_de_derivar(
        caso,
        request.user,
        plazas=pedido.valor("plazas"),
        texto=pedido.valor("q") or "",
        localidad=pedido.valor("localidad_dispositivo") or "",
        grupo=pedido.valor("grupo"),
        url_de_grupo=lambda grupo: _url_ficha(caso, **conservados, grupo=grupo),
        url_de_accion=lambda grupo, pk, plazas: _url_ficha(
            caso, **{**conservados, "plazas": plazas, "grupo": grupo, "derivar": pk}
        ),
    )
    panel["url_volver"] = _url_ficha(caso, **conservados)
    if panel["distancias"] and not getattr(settings, "GOOGLE_MAPS_API_KEY", ""):
        # Sin key de Google no hay botón ni script (issue 1297): «hay Google» se decide acá y el template solo mira esto.
        panel["distancias"] = None
    if panel["distancias"]:
        panel["distancias"]["ubicar_url"] = reverse("emergencia:caso_ubicar_domicilio", args=[caso.pk])
    # Para mostrar, un formulario sin enlazar: así «Plazas a pedir» arranca en el total del grupo.
    panel["form"] = PanelDerivarForm(
        initial={**conservados, "plazas": panel["plazas"], "grupo": pedido.valor("grupo")}, auto_id="panel_%s"
    )
    panel["form"].ofrecer_localidades(panel["localidades"])
    grupo = panel["grupo"]
    elegido = None
    if grupo is not None:
        elegido = next((fila for fila in grupo["instituciones"] if fila["id"] == pedido.valor("derivar")), None)
    confirmacion = None
    if elegido is not None and elegido["marca"] != selectores.MARCA_SIN_PLAZAS:
        faltan = elegido["marca"] == selectores.MARCA_FALTAN
        confirmacion = {
            "titulo": f"Derivar a {elegido['nombre']}",
            "subtitulo": f"{grupo['nombre']} · {elegido['libres']} plazas libres · {elegido['reservadas']} reservadas",
            "tono": "warning" if faltan else "brand",
            "faltan": faltan,
            # La mesa pide: las camas las reserva la institución cuando acepta (Cambio 535).
            "aviso": f"Vas a pedir {panel['plazas']} plazas y hay {elegido['libres']} libres. ¿Seguís?",
            "ya_pedidas": _ya_pedidas(elegido["id"], grupo["edificio_id"]),
            "accion": "Sí, derivar igual" if faltan else "Sí, derivar",
            "form": DerivarCasoForm(
                initial={
                    "dispositivo": elegido["id"],
                    "edificio": grupo["edificio_id"],
                    "plazas": panel["plazas"],
                    "confirmar_faltantes": faltan,
                },
                auto_id="derivar_%s",
            ),
        }
    return panel, confirmacion


def contexto_de_ficha(request, caso, *, atados=None, modal=None, solapa=None):
    """El contexto de la ficha (E3): lo arman el GET y la vuelta de una acción que falló.

    ``atados`` pone formularios ya enlazados (con lo que se mandó y sus errores) en lugar de los
    vacíos y ``modal`` dice cuál modal abre la página, para no perder lo escrito cuando una acción
    falla (Cambio 533). ``solapa`` es la que tiene que quedar a la vista cuando el formulario que
    falló vive en una (el de contactos); sin ella manda ``?tab=`` y, si no vino, la primera (Cambio 589).
    """

    contexto = mesa.ficha_de_caso(caso, request.user, sla_vigente(), timezone.now())
    contexto["solapa"] = mesa.solapa_de_la_ficha(solapa or request.GET.get("tab"))
    contexto["url_ficha"] = _url_ficha(caso)
    if contexto["duplicado"]:
        contexto["duplicado"]["url"] = reverse("emergencia:caso_detalle", args=[contexto["duplicado"]["pk"]])
    if contexto["puede_derivar"]:
        contexto["panel"], contexto["confirmar_derivar"] = _panel_de_la_ficha(request, caso)
    if contexto["puede_actuar"]:
        contexto["form_contacto"] = ContactoCasoForm(auto_id="contacto_%s")
        contexto["form_prioridad"] = PrioridadCasoForm(initial={"prioridad": caso.prioridad}, auto_id="prioridad_%s")
    if contexto["puede_cerrar"]:
        contexto["form_cierre"] = CierreCasoForm(auto_id="cierre_%s")
    if contexto["puede_cancelar_derivacion"]:
        contexto["form_cancelar"] = CancelarDerivacionForm(auto_id="cancelar_%s")
    if contexto["puede_reasignar"]:
        contexto["form_reasignar"] = ReasignarCasoForm(auto_id="reasignar_%s")
    if contexto["puede_cerrar_alojado"]:
        contexto["form_cerrar_alojado"] = CerrarAlojadoMesaForm(auto_id="cerrar_alojado_%s")
    if contexto["puede_cancelar_ingreso"]:
        contexto["form_cancelar_ingreso"] = CancelarIngresoMesaForm(
            initial={"derivacion": contexto["derivacion"]["id"] if contexto["derivacion"] else None},
            auto_id="cancelar_ingreso_%s",
        )
    for clave, form in (atados or {}).items():
        if clave in contexto:
            contexto[clave] = form
    contexto["modal_abierto"] = modal
    return contexto


class CasoDetalleView(MesaPermissionMixin, View):
    """E3: lo relevado, los contactos, la traza y, a la derecha, derivar o la derivación vigente."""

    def get(self, request, pk):
        caso = get_object_or_404(mesa.casos_para_ficha(), pk=pk)
        return render(request, TEMPLATE_FICHA, contexto_de_ficha(request, caso))


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
    #: Dónde vive el formulario en la ficha: su clave en el contexto, su ``auto_id`` y el modal que lo
    #: contiene. Con ellos, un error vuelve a abrir el modal con lo enviado (Cambio 533).
    clave_form = None
    auto_id = None
    modal = None
    #: La solapa de la ficha donde vive el formulario, para que un error la deje a la vista (Cambio 589).
    solapa = None

    def destino(self, caso):
        return _url_ficha(caso)

    def volver_a_mostrar(self, request, caso, form):
        """La ficha otra vez, con el formulario enlazado (lo enviado y el error) y su modal abierto.

        Si quien manda ya no tiene esa acción en la ficha (otro tomó el caso, cambió el estado), no hay
        formulario donde mostrar el error: vuelve el aviso por toast y la ficha, como antes del
        Cambio 533, en vez de un 400 sin el formulario (Cambio 535).
        """

        caso = get_object_or_404(mesa.casos_para_ficha(), pk=caso.pk)
        contexto = contexto_de_ficha(
            request, caso, atados={self.clave_form: form}, modal=self.modal, solapa=self.solapa
        )
        if self.clave_form not in contexto:
            messages.error(request, _errores_de(form))
            return redirect(_url_ficha(caso))
        return render(request, TEMPLATE_FICHA, contexto, status=400)

    def post(self, request, pk):
        caso = get_object_or_404(CasoEmergencia, pk=pk)
        form = None
        if self.form_class is not None:
            form = self.form_class(request.POST, **({"auto_id": self.auto_id} if self.auto_id else {}))
            if not form.is_valid():
                if self.clave_form:
                    return self.volver_a_mostrar(request, caso, form)
                messages.error(request, _errores_de(form))
                return redirect(_url_ficha(caso))
        try:
            aviso = self.ejecutar(request, caso, form)
        except (EstadoCambio, CasoDeOtroOperador) as cambio:
            messages.warning(request, cambio.mensaje)
            return redirect(_url_ficha(caso))
        except FaltanPlazas as faltan:
            return self.faltan_plazas(request, caso, form, faltan)
        except ValidationError as error:
            mensaje = " ".join(error.messages)
            if self.clave_form and form is not None:
                form.add_error(None, mensaje)
                return self.volver_a_mostrar(request, caso, form)
            messages.error(request, mensaje)
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
    clave_form = "form_reasignar"
    auto_id = "reasignar_%s"
    modal = "reasignar"

    def tiene_permiso(self, user):
        return puede_supervisar_la_mesa(user)

    def ejecutar(self, request, caso, form):
        operador = form.cleaned_data["operador"]
        servicio.reasignar_caso(caso, request.user, operador)
        return f"El caso {caso.numero} pasó a {mesa.nombre_de(operador)}."


class CambiarPrioridadView(_AccionDeCasoView):
    form_class = PrioridadCasoForm
    clave_form = "form_prioridad"
    auto_id = "prioridad_%s"
    modal = "prioridad"

    def ejecutar(self, request, caso, form):
        actualizado = servicio.cambiar_prioridad(caso, request.user, form.cleaned_data["prioridad"])
        return f"Prioridad del caso {caso.numero}: {actualizado.get_prioridad_display().lower()}."


class ContactoCasoView(_AccionDeCasoView):
    form_class = ContactoCasoForm
    clave_form = "form_contacto"
    auto_id = "contacto_%s"
    solapa = "contactos"

    def destino(self, caso):
        return _url_ficha(caso, tab=self.solapa)

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
            edificio=form.cleaned_data["edificio"],
            # La ficha siempre deriva desde un grupo del panel: sin edificio es el grupo «sin edificio asignado».
            sin_edificio=form.cleaned_data["edificio"] is None,
        )
        donde = f" ({derivacion.edificio.nombre})" if derivacion.edificio_id else ""
        return f"Caso {caso.numero} derivado a {derivacion.dispositivo.nombre}{donde}. Queda esperando que lo acepten."

    def faltan_plazas(self, request, caso, form, faltan):
        """RN-2.5: no se derivó. Se vuelve a abrir la confirmación, ahora con la pregunta."""

        messages.warning(request, " ".join(faltan.messages))
        edificio = form.cleaned_data["edificio"]
        grupo = clave_de_grupo(edificio.pk if edificio else None, form.cleaned_data["dispositivo"].pk)
        return redirect(
            _url_ficha(
                caso, plazas=form.cleaned_data["plazas"], grupo=grupo, derivar=form.cleaned_data["dispositivo"].pk
            )
        )


class UbicarDomicilioView(MesaPermissionMixin, View):
    """POST del panel «Derivar»: guarda el punto del domicilio que el navegador ubicó con Google (Cambio 520).

    Contesta JSON y no redirige: lo llama ``nodo-derivar-distancias.js`` en segundo plano. Si no se guarda,
    la pantalla sigue con la distancia que ya calculó.
    """

    http_method_names = ["post"]

    def post(self, request, pk):
        caso = get_object_or_404(CasoEmergencia, pk=pk)
        form = UbicarDomicilioForm(request.POST)
        if not form.is_valid():
            return JsonResponse({"guardado": False, "error": _errores_de(form)}, status=400)
        try:
            guardado = servicio.ubicar_domicilio(
                caso, request.user, form.cleaned_data["latitud"], form.cleaned_data["longitud"]
            )
        except ValidationError as error:
            return JsonResponse({"guardado": False, "error": " ".join(error.messages)}, status=400)
        except CasoDeOtroOperador as otro:
            return JsonResponse({"guardado": False, "error": str(otro)}, status=409)
        return JsonResponse({"guardado": guardado})


class CancelarDerivacionView(_AccionDeCasoView):
    form_class = CancelarDerivacionForm
    clave_form = "form_cancelar"
    auto_id = "cancelar_%s"
    modal = "cancelar"

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


class CancelarIngresoMesaView(_AccionDeCasoView):
    """Quien supervisa destraba un ingreso aceptado sin nadie confirmado (Cambio 535). El servicio lo vuelve a exigir."""

    form_class = CancelarIngresoMesaForm
    clave_form = "form_cancelar_ingreso"
    auto_id = "cancelar_ingreso_%s"
    modal = "cancelar_ingreso"

    def tiene_permiso(self, user):
        return puede_supervisar_la_mesa(user)

    def ejecutar(self, request, caso, form):
        actualizado = cancelar_ingreso_por_la_mesa(
            caso=caso,
            usuario=request.user,
            motivo=form.cleaned_data["motivo"],
            derivacion_vista=form.cleaned_data["derivacion"],
        )
        liberadas = actualizado.reservas_liberadas
        camas = "1 cama liberada" if liberadas == 1 else f"{liberadas} camas liberadas"
        return f"Ingreso del caso {caso.numero} cancelado ({camas}). El caso volvió a la mesa."


class _SupervisionDeCasoView(_AccionDeCasoView):
    """Las acciones de ``emergencia.cerrar_reabrir`` (Cambio 588): la vista lo decide y el servicio lo vuelve a exigir."""

    def tiene_permiso(self, user):
        return puede_cerrar_y_reabrir(user)


class CerrarAlojadoMesaView(_SupervisionDeCasoView):
    """Cierra con motivo una familia alojada (o con ingreso parcial) que ya no está; egresa a quien siga adentro."""

    form_class = CerrarAlojadoMesaForm
    clave_form = "form_cerrar_alojado"
    auto_id = "cerrar_alojado_%s"
    modal = "cerrar_alojado"

    def ejecutar(self, request, caso, form):
        cerrado = cerrar_alojado_por_la_mesa(caso, request.user, form.cleaned_data["motivo"])
        egresadas = cerrado.estadias_egresadas
        if not egresadas:
            return f"Caso {caso.numero} cerrado."
        personas = personas_egresadas(egresadas)
        return f"Caso {caso.numero} cerrado ({personas} del dispositivo)."


class ReabrirCasoView(_SupervisionDeCasoView):
    """Reabre un caso cerrado: vuelve al estado anterior al cierre, salvo que la familia ya tenga otro abierto."""

    def ejecutar(self, request, caso, form):
        reabierto = reabrir_caso(caso, request.user)
        return f"Caso {caso.numero} reabierto: vuelve a «{reabierto.get_estado_display()}»."


class CerrarCasoView(_AccionDeCasoView):
    form_class = CierreCasoForm
    clave_form = "form_cierre"
    auto_id = "cierre_%s"
    modal = "cerrar"

    def ejecutar(self, request, caso, form):
        servicio.cerrar_sin_alojamiento(
            caso, request.user, form.cleaned_data["motivo"], form.cleaned_data["observacion"]
        )
        return f"Caso {caso.numero} cerrado sin alojamiento."
