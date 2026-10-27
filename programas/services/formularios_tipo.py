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
from django.db.models import ProtectedError
from django.utils import timezone

from programas.models import DisenoFormulario, MomentoFormulario, TipoDispositivo
from programas.services.respuestas_dispositivo import formulario_vigente, tiene_respuestas

#: Dónde se completa cada formulario, como lo nombra la columna «Se completa en».
SE_COMPLETA_EN = {
    MomentoFormulario.CREAR_DISPOSITIVO: "Alta de la institución",
    MomentoFormulario.INGRESO: "Ingreso",
    MomentoFormulario.ASIGNACION_PLAZA: "Asignar o cambiar plaza",
    MomentoFormulario.NOVEDADES_TURNO: "Bitácora y cierre de turno",
    MomentoFormulario.EGRESO: "Egresar",
    MomentoFormulario.TRASLADO: "Trasladar",
    MomentoFormulario.RELEVAMIENTO: "Relevamiento edilicio (app de campo)",
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


#: Lo que hizo :func:`eliminar_formulario`.
BORRADO = "borrado"
DADO_DE_BAJA = "baja"


def puede_eliminar_formulario(diseno, respondido=None):
    """Punto único para decidir si un formulario del tipo se puede **borrar**.

    Con respuestas guardadas no: cada una lleva la foto de su versión y su fila apunta
    al diseño, así que el formulario se da de baja (:func:`eliminar_formulario`).
    ``respondido`` acepta el dato ya anotado (``anotar_tiene_respuestas``) para no
    consultar de nuevo.
    """
    if diseno.tipo_dispositivo_id is None:
        return False
    if respondido is None:
        respondido = tiene_respuestas(diseno)
    return not respondido


@transaction.atomic
def eliminar_formulario(diseno):
    """«Eliminar» de la tabla del tipo: borra el formulario sin respuestas y da de baja
    el que ya tiene. Dado de baja deja de pedirse en el alta de la institución, se sigue
    leyendo en el detalle y se puede reactivar. Devuelve :data:`BORRADO` o
    :data:`DADO_DE_BAJA`."""
    if diseno.tipo_dispositivo_id is None:
        raise ValidationError("Este formulario no se puede eliminar.", code="no_eliminable")
    diseno = DisenoFormulario.objects.select_for_update().get(pk=diseno.pk)
    if puede_eliminar_formulario(diseno):
        try:
            with transaction.atomic():
                diseno.delete()
            return BORRADO
        except ProtectedError:
            pass  # alguien respondió entre la lectura y el borrado: se da de baja igual
    if diseno.dado_de_baja_en is None:
        diseno.dado_de_baja_en = timezone.now()
        diseno.save(update_fields=["dado_de_baja_en", "modificado"])
    return DADO_DE_BAJA


def reactivar_formulario(diseno):
    """Vuelve a pedir un formulario dado de baja, con sus ítems y su versión."""
    if diseno.dado_de_baja_en is None:
        return
    diseno.dado_de_baja_en = None
    diseno.save(update_fields=["dado_de_baja_en", "modificado"])


# ── Qué formulario «Relevamiento» corresponde a un edificio (D1/D3) ─────────


def tipos_del_edificio(edificio):
    """Los tipos de las instituciones que ocupan el edificio, sin repetir y por nombre."""

    return list(TipoDispositivo.objects.filter(dispositivos__edificios=edificio).distinct().order_by("nombre", "pk"))


def formulario_de_tipo(tipo):
    """El formulario «Relevamiento» vigente del tipo, o ``None`` (sin formulario o dado de baja)."""

    return formulario_vigente(tipo.pk, MomentoFormulario.RELEVAMIENTO) if tipo is not None else None


def formularios_de_los_tipos(edificio):
    """``[(tipo, formulario | None)]`` de los tipos del edificio: lo que el modal de asignar
    muestra para elegir el formulario (D1) y para avisar cuando un tipo no tiene (D3)."""

    return [(tipo, formulario_de_tipo(tipo)) for tipo in tipos_del_edificio(edificio)]


def aviso_de_tipos(tipos_formularios):
    """El aviso del modal cuando el edificio aloja a **un solo** tipo y ese tipo no tiene formulario
    (con varios tipos, el selector ya marca «sin formulario»). ``tipos_formularios`` es
    :func:`formularios_de_los_tipos`."""

    if len(tipos_formularios) == 1 and tipos_formularios[0][1] is None:
        return aviso_sin_formulario(tipos_formularios[0][0])
    return ""


def aviso_sin_formulario(tipo):
    """El texto del modal cuando el tipo no tiene formulario «Relevamiento» (D3), o ``""``."""

    if tipo is None or formulario_de_tipo(tipo) is not None:
        return ""
    return (
        f"El tipo «{tipo.nombre}» no tiene un formulario «Relevamiento»: el territorial va a cargar solo la "
        "criticidad, las observaciones y las fotos."
    )


def diseno_para_asignar(edificio, tipo):
    """D1 y D3: el formulario que se fija al asignar.

    Con ``tipo`` explícito tiene que ser de alguna institución del edificio. Sin él, vale el
    único tipo del edificio; con varios hay que elegir. Un tipo sin formulario «Relevamiento»
    (o dado de baja) no impide asignar: el diseño queda en ``None`` y el territorial carga solo
    el resultado fijo.
    """

    tipos = tipos_del_edificio(edificio)
    if tipo is None:
        if len(tipos) > 1:
            raise ValidationError({"tipo": "El edificio aloja instituciones de distintos tipos: elegí el formulario."})
        tipo = tipos[0] if tipos else None
    elif tipo.pk not in {candidato.pk for candidato in tipos}:
        raise ValidationError({"tipo": "Ese tipo no corresponde a ninguna institución del edificio."})
    return formulario_de_tipo(tipo)
