from django.db.models.signals import post_save
from django.dispatch import receiver

from django.utils import timezone

from ..models.nachec import CasoNachec
from programas.models import DerivacionPrograma


@receiver(post_save, sender=DerivacionPrograma)
def crear_caso_nachec_desde_derivacion(sender, instance, created, **kwargs):
    """
    Cuando se crea una DerivacionPrograma hacia Ñachec,
    crear automáticamente un CasoNachec en estado DERIVADO.
    """
    if not created:
        if instance.estado == "ACEPTADA" and instance.programa_destino.tipo in ["NACHEC", "ÑACHEC"]:
            caso = CasoNachec.objects.filter(ciudadano_titular=instance.ciudadano).first()
            if caso and caso.estado == "DERIVADO":
                caso.estado = "EN_REVISION"
                caso.operador_admision = instance.respondido_por
                caso.save()
        elif instance.estado == "RECHAZADA" and instance.programa_destino.tipo in ["NACHEC", "ÑACHEC"]:
            caso = CasoNachec.objects.filter(
                ciudadano_titular=instance.ciudadano,
                estado="DERIVADO",
            ).first()
            if caso:
                caso.estado = "RECHAZADO"
                caso.observaciones = (
                    (caso.observaciones or "")
                    + f"\n\nDerivación rechazada: {instance.respuesta}"
                )
                caso.save()
        return

    if instance.programa_destino.tipo not in ["NACHEC", "ÑACHEC"]:
        return

    if CasoNachec.objects.filter(ciudadano_titular=instance.ciudadano).exclude(
        estado__in=["CERRADO", "RECHAZADO", "SUSPENDIDO"]
    ).exists():
        return

    CasoNachec.objects.create(
        ciudadano_titular=instance.ciudadano,
        estado="DERIVADO",
        prioridad="MEDIA",
        municipio=instance.ciudadano.domicilio or "Sin especificar",
        localidad="Sin especificar",
        direccion=instance.ciudadano.domicilio or "Sin especificar",
        fecha_derivacion=timezone.now().date(),
        motivo_derivacion=(
            instance.motivo
            or f"Derivado desde {instance.programa_origen.nombre if instance.programa_origen else 'Sistema'}"
        ),
        observaciones=(
            f"Derivado desde {instance.programa_origen.nombre if instance.programa_origen else 'Sistema'}"
        ),
    )
