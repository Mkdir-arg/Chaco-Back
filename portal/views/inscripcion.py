"""Formulario público de inscripción de Becas — superficie sin login (#293).

Paso 1: la persona se identifica con DNI + sexo. En orden (análisis #289):
captcha → rate limit por IP → padrón si el relevamiento lo tiene (RN-P14) →
duplicado por convocatoria (RN-P5) → consulta a Gran Base/RENAPER (RN-P6).
Con match se precargan **solo datos básicos** en la sesión (RN-P7); sin match
se continúa igual y el formulario quedará no validado.

Paso 2 (#294): el mismo formulario dinámico que la app de campo; su envío crea
el formulario y el legajo en el acto (#295) y, si el relevamiento lo tiene
activo, manda el comprobante por correo (#296).
"""

import logging
import uuid

from django.shortcuts import get_object_or_404, redirect, render

from portal.forms.inscripcion import InscripcionPaso1Form, InscripcionPaso2Form
from portal.services.inscripcion import (
    captcha_valido,
    clave_sesion,
    dni_ya_inscripto,
    intentos_excedidos,
    nuevo_captcha,
    pregunta_captcha,
    registrar_intento,
    relevamiento_disponible,
)
from programas.models import Relevamiento
from programas.services.becas import definicion_formulario
from programas.services.inscripcion_publica import (
    InscripcionDuplicada,
    InscripcionNoDisponible,
    crear_formulario_publico,
    enmascarar_email,
    enviar_confirmacion_inscripcion,
)
from programas.services.padron import esta_habilitado
from programas.services.personas import consultar_persona

logger = logging.getLogger(__name__)

MENSAJE_NO_HABILITADO = "No estás habilitado para esta inscripción."
MENSAJE_DOCUMENTO_NO_DISPONIBLE = "La inscripción no está disponible para ese documento."
MENSAJE_DEMASIADOS_INTENTOS = "Realizaste demasiados intentos. Esperá unos minutos y volvé a probar."


def _get_relevamiento(token):
    return get_object_or_404(
        Relevamiento.objects.select_related("convocatoria__segmento"),
        token_publico=token,
        tipo=Relevamiento.Tipo.PUBLICO,
    )


def _no_disponible(request, relevamiento):
    # Una sola pantalla para vencido, pausado, cupo lleno o cerrado (RN-P4).
    return render(request, "portal/inscripcion/no_disponible.html", {"relevamiento": relevamiento})


def _datos_basicos(data):
    """Lo único que puede viajar del servicio de identidad a la sesión y a la
    pantalla: nombre, apellido y fecha de nacimiento (RN-P7). Nunca domicilio."""
    return {
        "nombre": data.get("nombre", ""),
        "apellido": data.get("apellido", ""),
        "fecha_nacimiento": data.get("fecha_nacimiento", ""),
    }


def inscripcion_paso1(request, token):
    relevamiento = _get_relevamiento(token)
    if not relevamiento_disponible(relevamiento):
        return _no_disponible(request, relevamiento)

    form = InscripcionPaso1Form(request.POST or None)
    if request.method == "POST":
        if intentos_excedidos(request):
            form = InscripcionPaso1Form()  # no procesar nada del POST
            form.add_error(None, MENSAJE_DEMASIADOS_INTENTOS)
        elif not captcha_valido(request, request.POST.get("captcha")):
            registrar_intento(request)
            form.add_error("captcha", "La verificación no es correcta. Probá de nuevo.")
        elif form.is_valid():
            registrar_intento(request)
            dni = form.cleaned_data["dni"]
            sexo = form.cleaned_data["sexo"]
            if not esta_habilitado(relevamiento, dni, sexo):
                form.add_error(None, MENSAJE_NO_HABILITADO)
            elif dni_ya_inscripto(relevamiento.convocatoria, dni):
                return render(
                    request,
                    "portal/inscripcion/ya_inscripto.html",
                    {"relevamiento": relevamiento, "dni": dni},
                )
            else:
                resultado = consultar_persona(dni, sexo)
                if resultado.get("fallecido"):
                    form.add_error(None, MENSAJE_DOCUMENTO_NO_DISPONIBLE)
                else:
                    datos = _datos_basicos(resultado.get("data") or {}) if resultado.get("success") else None
                    validado = bool(datos and datos["nombre"] and datos["apellido"])
                    request.session[clave_sesion(relevamiento)] = {
                        "dni": dni,
                        "sexo": sexo,
                        "datos": datos if validado else None,
                        # Mismo contrato de origen que la app de campo (#82):
                        # "personas" acredita identidad; "manual" no.
                        "origen": "personas" if validado else "manual",
                    }
                    return redirect("portal:inscripcion_paso2", token=relevamiento.token_publico)
        else:
            registrar_intento(request)

    contexto = {
        "relevamiento": relevamiento,
        "convocatoria": relevamiento.convocatoria,
        "form": form,
        "captcha_pregunta": nuevo_captcha(request) if request.method == "POST" else pregunta_captcha(request),
    }
    return render(request, "portal/inscripcion/paso1.html", contexto)


