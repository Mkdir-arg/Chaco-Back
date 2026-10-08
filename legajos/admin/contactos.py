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
    # G1c-09: el combo de `legajo` listaba todos los legajos de atención y el de
    # `profesional` todos los usuarios. La lupa de `legajo` existe porque
    # `LegajoAtencionAdmin` está registrado (seguimiento MINOR de #645): sin eso,
    # `ForeignKeyRawIdWidget` no dibuja el link y el alta pide el UUID de memoria.
    raw_id_fields = ["legajo", "profesional"]
    # G1c-11 daba por N+1 el listado: medido, no lo es. `legajo` y `profesional` son FK
    # **no nulas**, y Django ya le aplica `select_related()` sin argumentos a toda
    # `ChangeList` con un campo relacionado en `list_display`, que esas las cubre. Un
    # `list_select_related` acá no cambiaría ninguna consulta.
    #
    # Lo que sí queda, y no se arregla desde el admin, es **una** consulta por fila:
    # `LegajoAtencion.__str__` abre `self.ciudadano`, que es una property, porque
    # `InscripcionPrograma.legajo_id` es un `UUIDField` suelto y no una FK — no hay
    # relación que el ORM pueda seguir ni prefetchear. Sacarla es cambiar ese vínculo
    # blando, que excede la ficha.


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
    # G1c-09: dos combos con el padrón entero, uno al lado del otro.
    #
    # El listado, en cambio, no necesita nada: los dos ciudadanos son FK no nulas y los
    # cubre el `select_related()` que Django aplica solo (ver `HistorialContactoAdmin`).
    raw_id_fields = ["ciudadano_principal", "ciudadano_vinculado"]
