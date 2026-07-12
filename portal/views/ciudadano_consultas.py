from django.shortcuts import redirect, render

from core.decorators import ciudadano_required

from ..forms import CiudadanoEnviarMensajeForm, CiudadanoNuevaConsultaForm
from ..selectors import (
    get_ciudadano_conversacion_or_404,
    get_ciudadano_conversaciones,
    get_ciudadano_perfil,
)
from ..services.consultas import (
    crear_consulta_ciudadana,
    crear_mensaje_ciudadano_desde_portal,
)


@ciudadano_required
def ciudadano_mis_consultas(request):
    ciudadano = get_ciudadano_perfil(request.user)
    context = {
        "ciudadano": ciudadano,
        "conversaciones": get_ciudadano_conversaciones(request.user, ciudadano),
    }
    return render(request, "portal/ciudadano/mis_consultas.html", context)


@ciudadano_required
def ciudadano_consulta_detalle(request, pk):
    ciudadano = get_ciudadano_perfil(request.user)
    conversacion = get_ciudadano_conversacion_or_404(request.user, ciudadano, pk)
    context = {
        "ciudadano": ciudadano,
        "conversacion": conversacion,
        # .all() reusa el prefetch del selector (Meta.ordering ya es fecha_envio)
        "mensajes": conversacion.mensajes.all(),
        "puede_enviar": conversacion.estado != "cerrada",
        "mensaje_form": CiudadanoEnviarMensajeForm(),
    }
    return render(request, "portal/ciudadano/consulta_detalle.html", context)


@ciudadano_required
def ciudadano_nueva_consulta(request):
    ciudadano = get_ciudadano_perfil(request.user)
    form = CiudadanoNuevaConsultaForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        conversacion = crear_consulta_ciudadana(
            ciudadano=ciudadano,
            user=request.user,
            motivo=form.cleaned_data["motivo"],
        )
        return redirect("portal:ciudadano_consulta_detalle", pk=conversacion.pk)

    return render(
        request,
        "portal/ciudadano/nueva_consulta.html",
        {
            "ciudadano": ciudadano,
            "form": form,
        },
    )


@ciudadano_required
def ciudadano_enviar_mensaje(request, pk):
    ciudadano = get_ciudadano_perfil(request.user)
    conversacion = get_ciudadano_conversacion_or_404(request.user, ciudadano, pk)
    form = CiudadanoEnviarMensajeForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        crear_mensaje_ciudadano_desde_portal(
            conversacion=conversacion,
            texto=form.cleaned_data["texto"],
        )

    return redirect("portal:ciudadano_consulta_detalle", pk=pk)
