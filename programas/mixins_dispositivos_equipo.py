"""La solapa «Equipo» de la ficha del dispositivo (Cambio 411) y sus modales armados por URL.

Salió de `dispositivos_legajo` sin cambiar comportamiento. Vive **fuera de `programas/views/`** como
`mixins_dispositivos`: una vista que le pide algo a otra vista es lo que mide el ratchet de
`programas/tests/test_arquitectura.py`.
"""

from django.contrib import messages
from django.urls import reverse
from django.utils.http import urlencode

from programas.forms_equipo_dispositivo import (
    MENSAJE_EQUIPO_PEDIR_ALTA,
    MENSAJE_EQUIPO_SIN_PERSONA,
    AlcanceMiembroEquipoForm,
    CrearPersonaEquipoForm,
    SumarMiembroEquipoForm,
)
from programas.mixins_dispositivos import (  # noqa: F401  (re-exportados: los importan otras vistas)
    DispositivoAltaPermissionMixin,
    DispositivoObjectPermissionMixin,
    DispositivoProgramaPermissionMixin,
    dispositivo_operable_o_404,
)
from programas.mixins_dispositivos_sectores import _entero
from programas.models import (
    Edificio,
)
from programas.services.equipo_dispositivo import (
    edificios_donde_agregar_persona,
    equipo_del_dispositivo,
    opciones_de_alcance,
    permisos_del_equipo,
    puede_crear_persona,
    roles_para_crear_persona,
)


class EquipoDelLegajoMixin:
    """La solapa «Equipo» de `DispositivoDetailView`: permisos, listado y modales de sumar y de alcance."""

    def _permisos_equipo(self, dispositivo):
        """``permisos_del_equipo`` de quien mira, resueltos una sola vez por request."""

        if not hasattr(self, "_permisos_del_equipo"):
            self._permisos_del_equipo = permisos_del_equipo(self.request.user, dispositivo)
        return self._permisos_del_equipo

    def _preparar_equipo(self, context, dispositivo):
        """Solapa «Equipo» (Cambio 411): la ve quien ve el dispositivo; arma quien lo gestiona.

        Los formularios de los modales se arman solo con su modal abierto, por URL: ``?tab=equipo&equipo=sumar``,
        ``?tab=equipo&equipo=alcance&miembro=<id>`` y ``?tab=infraestructura&agregar_persona=<edificio>`` (Cambio 523, PR 4).
        """

        permisos = self._permisos_equipo(dispositivo)
        miembros = equipo_del_dispositivo(dispositivo, permisos)
        if permisos.gestiona:
            url_detalle = reverse("dispositivos:detalle", args=[dispositivo.pk])
            for miembro in miembros:
                if miembro.puede_cambiar_alcance:
                    consulta = urlencode({"tab": "equipo", "equipo": "alcance", "miembro": miembro.pk})
                    miembro.url_cambiar_alcance = f"{url_detalle}?{consulta}"
        context["equipo"] = miembros
        context["n_equipo"] = len(miembros)
        context["puede_gestionar_equipo"] = permisos.gestiona
        if not permisos.gestiona:
            return
        pedido = self.request.GET.get("equipo")
        agregar = self.request.GET.get("agregar_persona")
        # Las opciones (consultas sobre usuarios y roles) se leen solo con un modal abierto: el detalle de siempre
        # sigue costando lo mismo.
        if pedido == "sumar":
            context["tab"] = "equipo"
            self._modal_sumar_persona(context, dispositivo, permisos)
        elif pedido == "alcance":
            context["tab"] = "equipo"
            self._modal_alcance(context, dispositivo, miembros, permisos)
        elif agregar:
            self._modal_sumar_persona(context, dispositivo, permisos, edificio_pk=_entero(agregar), en_edificio=True)

    def _modal_sumar_persona(self, context, dispositivo, permisos, edificio_pk=None, en_edificio=False):
        user = self.request.user
        edificio = None
        if en_edificio:
            donde = edificios_donde_agregar_persona(user, dispositivo, permisos)
            edificio = Edificio.objects.filter(pk=edificio_pk, dispositivos=dispositivo).first()
            if edificio is None or (donde is not None and edificio.pk not in donde):
                messages.warning(self.request, "No se pueden agregar personas a ese edificio.")
                return
        # «Crear persona» (Cambio 420) es de quien además administra los usuarios de Dispositivos: el resto ve
        # el pedido al administrador, tanto en el aviso de «sin resultados» como bajo el buscador.
        puede_crear = puede_crear_persona(user, dispositivo, permisos.gestiona)
        context["puede_crear_persona"] = puede_crear
        opciones = None if edificio else opciones_de_alcance(user, dispositivo, permisos)
        initial = {"edificio_fijo": edificio.pk} if edificio else None
        url_sugerencias = reverse("dispositivos:equipo_personas_buscar", args=[dispositivo.pk])
        context["form_equipo"] = SumarMiembroEquipoForm(
            dispositivo=dispositivo,
            url_sugerencias=url_sugerencias + ("?incluir=1" if edificio else ""),
            sin_resultados=MENSAJE_EQUIPO_SIN_PERSONA if puede_crear else MENSAJE_EQUIPO_PEDIR_ALTA,
            auto_id="equipo_%s",
            opciones=opciones,
            edificio_fijo=edificio is not None,
            initial=initial,
        )
        context["url_equipo_sumar"] = reverse("dispositivos:equipo_sumar", args=[dispositivo.pk])
        context["edificio_fijo"] = edificio
        if puede_crear:
            context["form_crear_persona"] = CrearPersonaEquipoForm(
                roles=roles_para_crear_persona(user),
                auto_id="crear_persona_%s",
                opciones=opciones,
                edificio_fijo=edificio is not None,
                initial=initial,
            )
            context["url_equipo_crear_persona"] = reverse("dispositivos:equipo_crear_persona", args=[dispositivo.pk])
        else:
            context["mensaje_pedir_alta"] = MENSAJE_EQUIPO_PEDIR_ALTA

    def _modal_alcance(self, context, dispositivo, miembros, permisos):
        """«Cambiar alcance» de una fila del Equipo, solo si el servidor se lo va a aceptar a quien lo abre."""

        pk = _entero(self.request.GET.get("miembro"))
        miembro = next((m for m in miembros if m.pk == pk), None)
        if miembro is None or not miembro.puede_cambiar_alcance:
            messages.warning(self.request, "No se puede cambiar el alcance de esa persona.")
            return
        context["miembro_alcance"] = miembro
        context["form_alcance"] = AlcanceMiembroEquipoForm(
            opciones=opciones_de_alcance(self.request.user, dispositivo, permisos),
            miembro=miembro,
            auto_id="alcance_%s",
        )
        context["url_equipo_alcance"] = reverse("dispositivos:equipo_alcance", args=[dispositivo.pk, miembro.pk])
