from django.db import models


class Dashboard(models.Model):
    """
    Modelo para almacenar información de dashboard.
    """

    llave = models.CharField(
        max_length=255,
        unique=True,
        primary_key=True,
        help_text="Llave única para identificar el registro en el dashboard.",
    )
    cantidad = models.BigIntegerField(
        default=0, help_text="Cantidad asociada al registro en el dashboard."
    )

    def aumentar_cantidad(self, cantidad: int = 1):
        self.cantidad += cantidad
        self.save()
