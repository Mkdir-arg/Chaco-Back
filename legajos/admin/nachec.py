"""
Admin para Programa Ñachec
"""
from django.contrib import admin
from django.utils.html import format_html
from ..models.nachec import (
    CasoNachec, RelevamientoNachec, EvaluacionVulnerabilidad,
    PlanIntervencionNachec, PrestacionNachec, TareaNachec,
    SeguimientoTerritorial, HistorialEstadoCaso
)


@admin.register(CasoNachec)
class CasoNachecAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'ciudadano_titular', 'estado_badge', 'prioridad_badge',
        'municipio', 'territorial', 'fecha_derivacion'
    ]
    list_filter = ['estado', 'prioridad', 'municipio', 'tiene_duplicado']
    search_fields = [
        'ciudadano_titular__nombre', 'ciudadano_titular__apellido',
        'ciudadano_titular__dni', 'municipio', 'localidad'
    ]
    readonly_fields = ['creado', 'modificado']

    fieldsets = (
        ('Ciudadano', {
            'fields': ('ciudadano_titular',)
        }),
        ('Estado', {
            'fields': ('estado', 'prioridad', 'tiene_duplicado', 'doc_pendiente')
        }),
        ('Ubicación', {
            'fields': ('municipio', 'localidad', 'direccion', 'referencias_domicilio')
        }),
        ('Asignaciones', {
            'fields': ('operador_admision', 'coordinador', 'territorial', 'referente_programa')
        }),
        ('Fechas', {
            'fields': ('fecha_derivacion', 'fecha_asignacion', 'fecha_relevamiento',
                      'fecha_evaluacion', 'fecha_cierre')
        }),
        ('Motivos', {
            'fields': ('motivo_derivacion', 'motivo_rechazo', 'motivo_suspension', 'motivo_cierre')
        }),
        ('SLA', {
            'fields': ('sla_revision', 'sla_relevamiento')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
        ('Auditoría', {
            'fields': ('creado', 'modificado'),
            'classes': ('collapse',)
        }),
    )

    def estado_badge(self, obj):
        colors = {
            'DERIVADO': 'gray',
            'EN_REVISION': 'blue',
            'A_ASIGNAR': 'orange',
            'ASIGNADO': 'purple',
            'EN_RELEVAMIENTO': 'cyan',
            'EVALUADO': 'teal',
            'PLAN_DEFINIDO': 'indigo',
            'EN_EJECUCION': 'green',
            'EN_SEGUIMIENTO': 'lime',
            'CERRADO': 'gray',
            'SUSPENDIDO': 'yellow',
            'RECHAZADO': 'red'
        }
        color = colors.get(obj.estado, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'

    def prioridad_badge(self, obj):
        colors = {
            'BAJA': '#10b981',
            'MEDIA': '#f59e0b',
            'ALTA': '#ef4444',
            'URGENTE': '#dc2626'
        }
        color = colors.get(obj.prioridad, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.get_prioridad_display()
        )
    prioridad_badge.short_description = 'Prioridad'


@admin.register(RelevamientoNachec)
class RelevamientoNachecAdmin(admin.ModelAdmin):
    list_display = ['caso', 'territorial', 'completado', 'fecha_finalizacion']
    list_filter = ['completado', 'tipo_vivienda', 'acceso_alimentos', 'urgencia_alimentaria']
    search_fields = ['caso__ciudadano_titular__nombre', 'caso__ciudadano_titular__apellido']
    readonly_fields = ['creado', 'modificado']

    fieldsets = (
        ('Caso', {
            'fields': ('caso', 'territorial')
        }),
        ('Composición Familiar', {
            'fields': ('cantidad_convivientes', 'hay_embarazo', 'hay_discapacidad', 'detalle_discapacidad')
        }),
        ('Ingresos y Empleo', {
            'fields': ('ingreso_mensual_rango', 'fuente_ingreso', 'situacion_laboral')
        }),
        ('Vivienda', {
            'fields': ('tipo_vivienda', 'material_predominante', 'tiene_agua', 'tiene_luz',
                      'tiene_gas', 'tiene_cloaca', 'personas_por_habitacion')
        }),
        ('Salud', {
            'fields': ('cobertura_salud', 'condiciones_cronicas')
        }),
        ('Educación', {
            'fields': ('menores_escolarizados', 'motivo_no_escolarizacion')
        }),
        ('Alimentación', {
            'fields': ('acceso_alimentos', 'frecuencia_comidas')
        }),
        ('Riesgos', {
            'fields': ('hay_violencia', 'detalle_violencia', 'hay_situacion_calle', 'urgencia_alimentaria')
        }),
        ('Geolocalización', {
            'fields': ('latitud', 'longitud')
        }),
        ('Estado', {
            'fields': ('completado', 'fecha_finalizacion', 'observaciones')
        }),
    )


@admin.register(EvaluacionVulnerabilidad)
class EvaluacionVulnerabilidadAdmin(admin.ModelAdmin):
    list_display = ['caso', 'categoria_final', 'score_total', 'evaluador', 'fecha_evaluacion']
    list_filter = ['categoria_final']
    search_fields = ['caso__ciudadano_titular__nombre', 'caso__ciudadano_titular__apellido']
    readonly_fields = ['fecha_evaluacion']

    fieldsets = (
        ('Caso', {
            'fields': ('caso', 'relevamiento', 'evaluador')
        }),
        ('Scoring', {
            'fields': ('score_total', 'score_version', 'categoria_sugerida')
        }),
        ('Dictamen', {
            'fields': ('categoria_final', 'dictamen', 'override_categoria', 'justificacion_override')
        }),
    )


@admin.register(PlanIntervencionNachec)
class PlanIntervencionNachecAdmin(admin.ModelAdmin):
    list_display = ['caso', 'referente', 'vigente', 'fecha_inicio', 'horizonte_dias']
    list_filter = ['vigente', 'incluye_alimentacion', 'incluye_vivienda', 'incluye_empleo']
    search_fields = ['caso__ciudadano_titular__nombre', 'caso__ciudadano_titular__apellido']

    fieldsets = (
        ('Caso', {
            'fields': ('caso', 'referente')
        }),
        ('Plan', {
            'fields': ('objetivo_general', 'fecha_inicio', 'horizonte_dias', 'vigente')
        }),
        ('Componentes', {
            'fields': ('incluye_alimentacion', 'incluye_vivienda', 'incluye_empleo',
                      'incluye_salud', 'incluye_educacion', 'incluye_emprendimiento')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
    )


class TareaNachecInline(admin.TabularInline):
    model = TareaNachec
    extra = 0
    fields = ['tipo', 'titulo', 'asignado_a', 'estado', 'fecha_vencimiento']


@admin.register(PrestacionNachec)
class PrestacionNachecAdmin(admin.ModelAdmin):
    list_display = ['tipo', 'caso', 'estado', 'responsable', 'fecha_programada', 'fecha_entregada']
    list_filter = ['tipo', 'estado', 'frecuencia']
    search_fields = ['caso__ciudadano_titular__nombre', 'descripcion']
    inlines = [TareaNachecInline]

    fieldsets = (
        ('Prestación', {
            'fields': ('plan', 'caso', 'tipo', 'subtipo', 'descripcion')
        }),
        ('Estado', {
            'fields': ('estado', 'frecuencia')
        }),
        ('Fechas', {
            'fields': ('fecha_programada', 'fecha_entregada')
        }),
        ('Responsable', {
            'fields': ('responsable', 'lugar_entrega')
        }),
        ('Confirmación', {
            'fields': ('receptor_nombre', 'confirmacion_firma', 'confirmacion_foto', 'confirmacion_codigo')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
    )


@admin.register(TareaNachec)
class TareaNachecAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'caso', 'tipo', 'asignado_a', 'estado', 'prioridad', 'fecha_vencimiento']
    list_filter = ['tipo', 'estado', 'prioridad']
    search_fields = ['titulo', 'descripcion', 'caso__ciudadano_titular__nombre']

    fieldsets = (
        ('Tarea', {
            'fields': ('caso', 'prestacion', 'tipo', 'titulo', 'descripcion')
        }),
        ('Asignación', {
            'fields': ('asignado_a', 'creado_por')
        }),
        ('Estado', {
            'fields': ('estado', 'prioridad')
        }),
        ('Fechas', {
            'fields': ('fecha_vencimiento', 'fecha_completada')
        }),
        ('Resultado', {
            'fields': ('resultado',)
        }),
    )


@admin.register(SeguimientoTerritorial)
class SeguimientoTerritorialAdmin(admin.ModelAdmin):
    list_display = ['caso', 'tipo', 'territorial', 'resultado', 'fecha_seguimiento']
    list_filter = ['tipo', 'resultado']
    search_fields = ['caso__ciudadano_titular__nombre', 'cambios_detectados']

    fieldsets = (
        ('Seguimiento', {
            'fields': ('caso', 'territorial', 'tipo', 'fecha_seguimiento')
        }),
        ('Resultado', {
            'fields': ('resultado', 'cambios_detectados', 'proxima_accion', 'fecha_proxima_revision')
        }),
        ('Evidencias', {
            'fields': ('fotos', 'observaciones')
        }),
    )


@admin.register(HistorialEstadoCaso)
class HistorialEstadoCasoAdmin(admin.ModelAdmin):
    list_display = ['caso', 'estado_anterior', 'estado_nuevo', 'usuario', 'timestamp']
    list_filter = ['estado_anterior', 'estado_nuevo']
    search_fields = ['caso__ciudadano_titular__nombre', 'observacion']
    readonly_fields = ['timestamp']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
