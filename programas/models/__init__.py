import json

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStamped
from legajos.models import Ciudadano


class Programa(TimeStamped):
    """Catálogo de programas sociales del sistema."""

    class TipoPrograma(models.TextChoices):
        ACOMPANAMIENTO_SOCIAL = "ACOMPANAMIENTO_SOCIAL", "Acompañamiento Social"
        ECONOMICO = "ECONOMICO", "Acompañamiento Económico"
        FAMILIAR = "FAMILIAR", "Acompañamiento Familiar"
        REDUCCION_DANOS = "REDUCCION_DANOS", "Reducción de Daños"
        REINSERCION_SOCIAL = "REINSERCION_SOCIAL", "Reinserción Social"
        CAPACITACION_COMUNITARIA = "CAPACITACION_COMUNITARIA", "Capacitación Comunitaria"
        BECAS = "BECAS", "Becas"
        DISPOSITIVOS = "DISPOSITIVOS", "Dispositivos"
        MERENDEROS = "MERENDEROS", "Merenderos"

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


# ===========================================================================
# Programa Dispositivos (épica #127 / análisis #128)
# ===========================================================================


class TipoDispositivo(TimeStamped):
    """Catálogo de tipos de institución del Programa Dispositivos."""

    codigo = models.CharField(max_length=50, unique=True, db_index=True, verbose_name="Código")
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    maneja_camas = models.BooleanField(default=False, verbose_name="Maneja camas")
    activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Tipo de dispositivo"
        verbose_name_plural = "Tipos de dispositivo"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Dispositivo(TimeStamped):
    """Legajo institucional de un dispositivo del Ministerio."""

    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        PENDIENTE_VALIDACION = "PENDIENTE_VALIDACION", "Pendiente de validación"
        ACTIVO = "ACTIVO", "Activo"
        OBSERVADO = "OBSERVADO", "Observado"
        RECHAZADO = "RECHAZADO", "Rechazado"
        INACTIVO = "INACTIVO", "Inactivo"
        CERRADO = "CERRADO", "Cerrado"

    tipo = models.ForeignKey(
        TipoDispositivo,
        on_delete=models.PROTECT,
        related_name="dispositivos",
        verbose_name="Tipo de dispositivo",
    )
    codigo = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="Código institucional")
    nombre = models.CharField(max_length=200, db_index=True, verbose_name="Nombre")
    domicilio = models.CharField(max_length=240, blank=True, verbose_name="Domicilio")
    localidad = models.CharField(max_length=120, blank=True, db_index=True, verbose_name="Localidad")
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    responsable_nombre = models.CharField(max_length=200, blank=True, verbose_name="Responsable")
    responsable_documento = models.CharField(max_length=20, blank=True, verbose_name="DNI/CUIT del responsable")
    contacto_telefono = models.CharField(max_length=40, blank=True, verbose_name="Teléfono")
    contacto_email = models.EmailField(blank=True, verbose_name="Email")
    horarios = models.TextField(blank=True, verbose_name="Días y horarios")
    camas_totales = models.PositiveIntegerField(default=0, verbose_name="Camas/plazas totales")
    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.BORRADOR,
        db_index=True,
        verbose_name="Estado",
    )

    class Meta:
        verbose_name = "Dispositivo"
        verbose_name_plural = "Dispositivos"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["tipo", "estado"]),
            models.Index(fields=["nombre", "estado"]),
            models.Index(fields=["nombre", "localidad"]),
        ]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class AsignacionDispositivo(TimeStamped):
    """Alcance fino de un rol sobre un dispositivo concreto."""

    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.CASCADE,
        related_name="asignaciones_roles",
        verbose_name="Dispositivo",
    )
    rol = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="asignaciones_dispositivos",
        verbose_name="Rol",
    )
    activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Asignación a dispositivo"
        verbose_name_plural = "Asignaciones a dispositivos"
        ordering = ["dispositivo", "rol"]
        constraints = [
            models.UniqueConstraint(
                fields=["dispositivo", "rol"],
                name="asignacion_dispositivo_unica_por_rol",
            )
        ]

    def __str__(self):
        return f"{self.rol} → {self.dispositivo}"


class TrazaDispositivoQuerySet(models.QuerySet):
    """Evita vías masivas de mutación para una auditoría solo-aditiva."""

    def update(self, **kwargs):
        raise ValidationError("Las trazas de dispositivos son inmutables.")

    def delete(self):
        raise ValidationError("Las trazas de dispositivos no se eliminan.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Las trazas de dispositivos son inmutables.")


class TrazaDispositivoManager(models.Manager.from_queryset(TrazaDispositivoQuerySet)):
    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Las trazas de dispositivos son inmutables.")


