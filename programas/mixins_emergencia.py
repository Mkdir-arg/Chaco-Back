"""Mixin de permisos de las vistas de Emergencia.

Vive **fuera de `programas/views/`** por el mismo motivo que `mixins_dispositivos.py`: lo
van a usar varias vistas del módulo (configuración hoy; bandeja, detalle y tablero
después) y una vista que le pide un helper a otra vista es lo que mide el ratchet de
`programas/tests/test_arquitectura.py`.

``core.rbac.requiere`` no alcanza para estas vistas: evalúa la capacidad **sin alcance**
(«la tiene por algún rol»). Las capacidades ``emergencia.*`` son de programa y se evalúan
con ``puede_en_programa_emergencia`` (RU-7).
"""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from programas.services.emergencia_programa import puede_en_programa_emergencia, puede_operar_la_mesa


class EmergenciaPermissionMixin(LoginRequiredMixin):
    """Exige ``capacidad_requerida`` con alcance sobre el programa EMERGENCIA.

    Sin sesión, al login. Con sesión y sin la capacidad en ese programa, 403: no hay nada
    que ocultar detrás de un 404, la pantalla no depende de un id.
    """

    capacidad_requerida = None

    def tiene_permiso(self, user):
        return puede_en_programa_emergencia(user, self.capacidad_requerida)

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not self.tiene_permiso(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class MesaPermissionMixin(EmergenciaPermissionMixin):
    """Las pantallas de la mesa: ``emergencia.operar`` **o** ``emergencia.supervisar`` en el programa.

    Supervisar implica operar (tabla de RU §4), tenga o no el rol tildadas las dos. La mesa
    ve todos los casos (RU-10): un caso no tiene alcance propio, así que un id inexistente
    es un 404 y nada más. Quién puede **actuar** sobre un caso —el que lo tiene tomado, o
    quien supervisa— lo decide el servicio, no este mixin.
    """

    def tiene_permiso(self, user):
        return puede_operar_la_mesa(user)
