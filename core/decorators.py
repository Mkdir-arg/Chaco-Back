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
            return redirect('portal:ciudadano_login')
        return view_func(request, *args, **kwargs)

    return _wrapped_view