class TrazaDispositivo(models.Model):
    """Historial inmutable de altas, cambios y validaciones del dispositivo."""

    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.CASCADE,
        related_name="trazas",
        verbose_name="Dispositivo",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trazas_dispositivos",
        verbose_name="Usuario",
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    accion = models.CharField(max_length=40, verbose_name="Acción")
    estado_anterior = models.CharField(max_length=30, blank=True, verbose_name="Estado anterior")
    estado_nuevo = models.CharField(max_length=30, blank=True, verbose_name="Estado nuevo")
    detalle = models.TextField(blank=True, verbose_name="Detalle")
    objects = TrazaDispositivoManager()

    class Meta:
        verbose_name = "Traza de dispositivo"
        verbose_name_plural = "Trazas de dispositivos"
        ordering = ["creado_en", "id"]
        base_manager_name = "objects"
        default_manager_name = "objects"

    def __str__(self):
        return f"{self.dispositivo} · {self.accion}"

    @property
    def detalle_legible(self):
        """Presenta cambios de campos sin exponer el JSON de auditoría."""

        try:
            cambios = json.loads(self.detalle)
        except (TypeError, json.JSONDecodeError):
            return self.detalle
        if not isinstance(cambios, dict):
            return self.detalle
        return " · ".join(
            f"{campo}: {valores.get('anterior', '—')} → {valores.get('nuevo', '—')}"
            for campo, valores in cambios.items()
            if isinstance(valores, dict)
        )

    @staticmethod
    def _estado_legible(estado):
        if not estado:
            return "—"
        try:
            return Dispositivo.Estado(estado).label
        except ValueError:
            return estado

    @property
    def estado_anterior_legible(self):
        return self._estado_legible(self.estado_anterior)

    @property
    def estado_nuevo_legible(self):
        return self._estado_legible(self.estado_nuevo)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Las trazas de dispositivos son inmutables.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Las trazas de dispositivos no se eliminan.")


class Cama(TimeStamped):
    """Unidad de capacidad identificable dentro de un dispositivo."""

    class Estado(models.TextChoices):
        DISPONIBLE = "DISPONIBLE", "Disponible"
        RESERVADA = "RESERVADA", "Reservada"
        OCUPADA = "OCUPADA", "Ocupada"
        FUERA_SERVICIO = "FUERA_SERVICIO", "Fuera de servicio"

    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="camas",
        verbose_name="Dispositivo",
    )
    codigo = models.CharField(max_length=50, verbose_name="Código")
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.DISPONIBLE,
        db_index=True,
        verbose_name="Estado",
    )

    class Meta:
        verbose_name = "Cama/plaza"
        verbose_name_plural = "Camas/plazas"
        ordering = ["dispositivo", "codigo"]
        constraints = [
            models.UniqueConstraint(fields=["dispositivo", "codigo"], name="cama_codigo_unico_por_dispositivo")
        ]
        indexes = [models.Index(fields=["dispositivo", "estado"])]

    def __str__(self):
        return f"{self.dispositivo.codigo} · {self.codigo}"


class Admision(TimeStamped):
    """Estadía de un ciudadano en un dispositivo; admite reingresos."""

    class Estado(models.TextChoices):
        SOLICITADO = "SOLICITADO", "Solicitado"
        EN_REVISION = "EN_REVISION", "En revisión"
        LISTA_ESPERA = "LISTA_ESPERA", "Lista de espera"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"
        ALOJADO = "ALOJADO", "Alojado"
        EGRESADO = "EGRESADO", "Egresado"
        TRASLADADO = "TRASLADADO", "Trasladado"

    ciudadano = models.ForeignKey(
        Ciudadano,
        on_delete=models.PROTECT,
        related_name="admisiones_dispositivos",
        verbose_name="Ciudadano",
    )
    dispositivo = models.ForeignKey(
        Dispositivo,
        on_delete=models.PROTECT,
        related_name="admisiones",
        verbose_name="Dispositivo",
    )
    inscripcion_programa = models.ForeignKey(
        InscripcionPrograma,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admisiones_dispositivos",
        verbose_name="Membresía al programa",
    )
    cama = models.ForeignKey(
        Cama,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="admisiones",
        verbose_name="Cama/plaza",
    )
    fecha_ingreso = models.DateTimeField(verbose_name="Fecha de ingreso")
    fecha_egreso = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de egreso")
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.SOLICITADO,
        db_index=True,
        verbose_name="Estado",
    )
    es_reingreso = models.BooleanField(default=False, verbose_name="Es reingreso")
    motivo_egreso = models.TextField(blank=True, verbose_name="Motivo de egreso")
    destino_egreso = models.CharField(max_length=240, blank=True, verbose_name="Destino de egreso/traslado")

    class Meta:
        verbose_name = "Admisión/estadía"
        verbose_name_plural = "Admisiones/estadías"
        ordering = ["-fecha_ingreso"]
        indexes = [
            models.Index(fields=["ciudadano", "estado"]),
            models.Index(fields=["dispositivo", "estado"]),
            models.Index(fields=["cama", "estado"]),
        ]

    def __str__(self):
        return f"{self.ciudadano.nombre_completo} · {self.dispositivo.nombre}"

    def clean(self):
        super().clean()
        if self.cama_id and self.dispositivo_id and self.cama.dispositivo_id != self.dispositivo_id:
            raise ValidationError({"cama": "La cama debe pertenecer al dispositivo de la admisión."})

        if not self.inscripcion_programa_id:
            return

        if self.ciudadano_id and self.inscripcion_programa.ciudadano_id != self.ciudadano_id:
            raise ValidationError({"inscripcion_programa": "La membresía debe pertenecer al ciudadano de la admisión."})
        if self.inscripcion_programa.programa.codigo != Programa.TipoPrograma.DISPOSITIVOS:
            raise ValidationError({"inscripcion_programa": "La membresía debe ser del programa Dispositivos."})


