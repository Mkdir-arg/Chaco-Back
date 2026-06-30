"""
Vista de ejemplo para el sistema de solapas dinámicas
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView

from programas.models import DerivacionPrograma, InscripcionPrograma, Programa

from ..models import Ciudadano
from ..services import SolapasService


@login_required
def ciudadano_detalle_con_solapas(request, ciudadano_id):
    """
    Vista del detalle del ciudadano con sistema de solapas dinámicas
    """
    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)

    # Obtener solapas dinámicas
    solapas = SolapasService.obtener_solapas_ciudadano(ciudadano)

    # Obtener programas activos
    programas_activos = SolapasService.obtener_programas_activos(ciudadano)

    # Obtener programas disponibles para derivación
    programas_disponibles = SolapasService.obtener_programas_disponibles_derivacion(ciudadano)

    # Obtener derivaciones pendientes
    derivaciones_pendientes = SolapasService.obtener_derivaciones_pendientes(ciudadano)

    # Obtener historial completo
    historial_programas = SolapasService.obtener_historial_programas(ciudadano)

    context = {
        "ciudadano": ciudadano,
        "solapas": solapas,
        "solapa_activa": "resumen",  # Por defecto, la solapa activa es "Resumen"
        "programas_activos": programas_activos,
        "programas_disponibles": programas_disponibles,
        "derivaciones_pendientes": derivaciones_pendientes,
        "historial_programas": historial_programas,
    }

    return render(request, "legajos/ciudadano_detalle_solapas.html", context)


@login_required
def derivar_a_programa(request, ciudadano_id):
    """
    Crea una derivación a otro programa
    """
    if request.method != "POST":
        return redirect("legajos:ciudadano_detalle", ciudadano_id=ciudadano_id)

    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)

    # Obtener datos del formulario
    programa_origen_id = request.POST.get("programa_origen")
    programa_destino_id = request.POST.get("programa_destino")
    motivo = request.POST.get("motivo")
    urgencia = request.POST.get("urgencia", "MEDIA")

    # Validar programa destino
    if not programa_destino_id:
        messages.error(request, "Debe seleccionar un programa destino")
        return redirect("legajos:ciudadano_detalle", ciudadano_id=ciudadano_id)

    programa_destino = get_object_or_404(Programa, id=programa_destino_id, estado=Programa.Estado.ACTIVO)

    # Obtener programa origen (si existe)
    programa_origen = None
    inscripcion_origen = None
    if programa_origen_id:
        programa_origen = get_object_or_404(Programa, id=programa_origen_id)
        inscripcion_origen = InscripcionPrograma.objects.filter(
            ciudadano=ciudadano, programa=programa_origen, estado__in=["ACTIVO", "EN_SEGUIMIENTO"]
        ).first()

    # Verificar que no exista derivación pendiente al mismo programa
    existe_pendiente = DerivacionPrograma.objects.filter(
        ciudadano=ciudadano, programa_destino=programa_destino, estado="PENDIENTE"
    ).exists()

    if existe_pendiente:
        messages.warning(request, f"Ya existe una derivación pendiente a {programa_destino.nombre}")
        return redirect("legajos:ciudadano_detalle", ciudadano_id=ciudadano_id)

    # Crear derivación
    DerivacionPrograma.objects.create(
        ciudadano=ciudadano,
        programa_origen=programa_origen,
        inscripcion_origen=inscripcion_origen,
        programa_destino=programa_destino,
        motivo=motivo,
        urgencia=urgencia,
        derivado_por=request.user,
    )

    messages.success(
        request, f"Derivación creada exitosamente a {programa_destino.nombre}. Estado: Pendiente de aceptación."
    )

    return redirect("legajos:ciudadano_detalle", ciudadano_id=ciudadano_id)


@login_required
def inscribir_a_programa(request, ciudadano_id):
    """
    Inscribe directamente a un ciudadano a un programa (sin derivación)
    """
    ciudadano = get_object_or_404(Ciudadano, id=ciudadano_id)

    if request.method == "POST":
        programa_id = request.POST.get("programa")
        notas = request.POST.get("notas", "")

        programa = get_object_or_404(Programa, id=programa_id, estado=Programa.Estado.ACTIVO)

        try:
            SolapasService.crear_inscripcion_directa(
                ciudadano=ciudadano, programa=programa, responsable=request.user, notas=notas
            )

            messages.success(request, f"Ciudadano inscrito exitosamente a {programa.nombre}")
            return redirect("legajos:ciudadano_detalle", ciudadano_id=ciudadano_id)

        except ValueError as e:
            messages.error(request, str(e))
            return redirect("legajos:ciudadano_detalle", ciudadano_id=ciudadano_id)

    # GET: Mostrar formulario
    programas_disponibles = SolapasService.obtener_programas_disponibles_derivacion(ciudadano)

    context = {
        "ciudadano": ciudadano,
        "programas_disponibles": programas_disponibles,
    }

    return render(request, "legajos/inscribir_programa_form.html", context)


@login_required
def aceptar_derivacion_programa(request, derivacion_id):
    """
    Acepta una derivación y crea la inscripción al programa
    """
    derivacion = get_object_or_404(DerivacionPrograma, id=derivacion_id)

    if request.method == "POST":
        responsable_id = request.POST.get("responsable")
        responsable = request.user

        if responsable_id:
            from django.contrib.auth.models import User

            responsable = get_object_or_404(User, id=responsable_id)

        try:
            derivacion.aceptar(usuario=request.user, responsable=responsable)

            messages.success(
                request,
                f"Derivación aceptada. {derivacion.ciudadano.nombre_completo} inscrito en {derivacion.programa_destino.nombre}",
            )

            # Redirigir al detalle del ciudadano con la nueva solapa
            return redirect("legajos:ciudadano_detalle", ciudadano_id=derivacion.ciudadano.id)

        except ValueError as e:
            messages.error(request, str(e))

    context = {
        "derivacion": derivacion,
    }

    return render(request, "legajos/aceptar_derivacion_programa.html", context)


@login_required
def rechazar_derivacion_programa(request, derivacion_id):
    """
    Rechaza una derivación
    """
    derivacion = get_object_or_404(DerivacionPrograma, id=derivacion_id)

    if request.method == "POST":
        motivo_rechazo = request.POST.get("motivo_rechazo")

        if not motivo_rechazo:
            messages.error(request, "Debe indicar el motivo del rechazo")
            return redirect("legajos:derivacion_programa_detalle", derivacion_id=derivacion_id)

        try:
            derivacion.rechazar(usuario=request.user, motivo_rechazo=motivo_rechazo)

            messages.warning(
                request,
                f"Derivación rechazada: {derivacion.ciudadano.nombre_completo} a {derivacion.programa_destino.nombre}",
            )

            return redirect("legajos:ciudadano_detalle", ciudadano_id=derivacion.ciudadano.id)

        except ValueError as e:
            messages.error(request, str(e))

    context = {
        "derivacion": derivacion,
    }

    return render(request, "legajos/rechazar_derivacion_programa.html", context)


@login_required
def cerrar_inscripcion_programa(request, inscripcion_id):
    """
    Cierra una inscripción a un programa
    """
    inscripcion = get_object_or_404(InscripcionPrograma, id=inscripcion_id)

    if request.method == "POST":
        motivo_cierre = request.POST.get("motivo_cierre")

        if not motivo_cierre:
            messages.error(request, "Debe indicar el motivo del cierre")
            return redirect("legajos:ciudadano_detalle", ciudadano_id=inscripcion.ciudadano.id)

        try:
            SolapasService.cerrar_inscripcion(
                inscripcion=inscripcion, motivo_cierre=motivo_cierre, usuario=request.user
            )

            messages.success(
                request,
                f"Inscripción cerrada: {inscripcion.ciudadano.nombre_completo} en {inscripcion.programa.nombre}",
            )

            return redirect("legajos:ciudadano_detalle", ciudadano_id=inscripcion.ciudadano.id)

        except ValueError as e:
            messages.error(request, str(e))

    context = {
        "inscripcion": inscripcion,
    }

    return render(request, "legajos/cerrar_inscripcion_programa.html", context)


class CiudadanoDetalleConSolapasView(LoginRequiredMixin, DetailView):
    """
    Vista basada en clases para el detalle del ciudadano con solapas dinámicas
    """

    model = Ciudadano
    template_name = "legajos/ciudadano_detalle_solapas.html"
    context_object_name = "ciudadano"
    pk_url_kwarg = "ciudadano_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ciudadano = self.object

        # Obtener solapas dinámicas
        context["solapas"] = SolapasService.obtener_solapas_ciudadano(ciudadano)
        context["solapa_activa"] = self.request.GET.get("solapa", "resumen")

        # Obtener programas activos
        context["programas_activos"] = SolapasService.obtener_programas_activos(ciudadano)

        # Obtener programas disponibles para derivación
        context["programas_disponibles"] = SolapasService.obtener_programas_disponibles_derivacion(ciudadano)

        # Obtener derivaciones pendientes
        context["derivaciones_pendientes"] = SolapasService.obtener_derivaciones_pendientes(ciudadano)

        # Obtener historial completo
        context["historial_programas"] = SolapasService.obtener_historial_programas(ciudadano)

        return context
