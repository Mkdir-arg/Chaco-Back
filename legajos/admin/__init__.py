from django.contrib import admin

from ..models import Adjunto, Ciudadano


@admin.register(Ciudadano)
class CiudadanoAdmin(admin.ModelAdmin):
    list_display = ("dni", "apellido", "nombre", "activo", "creado")
    search_fields = ("dni", "apellido", "nombre")
    list_filter = ("activo", "genero")
    ordering = ("apellido", "nombre")
    readonly_fields = ("creado", "modificado")

    # G1c-11: acá había un `get_queryset` con
    # `prefetch_related("inscripciones_programas__programa")`. Ni el `list_display`
    # (dni, apellido, nombre, activo, creado) ni los `fieldsets` abren las
    # inscripciones, así que eran dos consultas extra por página —una de ellas con un
    # `IN` de los 100 ciudadanos de la página— para alimentar una caché que nadie leía.

    fieldsets = (
        ("Información Personal", {"fields": ("dni", "nombre", "apellido", "fecha_nacimiento", "genero")}),
        ("Contacto", {"fields": ("telefono", "email", "domicilio")}),
        ("Estado", {"fields": ("activo",)}),
        ("Auditoría", {"fields": ("creado", "modificado"), "classes": ("collapse",)}),
    )


@admin.register(Adjunto)
class AdjuntoAdmin(admin.ModelAdmin):
    list_display = ["etiqueta", "content_type", "object_id", "creado"]
    list_filter = ["content_type", "creado"]
    search_fields = ["etiqueta"]


from .contactos import *  # noqa: F401,F403,E402
