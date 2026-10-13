"""Vistas del legajo institucional de Dispositivos."""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.utils import IntegrityError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.rbac import puede
from programas.forms import DispositivoForm
from programas.forms_dispositivos import CambioPlazaForm, EgresoForm
from programas.mixins_dispositivos import (  # noqa: F401  (re-exportados: los importan otras vistas)
    DispositivoObjectPermissionMixin,
    DispositivoProgramaPermissionMixin,
)
from programas.models import Dispositivo, Estadia, TipoDispositivo
from programas.selectors.estadia_detalle import detalle_de_estadia
from programas.services.detalle_dispositivo import (
    aviso_sin_ingresos,
    contar_alojadas,
    estadias_del_dispositivo,
    eventos_de_historial,
    indicadores_de_plazas,
    normalizar_filtros,
    pildoras_de_estadias,
    sectores_del_censo,
)
from programas.services.dispositivos import (
    buscar_posibles_duplicados,
    cerrar_dispositivo,
    dispositivos_visibles,
    enviar_a_validacion,
    inactivar_dispositivo,
    observar_dispositivo,
    puede_en_programa_dispositivos,
    puede_operar_dispositivo,
    rechazar_dispositivo,
    registrar_alta_dispositivo,
    registrar_edicion_dispositivo,
    validar_dispositivo,
)
from programas.services.estadias import CAP_ADMITIR, CAP_EGRESAR, cambiar_plaza, egresar_persona
from programas.services.ingreso import maneja_plazas, plazas_para_ingresar
from programas.services.ocupacion import ocupacion_de_plazas
from programas.services.reportes import filtrar_dispositivos
from programas.services.sectores_plazas import sectores_con_plazas
from programas.views.ajax_utils import ajax_redirect, is_ajax


