"""Aviso por correo de cómo se resolvió el formulario de Becas (Cambio 44).

Cuando el técnico resuelve un formulario en la bandeja de revisión, el
ciudadano se entera por correo. Son **cuatro** desenlaces y no dos, porque
«Aprobar» tiene dos: con cupo aprueba, sin cupo deja en lista de espera
(``aprobar_o_poner_en_espera``), y la promoción posterior desde la lista
vuelve a avisar. ``Formulario.Estado`` no tiene un estado «en espera»: sin
cupo el formulario sigue en ``ENVIADO``, así que el desenlace lo trae quien
llama, no se deduce del estado.

Mismo contrato que el comprobante de inscripción
(``inscripcion_publica.enviar_confirmacion_inscripcion``): respeta el toggle
``confirmar_por_email`` del relevamiento, manda las dos versiones (texto
plano + HTML de marca) y **nunca rompe la acción del técnico** — si SMTP
falla se loguea y devuelve ``False``, con la aprobación o el rechazo ya
firmes.

Se llama **desde la vista**, después de que el servicio de dominio devolvió:
``aprobar_o_poner_en_espera`` y ``promover_lista_espera`` son
``@transaction.atomic`` y un rollback dejaría el correo enviado sin forma de
retractarlo.

Aplica a los dos tipos de relevamiento —público por link y territorial de
campo—: ``email_contacto`` es obligatorio en el modelo y viaja también en el
serializer de la app móvil.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from users.services.correo import contexto_pie

logger = logging.getLogger(__name__)

APROBADO = "aprobado"
LISTA_ESPERA = "lista_espera"
RECHAZADO = "rechazado"
PROMOVIDO = "promovido"

# El asunto es lo único del aviso que no vive en la plantilla: Django lo
# necesita armado antes de renderizar el cuerpo. La promoción usa el mismo
# asunto que la aprobación directa porque para el ciudadano es el mismo hecho.
ASUNTOS = {
    APROBADO: "Tu inscripción fue aprobada",
    LISTA_ESPERA: "Tu inscripción quedó en lista de espera",
    RECHAZADO: "Novedades sobre tu inscripción",
    PROMOVIDO: "Tu inscripción fue aprobada",
}

PLANTILLA_TXT = "programas/becas/email/resolucion_body.txt"
PLANTILLA_HTML = "programas/becas/email/resolucion_body.html"


def _identidad(formulario):
    """``(nombre de pila, documento)`` del inscripto.

    Prioriza el ``Ciudadano`` vinculado: ``datos_identificacion`` se limpia
    cuando el legajo se resuelve, y para cuando el formulario se resuelve casi
    siempre está vinculado (aprobar exige identidad validada). El fallback
    cubre el rechazo, que puede resolverse sin ciudadano resuelto.

    Se devuelve solo el nombre de pila: si la identidad no se validó puede no
    haber nombre, y el saludo queda sin él en lugar de con un hueco raro.
    """
    ciudadano = formulario.ciudadano
    identificacion = formulario.datos_identificacion or {}
    nombre = str(getattr(ciudadano, "nombre", "") or identificacion.get("nombre") or "").strip()
    documento = str(getattr(ciudadano, "dni", "") or identificacion.get("dni") or "").strip()
    return nombre.split(" ")[0], documento


def enviar_aviso_resolucion(formulario, resultado, *, motivo="", protocol="https", domain=""):
    """Avisa al ciudadano cómo se resolvió su formulario.

    ``resultado`` ∈ {"aprobado", "lista_espera", "rechazado", "promovido"}.
    ``motivo`` es el texto que escribió el técnico al rechazar y viaja **tal
    cual** al cuerpo, por decisión del cliente. ``protocol`` y ``domain`` arman
    la URL absoluta del logo —los clientes de correo no resuelven rutas
    relativas—; sin ellos se cae a ``settings.DOMINIO``.

    Devuelve ``True`` solo si el correo salió. Devuelve ``False`` —sin
    propagar nunca— si el relevamiento no notifica, si el formulario no tiene
    correo de contacto, si el ``resultado`` no es uno de los cuatro o si el
    envío falló.
    """
    if resultado not in ASUNTOS:
        logger.error(
            "Resultado desconocido %r al avisar la resolución del formulario %s",
            resultado,
            formulario.pk,
        )
        return False

    relevamiento = formulario.relevamiento
    if not relevamiento.confirmar_por_email or not formulario.email_contacto:
        return False

    convocatoria = relevamiento.convocatoria
    nombre, documento = _identidad(formulario)
    asunto = f"{ASUNTOS[resultado]} — {convocatoria.nombre}"
    contexto = {
        "resultado": resultado,
        "asunto": asunto,
        "numero": formulario.numero,
        "convocatoria": convocatoria.nombre,
        "segmento": convocatoria.segmento.nombre,
        "nombre": nombre,
        "documento": documento,
        "motivo": (motivo or "").strip(),
        "protocol": protocol,
        "domain": domain or settings.DOMINIO,
        "encabezado_seccion": "Portal Ciudadano",
        **contexto_pie(),
    }
    # El armado entra en el try junto con el envío: la vista ya commiteó la
    # aprobación o el rechazo cuando llega acá, así que ni un error de
    # plantilla puede escaparse y voltear la acción del técnico con un 500.
    try:
        cuerpo = render_to_string(PLANTILLA_TXT, contexto)
        html = render_to_string(PLANTILLA_HTML, contexto)
        mensaje = EmailMultiAlternatives(
            subject=asunto,
            body=cuerpo,
            from_email=None,
            to=[formulario.email_contacto],
        )
        mensaje.attach_alternative(html, "text/html")
        mensaje.send(fail_silently=False)
    except Exception:  # SMTP caído, mal configurado, rechazo del servidor…
        logger.exception(
            "No se pudo enviar el aviso de resolución (%s) del formulario %s (relevamiento %s)",
            resultado,
            formulario.pk,
            relevamiento.pk,
        )
        return False
    return True
