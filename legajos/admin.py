from django.contrib import admin
from .models import Ciudadano, Derivacion, Adjunto
from .models_programas import Programa, InscripcionPrograma, DerivacionPrograma


@admin.register(Ciudadano)
class CiudadanoAdmin(admin.ModelAdmin):
    list_display = ("dni", "apellido", "nombre", "activo", "creado")
    search_fields = ("dni", "apellido", "nombre")
    list_filter = ("activo", "genero")
    ordering = ("apellido", "nombre")
    readonly_fields = ("creado", "modificado")
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('inscripciones_programas__programa')
    
    fieldsets = (
        ("Información Personal", {
            "fields": ("dni", "nombre", "apellido", "fecha_nacimiento", "genero")
        }),
        ("Contacto", {
            "fields": ("telefono", "email", "domicilio")
        }),
        ("Estado", {
            "fields": ("activo",)
        }),
        ("Auditoría", {
            "fields": ("creado", "modificado"),
            "classes": ("collapse",)
        }),
    )


@admin.register(Derivacion)
class DerivacionAdmin(admin.ModelAdmin):
    list_display = ['legajo', 'actividad_destino', 'urgencia', 'estado', 'creado']
    list_filter = ['urgencia', 'estado', 'creado']
    search_fields = ['legajo__codigo', 'motivo', 'actividad_destino__nombre']
    date_hierarchy = 'creado'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('legajo', 'actividad_destino')


@admin.register(Adjunto)
class AdjuntoAdmin(admin.ModelAdmin):
    list_display = ['etiqueta', 'content_type', 'object_id', 'creado']
    list_filter = ['content_type', 'creado']
    search_fields = ['etiqueta']


# Registrar modelos de contactos en admin
try:
    from .admin_contactos import *
except ImportError:
    pass

# Registrar modelos de programas en admin
try:
    from .admin_programas import *
except ImportError:
    pass

# Registrar modelos de Ñachec en admin
try:
    from .admin_nachec import *
except ImportError:
    pass


# ============================================================================
# SISTEMA NODO - MODELOS INSTITUCIONALES