class DispositivoListView(DispositivoProgramaPermissionMixin, ListView):
    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/legajo/list.html"
    context_object_name = "dispositivos"

    def get_queryset(self):
        queryset = dispositivos_visibles(self.request.user).select_related("tipo")
        return filtrar_dispositivos(
            queryset,
            tipo=self.request.GET.get("tipo"),
            estado=self.request.GET.get("estado"),
            localidad=self.request.GET.get("localidad", "").strip(),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["estados"] = Dispositivo.Estado.choices
        context["tipos"] = TipoDispositivo.objects.filter(activo=True).order_by("nombre")
        return context


class DispositivoCreateView(DispositivoProgramaPermissionMixin, CreateView):
    capacidad_requerida = "dispositivo.crear"
    model = Dispositivo
    form_class = DispositivoForm
    template_name = "programas/dispositivos/legajo/form.html"

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save()
                registrar_alta_dispositivo(self.object, self.request.user)
        except IntegrityError:
            form.add_error("codigo", "Ya existe un dispositivo con este código institucional.")
            return self.form_invalid(form)
        messages.success(self.request, "Dispositivo creado como borrador.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("dispositivos:detalle", args=[self.object.pk])


class DispositivoDuplicateSearchView(DispositivoProgramaPermissionMixin, View):
    capacidad_requerida = "dispositivo.crear"

    def get(self, request):
        resultado = buscar_posibles_duplicados(
            codigo=request.GET.get("codigo", ""),
            nombre=request.GET.get("nombre", ""),
            localidad=request.GET.get("localidad", ""),
        )
        coincidencias = resultado["dispositivos"]
        hay_coincidencias = resultado["codigo_duplicado"] or coincidencias.exists()
        if puede_en_programa_dispositivos(request.user, "dispositivo.ver"):
            coincidencias = coincidencias.filter(pk__in=dispositivos_visibles(request.user).values("pk"))
        else:
            coincidencias = Dispositivo.objects.none()
        return JsonResponse(
            {
                "codigo_duplicado": resultado["codigo_duplicado"],
                "hay_coincidencias": hay_coincidencias,
                "coincidencias": [
                    {
                        "codigo": dispositivo.codigo,
                        "nombre": dispositivo.nombre,
                        "localidad": dispositivo.localidad,
                        "estado": dispositivo.get_estado_display(),
                    }
                    for dispositivo in coincidencias
                ],
            }
        )


class DispositivoDetailView(DispositivoObjectPermissionMixin, DetailView):
    """Detalle del dispositivo (MVP v2, etapa 2 · P4): indicadores, sectores, estadías e historial.

    Las cifras de plazas salen del censo de `ocupacion_de_plazas` y el resto de los datos de
    `programas.services.detalle_dispositivo`: acá solo se orquesta y se resuelven permisos.
    """

    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/legajo/detail.html"
    context_object_name = "dispositivo"

    def get_queryset(self):
        return Dispositivo.objects.select_related("tipo")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dispositivo = self.object
        user = self.request.user
        get = self.request.GET

        # Una sola llamada al censo: la franja, el desglose por sector y el contador de la
        # solapa salen del mismo cálculo. La pantalla no deriva el estado de ninguna plaza.
        ocupacion = ocupacion_de_plazas(dispositivo).de(dispositivo)
        sectores = sectores_del_censo(ocupacion)
        estado, sector = normalizar_filtros(get.get("estado", ""), get.get("sector", ""), {s["pk"] for s in sectores})
        historial, eventos = eventos_de_historial(dispositivo, get.get("historial_page"))
        estadias = estadias_del_dispositivo(dispositivo, estado=estado, sector=sector, pagina=get.get("estadias_page"))
        puede_egresar = puede_operar_dispositivo(user, dispositivo, CAP_EGRESAR)
        if puede_egresar:
            for estadia in estadias:
                if estadia.estado == Estadia.Estado.ACTIVA:
                    estadia.url_egresar = reverse("dispositivos:egresar", args=[dispositivo.pk, estadia.pk])

        context.update(
            {
                "maneja_plazas": maneja_plazas(dispositivo),
                "aviso_sin_ingresos": aviso_sin_ingresos(dispositivo),
                "indicadores": indicadores_de_plazas(ocupacion.conteo),
                "sectores": sectores,
                "n_plazas": ocupacion.conteo.operativas,
                "n_alojadas": contar_alojadas(dispositivo),
                "estadias": estadias,
                "pildoras": pildoras_de_estadias(estado, sector, sectores),
                # La píldora es un <form method="get">: sin esto, filtrar perdería la solapa de la URL.
                "ocultos_estadias": [("tab", "estadias")],
                "hay_filtros_estadias": bool(estado or sector),
                "historial": historial,
                "eventos": eventos,
                "puede_editar": puede_operar_dispositivo(user, dispositivo, "dispositivo.editar"),
                "puede_validar": puede_operar_dispositivo(user, dispositivo, "dispositivo.validar"),
                "puede_admitir": puede_operar_dispositivo(user, dispositivo, "dispositivo.admitir"),
                "puede_ver_ciudadano": puede(user, "ciudadano.ver"),
                "puede_egresar": puede_egresar,
                "form_egreso": EgresoForm() if puede_egresar else None,
                "url_ingreso": reverse("dispositivos:ingreso_persona", args=[dispositivo.pk]),
                "url_sectores": reverse("dispositivos:sectores", args=[dispositivo.pk]),
            }
        )
        return context


class DispositivoUpdateView(DispositivoObjectPermissionMixin, UpdateView):
    capacidad_requerida = "dispositivo.editar"
    model = Dispositivo
    form_class = DispositivoForm
    template_name = "programas/dispositivos/legajo/form.html"
    context_object_name = "dispositivo"

    def get_object(self, queryset=None):
        dispositivo = super().get_object(queryset)
        if dispositivo.estado == Dispositivo.Estado.CERRADO:
            raise PermissionDenied
        return dispositivo

    def form_valid(self, form):
        with transaction.atomic():
            dispositivo = Dispositivo.objects.select_for_update().get(pk=self.object.pk)
            if dispositivo.estado == Dispositivo.Estado.CERRADO:
                raise PermissionDenied
            cambios = {
                field: {"anterior": getattr(dispositivo, field), "nuevo": form.cleaned_data[field]}
                for field in form.changed_data
            }
            for field in form.changed_data:
                setattr(dispositivo, field, form.cleaned_data[field])
            if cambios:
                dispositivo.save(update_fields=[*form.changed_data, "modificado"])
                registrar_edicion_dispositivo(dispositivo, self.request.user, cambios)
            self.object = dispositivo
        messages.success(self.request, "Dispositivo actualizado.")
        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse("dispositivos:detalle", args=[self.object.pk])


class DispositivoActionView(DispositivoProgramaPermissionMixin, View):
    accion = None

    def ejecutar(self, dispositivo, request):
        raise NotImplementedError

    def post(self, request, pk):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        if not puede_operar_dispositivo(request.user, dispositivo, self.capacidad_requerida):
            if is_ajax(request):
                return JsonResponse(
                    {"ok": False, "message": "No tenés permiso para realizar esta acción."},
                    status=403,
                )
            raise PermissionDenied
        try:
            self.ejecutar(dispositivo, request)
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, self.mensaje_exito)
        return redirect("dispositivos:detalle", pk=dispositivo.pk)


class DispositivoEnviarValidacionView(DispositivoActionView):
    capacidad_requerida = "dispositivo.editar"
    mensaje_exito = "Dispositivo enviado a validación."

    def ejecutar(self, dispositivo, request):
        enviar_a_validacion(dispositivo, request.user)


class DispositivoValidarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.validar"
    mensaje_exito = "Dispositivo validado y habilitado para admitir."

    def ejecutar(self, dispositivo, request):
        validar_dispositivo(dispositivo, request.user)


class DispositivoObservarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.validar"
    mensaje_exito = "Dispositivo observado."

    def ejecutar(self, dispositivo, request):
        observar_dispositivo(dispositivo, request.user, request.POST.get("motivo"))


class DispositivoRechazarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.validar"
    mensaje_exito = "Dispositivo rechazado."

    def ejecutar(self, dispositivo, request):
        rechazar_dispositivo(dispositivo, request.user, request.POST.get("motivo"))


class DispositivoInactivarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.editar"
    mensaje_exito = "Dispositivo inactivado."

    def ejecutar(self, dispositivo, request):
        inactivar_dispositivo(dispositivo, request.user)


class DispositivoCerrarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.editar"
    mensaje_exito = "Dispositivo cerrado."

    def ejecutar(self, dispositivo, request):
        cerrar_dispositivo(dispositivo, request.user)


class DispositivoSectoresView(DispositivoObjectPermissionMixin, DetailView):
    """«Sectores y plazas» (MVP v2, etapa 1 · P5): el mapa de plazas de cada sector."""

    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/sectores/sectores.html"
    context_object_name = "dispositivo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(sectores_con_plazas(self.object))
        context["migas"] = [
            {"label": "Dispositivos", "url": reverse("dispositivos:lista")},
            {"label": self.object.nombre, "url": reverse("dispositivos:detalle", args=[self.object.pk])},
            {"label": "Sectores y plazas", "url": ""},
        ]
        return context


# Egreso (MVP v2, etapa 2 · #691). El egreso muta estado: solo POST con CSRF. La regla de fondo
# vive en `programas.services.estadias.egresar_persona`; la vista traduce lo que el servicio
# rechaza a lo que el modal sabe mostrar. La disponibilidad de la plaza no se cuenta acá: la
# recalcula `programas.services.ocupacion`. La lista de personas y el modal viven en la solapa
# Estadías del detalle (P4): hay una sola lista de personas por dispositivo.

#: Valor del campo oculto `volver` con el que el modal de egreso de P7 pide volver a la estadía.
VOLVER_A_LA_ESTADIA = "estadia"


def url_solapa_estadias(dispositivo_pk):
    """El detalle del dispositivo abierto en la solapa Estadías."""

    return f"{reverse('dispositivos:detalle', args=[dispositivo_pk])}?tab=estadias"


class DispositivoEstadiasView(LoginRequiredMixin, View):
    """Compatibilidad: la lista de personas alojadas pasó a la solapa Estadías del detalle.

    No resuelve capacidades porque no muestra nada: el detalle hace las suyas.
    """

    def get(self, request, pk):
        return redirect(url_solapa_estadias(pk))


class EstadiaEgresarView(DispositivoProgramaPermissionMixin, View):
    """Registra el egreso. Solo POST: un GET no muta nada ni muestra nada."""

    capacidad_requerida = CAP_EGRESAR
    http_method_names = ["post"]

    def post(self, request, pk, estadia_pk):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        if not puede_operar_dispositivo(request.user, dispositivo, CAP_EGRESAR):
            raise PermissionDenied
        estadia = get_object_or_404(Estadia.objects.select_related("ciudadano"), pk=estadia_pk, dispositivo=dispositivo)
        volver = self._volver(request, dispositivo, estadia)

        form = EgresoForm(request.POST, estadia=estadia)
        if not form.is_valid():
            return self._rechazar(request, form.errors, volver)

        datos = form.cleaned_data
        try:
            egresar_persona(
                estadia=estadia,
                usuario=request.user,
                fecha_egreso=datos["fecha_egreso"],
                motivo=datos["observaciones"],
                motivo_egreso=datos["motivo"],
                destino=datos["destino"],
                pertenencias_devueltas=datos["pertenencias_devueltas"],
            )
        except ValidationError as error:
            return self._rechazar(request, self._errores_del_servicio(error, form), volver)

        mensaje = f"Egreso registrado: {estadia.ciudadano.nombre_completo}."
        if is_ajax(request):
            return ajax_redirect(request, volver, mensaje)
        messages.success(request, mensaje)
        return redirect(volver)

    @staticmethod
    def _volver(request, dispositivo, estadia):
        """A dónde vuelve el modal: P7 si lo pidió con `volver=estadia`, si no la solapa Estadías de P4.

        El destino lo arma el servidor con `reverse`: el campo es una **clave**, no una URL,
        así que ningún valor que llegue en el POST puede mandar al usuario afuera. Cualquier
        cosa que no sea `estadia` cae al destino de siempre.
        """

        if request.POST.get("volver") == VOLVER_A_LA_ESTADIA:
            return reverse("dispositivos:estadia_detalle", args=[dispositivo.pk, estadia.pk])
        return url_solapa_estadias(dispositivo.pk)

    @staticmethod
    def _errores_del_servicio(error, form):
        """Lo que el servicio rechaza, en la forma `{campo: [mensajes]}` del modal.

        Una clave que el formulario no tiene (p. ej. `estado`: la estadía ya estaba
        cerrada) va al error general, que es el único lugar donde el modal la puede mostrar.
        """

        errores = {}
        for campo, mensajes in error.message_dict.items():
            destino = campo if campo in form.fields else "__all__"
            errores.setdefault(destino, []).extend(mensajes)
        return errores

    @staticmethod
    def _rechazar(request, errores, volver):
        if is_ajax(request):
            return JsonResponse({"ok": False, "errors": {k: list(v) for k, v in errores.items()}}, status=400)
        for mensajes in errores.values():
            for mensaje in mensajes:
                messages.error(request, mensaje)
        return redirect(volver)


# Detalle de la estadía (MVP v2, etapa 3 · #698 · P7). La persona alojada con su plaza, su
# línea de tiempo y las dos acciones que la mueven: cambiar de plaza y egresar.
CAP_VER_CIUDADANO = "ciudadano.ver"
#: Movimientos por página en la solapa Movimientos.
MOVIMIENTOS_POR_PAGINA = 25
#: Los dos formularios de P7 tienen un campo `motivo`: con el `id_%s` de Django los dos
#: controles saldrían con `id="id_motivo"` y el label del segundo apuntaría al primero.
AUTO_ID_CAMBIO = "cambio_%s"


def _estadia_del_dispositivo(dispositivo, estadia_pk):
    """La estadía, solo si es de ese dispositivo: un id de otro da 404, nunca la estadía ajena."""

    return get_object_or_404(
        Estadia.objects.select_related(
            "ciudadano", "dispositivo", "plaza__sector", "motivo", "ingresada_por", "egresada_por"
        ),
        pk=estadia_pk,
        dispositivo=dispositivo,
    )


def _sectores_para_cambio(estadia):
    """Las plazas del dispositivo con su estado, de `ocupacion.estado_de_plazas` (vía el asistente de ingreso).

    Es la misma fuente que el mapa y que el ingreso: acá no se decide qué es una plaza libre.
    """

    sectores, _elegibles = plazas_para_ingresar(estadia.dispositivo)
    return sectores


class EstadiaDetalleView(DispositivoObjectPermissionMixin, DetailView):
    """La estadía de una persona (P7): identidad, plaza, línea de tiempo y acciones.

    Qué la habilita: `dispositivo.ver` con alcance de programa **y** asignación al
    dispositivo (el mismo mixin que el detalle del dispositivo) **y** `ciudadano.ver`. La
    pantalla muestra nombre, DNI y la historia de una persona: sin `ciudadano.ver` se
    responde 403 **antes** de buscar la estadía, para que probar ids no diga cuáles
    existen (la regla que sentó la solapa del legajo, #697).
    """

    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/estadia/detalle.html"
    context_object_name = "dispositivo"

    def get_object(self, queryset=None):
        dispositivo = super().get_object(queryset)
        if not puede(self.request.user, CAP_VER_CIUDADANO):
            raise PermissionDenied
        self.estadia = _estadia_del_dispositivo(dispositivo, self.kwargs["estadia_pk"])
        return dispositivo

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dispositivo, estadia, usuario = self.object, self.estadia, self.request.user
        datos = detalle_de_estadia(estadia)
        context.update(datos)

        context["movimientos_page"] = Paginator(datos["movimientos"], MOVIMIENTOS_POR_PAGINA).get_page(
            self.request.GET.get("movimientos_page")
        )
        url_volver = url_solapa_estadias(dispositivo.pk)
        context["url_volver"] = url_volver
        context["url_legajo"] = reverse("legajos:ciudadano_detalle", args=[estadia.ciudadano_id])
        context["url_trayectoria"] = reverse("legajos:dispositivos_ciudadano", args=[estadia.ciudadano_id])
        context["migas"] = [
            {"label": "Dispositivos", "url": reverse("dispositivos:lista")},
            {"label": dispositivo.nombre, "url": reverse("dispositivos:detalle", args=[dispositivo.pk])},
            {"label": "Estadías", "url": url_volver},
            {"label": datos["persona"]["nombre_completo"], "url": ""},
        ]

        # Las acciones solo sobre una estadía abierta, y cada una con la capacidad que exige
        # su servicio: el botón no se ofrece a quien el servicio va a rechazar. Cambiar de
        # plaza supone tener una: una estadía sin plaza (tipo que no las identifica) no la ofrece.
        abierta = estadia.activa
        context["puede_cambiar_plaza"] = (
            abierta and estadia.plaza_id is not None and puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR)
        )
        context["puede_egresar"] = abierta and puede_operar_dispositivo(usuario, dispositivo, CAP_EGRESAR)
        if context["puede_cambiar_plaza"]:
            form_cambio = CambioPlazaForm(
                estadia=estadia, sectores=_sectores_para_cambio(estadia), auto_id=AUTO_ID_CAMBIO
            )
            # Sin plazas libres no se ofrece: el modal no tendría a dónde mover a nadie.
            context["puede_cambiar_plaza"] = form_cambio.hay_plazas_libres
            context["form_cambio"] = form_cambio
            context["url_cambiar_plaza"] = reverse("dispositivos:cambiar_plaza", args=[dispositivo.pk, estadia.pk])
        if context["puede_egresar"]:
            context["form_egreso"] = EgresoForm(estadia=estadia)
            context["url_egresar"] = reverse("dispositivos:egresar", args=[dispositivo.pk, estadia.pk])
        return context


