from uuid import uuid4

from django.conf import settings
from django.db import models


def generate_codigo():
    """Genera un código único para legajos"""
    return str(uuid4())


class Provincia(models.Model):
    """
    Guardado de las provincias de los vecinos y vecinas registrados.
    """

    nombre = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return str(self.nombre)

    class Meta:
        ordering = ["id"]
        verbose_name = "Provincia"
        verbose_name_plural = "Provincia"


class Mes(models.Model):
    nombre = models.CharField(max_length=255)

    def __str__(self):
        return str(self.nombre)

    class Meta:
        ordering = ["id"]
        verbose_name = "Mes"
        verbose_name_plural = "Meses"


class Dia(models.Model):
    nombre = models.CharField(max_length=255)

    def __str__(self):
        return str(self.nombre)

    class Meta:
        ordering = ["id"]
        verbose_name = "Dia"
        verbose_name_plural = "Dias"


class Municipio(models.Model):
    """
    Guardado de los municipios de los vecinos y vecinas registrados.
    """

    nombre = models.CharField(max_length=255)
    provincia = models.ForeignKey(Provincia, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return str(self.nombre)

    class Meta:
        ordering = ["id"]
        verbose_name = "Municipio"
        verbose_name_plural = "Municipio"
        unique_together = (
            "nombre",
            "provincia",
        )


class Localidad(models.Model):
    """
    Guardado de las localidades de los vecinos y vecinas registrados.
    """

    nombre = models.CharField(max_length=255)
    municipio = models.ForeignKey(Municipio, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return str(self.nombre)

    class Meta:
        verbose_name = "Localidad"
        verbose_name_plural = "Localidad"
        unique_together = (
            "nombre",
            "municipio",
        )


class Sexo(models.Model):
    sexo = models.CharField(max_length=10)

    def __str__(self):
        return str(self.sexo)

    class Meta:
        verbose_name = "Sexo"
        verbose_name_plural = "Sexos"


class TimeStamped(models.Model):
    """Modelo abstracto para timestamps automáticos"""

    creado = models.DateTimeField(auto_now_add=True)
    modificado = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LegajoBase(TimeStamped):
    """Modelo base abstracto para todos los tipos de legajos"""

    class Estado(models.TextChoices):
        ABIERTO = "ABIERTO", "Abierto"
        EN_SEGUIMIENTO = "EN_SEGUIMIENTO", "En seguimiento"
        DERIVADO = "DERIVADO", "Derivado"
        CERRADO = "CERRADO", "Cerrado"

    class Confidencialidad(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        RESTRINGIDA = "RESTRINGIDA", "Restringida"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    codigo = models.CharField(max_length=36, unique=True, default=generate_codigo)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTO)
    fecha_apertura = models.DateField(auto_now_add=True)
    fecha_cierre = models.DateField(null=True, blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="legajos_responsable"
    )
    confidencialidad = models.CharField(
        max_length=20, choices=Confidencialidad.choices, default=Confidencialidad.NORMAL
    )
    notas = models.TextField(blank=True)

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["fecha_apertura"]),
            models.Index(fields=["responsable"]),
        ]
