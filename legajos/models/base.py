from functools import cached_property

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.exceptions import ValidationError
from core.models import TimeStamped, LegajoBase
# from simple_history.models import HistoricalRecords  # Comentado temporalmente


class Ciudadano(TimeStamped):
    """Modelo para ciudadanos del sistema de legajos"""

    class Genero(models.TextChoices):
        MASCULINO = "M", "Masculino"
        FEMENINO = "F", "Femenino"
        NO_BINARIO = "X", "No binario"

    dni = models.CharField(max_length=20, unique=True, db_index=True)
    nombre = models.CharField(max_length=120, db_index=True)
    apellido = models.CharField(max_length=120, db_index=True)
    fecha_nacimiento = models.DateField(null=True, blank=True, db_index=True)
    genero = models.CharField(max_length=1, choices=Genero.choices, blank=True, db_index=True)
    telefono = models.CharField(max_length=40, blank=True, db_index=True)
    email = models.EmailField(blank=True, db_index=True)
    domicilio = models.CharField(max_length=240, blank=True)

    # Datos territoriales
    provincia = models.ForeignKey(
        'core.Provincia',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ciudadanos'
    )
    municipio = models.ForeignKey(
        'core.Municipio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ciudadanos'
    )
    localidad = models.ForeignKey(
        'core.Localidad',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ciudadanos'
    )

    activo = models.BooleanField(default=True, db_index=True)

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ciudadano_perfil',
        verbose_name='Usuario del portal',
    )

    # --- Perfil ampliado ---

    foto = models.ImageField(
        upload_to='ciudadanos/fotos/',
        blank=True,
        null=True,
        verbose_name='Foto',
    )

    # Situación habitacional
    class TipoVivienda(models.TextChoices):
        PROPIA = 'PROPIA', 'Propia'
        ALQUILADA = 'ALQUILADA', 'Alquilada'
        PRESTADA = 'PRESTADA', 'Prestada / cedida'
        VILLA = 'VILLA', 'Villa / asentamiento'
        SIN_TECHO = 'SIN_TECHO', 'Sin techo'
        OTRO = 'OTRO', 'Otro'

    class TenenciaVivienda(models.TextChoices):
        TITULAR = 'TITULAR', 'Titular'
        CONYUGE = 'CONYUGE', 'Cónyuge / conviviente'
        FAMILIAR = 'FAMILIAR', 'Familiar'
        INQUILINO = 'INQUILINO', 'Inquilino'
        OCUPANTE = 'OCUPANTE', 'Ocupante sin título'
        OTRO = 'OTRO', 'Otro'

    tipo_vivienda = models.CharField(
        max_length=20, choices=TipoVivienda.choices, blank=True, verbose_name='Tipo de vivienda',
    )
    tenencia_vivienda = models.CharField(
        max_length=20, choices=TenenciaVivienda.choices, blank=True, verbose_name='Tenencia de vivienda',
    )
    condiciones_vivienda = models.TextField(blank=True, verbose_name='Condiciones de la vivienda')

    # Situación laboral
    class SituacionLaboral(models.TextChoices):
        EMPLEADO_FORMAL = 'EMPLEADO_FORMAL', 'Empleado formal'
        EMPLEADO_INFORMAL = 'EMPLEADO_INFORMAL', 'Empleado informal'
        CUENTAPROPISTA = 'CUENTAPROPISTA', 'Cuenta propia'
        DESEMPLEADO = 'DESEMPLEADO', 'Desempleado'
        JUBILADO = 'JUBILADO', 'Jubilado / pensionado'
        ESTUDIANTE = 'ESTUDIANTE', 'Estudiante'
        SIN_ACTIVIDAD = 'SIN_ACTIVIDAD', 'Sin actividad'
        OTRO = 'OTRO', 'Otro'

    class IngresoEstimado(models.TextChoices):
        SIN_INGRESO = 'SIN_INGRESO', 'Sin ingreso'
        MENOS_CBT = 'MENOS_CBT', 'Menos de una CBT'
        ENTRE_1_2_CBT = 'ENTRE_1_2_CBT', 'Entre 1 y 2 CBT'
        MAS_2_CBT = 'MAS_2_CBT', 'Más de 2 CBT'

    situacion_laboral = models.CharField(
        max_length=20, choices=SituacionLaboral.choices, blank=True, verbose_name='Situación laboral',
    )
    ingreso_estimado = models.CharField(
        max_length=20, choices=IngresoEstimado.choices, blank=True, verbose_name='Ingreso estimado',
    )
    obra_social = models.CharField(max_length=200, blank=True, verbose_name='Obra social / prepaga')

    # Situación educativa
    class NivelEducativo(models.TextChoices):
        SIN_INSTRUCCION = 'SIN_INSTRUCCION', 'Sin instrucción'
        PRIMARIO_INCOMPLETO = 'PRIMARIO_INCOMPLETO', 'Primario incompleto'
        PRIMARIO_COMPLETO = 'PRIMARIO_COMPLETO', 'Primario completo'
        SECUNDARIO_INCOMPLETO = 'SECUNDARIO_INCOMPLETO', 'Secundario incompleto'
        SECUNDARIO_COMPLETO = 'SECUNDARIO_COMPLETO', 'Secundario completo'
        TERCIARIO = 'TERCIARIO', 'Terciario / universitario'
        POSGRADO = 'POSGRADO', 'Posgrado'

    nivel_educativo = models.CharField(
        max_length=25, choices=NivelEducativo.choices, blank=True, verbose_name='Nivel educativo',
    )

    # Cobertura médica (sensible)
    cobertura_medica = models.CharField(max_length=200, blank=True, verbose_name='Cobertura médica')
    medicacion_habitual = models.TextField(blank=True, verbose_name='Medicación habitual')

    # Documentación migratoria
    class DniFisico(models.TextChoices):
        TIENE = 'TIENE', 'Tiene DNI'
        EN_TRAMITE = 'EN_TRAMITE', 'En trámite'
        NO_TIENE = 'NO_TIENE', 'No tiene'

    class EstadoRenaper(models.TextChoices):
        REGISTRADO = 'REGISTRADO', 'Registrado'
        NO_REGISTRADO = 'NO_REGISTRADO', 'No registrado'
        CON_OBSERVACION = 'CON_OBSERVACION', 'Con observación'
        FALLECIDO = 'FALLECIDO', 'Fallecido'

    class EstadoMigratorio(models.TextChoices):
        NACIONAL = 'NACIONAL', 'Nacional'
        RESIDENTE_PERMANENTE = 'RESIDENTE_PERMANENTE', 'Residente permanente'
        RESIDENTE_TEMPORARIO = 'RESIDENTE_TEMPORARIO', 'Residente temporario'
        SOLICITANTE_ASILO = 'SOLICITANTE_ASILO', 'Solicitante de asilo'
        IRREGULAR = 'IRREGULAR', 'Situación irregular'

    dni_fisico = models.CharField(
        max_length=15, choices=DniFisico.choices, blank=True, verbose_name='DNI físico',
    )
    estado_renaper = models.CharField(
        max_length=20, choices=EstadoRenaper.choices, blank=True, verbose_name='Estado RENAPER',
    )
    estado_migratorio = models.CharField(
        max_length=25, choices=EstadoMigratorio.choices, blank=True, verbose_name='Estado migratorio',
    )

    # Observaciones generales
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    # Historial de cambios
    # history = HistoricalRecords()  # Comentado temporalmente

    class Meta:
        verbose_name = "Ciudadano"
        verbose_name_plural = "Ciudadanos"
        indexes = [
            models.Index(fields=["dni"]),
            models.Index(fields=["apellido", "nombre"]),
            models.Index(fields=["activo", "apellido"]),
            models.Index(fields=["email"]),
            models.Index(fields=["tipo_vivienda"]),
            models.Index(fields=["situacion_laboral"]),
            models.Index(fields=["nivel_educativo"]),
            models.Index(fields=["estado_renaper"]),
        ]

    def __str__(self):
        return f"{self.apellido}, {self.nombre} ({self.dni})"

    # Managers
    objects = models.Manager()  # Manager por defecto

    @property
    def nombre_completo(self):
        """Retorna el nombre completo del ciudadano"""
        return f"{self.nombre} {self.apellido}"

    @property
    def edad(self):
        """Edad en años calculada desde fecha_nacimiento (None si no hay fecha)."""
        if not self.fecha_nacimiento:
            return None
        from datetime import date
        hoy = date.today()
        return hoy.year - self.fecha_nacimiento.year - (
            (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )


class LegajoAtencion(LegajoBase):
    """Legajo de atención individual para ciudadanos"""

    class ViaIngreso(models.TextChoices):
        ESPONTANEA = "ESPONTANEA", "Consulta espontánea"
        DERIVACION = "DERIVACION", "Derivación"
        JUDICIAL = "JUDICIAL", "Judicial"
        HOSPITAL = "HOSPITAL", "Hospital/Guardia"

    responsable = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legajos_atencion_responsable",
        limit_choices_to={'groups__name': 'Responsable'},
        verbose_name="Responsable",
        help_text="Usuario con rol de Responsable asignado al legajo"
    )
    via_ingreso = models.CharField(
        max_length=20,
        choices=ViaIngreso.choices,
        default=ViaIngreso.ESPONTANEA,
        db_index=True
    )
    fecha_admision = models.DateField(auto_now_add=True, db_index=True)
    plan_vigente = models.BooleanField(default=False, db_index=True)
    nivel_riesgo = models.CharField(
        max_length=20,
        default="BAJO",
        db_index=True
    )

    # Historial de cambios
    # history = HistoricalRecords()  # Comentado temporalmente

    class Meta:
        verbose_name = "Acompañamiento"
        verbose_name_plural = "Acompañamientos"
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["nivel_riesgo", "fecha_admision"]),
            models.Index(fields=["plan_vigente", "estado"]),
            models.Index(fields=["via_ingreso", "fecha_admision"]),
        ]

    @cached_property
    def inscripcion_programa(self):
        from ..linking import get_linked_inscripcion_for_legajo

        return get_linked_inscripcion_for_legajo(self)

    @property
    def ciudadano(self):
        inscripcion = self.inscripcion_programa
        return inscripcion.ciudadano if inscripcion else None

    @property
    def ciudadano_id(self):
        ciudadano = self.ciudadano
        return ciudadano.id if ciudadano else None

    @property
    def programa(self):
        inscripcion = self.inscripcion_programa
        return inscripcion.programa if inscripcion else None

    @property
    def dispositivo(self):
        return self.programa

    @property
    def seguimientos(self):
        return self.historial_contactos

    def __str__(self):
        ciudadano = self.ciudadano
        if ciudadano:
            return f"Legajo {self.codigo} - {ciudadano}"
        return f"Legajo {self.codigo}"

    def get_absolute_url(self):
        from django.urls import reverse

        if self.ciudadano_id:
            return reverse('legajos:ciudadano_detalle', kwargs={'pk': self.ciudadano_id})
        return reverse('legajos:lista')

    def puede_cerrar(self):
        """Verifica si el legajo puede cerrarse"""
        from datetime import datetime, timedelta
        if self.estado == 'CERRADO':
            return False, "El legajo ya está cerrado"

        # Verificar seguimiento reciente (últimos 30 días)
        fecha_limite = datetime.now().date() - timedelta(days=30)
        tiene_seguimiento_reciente = self.historial_contactos.filter(
            creado__date__gte=fecha_limite
        ).exists()

        if self.plan_vigente and not tiene_seguimiento_reciente:
            return False, "Requiere seguimiento reciente o justificación para cerrar"

        return True, "Puede cerrarse"

    def cerrar(self, motivo_cierre=None, usuario=None):
        """Cierra el legajo"""
        from datetime import datetime
        puede, mensaje = self.puede_cerrar()
        if not puede and not motivo_cierre:
            raise ValidationError(mensaje)

        self.estado = 'CERRADO'
        self.fecha_cierre = datetime.now().date()
        if motivo_cierre:
            if not self.notas:
                self.notas = f"Motivo de cierre: {motivo_cierre}"
            else:
                self.notas += f"\n\nMotivo de cierre: {motivo_cierre}"
        self.save()

    def reabrir(self, motivo_reapertura=None, usuario=None):
        """Reabre el legajo"""
        if self.estado != 'CERRADO':
            raise ValidationError("Solo se pueden reabrir legajos cerrados")

        self.estado = 'EN_SEGUIMIENTO'
        self.fecha_cierre = None
        if motivo_reapertura:
            if not self.notas:
                self.notas = f"Motivo de reapertura: {motivo_reapertura}"
            else:
                self.notas += f"\n\nMotivo de reapertura: {motivo_reapertura}"
        self.save()

    @property
    def dias_desde_admision(self):
        """Días transcurridos desde la admisión"""
        from datetime import datetime
        return (datetime.now().date() - self.fecha_admision).days

    # Managers
    objects = models.Manager()  # Manager por defecto

    @property
    def tiempo_primer_contacto(self):
        """Días hasta el primer seguimiento"""
        return None


