"""Formularios de un tipo de dispositivo, uno por momento (P17).

Cada formulario es un ``DisenoFormulario`` cuyo dueño es el tipo, con el mismo
motor que el constructor de Becas (``programas.services.diseno`` y
``programas.services.constructor``): grupos, textos, campos propios, condiciones y
una ``version`` que sube con cada guardado. Nace vacío —no hereda catálogo— y un
tipo tiene a lo sumo uno por momento (``uniq_diseno_tipo_momento``).
"""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from programas.models import DisenoFormulario, MomentoFormulario

#: Dónde se completa cada formulario, como lo nombra la columna «Se completa en».
SE_COMPLETA_EN = {
    MomentoFormulario.CREAR_DISPOSITIVO: "Alta de la institución",
    MomentoFormulario.INGRESO: "Ingreso",
    MomentoFormulario.ASIGNACION_PLAZA: "Asignar o cambiar plaza",
    MomentoFormulario.NOVEDADES_TURNO: "Bitácora y cierre de turno",
    MomentoFormulario.EGRESO: "Egresar",
    MomentoFormulario.TRASLADO: "Trasladar",
    MomentoFormulario.PROPIO: "Sin asignar",
}


def momentos_libres(ocupados):
    """``[(valor, etiqueta)]`` de los momentos que el tipo todavía no usa, en el
    orden de ``MomentoFormulario``. ``ocupados`` son los momentos ya tomados."""
    ocupados = set(ocupados)
    return [(valor, etiqueta) for valor, etiqueta in MomentoFormulario.choices if valor not in ocupados]


def _ya_existe(momento):
    return ValidationError(
        f"Este tipo ya tiene el formulario «{MomentoFormulario(momento).label}».",
        code="momento_ocupado",
    )


def crear_formulario(tipo, momento, usuario=None):
    """El formulario del ``momento`` para ``tipo``, vacío y en la versión 1.

    Un momento desconocido o ya tomado es un ``ValidationError``; dos altas a la
    vez del mismo momento las frena la restricción única de la base y la segunda
    recibe el mismo error.
    """
    if momento not in MomentoFormulario.values:
        raise ValidationError("Elegí un momento válido.", code="momento_invalido")
    if DisenoFormulario.objects.filter(tipo_dispositivo=tipo, momento=momento).exists():
        raise _ya_existe(momento)
    try:
        with transaction.atomic():
            return DisenoFormulario.objects.create(tipo_dispositivo=tipo, momento=momento, actualizado_por=usuario)
    except IntegrityError as exc:
        raise _ya_existe(momento) from exc


def puede_eliminar_formulario(diseno):
    """Punto único para decidir si un formulario del tipo se puede eliminar.

    Hoy nadie lo responde todavía, así que siempre se puede. Cuando haya
    respuestas guardadas con la foto de una versión, acá se endurece: con
    respuestas, el formulario se da de baja y no se borra.
    """
    return diseno.tipo_dispositivo_id is not None


def eliminar_formulario(diseno):
    """Borra el formulario y sus ítems; el momento queda libre para volver a crearlo."""
    if not puede_eliminar_formulario(diseno):
        raise ValidationError("Este formulario no se puede eliminar.", code="no_eliminable")
    diseno.delete()
