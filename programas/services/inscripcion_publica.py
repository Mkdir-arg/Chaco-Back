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

import logging
import uuid

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_date

from programas.models import AdjuntoFormulario, Convocatoria, Formulario, Relevamiento
from programas.services.becas import (
    formulario_por_client_uuid,
    resolver_ciudadano_offline,
)
from programas.services.padron import esta_habilitado
from programas.services.personas import fecha_iso
from programas.services.respuestas import identidad_desde_respuestas, legacy_desde_respuestas
from users.services.correo import contexto_pie


class InscripcionNoDisponible(Exception):
    """El relevamiento dejó de aceptar envíos (vencido, pausado, cupo, cerrado)."""


class InscripcionDuplicada(Exception):
    """El DNI ya está inscripto en la convocatoria (RN-P5)."""


class InscripcionNoHabilitada(Exception):
    """El DNI+sexo dejó de figurar en el padrón del relevamiento (RN-P14)."""


def dni_en_convocatoria(convocatoria, dni):
    """RN-P5, única definición: cualquier relevamiento de la convocatoria (de
    campo o público), por ciudadano resuelto o identificación offline. La usan
    el paso 1 del portal y el re-chequeo transaccional del envío.

    Cuenta también los formularios RECHAZADO/BAJA (mismo criterio que la app
    de campo): una persona rechazada no puede reinscribirse por link. Es una
    decisión tomada por omisión, pendiente de confirmar con el programa.
    """
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
    # "personas" (Base de Personas) y "padron" (Cambio 57) acreditan identidad.
    origen = identificacion.get("origen") or "manual"
    es_validado = origen in ("personas", "padron")
    cleaned = form.cleaned_data
    pide_gps = bool(form.definicion.get("requiere_gps"))
    # Cambio 58 (D3): respuestas por clave de ítem + foto de la definición; el
    # contrato anterior (``data`` por pk y columnas fijas) se sigue escribiendo
    # como puente para los lectores que todavía no migraron.
    respuestas = form.respuestas()
    foto = form.foto
    data, fijos = legacy_desde_respuestas(respuestas, foto)
    identidad_respondida = identidad_desde_respuestas(respuestas, foto)

    with transaction.atomic():
        rel = Relevamiento.objects.select_for_update().get(pk=relevamiento.pk)
        if client_uuid:
            try:
                client_uuid_obj = uuid.UUID(str(client_uuid))
            except (TypeError, ValueError):
                client_uuid_obj = None
            if client_uuid_obj:
                existente = formulario_por_client_uuid(rel, client_uuid_obj)
                if existente:
                    return existente, False
        if rel.estado != Relevamiento.Estado.EN_CURSO or not rel.habilitado_en(timezone.now()):
            raise InscripcionNoDisponible()
        if rel.formularios.count() >= rel.cupo_maximo:
            raise InscripcionNoDisponible()
        # El duplicado es por convocatoria completa: se lockea la convocatoria
        # para que dos envíos simultáneos por relevamientos distintos no pasen.
        convocatoria = Convocatoria.objects.select_for_update().get(pk=rel.convocatoria_id)
        if dni_en_convocatoria(convocatoria, dni):
            raise InscripcionDuplicada()
        if not esta_habilitado(rel, dni, identificacion.get("sexo", "")):
            raise InscripcionNoHabilitada()

        if es_validado:
            nombre = datos_basicos.get("nombre", "")
            apellido = datos_basicos.get("apellido", "")
            fecha_nacimiento = fecha_iso(datos_basicos.get("fecha_nacimiento")) or identidad_respondida.get(
                "fecha_nacimiento", ""
            )
        else:
            nombre = identidad_respondida.get("nombre", "")
            apellido = identidad_respondida.get("apellido", "")
            fecha_nacimiento = identidad_respondida.get("fecha_nacimiento", "")

        formulario = Formulario.objects.create(
            relevamiento=rel,
            celular=fijos.get("celular", ""),
            email_contacto=fijos.get("email_contacto", ""),
            apoderado_nombre=fijos.get("apoderado_nombre", ""),
            apoderado_apellido=fijos.get("apoderado_apellido", ""),
            apoderado_dni=fijos.get("apoderado_dni", ""),
            apoderado_genero=fijos.get("apoderado_genero", ""),
            apoderado_fecha_nacimiento=parse_date(str(fijos.get("apoderado_fecha_nacimiento") or "")) or None,
            # Solo si el segmento pide ubicación: el navegador la manda igual y
            # es el domicilio del ciudadano con precisión de metros.
            gps_lat=cleaned.get("gps_lat") if pide_gps else None,
            gps_lng=cleaned.get("gps_lng") if pide_gps else None,
            data=data,
            respuestas=respuestas,
            definicion=foto,
            # Mismo contrato que el sync offline de la app: el origen
            # "personas" acredita identidad (validado_renaper); "manual" no.
            datos_identificacion={
                "dni": dni,
                "sexo": identificacion.get("sexo", ""),
                "nombre": nombre,
                "apellido": apellido,
                "fecha_nacimiento": fecha_nacimiento,
                "origen": origen if es_validado else "manual",
                # Localidad del padrón: solo para completar el legajo.
                "localidad_id": datos_basicos.get("localidad_id") if es_validado else None,
            },
            client_uuid=client_uuid,
            capturado_en=timezone.now(),
            created_by=None,
            validado_renaper=bool(es_validado and nombre and apellido),
            origen_validacion=(origen if es_validado and nombre and apellido else ""),
        )
        for clave, item, archivo in form.archivos():
            if not (clave.startswith("pg-") or clave.startswith("rn-")):
                continue  # un campo propio no puede ser archivo (lo veta el constructor)
            AdjuntoFormulario.objects.create(
                formulario=formulario,
                pregunta_global_id=item["id"] if clave.startswith("pg-") else None,
                requisito_nativo_id=item["id"] if clave.startswith("rn-") else None,
                archivo=archivo,
            )
        resolver_ciudadano_offline(formulario)
        formulario.refresh_from_db()
    return formulario, True


