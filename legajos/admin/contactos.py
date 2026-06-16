from django.contrib import admin

from ..models.contactos import HistorialContacto, VinculoFamiliar


@admin.register(HistorialContacto)
class HistorialContactoAdmin(admin.ModelAdmin):
    list_display = [
        "legajo",
        "tipo_contacto",
        "fecha_contacto",
        "profesional",
        "estado",
        "duracion_formateada",
        "seguimiento_requerido",
    ]
    list_filter = [
        "tipo_contacto",
        "estado",
        "seguimiento_requerido",
        "fecha_contacto",
        "profesional",
    ]
    search_fields = [
        "legajo__codigo",
        "motivo",
        "resumen",
    ]
    date_hierarchy = "fecha_contacto"
    ordering = ["-fecha_contacto"]


@admin.register(VinculoFamiliar)
class VinculoFamiliarAdmin(admin.ModelAdmin):
    list_display = [
        "ciudadano_principal",
        "tipo_vinculo",
        "ciudadano_vinculado",
        "es_contacto_emergencia",
        "es_referente_tratamiento",
        "convive",
        "activo",
    ]
    list_filter = [
        "tipo_vinculo",
        "es_contacto_emergencia",
        "es_referente_tratamiento",
        "convive",
        "activo",
    ]
    search_fields = [
        "ciudadano_principal__nombre",
        "ciudadano_principal__apellido",
        "ciudadano_vinculado__nombre",
        "ciudadano_vinculado__apellido",
    ]
