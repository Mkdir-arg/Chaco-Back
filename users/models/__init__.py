import uuid

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.rbac import (
    CATEGORIA_BACKOFFICE,
    CATEGORIA_PROGRAMA,
    CATEGORIAS_ROL_CHOICES,
    todas_las_capacidades,
)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    dark_mode = models.BooleanField(default=True)
    dni = models.CharField(max_length=8, unique=True, null=True, blank=True, verbose_name="DNI")
    telefono = models.CharField(max_length=30, blank=True, default="", verbose_name="Teléfono")
    institucion = models.CharField(max_length=255, blank=True, default="", verbose_name="Institución")
    observacion = models.TextField(blank=True, default="", verbose_name="Observación")
    backoffice_session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        editable=False,
        verbose_name="Sesión activa de Backoffice",
    )
    # El alta manda una clave provisoria por correo: hasta que el usuario la
    # cambie, el middleware no lo deja operar (RN-C2 del análisis #236).
    debe_cambiar_contrasena = models.BooleanField(
        default=False,
        editable=False,
        verbose_name="Debe cambiar la contraseña",
    )

    def __str__(self):
        return f"Perfil de {self.user.username}"


class RolMeta(models.Model):
    """Metadatos de un Rol del backoffice. Un Rol = ``Group`` + ``RolMeta``.

    Aporta la descripción autoexplicada, la categoría, la marca de protegido
    (no editable/eliminable desde la UI) y el estado activo (un rol inactivo no
    es asignable). Las capacidades se tildan sobre el ``Group`` vía
    ``group.permissions``.
    """

    grupo = models.OneToOneField(Group, on_delete=models.CASCADE, related_name="meta", verbose_name="Rol")
    # OPS-06 fase 2: identificador **estable** de los roles que siembra el arranque.
    # Los seeds los buscaban por ``Group.name``, que el ABM deja renombrar: renombrar
    # «Becas — Coordinador» hacía que el arranque siguiente creara un segundo rol con
    # el nombre canónico, vacío de usuarios y con todas las capacidades. Con la clave,
    # el seed reconoce el rol renombrado y lo respeta.
    #
    # Nula para todo rol creado desde el ABM: solo la llevan los sembrados. Es única
    # —MySQL y MariaDB admiten varios NULL en un índice único— así que dos roles no
    # pueden disputarse la misma identidad.
    clave = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        unique=True,
        editable=False,
        verbose_name="Clave del rol sembrado",
        help_text="Identificador estable de los roles que crea el arranque. Vacío en los roles creados a mano.",
    )
    descripcion = models.TextField(blank=True, default="", verbose_name="Descripción")
    categoria = models.CharField(
        max_length=20,
        choices=CATEGORIAS_ROL_CHOICES,
        default=CATEGORIA_BACKOFFICE,
        verbose_name="Categoría",
    )
    protegido = models.BooleanField(default=False, verbose_name="Protegido")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    programa = models.ForeignKey(
        "programas.Programa",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="roles_meta",
        verbose_name="Programa",
        help_text="Solo para roles de categoría 'Programa': acota el rol a ese programa.",
    )

    class Meta:
        verbose_name = "Metadato de rol"
        verbose_name_plural = "Metadatos de roles"

    def clean(self):
        super().clean()
        if self.categoria == CATEGORIA_PROGRAMA and self.programa_id is None:
            raise ValidationError({"programa": "Debés seleccionar un programa para los roles de categoría Programa."})
        if self.categoria != CATEGORIA_PROGRAMA and self.programa_id is not None:
            raise ValidationError(
                {"programa": "Solo los roles de categoría Programa pueden tener un programa asociado."}
            )

    def __str__(self):
        return self.grupo.name


class CapacidadRevocada(models.Model):
    """Capacidad que una migración le **quitó** a un rol, con su motivo.

    Existe para que una migración de datos que revoca accesos tenga **reversa real**:
    desaplicarla no puede «recalcular» lo que borró, porque el dato ya no está. Acá
    queda la fila exacta (rol, codename) que se quitó, así que la reversa restituye lo
    mismo y no una aproximación.

    Es además el registro que el PM puede leer después del deploy para contestar «¿a
    quién le sacó qué este release?» sin depender de que alguien haya guardado el log
    del contenedor. Las filas las borra la reversa; si la migración no se revierte,
    quedan como historia.
    """

    grupo = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name="capacidades_revocadas",
        verbose_name="Rol",
    )
    codename = models.CharField(max_length=100, verbose_name="Capacidad (codename)")
    migracion = models.CharField(max_length=100, verbose_name="Migración que la quitó")
    creado = models.DateTimeField(auto_now_add=True, verbose_name="Creado")

    class Meta:
        verbose_name = "Capacidad revocada por una migración"
        verbose_name_plural = "Capacidades revocadas por migraciones"
        constraints = [
            models.UniqueConstraint(
                fields=["grupo", "codename", "migracion"],
                name="users_capacidadrevocada_unica",
            )
        ]

    def __str__(self):
        return f"{self.grupo_id}:{self.codename} ({self.migracion})"


class Capacidad(models.Model):
    """Modelo ancla de las capacidades del RBAC. **No** gestiona tabla propia.

    Su único objeto es aportar el ``content_type`` y la lista de ``permissions``
    (derivada del catálogo en :mod:`core.rbac`) que Django materializa como
    ``Permission`` reales durante ``migrate``. Esos permisos se tildan sobre los
    roles y se consultan vía ``core.rbac.puede``.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = todas_las_capacidades()
        verbose_name = "Capacidad"
        verbose_name_plural = "Capacidades"


class SolicitudCambioEmail(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="solicitudes_cambio_email",
        verbose_name="Usuario",
    )
    nuevo_email = models.EmailField(verbose_name="Nuevo email")
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
        verbose_name="Token de confirmación",
    )
    creado = models.DateTimeField(auto_now_add=True)
    confirmado = models.BooleanField(default=False)
    expirado = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Solicitud de cambio de email"
        verbose_name_plural = "Solicitudes de cambio de email"
        indexes = [
            models.Index(fields=["user", "confirmado"]),
            models.Index(fields=["creado"]),
        ]

    def __str__(self):
        return f"Cambio email {self.user.username} → {self.nuevo_email}"

    @property
    def esta_vigente(self):
        from datetime import timedelta

        return not self.confirmado and not self.expirado and (timezone.now() - self.creado) < timedelta(hours=24)
