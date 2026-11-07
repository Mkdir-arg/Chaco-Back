"""Equipo de un dispositivo: las acciones de la solapa «Equipo» (Cambio 411).

Cada acción es un POST que re-verifica en el servidor: la vista exige ``puede_gestionar_equipo``
(admin de Dispositivos o responsable de **ese** dispositivo) antes de mirar nada más, y el
servicio (``equipo_dispositivo``) vuelve a exigirlo. El botón escondido no es una barrera.

«Crear persona» (Cambio 420) exige además administrar los usuarios del programa Dispositivos
(``puede_crear_persona``): sin eso, 403 aunque se pueda gestionar el Equipo.
"""

import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from core.http_cache import sin_cache
from core.services.throttle import rate_limit_excedido
from programas.forms_dispositivos import CrearPersonaEquipoForm, SumarMiembroEquipoForm
from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin
from programas.models import Dispositivo, MiembroEquipoDispositivo
from programas.selectors.equipo_sugeridas import sugerir_pares_equipo
from programas.services import equipo_dispositivo as equipo
from programas.views.ajax_utils import ajax_redirect, errores_del_servicio, is_ajax
from users.forms import MENSAJE_DNI_DUPLICADO
from users.services.correo import ENTREGA_LINK, entregar_credenciales_provisorias
from users.views.quick_create import MENSAJES_COLISION, MENSAJES_DNI_DUPLICADO, _campo_en_colision

logger = logging.getLogger(__name__)

#: Cubeta por operador (sin IP) del alta de personas desde el Equipo, como las del alta de agentes.
CUBETA_ALTA_PERSONA_EQUIPO = "equipo_alta_persona"
ALTAS_PERSONA_POR_MINUTO = 20


def url_solapa_equipo(dispositivo_pk):
    return f"{reverse('dispositivos:detalle', args=[dispositivo_pk])}?tab=equipo"


class _EquipoAccionView(DispositivoProgramaPermissionMixin, View):
    """Base: solo POST, con la compuerta de gestión antes de cualquier otra cosa."""

    capacidad_requerida = "dispositivo.ver"
    http_method_names = ["post"]
    mensaje_exito = ""

    def ejecutar(self, request, dispositivo, miembro):
        raise NotImplementedError

    #: El formulario del modal, si la acción lo tiene: dice a qué campo va cada error.
    form = None
    mensaje_sin_permiso = "Solo el admin de Dispositivos o un responsable arma el Equipo."

    def autorizado(self, request, dispositivo):
        return equipo.puede_gestionar_equipo(request.user, dispositivo)

    def post(self, request, pk, **kwargs):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        if not self.autorizado(request, dispositivo):
            if is_ajax(request):
                return JsonResponse({"ok": False, "message": self.mensaje_sin_permiso}, status=403)
            raise PermissionDenied
        volver = url_solapa_equipo(dispositivo.pk)
        try:
            self.ejecutar(request, dispositivo, kwargs)
        except PermissionDenied:
            raise
        except ValidationError as error:
            if is_ajax(request):
                return JsonResponse({"ok": False, "errors": errores_del_servicio(error, self.form)}, status=400)
            messages.error(request, error.messages[0])
            return redirect(volver)
        if is_ajax(request):
            return ajax_redirect(request, volver, self.mensaje_exito)
        messages.success(request, self.mensaje_exito)
        return redirect(volver)


class EquipoSumarView(_EquipoAccionView):
    mensaje_exito = "Persona sumada al Equipo."

    def ejecutar(self, request, dispositivo, kwargs):
        form = self.form = SumarMiembroEquipoForm(request.POST, dispositivo=dispositivo)
        if not form.is_valid():
            raise ValidationError({campo: list(mensajes) for campo, mensajes in form.errors.items()})
        usuario, rol = form.cleaned_data["persona_rol"]
        equipo.sumar_miembro(
            actor=request.user,
            dispositivo=dispositivo,
            usuario=usuario,
            rol=rol,
            es_responsable=form.cleaned_data["es_responsable"],
        )


