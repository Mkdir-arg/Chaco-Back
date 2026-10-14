from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

from users.models import Profile


class BackofficeSingleSessionMiddleware:
    """Mantiene una sola sesión web activa sin afectar los tokens Mobile."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            profile, _ = Profile.objects.get_or_create(user=request.user)
            # Evita que templates/context processors vuelvan a consultar la
            # misma relación OneToOne durante este request.
            request.user._state.fields_cache["profile"] = profile
            current_key = request.session.session_key

            # Conserva las sesiones que ya estaban abiertas al desplegar esto.
            if not profile.backoffice_session_key:
                profile.backoffice_session_key = current_key
                profile.save(update_fields=["backoffice_session_key"])
            elif profile.backoffice_session_key != current_key:
                logout(request)
                messages.warning(request, "Tu sesión fue reemplazada por un nuevo ingreso.")
                return redirect(reverse("users:login"))

        return self.get_response(request)


class CambioContrasenaObligatorioMiddleware:
    """Con clave provisoria sin cambiar, la única pantalla disponible es cambiarla.

    Va después de BackofficeSingleSessionMiddleware, que ya dejó el Profile en la
    caché de relaciones del request: este chequeo no agrega consultas.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # /api/ usa tokens (Mobile): ahí request.user todavía es anónimo y el
        # cambio de clave se resuelve en el navegador, no interceptando la API.
        if request.user.is_authenticated and not request.path.startswith("/api/"):
            # RelatedObjectDoesNotExist hereda de AttributeError: getattr alcanza.
            profile = getattr(request.user, "profile", None)
            if profile is not None and profile.debe_cambiar_contrasena:
                destino = reverse("users:cambiar_contrasena_obligatorio")
                if request.path not in (destino, reverse("users:logout")):
                    return redirect(destino)

        return self.get_response(request)
