from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from core.rbac import requiere
from .selectors.ciudadanos import buscar_ciudadanos_rapido


@login_required
@requiere("ciudadano.ver", "ciudadano.crear")
def ciudadano_buscar_api(request):
    """
    Endpoint AJAX para la búsqueda rápida de ciudadanos desde el header del backoffice.
    GET /legajos/ciudadanos/buscar/?q=<término>
    """
    q = request.GET.get('q', '')
    resultados = buscar_ciudadanos_rapido(q)
    return JsonResponse({'resultados': resultados})