# ===========================================================================
# Programa Merenderos (épica #127 / análisis #128)
# ===========================================================================


class Merendero(TimeStamped):
    """Legajo institucional de un merendero."""

    class Estado(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        SUSPENDIDO = "SUSPENDIDO", "Suspendido"
        CERRADO = "CERRADO", "Cerrado"

    codigo = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="Código institucional")
    nombre = models.CharField(max_length=200, db_index=True, verbose_name="Nombre")
    domicilio = models.CharField(max_length=240, verbose_name="Domicilio")
    zona = models.CharField(max_length=120, blank=True, verbose_name="Zona")
    barrio = models.CharField(max_length=120, blank=True, verbose_name="Barrio")
    telefono = models.CharField(max_length=40, blank=True, verbose_name="Teléfono")
    responsable_nombre = models.CharField(max_length=200, verbose_name="Responsable")
    responsable_documento = models.CharField(max_length=20, blank=True, verbose_name="DNI/CUIT del responsable")
    responsable_email = models.EmailField(blank=True, verbose_name="Email del responsable")
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ACTIVO,
        db_index=True,
        verbose_name="Estado",
    )

    class Meta:
        verbose_name = "Merendero"
        verbose_name_plural = "Merenderos"
        ordering = ["nombre"]
        indexes = [models.Index(fields=["nombre", "estado"])]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class SolicitudMerendero(TimeStamped):
    """Solicitud documentada para el alta o regularización de un merendero."""

    class Estado(models.TextChoices):
        BORRADOR = "BORRADOR", "Borrador"
        EN_REVISION = "EN_REVISION", "En revisión"
        OBSERVADA = "OBSERVADA", "Observada"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    merendero = models.ForeignKey(
        Merendero,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitudes",
        verbose_name="Merendero",
    )
    documentacion = models.FileField(
        upload_to="merenderos/solicitudes/%Y/%m/",
        verbose_name="Documentación respaldatoria",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
        db_index=True,
        verbose_name="Estado",
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    class Meta:
        verbose_name = "Solicitud de merendero"
        verbose_name_plural = "Solicitudes de merenderos"
        ordering = ["-creado"]
        indexes = [models.Index(fields=["merendero", "estado"])]

    def __str__(self):
        merendero = self.merendero.nombre if self.merendero_id else "Alta pendiente"
        return f"Solicitud #{self.pk} · {merendero}"


class EntregaMercaderia(TimeStamped):
    """Entrega histórica de kits de mercadería a un merendero."""

    merendero = models.ForeignKey(
        Merendero,
        on_delete=models.PROTECT,
        related_name="entregas_mercaderia",
        verbose_name="Merendero",
    )
    fecha = models.DateField(db_index=True, verbose_name="Fecha de entrega")
    cantidad_kits = models.PositiveIntegerField(verbose_name="Cantidad de kits")
    servicio = models.CharField(max_length=120, blank=True, verbose_name="Servicio")
    responsable_receptor = models.CharField(max_length=200, blank=True, verbose_name="Responsable receptor")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    anulada = models.BooleanField(default=False, db_index=True, verbose_name="Anulada")

    class Meta:
        verbose_name = "Entrega de mercadería"
        verbose_name_plural = "Entregas de mercadería"
        ordering = ["-fecha", "-creado"]
        indexes = [models.Index(fields=["merendero", "fecha"])]

    def __str__(self):
        return f"{self.merendero.nombre} · {self.fecha:%Y-%m-%d} · {self.cantidad_kits} kits"


class PrestacionMensual(TimeStamped):
    """Cabecera mensual de la prestación alimentaria F-02."""

    merendero = models.ForeignKey(
        Merendero,
        on_delete=models.PROTECT,
        related_name="prestaciones_mensuales",
        verbose_name="Merendero",
    )
    anio = models.PositiveSmallIntegerField(verbose_name="Año")
    mes = models.PositiveSmallIntegerField(verbose_name="Mes")
    servicios = models.JSONField(default=list, blank=True, verbose_name="Servicios habilitados")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    anulada = models.BooleanField(default=False, db_index=True, verbose_name="Anulada")

    class Meta:
        verbose_name = "Prestación alimentaria mensual"
        verbose_name_plural = "Prestaciones alimentarias mensuales"
        ordering = ["-anio", "-mes"]
        constraints = [
            models.UniqueConstraint(
                fields=["merendero", "anio", "mes"],
                name="prestacion_mensual_unica_por_merendero",
            ),
            models.CheckConstraint(check=models.Q(mes__gte=1, mes__lte=12), name="prestacion_mensual_mes_valido"),
        ]

    def __str__(self):
        return f"{self.merendero.nombre} · {self.mes:02d}/{self.anio}"


class PrestacionDiaria(TimeStamped):
    """Raciones informadas para un servicio en un día del F-02 mensual."""

    class Servicio(models.TextChoices):
        DESAYUNO = "DESAYUNO", "Desayuno/colación"
        ALMUERZO = "ALMUERZO", "Almuerzo"
        MERIENDA = "MERIENDA", "Merienda/colación"
        CENA = "CENA", "Cena"

    prestacion = models.ForeignKey(
        PrestacionMensual,
        on_delete=models.PROTECT,
        related_name="lineas_diarias",
        verbose_name="Prestación mensual",
    )
    dia = models.PositiveSmallIntegerField(verbose_name="Día")
    servicio = models.CharField(max_length=20, choices=Servicio.choices, verbose_name="Servicio")
    raciones = models.PositiveIntegerField(verbose_name="Raciones")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    firmado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prestaciones_diarias_firmadas",
        verbose_name="Firmado por",
    )
    anulada = models.BooleanField(default=False, db_index=True, verbose_name="Anulada")

    class Meta:
        verbose_name = "Línea diaria de prestación alimentaria"
        verbose_name_plural = "Líneas diarias de prestación alimentaria"
        ordering = ["prestacion", "dia", "servicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["prestacion", "dia", "servicio"],
                name="prestacion_diaria_unica_por_servicio",
            ),
            models.CheckConstraint(check=models.Q(dia__gte=1, dia__lte=31), name="prestacion_diaria_dia_valido"),
        ]

    def __str__(self):
        return f"{self.prestacion} · día {self.dia} · {self.get_servicio_display()}"


