from django.db import models

from .base import Localidad, TimeStamped


class UbicacionLocalidad(TimeStamped):
    """Centroide oficial de una localidad del catálogo, para ubicarla en un mapa.

    Vive aparte de ``Localidad`` para no alterar una tabla compartida de todo el país:
    solo tienen fila las localidades que concilian con el dataset de la fuente (hoy
    BAHRA/Georef, ver ``core/data/localidades_chaco_georef.csv``). Una localidad sin
    fila no tiene posición conocida y no se dibuja. La carga la hace
    ``manage.py cargar_ubicaciones_localidades``.
    """

    FUENTE_BAHRA_GEOREF = "BAHRA/Georef"

    localidad = models.OneToOneField(
        Localidad,
        on_delete=models.CASCADE,
        related_name="ubicacion",
        verbose_name="Localidad",
    )
    latitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Latitud")
    longitud = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Longitud")
    departamento = models.CharField(max_length=255, blank=True, verbose_name="Departamento")
    fuente = models.CharField(max_length=50, verbose_name="Fuente")
    id_fuente = models.CharField(max_length=32, verbose_name="Id en la fuente")

    class Meta:
        verbose_name = "Ubicación de localidad"
        verbose_name_plural = "Ubicaciones de localidades"

    def __str__(self):
        return f"{self.localidad} ({self.latitud}, {self.longitud})"
