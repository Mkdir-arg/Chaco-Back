from django.http import JsonResponse
from django.views.generic import TemplateView

from core.selectors.geografia import get_localidades_values, get_municipios_values

from ..selectors import get_portal_home_context


class PortalHomeView(TemplateView):
    template_name = "portal/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_portal_home_context())
        return context


def get_municipios(request):
    provincia_id = request.GET.get("provincia_id")
    return JsonResponse(get_municipios_values(provincia_id), safe=False)


def get_localidades(request):
    municipio_id = request.GET.get("municipio_id")
    return JsonResponse(get_localidades_values(municipio_id), safe=False)
