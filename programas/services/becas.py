"""Helpers de dominio del Programa Becas (épica #69 / análisis #70).

Funciones puras sobre los modelos de Becas. La autorización combinada con el
RBAC (admin vs coordinador con alcance) vive en ``programas.services.autorizacion``.
"""

from datetime import date

from django.db import models, transaction

from legajos.models import Ciudadano
from programas.models import (
    AsignacionCoordinador,
    PreguntaGlobal,
    RequisitoNativo,
    Segmento,
)


def get_campos_formulario(convocatoria):
    """Devuelve ``(globales, requisitos)`` para renderizar el formulario.

    - ``globales``: ``PreguntaGlobal`` activas, ordenadas (RN-31).
    - ``requisitos``: ``RequisitoNativo`` del segmento (subsegmento=None) y, si la
      convocatoria tiene subsegmento, también los del subsegmento (herencia; RN-32).
    """
    globales = PreguntaGlobal.objects.filter(activo=True).order_by("orden", "id")
    if convocatoria.subsegmento_id:
        requisitos = RequisitoNativo.objects.filter(
            models.Q(segmento_id=convocatoria.segmento_id, subsegmento__isnull=True)
            | models.Q(subsegmento_id=convocatoria.subsegmento_id)
        ).order_by("orden", "id")
    else:
        requisitos = RequisitoNativo.objects.filter(
            segmento_id=convocatoria.segmento_id, subsegmento__isnull=True
        ).order_by("orden", "id")
    return globales, requisitos


def _campo_dict(obj):
    return {
        "id": obj.pk,
        "texto": obj.texto,
        "tipo": obj.tipo,
        "opciones": obj.opciones or [],
        "obligatorio": obj.obligatorio,
        "orden": obj.orden,
    }


def definicion_formulario(relevamiento):
    """Definición del formulario para la app de campo (#82).

    Devuelve preguntas globales y requisitos (con herencia de subsegmento) según
    la convocatoria del relevamiento, más el flag ``requiere_gps`` del segmento.
    """
    convocatoria = relevamiento.convocatoria
    globales, requisitos = get_campos_formulario(convocatoria)
    return {
        "requiere_gps": convocatoria.segmento.requiere_gps,
        "globales": [_campo_dict(p) for p in globales],
        "requisitos": [_campo_dict(r) for r in requisitos],
    }


def get_segmentos_coordinador(user):
    """Segmentos sobre los que ``user`` tiene una asignación de coordinador activa."""
    if user is None or not getattr(user, "is_authenticated", False):
        return Segmento.objects.none()
    return Segmento.objects.filter(
        asignaciones_coordinador__coordinador=user,
        asignaciones_coordinador__activo=True,
    ).distinct()


def coordinador_gestiona_segmento(user, segmento):
    """¿``user`` tiene asignación de coordinador activa sobre ``segmento``?

    Chequeo puro sobre ``AsignacionCoordinador`` (sin considerar el rol Admin).
    La verificación completa de acceso está en
    :func:`programas.services.autorizacion.puede_gestionar_segmento`.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return AsignacionCoordinador.objects.filter(coordinador=user, segmento=segmento, activo=True).exists()


def es_menor(fecha_nacimiento, referencia=None):
    """True si ``fecha_nacimiento`` corresponde a un menor de 18 años (RN-22).

    Devuelve None si no hay fecha (no se puede determinar).
    """
    if not fecha_nacimiento:
        return None
    hoy = referencia or date.today()
    edad = hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))
    return edad < 18


def registrar_traza(formulario, usuario, cambios):
    """Registra en ``TracaFormulario`` una lista de cambios de campos (RN-14/29).

    ``cambios``: iterable de ``(campo, valor_anterior, valor_nuevo)``. Crea una
    fila inmutable por cambio. Devuelve la cantidad registrada.
    """
    from programas.models import TracaFormulario

    objs = [
        TracaFormulario(
            formulario=formulario,
            editado_por=usuario,
            campo=campo,
            valor_anterior="" if va in (None, "") else str(va),
            valor_nuevo="" if vn in (None, "") else str(vn),
        )
        for (campo, va, vn) in cambios
    ]
    if objs:
        TracaFormulario.objects.bulk_create(objs)
    return len(objs)


@transaction.atomic
def resolver_ciudadano_offline(formulario):
    """Resuelve el ciudadano de un formulario que llegó por sync offline.

    Si ``ciudadano`` es None y hay ``datos_identificacion``, hace
    ``get_or_create`` por DNI (linkea si existe, crea con datos mínimos si no) y
    limpia ``datos_identificacion``. Idempotente: si ya hay ciudadano, no hace nada.
    """
    if formulario.ciudadano_id or not formulario.datos_identificacion:
        return formulario.ciudadano

    datos = formulario.datos_identificacion
    dni = datos.get("dni")
    if not dni:
        return None

    ciudadano, _creado = Ciudadano.objects.get_or_create(
        dni=dni,
        defaults={
            "nombre": datos.get("nombre", ""),
            "apellido": datos.get("apellido", ""),
            "fecha_nacimiento": datos.get("fecha_nacimiento") or None,
        },
    )
    formulario.ciudadano = ciudadano
    formulario.datos_identificacion = None
    formulario.save(update_fields=["ciudadano", "datos_identificacion", "modificado"])
    return ciudadano
