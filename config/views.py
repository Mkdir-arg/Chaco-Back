from django.shortcuts import render
from django.views.csrf import csrf_failure as csrf_failure_django


def server_error(request, template_name="500.html"):
    """Render the 500 error page with the request in the context."""
    return render(request, template_name, status=500)


def _destino_seguro(request):
    """La ruta a la que se puede volver, sin abrir un redirect a otro dominio.

    `//otro-dominio` es una ruta válida para el navegador pero una URL absoluta
    dentro de un `href`, así que no alcanza con exigir que empiece con «/».
    """
    destino = request.get_full_path()
    if destino.startswith("/") and not destino.startswith("//"):
        return destino
    return "/portal/"


def csrf_failure(request, reason=""):
    """CSRF fallido: en el portal público la pantalla tiene que ser recuperable.

    El 403 crudo de Django no le dice nada a un ciudadano ni le deja continuar, y
    en un formulario público la causa habitual no es un ataque: el backoffice y el
    portal comparten dominio y `django.contrib.auth.login` rota la cookie CSRF de
    todo el navegador, así que un formulario abierto en otra pestaña se queda con
    un token que ya no vale.

    Fuera del portal se conserva la pantalla de Django tal como estaba: el
    backoffice es una superficie con login y su 403 no se toca en este cambio.
    """
    if request.path.startswith("/portal/"):
        return render(
            request,
            "portal/sesion_vencida.html",
            {"volver": _destino_seguro(request), "motivo": reason},
            status=403,
        )
    return csrf_failure_django(request, reason=reason)
