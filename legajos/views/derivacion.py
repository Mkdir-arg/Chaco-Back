from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from core.rbac import puede, requiere

from ..forms import DerivarProgramaForm
from ..models import Ciudadano


@requiere("ciudadano.editar")
def derivar_programa_view(request, ciudadano_id):
    """Pantalla de derivación/inscripción de ciudadanos a programas activos.

    La pantalla crea una derivación o —con la opción habilitada— inscribe
    directo en el programa, así que exige ``ciudadano.editar`` y no solo sesión
    (SEC-12).

    ``puede_inscripcion_directa`` salía de ``request.user.is_staff``, que es la
    marca de acceso al admin de Django y no una capacidad del RBAC: un usuario
    con el tilde de staff y sin ningún rol inscribía a cualquiera en cualquier
    programa, y un operador con todas las capacidades de Legajos no podía.
    **DECISIÓN CLIENTE D-12 = reusar ``ciudadano.editar``**, sin capacidad
    nueva: quien puede abrir esta pantalla puede además inscribir directo.
    """
    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)
    puede_inscripcion_directa = puede(request.user, "ciudadano.editar")

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
