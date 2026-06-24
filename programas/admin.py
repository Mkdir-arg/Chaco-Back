from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    AsignacionCoordinador,
    Convocatoria,
    CupoSegmento,
    DerivacionPrograma,
    Formulario,
    InscripcionPrograma,
    ListaEspera,
    Programa,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TracaFormulario,
)


@admin.register(Programa)
class ProgramaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo", "estado", "orden", "ver_programa_button")
    list_filter = ("estado", "tipo")
    search_fields = ("codigo", "nombre")
    ordering = ("orden", "nombre")

    fieldsets = (
        ("Información Básica", {
            "fields": ("codigo", "nombre", "tipo", "descripcion"),
        }),
        ("Configuración Visual", {
            "fields": ("color", "icono", "orden"),
        }),
        ("Opciones", {
            "fields": ("naturaleza", "tiene_turnos", "cupo_maximo", "tiene_lista_espera", "subsecretaria"),
        }),
        ("Estado", {
            "fields": ("estado",),
        }),
    )

    def ver_programa_button(self, obj):
        url = reverse("legajos:programa_detalle", args=[obj.id])
        return format_html(
            '<a class="button" href="{}" style="background-color: {}; color: white; '
            'padding: 5px 10px; border-radius: 4px; text-decoration: none;">'
            "Ver Programa</a>",
            url,
            obj.color,
        )
    ver_programa_button.short_description = "Acciones"


@admin.register(InscripcionPrograma)
class InscripcionProgramaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "ciudadano", "programa", "estado", "responsable", "fecha_inscripcion")
    list_filter = ("estado", "via_ingreso", "programa", "fecha_inscripcion")
    search_fields = ("codigo", "ciudadano__dni", "ciudadano__nombre", "ciudadano__apellido")
    readonly_fields = ("codigo", "creado", "modificado")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("ciudadano", "programa", "responsable")

    fieldsets = (
        ("Información Básica", {
            "fields": ("codigo", "ciudadano", "programa"),
        }),
        ("Estado", {
            "fields": ("estado", "via_ingreso", "responsable"),
        }),
        ("Fechas", {
            "fields": ("fecha_inscripcion", "fecha_inicio", "fecha_cierre"),
        }),
        ("Observaciones", {
            "fields": ("notas", "motivo_cierre"),
        }),
        ("Auditoría", {
            "fields": ("creado", "modificado"),
            "classes": ("collapse",),
        }),
    )


@admin.register(DerivacionPrograma)
class DerivacionProgramaAdmin(admin.ModelAdmin):
    list_display = ("ciudadano", "programa_origen", "programa_destino", "estado", "urgencia", "derivado_por", "creado")
    list_filter = ("estado", "urgencia", "programa_destino", "creado")
    search_fields = ("ciudadano__dni", "ciudadano__nombre", "ciudadano__apellido", "motivo")
    readonly_fields = ("creado", "modificado", "fecha_respuesta")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "ciudadano", "programa_origen", "programa_destino",
            "derivado_por", "respondido_por", "inscripcion_creada",
        )

    fieldsets = (
        ("Información Básica", {
            "fields": ("ciudadano", "programa_origen", "programa_destino"),
        }),
        ("Derivación", {
            "fields": ("motivo", "urgencia", "estado", "derivado_por"),
        }),
        ("Respuesta", {
            "fields": ("respuesta", "fecha_respuesta", "respondido_por", "inscripcion_creada"),
        }),
        ("Auditoría", {
            "fields": ("creado", "modificado"),
            "classes": ("collapse",),
        }),
    )


# ===========================================================================
# Programa Becas
# ===========================================================================


class SubsegmentoInline(admin.TabularInline):
    model = Subsegmento
    extra = 0


class RequisitoNativoInline(admin.TabularInline):
    model = RequisitoNativo
    extra = 0


@admin.register(Segmento)
class SegmentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cupo_maximo", "requiere_gps", "activo")
    list_filter = ("activo", "requiere_gps")
    search_fields = ("nombre",)
    inlines = (SubsegmentoInline, RequisitoNativoInline)


@admin.register(Subsegmento)
class SubsegmentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "segmento", "cupo_maximo")
    list_filter = ("segmento",)
    search_fields = ("nombre",)


@admin.register(CupoSegmento)
class CupoSegmentoAdmin(admin.ModelAdmin):
    list_display = ("segmento", "cupo_ocupado")
    search_fields = ("segmento__nombre",)


@admin.register(Convocatoria)
class ConvocatoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "segmento", "subsegmento", "fecha_inicio", "fecha_fin", "activo")
    list_filter = ("activo", "segmento")
    search_fields = ("nombre",)


@admin.register(Relevamiento)
class RelevamientoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "convocatoria", "territorial", "fecha_asignada", "zona", "estado")
    list_filter = ("estado", "convocatoria")
    search_fields = ("nombre", "zona", "territorial__username")
    readonly_fields = ("nombre",)


@admin.register(PreguntaGlobal)
class PreguntaGlobalAdmin(admin.ModelAdmin):
    list_display = ("orden", "texto", "tipo", "obligatorio", "activo")
    list_filter = ("activo", "tipo", "obligatorio")
    search_fields = ("texto",)
    ordering = ("orden", "id")


@admin.register(RequisitoNativo)
class RequisitoNativoAdmin(admin.ModelAdmin):
    list_display = ("texto", "segmento", "subsegmento", "tipo", "orden")
    list_filter = ("segmento", "tipo")
    search_fields = ("texto",)


@admin.register(AsignacionCoordinador)
class AsignacionCoordinadorAdmin(admin.ModelAdmin):
    list_display = ("coordinador", "segmento", "activo", "fecha_asignacion")
    list_filter = ("activo", "segmento")
    search_fields = ("coordinador__username", "segmento__nombre")


class TracaFormularioInline(admin.TabularInline):
    model = TracaFormulario
    extra = 0
    readonly_fields = ("editado_por", "created_at", "campo", "valor_anterior", "valor_nuevo")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Formulario)
class FormularioAdmin(admin.ModelAdmin):
    list_display = ("id", "relevamiento", "ciudadano", "estado", "validado_renaper", "creado")
    list_filter = ("estado", "validado_renaper", "relevamiento")
    search_fields = ("ciudadano__dni", "ciudadano__nombre", "ciudadano__apellido", "celular")
    readonly_fields = ("creado", "modificado")
    inlines = (TracaFormularioInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("relevamiento", "ciudadano", "created_by")


@admin.register(TracaFormulario)
class TracaFormularioAdmin(admin.ModelAdmin):
    list_display = ("formulario", "campo", "editado_por", "created_at")
    list_filter = ("created_at",)
    search_fields = ("campo", "formulario__id")
    readonly_fields = ("formulario", "editado_por", "created_at", "campo", "valor_anterior", "valor_nuevo")


@admin.register(ListaEspera)
class ListaEsperaAdmin(admin.ModelAdmin):
    list_display = ("segmento", "posicion", "formulario", "promovido", "fecha_ingreso")
    list_filter = ("segmento", "promovido")
