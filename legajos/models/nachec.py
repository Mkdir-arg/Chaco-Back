"""
Modelos para el Programa Ñachec - Asistencia Social Familiar
Reutiliza: Ciudadano, VinculoFamiliar, Adjunto, User
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from core.models import TimeStamped
from .base import Ciudadano


# ============================================================================
# TEXT CHOICES - Estados y Opciones
# ============================================================================

class EstadoCaso(models.TextChoices):
    """Estados del caso Ñachec"""
    DERIVADO = "DERIVADO", "Derivado"
    EN_REVISION = "EN_REVISION", "En Revisión"
    A_ASIGNAR = "A_ASIGNAR", "A Asignar"
    ASIGNADO = "ASIGNADO", "Asignado"
    EN_RELEVAMIENTO = "EN_RELEVAMIENTO", "En Relevamiento"
    EVALUADO = "EVALUADO", "Evaluado"
    PLAN_DEFINIDO = "PLAN_DEFINIDO", "Plan Definido"
    EN_EJECUCION = "EN_EJECUCION", "En Ejecución"
    EN_SEGUIMIENTO = "EN_SEGUIMIENTO", "En Seguimiento"
    CERRADO = "CERRADO", "Cerrado"
    SUSPENDIDO = "SUSPENDIDO", "Suspendido"
    RECHAZADO = "RECHAZADO", "Rechazado"


class PrioridadCaso(models.TextChoices):
    """Prioridad del caso"""
    BAJA = "BAJA", "Baja"
    MEDIA = "MEDIA", "Media"
    ALTA = "ALTA", "Alta"
    URGENTE = "URGENTE", "Urgente"


class RangoIngreso(models.TextChoices):
    """Rango de ingreso mensual"""
    SIN_INGRESOS = "SIN_INGRESOS", "Sin ingresos"
    HASTA_50K = "HASTA_50K", "Hasta $50.000"
    ENTRE_50K_100K = "50K_100K", "$50.000 - $100.000"
    ENTRE_100K_200K = "100K_200K", "$100.000 - $200.000"
    MAS_200K = "MAS_200K", "Más de $200.000"


class FuenteIngreso(models.TextChoices):
    """Fuente principal de ingresos"""
    FORMAL = "FORMAL", "Trabajo formal"
    INFORMAL = "INFORMAL", "Trabajo informal"
    PLANES = "PLANES", "Planes sociales"
    JUBILACION = "JUBILACION", "Jubilación/Pensión"
    NINGUNO = "NINGUNO", "Ninguno"
    MIXTO = "MIXTO", "Mixto"


class SituacionLaboral(models.TextChoices):
    """Situación laboral del titular"""
    EMPLEADO = "EMPLEADO", "Empleado"
    DESEMPLEADO = "DESEMPLEADO", "Desempleado"
    CHANGAS = "CHANGAS", "Changas/Ocasional"
    CUENTA_PROPIA = "CUENTA_PROPIA", "Cuenta propia"
    JUBILADO = "JUBILADO", "Jubilado"
    ESTUDIANTE = "ESTUDIANTE", "Estudiante"


class TipoVivienda(models.TextChoices):
    """Tipo de vivienda"""
    PROPIA = "PROPIA", "Propia"
    ALQUILADA = "ALQUILADA", "Alquilada"
    PRESTADA = "PRESTADA", "Prestada"
    PRECARIA = "PRECARIA", "Precaria"
    OCUPADA = "OCUPADA", "Ocupada"
    CALLE = "CALLE", "Situación de calle"


class MaterialVivienda(models.TextChoices):
    """Material predominante de la vivienda"""
    LADRILLO = "LADRILLO", "Ladrillo"
    MADERA = "MADERA", "Madera"
    CHAPA = "CHAPA", "Chapa"
    CARTON = "CARTON", "Cartón"
    MIXTO = "MIXTO", "Mixto"


class CoberturaSalud(models.TextChoices):
    """Cobertura de salud"""
    OBRA_SOCIAL = "OBRA_SOCIAL", "Obra social"
    PREPAGA = "PREPAGA", "Prepaga"
    PUBLICA = "PUBLICA", "Pública"
    NINGUNA = "NINGUNA", "Ninguna"


class AccesoAlimentos(models.TextChoices):
    """Acceso a alimentos"""
    SUFICIENTE = "SUFICIENTE", "Suficiente"
    INSUFICIENTE = "INSUFICIENTE", "Insuficiente"
    CRITICO = "CRITICO", "Crítico"


class TipoPrestacion(models.TextChoices):
    """Tipos de prestación"""
    ALIMENTARIA = "ALIMENTARIA", "Alimentaria"
    VIVIENDA = "VIVIENDA", "Vivienda"
    CAPACITACION = "CAPACITACION", "Capacitación"
    EMPLEO = "EMPLEO", "Empleo"
    SALUD = "SALUD", "Salud"
    EDUCACION = "EDUCACION", "Educación"
    EMPRENDIMIENTO = "EMPRENDIMIENTO", "Emprendimiento"
    OTRO = "OTRO", "Otro"


class EstadoPrestacion(models.TextChoices):
    """Estados de la prestación"""
    CREADA = "CREADA", "Creada"
    PROGRAMADA = "PROGRAMADA", "Programada"
    EN_PROCESO = "EN_PROCESO", "En Proceso"
    EN_CURSO = "EN_CURSO", "En Curso"  # DEPRECATED: usar EN_PROCESO
    ENTREGADA = "ENTREGADA", "Entregada"
    COMPLETADA = "COMPLETADA", "Completada"
    CANCELADA = "CANCELADA", "Cancelada"


class FrecuenciaPrestacion(models.TextChoices):
    """Frecuencia de la prestación"""
    UNICA = "UNICA", "Única"
    SEMANAL = "SEMANAL", "Semanal"
    QUINCENAL = "QUINCENAL", "Quincenal"
    MENSUAL = "MENSUAL", "Mensual"


class TipoTarea(models.TextChoices):
    """Tipos de tarea"""
    RELEVAMIENTO = "RELEVAMIENTO", "Relevamiento inicial"
    AMPLIACION = "AMPLIACION", "Ampliación de información"
    ENTREGA = "ENTREGA", "Programar entrega"
    SEGUIMIENTO = "SEGUIMIENTO", "Seguimiento"
    INSCRIPCION = "INSCRIPCION", "Inscripción"
    VALIDACION = "VALIDACION", "Validación técnica"
    OTRO = "OTRO", "Otro"


class EstadoTarea(models.TextChoices):
    """Estados de la tarea"""
    PENDIENTE = "PENDIENTE", "Pendiente"
    EN_PROCESO = "EN_PROCESO", "En Proceso"
    COMPLETADA = "COMPLETADA", "Completada"
    CANCELADA = "CANCELADA", "Cancelada"


class TipoSeguimiento(models.TextChoices):
    """Tipo de seguimiento territorial"""
    VISITA = "VISITA", "Visita domiciliaria"
    LLAMADA = "LLAMADA", "Llamada telefónica"


class ResultadoSeguimiento(models.TextChoices):
    """Resultado del seguimiento"""
    MEJORA = "MEJORA", "Mejora"
    IGUAL = "IGUAL", "Igual"
    PEOR = "PEOR", "Peor"


class CategoriaVulnerabilidad(models.TextChoices):
    """Categoría de vulnerabilidad"""
    ALTO = "ALTO", "Alto"
    MEDIO = "MEDIO", "Medio"
    BAJO = "BAJO", "Bajo"


# ============================================================================
# MODELOS
# ============================================================================

class CasoNachec(TimeStamped):
    """Caso del Programa Ñachec - Instancia operativa"""

    # Ciudadano titular (reutiliza modelo existente)
    ciudadano_titular = models.ForeignKey(
        Ciudadano,
        on_delete=models.PROTECT,
        related_name="casos_nachec"
    )

    # Estado y prioridad
    estado = models.CharField(
        max_length=20,
        choices=EstadoCaso.choices,
        default=EstadoCaso.DERIVADO,
        db_index=True
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PrioridadCaso.choices,
        default=PrioridadCaso.MEDIA,
        db_index=True
    )

    # Ubicación
    municipio = models.CharField(max_length=100, db_index=True)
    localidad = models.CharField(max_length=100, db_index=True)
    direccion = models.TextField()
    referencias_domicilio = models.TextField(blank=True)

    # Asignaciones (roles)
    operador_admision = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos_nachec_admision"
    )
    coordinador = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos_nachec_coordinacion"
    )
    territorial = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos_nachec_territorial"
    )
    referente_programa = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="casos_nachec_referente"
    )

    # Fechas clave
    fecha_derivacion = models.DateField(db_index=True)
    fecha_asignacion = models.DateField(null=True, blank=True)
    fecha_inicio_relevamiento = models.DateTimeField(null=True, blank=True)
    fecha_relevamiento = models.DateField(null=True, blank=True)
    fecha_evaluacion = models.DateField(null=True, blank=True)
    fecha_cierre = models.DateField(null=True, blank=True)

    # Motivos
    motivo_derivacion = models.TextField()
    motivo_rechazo = models.TextField(blank=True)
    motivo_suspension = models.TextField(blank=True)
    motivo_cierre = models.TextField(blank=True)
    instrucciones_asignacion = models.TextField(null=True, blank=True)

    # SLA y alertas
    sla_revision = models.DateField(null=True, blank=True)
    sla_relevamiento = models.DateField(null=True, blank=True)
    tiene_duplicado = models.BooleanField(default=False)
    doc_pendiente = models.BooleanField(default=False)

    # Observaciones
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Caso Ñachec"
        verbose_name_plural = "Casos Ñachec"
        ordering = ["-fecha_derivacion"]
        indexes = [
            models.Index(fields=["estado", "prioridad"]),
            models.Index(fields=["municipio", "localidad"]),
            models.Index(fields=["territorial", "estado"]),
            models.Index(fields=["fecha_derivacion"]),
        ]

    def __str__(self):
        return f"Caso {self.id} - {self.ciudadano_titular.nombre_completo} ({self.get_estado_display()})"

    def recalcular_estado_por_prestaciones(self):
        """Recalcula estado del caso según prestaciones activas del plan vigente"""
        # Solo aplica si caso está en EN_EJECUCION o EN_SEGUIMIENTO
        if self.estado not in ['EN_EJECUCION', 'EN_SEGUIMIENTO']:
            return False

        # Obtener plan vigente
        plan_vigente = PlanIntervencionNachec.objects.filter(caso=self, vigente=True).first()
        if not plan_vigente:
            return False

        # Contar prestaciones activas
        prestaciones_activas = PrestacionNachec.objects.filter(
            plan=plan_vigente,
            estado__in=['PROGRAMADA', 'EN_PROCESO', 'EN_CURSO']
        ).count()

        estado_anterior = self.estado
        cambio = False

        if prestaciones_activas == 0 and self.estado == 'EN_EJECUCION':
            self.estado = 'EN_SEGUIMIENTO'
            cambio = True
        elif prestaciones_activas > 0 and self.estado == 'EN_SEGUIMIENTO':
            self.estado = 'EN_EJECUCION'
            cambio = True

        if cambio:
            self.save()
            return {'cambio': True, 'estado_anterior': estado_anterior, 'estado_nuevo': self.estado, 'prestaciones_activas': prestaciones_activas}

        return {'cambio': False}


class RelevamientoNachec(TimeStamped):
    """Relevamiento sociofamiliar"""

    caso = models.OneToOneField(
        CasoNachec,
        on_delete=models.CASCADE,
        related_name="relevamiento"
    )
    territorial = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="relevamientos_nachec"
    )

    # Composición familiar
    cantidad_convivientes = models.PositiveIntegerField()
    hay_embarazo = models.BooleanField(default=False)
    hay_discapacidad = models.BooleanField(default=False)
    detalle_discapacidad = models.TextField(blank=True)

    # Ingresos y empleo
    ingreso_mensual_rango = models.CharField(
        max_length=20,
        choices=RangoIngreso.choices
    )
    fuente_ingreso = models.CharField(
        max_length=20,
        choices=FuenteIngreso.choices
    )
    situacion_laboral = models.CharField(
        max_length=20,
        choices=SituacionLaboral.choices
    )

    # Vivienda
    tipo_vivienda = models.CharField(
        max_length=20,
        choices=TipoVivienda.choices
    )
    material_predominante = models.CharField(
        max_length=20,
        choices=MaterialVivienda.choices
    )
    tiene_agua = models.BooleanField(default=False)
    tiene_luz = models.BooleanField(default=False)
    tiene_gas = models.BooleanField(default=False)
    tiene_cloaca = models.BooleanField(default=False)
    personas_por_habitacion = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Salud
    cobertura_salud = models.CharField(
        max_length=20,
        choices=CoberturaSalud.choices
    )
    condiciones_cronicas = models.TextField(blank=True)

    # Educación
    menores_escolarizados = models.BooleanField(default=True)
    motivo_no_escolarizacion = models.TextField(blank=True)

    # Alimentación
    acceso_alimentos = models.CharField(
        max_length=20,
        choices=AccesoAlimentos.choices
    )
    frecuencia_comidas = models.PositiveIntegerField(
        help_text="Cantidad de comidas diarias"
    )

    # Riesgos y urgencias
    hay_violencia = models.BooleanField(default=False)
    detalle_violencia = models.TextField(blank=True)
    hay_situacion_calle = models.BooleanField(default=False)
    urgencia_alimentaria = models.BooleanField(default=False)

    # Geolocalización
    latitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )
    longitud = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )

    # Estado del relevamiento
    completado = models.BooleanField(default=False)
    fecha_finalizacion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    observaciones_cierre = models.TextField(blank=True, help_text="Observaciones al finalizar relevamiento")

    # Scoring de vulnerabilidad (versionado)
    score_total = models.PositiveIntegerField(null=True, blank=True, help_text="Score 0-100")
    score_categoria = models.CharField(max_length=10, blank=True, choices=CategoriaVulnerabilidad.choices)
    score_detalle = models.JSONField(null=True, blank=True, help_text="Desglose por dimensión")
    score_version = models.CharField(max_length=10, default="v1", help_text="Versión del algoritmo de scoring")

    class Meta:
        verbose_name = "Relevamiento Ñachec"
        verbose_name_plural = "Relevamientos Ñachec"

    def __str__(self):
        return f"Relevamiento - Caso {self.caso.id}"

    def calcular_scoring(self):
        """Calcula scoring de vulnerabilidad v1 (0-100)"""
        score = 0
        detalle = {}

        # Familia (0-15)
        familia = 0
        if self.cantidad_convivientes >= 6:
            familia += 5
        elif self.cantidad_convivientes >= 4:
            familia += 3
        if self.hay_embarazo:
            familia += 5
        if self.hay_discapacidad:
            familia += 5
        detalle['familia'] = min(familia, 15)

        # Ingresos (0-25)
        ingresos = 0
        if self.ingreso_mensual_rango in ['SIN_INGRESOS', 'HASTA_50K']:
            ingresos += 15
        elif self.ingreso_mensual_rango == '50K_100K':
            ingresos += 10
        if self.fuente_ingreso in ['NINGUNO', 'PLANES']:
            ingresos += 5
        if self.situacion_laboral == 'DESEMPLEADO':
            ingresos += 5
        detalle['ingresos'] = min(ingresos, 25)

        # Vivienda (0-20)
        vivienda = 0
        if self.tipo_vivienda in ['PRECARIA', 'CALLE', 'OCUPADA']:
            vivienda += 10
        if self.material_predominante in ['CARTON', 'CHAPA']:
            vivienda += 5
        servicios = sum([self.tiene_agua, self.tiene_luz, self.tiene_gas, self.tiene_cloaca])
        if servicios <= 1:
            vivienda += 5
        elif servicios == 2:
            vivienda += 3
        detalle['vivienda'] = min(vivienda, 20)

        # Salud/Alimentación (0-25)
        salud = 0
        if self.cobertura_salud == 'NINGUNA':
            salud += 8
        if self.acceso_alimentos == 'CRITICO':
            salud += 10
        elif self.acceso_alimentos == 'INSUFICIENTE':
            salud += 5
        if self.frecuencia_comidas < 2:
            salud += 7
        elif self.frecuencia_comidas == 2:
            salud += 3
        detalle['salud'] = min(salud, 25)

        # Riesgos (0-15)
        riesgos = 0
        if self.hay_violencia:
            riesgos += 8
        if self.urgencia_alimentaria:
            riesgos += 7
        detalle['riesgos'] = min(riesgos, 15)

        # Total
        score = sum(detalle.values())

        # Categoría
        if score <= 30:
            categoria = 'BAJO'
        elif score <= 60:
            categoria = 'MEDIO'
        else:
            categoria = 'ALTO'

        return score, categoria, detalle

    def is_completo(self):
        """Verifica si el relevamiento está completo"""
        campos_obligatorios = [
            self.cantidad_convivientes,
            self.ingreso_mensual_rango,
            self.fuente_ingreso,
            self.situacion_laboral,
            self.tipo_vivienda,
            self.material_predominante,
            self.cobertura_salud,
            self.acceso_alimentos,
            self.frecuencia_comidas
        ]
        return all(campo for campo in campos_obligatorios)

    def faltantes_por_seccion(self):
        """Devuelve dict con campos faltantes por sección del wizard"""
        faltantes = {
            'familia': [],
            'ingresos': [],
            'vivienda': [],
            'salud': [],
            'riesgos': []
        }

        # Familia
        if not self.cantidad_convivientes:
            faltantes['familia'].append('Cantidad de convivientes')

        # Ingresos
        if not self.ingreso_mensual_rango:
            faltantes['ingresos'].append('Rango de ingreso')
        if not self.fuente_ingreso:
            faltantes['ingresos'].append('Fuente de ingreso')
        if not self.situacion_laboral:
            faltantes['ingresos'].append('Situación laboral')

        # Vivienda
        if not self.tipo_vivienda:
            faltantes['vivienda'].append('Tipo de vivienda')
        if not self.material_predominante:
            faltantes['vivienda'].append('Material predominante')

        # Salud
        if not self.cobertura_salud:
            faltantes['salud'].append('Cobertura de salud')
        if not self.acceso_alimentos:
            faltantes['salud'].append('Acceso a alimentos')
        if not self.frecuencia_comidas:
            faltantes['salud'].append('Frecuencia de comidas')

        return faltantes


class EvaluacionVulnerabilidad(TimeStamped):
    """Evaluación de vulnerabilidad con scoring"""

    caso = models.OneToOneField(
        CasoNachec,
        on_delete=models.CASCADE,
        related_name="evaluacion"
    )
    relevamiento = models.ForeignKey(
        RelevamientoNachec,
        on_delete=models.PROTECT,
        related_name="evaluaciones"
    )
    evaluador = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="evaluaciones_nachec"
    )

    # Scoring del relevamiento (copiado para trazabilidad)
    score_total = models.PositiveIntegerField(help_text="Score 0-100")
    score_version = models.CharField(max_length=10, default="v1")
    categoria_sugerida = models.CharField(
        max_length=10,
        choices=CategoriaVulnerabilidad.choices,
        help_text="Categoría calculada por scoring"
    )

    # Dictamen profesional
    dictamen = models.TextField(help_text="Dictamen del evaluador (min 20 caracteres)")
    categoria_final = models.CharField(
        max_length=10,
        choices=CategoriaVulnerabilidad.choices,
        help_text="Categoría final confirmada por evaluador"
    )

    # Override
    override_categoria = models.BooleanField(
        default=False,
        help_text="True si categoría final difiere de sugerida"
    )
    justificacion_override = models.TextField(
        blank=True,
        help_text="Justificación obligatoria si hay override"
    )

    fecha_evaluacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evaluación de Vulnerabilidad"
        verbose_name_plural = "Evaluaciones de Vulnerabilidad"

    def __str__(self):
        return f"Evaluación - Caso {self.caso.id} ({self.get_categoria_final_display()})"


class PlanIntervencionNachec(TimeStamped):
    """Plan de intervención con componentes"""

    caso = models.ForeignKey(
        CasoNachec,
        on_delete=models.CASCADE,
        related_name="planes"
    )
    referente = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="planes_nachec"
    )

    # Objetivo y horizonte
    objetivo_general = models.TextField()
    fecha_inicio = models.DateField()
    horizonte_dias = models.PositiveIntegerField(
        help_text="30, 60 o 90 días"
    )

    # Componentes (líneas de acción)
    incluye_alimentacion = models.BooleanField(default=False)
    incluye_vivienda = models.BooleanField(default=False)
    incluye_empleo = models.BooleanField(default=False)
    incluye_salud = models.BooleanField(default=False)
    incluye_educacion = models.BooleanField(default=False)
    incluye_emprendimiento = models.BooleanField(default=False)

    # Estado
    vigente = models.BooleanField(default=True, db_index=True)
    fecha_activacion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Plan de Intervención Ñachec"
        verbose_name_plural = "Planes de Intervención Ñachec"
        ordering = ["-fecha_inicio"]

    def __str__(self):
        return f"Plan - Caso {self.caso.id} ({'Vigente' if self.vigente else 'Histórico'})"


class PrestacionNachec(TimeStamped):
    """Prestación concreta (ayuda)"""

    plan = models.ForeignKey(
        PlanIntervencionNachec,
        on_delete=models.CASCADE,
        related_name="prestaciones"
    )
    caso = models.ForeignKey(
        CasoNachec,
        on_delete=models.CASCADE,
        related_name="prestaciones"
    )

    # Tipo y descripción
    tipo = models.CharField(
        max_length=20,
        choices=TipoPrestacion.choices,
        db_index=True
    )
    subtipo = models.CharField(max_length=100, blank=True)
    descripcion = models.TextField()

    # Estado y frecuencia
    estado = models.CharField(
        max_length=20,
        choices=EstadoPrestacion.choices,
        default=EstadoPrestacion.CREADA,
        db_index=True
    )
    frecuencia = models.CharField(
        max_length=20,
        choices=FrecuenciaPrestacion.choices
    )

    # Fechas
    fecha_programada = models.DateField(null=True, blank=True)
    fecha_entregada = models.DateField(null=True, blank=True)
    sla_hasta = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha límite de cumplimiento (SLA)"
    )

    # Responsable y lugar
    responsable = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="prestaciones_nachec"
    )
    lugar_entrega = models.CharField(max_length=200, blank=True)

    # Confirmación de entrega
    receptor_nombre = models.CharField(max_length=120, blank=True)
    confirmacion_firma = models.FileField(
        upload_to="nachec/confirmaciones/",
        blank=True
    )
    confirmacion_foto = models.FileField(
        upload_to="nachec/confirmaciones/",
        blank=True
    )
    confirmacion_codigo = models.CharField(max_length=50, blank=True)

    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Prestación Ñachec"
        verbose_name_plural = "Prestaciones Ñachec"
        ordering = ["-fecha_programada"]
        indexes = [
            models.Index(fields=["caso", "estado"]),
            models.Index(fields=["tipo", "estado"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - Caso {self.caso.id}"


class TareaNachec(TimeStamped):
    """Tarea asignable con vencimiento"""

    caso = models.ForeignKey(
        CasoNachec,
        on_delete=models.CASCADE,
        related_name="tareas"
    )
    prestacion = models.ForeignKey(
        PrestacionNachec,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tareas"
    )

    # Tipo y descripción
    tipo = models.CharField(
        max_length=20,
        choices=TipoTarea.choices,
        db_index=True
    )
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()

    # Asignación
    asignado_a = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="tareas_nachec_asignadas"
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="tareas_nachec_creadas"
    )

    # Estado y prioridad
    estado = models.CharField(
        max_length=20,
        choices=EstadoTarea.choices,
        default=EstadoTarea.PENDIENTE,
        db_index=True
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PrioridadCaso.choices,
        default=PrioridadCaso.MEDIA
    )

    # Fechas
    fecha_vencimiento = models.DateField(db_index=True)
    fecha_completada = models.DateTimeField(null=True, blank=True)

    # Resultado
    resultado = models.TextField(blank=True)

    class Meta:
        verbose_name = "Tarea Ñachec"
        verbose_name_plural = "Tareas Ñachec"
        ordering = ["fecha_vencimiento", "-prioridad"]
        indexes = [
            models.Index(fields=["asignado_a", "estado"]),
            models.Index(fields=["fecha_vencimiento", "estado"]),
        ]

    def __str__(self):
        return f"{self.titulo} - {self.asignado_a.get_full_name()}"


class SeguimientoTerritorial(TimeStamped):
    """Seguimiento territorial periódico"""

    caso = models.ForeignKey(
        CasoNachec,
        on_delete=models.CASCADE,
        related_name="seguimientos"
    )
    territorial = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="seguimientos_nachec"
    )

    # Tipo y fecha
    tipo = models.CharField(
        max_length=10,
        choices=TipoSeguimiento.choices
    )
    fecha_seguimiento = models.DateTimeField()

    # Resultado
    resultado = models.CharField(
        max_length=10,
        choices=ResultadoSeguimiento.choices
    )
    cambios_detectados = models.TextField()
    proxima_accion = models.TextField()
    fecha_proxima_revision = models.DateField()

    # Evidencias (JSON con URLs de fotos)
    fotos = models.JSONField(blank=True, null=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = "Seguimiento Territorial"
        verbose_name_plural = "Seguimientos Territoriales"
        ordering = ["-fecha_seguimiento"]
        indexes = [
            models.Index(fields=["caso", "-fecha_seguimiento"]),
            models.Index(fields=["territorial", "-fecha_seguimiento"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - Caso {self.caso.id} ({self.fecha_seguimiento.date()})"


class HistorialEstadoCaso(TimeStamped):
    """Historial de cambios de estado del caso"""

    caso = models.ForeignKey(
        CasoNachec,
        on_delete=models.CASCADE,
        related_name="historial_estados"
    )
    estado_anterior = models.CharField(max_length=20)
    estado_nuevo = models.CharField(max_length=20)
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="cambios_estado_nachec"
    )
    observacion = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historial de Estado"
        verbose_name_plural = "Historial de Estados"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["caso", "-timestamp"]),
        ]

    def __str__(self):
        return f"Caso {self.caso.id}: {self.estado_anterior} → {self.estado_nuevo}"
