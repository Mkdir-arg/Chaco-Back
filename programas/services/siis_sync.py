"""Sincronización del estado de los programas SIIS vinculados.

La corre ``manage.py sincronizar_programas_siis``. Contrasta el
``siis_programa_id`` de cada ``ProgramaSiis`` contra el catálogo **completo**
de SIIS: con ``estado=ACTIVO`` un programa dado de baja simplemente desaparece
de la respuesta y no se distingue de una lista incompleta.

Cuando un programa deja de estar vigente queda bloqueado para operar y el
bloqueo cascadea a todos sus segmentos (ver ``ProgramaSiis.pausa_efectiva``);
la baja se informa en pantalla.
"""

from django.utils import timezone

from programas.models import ProgramaSiis
from programas.services.siis import ESTADO_DESCONOCIDO, listar_programas_todos


def sincronizar_estado_programas(dry_run=False):
    """Actualiza el estado SIIS de cada programa vinculado.

    Devuelve las transiciones detectadas como ``[(programa, anterior, nuevo)]``.
    Idempotente: solo escribe los programas cuyo estado cambió.
    """
    catalogo = {programa["id"]: programa for programa in listar_programas_todos()}
    ahora = timezone.now()
    cambios = []

    for programa in ProgramaSiis.objects.iterator():
        remoto = catalogo.get(programa.siis_programa_id)
        nuevo = remoto["estado"] if remoto else ESTADO_DESCONOCIDO
        anterior = programa.siis_programa_estado or ""
        if nuevo != anterior:
            cambios.append((programa, anterior, nuevo))
        if dry_run:
            continue
        programa.siis_programa_estado = nuevo
        programa.siis_verificado_en = ahora
        programa.save(update_fields=["siis_programa_estado", "siis_verificado_en", "modificado"])

    return cambios
