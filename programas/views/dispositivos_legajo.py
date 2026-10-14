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
from django.utils.http import urlencode
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.rbac import puede
from programas.forms import DispositivoForm
from programas.forms_dispositivos import (
    AgregarPlazasForm,
    CambioPlazaForm,
    EdificioForm,
    EgresoForm,
    LiberarPlazaForm,
    PlazaForm,
    SacarPlazaDeServicioForm,
    SectorForm,
    VincularEdificioForm,
)
from programas.mixins_dispositivos import (  # noqa: F401  (re-exportados: los importan otras vistas)
    DispositivoObjectPermissionMixin,
    DispositivoProgramaPermissionMixin,
)
from programas.models import Dispositivo, Edificio, Estadia, Plaza, Sector, TipoDispositivo
from programas.selectors.capacidad_dispositivo import edificios_vinculables
from programas.selectors.estadia_detalle import (
    detalle_de_estadia,
    novedades_de_estadia,
)
from programas.selectors.estadia_detalle import (
    normalizar_solapa as normalizar_solapa_estadia,
)
from programas.services.detalle_dispositivo import (
    alertas_del_dispositivo,
    aviso_sin_ingresos,
    contar_alojadas,
    estadias_del_dispositivo,
    eventos_de_historial,
    indicadores_de_plazas,
    infraestructura_del_dispositivo,
    normalizar_filtros,
    normalizar_solapa,
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
from programas.services.estadias import (
    CAP_ADMITIR,
    CAP_EDITAR,
    CAP_EGRESAR,
    cambiar_plaza,
    egresar_persona,
    liberar_reserva,
    reserva_abierta_de,
    sacar_plaza_de_servicio,
    volver_plaza_a_servicio,
)
from programas.services.ingreso import maneja_plazas, plazas_para_ingresar
from programas.services.inspecciones import semaforos_de_dispositivos
from programas.services.ocupacion import ocupacion_de_plazas, tension_de_ocupacion
from programas.services.reportes import filtrar_dispositivos
from programas.services.sectores_plazas import (
    ACCION_FUERA_SERVICIO,
    ACCION_LIBERAR,
    ACCION_VOLVER,
    plaza_para_accion,
    sectores_con_plazas,
)
from programas.views.ajax_utils import ajax_redirect, is_ajax


class DispositivoListView(DispositivoProgramaPermissionMixin, ListView):
    """P2 · Listado de instituciones (MVP v2, etapa 4).

    Pagina de a 25: sin eso la puerta de entrada del programa materializaba el padrón
    entero y pagaba el semáforo y las plazas de todas las filas en cada visita. El
    semáforo edilicio y la ocupación se calculan **una vez por página** —tres consultas
    cada uno, no una por fila— y el template solo dibuja lo que el servicio decidió.
    """

    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/legajo/list.html"
    context_object_name = "dispositivos"
    paginate_by = 25

    def _filtros(self):
        return {
            "tipo": self.request.GET.get("tipo", ""),
            "estado": self.request.GET.get("estado", ""),
            "localidad": self.request.GET.get("localidad", "").strip(),
        }

    def get_queryset(self):
        queryset = dispositivos_visibles(self.request.user).select_related("tipo")
        # `nombre` solo —el orden del modelo— no alcanza para paginar: dos instituciones
        # homónimas pueden repetirse o perderse entre páginas según el plan del motor.
        # `codigo` es único, así que con él el orden queda total.
        return filtrar_dispositivos(queryset, **self._filtros()).order_by("nombre", "codigo")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filtros = self._filtros()
        context["estados"] = Dispositivo.Estado.choices
        context["estado_actual"] = filtros["estado"]
        context["tipos"] = TipoDispositivo.objects.filter(activo=True).order_by("nombre")
        context["tipo_actual"] = filtros["tipo"]
        context["localidad_actual"] = filtros["localidad"]
        puede_crear = puede_en_programa_dispositivos(self.request.user, "dispositivo.crear")
        context["puede_crear"] = puede_crear
        # Sin `dispositivo.crear` el estado vacío no ofrece el alta: el botón llevaría a un
        # 403, y el alcance vacío de quien solo consulta no se resuelve dando de alta.
        context["url_crear"] = reverse("dispositivos:crear") if puede_crear else ""
        context["url_sin_filtros"] = reverse("dispositivos:lista")
        # La exportación lleva los filtros y **no** la página: exporta el padrón filtrado
        # entero, no los 25 que se están mirando.
        context["exportar_qs"] = urlencode({clave: valor for clave, valor in filtros.items() if valor})
        # Semáforo edilicio y plazas de **la página**, cada uno en tres consultas fijas y
        # no una por fila. Texto, tono y nivel los deciden los servicios; el template solo
        # dibuja el badge.
        dispositivos = list(context["dispositivos"])
        ids = [dispositivo.pk for dispositivo in dispositivos]
        semaforos = semaforos_de_dispositivos(ids)
        censo = ocupacion_de_plazas(ids)
        for dispositivo in dispositivos:
            dispositivo.semaforo = semaforos[dispositivo.pk]
            dispositivo.plazas = tension_de_ocupacion(censo.de(dispositivo).conteo, tipo=dispositivo.tipo)
        context["dispositivos"] = context["object_list"] = dispositivos
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
    """Detalle del dispositivo (MVP v2, etapa 2 · P4): indicadores, sectores, estadías, infraestructura e historial.

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
        historial, eventos = eventos_de_historial(dispositivo, get.get("historial_page"), user)
        estadias = estadias_del_dispositivo(dispositivo, estado=estado, sector=sector, pagina=get.get("estadias_page"))
        puede_egresar = puede_operar_dispositivo(user, dispositivo, CAP_EGRESAR)
        puede_cambiar = puede_operar_dispositivo(user, dispositivo, CAP_ADMITIR)
        puede_ver_ciudadano = puede(user, "ciudadano.ver")
        for estadia in estadias:
            if puede_ver_ciudadano:
                estadia.url_ver = reverse("dispositivos:estadia_detalle", args=[dispositivo.pk, estadia.pk])
            if puede_cambiar and estadia.activa and estadia.plaza_id is not None:
                estadia.url_cambiar = f"{self.request.path}?{urlencode({'tab': 'estadias', 'cambio': estadia.pk})}"
                estadia.motivo_cambiar = (
                    "No hay plazas libres en el dispositivo." if not ocupacion.conteo.disponibles else ""
                )
        if puede_egresar:
            for estadia in estadias:
                if estadia.estado == Estadia.Estado.ACTIVA:
                    estadia.url_egresar = reverse("dispositivos:egresar", args=[dispositivo.pk, estadia.pk])
                    estadia.url_modal_egreso = (
                        f"{self.request.path}?{urlencode({'tab': 'estadias', 'egreso': estadia.pk})}"
                    )

        con_plazas = maneja_plazas(dispositivo)
        context.update(
            {
                "maneja_plazas": con_plazas,
                # La solapa abierta la resuelve el servidor y se la pasa a Alpine: una
                # pedida que este dispositivo no tiene dejaba la tarjeta en blanco.
                "tab": normalizar_solapa(get.get("tab", ""), con_plazas=con_plazas),
                "aviso_sin_ingresos": aviso_sin_ingresos(dispositivo),
                # Avisan y no bloquean: ninguna decide si un botón aparece o una acción
                # procede. Son las mismas para todos; lo que depende de quién mira es el
                # enlace de resolución, porque la pantalla de destino tiene su capacidad.
                "alertas": alertas_del_dispositivo(dispositivo, usuario=user),
                "indicadores": indicadores_de_plazas(ocupacion.conteo, tipo=dispositivo.tipo),
                "sectores": sectores,
                "n_plazas": ocupacion.conteo.totales,
                "n_alojadas": contar_alojadas(dispositivo),
                "estadias": estadias,
                "pildoras": pildoras_de_estadias(estado, sector, sectores),
                # La píldora es un <form method="get">: sin esto, filtrar perdería la solapa de la URL.
                "ocultos_estadias": [("tab", "estadias")],
                "hay_filtros_estadias": bool(estado or sector),
                "historial": historial,
                "eventos": eventos,
                # `user` y no solo el dispositivo: el nombre del agente de un relevamiento en
                # curso no lo ve la institución relevada (`inspecciones.ve_la_asignacion`).
                "infraestructura": infraestructura_del_dispositivo(
                    dispositivo, get.get("relevamientos_page"), usuario=user
                ),
                "puede_editar": puede_operar_dispositivo(user, dispositivo, "dispositivo.editar"),
                "puede_validar": puede_operar_dispositivo(user, dispositivo, "dispositivo.validar"),
                "puede_admitir": puede_operar_dispositivo(user, dispositivo, "dispositivo.admitir"),
                "puede_ver_ciudadano": puede_ver_ciudadano,
                "puede_egresar": puede_egresar,
                "url_ingreso": reverse("dispositivos:ingreso_persona", args=[dispositivo.pk]),
                "url_sectores": reverse("dispositivos:sectores", args=[dispositivo.pk]),
            }
        )
        self._preparar_modales_de_estadia(context, dispositivo, puede_cambiar, puede_egresar)
        self._preparar_modales_de_edificio(context, dispositivo, context["puede_editar"])
        return context

    def _preparar_modales_de_estadia(self, context, dispositivo, puede_cambiar, puede_egresar):
        """Un solo modal abierto por URL, sin formularios ni consultas por fila (contrato P21)."""

        for parametro, autorizado in (("cambio", puede_cambiar), ("egreso", puede_egresar)):
            pedido = self.request.GET.get(parametro, "")
            if not pedido:
                continue
            if not autorizado:
                raise PermissionDenied
            # Un id ajeno, inexistente o no ASCII tiene la misma respuesta.
            estadia_pk = int(pedido) if pedido.isascii() and pedido.isdecimal() else None
            estadia = _estadia_del_dispositivo(dispositivo, estadia_pk)
            if not estadia.activa:
                messages.info(self.request, "La estadía ya está cerrada.")
                continue
            if parametro == "cambio":
                if estadia.plaza_id is None:
                    continue
                sectores, _ = plazas_para_ingresar(dispositivo)
                form = CambioPlazaForm(estadia=estadia, sectores=sectores, auto_id=AUTO_ID_CAMBIO)
                if not form.hay_plazas_libres:
                    messages.info(self.request, "No hay plazas libres en el dispositivo.")
                    continue
                context["form_cambio"] = form
                context["url_cambiar_plaza"] = reverse("dispositivos:cambiar_plaza", args=[dispositivo.pk, estadia.pk])
                context["estadia_cambio"] = estadia
            else:
                context["estadia_egreso"] = estadia
                context["form_egreso"] = EgresoForm(estadia=estadia)
                context["url_egresar"] = reverse("dispositivos:egresar", args=[dispositivo.pk, estadia.pk])
            context["tab"] = "estadias"
            break

    def _preparar_modales_de_edificio(self, context, dispositivo, puede_editar):
        """El alta, la edición y la vinculación del edificio de la solapa Infraestructura (P19).

        Se abren con `?tab=infraestructura&edificio=nuevo|<id>|vincular`. Ninguno cuesta
        nada mientras esté cerrado: el selector de edificios vinculables y la ficha del que
        se edita se leen **solo** con su modal abierto, así que el detalle de siempre sigue
        costando lo mismo.
        """

        if not puede_editar:
            return
        pedido = self.request.GET.get("edificio", "")
        if pedido == "nuevo":
            context["form_edificio"] = EdificioForm()
            context["url_edificio"] = reverse("dispositivos:edificio_crear", args=[dispositivo.pk])
        elif pedido == "vincular":
            vinculables = edificios_vinculables(self.request.user, dispositivo)
            # Se pregunta antes de armar el modal: un combo vacío sería un callejón sin
            # salida y quien lo abrió no sabría por qué. Son dos consultas —`ModelChoiceField`
            # recorre su queryset con `iterator()` y no reusa esta caché, como ya pasa en el
            # «Nuevo relevamiento» de P21—, y se pagan solo con el modal abierto.
            if not vinculables.exists():
                messages.info(
                    self.request,
                    "No hay ningún edificio de tu alcance que esta institución todavía no ocupe: "
                    "cargá el inmueble con «Cargar edificio».",
                )
                return
            context["form_vincular"] = VincularEdificioForm(edificios=vinculables)
            context["url_vincular"] = reverse("dispositivos:edificio_vincular", args=[dispositivo.pk])
        elif pedido:
            pk = _entero(pedido)
            # Acotado al dispositivo: el edificio de otra institución y el inexistente dan
            # lo mismo, que es lo que el servicio vuelve a exigir al guardar.
            edificio = Edificio.objects.filter(pk=pk, dispositivos=dispositivo).first() if pk is not None else None
            if edificio is None:
                messages.warning(self.request, "Ese edificio ya no se puede editar desde acá.")
            else:
                context["edificio_en_edicion"] = edificio
                context["form_edificio"] = EdificioForm(edificio=edificio)
                context["url_edificio"] = reverse("dispositivos:edificio_editar", args=[dispositivo.pk, edificio.pk])


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


def errores_por_campo(error, campos):
    """Lo que un servicio rechaza, en la forma `{campo: [mensajes]}` del arquetipo Modal.

    Una clave que el modal no dibuja —o un `ValidationError` sin campo— va al error
    general (`__all__`), que es el único lugar donde se puede mostrar sin perderla.
    """

    if not hasattr(error, "error_dict"):
        return {"__all__": list(error.messages)}
    errores = {}
    for campo, mensajes in error.message_dict.items():
        errores.setdefault(campo if campo in campos else "__all__", []).extend(mensajes)
    return errores


class DispositivoActionView(DispositivoProgramaPermissionMixin, View):
    """Una acción del encabezado de P4. Solo POST; la regla vive en el servicio.

    Las que piden un motivo (Observar, Rechazar) se envían desde un modal con `data-ajax`,
    así que responden el contrato JSON del arquetipo: `{ok, redirect}` al guardar y, si el
    servicio rechaza, **400 con el error en su campo** —`data-error="motivo"`— en vez de un
    toast después de recargar la pantalla. Sin JS el formulario postea igual y el error
    vuelve como mensaje: la vista no depende de que haya fetch.
    """

    accion = None
    #: Los campos que el modal de la acción dibuja y puede marcar con `data-error`.
    campos_del_modal = ()

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
        volver = reverse("dispositivos:detalle", args=[dispositivo.pk])
        try:
            self.ejecutar(dispositivo, request)
        except ValidationError as error:
            if is_ajax(request):
                errores = errores_por_campo(error, self.campos_del_modal)
                return JsonResponse({"ok": False, "errors": errores}, status=400)
            messages.error(request, error.messages[0])
            return redirect(volver)
        if is_ajax(request):
            return ajax_redirect(request, volver, self.mensaje_exito)
        messages.success(request, self.mensaje_exito)
        return redirect(volver)


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
    campos_del_modal = ("motivo",)

    def ejecutar(self, dispositivo, request):
        observar_dispositivo(dispositivo, request.user, request.POST.get("motivo"))


class DispositivoRechazarView(DispositivoActionView):
    capacidad_requerida = "dispositivo.validar"
    mensaje_exito = "Dispositivo rechazado."
    campos_del_modal = ("motivo",)

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


def _entero(valor):
    """El id de un parámetro GET, o `None`. Solo dígitos ASCII: un superíndice o un dígito
    arábigo pasan `isdigit()` y rompen `int()`."""

    valor = (valor or "").strip()
    return int(valor) if valor.isascii() and valor.isdecimal() else None


class DispositivoSectoresView(DispositivoObjectPermissionMixin, DetailView):
    """«Sectores y plazas» (MVP v2, etapas 1 y 5 · P5): el mapa de plazas y sus acciones.

    El modal de la acción se abre con `?plaza=<id>` y lo arma el servidor, como los de P21:
    el contenido depende del estado de esa plaza y la celda del mapa solo sabe navegar. Si
    la plaza no se puede gestionar —ajena, inexistente, de un sector dado de baja o sin la
    capacidad— el modal no se abre y el aviso es el mismo para los cuatro casos.

    Los tres modales de configuración del carril C5 —«Nuevo sector», «Editar sector» y
    «+ Agregar plazas»— se abren igual, con `?sector=nuevo`, `?sector=<id>` y `?plazas=1`,
    y **solo** si quien mira puede configurar las plazas: sin eso, el formulario llegaría
    armado a quien la acción va a rechazar. Lo que cuestan se paga únicamente con el modal
    abierto; el mapa cerrado sigue en las consultas fijas de su presupuesto.
    """

    capacidad_requerida = "dispositivo.ver"
    model = Dispositivo
    template_name = "programas/dispositivos/sectores/sectores.html"
    context_object_name = "dispositivo"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dispositivo = self.object
        usuario = self.request.user
        puede_liberar = puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR)
        puede_configurar_plazas = puede_operar_dispositivo(usuario, dispositivo, CAP_EDITAR)

        context.update(
            sectores_con_plazas(
                dispositivo,
                puede_liberar=puede_liberar,
                puede_configurar_plazas=puede_configurar_plazas,
                puede_ver_personas=puede(usuario, "ciudadano.ver"),
            )
        )
        context["migas"] = [
            {"label": "Dispositivos", "url": reverse("dispositivos:lista")},
            {"label": dispositivo.nombre, "url": reverse("dispositivos:detalle", args=[dispositivo.pk])},
            {"label": "Sectores y plazas", "url": ""},
        ]
        context["puede_configurar_plazas"] = puede_configurar_plazas
        self._preparar_modal(context, dispositivo, puede_liberar, puede_configurar_plazas)
        self._preparar_modales_de_configuracion(context, dispositivo, puede_configurar_plazas)
        return context

    def _preparar_modales_de_configuracion(self, context, dispositivo, puede_configurar_plazas):
        """«Nuevo sector», «Editar sector» y «+ Agregar plazas»: cuál abrir y con qué formulario.

        Un sector ajeno, inexistente o dado de baja no abre nada y avisa lo mismo que una
        plaza no gestionable: tres respuestas distintas serían un oráculo de ids. El sector
        dado de baja entra igual —se edita para reactivarlo—, lo que no abre es el que no
        es de este dispositivo.
        """

        if not puede_configurar_plazas:
            return
        pedido = self.request.GET.get("sector", "")
        if pedido == "nuevo":
            context["form_sector"] = SectorForm()
            context["url_sector"] = reverse("dispositivos:sector_crear", args=[dispositivo.pk])
        elif pedido:
            pk = _entero(pedido)
            sector = Sector.objects.filter(pk=pk, dispositivo=dispositivo).first() if pk is not None else None
            if sector is None:
                messages.warning(self.request, "Ese sector ya no se puede editar desde acá.")
            else:
                context["sector_en_edicion"] = sector
                context["form_sector"] = SectorForm(sector=sector)
                context["url_sector"] = reverse("dispositivos:sector_editar", args=[dispositivo.pk, sector.pk])

        if self.request.GET.get("plazas"):
            context["form_plazas"] = AgregarPlazasForm(
                dispositivo=dispositivo,
                sectores=Sector.objects.filter(dispositivo=dispositivo, activo=True),
            )
            context["url_plazas"] = reverse("dispositivos:plazas_agregar", args=[dispositivo.pk])
            pk = _entero(self.request.GET.get("plazas", ""))
            if pk is not None:
                context["form_plazas"].initial["sector"] = pk

        pedido = self.request.GET.get("editar_plaza", "")
        if pedido:
            pk = _entero(pedido)
            plaza = Plaza.objects.filter(pk=pk, sector__dispositivo=dispositivo).first() if pk is not None else None
            if plaza is None:
                messages.warning(self.request, "Esa plaza ya no se puede editar desde acá.")
            else:
                context["plaza_en_edicion"] = plaza
                context["form_editar_plaza"] = PlazaForm(dispositivo=dispositivo, plaza=plaza)
                context["url_editar_plaza"] = reverse("dispositivos:plaza_editar", args=[dispositivo.pk, plaza.pk])

    def _preparar_modal(self, context, dispositivo, puede_liberar, puede_configurar_plazas):
        pedida = self.request.GET.get("plaza", "")
        if not pedida:
            return
        pk = _entero(pedida)
        accion = (
            plaza_para_accion(
                dispositivo, pk, puede_liberar=puede_liberar, puede_configurar_plazas=puede_configurar_plazas
            )
            if pk is not None
            else None
        )
        if accion is None:
            messages.warning(self.request, "Esa plaza ya no se puede gestionar desde acá.")
            return
        plaza = accion["plaza"]
        context["plaza_accion"] = accion
        context["url_plaza_accion"] = reverse(URL_DE_ACCION[accion["accion"]], args=[dispositivo.pk, plaza.pk])
        if accion["bloqueo"]:
            return
        if accion["accion"] == ACCION_LIBERAR:
            context["form_plaza"] = LiberarPlazaForm()
        elif accion["accion"] == ACCION_FUERA_SERVICIO:
            context["form_plaza"] = SacarPlazaDeServicioForm()


# Acciones sobre una plaza del mapa (P5). Mutan: solo POST con CSRF. Las reglas —que la
# plaza no esté tomada, que la reserva siga abierta, el bloqueo de la fila— viven en
# `programas.services.estadias`; acá se resuelve el alcance y se traduce lo que el
# servicio rechaza a lo que el modal sabe mostrar.

#: Adónde manda el modal de cada acción. La vista lo resuelve con `reverse`: el template
#: no arma URLs y el parámetro `?plaza=` nunca se usa como destino.
URL_DE_ACCION = {
    ACCION_LIBERAR: "dispositivos:plaza_liberar",
    ACCION_FUERA_SERVICIO: "dispositivos:plaza_fuera_servicio",
    ACCION_VOLVER: "dispositivos:plaza_volver_servicio",
}


class _PlazaAccionView(DispositivoProgramaPermissionMixin, View):
    """Base de las tres acciones del mapa de plazas.

    La capacidad en el programa la exige el mixin; el alcance al dispositivo, una compuerta
    acá, **antes** de mirar la plaza y de validar el formulario: si no, quien no opera el
    dispositivo recibiría 404 con una plaza inexistente y otra cosa con una ajena, y podría
    distinguirlas. Después el servicio vuelve a exigir lo suyo, que es donde vive la regla.
    """

    http_method_names = ["post"]
    form_class = None
    mensaje_exito = ""

    def post(self, request, pk, plaza_pk):
        dispositivo = get_object_or_404(Dispositivo, pk=pk)
        volver = reverse("dispositivos:sectores", args=[dispositivo.pk])
        if not puede_operar_dispositivo(request.user, dispositivo, self.capacidad_requerida):
            if is_ajax(request):
                return JsonResponse({"ok": False, "message": "No tenés alcance sobre este dispositivo."}, status=403)
            raise PermissionDenied
        # La ajena, la inexistente y la del sector dado de baja dan el mismo 404: ninguna de
        # las tres se dibuja en el mapa, y tres respuestas distintas serían un oráculo.
        plaza = get_object_or_404(
            # Con el sector y su dispositivo ya traídos: los servicios los leen del objeto
            # que reciben para resolver el alcance, y sin esto serían dos consultas más.
            Plaza.objects.select_related("sector__dispositivo"),
            pk=plaza_pk,
            sector__dispositivo=dispositivo,
            sector__activo=True,
        )
        form = self.form_class(request.POST) if self.form_class else None
        if form is not None and not form.is_valid():
            return self._rechazar(request, form.errors, volver)
        try:
            self.ejecutar(request, plaza, form.cleaned_data if form else {})
        except PermissionDenied:
            if is_ajax(request):
                return JsonResponse({"ok": False, "message": "No tenés alcance sobre este dispositivo."}, status=403)
            raise
        except ValidationError as error:
            return self._rechazar(request, self._errores_del_servicio(error, form), volver)
        mensaje = self.mensaje_exito.format(plaza=plaza.codigo)
        if is_ajax(request):
            return ajax_redirect(request, volver, mensaje)
        messages.success(request, mensaje)
        return redirect(volver)

    @staticmethod
    def _errores_del_servicio(error, form):
        """Lo que el servicio rechaza, en la forma `{campo: [mensajes]}` del modal.

        Una clave que el formulario no tiene —`estado` cuando la reserva ya se liberó,
        `plaza` cuando quedó tomada— va al error general, el único lugar donde el modal la
        puede mostrar.
        """

        if not hasattr(error, "error_dict"):
            return {"__all__": list(error.messages)}
        campos = form.fields if form else {}
        errores = {}
        for campo, mensajes in error.message_dict.items():
            destino = campo if campo in campos else "__all__"
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


class PlazaLiberarView(_PlazaAccionView):
    """Suelta la reserva o el préstamo que tiene tomada la plaza (resuelve la alerta de P4)."""

    capacidad_requerida = CAP_ADMITIR
    form_class = LiberarPlazaForm
    mensaje_exito = "Plaza {plaza} liberada."

    def ejecutar(self, request, plaza, datos):
        # La reserva se vuelve a buscar acá y no viaja en el POST: entre que la pantalla se
        # dibujó y el envío, un ingreso pudo consumirla. `liberar_reserva` la relee con la
        # fila bloqueada y rechaza la que ya no está vigente.
        reserva = reserva_abierta_de(plaza)
        if reserva is None:
            raise ValidationError({"estado": "La plaza ya no tiene una reserva ni un préstamo sin liberar."})
        liberar_reserva(reserva=reserva, usuario=request.user, motivo=datos.get("motivo", ""))


class PlazaFueraDeServicioView(_PlazaAccionView):
    """Saca la plaza de servicio con su motivo. Falla si está tomada: primero se reubica."""

    capacidad_requerida = CAP_EDITAR
    form_class = SacarPlazaDeServicioForm
    mensaje_exito = "Plaza {plaza} fuera de servicio."

    def ejecutar(self, request, plaza, datos):
        sacar_plaza_de_servicio(plaza=plaza, usuario=request.user, motivo=datos["motivo"])


class PlazaVolverAServicioView(_PlazaAccionView):
    """Repone la plaza (resuelve la alerta «plazas fuera de servicio» de P4)."""

    capacidad_requerida = CAP_EDITAR
    mensaje_exito = "Plaza {plaza} de nuevo en servicio."

    def ejecutar(self, request, plaza, datos):
        volver_plaza_a_servicio(plaza=plaza, usuario=request.user)


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

        return errores_por_campo(error, form.fields)

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
        # Las novedades de la bitácora en las que la persona está involucrada: de lectura,
        # paginadas y con su propio presupuesto (`dispositivos_estadia_novedades`). Se cargan
        # y se corrigen en la bitácora del turno (P10).
        context["novedades_page"] = novedades_de_estadia(estadia, self.request.GET.get("novedades_page"))
        context["tab"] = normalizar_solapa_estadia(self.request.GET.get("tab", ""))
        context["url_bitacora"] = reverse("dispositivos:bitacora", args=[dispositivo.pk])
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
        volver = (
            url_solapa_estadias(dispositivo.pk)
            if request.POST.get("volver") == "dispositivo"
            else reverse("dispositivos:estadia_detalle", args=[dispositivo.pk, estadia.pk])
        )

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
