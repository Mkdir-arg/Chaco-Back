from django.contrib.auth.models import User
from django.db import models

from core.models import TimeStamped
from legajos.models import Ciudadano


class Programa(TimeStamped):
    """Catálogo de programas sociales del sistema."""

    class TipoPrograma(models.TextChoices):
        ACOMPANAMIENTO_SOCIAL = "ACOMPANAMIENTO_SOCIAL", "Acompañamiento Social"
        NACHEC = "NACHEC", "ÑACHEC"
        ECONOMICO = "ECONOMICO", "Acompañamiento Económico"
        FAMILIAR = "FAMILIAR", "Acompañamiento Familiar"
        REDUCCION_DANOS = "REDUCCION_DANOS", "Reducción de Daños"
        REINSERCION_SOCIAL = "REINSERCION_SOCIAL", "Reinserción Social"
        CAPACITACION_COMUNITARIA = "CAPACITACION_COMUNITARIA", "Capacitación Comunitaria"

    class Naturaleza(models.TextChoices):
        UN_SOLO_ACTO = "UN_SOLO_ACTO", "Un solo acto"
        PERSISTENTE = "PERSISTENTE", "Persistente"

    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        ACTIVO = "ACTIVO", "Activo"
        SUSPENDIDO = "SUSPENDIDO", "Suspendido"
        INACTIVO = "INACTIVO", "Inactivo"

    codigo = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="Código")
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    tipo = models.CharField(max_length=50, blank=True, verbose_name="Tipo")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")

    naturaleza = models.CharField(
        max_length=20,
        choices=Naturaleza.choices,
        null=True,
        blank=True,
        verbose_name="Naturaleza",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
        db_index=True,
        verbose_name="Estado",
    )
    tiene_turnos = models.BooleanField(default=False, verbose_name="Tiene turnos")
    cupo_maximo = models.PositiveIntegerField(null=True, blank=True, verbose_name="Cupo máximo")
    tiene_lista_espera = models.BooleanField(default=False, verbose_name="Tiene lista de espera")

    icono = models.CharField(
        max_length=50,
        default="folder",
        verbose_name="Ícono",
        help_text="Nombre del ícono (ej: people, assessment, school)",
    )
    color = models.CharField(
        max_length=20,
        default="#6366f1",
        verbose_name="Color",
        help_text="Color hex para la UI (ej: #6366f1)",
    )
    orden = models.PositiveIntegerField(
        default=0,
        verbose_name="Orden",
        help_text="Orden de visualización en solapas (menor = primero)",
    )

    subsecretaria = models.ForeignKey(
        "core.Subsecretaria",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Subsecretaría",
    )

    class Meta:
        verbose_name = "Programa"
        verbose_name_plural = "Programas"
        ordering = ["orden", "nombre"]
        indexes = [
            models.Index(fields=["estado", "orden"]),
        ]

    def __str__(self):
        return self.nombre