# ===========================================================================
# Programa Becas (épica #69 / análisis #70)
# ---------------------------------------------------------------------------
# Modelos propios del Programa Becas. Viven junto a los modelos genéricos de
# programas (`Programa`, `InscripcionPrograma`, `DerivacionPrograma`) pero son
# independientes: NO tienen FK al modelo genérico `Programa`. La instancia
# genérica `Programa(codigo="BECAS")` solo se usa para anclar el alcance del
# RBAC (roles de categoría "Programa") y la futura solapa del legajo.
# ===========================================================================


class TipoCampo(models.TextChoices):
    """Tipo de campo de una pregunta global o requisito nativo."""

    STRING = "STRING", "Texto"
    INT = "INT", "Número entero"
    SELECTOR = "SELECTOR", "Selector (una opción)"
    SELECTOR_MULTIPLE = "SELECTOR_MULTIPLE", "Selector múltiple"
    DATE = "DATE", "Fecha"
    ARCHIVO = "ARCHIVO", "Archivo adjunto"


class CampoTipoDispositivo(TimeStamped):
    """Campo configurable del formulario propio de un tipo de dispositivo."""

    tipo_dispositivo = models.ForeignKey(
        TipoDispositivo,
        on_delete=models.CASCADE,
        related_name="campos_configurados",
        verbose_name="Tipo de dispositivo",
    )
    seccion = models.CharField(max_length=200, verbose_name="Sección")
    nombre = models.CharField(max_length=240, verbose_name="Nombre")
    tipo_campo = models.CharField(max_length=20, choices=TipoCampo.choices, verbose_name="Tipo de campo")
    opciones = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Opciones",
        help_text="Lista de strings; solo para SELECTOR / SELECTOR_MULTIPLE.",
    )
    obligatorio = models.BooleanField(default=False, verbose_name="Obligatorio")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")

    class Meta:
        verbose_name = "Campo de tipo de dispositivo"
        verbose_name_plural = "Campos de tipos de dispositivo"
        ordering = ["orden", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_dispositivo", "seccion", "nombre"],
                name="uniq_campo_tipo_dispositivo_seccion_nombre",
            )
        ]

    def __str__(self):
        return f"{self.tipo_dispositivo}: {self.seccion} · {self.nombre}"


