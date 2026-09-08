from django.db import transaction
from django.utils import timezone

from programas.models import RegistroPausa


@transaction.atomic
def cambiar_pausa(objeto, usuario, pausar, motivo):
    """Cambia el estado y agrega un evento inmutable al historial."""
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValueError("El motivo es obligatorio.")

    objeto = objeto.__class__.objects.select_for_update().get(pk=objeto.pk)
    ahora = timezone.now()
    objeto.pausado = pausar
    objeto.pausa_motivo = motivo if pausar else ""
    objeto.pausado_por = usuario if pausar else None
    objeto.pausado_en = ahora if pausar else None
    objeto.save(update_fields=["pausado", "pausa_motivo", "pausado_por", "pausado_en", "modificado"])

    RegistroPausa.objects.create(
        tipo_entidad=objeto._meta.model_name,
        objeto_id=objeto.pk,
        objeto_nombre=str(objeto),
        accion=RegistroPausa.Accion.PAUSAR if pausar else RegistroPausa.Accion.REANUDAR,
        motivo=motivo,
        usuario=usuario,
    )
    return objeto
