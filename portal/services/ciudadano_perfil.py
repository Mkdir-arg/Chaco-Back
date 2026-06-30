from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse

from users.models import SolicitudCambioEmail


class CambioEmailInvalidoError(Exception):
    pass


class CambioEmailExpiradoError(Exception):
    pass


def crear_solicitud_cambio_email(*, request, user, nuevo_email):
    SolicitudCambioEmail.objects.filter(
        user=user,
        confirmado=False,
        expirado=False,
    ).update(expirado=True)

    solicitud = SolicitudCambioEmail.objects.create(
        user=user,
        nuevo_email=nuevo_email,
    )
    link = request.build_absolute_uri(
        reverse("portal:ciudadano_confirmar_email", kwargs={"token": str(solicitud.token)})
    )
    send_mail(
        subject="Confirmar cambio de email — Portal Ciudadano",
        message=(
            f"Hacé clic en el siguiente enlace para confirmar tu nuevo email:\n\n"
            f"{link}\n\n"
            f"Este enlace vence en 24 horas."
        ),
        from_email=None,
        recipient_list=[nuevo_email],
        fail_silently=False,
    )
    return solicitud


@transaction.atomic
def confirmar_cambio_email(*, token):
    try:
        solicitud = (
            SolicitudCambioEmail.objects.select_for_update()
            .select_related("user")
            .get(
                token=token,
                confirmado=False,
                expirado=False,
            )
        )
    except SolicitudCambioEmail.DoesNotExist as exc:
        raise CambioEmailInvalidoError() from exc

    if not solicitud.esta_vigente:
        solicitud.expirado = True
        solicitud.save(update_fields=["expirado"])
        raise CambioEmailExpiradoError()

    user = solicitud.user
    ciudadano = user.ciudadano_perfil
    user.email = solicitud.nuevo_email
    user.save(update_fields=["email"])

    ciudadano.email = solicitud.nuevo_email
    ciudadano.save(update_fields=["email"])

    solicitud.confirmado = True
    solicitud.save(update_fields=["confirmado"])
    return user, ciudadano
