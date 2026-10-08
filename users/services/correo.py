"""Correos de credenciales del backoffice.

Desde el 14/08/2026 el alta de usuario envía la **clave provisoria** en el cuerpo
del mensaje (análisis #236). Esto revierte el criterio del Cambio 13 del archivo
vivo ("no se envían contraseñas en texto plano"): la mitigación acordada es que la
clave sirve una sola vez, porque el primer login obliga a cambiarla.
"""

import secrets

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from core import rbac

# Sin caracteres ambiguos (0/O, 1/l/I): la clave se lee de un correo y se tipea a mano.
ALFABETO_CLAVE = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
LARGO_CLAVE = 12

#: Cómo se entregaron las credenciales. Lo devuelve
#: :func:`entregar_credenciales_provisorias` para que la pantalla diga la verdad.
ENTREGA_CLAVE = "clave"
ENTREGA_LINK = "link"


def generar_password_provisoria(largo: int = LARGO_CLAVE) -> str:
    return "".join(secrets.choice(ALFABETO_CLAVE) for _ in range(largo))


def contexto_pie() -> dict:
    """Datos comunes a todos los correos: prefijo de asunto y pie.

    Se usa también como ``extra_email_context`` del flujo de recupero de Django.
    """
    return {
        "prefijo_asunto": settings.EMAIL_ASUNTO_PREFIJO,
        "soporte": settings.EMAIL_SOPORTE,
        "direccion_postal": settings.EMAIL_PIE_DIRECCION,
    }


def enviar_credenciales_usuario(
    user, password_provisoria, *, protocol="https", domain="", rol="", enlace_establecer=""
):
    """Envía los datos de acceso del usuario recién creado.

    Con ``password_provisoria`` el correo lleva la clave y la promesa de que el
    sistema va a pedir cambiarla en el primer ingreso. Con ``enlace_establecer``
    —el caso del territorial, D-26— lleva un link de un solo uso para que la
    defina él: a esa persona el backoffice nunca le va a pedir nada, porque el
    login web la rechaza y la app entra por la API.
    """
    if not user.email:
        raise ValueError("El usuario no tiene un correo electrónico informado.")

    contexto = {
        "user": user,
        "password_provisoria": password_provisoria,
        "enlace_establecer": enlace_establecer,
        "rol": rol,
        "protocol": protocol,
        "domain": domain,
        "enlace_login": f"{protocol}://{domain}{reverse('users:login')}",
        **contexto_pie(),
    }

    # Django colapsa el asunto a una línea; el template lo deja legible igual.
    asunto = "".join(render_to_string("user/email/credenciales_usuario_asunto.txt", contexto).splitlines())
    cuerpo = render_to_string("user/email/credenciales_usuario.txt", contexto)
    html = render_to_string("user/email/credenciales_usuario.html", contexto)

    mensaje = EmailMultiAlternatives(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [user.email])
    mensaje.attach_alternative(html, "text/html")
    return mensaje.send(fail_silently=False)


def entregar_credenciales_provisorias(user, request, rol=""):
    """Entrega las credenciales del alta y devuelve **cómo** las entregó.

    Lógica compartida por las dos altas del producto —el ABM de usuarios y el alta
    rápida de los modales de Becas—, para que no queden con criterios distintos.
    Propaga la excepción si el envío falla: el usuario ya quedó creado, y quien
    llama decide cómo avisar (RN-C3).

    **D-26 (auditoría oct-2026):** al usuario que solo existe para la app de campo
    no se le manda una clave provisoria en texto plano, sino un **link de reseteo**
    para que elija la suya. El Cambio 37 había aceptado mandarla en claro apoyado
    en que «sirve una sola vez, porque el primer login obliga a cambiarla»; para el
    territorial esa mitigación no existe: el login web lo rechaza
    (``territorial_mobile_only``) y la API no mira el flag, así que la clave del
    correo le quedaba vigente **para siempre** y
    ``debe_cambiar_contrasena`` en ``True`` sin manera de limpiarlo. El resto de
    los usuarios sigue igual que antes.
    """
    from users.models import Profile

    # Se marca sobre la instancia que el User trae cacheada y se sincroniza la
    # relación: es de donde la leen el middleware y el gate de clave (RED-52).
    profile = getattr(user, "profile", None) or Profile.objects.create(user=user)
    profile.debe_cambiar_contrasena = True
    profile.save(update_fields=["debe_cambiar_contrasena"])
    user._state.fields_cache["profile"] = profile

    protocol = "https" if request.is_secure() else "http"
    domain = request.get_host()
    rol = rol or ", ".join(user.groups.values_list("name", flat=True))
    solo_campo = rbac.es_solo_campo(user)

    # En los dos casos la clave que había deja de servir. En el del link, la que
    # se escribe no la conoce nadie: es solo para que la cuenta tenga una clave
    # usable y «Olvidé mi contraseña» siga funcionando si el link vence.
    password_provisoria = generar_password_provisoria(32 if solo_campo else LARGO_CLAVE)
    user.set_password(password_provisoria)
    user.save(update_fields=["password"])

    enlace_establecer = ""
    if solo_campo:
        enlace_establecer = "{}://{}{}".format(
            protocol,
            domain,
            reverse(
                "users:establecer_contrasena",
                kwargs={
                    "uidb64": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": default_token_generator.make_token(user),
                },
            ),
        )
        password_provisoria = ""

    enviar_credenciales_usuario(
        user,
        password_provisoria,
        protocol=protocol,
        domain=domain,
        rol=rol,
        enlace_establecer=enlace_establecer,
    )
    return ENTREGA_LINK if solo_campo else ENTREGA_CLAVE
