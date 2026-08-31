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
from datetime import datetime

from django.conf import settings
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from portal.forms.inscripcion import InscripcionPaso1Form, InscripcionPaso2Form
from portal.services.inscripcion import (
    captcha_activo,
    captcha_valido,
    clave_sesion,
    consumir_captcha,
    dni_ya_inscripto,
    documento_excedido,
    nuevo_captcha,
    paso1_excedido,
    paso2_excedido,
    pregunta_captcha,
    relevamiento_disponible,
)
from programas.models import Relevamiento
from programas.services.becas import definicion_formulario
from programas.services.identidad import identificar
from programas.services.inscripcion_publica import (
    InscripcionDuplicada,
    InscripcionNoDisponible,
    InscripcionNoHabilitada,
    crear_formulario_publico,
    enmascarar_email,
    enviar_confirmacion_inscripcion,
)
from programas.services.padron import esta_habilitado

logger = logging.getLogger(__name__)

# Un ÚNICO mensaje para los tres rechazos del paso 1 —fuera del padrón, ya
# inscripto, documento no disponible— porque textos distintos convertían el
# formulario en un oráculo: barriendo documentos se reconstruía el padrón de
# habilitados (dato socioeconómico) y se averiguaba quién ya se había inscripto,
# incluidas las personas relevadas en campo. Revisión de seguridad del 26/08/2026.
MENSAJE_RECHAZO = (
    "No podés inscribirte con ese documento. Si creés que es un error, comunicate con el programa al +54 362 430-0002."
)
MENSAJE_DEMASIADOS_INTENTOS = "Realizaste demasiados intentos. Esperá unos minutos y volvé a probar."
# Cuánto vale la identificación del paso 1 antes de tener que rehacerla.
IDENTIFICACION_VIGENCIA_SEGUNDOS = 45 * 60


