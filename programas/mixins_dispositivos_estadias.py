"""Estadías de un dispositivo: las filas de la tabla y los modales de cambio y egreso armados por URL (Cambio 566).

Salió de `dispositivos_legajo` sin cambiar comportamiento, para que la ficha de la institución y la solapa Estadías de
la página del edificio compartan el armado. Vive **fuera de `programas/views/`** como `mixins_dispositivos_equipo`: una
vista que le pide algo a otra vista es lo que mide el ratchet de `programas/tests/test_arquitectura.py`.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode

from programas.forms_dinamicos import formulario_de_momento_para
from programas.forms_dispositivos import EgresoForm
from programas.mixins_dispositivos_sectores import _form_de_cambio_de_plaza
from programas.models import Estadia, MomentoFormulario
from programas.services.dispositivos import q_edificios_en_alcance
from programas.services.ingreso import maneja_plazas
from programas.services.sectores_plazas import se_puede_cambiar_plaza


def _estadia_del_dispositivo(dispositivo, estadia_pk, usuario, capacidad="dispositivo.ver", q_extra=None):
    """La estadía, solo si es de ese dispositivo y de un edificio alcanzado: un id ajeno da 404 (RN4)."""

    return get_object_or_404(
        Estadia.objects.select_related(
            "ciudadano", "dispositivo", "plaza__sector", "motivo", "ingresada_por", "egresada_por"
        )
        .filter(q_edificios_en_alcance(usuario, capacidad, "dispositivo_id", "plaza__sector__edificio_id"))
        .filter(q_extra if q_extra is not None else Q()),
        pk=estadia_pk,
        dispositivo=dispositivo,
    )


def formulario_de_egreso(dispositivo, data=None, files=None):
    """El formulario de «Egreso» que hoy pide el tipo del dispositivo, o ``None`` (sin formulario o dado de
    baja). Se arma **en el servidor** para la estadía del modal: P7 lo dibuja con la pantalla y P4 con el
    `?egreso=<id>` que abre ese modal, así que el tipo correcto llega sin un fetch por fila."""

    return formulario_de_momento_para(dispositivo.tipo_id, MomentoFormulario.EGRESO, data, files)


def preparar_filas_de_estadias(
    estadias,
    *,
    dispositivo,
    url_base,
    puede_ver_ciudadano,
    puede_cambiar,
    puede_egresar,
    con_plazas,
    plazas_elegibles,
):
    """Deja en cada estadía de la página lo que la fila dibuja: el nombre, el enlace a la estadía y sus acciones.

    La comparten la solapa Estadías de la ficha de la institución y la del edificio (Cambio 566). ``url_base`` es la
    página que abre el modal de cambio (``?tab=estadias&cambio=<id>``); ``plazas_elegibles`` es una función que
    devuelve el conjunto de plazas libres y solo se llama si alguna fila ofrece el cambio.
    """

    for estadia in estadias:
        estadia.persona_visible = estadia.ciudadano.apellido_nombre if puede_ver_ciudadano else "Persona alojada"
        estadia.persona_del_menu = estadia.persona_visible
        if not puede_ver_ciudadano:
            if estadia.plaza_id:
                ubicacion = f"{estadia.plaza.sector.nombre} · {estadia.plaza.codigo}"
                estadia.persona_del_menu += f" en {ubicacion}"
            else:
                ingreso = timezone.localtime(estadia.fecha_ingreso).strftime("%d/%m/%Y %H:%M")
                estadia.persona_del_menu += f" con ingreso {ingreso} · estadía N.º {estadia.pk}"
        if puede_ver_ciudadano:
            estadia.url_ver = reverse("dispositivos:estadia_detalle", args=[dispositivo.pk, estadia.pk])
        # Con plaza se ofrece «Cambiar plaza»; sin plaza, «Asignar plaza» (solo si el tipo
        # maneja plazas: si no, no hay a dónde asignar). El mapa se calcula una vez.
        estadia.asigna_plaza = estadia.plaza_id is None
        if puede_cambiar and estadia.activa and se_puede_cambiar_plaza(estadia, dispositivo, con_plazas=con_plazas):
            estadia.url_cambiar = f"{url_base}?{urlencode({'tab': 'estadias', 'cambio': estadia.pk})}"
            estadia.motivo_cambiar = "No hay plazas libres en el dispositivo." if not plazas_elegibles() else ""
    if puede_egresar:
        for estadia in estadias:
            if estadia.estado == Estadia.Estado.ACTIVA:
                estadia.url_egresar = reverse("dispositivos:egresar", args=[dispositivo.pk, estadia.pk])
                estadia.url_modal_egreso = f"{url_base}?{urlencode({'tab': 'estadias', 'egreso': estadia.pk})}"


def contexto_modales_de_estadia(
    request, dispositivo, *, puede_cambiar, puede_egresar, puede_ver_ciudadano, mapa_de_ingreso, q_alcance=None
):
    """El modal de cambio o de egreso que pide la URL (``?cambio=<id>`` o ``?egreso=<id>``): un solo modal, o ``{}``.

    Lo comparten la ficha de la institución y la página del edificio (Cambio 566). ``mapa_de_ingreso`` es una función
    que devuelve los sectores con plazas elegibles. Un parámetro sin capacidad da 403; un id ajeno, 404.
    """

    for parametro, autorizado in (("cambio", puede_cambiar), ("egreso", puede_egresar)):
        pedido = request.GET.get(parametro, "")
        if not pedido:
            continue
        if not autorizado:
            raise PermissionDenied
        # Un id ajeno, inexistente o no ASCII tiene la misma respuesta.
        estadia_pk = int(pedido) if pedido.isascii() and pedido.isdecimal() else None
        estadia = _estadia_del_dispositivo(dispositivo, estadia_pk, request.user, q_extra=q_alcance)
        estadia.persona_visible = estadia.ciudadano.apellido_nombre if puede_ver_ciudadano else "Persona alojada"
        if not estadia.activa:
            messages.info(request, "La estadía ya está cerrada.")
            continue
        if parametro == "cambio":
            # Sin plaza es «Asignar plaza»: el mismo modal, con el motivo opcional.
            if not se_puede_cambiar_plaza(estadia, dispositivo, con_plazas=maneja_plazas(dispositivo)):
                if estadia.plaza_id is not None:
                    messages.info(request, "No se puede cambiar de plaza: el dispositivo está cerrado.")
                continue
            form, url = _form_de_cambio_de_plaza(dispositivo, estadia, mapa_de_ingreso())
            if not form.hay_plazas_libres:
                messages.info(request, "No hay plazas libres en el dispositivo.")
                continue
            return {
                "form_cambio": form,
                "url_cambiar_plaza": url,
                "estadia_cambio": estadia,
                "es_asignacion": form.asigna,
                "tab": "estadias",
            }
        return {
            "estadia_egreso": estadia,
            "form_egreso": EgresoForm(estadia=estadia),
            "formulario_egreso": formulario_de_egreso(dispositivo),
            "url_egresar": reverse("dispositivos:egresar", args=[dispositivo.pk, estadia.pk]),
            "tab": "estadias",
        }
    return {}