def inscripcion_paso2(request, token):
    """Paso 2 (#294): el mismo formulario dinámico que la app de campo, más
    contacto, apoderado para menores y GPS best-effort. El envío crea el
    formulario y el legajo en el acto (#295) y redirige al comprobante."""
    relevamiento = _get_relevamiento(token)
    if not relevamiento_disponible(relevamiento):
        return _no_disponible(request, relevamiento)
    identificacion = request.session.get(clave_sesion(relevamiento))
    if not identificacion:
        return redirect("portal:inscripcion_paso1", token=relevamiento.token_publico)

    # Idempotencia del doble submit: un client_uuid por identificación, igual
    # que las capturas de la app (RN de #295).
    if not identificacion.get("client_uuid"):
        identificacion["client_uuid"] = str(uuid.uuid4())
        request.session[clave_sesion(relevamiento)] = identificacion

    definicion = definicion_formulario(relevamiento)
    form = InscripcionPaso2Form(
        request.POST or None,
        request.FILES or None,
        definicion=definicion,
        identificacion=identificacion,
    )
    if request.method == "POST" and form.is_valid():
        try:
            formulario, creado = crear_formulario_publico(
                relevamiento,
                identificacion=identificacion,
                form=form,
                client_uuid=identificacion["client_uuid"],
            )
        except InscripcionNoDisponible:
            return _no_disponible(request, relevamiento)
        except InscripcionDuplicada:
            return render(
                request,
                "portal/inscripcion/ya_inscripto.html",
                {"relevamiento": relevamiento, "dni": identificacion["dni"]},
            )
        # Correo de confirmación (#296): solo si el relevamiento lo tiene
        # activo y solo en el envío que creó el formulario; su falla no
        # rompe nada (queda logueada).
        correo_enviado = bool(creado and enviar_confirmacion_inscripcion(formulario))
        request.session.pop(clave_sesion(relevamiento), None)
        request.session[f"inscripcion_ok_{relevamiento.pk}"] = {
            "numero": formulario.numero,
            "email": enmascarar_email(formulario.email_contacto),
            "correo_enviado": correo_enviado,
        }
        return redirect("portal:inscripcion_confirmacion", token=relevamiento.token_publico)

    return render(
        request,
        "portal/inscripcion/paso2.html",
        {
            "relevamiento": relevamiento,
            "convocatoria": relevamiento.convocatoria,
            "identificacion": identificacion,
            "form": form,
            "requiere_gps": definicion["requiere_gps"],
        },
    )


def inscripcion_confirmacion(request, token):
    """Comprobante del envío. Se alimenta de la sesión para tolerar el refresh
    sin duplicar nada; sin envío previo, vuelve al paso 1."""
    relevamiento = _get_relevamiento(token)
    comprobante = request.session.get(f"inscripcion_ok_{relevamiento.pk}")
    if not comprobante:
        return redirect("portal:inscripcion_paso1", token=relevamiento.token_publico)
    return render(
        request,
        "portal/inscripcion/confirmacion.html",
        {
            "relevamiento": relevamiento,
            "convocatoria": relevamiento.convocatoria,
            "comprobante": comprobante,
        },
    )
