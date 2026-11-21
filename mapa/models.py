"""Puntos sueltos del mapa general (`/mapa/`, Cambio 493, fase 3).

Lo que no tiene ficha propia en el sistema y hace falta ubicar: una sede, un equipo, un vehículo.
Los dispositivos, los edificios y los casos de Emergencia no se cargan acá: el mapa los lee de sus
propios modelos, así la ubicación se edita en un solo lugar.
"""

from django.contrib.auth.models import User
from django.db import models

from core.coordenadas import VALIDADORES_LATITUD, VALIDADORES_LONGITUD
from core.models import TimeStamped


class Punto(TimeStamped):
    class Categoria(models.TextChoices):
        SEDE = "SEDE", "Sede"
        EQUIPO = "EQUIPO", "Equipo"
        VEHICULO = "VEHICULO", "Vehículo"
        OTRO = "OTRO", "Otro"

    nombre = models.CharField(max_length=120, verbose_name="Nombre")
    categoria = models.CharField(
        max_length=10, choices=Categoria.choices, default=Categoria.OTRO, verbose_name="Categoría"
    )
    descripcion = models.CharField(max_length=500, blank=True, verbose_name="Descripción")
    latitud = models.DecimalField(
        max_digits=9, decimal_places=6, validators=VALIDADORES_LATITUD, verbose_name="Latitud"
    )
    longitud = models.DecimalField(
        max_digits=9, decimal_places=6, validators=VALIDADORES_LONGITUD, verbose_name="Longitud"
    )
    cargado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="puntos_del_mapa",
        verbose_name="Cargado por",
    )

    class Meta:
        verbose_name = "Punto del mapa"
        verbose_name_plural = "Puntos del mapa"
        ordering = ["nombre", "pk"]

    def __str__(self):
        return f"{self.nombre} ({self.get_categoria_display()})"
