from functools import wraps

from django.shortcuts import redirect

from core.rbac import es_ciudadano_portal


def ciudadano_required(view_func):
    """Permite acceso solo a ciudadanos del portal. Redirige al login del portal.

    Usa el marcador de identidad ``es_ciudadano_portal`` (no una capacidad de
    backoffice): el portal y el backoffice quedan separados.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not es_ciudadano_portal(request.user):
            return redirect("portal:ciudadano_login")
        # Un ciudadano del portal SIN legajo vinculado es un estado inválido
        # (p. ej. el grupo "Ciudadanos" se asignó a mano): degradar sin 500.
        from legajos.models import Ciudadano

        if not Ciudadano.objects.filter(usuario=request.user).exists():
            from django.contrib import messages
            from django.contrib.auth import logout

            messages.error(
                request,
                "Tu cuenta no tiene un legajo de ciudadano asociado. Contactá al administrador.",
            )
            logout(request)
            return redirect("portal:ciudadano_login")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