class EstadiaCambiarPlazaView(DispositivoProgramaPermissionMixin, View):
    """Mueve a la persona a otra plaza del dispositivo. Solo POST, con CSRF.

    La regla vive en `programas.services.estadias.cambiar_plaza`, que exige
    `dispositivo.admitir` con alcance, bloquea la plaza y la estadía y registra el
    movimiento. La vista valida lo que el operador puede corregir sin salir del modal y
    traduce lo que el servicio rechaza al formato del modal, igual que el egreso.
    """

    capacidad_requerida = CAP_ADMITIR
    http_method_names = ["post"]

    def post(self, request, pk, estadia_pk):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        if not puede_operar_dispositivo(request.user, dispositivo, CAP_ADMITIR):
            raise PermissionDenied
        estadia = _estadia_del_dispositivo(dispositivo, estadia_pk)
        volver = reverse("dispositivos:estadia_detalle", args=[dispositivo.pk, estadia.pk])

        form = CambioPlazaForm(
            request.POST, estadia=estadia, sectores=_sectores_para_cambio(estadia), auto_id=AUTO_ID_CAMBIO
        )
        if not form.is_valid():
            return EstadiaEgresarView._rechazar(request, form.errors, volver)

        datos = form.cleaned_data
        try:
            movimiento = cambiar_plaza(
                estadia=estadia,
                plaza=datos["plaza"],
                usuario=request.user,
                motivo=datos["motivo"],
                momento=datos["momento"],
            )
        except ValidationError as error:
            return EstadiaEgresarView._rechazar(request, EstadiaEgresarView._errores_del_servicio(error, form), volver)

        mensaje = f"Cambio de plaza registrado: {movimiento.plaza_destino.codigo}."
        if is_ajax(request):
            return ajax_redirect(request, volver, mensaje)
        messages.success(request, mensaje)
        return redirect(volver)
