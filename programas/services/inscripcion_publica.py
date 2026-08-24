"""Ingesta del formulario público de Becas (#295, análisis #289).

El envío del paso 2 del link crea exactamente lo mismo que un sync de la app
de campo: un ``Formulario`` ENVIADO dentro del relevamiento **y el legajo
ciudadano en el acto** (RN-P8, vía ``resolver_ciudadano_offline``). Para el
backoffice el resultado es indistinguible: entra a la bandeja de revisión sin
ningún cambio en ella.

Garantías dentro de la transacción (mismo patrón que la API de campo):
- cupo bajo ``select_for_update`` (dos envíos al último lugar → entra uno);
- idempotencia por ``client_uuid`` (doble submit devuelve el mismo formulario);
- re-chequeo del duplicado por convocatoria (RN-P5) — entre el paso 1 y el
  envío pudo inscribirse otro con el mismo DNI.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from programas.models import AdjuntoFormulario, Formulario, Relevamiento
from programas.services.becas import resolver_ciudadano_offline


class InscripcionNoDisponible(Exception):
    """El relevamiento dejó de aceptar envíos (vencido, pausado, cupo, cerrado)."""


class InscripcionDuplicada(Exception):
    """El DNI ya está inscripto en la convocatoria (RN-P5)."""


def _dni_en_convocatoria(convocatoria, dni):
    return (
        Formulario.objects.filter(relevamiento__convocatoria=convocatoria)
        .filter(Q(ciudadano__dni=dni) | Q(datos_identificacion__dni=dni))
        .exists()
    )


def crear_formulario_publico(relevamiento, *, identificacion, form, client_uuid):
    """Crea el formulario de una inscripción pública validada.

    ``identificacion`` es el dict del paso 1 (dni, sexo, datos básicos, origen)
    y ``form`` un ``InscripcionPaso2Form`` válido. Devuelve ``(formulario,
    creado)``: con ``creado=False`` el ``client_uuid`` ya había ingresado
    (doble submit) y se devuelve el formulario original.
    """
    dni = identificacion["dni"]
    datos_basicos = identificacion.get("datos") or {}
    es_validado = identificacion.get("origen") == "personas"
    cleaned = form.cleaned_data

    with transaction.atomic():
        rel = Relevamiento.objects.select_for_update().get(pk=relevamiento.pk)
        if client_uuid:
            existente = rel.formularios.filter(client_uuid=client_uuid).first()
            if existente:
                return existente, False
        if rel.estado != Relevamiento.Estado.EN_CURSO or not rel.habilitado_en(timezone.now()):
            raise InscripcionNoDisponible()
        if rel.formularios.count() >= rel.cupo_maximo:
            raise InscripcionNoDisponible()
        if _dni_en_convocatoria(rel.convocatoria, dni):
            raise InscripcionDuplicada()

        if es_validado:
            nombre = datos_basicos.get("nombre", "")
            apellido = datos_basicos.get("apellido", "")
            fecha_nacimiento = datos_basicos.get("fecha_nacimiento", "")
        else:
            nombre = cleaned.get("nombre", "")
            apellido = cleaned.get("apellido", "")
            fecha = cleaned.get("fecha_nacimiento")
            fecha_nacimiento = fecha.isoformat() if fecha else ""

        formulario = Formulario.objects.create(
            relevamiento=rel,
            celular=cleaned["celular"],
            email_contacto=cleaned["email_contacto"],
            apoderado_nombre=cleaned.get("apoderado_nombre", ""),
            apoderado_apellido=cleaned.get("apoderado_apellido", ""),
            apoderado_dni=cleaned.get("apoderado_dni", ""),
            apoderado_genero=cleaned.get("apoderado_genero", ""),
            apoderado_fecha_nacimiento=cleaned.get("apoderado_fecha_nacimiento"),
            gps_lat=cleaned.get("gps_lat"),
            gps_lng=cleaned.get("gps_lng"),
            data=form.respuestas(),
            # Mismo contrato que el sync offline de la app: el origen
            # "personas" acredita identidad (validado_renaper); "manual" no.
            datos_identificacion={
                "dni": dni,
                "sexo": identificacion.get("sexo", ""),
                "nombre": nombre,
                "apellido": apellido,
                "fecha_nacimiento": fecha_nacimiento,
                "origen": "personas" if es_validado else "manual",
            },
            client_uuid=client_uuid,
            capturado_en=timezone.now(),
            created_by=None,
            validado_renaper=bool(es_validado and nombre and apellido),
        )
        for alcance, campo_id, archivo in form.archivos():
            AdjuntoFormulario.objects.create(
                formulario=formulario,
                pregunta_global_id=campo_id if alcance == "global" else None,
                requisito_nativo_id=campo_id if alcance == "requisito" else None,
                archivo=archivo,
            )
        resolver_ciudadano_offline(formulario)
        formulario.refresh_from_db()
    return formulario, True
