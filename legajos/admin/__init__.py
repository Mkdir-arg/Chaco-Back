from django.contrib import admin

from ..models import Adjunto, Ciudadano, LegajoAtencion


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


@admin.register(LegajoAtencion)
class LegajoAtencionAdmin(admin.ModelAdmin):
    """Registrado para que la lupa de `legajo` exista (seguimiento MINOR de #645).

    `HistorialContactoAdmin` pasó `legajo` a `raw_id_fields` en G1c-09, y
    `ForeignKeyRawIdWidget` solo dibuja el link de búsqueda si el modelo apuntado está
    registrado: sin esto, el alta de un contacto desde el `/admin/` pedía tipear el UUID
    del legajo de memoria. Volver al `<select>` sería reponer el combo con la tabla
    entera que esa ficha sacó.

    No expone nada nuevo: al `/admin/` se entra con `is_staff`, que ningún camino del ABM
    de Usuarios otorga (ver `users/admin.py`), el `__str__` del legajo ya se mostraba en
    el listado de contactos y `Ciudadano` ya está registrado acá al lado.

    `list_display` y `search_fields` solo nombran **columnas reales**: `ciudadano` y
    `programa` son properties que resuelven el vínculo blando `InscripcionPrograma.
    legajo_id` (un `UUIDField`, no una FK), así que ponerlas serían dos consultas por
    fila y el ORM no las sabe buscar.
    """

    list_display = ("codigo", "estado", "fecha_admision", "via_ingreso", "nivel_riesgo", "responsable")
    # `LegajoAtencion.responsable` **redefine** el de `LegajoBase` como `null=True`, y el
    # `select_related()` que Django aplica solo a toda `ChangeList` sigue nada más que las
    # FK no nulas (la lección de G1c-11): sin esta línea el listado hacía una consulta por
    # fila. Medido: 13 consultas con 5 filas y 43 con 35.
    list_select_related = ("responsable",)
    list_filter = ("estado", "via_ingreso", "nivel_riesgo", "plan_vigente")
    search_fields = ("codigo",)
    ordering = ("-fecha_admision",)
    raw_id_fields = ("responsable",)
    readonly_fields = ("creado", "modificado")


@admin.register(Adjunto)
class AdjuntoAdmin(admin.ModelAdmin):
    list_display = ["etiqueta", "content_type", "object_id", "creado"]
    list_filter = ["content_type", "creado"]
    search_fields = ["etiqueta"]


from .contactos import *  # noqa: F401,F403,E402