class InscripcionPrograma(TimeStamped):
    """Registro de un ciudadano en un programa social."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACTIVO = "ACTIVO", "Activo"
        EN_SEGUIMIENTO = "EN_SEGUIMIENTO", "En Seguimiento"
        SUSPENDIDO = "SUSPENDIDO", "Suspendido"
        CERRADO = "CERRADO", "Cerrado"
        DADO_DE_BAJA = "DADO_DE_BAJA", "Dado de Baja"

    class ViaIngreso(models.TextChoices):
        DIRECTO = "DIRECTO", "Ingreso Directo"
        DERIVACION_INTERNA = "DERIVACION_INTERNA", "Derivación Interna"
        DERIVACION_EXTERNA = "DERIVACION_EXTERNA", "Derivación Externa"
        ESPONTANEO = "ESPONTANEO", "Espontáneo"

    ciudadano = models.ForeignKey(
        Ciudadano,
        on_delete=models.CASCADE,
        related_name="inscripciones_programas",
    )
    programa = models.ForeignKey(
        Programa,
        on_delete=models.PROTECT,
        related_name="inscripciones",
    )

    codigo = models.CharField(max_length=100, unique=True, editable=False, db_index=True)
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
    )
    via_ingreso = models.CharField(
        max_length=30,
        choices=ViaIngreso.choices,
        default=ViaIngreso.DIRECTO,
    )
    fecha_inscripcion = models.DateField(auto_now_add=True, db_index=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_cierre = models.DateField(null=True, blank=True, db_index=True)

    responsable = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programas_responsable",
    )

    legajo_id = models.UUIDField(null=True, blank=True)

    notas = models.TextField(blank=True)
    motivo_cierre = models.TextField(blank=True)

    class Meta:
        verbose_name = "Inscripción a Programa"
        verbose_name_plural = "Inscripciones a Programas"
        unique_together = [["ciudadano", "programa"]]
        ordering = ["-fecha_inscripcion"]
        indexes = [
            models.Index(fields=["ciudadano", "estado"]),
            models.Index(fields=["programa", "estado"]),
            models.Index(fields=["estado", "fecha_inscripcion"]),
        ]

    def __str__(self):
        return f"{self.ciudadano.nombre_completo} - {self.programa.nombre}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            from datetime import datetime
            self.codigo = f"{self.programa.codigo}-{datetime.now().strftime('%Y%m%d')}-{self.ciudadano.dni}"
        super().save(*args, **kwargs)

    @property
    def esta_activo(self):
        return self.estado in ["ACTIVO", "EN_SEGUIMIENTO"]


class DerivacionPrograma(TimeStamped):
    """Derivación de un ciudadano entre programas."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACEPTADA = "ACEPTADA", "Aceptada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        CANCELADA = "CANCELADA", "Cancelada"

    class Urgencia(models.TextChoices):
        BAJA = "BAJA", "Baja"
        MEDIA = "MEDIA", "Media"
        ALTA = "ALTA", "Alta"

    ciudadano = models.ForeignKey(
        Ciudadano,
        on_delete=models.CASCADE,
        related_name="derivaciones_programas",
    )
    programa_origen = models.ForeignKey(
        Programa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derivaciones_origen",
    )
    inscripcion_origen = models.ForeignKey(
        InscripcionPrograma,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derivaciones_realizadas",
    )
    programa_destino = models.ForeignKey(
        Programa,
        on_delete=models.PROTECT,
        related_name="derivaciones_destino",
    )

    motivo = models.TextField()
    urgencia = models.CharField(
        max_length=20,
        choices=Urgencia.choices,
        default=Urgencia.MEDIA,
        db_index=True,
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
        db_index=True,
    )

    derivado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="derivaciones_programas_realizadas",
    )

    respuesta = models.TextField(blank=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    respondido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derivaciones_programas_respondidas",
    )
    inscripcion_creada = models.OneToOneField(
        InscripcionPrograma,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="derivacion_origen",
    )

    class Meta:
        verbose_name = "Derivación entre Programas"
        verbose_name_plural = "Derivaciones entre Programas"
        ordering = ["-creado"]
        indexes = [
            models.Index(fields=["ciudadano", "estado"]),
            models.Index(fields=["programa_destino", "estado"]),
            models.Index(fields=["estado", "urgencia"]),
        ]

    def __str__(self):
        origen = self.programa_origen.nombre if self.programa_origen else "Espontáneo"
        return f"{self.ciudadano.nombre_completo}: {origen} → {self.programa_destino.nombre}"

    def aceptar(self, usuario, responsable=None):
        from django.db import transaction
        from django.utils import timezone

        with transaction.atomic():
            self.refresh_from_db()
            if self.estado != "PENDIENTE":
                raise ValueError("Esta derivación ya fue procesada")

            inscripcion_existente = InscripcionPrograma.objects.filter(
                ciudadano=self.ciudadano,
                programa=self.programa_destino,
                estado__in=["ACTIVO", "EN_SEGUIMIENTO"],
            ).first()

            if inscripcion_existente:
                self.estado = "ACEPTADA"
                self.fecha_respuesta = timezone.now()
                self.respondido_por = usuario
                self.inscripcion_creada = inscripcion_existente
                self.save()
                return inscripcion_existente

            inscripcion = InscripcionPrograma.objects.create(
                ciudadano=self.ciudadano,
                programa=self.programa_destino,
                via_ingreso="DERIVACION_INTERNA" if self.programa_origen else "DERIVACION_EXTERNA",
                estado="ACTIVO",
                responsable=responsable or usuario,
                notas=(
                    f"Derivado desde: {self.programa_origen.nombre if self.programa_origen else 'Espontáneo'}"
                    f"\nMotivo: {self.motivo}"
                ),
            )
            self.estado = "ACEPTADA"
            self.fecha_respuesta = timezone.now()
            self.respondido_por = usuario
            self.inscripcion_creada = inscripcion
            self.save()
            return inscripcion

    def rechazar(self, usuario, motivo_rechazo):
        from django.utils import timezone

        if self.estado != "PENDIENTE":
            raise ValueError("Solo se pueden rechazar derivaciones pendientes")
        self.estado = "RECHAZADA"
        self.respuesta = motivo_rechazo
        self.fecha_respuesta = timezone.now()
        self.respondido_por = usuario
        self.save()