class Segmento(TimeStamped):
    """Sub-modalidad de la beca con cupo y requisitos nativos propios (§6.2)."""

    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    cupo_maximo = models.PositiveIntegerField(verbose_name="Cupo máximo")
    requiere_gps = models.BooleanField(
        default=False,
        verbose_name="Requiere geolocalización GPS",
        help_text="Si está activo, el formulario del territorial pide lat/lng.",
    )
    activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Segmento"
        verbose_name_plural = "Segmentos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def tiene_subsegmentos(self):
        return self.subsegmentos.exists()

    @property
    def cupo_distribuido(self):
        """Suma de cupos de los subsegmentos (0 si no tiene)."""
        return self.subsegmentos.aggregate(t=models.Sum("cupo_maximo"))["t"] or 0

    @property
    def cupo_disponible(self):
        """Cupo del segmento aún no distribuido en subsegmentos."""
        return self.cupo_maximo - self.cupo_distribuido

    @property
    def cupo_maximo_efectivo(self):
        """Cupo total del segmento (referencia para CupoSegmento)."""
        return self.cupo_maximo


class Subsegmento(TimeStamped):
    """Nivel opcional dentro de un segmento, con cupo propio (RN-35/40)."""

    segmento = models.ForeignKey(
        Segmento,
        on_delete=models.CASCADE,
        related_name="subsegmentos",
        verbose_name="Segmento",
    )
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    cupo_maximo = models.PositiveIntegerField(verbose_name="Cupo máximo")

    class Meta:
        verbose_name = "Subsegmento"
        verbose_name_plural = "Subsegmentos"
        ordering = ["segmento", "nombre"]
        unique_together = [["segmento", "nombre"]]

    def __str__(self):
        return f"{self.segmento.nombre} / {self.nombre}"

    def clean(self):
        """RN-40: sum(hermanos.cupo_maximo) + nuevo_cupo <= segmento.cupo_maximo."""
        super().clean()
        if self.segmento_id and self.cupo_maximo is not None:
            hermanos = Subsegmento.objects.filter(segmento_id=self.segmento_id)
            if self.pk:
                hermanos = hermanos.exclude(pk=self.pk)
            suma = hermanos.aggregate(t=models.Sum("cupo_maximo"))["t"] or 0
            tope = self.segmento.cupo_maximo
            if suma + self.cupo_maximo > tope:
                disponible = max(tope - suma, 0)
                raise ValidationError(
                    f"El cupo del subsegmento ({self.cupo_maximo}) más los existentes "
                    f"({suma}) supera el cupo del segmento ({tope}). "
                    f"Máximo disponible: {disponible}."
                )


