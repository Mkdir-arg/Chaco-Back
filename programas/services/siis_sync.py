"""Sincronización del estado de los programas SIIS vinculados a segmentos.

La corre ``manage.py sincronizar_programas_siis``. Contrasta el
``siis_programa_id`` de cada segmento contra el catálogo **completo** de SIIS:
con ``estado=ACTIVO`` un programa dado de baja simplemente desaparece de la
respuesta y no se distingue de una lista incompleta.

Cuando un programa deja de estar vigente, el segmento queda bloqueado para
operar (ver ``Segmento.pausa_efectiva``) y la baja se informa en pantalla.
"""

from django.utils import timezone

from programas.models import Segmento
from programas.services.siis import ESTADO_DESCONOCIDO, listar_programas_todos


def sincronizar_estado_programas(dry_run=False):
    """Actualiza el estado SIIS de cada segmento vinculado.

    Devuelve las transiciones detectadas como ``[(segmento, anterior, nuevo)]``.
    Idempotente: solo escribe los segmentos cuyo estado cambió.
    """
    catalogo = {programa["id"]: programa for programa in listar_programas_todos()}
    ahora = timezone.now()
    cambios = []

    for segmento in Segmento.objects.exclude(siis_programa_id__isnull=True).iterator():
        programa = catalogo.get(segmento.siis_programa_id)
        nuevo = programa["estado"] if programa else ESTADO_DESCONOCIDO
        anterior = segmento.siis_programa_estado or ""
        if nuevo != anterior:
            cambios.append((segmento, anterior, nuevo))
        if dry_run:
            continue
        segmento.siis_programa_estado = nuevo
        segmento.siis_verificado_en = ahora
        segmento.save(update_fields=["siis_programa_estado", "siis_verificado_en", "modificado"])

    return cambios
