from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.utils import timezone
from django.views.generic import TemplateView

from dashboard.utils import contar_ciudadanos, contar_usuarios
from programas.models import InscripcionPrograma
from users.models import User


# NOTA: esta vista NO se cachea con cache_page/cache_view. Era una página
# autenticada y cache_page (como decorador de vista) genera la clave de cache
# antes de que el middleware agregue ``Vary: Cookie``, por lo que cacheaba la
# página COMPLETA cross-user (sidebar con datos del usuario incluido). Las
# métricas son COUNTs baratos; si hiciera falta optimizar, cachear los cálculos
# a nivel de datos (no la página).
class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from dashboard.utils import (
            contar_alertas_activas,
            contar_legajos,
            contar_seguimientos_hoy,
        )

        context["total_usuarios"] = contar_usuarios()
        context["total_ciudadanos"] = contar_ciudadanos()

        legajo_stats = contar_legajos()
        context["total_legajos"] = legajo_stats["total"]
        context["legajos_activos"] = legajo_stats["activos"]

        context["seguimientos_hoy"] = contar_seguimientos_hoy()
        context["alertas_activas"] = contar_alertas_activas()
        context["actividad_hoy"] = context["seguimientos_hoy"]

        hace_24h = timezone.now() - timedelta(hours=24)
        # Clave **propia**: `inicio_view` dejó de compartirla. Su contador pasó a
        # `home:ingresos_backoffice_24h` y excluye a los ciudadanos del portal (G2-04);
        # este sigue contando a todos, que es el comportamiento viejo de esta vista
        # tapada (RED-78). Las dos claves ya no se pisan.
        context["usuarios_activos"] = cache.get_or_set(
            "home:usuarios_activos_24h",
            lambda: User.objects.filter(last_login__gte=hace_24h).count(),
            300,
        )

        # `fecha_inscripcion` es un DateField en hora local: con la fecha UTC, el
        # 1 de cada mes a la noche el «mes» arrancaba un día tarde (BEC-18).
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        context["registros_mes"] = cache.get_or_set(
            "home:inscripciones_mes",
            lambda: InscripcionPrograma.objects.filter(fecha_inscripcion__gte=inicio_mes).count(),
            300,
        )

        return context