def _identificacion_vencida(identificacion):
    """La identificación del paso 1 vale un rato, no las 24 h de la sesión.

    En una terminal compartida —un cíber, un centro comunitario— el documento de
    la persona anterior quedaba listo para completar. Se guarda un sello propio
    en vez de acortar la sesión entera, que se llevaba puesto el paso 2 a medio
    llenar.
    """
    sellada = identificacion.get("sellada")
    if not sellada:
        return False
    try:
        momento = datetime.fromisoformat(sellada)
    except (TypeError, ValueError):
        return True
    return (timezone.now() - momento).total_seconds() > IDENTIFICACION_VIGENCIA_SEGUNDOS


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
    pantalla: nombre, apellido y fecha de nacimiento (RN-P7). Nunca domicilio.
    La localidad del padrón (Cambio 57) viaja solo como id para el legajo: no
    se muestra."""
    data = data or {}
    return {
        "nombre": data.get("nombre", ""),
        "apellido": data.get("apellido", ""),
        "fecha_nacimiento": data.get("fecha_nacimiento", ""),
        "localidad_id": data.get("localidad_id"),
    }


def inscripcion_paso1(request, token):
    relevamiento = _get_relevamiento(token)
    if not relevamiento_disponible(relevamiento):
        return _no_disponible(request, relevamiento)

    form = InscripcionPaso1Form(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        if paso1_excedido(request):
            # Solo se valida el form para poder colgarle el error general: no
            # se registra el intento ni se consulta identidad.
            form.is_valid()
            form.add_error(None, MENSAJE_DEMASIADOS_INTENTOS)
        elif not captcha_valido(request, request.POST.get("captcha")):
            form.add_error("captcha", "La verificación no es correcta. Probá de nuevo.")
        elif form.is_valid():
            consumir_captcha(request)
            dni = form.cleaned_data["dni"]
            sexo = form.cleaned_data["sexo"]
            if documento_excedido(request, dni):
                # Recién acá: el captcha ya se resolvió, así que esta cubeta no
                # se puede quemar en nombre de otro con un script.
                form.add_error(None, MENSAJE_DEMASIADOS_INTENTOS)
            elif not esta_habilitado(relevamiento, dni, sexo):
                form.add_error(None, MENSAJE_RECHAZO)
            elif dni_ya_inscripto(relevamiento.convocatoria, dni):
                form.add_error(None, MENSAJE_RECHAZO)
            else:
                # Cascada del Cambio 57 sobre el padrón efectivo del
                # relevamiento (propio o heredado, Cambio 59) → Gran Base → manual.
                resultado = identificar(relevamiento, dni, sexo)
                if resultado["fallecido"]:
                    form.add_error(None, MENSAJE_RECHAZO)
                else:
                    validado = resultado["validado"]
                    request.session[clave_sesion(relevamiento)] = {
                        "dni": dni,
                        "sexo": sexo,
                        "datos": _datos_basicos(resultado["datos"]) if validado else None,
                        # Mismo contrato de origen que la app de campo (#82):
                        # "personas" y "padron" acreditan identidad; "manual" no.
                        "origen": resultado["origen"] if validado else "manual",
                    }
                    # Caduca por sí misma, sin tocar la expiración de la
                    # sesión: acortar la sesión entera hacía perder el paso 2 a
                    # medio completar (con los adjuntos ya elegidos). El sello
                    # se renueva en cada paso del formulario.
                    request.session[clave_sesion(relevamiento)]["sellada"] = timezone.now().isoformat()
                    return redirect("portal:inscripcion_paso2", token=relevamiento.token_publico)

    contexto = {
        "relevamiento": relevamiento,
        "convocatoria": relevamiento.convocatoria,
        "form": form,
        "captcha_pregunta": (
            nuevo_captcha(request)
            if request.method == "POST" and captcha_activo() == "aritmetico"
            else pregunta_captcha(request)
        ),
        "captcha_tipo": captcha_activo(),
        "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
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
    if not identificacion or _identificacion_vencida(identificacion):
        request.session.pop(clave_sesion(relevamiento), None)
        return redirect("portal:inscripcion_paso1", token=relevamiento.token_publico)
    # Cada paso por el formulario renueva la vigencia: lo que caduca es dejarlo
    # abandonado, no tardar en completarlo.
    identificacion["sellada"] = timezone.now().isoformat()
    request.session[clave_sesion(relevamiento)] = identificacion
    if request.method == "POST" and paso2_excedido(request, identificacion.get("dni", "")):
        # El envío es el que escribe y el que recibe archivos: sin techo, una
        # sesión válida podía POSTear adjuntos indefinidamente.
        return render(request, "portal/inscripcion/demasiados_intentos.html", {"relevamiento": relevamiento})

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
        except InscripcionNoHabilitada:
            # El padrón cambió entre el paso 1 y el envío (RN-P14).
            form.add_error(None, MENSAJE_RECHAZO)
        else:
            # Correo de confirmación (#296): solo si el relevamiento lo tiene
            # activo y solo en el envío que creó el formulario; su falla no
            # rompe nada (queda logueada).
            correo_enviado = bool(
                creado
                and enviar_confirmacion_inscripcion(
                    formulario,
                    protocol="https" if request.is_secure() else "http",
                    domain=request.get_host(),
                )
            )
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
            # Los items con sus condiciones para el motor del navegador (Cambio 58).
            "planos": form.planos(),
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


@require_GET
def csrf_token_vigente(request):
    """Devuelve el token CSRF que corresponde a la cookie actual del navegador.

    El backoffice y el portal comparten dominio, y `django.contrib.auth.login`
    rota la cookie CSRF de todo el navegador (Django lo hace en `login()`). Quien
    tenía este formulario público abierto en otra pestaña se quedaba con un token
    viejo y el envío moría en un 403 sin poder recuperarse. El shell del
    formulario pide el token de nuevo cada vez que la pestaña vuelve al frente.

    No expone nada: es el mismo token que ya viaja en el HTML del formulario y
    solo lo puede leer una página del propio origen.
    """
    respuesta = JsonResponse({"token": get_token(request)})
    respuesta["Cache-Control"] = "no-store"
    return respuesta
