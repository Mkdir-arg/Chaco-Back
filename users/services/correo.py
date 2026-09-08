"""Correos de credenciales del backoffice.

Desde el 14/08/2026 el alta de usuario envía la **clave provisoria** en el cuerpo
del mensaje (análisis #236). Esto revierte el criterio del Cambio 13 del archivo
vivo ("no se envían contraseñas en texto plano"): la mitigación acordada es que la
clave sirve una sola vez, porque el primer login obliga a cambiarla.
"""

import secrets

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

# Sin caracteres ambiguos (0/O, 1/l/I): la clave se lee de un correo y se tipea a mano.
ALFABETO_CLAVE = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
LARGO_CLAVE = 12


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


def enviar_credenciales_usuario(user, password_provisoria, *, protocol="https", domain="", rol=""):
    """Envía usuario + clave provisoria. El primer login obliga a cambiarla."""
    if not user.email:
        raise ValueError("El usuario no tiene un correo electrónico informado.")

    contexto = {
        "user": user,
        "password_provisoria": password_provisoria,
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
    """Asigna una clave provisoria, exige el cambio al primer ingreso y la envía.

    Lógica compartida por las dos altas del producto —el ABM de usuarios y el alta
    rápida de los modales de Becas—, para que no queden con criterios distintos.
    Propaga la excepción si el envío falla: el usuario ya quedó creado, y quien
    llama decide cómo avisar (RN-C3).
    """
    from users.models import Profile

    password_provisoria = generar_password_provisoria()

    # Se marca sobre la instancia que el User trae cacheada, no con un
    # update_or_create: `save_user_profile` (post_save de User) re-guarda ese
    # objeto cacheado en cada `user.save()`, y uno escrito por otra vía quedaría
    # pisado por el valor viejo — empezando por el `update_last_login` del login.
    profile = getattr(user, "profile", None) or Profile.objects.create(user=user)
    profile.debe_cambiar_contrasena = True
    profile.save(update_fields=["debe_cambiar_contrasena"])
    user._state.fields_cache["profile"] = profile

    user.set_password(password_provisoria)
    user.save(update_fields=["password"])

    return enviar_credenciales_usuario(
        user,
        password_provisoria,
        protocol="https" if request.is_secure() else "http",
        domain=request.get_host(),
        rol=rol or ", ".join(user.groups.values_list("name", flat=True)),
    )