class EquipoCrearPersonaView(_EquipoAccionView):
    """Crea a la persona que no estaba y la suma al Equipo, todo o nada (Cambio 420).

    La puerta es ``puede_crear_persona`` (403 antes de mirar el formulario). El usuario se crea con el
    formulario y el servicio del ABM de Usuarios; la clave llega por enlace al correo, ya con la
    transacción cerrada.
    """

    mensaje_exito = "Persona creada y sumada al Equipo."
    mensaje_sin_permiso = "Solo quien administra los usuarios de Dispositivos da de alta personas."

    def autorizado(self, request, dispositivo):
        return equipo.puede_crear_persona(request.user, dispositivo)

    def ejecutar(self, request, dispositivo, kwargs):
        if rate_limit_excedido(
            request,
            CUBETA_ALTA_PERSONA_EQUIPO,
            ALTAS_PERSONA_POR_MINUTO,
            sufijo=str(request.user.pk),
            incluir_ip=False,
        ):
            raise ValidationError("Hiciste muchas altas seguidas. Esperá un minuto y probá de nuevo.")
        form = self.form = CrearPersonaEquipoForm(request.POST, roles=equipo.roles_para_crear_persona(request.user))
        if not form.is_valid():
            raise ValidationError({campo: list(mensajes) for campo, mensajes in form.errors.items()})
        datos = form.cleaned_data
        alta = equipo.datos_de_alta_de_persona(
            actor=request.user,
            dni=datos["dni"],
            nombre=datos["first_name"],
            apellido=datos["last_name"],
            correo=datos["email"],
            rol=datos["rol"],
        )
        if not alta.is_valid():
            raise ValidationError(self._errores_del_alta(alta))
        try:
            usuario = equipo.crear_persona_y_sumar(
                actor=request.user,
                dispositivo=dispositivo,
                alta=alta,
                rol=datos["rol"],
                es_responsable=datos["es_responsable"],
            )
        except IntegrityError as error:
            # La carrera: dos altas con el mismo valor pasan la validación y la segunda choca con el índice único.
            campo = _campo_en_colision(error)
            logger.warning("Alta de persona desde el Equipo: colisión de unicidad (campo %s)", campo)
            raise ValidationError({"dni" if campo in ("dni", "username") else "__all__": MENSAJES_COLISION[campo]})
        aviso = self._entregar_clave(request, usuario, datos["rol"])
        self.mensaje_exito = f"Persona creada y sumada al Equipo. {aviso}"

    @staticmethod
    def _errores_del_alta(alta):
        """Los errores del formulario del ABM, en los campos de este modal."""

        errores = {}
        for campo, lista in alta.errors.items():
            mensajes = [str(error) for error in lista]
            destino = {"groups": "rol", "username": "dni"}.get(campo, campo)
            if campo == "dni":
                mensajes = [
                    MENSAJES_DNI_DUPLICADO["equipo"] if mensaje == MENSAJE_DNI_DUPLICADO else mensaje
                    for mensaje in mensajes
                ]
            if destino not in CrearPersonaEquipoForm.base_fields:
                destino = "__all__"
            errores.setdefault(destino, []).extend(mensajes)
        return errores

    @staticmethod
    def _entregar_clave(request, usuario, rol):
        try:
            modalidad = entregar_credenciales_provisorias(usuario, request, rol=rol.name)
        except Exception:
            logger.exception("La persona fue creada, pero no se pudo enviar el correo con la clave")
            return 'No se pudo enviar el correo: puede entrar con "Olvidé mi contraseña".'
        if modalidad == ENTREGA_LINK:
            return "Se envió el correo con el enlace para definir la contraseña."
        return "Se envió el correo con la clave provisoria."


class EquipoPersonasSugeridasView(DispositivoProgramaPermissionMixin, View):
    """Sugiere «Persona — Rol» mientras se escribe en «Sumar persona» (Cambio 420). Solo lectura, solo JSON.

    Pide lo mismo que sumar: ``puede_gestionar_equipo`` de **este** dispositivo (403 JSON si no). Sin
    correo, teléfono ni DNI. Sin registrar lo tecleado: es un nombre, dato personal.
    """

    capacidad_requerida = "dispositivo.ver"
    http_method_names = ["get"]

    def get(self, request, pk):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        if not equipo.puede_gestionar_equipo(request.user, dispositivo):
            return sin_cache(
                JsonResponse({"ok": False, "message": "No tenés alcance para armar el Equipo."}, status=403)
            )
        return sin_cache(JsonResponse(sugerir_pares_equipo(dispositivo, request.GET.get("q", ""))))


class _EquipoMiembroView(_EquipoAccionView):
    """Una acción sobre una fila del Equipo; la fila tiene que ser de **este** dispositivo."""

    def servicio(self, **kwargs):
        raise NotImplementedError

    def ejecutar(self, request, dispositivo, kwargs):
        miembro = get_object_or_404(MiembroEquipoDispositivo, pk=kwargs["miembro_pk"], dispositivo=dispositivo)
        self.servicio(actor=request.user, miembro=miembro)


class EquipoBajaView(_EquipoMiembroView):
    mensaje_exito = "Persona dada de baja del Equipo."
    servicio = staticmethod(equipo.dar_de_baja)


class EquipoMarcarResponsableView(_EquipoMiembroView):
    mensaje_exito = "Persona marcada como responsable."
    servicio = staticmethod(equipo.marcar_responsable)


class EquipoDesmarcarResponsableView(_EquipoMiembroView):
    mensaje_exito = "La persona dejó de ser responsable."
    servicio = staticmethod(equipo.desmarcar_responsable)
