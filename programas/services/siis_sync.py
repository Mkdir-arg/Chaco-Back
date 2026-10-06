"""Sincronización del estado de los programas SIIS vinculados.

La corre ``manage.py sincronizar_programas_siis``. Contrasta el
``siis_programa_id`` de cada ``ProgramaSiis`` contra el catálogo **completo**
de SIIS: con ``estado=ACTIVO`` un programa dado de baja simplemente desaparece
de la respuesta y no se distingue de una lista incompleta.

Cuando un programa deja de estar vigente queda bloqueado para operar y el
bloqueo cascadea a todos sus segmentos (ver ``ProgramaSiis.pausa_efectiva``);
la baja se informa en pantalla.

Esa ambigüedad —baja y error del servicio se ven igual— es lo que obliga a la
guarda de SIIS-06: el catálogo vacío no se escribe nunca, y una ausencia que
alcanza a todos los programas vinculados o a más de la mitad necesita que
alguien la confirme con ``forzar``. Corre a las 04:00 sin nadie mirando, así que
el default tiene que ser no tocar nada: un programa que sigue ACTIVO cuando en
SIIS se dio de baja se arregla al día siguiente; todos los programas bloqueados
de golpe deja Becas parada hasta que alguien se da cuenta.
"""

from django.utils import timezone

from programas.models import ProgramaSiis
from programas.services.siis import ESTADO_DESCONOCIDO, SiisCatalogError, listar_programas_todos

#: Proporción de ausencias a partir de la cual la sincronización pide confirmación
#: (default de D-S06: «todos o más del 50 %»). Solo se aplica con dos o más
#: programas vinculados: con uno solo, cualquier baja real es el 100 % y la
#: guarda dejaría de poder detectarla nunca.
UMBRAL_AUSENCIAS = 0.5
MINIMO_PARA_LA_GUARDA = 2


def sincronizar_estado_programas(dry_run=False, forzar=False):
    """Actualiza el estado SIIS de cada programa vinculado.

    Devuelve las transiciones detectadas como ``[(programa, anterior, nuevo)]``.
    Idempotente: solo escribe los programas cuyo estado cambió.

    Lanza :class:`SiisCatalogError` —sin escribir nada— si el catálogo vino
    vacío o si la ausencia es masiva y no se pasó ``forzar``.
    """
    catalogo = {programa["id"]: programa for programa in listar_programas_todos()}
    if not catalogo:
        raise SiisCatalogError("SIIS devolvió un catálogo vacío: no se sincroniza.")

    ahora = timezone.now()
    cambios = []
    # Se recorre entero y recién después se escribe: la guarda necesita el total,
    # y lo que decide es «cuántos quedarían bloqueados», no «cuántos vi hasta acá».
    veredictos = []
    for programa in ProgramaSiis.objects.iterator():
        remoto = catalogo.get(programa.siis_programa_id)
        nuevo = remoto["estado"] if remoto else ESTADO_DESCONOCIDO
        anterior = programa.siis_programa_estado or ""
        veredictos.append((programa, nuevo))
        if nuevo != anterior:
            cambios.append((programa, anterior, nuevo))

    nuevos_desconocidos = sum(1 for _, _, nuevo in cambios if nuevo == ESTADO_DESCONOCIDO)
    _exigir_confirmacion(nuevos_desconocidos, len(veredictos), forzar)

    if not dry_run:
        for programa, nuevo in veredictos:
            programa.siis_programa_estado = nuevo
            programa.siis_verificado_en = ahora
            programa.save(update_fields=["siis_programa_estado", "siis_verificado_en", "modificado"])

    return cambios


def _exigir_confirmacion(nuevos_desconocidos, vinculados, forzar):
    """La ausencia masiva se parece más a un error de SIIS que a una baja real."""
    if forzar or vinculados < MINIMO_PARA_LA_GUARDA or not nuevos_desconocidos:
        return
    if nuevos_desconocidos < vinculados and nuevos_desconocidos / vinculados <= UMBRAL_AUSENCIAS:
        return
    raise SiisCatalogError(
        f"SIIS no informó {nuevos_desconocidos} de {vinculados} programas vinculados: "
        "quedarían todos bloqueados. No se sincroniza. Si la baja es real, "
        "volvé a correrlo con --forzar."
    )
