from django.conf import settings
from django.core.mail import send_mail


def enviar_invitacion_usuario(user, enlace_contrasena):
    """Envía el alta sin incluir contraseñas en texto plano."""
    if not user.email:
        raise ValueError("El usuario no tiene un correo electrónico informado.")

    nombre = user.get_full_name().strip() or user.username
    asunto = "Tu usuario de DATAÑACH fue creado"
    cuerpo = (
        f"Hola {nombre},\n\n"
        "Se creó tu usuario para ingresar a DATAÑACH.\n\n"
        f"Usuario: {user.username}\n"
        f"Para establecer tu contraseña ingresá en: {enlace_contrasena}\n\n"
        "Por seguridad, no compartas este enlace. Si no solicitaste el acceso, "
        "comunicate con el administrador del sistema.\n"
    )
    return send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
