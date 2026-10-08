"""Modelos de `programas` en el `/admin/` de Django.

**Nada acá puede crecer con la tabla** (G1c-09 y G1c-11, auditoría oct-2026). Son los
dos defectos que el admin trae de fábrica y que con 40.000 casos chocan contra el
`read_timeout` de 10 s:

- En la **ficha**, un `<select>` de una FK trae todas las filas del modelo apuntado y
  llama a su `__str__` por opción. `Formulario.__str__` abre el ciudadano e
  `InscripcionPrograma.__str__` abre ciudadano y programa, así que el combo es una
  consulta por fila: medido en la PoC de la auditoría, la ficha de un caso pasa de 19 a
  46 consultas cuando la tabla pasa de 5 a 35 filas, y el alta de una derivación de 21 a
  80. Se arregla con `raw_id_fields`, que deja el id más la lupa de búsqueda.
- En el **listado**, una FK de `list_display` puede ser una consulta por fila. No
  siempre: desde que `ChangeList.apply_select_related` existe, Django llama solo a
  `select_related()` **sin argumentos** cuando `list_display` tiene algún campo
  relacionado, y eso ya cubre las FK. Pero `select_related()` sin argumentos sigue
  **únicamente las FK no nulas**, así que quedan afuera dos casos, que son los que este
  archivo arregla con `list_select_related`: las FK **nulables**
  (`Formulario.ciudadano`, `Relevamiento.territorial`, `TracaFormulario.editado_por`) y
  los saltos de **segundo** nivel que pide el `__str__` del objeto mostrado
  (`Formulario.__str__` abre el ciudadano, así que el listado de trazas y el de lista de
  espera lo necesitan).

Ninguna de las dos cosas cambia qué se puede editar ni quién puede entrar: la
validación sigue siendo la del `ModelForm` y los permisos, los de Django.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    AsignacionCoordinador,
    AsignacionDispositivo,
    AsignacionReferente,
    AsignacionTerritorial,
    Convocatoria,
    CupoSegmento,
    DerivacionPrograma,
    Formulario,
    InscripcionPrograma,
    ListaEspera,
    PreguntaGlobal,
    Programa,
    ProgramaSiis,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TracaFormulario,
)


class SinBorradoMixin:
    """DAT-02: estos modelos no se borran desde `/admin/`.

    `Relevamiento`, `Formulario`, `TracaFormulario` y `ListaEspera` arrastran en
    cascada los adjuntos del ciudadano, las trazas de edición (RN-14/29 las declara
    **inmutables**) y la posición en la lista de espera. La pantalla de confirmación
    lista la cascada, pero la lista es larga y la acción masiva `delete_selected`
    borra varios de un saque sin que nadie lea nada. No hay ningún procedimiento que
    pida borrar un caso: lo que hay es rechazarlo.

    Con `has_delete_permission` en `False` Django además saca `delete_selected` de
    las acciones y el botón «Eliminar» de la ficha.
    """

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Programa)
class ProgramaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "tipo", "estado", "orden", "ver_programa_button")
    list_filter = ("estado", "tipo")
    search_fields = ("codigo", "nombre")
    ordering = ("orden", "nombre")

    fieldsets = (
        (
            "Información Básica",
            {
                "fields": ("codigo", "nombre", "tipo", "descripcion"),
            },
        ),
        (
            "Configuración Visual",
            {
                "fields": ("color", "icono", "orden"),
            },
        ),
        (
            "Opciones",
            {
                "fields": ("naturaleza", "tiene_turnos", "cupo_maximo", "tiene_lista_espera", "subsecretaria"),
            },
        ),
        (
            "Indicadores operativos",
            {
                "fields": (
                    "umbral_disponibilidad_verde",
                    "dias_actualizacion_verde",
                    "dias_actualizacion_amarillo",
                    "umbral_completitud_amarillo",
                    "umbral_completitud_verde",
                ),
            },
        ),
        (
            "Estado",
            {
                "fields": ("estado",),
            },
        ),
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
    # `fecha_inscripcion` es `editable=False` en el modelo y estaba en los `fieldsets`
    # sin ser de solo lectura: el alta y la ficha de una inscripción respondían **500**
    # (`FieldError: cannot be specified for InscripcionPrograma model form as it is a
    # non-editable field`). Lo encontró el test de G1c-09 al abrir las dos pantallas.
    readonly_fields = ("codigo", "fecha_inscripcion", "creado", "modificado")
    # G1c-09: `ciudadano` es la tabla del padrón y `responsable` crece con los
    # territoriales. `programa` queda en combo: son una decena de filas.
    raw_id_fields = ("ciudadano", "responsable")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("ciudadano", "programa", "responsable")

    fieldsets = (
        (
            "Información Básica",
            {
                "fields": ("codigo", "ciudadano", "programa"),
            },
        ),
        (
            "Estado",
            {
                "fields": ("estado", "via_ingreso", "responsable"),
            },
        ),
        (
            "Fechas",
            {
                "fields": ("fecha_inscripcion", "fecha_inicio", "fecha_cierre"),
            },
        ),
        (
            "Observaciones",
            {
                "fields": ("notas", "motivo_cierre"),
            },
        ),
        (
            "Auditoría",
            {
                "fields": ("creado", "modificado"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(DerivacionPrograma)
class DerivacionProgramaAdmin(admin.ModelAdmin):
    list_display = ("ciudadano", "programa_origen", "programa_destino", "estado", "urgencia", "derivado_por", "creado")
    list_filter = ("estado", "urgencia", "programa_destino", "creado")
    search_fields = ("ciudadano__dni", "ciudadano__nombre", "ciudadano__apellido", "motivo")
    readonly_fields = ("creado", "modificado", "fecha_respuesta")
    # G1c-09: el alta de una derivación era la peor de las dos fichas medidas (21 → 80
    # consultas con 5 → 35 inscripciones), porque `inscripcion_creada` listaba todas las
    # inscripciones y cada opción abría ciudadano y programa.
    raw_id_fields = ("ciudadano", "inscripcion_creada", "derivado_por", "respondido_por")

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "ciudadano",
                "programa_origen",
                "programa_destino",
                "derivado_por",
                "respondido_por",
                "inscripcion_creada",
            )
        )

    fieldsets = (
        (
            "Información Básica",
            {
                "fields": ("ciudadano", "programa_origen", "programa_destino"),
            },
        ),
        (
            "Derivación",
            {
                "fields": ("motivo", "urgencia", "estado", "derivado_por"),
            },
        ),
        (
            "Respuesta",
            {
                "fields": ("respuesta", "fecha_respuesta", "respondido_por", "inscripcion_creada"),
            },
        ),
        (
            "Auditoría",
            {
                "fields": ("creado", "modificado"),
                "classes": ("collapse",),
            },
        ),
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
    fk_name = "segmento"


@admin.register(ProgramaSiis)
class ProgramaSiisAdmin(admin.ModelAdmin):
    list_display = ("nombre", "siis_programa_id", "siis_programa_estado", "pausado", "siis_verificado_en")
    list_filter = ("siis_programa_estado", "pausado")
    search_fields = ("nombre",)


@admin.register(Segmento)
class SegmentoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "programa", "cupo_maximo", "requiere_gps", "activo")
    list_filter = ("activo", "requiere_gps", "programa")
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
    # DAT-02: `cupo_ocupado` es un contador derivado (lo mantiene el servicio de
    # cupo). Editarlo a mano desajusta la cuenta contra la que valida
    # `Segmento.clean()` y no deja traza de quién lo tocó.
    readonly_fields = ("cupo_ocupado",)


@admin.register(Convocatoria)
class ConvocatoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "segmento", "subsegmento", "fecha_inicio", "fecha_fin", "activo")
    list_filter = ("activo", "segmento")
    search_fields = ("nombre",)


@admin.register(Relevamiento)
class RelevamientoAdmin(SinBorradoMixin, admin.ModelAdmin):
    list_display = ("nombre", "tipo", "convocatoria", "territorial", "fecha_asignada", "fecha_hasta", "zona", "estado")
    list_filter = ("tipo", "estado", "convocatoria")
    search_fields = ("nombre", "zona", "territorial__username")
    readonly_fields = ("nombre", "token_publico")
    # G1c-11: `convocatoria` y `territorial` se muestran en cada fila del listado.
    list_select_related = ("convocatoria", "territorial")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and "tipo" not in fields:
            fields.append("tipo")
        return fields


@admin.register(PreguntaGlobal)
class PreguntaGlobalAdmin(admin.ModelAdmin):
    list_display = ("orden", "texto", "tipo", "obligatorio", "activo")
    list_filter = ("activo", "tipo", "obligatorio")
    search_fields = ("texto",)
    ordering = ("orden", "id")


@admin.register(RequisitoNativo)
class RequisitoNativoAdmin(admin.ModelAdmin):
    list_display = ("texto", "programa", "segmento", "subsegmento", "tipo", "orden")
    list_filter = ("programa", "segmento", "tipo")
    search_fields = ("texto",)


@admin.register(AsignacionCoordinador)
class AsignacionCoordinadorAdmin(admin.ModelAdmin):
    list_display = ("coordinador", "segmento", "activo", "fecha_asignacion")
    list_filter = ("activo", "segmento")
    search_fields = ("coordinador__username", "segmento__nombre")


@admin.register(AsignacionReferente)
class AsignacionReferenteAdmin(admin.ModelAdmin):
    list_display = ("referente", "coordinador", "fecha_asignacion")
    search_fields = ("referente__username", "coordinador__username")


@admin.register(AsignacionDispositivo)
class AsignacionDispositivoAdmin(admin.ModelAdmin):
    list_display = ("rol", "dispositivo", "activo", "creado")
    list_filter = ("activo", "dispositivo__tipo")
    search_fields = ("rol__name", "dispositivo__codigo", "dispositivo__nombre")


@admin.register(AsignacionTerritorial)
class AsignacionTerritorialAdmin(admin.ModelAdmin):
    list_display = ("territorial", "segmento", "fecha_asignacion")
    list_filter = ("segmento",)
    search_fields = ("territorial__username", "segmento__nombre")


class TracaFormularioInline(admin.TabularInline):
    model = TracaFormulario
    extra = 0
    readonly_fields = ("editado_por", "created_at", "campo", "valor_anterior", "valor_nuevo")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Formulario)
class FormularioAdmin(SinBorradoMixin, admin.ModelAdmin):
    list_display = ("id", "relevamiento", "ciudadano", "estado", "validado_renaper", "creado")
    list_filter = ("estado", "validado_renaper", "relevamiento")
    search_fields = ("ciudadano__dni", "ciudadano__nombre", "ciudadano__apellido", "celular")
    # DAT-02: los campos que cuentan la historia del caso se leen, no se escriben.
    # El estado lo mueven la revisión y el masivo dejando `TracaFormulario`; la
    # validación de identidad y su origen los pone la cascada del Cambio 57; `data`
    # es lo que la persona declaró y `datos_siis` lo que el coordinador corrigió
    # para el alta. Cambiarlos por acá no dejaba ninguna traza.
    readonly_fields = (
        "creado",
        "modificado",
        "estado",
        "validado_renaper",
        "identidad_forzada",
        "origen_validacion",
        "datos_siis",
        "data",
    )
    inlines = (TracaFormularioInline,)
    # G1c-09: las cinco FK editables de la ficha apuntan a tablas que crecen con el
    # padrón. `duplicado_de` es la peor: es un `<select>` de todos los formularios y
    # `Formulario.__str__` abre el ciudadano de cada opción (el `NPlusOneError` que zeal
    # marcaba en la PoC).
    raw_id_fields = ("relevamiento", "ciudadano", "duplicado_de", "apoderado_ciudadano", "created_by")

    def get_queryset(self, request):
        # Sirve para el listado y para la ficha, así que G1c-11 no necesita además un
        # `list_select_related` acá.
        return super().get_queryset(request).select_related("relevamiento", "ciudadano", "created_by")


@admin.register(TracaFormulario)
class TracaFormularioAdmin(SinBorradoMixin, admin.ModelAdmin):
    list_display = ("formulario", "campo", "editado_por", "created_at")
    list_filter = ("created_at",)
    # G1c-11: `=` fuerza la igualdad. Sin él Django busca el id con `LIKE %texto%`, que
    # sobre la tabla de trazas —la que más filas tiene después de los casos— es un scan.
    search_fields = ("campo", "=formulario__id")
    readonly_fields = ("formulario", "editado_por", "created_at", "campo", "valor_anterior", "valor_nuevo")
    # G1c-11: `TracaFormulario.__str__` usa `formulario_id` (no consulta), pero el
    # listado muestra la columna `formulario`, que sí resuelve la FK fila por fila, y
    # `Formulario.__str__` abre a su vez el ciudadano.
    list_select_related = ("formulario__ciudadano", "editado_por")


@admin.register(ListaEspera)
class ListaEsperaAdmin(SinBorradoMixin, admin.ModelAdmin):
    list_display = ("segmento", "posicion", "formulario", "promovido", "fecha_ingreso")
    list_filter = ("segmento", "promovido")
    # G1c-09: el combo de `formulario` listaba todos los casos.
    raw_id_fields = ("formulario",)
    # G1c-11: dos FK por fila, y la del formulario arrastra su ciudadano.
    list_select_related = ("segmento", "formulario__ciudadano")