class CupoSegmento(TimeStamped):
    """Contador de cupo ocupado por segmento. La ocupación efectiva (post-SIS)
    queda fuera del alcance de esta versión; el modelo es la estructura base."""

    segmento = models.OneToOneField(
        Segmento,
        on_delete=models.CASCADE,
        related_name="cupo",
        verbose_name="Segmento",
    )
    cupo_ocupado = models.PositiveIntegerField(default=0, verbose_name="Cupo ocupado")

    class Meta:
        verbose_name = "Cupo de Segmento"
        verbose_name_plural = "Cupos de Segmentos"
        constraints = [
            models.CheckConstraint(
                check=models.Q(cupo_ocupado__gte=0),
                name="cupo_segmento_ocupado_no_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.segmento.nombre}: {self.cupo_ocupado}/{self.cupo_maximo_efectivo}"

    @property
    def cupo_maximo_efectivo(self):
        return self.segmento.cupo_maximo_efectivo

    def clean(self):
        super().clean()
        if self.segmento_id and self.cupo_ocupado > self.cupo_maximo_efectivo:
            raise ValidationError(
                f"El cupo ocupado ({self.cupo_ocupado}) no puede superar el cupo "
                f"máximo del segmento ({self.cupo_maximo_efectivo})."
            )


class Convocatoria(TimeStamped):
    """Agrupador dentro del programa; apunta a un segmento (requerido) y a un
    subsegmento opcional de ese segmento (RN-30)."""

    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    segmento = models.ForeignKey(
        Segmento,
        on_delete=models.PROTECT,
        related_name="convocatorias",
        verbose_name="Segmento",
    )
    subsegmento = models.ForeignKey(
        Subsegmento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="convocatorias",
        verbose_name="Subsegmento",
    )
    fecha_inicio = models.DateField(verbose_name="Fecha de inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de fin")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")
    # Trazabilidad del cierre automático por vencimiento (procesar_vencimientos).
    # Distingue la baja por fecha de la desactivación manual y guarda el cuándo.
    cerrada_automaticamente = models.BooleanField(
        default=False,
        verbose_name="Cerrada por vencimiento",
        help_text="La cerró el proceso de vencimientos al pasar la fecha de fin (no una baja manual).",
    )
    cerrada_el = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de cierre automático",
    )

    class Meta:
        verbose_name = "Convocatoria"
        verbose_name_plural = "Convocatorias"
        ordering = ["-fecha_inicio", "nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        """El subsegmento (si se indica) debe pertenecer al segmento elegido."""
        super().clean()
        if self.subsegmento_id and self.segmento_id:
            if self.subsegmento.segmento_id != self.segmento_id:
                raise ValidationError({"subsegmento": "El subsegmento debe pertenecer al segmento seleccionado."})

    @property
    def esta_vencida(self):
        """Vencida = la fecha de fin ya pasó (el corte usa el 'hoy' de la zona
        horaria del proyecto, igual que ``Relevamiento.esta_vencido``)."""
        from django.utils import timezone

        return self.fecha_fin is not None and self.fecha_fin < timezone.localdate()


class Relevamiento(TimeStamped):
    """Campaña de campo asignada a un territorial. Nombre auto-generado."""

    class Estado(models.TextChoices):
        ASIGNADO = "ASIGNADO", "Asignado"
        EN_CURSO = "EN_CURSO", "En curso"
        FINALIZANDO = "FINALIZANDO", "Finalizando (sync)"
        FINALIZADO = "FINALIZADO", "Finalizado"
        EN_REVISION = "EN_REVISION", "En revisión"
        TERMINADO = "TERMINADO", "Terminado"

    nombre = models.CharField(max_length=100, editable=False, verbose_name="Nombre")
    convocatoria = models.ForeignKey(
        Convocatoria,
        on_delete=models.PROTECT,
        related_name="relevamientos",
        verbose_name="Convocatoria",
    )
    territorial = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="relevamientos_asignados",
        verbose_name="Territorial",
    )
    fecha_asignada = models.DateField(verbose_name="Fecha asignada")
    zona = models.CharField(max_length=200, verbose_name="Zona")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ASIGNADO,
        db_index=True,
        verbose_name="Estado",
    )
    fecha_finalizado = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de finalización")

    class Meta:
        verbose_name = "Relevamiento"
        verbose_name_plural = "Relevamientos"
        ordering = ["-fecha_asignada", "nombre"]
        indexes = [
            models.Index(fields=["estado", "fecha_asignada"]),
        ]

    def __str__(self):
        return self.nombre

    @classmethod
    def proximo_nombre(cls):
        """Nombre autogenerado del próximo relevamiento.

        Usa ``Max(id)`` en vez de ``count()`` (evita el full scan y la carrera
        de dos altas simultáneas con el mismo número).
        """
        siguiente = (cls.objects.aggregate(m=models.Max("id"))["m"] or 0) + 1
        return f"Relevamiento {siguiente:03d}"

    def save(self, *args, **kwargs):
        if not self.nombre:
            self.nombre = self.proximo_nombre()
        super().save(*args, **kwargs)

    @property
    def segmento(self):
        return self.convocatoria.segmento

    @property
    def esta_vencido(self):
        """Vencido = sigue abierto en campo y la fecha asignada ya pasó."""
        from django.utils import timezone

        return (
            self.estado in (self.Estado.ASIGNADO, self.Estado.EN_CURSO)
            and self.fecha_asignada is not None
            and self.fecha_asignada < timezone.localdate()
        )


class PreguntaGlobal(TimeStamped):
    """Pregunta del cuestionario social (requisito general); aplica a todos los
    formularios. Los adjuntos obligatorios fijos se modelan como tipo ARCHIVO."""

    texto = models.CharField(max_length=500, verbose_name="Texto")
    tipo = models.CharField(max_length=20, choices=TipoCampo.choices, verbose_name="Tipo de campo")
    opciones = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Opciones",
        help_text="Lista de strings; solo para SELECTOR / SELECTOR_MULTIPLE.",
    )
    activo = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name="Activo",
        help_text="Si está inactivo no aparece en el formulario.",
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    obligatorio = models.BooleanField(default=True, verbose_name="Obligatorio")

    class Meta:
        verbose_name = "Pregunta global"
        verbose_name_plural = "Preguntas globales"
        ordering = ["orden", "id"]

    def __str__(self):
        return self.texto


class RequisitoNativo(TimeStamped):
    """Requisito configurable de un segmento (o subsegmento). Genera un campo
    obligatorio en el formulario del territorial (RN-32)."""

    texto = models.CharField(max_length=500, verbose_name="Texto")
    tipo = models.CharField(max_length=20, choices=TipoCampo.choices, verbose_name="Tipo de campo")
    opciones = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Opciones",
        help_text="Lista de strings; solo para SELECTOR / SELECTOR_MULTIPLE.",
    )
    segmento = models.ForeignKey(
        Segmento,
        on_delete=models.CASCADE,
        related_name="requisitos",
        verbose_name="Segmento",
    )
    subsegmento = models.ForeignKey(
        Subsegmento,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="requisitos",
        verbose_name="Subsegmento",
        help_text="Si es nulo, el requisito es del segmento; si no, del subsegmento.",
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    obligatorio = models.BooleanField(default=True, verbose_name="Obligatorio")

    class Meta:
        verbose_name = "Requisito nativo"
        verbose_name_plural = "Requisitos nativos"
        ordering = ["orden", "id"]

    def __str__(self):
        destino = self.subsegmento.nombre if self.subsegmento_id else self.segmento.nombre
        return f"{destino}: {self.texto}"

    def clean(self):
        """El subsegmento (si se indica) debe pertenecer al segmento."""
        super().clean()
        if self.subsegmento_id and self.segmento_id:
            if self.subsegmento.segmento_id != self.segmento_id:
                raise ValidationError({"subsegmento": "El subsegmento debe pertenecer al segmento seleccionado."})


class AsignacionCoordinador(TimeStamped):
    """Asignación de un coordinador a un segmento (alcance fino del rol)."""

    segmento = models.ForeignKey(
        Segmento,
        on_delete=models.CASCADE,
        related_name="asignaciones_coordinador",
        verbose_name="Segmento",
    )
    coordinador = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="segmentos_coordinados",
        verbose_name="Coordinador",
    )
    activo = models.BooleanField(default=True, db_index=True, verbose_name="Activo")
    fecha_asignacion = models.DateField(auto_now_add=True, verbose_name="Fecha de asignación")

    class Meta:
        verbose_name = "Asignación de coordinador"
        verbose_name_plural = "Asignaciones de coordinadores"
        unique_together = [["segmento", "coordinador"]]
        ordering = ["segmento", "coordinador"]

    def __str__(self):
        return f"{self.coordinador} → {self.segmento.nombre}"


class AsignacionTerritorial(TimeStamped):
    """Asignación de un territorial a un segmento (un territorial → un segmento).

    Se crea/edita únicamente desde el ABM de Usuarios (obligatoria al asignar
    un rol con capacidad ``becas.campo``); el detalle del segmento solo la
    muestra. Acota qué territoriales pueden recibir relevamientos de cada
    convocatoria (el relevamiento hereda el segmento de su convocatoria).
    """

    segmento = models.ForeignKey(
        Segmento,
        on_delete=models.CASCADE,
        related_name="asignaciones_territorial",
        verbose_name="Segmento",
    )
    territorial = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="asignacion_territorial",
        verbose_name="Territorial",
    )
    fecha_asignacion = models.DateField(auto_now_add=True, verbose_name="Fecha de asignación")

    class Meta:
        verbose_name = "Asignación de territorial"
        verbose_name_plural = "Asignaciones de territoriales"
        ordering = ["segmento", "territorial"]

    def __str__(self):
        return f"{self.territorial} → {self.segmento.nombre}"


class Formulario(TimeStamped):
    """Una persona relevada (1 por relevamiento). Llega del territorial y el
    backoffice lo revisa (aprobado/rechazado). La validación SIS y la ocupación
    de cupo quedan fuera del alcance de esta versión."""

    class Estado(models.TextChoices):
        ENVIADO = "ENVIADO", "Enviado"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"
        BAJA = "BAJA", "Dado de baja"

    relevamiento = models.ForeignKey(
        Relevamiento,
        on_delete=models.CASCADE,
        related_name="formularios",
        verbose_name="Relevamiento",
    )
    ciudadano = models.ForeignKey(
        Ciudadano,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="formularios_becas",
        verbose_name="Ciudadano",
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.ENVIADO,
        db_index=True,
        verbose_name="Estado",
    )
    motivo_rechazo = models.TextField(blank=True, verbose_name="Motivo de rechazo")
    validado_renaper = models.BooleanField(default=False, verbose_name="Validado RENAPER")

    # Bloque C — Contacto (manual, obligatorio)
    celular = models.CharField(max_length=20, verbose_name="Celular")
    email_contacto = models.EmailField(verbose_name="Correo electrónico")

    # Bloque D — Apoderado (solo si el ciudadano es menor; RN-22)
    apoderado_nombre = models.CharField(max_length=120, blank=True, verbose_name="Nombre del apoderado")
    apoderado_apellido = models.CharField(max_length=120, blank=True, verbose_name="Apellido del apoderado")
    apoderado_fecha_nacimiento = models.DateField(
        null=True, blank=True, verbose_name="Fecha de nacimiento del apoderado"
    )

    # Geolocalización (solo si el segmento lo requiere; §6.2)
    gps_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="GPS latitud")
    gps_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="GPS longitud")

    # Respuestas dinámicas: {"globales": {pk: valor}, "requisitos": {pk: valor}}
    data = models.JSONField(default=dict, blank=True, verbose_name="Respuestas")

    # Identificación offline (cuando ciudadano=null en el sync)
    datos_identificacion = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Datos de identificación (offline)",
        help_text="dni, nombre, apellido, fecha_nacimiento, origen. Se limpia al resolver el ciudadano.",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="formularios_becas_creados",
        verbose_name="Creado por",
    )

    class Meta:
        verbose_name = "Formulario"
        verbose_name_plural = "Formularios"
        ordering = ["-creado"]
        indexes = [
            models.Index(fields=["relevamiento", "estado"]),
            models.Index(fields=["estado"]),
        ]

    def __str__(self):
        if self.ciudadano_id:
            return f"Formulario #{self.pk} - {self.ciudadano}"
        return f"Formulario #{self.pk} (sin ciudadano)"


class AdjuntoFormulario(TimeStamped):
    """Archivo subido por el territorial para un campo tipo ARCHIVO (pregunta
    global o requisito nativo) de un formulario (#82)."""

    formulario = models.ForeignKey(
        Formulario,
        on_delete=models.CASCADE,
        related_name="adjuntos",
        verbose_name="Formulario",
    )
    pregunta_global = models.ForeignKey(
        PreguntaGlobal,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="adjuntos_formulario",
        verbose_name="Pregunta global",
    )
    requisito_nativo = models.ForeignKey(
        RequisitoNativo,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="adjuntos_formulario",
        verbose_name="Requisito nativo",
    )
    archivo = models.FileField(upload_to="becas/adjuntos/%Y/%m/", verbose_name="Archivo")

    class Meta:
        verbose_name = "Adjunto de formulario"
        verbose_name_plural = "Adjuntos de formulario"
        ordering = ["-creado"]
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(pregunta_global__isnull=False, requisito_nativo__isnull=True)
                    | models.Q(pregunta_global__isnull=True, requisito_nativo__isnull=False)
                ),
                name="adjunto_formulario_una_sola_referencia",
            )
        ]

    def __str__(self):
        campo = self.pregunta_global or self.requisito_nativo
        return f"Formulario #{self.formulario_id} · {campo}"


