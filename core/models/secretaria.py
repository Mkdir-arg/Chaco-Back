from django.db import models

from .base import TimeStamped


class Secretaria(TimeStamped):
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        verbose_name = "Secretaría"
        verbose_name_plural = "Secretarías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def puede_eliminarse(self):
        return not self.subsecretarias.exists()


class Subsecretaria(TimeStamped):
    secretaria = models.ForeignKey(
        Secretaria,
        on_delete=models.PROTECT,
        related_name="subsecretarias",
        verbose_name="Secretaría",
    )
    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activa")

    class Meta:
        verbose_name = "Subsecretaría"
        verbose_name_plural = "Subsecretarías"
        ordering = ["secretaria__nombre", "nombre"]
        unique_together = [("nombre", "secretaria")]

    def __str__(self):
        return f"{self.secretaria.nombre} › {self.nombre}"

    def puede_eliminarse(self):
        return not self.programa_set.filter(subsecretaria=self).exists()
