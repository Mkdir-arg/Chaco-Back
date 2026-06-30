from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import DerivarProgramaForm
from ..models import Ciudadano


@login_required
def derivar_programa_view(request, ciudadano_id):
    """Pantalla de derivación/inscripción de ciudadanos a programas activos."""
    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
    puede_inscripcion_directa = request.user.is_staff

    payload = request.POST
    if request.method == "POST" and "programa_destino" in request.POST and "institucion_programa" not in request.POST:
        payload = request.POST.copy()
        payload["institucion_programa"] = request.POST.get("programa_destino", "")

    if request.method == "POST":
        form = DerivarProgramaForm(
            payload,
            ciudadano=ciudadano,
            allow_inscripcion_directa=puede_inscripcion_directa,
        )
        if form.is_valid():
            resultado = form.save(usuario=request.user)
            objeto = resultado["objeto"]

            if resultado["tipo"] == "inscripcion":
                messages.success(
                    request,
                    f"{ciudadano.nombre_completo} fue inscrito/a directamente en {objeto.programa.nombre}.",
                )
            else:
                messages.success(
                    request,
                    f"Derivación creada a {objeto.programa_destino.nombre}. Estado: Pendiente.",
                )
            return redirect("legajos:ciudadano_detalle", pk=ciudadano.id)
    else:
        form = DerivarProgramaForm(
            ciudadano=ciudadano,
            allow_inscripcion_directa=puede_inscripcion_directa,
        )

    return render(
        request,
        "legajos/derivar_programa.html",
        {
            "form": form,
            "ciudadano": ciudadano,
            "puede_inscripcion_directa": puede_inscripcion_directa,
        },
    )