class TracaFormulario(models.Model):
    """Registro inmutable de una edición de campo de un formulario (RN-14/29).
    Solo se agrega, nunca se modifica."""

    formulario = models.ForeignKey(
        Formulario,
        on_delete=models.CASCADE,
        related_name="trazas",
        verbose_name="Formulario",
    )
    editado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="trazas_formulario",
        verbose_name="Editado por",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    campo = models.CharField(max_length=200, verbose_name="Campo")
    valor_anterior = models.TextField(blank=True, verbose_name="Valor anterior")
    valor_nuevo = models.TextField(blank=True, verbose_name="Valor nuevo")

    class Meta:
        verbose_name = "Traza de formulario"
        verbose_name_plural = "Trazas de formularios"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.formulario_id} · {self.campo} ({self.created_at:%Y-%m-%d %H:%M})"


class ListaEspera(TimeStamped):
    """Persona validada-OK sin cupo disponible. La lógica de promoción depende
    de SIS y queda fuera del alcance de esta versión; el modelo es la base."""

    formulario = models.ForeignKey(
        Formulario,
        on_delete=models.CASCADE,
        related_name="lista_espera",
        verbose_name="Formulario",
    )
    segmento = models.ForeignKey(
        Segmento,
        on_delete=models.CASCADE,
        related_name="lista_espera",
        verbose_name="Segmento",
    )
    posicion = models.PositiveIntegerField(verbose_name="Posición")
    promovido = models.BooleanField(default=False, verbose_name="Promovido")
    fecha_ingreso = models.DateField(auto_now_add=True, verbose_name="Fecha de ingreso")

    class Meta:
        verbose_name = "Lista de espera"
        verbose_name_plural = "Listas de espera"
        ordering = ["segmento", "posicion"]
        indexes = [
            models.Index(fields=["segmento", "promovido"]),
        ]

    def __str__(self):
        return f"{self.segmento.nombre} #{self.posicion}"
