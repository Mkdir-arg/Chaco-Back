import uuid

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import models
from django.utils import timezone

from core.rbac import (
    CATEGORIA_BACKOFFICE,
    CATEGORIAS_ROL_CHOICES,
    todas_las_capacidades,
)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    dark_mode = models.BooleanField(default=True)

    def __str__(self):
        return f"Perfil de {self.user.username}"


class RolMeta(models.Model):
    """Metadatos de un Rol del backoffice. Un Rol = ``Group`` + ``RolMeta``.

    Aporta la descripción autoexplicada, la categoría, la marca de protegido
    (no editable/eliminable desde la UI) y el estado activo (un rol inactivo no
    es asignable). Las capacidades se tildan sobre el ``Group`` vía
    ``group.permissions``.
    """

    grupo = models.OneToOneField(
        Group, on_delete=models.CASCADE, related_name="meta", verbose_name="Rol"
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

    def __str__(self):
        return self.grupo.name


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
        related_name='solicitudes_cambio_email',
        verbose_name='Usuario',
    )
    nuevo_email = models.EmailField(verbose_name='Nuevo email')
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        db_index=True,
        editable=False,
        verbose_name='Token de confirmación',
    )
    creado = models.DateTimeField(auto_now_add=True)
    confirmado = models.BooleanField(default=False)
    expirado = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Solicitud de cambio de email'
        verbose_name_plural = 'Solicitudes de cambio de email'
        indexes = [
            models.Index(fields=['user', 'confirmado']),
            models.Index(fields=['creado']),
        ]

    def __str__(self):
        return f"Cambio email {self.user.username} → {self.nuevo_email}"

    @property
    def esta_vigente(self):
        from datetime import timedelta
        return (
            not self.confirmado
            and not self.expirado
            and (timezone.now() - self.creado) < timedelta(hours=24)
        )
