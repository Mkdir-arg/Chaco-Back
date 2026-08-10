from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from programas.models import Convocatoria, RegistroPausa, Relevamiento, Segmento, Subsegmento
from programas.services.autorizacion import es_admin_becas, puede_gestionar_segmento
from programas.services.pausas import cambiar_pausa

TIPOS = {
    "convocatoria": (Convocatoria, "becas:convocatoria_detalle"),
    "segmento": (Segmento, "becas:segmento_detalle"),
    "subsegmento": (Subsegmento, "becas:subsegmento_detalle"),
    "relevamiento": (Relevamiento, "becas:relevamiento_detalle"),
}


def _segmento_de(objeto):
    if isinstance(objeto, Segmento):
        return objeto
    if isinstance(objeto, Subsegmento):
        return objeto.segmento
    if isinstance(objeto, Convocatoria):
        return objeto.segmento
    return objeto.convocatoria.segmento


@login_required
def gestionar_pausa(request, tipo, pk):
    configuracion = TIPOS.get(tipo)
    if not configuracion:
        raise PermissionDenied("Tipo de elemento no permitido.")
    modelo, redirect_name = configuracion
    objeto = get_object_or_404(modelo, pk=pk)

    if not es_admin_becas(request.user) or not puede_gestionar_segmento(request.user, _segmento_de(objeto)):
        raise PermissionDenied("Solo el Administrador del programa puede pausar este elemento.")

    if request.method == "POST":
        pausar = request.POST.get("accion") == "pausar"
        if pausar == objeto.pausado:
            messages.info(request, "El elemento ya se encuentra en ese estado.")
            return redirect(redirect_name, pk=objeto.pk)
        try:
            cambiar_pausa(objeto, request.user, pausar, request.POST.get("motivo"))
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"{objeto} fue {'pausado' if pausar else 'reanudado'} correctamente.")
            return redirect(redirect_name, pk=objeto.pk)

    historial = RegistroPausa.objects.filter(tipo_entidad=tipo, objeto_id=objeto.pk).select_related("usuario")[:20]
    return render(
        request,
        "programas/becas/pausa_form.html",
        {"objeto": objeto, "tipo": tipo, "historial_pausas": historial},
    )