# --- Correo de confirmación (#296, RN-P10) ---------------------------------

logger = logging.getLogger(__name__)


def enmascarar_email(email):
    """``maria.gomez@correo.com`` → ``ma•••@correo.com`` para el comprobante."""
    usuario, _, dominio = (email or "").partition("@")
    if not dominio:
        return email or ""
    visible = usuario[:2] if len(usuario) > 2 else usuario[:1]
    return f"{visible}•••@{dominio}"


def enviar_confirmacion_inscripcion(formulario, *, protocol="https", domain=""):
    """Manda el comprobante a ``email_contacto`` si el relevamiento tiene el
    toggle activo. Exclusivo del flujo público: la API de campo no lo llama.

    Va en dos versiones, como el resto de los correos del sistema: texto plano y
    HTML de marca (``confirmacion_body.txt`` / ``.html``). ``protocol`` y
    ``domain`` arman la URL absoluta del logo —los clientes de correo no
    resuelven rutas relativas—; sin ellos se cae a ``settings.DOMINIO``.

    Nunca rompe la inscripción: cualquier falla de SMTP se loguea y devuelve
    ``False`` (el formulario ya quedó creado y la persona ve su comprobante).
    """
    relevamiento = formulario.relevamiento
    if not relevamiento.confirmar_por_email or not formulario.email_contacto:
        return False
    convocatoria = relevamiento.convocatoria
    identificacion = formulario.datos_identificacion or {}
    contexto = {
        "numero": formulario.numero,
        "convocatoria": convocatoria.nombre,
        "segmento": convocatoria.segmento.nombre,
        # Nombre de pila para el saludo: si la identidad no se validó puede no
        # estar, y el saludo queda sin nombre en lugar de con un hueco raro.
        "nombre": (identificacion.get("nombre") or "").split(" ")[0],
        "documento": identificacion.get("dni") or getattr(formulario.ciudadano, "dni", "") or "",
        "enviado_el": timezone.localtime(formulario.creado).strftime("%d/%m/%Y %H:%M"),
        "protocol": protocol,
        "domain": domain or settings.DOMINIO,
        "encabezado_seccion": "Portal Ciudadano",
        **contexto_pie(),
    }
    cuerpo = render_to_string("portal/inscripcion/email/confirmacion_body.txt", contexto)
    html = render_to_string("portal/inscripcion/email/confirmacion_body.html", contexto)
    mensaje = EmailMultiAlternatives(
        subject=f"Comprobante de inscripción — {convocatoria.nombre}",
        body=cuerpo,
        from_email=None,
        to=[formulario.email_contacto],
    )
    mensaje.attach_alternative(html, "text/html")
    try:
        mensaje.send(fail_silently=False)
    except Exception:  # SMTP caído, mal configurado, rechazo del servidor…
        logger.exception(
            "No se pudo enviar el correo de confirmación del formulario %s (relevamiento %s)",
            formulario.pk,
            relevamiento.pk,
        )
        return False
    return True
