"""Bitácora del turno de un dispositivo (MVP v2, etapa 3 · #697 · P10).

Quién ve qué
------------

* **Leer** la bitácora pide ``dispositivo.ver`` **con alcance** al dispositivo, igual que el
  media de sus adjuntos (`core.views.media`): es el registro diario de la institución, y lo
  ve quien ve la institución.
* **Cargar y corregir** pide ``dispositivo.bitacora`` con alcance; **configurar turnos**,
  ``dispositivo.editar`` con alcance. Lo verifica el servicio
  (`programas.services.bitacora`), que es el que tiene la regla; las vistas de POST solo
  exigen la capacidad en el programa para no llegar hasta ahí sin ella, y traducen el
  ``PermissionDenied`` del servicio a un 403.
* Las personas involucradas se **nombran** solo con ``ciudadano.ver`` (Cambio 271).

Lo que no se duplica
--------------------

Que una novedad sea del turno en curso, que las personas estuvieran alojadas en ese
momento, el tope de adjuntos y la superposición de turnos son reglas del servicio. La vista
no las repite: si el servicio rechaza, muestra su mensaje en el campo que corresponde.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView

from core import rbac
from programas.forms_dispositivos import CorreccionForm, NovedadForm, TurnoForm
from programas.mixins_dispositivos import DispositivoObjectPermissionMixin, DispositivoProgramaPermissionMixin
from programas.models import Dispositivo
from programas.services.bitacora import (
    CAP_BITACORA,
    CAP_EDITAR,
    corregir_entrada,
    crear_turno,
    editar_turno,
    registrar_entrada,
)
from programas.services.bitacora_pantalla import pantalla_bitacora
from programas.services.dispositivos import puede_operar_dispositivo
from programas.views.ajax_utils import ajax_redirect, is_ajax

CAP_VER = "dispositivo.ver"
CAP_VER_CIUDADANO = "ciudadano.ver"


class BitacoraTurnoView(DispositivoObjectPermissionMixin, DetailView):
    """P10: los turnos del día, sus novedades, el censo calculado y los modales de carga."""

    capacidad_requerida = CAP_VER
    model = Dispositivo
    template_name = "programas/dispositivos/bitacora/bitacora.html"
    context_object_name = "dispositivo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dispositivo = self.object
        usuario = self.request.user
        puede_cargar = puede_operar_dispositivo(usuario, dispositivo, CAP_BITACORA)
        puede_configurar = puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR)
        nombrar_personas = rbac.puede(usuario, CAP_VER_CIUDADANO)
        url_base = reverse("dispositivos:bitacora", args=[dispositivo.pk])

        datos = pantalla_bitacora(
            dispositivo,
            fecha=self.request.GET.get("fecha"),
            turno_id=self.request.GET.get("turno"),
            tipo=self.request.GET.get("tipo", ""),
            puede_cargar=puede_cargar,
            puede_configurar=puede_configurar,
            nombrar_personas=nombrar_personas,
            url_base=url_base,
        )
        context.update(datos)
        context["puede_configurar"] = puede_configurar
        if datos["puede_cargar"]:
            context["form_novedad"] = NovedadForm(personas=datos["personas"], max_adjuntos=datos["max_adjuntos"])
            if datos["corregibles"]:
                context["form_correccion"] = CorreccionForm(
                    corregibles=[(item["pk"], item["etiqueta"]) for item in datos["corregibles"]]
                )
                context["corregibles_datos"] = {
                    str(item["pk"]): {"tipo": item["tipo"], "texto": item["texto"]} for item in datos["corregibles"]
                }
        if puede_configurar:
            context["form_turno"] = TurnoForm(
                turnos=[(item["pk"], item["etiqueta"]) for item in datos["turnos_config"]]
            )
            context["turnos_datos"] = {
                str(item["pk"]): {
                    "nombre": item["nombre"],
                    "desde": item["desde"],
                    "hasta": item["hasta"],
                    "orden": str(item["orden"]),
                    "activo": item["activo"],
                }
                for item in datos["turnos_config"]
            }
        # Los modales se piden por GET (`?novedad=1`, `?corregir=<id>`, `?turnos=1`), como en
        # Configuración: las acciones de la tarjeta del turno son enlaces a esta pantalla, y la
        # vista decide si el modal arranca abierto. Solo si el usuario lo puede usar.
        parametros = self.request.GET
        context["abrir_modal_novedad"] = "novedad" in parametros and "form_novedad" in context
        context["abrir_modal_turnos"] = "turnos" in parametros and puede_configurar
        pedida = parametros.get("corregir", "")
        context["correccion_inicial"] = pedida if pedida in context.get("corregibles_datos", {}) else ""
        context["abrir_modal_corregir"] = bool(context["correccion_inicial"])
        context["migas"] = [
            {"label": "Dispositivos", "url": reverse("dispositivos:lista")},
            {"label": dispositivo.nombre, "url": reverse("dispositivos:detalle", args=[dispositivo.pk])},
            {"label": "Bitácora", "url": ""},
        ]
        return context


def _errores_del_servicio(error, form):
    """Lo que el servicio rechaza, en la forma ``{campo: [mensajes]}`` del modal.

    Una clave que el formulario no tiene (``turno``, ``dispositivo``, ``entrada`` cuando el
    form no la lleva) va al error general, el único lugar donde el modal la puede mostrar.
    Un error sin campo (el de formato de un adjunto) también.
    """

    if not hasattr(error, "error_dict"):
        return {"__all__": list(error.messages)}
    errores = {}
    for campo, mensajes in error.message_dict.items():
        destino = campo if campo in form.fields else "__all__"
        errores.setdefault(destino, []).extend(mensajes)
    return errores


def _rechazar(request, errores, volver):
    if is_ajax(request):
        return JsonResponse({"ok": False, "errors": {k: list(v) for k, v in errores.items()}}, status=400)
    for mensajes in errores.values():
        for mensaje in mensajes:
            messages.error(request, mensaje)
    return redirect(volver)


def _sin_alcance(request, mensaje):
    if is_ajax(request):
        return JsonResponse({"ok": False, "message": mensaje}, status=403)
    raise PermissionDenied(mensaje)


class _BitacoraPostView(DispositivoProgramaPermissionMixin, View):
    """Base de los POST del modal: la capacidad en el programa la exige el mixin; el
    alcance al dispositivo, una compuerta acá y el servicio, que conserva su regla.

    La compuerta va **antes** de validar el formulario: si no, quien no opera el
    dispositivo recibiría 403 con un id ajeno y 400 con uno inexistente, y podría
    distinguirlos (un oráculo de ids de otras instituciones).
    """

    http_method_names = ["post"]
    form_class = None
    mensaje_exito = ""

    def post(self, request, pk):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        volver = reverse("dispositivos:bitacora", args=[dispositivo.pk])
        if not puede_operar_dispositivo(request.user, dispositivo, self.capacidad_requerida):
            return _sin_alcance(request, "No tenés alcance sobre este dispositivo.")
        form = self.armar_form(request, dispositivo)
        if not form.is_valid():
            return _rechazar(request, form.errors, volver)
        try:
            self.ejecutar(request, dispositivo, form.cleaned_data)
        except PermissionDenied as error:
            return _sin_alcance(request, str(error) or "No tenés permiso para realizar esta acción.")
        except ValidationError as error:
            return _rechazar(request, _errores_del_servicio(error, form), volver)
        if is_ajax(request):
            return ajax_redirect(request, volver, self.mensaje_exito)
        messages.success(request, self.mensaje_exito)
        return redirect(volver)


class NovedadCrearView(_BitacoraPostView):
    """Carga una novedad del turno en curso."""

    capacidad_requerida = CAP_BITACORA
    mensaje_exito = "Novedad cargada en la bitácora."

    def armar_form(self, request, dispositivo):
        return NovedadForm(
            request.POST,
            request.FILES,
            personas=[(valor, valor) for valor in request.POST.getlist("personas")],
        )

    def ejecutar(self, request, dispositivo, datos):
        # Sin `ciudadano.ver` el modal no ofrece personas: si llegan igual, no se vinculan.
        personas = datos["personas"] if rbac.puede(request.user, CAP_VER_CIUDADANO) else ()
        registrar_entrada(
            dispositivo=dispositivo,
            usuario=request.user,
            tipo=datos["tipo"],
            texto=datos["texto"],
            momento=datos["momento"],
            personas=personas,
            adjuntos=datos["adjuntos"],
        )


class NovedadCorregirView(_BitacoraPostView):
    """Corrige una novedad agregando una versión: la anterior sigue visible."""

    capacidad_requerida = CAP_BITACORA
    mensaje_exito = "Novedad corregida: la versión anterior sigue visible."

    def armar_form(self, request, dispositivo):
        return CorreccionForm(request.POST, dispositivo=dispositivo)

    def ejecutar(self, request, dispositivo, datos):
        corregir_entrada(
            entrada=datos["entrada"],
            usuario=request.user,
            texto=datos["texto"],
            tipo=datos["tipo"],
            motivo=datos["motivo"],
        )


class TurnoGuardarView(_BitacoraPostView):
    """Alta (sin `turno`) o edición de un turno del dispositivo."""

    capacidad_requerida = CAP_EDITAR
    mensaje_exito = "Turno guardado."

    def armar_form(self, request, dispositivo):
        return TurnoForm(request.POST, dispositivo=dispositivo)

    def ejecutar(self, request, dispositivo, datos):
        orden = datos["orden"] if datos["orden"] is not None else 0
        if datos["turno"] is None:
            crear_turno(
                dispositivo=dispositivo,
                usuario=request.user,
                nombre=datos["nombre"],
                hora_desde=datos["hora_desde"],
                hora_hasta=datos["hora_hasta"],
                orden=orden,
            )
            return
        editar_turno(
            turno=datos["turno"],
            usuario=request.user,
            nombre=datos["nombre"],
            hora_desde=datos["hora_desde"],
            hora_hasta=datos["hora_hasta"],
            orden=orden,
            activo=datos["activo"],
        )
