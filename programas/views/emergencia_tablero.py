"""E1 · Tablero del supervisor de Emergencia: si la emergencia está bajo control, en una pantalla.

Solo orquesta: arma una vez la foto del tablero (``selectors.emergencia_tablero``), le pide a
cada selector su parte y a ``services.avisos_emergencia`` los avisos, y lo pasa al template.
Lo ve solo quien supervisa la mesa (decisión del PM, RU §4: el operador no): sin la
capacidad en el programa, 403.

Sin auto-refresh: «Actualizar» vuelve a pedir la pantalla.

**Presupuesto de la vista completa** (``test_emergencia_tablero``, 500 casos abiertos, 50
dispositivos y 200 entregas): los 10 de los selectores, a lo sumo 3 de los avisos, el SLA
vigente y lo que ponen la sesión, el usuario y el shell (sidebar y permisos memoizados).
"""

from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from programas.mixins_emergencia import EmergenciaPermissionMixin
from programas.selectors import emergencia_tablero as tablero
from programas.services.avisos_emergencia import avisos_del_tablero
from programas.services.configuracion_emergencia import sla_vigente
from programas.services.emergencia_programa import CAP_SUPERVISAR

TEMPLATE = "programas/emergencia/tablero.html"


class TableroView(EmergenciaPermissionMixin, View):
    capacidad_requerida = CAP_SUPERVISAR

    def get(self, request):
        sla, ahora = sla_vigente(), timezone.now()
        foto = tablero.foto_del_tablero(sla, ahora)
        entregas, total_entregas = tablero.entregas_en_camino(ahora)
        contexto = {
            "resumen": tablero.resumen(sla, ahora, foto=foto),
            "localidades": tablero.por_localidad(sla, ahora, foto=foto),
            "tiempos": tablero.tiempos(sla, ahora, foto=foto),
            "entregas": entregas,
            "entregas_ocultas": max(total_entregas - len(entregas), 0),
            "avisos": avisos_del_tablero(sla, ahora, usuario=request.user, foto=foto),
            "actualizado": f"{timezone.localtime(ahora):%d/%m/%Y %H:%M}",
            "url_actualizar": reverse("emergencia:tablero"),
            "url_entregas": f"{reverse('emergencia:entregas')}?solapa=abiertas",
        }
        return render(request, TEMPLATE, contexto)
