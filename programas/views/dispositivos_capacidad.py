"""Alta y edición de la capacidad instalada: edificio, sectores y plazas (carril C5 · P5 y P19).

Las acciones que P5 ofrece en su encabezado («Nuevo sector», «+ Agregar plazas») y en el
de cada sector («Editar sector»), más el edificio de la solapa Infraestructura de P4/P19.
Todas mutan, así que son **solo POST con CSRF**; los modales que las disparan los abre un
parámetro GET sobre la pantalla que ya existe y los arma el servidor, que es la variante
del arquetipo Modal que P21 sentó y P5 ya usa para las acciones de una plaza.

Reparto de responsabilidades: la capacidad en el programa la exige el mixin; el alcance al
dispositivo, una compuerta acá, **antes** de mirar el sector, el edificio o el formulario
—si no, quien no opera el dispositivo recibiría 404 con un id inexistente y otra cosa con
uno ajeno, y podría distinguirlos—; y la regla de fondo vuelve a exigirla el servicio, que
relee con la fila bloqueada.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View

from programas.forms_dispositivos import (
    AgregarPlazasForm,
    EdificioForm,
    PlazaForm,
    SectorForm,
    VincularEdificioForm,
)
from programas.mixins_dispositivos import DispositivoProgramaPermissionMixin
from programas.models import Dispositivo, Edificio, Plaza, Sector
from programas.selectors.capacidad_dispositivo import edificios_vinculables
from programas.services.dispositivos import puede_operar_dispositivo
from programas.services.edificios import (
    CAP_EDITAR,
    crear_edificio,
    desvincular_edificio,
    editar_edificio,
    vincular_edificio,
)
from programas.services.plazas import agregar_plazas, crear_sector, editar_plaza, editar_sector
from programas.views.ajax_utils import ajax_redirect, errores_del_servicio, is_ajax, rechazar

#: Adónde vuelve cada familia de acciones. Las de sectores y plazas, al mapa (P5); las del
#: edificio, al detalle abierto en su solapa (P4/P19). Se arman con `reverse`: ningún
#: parámetro que llegue en el POST puede mandar al usuario afuera.
SOLAPA_INFRAESTRUCTURA = "infraestructura"


def _id_de_seleccion(valor):
    if not (valor.isascii() and valor.isdecimal()):
        raise Http404
    return int(valor)


def url_mapa_de_plazas(dispositivo_pk):
    return reverse("dispositivos:sectores", args=[dispositivo_pk])


def url_solapa_infraestructura(dispositivo_pk):
    return f"{reverse('dispositivos:detalle', args=[dispositivo_pk])}?tab={SOLAPA_INFRAESTRUCTURA}"


class _AccionDeCapacidadView(DispositivoProgramaPermissionMixin, View):
    """Base de las acciones de configuración: alcance, formulario, servicio y vuelta.

    Las subclases ponen el formulario (`construir_form`), qué hace el servicio (`ejecutar`)
    y el mensaje de éxito; todo lo demás —el 403 de alcance, el 400 con los errores del
    modal, el toast y el redirect— es el mismo para las siete.
    """

    capacidad_requerida = CAP_EDITAR
    http_method_names = ["post"]

    def volver(self, dispositivo):
        raise NotImplementedError

    def construir_form(self, request, dispositivo):
        """El formulario ya acotado al dispositivo, o ``None`` si la acción no pide datos."""

        return None

    def ejecutar(self, request, dispositivo, datos):
        raise NotImplementedError

    def mensaje(self, resultado):
        raise NotImplementedError

    def post(self, request, pk, **kwargs):
        dispositivo = get_object_or_404(Dispositivo.objects.select_related("tipo"), pk=pk)
        volver = self.volver(dispositivo)
        if not puede_operar_dispositivo(request.user, dispositivo, self.capacidad_requerida):
            if is_ajax(request):
                return JsonResponse({"ok": False, "message": "No tenés alcance sobre este dispositivo."}, status=403)
            raise PermissionDenied

        form = self.construir_form(request, dispositivo)
        if form is not None and not form.is_valid():
            return rechazar(request, form.errors, volver)
        try:
            resultado = self.ejecutar(request, dispositivo, form.cleaned_data if form else {})
        except PermissionDenied:
            if is_ajax(request):
                return JsonResponse({"ok": False, "message": "No tenés alcance sobre este dispositivo."}, status=403)
            raise
        except ValidationError as error:
            return rechazar(request, errores_del_servicio(error, form), volver)

        texto = self.mensaje(resultado)
        if is_ajax(request):
            return ajax_redirect(request, volver, texto)
        messages.success(request, texto)
        return redirect(volver)


# --------------------------------------------------------------------------- #
# Sectores y plazas (P5)
# --------------------------------------------------------------------------- #


class _AccionDeSectorView(_AccionDeCapacidadView):
    def volver(self, dispositivo):
        return url_mapa_de_plazas(dispositivo.pk)


def sector_del_dispositivo(dispositivo, sector_pk):
    """El sector, solo si es de ese dispositivo: uno ajeno da el mismo 404 que uno inexistente."""

    return get_object_or_404(Sector, pk=sector_pk, dispositivo=dispositivo)


class SectorCrearView(_AccionDeSectorView):
    """«Nuevo sector» del encabezado de P5."""

    def construir_form(self, request, dispositivo):
        return SectorForm(request.POST)

    def ejecutar(self, request, dispositivo, datos):
        return crear_sector(dispositivo=dispositivo, usuario=request.user, **datos)

    def mensaje(self, resultado):
        return f"Sector {resultado.nombre} creado."


class SectorEditarView(_AccionDeSectorView):
    """«Editar sector» del encabezado de cada sector de P5, incluida su baja.

    La baja no tiene acción propia: es el switch «Sector activo» del mismo formulario,
    porque es un estado del sector y no otra cosa. Quien la intenta con plazas tomadas
    recibe el motivo en ese campo, que es donde la decisión se toma.
    """

    def construir_form(self, request, dispositivo):
        self.sector = sector_del_dispositivo(dispositivo, self.kwargs["sector_pk"])
        return SectorForm(request.POST, sector=self.sector)

    def ejecutar(self, request, dispositivo, datos):
        return editar_sector(sector=self.sector, usuario=request.user, **datos)

    def mensaje(self, resultado):
        if not resultado.activo:
            return f"Sector {resultado.nombre} dado de baja."
        return f"Sector {resultado.nombre} actualizado."


class PlazasAgregarView(_AccionDeSectorView):
    """«+ Agregar plazas» del encabezado de P5: el lote, con su sector elegido en el modal."""

    def construir_form(self, request, dispositivo):
        if request.POST.get("sector"):
            get_object_or_404(Sector, pk=_id_de_seleccion(request.POST["sector"]), dispositivo=dispositivo, activo=True)
        return AgregarPlazasForm(
            request.POST,
            dispositivo=dispositivo,
            sectores=Sector.objects.filter(dispositivo=dispositivo, activo=True),
        )

    def ejecutar(self, request, dispositivo, datos):
        return agregar_plazas(
            sector=datos["sector"],
            usuario=request.user,
            cantidad=datos["cantidad"],
            tipo=datos["tipo"],
            prefijo=datos["prefijo"],
        )

    def mensaje(self, resultado):
        return f"{len(resultado)} plaza{'s' if len(resultado) > 1 else ''} agregada{'s' if len(resultado) > 1 else ''}."


class PlazaEditarView(_AccionDeSectorView):
    def construir_form(self, request, dispositivo):
        self.plaza = get_object_or_404(
            Plaza.objects.select_related("sector__dispositivo__tipo"),
            pk=self.kwargs["plaza_pk"],
            sector__dispositivo=dispositivo,
        )
        return PlazaForm(request.POST, dispositivo=dispositivo, plaza=self.plaza)

    def ejecutar(self, request, dispositivo, datos):
        return editar_plaza(plaza=self.plaza, usuario=request.user, **datos)

    def mensaje(self, resultado):
        return f"Plaza {resultado.codigo} actualizada."


# --------------------------------------------------------------------------- #
# Edificio (solapa Infraestructura de P4 · P19)
# --------------------------------------------------------------------------- #


class _AccionDeEdificioView(_AccionDeCapacidadView):
    def volver(self, dispositivo):
        return url_solapa_infraestructura(dispositivo.pk)


class EdificioCrearView(_AccionDeEdificioView):
    """Alta del inmueble desde la institución que lo ocupa: nace vinculado a ella."""

    def construir_form(self, request, dispositivo):
        return EdificioForm(request.POST)

    def ejecutar(self, request, dispositivo, datos):
        return crear_edificio(dispositivo=dispositivo, usuario=request.user, **datos)

    def mensaje(self, resultado):
        return f"Edificio {resultado.nombre} cargado."


class EdificioEditarView(_AccionDeEdificioView):
    """Corrección de los datos del inmueble. Si el predio es compartido, la ven las dos instituciones."""

    def construir_form(self, request, dispositivo):
        self.edificio = get_object_or_404(Edificio, pk=self.kwargs["edificio_pk"], dispositivos=dispositivo)
        return EdificioForm(request.POST, edificio=self.edificio)

    def ejecutar(self, request, dispositivo, datos):
        return editar_edificio(edificio=self.edificio, dispositivo=dispositivo, usuario=request.user, **datos)

    def mensaje(self, resultado):
        return f"Edificio {resultado.nombre} actualizado."


class EdificioVincularView(_AccionDeEdificioView):
    """Predio compartido: declarar que esta institución ocupa un edificio que ya existe."""

    def construir_form(self, request, dispositivo):
        edificios = edificios_vinculables(request.user, dispositivo)
        if request.POST.get("edificio"):
            get_object_or_404(edificios, pk=_id_de_seleccion(request.POST["edificio"]))
        return VincularEdificioForm(request.POST, edificios=edificios)

    def ejecutar(self, request, dispositivo, datos):
        return vincular_edificio(edificio=datos["edificio"], dispositivo=dispositivo, usuario=request.user)

    def mensaje(self, resultado):
        return f"Edificio {resultado.nombre} vinculado a esta institución."


class EdificioDesvincularView(_AccionDeEdificioView):
    """Deshace el vínculo. No borra el edificio ni sus relevamientos: son del inmueble."""

    def ejecutar(self, request, dispositivo, datos):
        edificio = get_object_or_404(Edificio, pk=self.kwargs["edificio_pk"], dispositivos=dispositivo)
        return desvincular_edificio(edificio=edificio, dispositivo=dispositivo, usuario=request.user)

    def mensaje(self, resultado):
        return f"Edificio {resultado.nombre} desvinculado de esta institución."