class Derivacion(TimeStamped):
    """Derivaciones entre dispositivos"""

    class Urgencia(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACEPTADA = "ACEPTADA", "Aceptada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    legajo = models.ForeignKey(
        LegajoAtencion,
        on_delete=models.CASCADE,
        related_name="derivaciones"
    )
    actividad_destino = models.ForeignKey(
        'programas.Programa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derivaciones",
        verbose_name="Programa destino"
    )
    motivo = models.TextField()
    urgencia = models.CharField(
        max_length=20,
        choices=Urgencia.choices,
        default=Urgencia.MEDIA,
        db_index=True
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True
    )
    respuesta = models.CharField(max_length=120, blank=True)
    fecha_aceptacion = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "Derivación"
        verbose_name_plural = "Derivaciones"
        ordering = ["-creado"]
        indexes = [
            models.Index(fields=["legajo", "estado"]),
            models.Index(fields=["urgencia"]),
            models.Index(fields=["estado", "urgencia"]),
        ]

    def __str__(self):
        return f"Derivación de legajo {self.legajo_id}"

    def clean(self):
        pass


class Adjunto(TimeStamped):
    """Adjuntos genéricos para cualquier modelo"""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    content_object = GenericForeignKey("content_type", "object_id")
    archivo = models.FileField(upload_to="adjuntos/")
    etiqueta = models.CharField(max_length=120, blank=True)

    class Meta:
        verbose_name = "Adjunto"
        verbose_name_plural = "Adjuntos"
        ordering = ["-creado"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"Adjunto - {self.etiqueta or self.archivo.name}"


class AlertaCiudadano(TimeStamped):
    """Sistema de alertas automáticas para ciudadanos"""

    class TipoAlerta(models.TextChoices):
        RIESGO_ALTO = "RIESGO_ALTO", "Riesgo Alto"
        RIESGO_SUICIDA = "RIESGO_SUICIDA", "Riesgo Suicida"
        VIOLENCIA = "VIOLENCIA", "Situación de Violencia"
        SIN_CONTACTO = "SIN_CONTACTO", "Sin Contacto Prolongado"
        SIN_EVALUACION = "SIN_EVALUACION", "Sin Evaluación Inicial"
        SIN_PLAN = "SIN_PLAN", "Sin Plan de Intervención"
        EVENTO_CRITICO = "EVENTO_CRITICO", "Evento Crítico Reciente"
        DERIVACION_PENDIENTE = "DERIVACION_PENDIENTE", "Derivación Pendiente"
        SIN_RED_FAMILIAR = "SIN_RED_FAMILIAR", "Sin Red Familiar"
        SIN_CONSENTIMIENTO = "SIN_CONSENTIMIENTO", "Sin Consentimiento"
        CONTACTOS_FALLIDOS = "CONTACTOS_FALLIDOS", "Contactos Fallidos"
        PLAN_VENCIDO = "PLAN_VENCIDO", "Plan Vencido"

    class Prioridad(models.TextChoices):
        CRITICA = "CRITICA", "Crítica"
        ALTA = "ALTA", "Alta"
        MEDIA = "MEDIA", "Media"
        BAJA = "BAJA", "Baja"

    ciudadano = models.ForeignKey(
        Ciudadano,
        on_delete=models.CASCADE,
        related_name="alertas"
    )
    legajo = models.ForeignKey(
        LegajoAtencion,
        on_delete=models.CASCADE,
        related_name="alertas",
        null=True,
        blank=True
    )
    tipo = models.CharField(max_length=30, choices=TipoAlerta.choices, db_index=True)
    prioridad = models.CharField(max_length=10, choices=Prioridad.choices, db_index=True)
    mensaje = models.CharField(max_length=200)
    activa = models.BooleanField(default=True, db_index=True)
    fecha_cierre = models.DateTimeField(null=True, blank=True, db_index=True)
    cerrada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alertas_cerradas"
    )

    class Meta:
        verbose_name = "Alerta de Ciudadano"
        verbose_name_plural = "Alertas de Ciudadanos"
        ordering = ["-creado"]
        indexes = [
            models.Index(fields=["ciudadano", "activa"]),
            models.Index(fields=["tipo", "prioridad"]),
            models.Index(fields=["legajo", "activa"]),
            models.Index(fields=["activa", "prioridad", "-creado"]),
            models.Index(fields=["cerrada_por", "fecha_cierre"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.ciudadano}"

    def cerrar(self, usuario=None):
        """Cerrar la alerta"""
        from django.utils import timezone
        self.activa = False
        self.fecha_cierre = timezone.now()
        self.cerrada_por = usuario
        self.save()

    @property
    def color_css(self):
        """Retorna las clases CSS según la prioridad"""
        colores = {
            'CRITICA': 'bg-red-100 text-red-800 border-red-200',
            'ALTA': 'bg-orange-100 text-orange-800 border-orange-200',
            'MEDIA': 'bg-yellow-100 text-yellow-800 border-yellow-200',
            'BAJA': 'bg-blue-100 text-blue-800 border-blue-200',
        }
        return colores.get(self.prioridad, 'bg-gray-100 text-gray-800 border-gray-200')
