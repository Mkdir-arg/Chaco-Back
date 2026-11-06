"""La marca de un caso dado de alta de oficio (``inscribir_de_oficio``).

Esas personas ya figuran en SIIS y la API de alta no deduplica, así que **ningún
camino** puede volver a informarlas: ni el botón, ni los procesos masivos, ni
``enviar_casos_siis``. La marca es una traza ``alta_de_oficio`` escrita al
**crear** el caso (también el que queda ENVIADO sin validar), no al aprobarlo.

Módulo aparte y sin dependencias de servicios para que ``siis_envio``,
``proceso_masivo`` y ``cupo`` lo importen sin ciclos.
"""

from django.db.models import Exists, OuterRef

from programas.models import TracaFormulario

CAMPO_TRAZA = "alta_de_oficio"
CODIGO_ERROR = "ALTA_DE_OFICIO"
DETALLE_MARCA = "Alta de oficio sin validación ni alta en SIIS (beneficiaria vigente, ya figura en SIIS)"


def es_alta_de_oficio(formulario_pk):
    """Consulta puntual por el índice de ``formulario_id``."""
    return TracaFormulario.objects.filter(formulario_id=formulario_pk, campo=CAMPO_TRAZA).exists()


def marcada():
    """``Exists`` correlacionado por ``formulario_id`` (indexado). Se usa negado
    (``~marcada()``) en los querysets de candidatos: nunca un ``IN`` con ids."""
    return Exists(TracaFormulario.objects.filter(formulario_id=OuterRef("pk"), campo=CAMPO_TRAZA))


def marcar(formulario, usuario):
    """Escribe la marca si el caso no la tiene. Idempotente."""
    if es_alta_de_oficio(formulario.pk):
        return False
    from programas.services.becas import registrar_traza

    registrar_traza(formulario, usuario, [(CAMPO_TRAZA, "", DETALLE_MARCA)])
    return True
