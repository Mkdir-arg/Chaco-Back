import time

from django.http import HttpResponse


class PerformanceMiddleware:
    """Middleware para optimizaciones de performance"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        # Nota: No devolvemos 304 antes de procesar la vista.
        # Para contenido dinámico, el ETag debe calcularse sobre la
        # respuesta real. Devolver 304 en esta etapa puede congelar
        # páginas con datos obsoletos.

        response = self.get_response(request)

        # Agregar headers de performance
        if hasattr(response, "status_code") and response.status_code == 200:
            processing_time = time.time() - start_time
            response["X-Processing-Time"] = f"{processing_time:.3f}s"

            # Cache control para recursos estáticos
            if request.path.startswith("/static/"):
                response["Cache-Control"] = "public, max-age=31536000"  # 1 año
            elif request.path.startswith("/media/"):
                response["Cache-Control"] = "public, max-age=86400"  # 1 día

            # ETag correcto para páginas dinámicas
            # Calculamos el ETag sobre el contenido ya generado y, si coincide
            # con If-None-Match, devolvemos 304 Not Modified en ese momento.
            if request.method == "GET" and not request.path.startswith(("/static/", "/media/")):
                current_etag = f'"{hash(response.content)}"'
                response["ETag"] = current_etag

                # Para vistas autenticadas, indicar que la respuesta varía por cookie
                # (evita compartir validaciones condicionales entre usuarios).
                if getattr(request, "user", None) and request.user.is_authenticated:
                    vary = response.get("Vary")
                    response["Vary"] = f"{vary}, Cookie" if vary else "Cookie"

                if request.META.get("HTTP_IF_NONE_MATCH") == current_etag:
                    not_modified = HttpResponse(status=304)
                    not_modified["ETag"] = current_etag
                    # Propagar Vary si se agregó
                    if "Vary" in response:
                        not_modified["Vary"] = response["Vary"]
                    return not_modified

        return response
