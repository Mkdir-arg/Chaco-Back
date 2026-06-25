from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from conversaciones.models import Mensaje

from ..models import LegajoAtencion
from ..services import AlertasService


@receiver(post_save, sender=Mensaje)
def alerta_mensaje_ciudadano(sender, instance, created, **kwargs):
    """Genera alerta cuando un ciudadano envía mensaje."""
    if created and instance.remitente == "ciudadano":
        AlertasService.generar_alerta_mensaje_ciudadano(instance.conversacion)


@receiver(post_save, sender=LegajoAtencion)
def verificar_alertas_legajo(sender, instance, created, **kwargs):
    """Genera alertas automáticas al crear o modificar legajo."""
    if instance.ciudadano_id:
        AlertasService.generar_alertas_ciudadano(instance.ciudadano_id)


@receiver(pre_save, sender=LegajoAtencion)
def detectar_cambio_riesgo(sender, instance, **kwargs):
    """Detecta cambios en el nivel de riesgo."""
    if not instance.pk:
        return
    nivel_anterior = (
        LegajoAtencion.objects.filter(pk=instance.pk)
        .values_list("nivel_riesgo", flat=True)
        .first()
    )
    if nivel_anterior is None:
        return
    if nivel_anterior != instance.nivel_riesgo and instance.nivel_riesgo == "ALTO":
        AlertasService.generar_alerta_evento_critico(
            instance,
            "CAMBIO_RIESGO",
            f"Nivel de riesgo cambiado de {nivel_anterior} a {instance.nivel_riesgo}",
        )
