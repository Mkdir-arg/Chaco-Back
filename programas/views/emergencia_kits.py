"""Entregas de kits de Emergencia en el backoffice: E4 (listado y asistente), E5 (detalle) y la
recepción dentro del dispositivo.

Las vistas **no tienen reglas de la entrega**. Cada acción llama a la función de
``programas/services/kits.py`` —la misma que usa la API de la app (RU-2)— y traduce lo que
esa función contesta, igual que la mesa (``programas/views/emergencia.py``):

* ``PermissionDenied`` de la mesa → 403. No se atrapa.
* :class:`EstadoCambio` → la pantalla quedó vieja (la otra pestaña, la guardia, la mesa). Es el
  409 de la API; acá se vuelve a la pantalla con el mensaje del servicio (RU-20).
* ``ValidationError`` → el mensaje del servicio, en su campo si la pantalla tiene formulario.

**Dos superficies, dos alcances** (RN-4.8):

* La mesa (``MesaPermissionMixin``) ve todas las entregas: un id inexistente es un 404 y nada más.
* La guardia (:class:`RecepcionKitsMixin`) entra **por su dispositivo**. Sin
  ``emergencia.recibir_kit`` en ninguno, 403; con la capacidad pero sin alcance sobre **ese**
  dispositivo —o con una entrega de otro—, **404**, igual que un id inexistente (plan §2, C2).

**El asistente «Nueva entrega» no usa la sesión.** La ficha del arquetipo Wizard avisa que la
sesión la comparten todas las pestañas, y pide que cada paso lleve en ocultos lo que mostró
para compararlo con ella. Acá no hay nada que comparar: el destino viaja en la URL y las
cantidades en los ocultos del paso 3, así que «Crear entrega» escribe exactamente lo que esa
pantalla mostró, haya las pestañas que haya. Es el mismo criterio con el que «Nuevo caso» se
resolvió sin sesión (PR 3), con los tres pasos que pide el diseño.
"""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from programas.forms_emergencia_kits import (
    BuscarDestinoForm,
    CancelarEntregaForm,
    ConfirmarEntregaForm,
    EnCaminoForm,
    FiltrosEntregasForm,
    ItemsEntregaForm,
    ObservarEntregaForm,
    RecepcionKitForm,
)
from programas.mixins_emergencia import MesaPermissionMixin
from programas.models import EntregaKit
from programas.selectors import kits as selectores
from programas.services import kits as servicio
from programas.services.configuracion_emergencia import catalogo_kits
from programas.services.dispositivos import dispositivos_en_alcance, puede_operar_dispositivo
from programas.services.emergencia import EstadoCambio
from programas.services.emergencia_programa import CAP_RECIBIR_KIT, puede_supervisar_la_mesa

TEMPLATE_LISTADO = "programas/emergencia/kits/list.html"
TEMPLATE_DETALLE = "programas/emergencia/kits/detail.html"
TEMPLATE_DESTINO = "programas/emergencia/kits/nueva_destino.html"
TEMPLATE_ITEMS = "programas/emergencia/kits/nueva_items.html"
TEMPLATE_CONFIRMAR = "programas/emergencia/kits/nueva_confirmar.html"
TEMPLATE_PENDIENTES = "programas/emergencia/kits/pendientes.html"
TEMPLATE_RECIBIR = "programas/emergencia/kits/recibir.html"

ENTREGAS_POR_PAGINA = 50
DESTINOS_POR_PAGINA = 20

#: Parámetros del listado que no son un filtro que el usuario eligió: la página, la solapa
#: y los dos que abren un modal por GET.
NO_SON_FILTRO = ("page", "solapa", "en_camino", "cancelar")

PASOS_DEL_ASISTENTE = ("Destino", "Ítems y cantidades", "Confirmar")
VOLVER_AL_LISTADO = "listado"


def _url(nombre, *args, **parametros):
    """``reverse`` más un querystring con los parámetros que traen valor."""

    url = reverse(nombre, args=args)
    consulta = urlencode({clave: valor for clave, valor in parametros.items() if valor not in (None, "")})
    return f"{url}?{consulta}" if consulta else url


def _errores_de(form):
    """Los errores de un formulario chico en una línea, para el aviso."""

    return " ".join(dict.fromkeys(error for errores in form.errors.values() for error in errores))


def _estado(entrega):
    texto, tono = servicio.estado_visible_de_entrega(entrega)
    return {"estado_texto": texto, "estado_tono": tono}


def _quien_y_cuando(usuario, momento):
    return f"{selectores.nombre_de(usuario)} · {selectores.fecha_hora(momento)}" if usuario and momento else ""


# ---------------------------------------------------------------------------
# E4 · Listado
# ---------------------------------------------------------------------------


class EntregasListView(MesaPermissionMixin, View):
    """E4: las entregas de la mesa, por solapa, filtradas y paginadas de a 50.

    «Marcar en camino» y «Cancelar» piden datos, así que son modales del arquetipo Modal
    abiertos por parámetro GET (``?en_camino=<id>``, ``?cancelar=<id>``): el menú de la fila
    solo navega y el modal lo arma el servidor si la entrega sigue estando para eso.
    """

    def _chips(self, actual, conteos, elegidos):
        return [
            {
                "texto": texto,
                "url": _url("emergencia:entregas", solapa=solapa, **elegidos),
                "activo": solapa == actual,
                "n": conteos.get(solapa, 0),
            }
            for solapa, texto in selectores.SOLAPAS
        ]

    def _fila(self, entrega, conservados):
        acciones = []
        if entrega.estado == EntregaKit.Estado.PREPARADA:
            acciones.append(
                {
                    "texto": "Marcar en camino",
                    "icono": "fa-truck",
                    "url": _url("emergencia:entregas", en_camino=entrega.pk, **conservados),
                }
            )
        if entrega.abierta:
            acciones.append(
                {
                    "texto": "Cancelar",
                    "icono": "fa-ban",
                    "url": _url("emergencia:entregas", cancelar=entrega.pk, **conservados),
                    "peligro": True,
                }
            )
        return {
            "entrega": entrega,
            "items": selectores.resumen_de_items(list(entrega.lineas.all())),
            "armada": _quien_y_cuando(entrega.armada_por, entrega.creado),
            "recibida": _quien_y_cuando(entrega.recibida_por, entrega.recibida_en),
            "url": reverse("emergencia:entrega_detalle", args=[entrega.pk]),
            "acciones": acciones,
            **_estado(entrega),
        }

    def _modal(self, request, parametro, form_class, estados, nombre_url):
        """El modal que pide la URL, si la entrega sigue en uno de ``estados``. Si no, no se abre."""

        pedido = request.GET.get(parametro, "")
        if not pedido.isdecimal():
            return None
        entrega = EntregaKit.objects.select_related("dispositivo").filter(pk=pedido, estado__in=estados).first()
        if entrega is None:
            return None
        return {
            "entrega": entrega,
            "form": form_class(auto_id=f"{parametro}_%s"),
            "url": reverse(nombre_url, args=[entrega.pk]),
        }

    def get(self, request):
        form = FiltrosEntregasForm(request.GET)
        filtros = form.filtros()
        solapa = filtros["solapa"]
        elegidos = {campo: valor for campo, valor in form.limpios().items() if campo not in NO_SON_FILTRO}
        pagina = Paginator(selectores.listado_de_entregas(filtros), ENTREGAS_POR_PAGINA).get_page(
            request.GET.get("page")
        )
        conservados = {"solapa": solapa, **elegidos, "page": pagina.number if pagina.number > 1 else None}
        conteos = selectores.conteos_de_solapas()
        dispositivos, localidades = selectores.destinos_con_entregas()
        contexto = {
            "page_obj": pagina,
            "filas": [self._fila(entrega, conservados) for entrega in pagina.object_list],
            "solapa": solapa,
            "solapas": self._chips(solapa, conteos, elegidos),
            "filtro": elegidos,
            "estados": EntregaKit.Estado.choices,
            "dispositivos": dispositivos,
            "localidades": localidades,
            "hay_entregas": conteos["total"] > 0,
            "url_sin_filtros": _url("emergencia:entregas", solapa=solapa),
            "url_nueva": reverse("emergencia:entrega_nueva"),
            "volver_al_listado": VOLVER_AL_LISTADO,
            "modal_en_camino": self._modal(
                request, "en_camino", EnCaminoForm, [EntregaKit.Estado.PREPARADA], "emergencia:entrega_en_camino"
            ),
            "modal_cancelar": self._modal(
                request, "cancelar", CancelarEntregaForm, EntregaKit.ESTADOS_ABIERTOS, "emergencia:entrega_cancelar"
            ),
        }
        return render(request, TEMPLATE_LISTADO, contexto)


# ---------------------------------------------------------------------------
# E4 · «Nueva entrega» (asistente de 3 pasos, sin sesión)
# ---------------------------------------------------------------------------


def _pasos(paso_actual):
    """El contexto del indicador de pasos. Solo el paso 1 es un link: al 2 se vuelve con «Anterior»,
    que lleva las cantidades (un link las perdería)."""

    pasos = [{"etiqueta": etiqueta} for etiqueta in PASOS_DEL_ASISTENTE]
    if paso_actual > 1:
        pasos[0]["url"] = reverse("emergencia:entrega_nueva")
    return {
        "pasos": pasos,
        "paso_actual": paso_actual,
        "total_pasos": len(PASOS_DEL_ASISTENTE),
        "url_entregas": reverse("emergencia:entregas"),
    }


def _ultima_entrega(resumen):
    ultima = resumen["ultima_entrega"]
    if ultima is None:
        return None
    return {
        "numero": ultima["numero"],
        "fecha": selectores.fecha_hora(ultima["fecha"]),
        "con_diferencias": ultima["con_diferencias"],
    }


def _destino(dispositivo, resumen):
    """Lo que el asistente muestra de un dispositivo: nada de su operación interna más que estas cifras."""

    return {
        "pk": dispositivo.pk,
        "nombre": dispositivo.nombre,
        "localidad": dispositivo.localidad,
        "alojadas": resumen["alojadas"],
        "plazas": f"{resumen['plazas_ocupadas']} de {resumen['plazas_operativas']}",
        "ultima_entrega": _ultima_entrega(resumen),
        "url": reverse("emergencia:entrega_nueva_items", args=[dispositivo.pk]),
    }


class NuevaEntregaDestinoView(MesaPermissionMixin, View):
    """Paso 1: a qué dispositivo. Un listado con buscador; elegir es navegar al paso 2."""

    def get(self, request):
        buscador = BuscarDestinoForm(request.GET)
        pagina = Paginator(selectores.destinos_posibles(buscador.texto()), DESTINOS_POR_PAGINA).get_page(
            request.GET.get("page")
        )
        dispositivos = list(pagina.object_list)
        resumenes = selectores.resumenes_de_destino(dispositivos)
        contexto = {
            **_pasos(1),
            "page_obj": pagina,
            "destinos": [_destino(dispositivo, resumenes[dispositivo.pk]) for dispositivo in dispositivos],
            "q": buscador.texto(),
            "url_sin_filtros": reverse("emergencia:entrega_nueva"),
        }
        return render(request, TEMPLATE_DESTINO, contexto)


class _PasoConDestino(MesaPermissionMixin, View):
    """Los pasos 2 y 3: el destino viene en la URL y tiene que seguir activo (RN-4.2)."""

    def _destino(self, pk):
        return get_object_or_404(selectores.destinos_posibles(), pk=pk)

    def _original(self, pedido, dispositivo):
        """La entrega que se repone, si la URL o el oculto la nombran y es de ese dispositivo."""

        if not str(pedido or "").isdecimal():
            return None
        return (
            selectores.entregas_para_detalle()
            .filter(pk=pedido, dispositivo=dispositivo, estado=EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS)
            .first()
        )

    def _contexto(self, paso, dispositivo, form, original):
        return {
            **_pasos(paso),
            "destino": _destino(dispositivo, selectores.resumen_destino(dispositivo)),
            "form": form,
            "repone_a": original,
            "url_items": reverse("emergencia:entrega_nueva_items", args=[dispositivo.pk]),
            "url_confirmar": reverse("emergencia:entrega_nueva_confirmar", args=[dispositivo.pk]),
            "url_configuracion": (
                reverse("emergencia:configuracion") if puede_supervisar_la_mesa(self.request.user) else ""
            ),
        }

    def _paso_items(self, request, dispositivo, form, original, status=200):
        return render(request, TEMPLATE_ITEMS, self._contexto(2, dispositivo, form, original), status=status)


class NuevaEntregaItemsView(_PasoConDestino):
    """Paso 2: qué y cuánto. No escribe nada: «Continuar» manda las cantidades al paso 3.

    Con ``?repone=<id>`` (el botón «Reponer» de E5) arranca con las diferencias negativas de
    esa entrega como cantidades (HU-4.5). El POST es el «Anterior» del paso 3: vuelve a
    mostrar el formulario con lo que ya se había cargado.
    """

    def get(self, request, dispositivo):
        destino = self._destino(dispositivo)
        original = self._original(request.GET.get("repone"), destino)
        iniciales = {}
        if original is not None:
            iniciales = ItemsEntregaForm.iniciales_de(
                selectores.faltantes_de(selectores.lineas_de(original)), repone_a=original
            )
        form = ItemsEntregaForm(initial=iniciales, catalogo=catalogo_kits(solo_activos=True))
        return self._paso_items(request, destino, form, original)

    def post(self, request, dispositivo):
        destino = self._destino(dispositivo)
        catalogo = list(catalogo_kits(solo_activos=True))
        cargado = ItemsEntregaForm(request.POST, catalogo=catalogo)
        # Lo que venía bien se conserva; lo que no, se vuelve a pedir en blanco.
        iniciales = cargado.cantidades_cargadas() if cargado.is_valid() else {}
        original = self._original(iniciales.get("repone_a"), destino)
        return self._paso_items(request, destino, ItemsEntregaForm(initial=iniciales, catalogo=catalogo), original)


class NuevaEntregaConfirmarView(_PasoConDestino):
    """Paso 3: el resumen y «Crear entrega». Es el único paso que escribe.

    Llega por POST desde el paso 2 (muestra el resumen) y por POST desde sí mismo con
    ``confirmar`` (crea). Lo que crea es lo que traen sus ocultos: lo que la pantalla mostró.
    """

    def get(self, request, dispositivo):
        return redirect("emergencia:entrega_nueva_items", dispositivo)

    def _resumen(self, request, dispositivo, form, original, lineas, status=200):
        contexto = self._contexto(3, dispositivo, form, original)
        contexto["lineas"] = [
            {"item": item.nombre, "cantidad": cantidad, "unidad": item.unidad} for item, cantidad in lineas
        ]
        return render(request, TEMPLATE_CONFIRMAR, contexto, status=status)

    def post(self, request, dispositivo):
        destino = self._destino(dispositivo)
        catalogo = list(catalogo_kits(solo_activos=True))
        if "confirmar" not in request.POST:
            cargado = ItemsEntregaForm(request.POST, catalogo=catalogo)
            original = self._original(request.POST.get("repone_a"), destino)
            if not cargado.is_valid():
                return self._paso_items(request, destino, cargado, original, status=400)
            form = ConfirmarEntregaForm(initial=cargado.cantidades_cargadas(), catalogo=catalogo)
            return self._resumen(request, destino, form, original, cargado.lineas())

        form = ConfirmarEntregaForm(request.POST, catalogo=catalogo)
        original = self._original(request.POST.get("repone_a"), destino)
        if not form.is_valid():
            return self._resumen(request, destino, form, original, form.lineas(), status=400)
        try:
            entrega = servicio.crear_entrega(
                request.user,
                destino,
                form.lineas(),
                observacion=form.cleaned_data["observacion"],
                repone_a=form.cleaned_data["repone_a"],
            )
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._resumen(request, destino, form, original, form.lineas(), status=400)
        messages.success(request, f"Entrega {entrega.numero} armada para {destino.nombre}. Queda preparada.")
        return redirect("emergencia:entrega_detalle", entrega.pk)


# ---------------------------------------------------------------------------
# E5 · Detalle
# ---------------------------------------------------------------------------


def _datos_de_cabecera(entrega):
    datos = [
        {"etiqueta": "Dispositivo destino", "valor": entrega.dispositivo.nombre},
        {"etiqueta": "Localidad", "valor": entrega.dispositivo.localidad},
        {"etiqueta": "Armada por", "valor": _quien_y_cuando(entrega.armada_por, entrega.creado)},
        {"etiqueta": "En camino desde", "valor": selectores.fecha_hora(entrega.despachada_en)},
        {"etiqueta": "Transporte", "valor": entrega.transporte},
        {"etiqueta": "Recibida por", "valor": _quien_y_cuando(entrega.recibida_por, entrega.recibida_en)},
    ]
    if entrega.estado == EntregaKit.Estado.CANCELADA:
        datos.append({"etiqueta": "Motivo de la cancelación", "valor": entrega.motivo_cancelacion})
    return datos


def _enlace_a(entrega):
    return {
        "numero": entrega.numero,
        "url": reverse("emergencia:entrega_detalle", args=[entrega.pk]),
        **_estado(entrega),
    }


class EntregaDetalleView(MesaPermissionMixin, View):
    """E5: lo enviado contra lo recibido, las observaciones, el remito y la traza."""

    def get(self, request, pk):
        entrega = get_object_or_404(selectores.entregas_para_detalle(), pk=pk)
        lineas = selectores.lineas_de(entrega)
        recibida = entrega.recibida
        faltantes = selectores.faltantes_de(lineas) if selectores.con_diferencias(entrega) else []
        contexto = {
            "entrega": entrega,
            "titulo": f"Entrega {entrega.numero}",
            "bajada": " · ".join(
                parte for parte in (entrega.dispositivo.nombre, entrega.dispositivo.localidad) if parte
            ),
            "datos": _datos_de_cabecera(entrega),
            "lineas": lineas,
            "eventos": selectores.traza_de(entrega),
            "remito": (
                [
                    {
                        "url": entrega.remito.url,
                        "rotulo": "Remito",
                        "alt": f"Remito de la entrega {entrega.numero}",
                        "fecha": entrega.recibida_en,
                    }
                ]
                if entrega.remito
                else []
            ),
            "repone_a": _enlace_a(entrega.repone_a) if entrega.repone_a_id else None,
            "reposiciones": [_enlace_a(reposicion) for reposicion in selectores.reposiciones_de(entrega)],
            "recibida": recibida,
            "puede_marcar_en_camino": entrega.estado == EntregaKit.Estado.PREPARADA,
            "puede_cancelar": entrega.abierta,
            "url_reponer": (
                _url("emergencia:entrega_nueva_items", entrega.dispositivo_id, repone=entrega.pk) if faltantes else ""
            ),
            **_estado(entrega),
        }
        if contexto["puede_marcar_en_camino"]:
            contexto["form_en_camino"] = EnCaminoForm(auto_id="en_camino_%s")
        if contexto["puede_cancelar"]:
            contexto["form_cancelar"] = CancelarEntregaForm(auto_id="cancelar_%s")
        if recibida:
            contexto["form_observar"] = ObservarEntregaForm(
                initial={"texto": entrega.observacion_mesa}, auto_id="observar_%s"
            )
        return render(request, TEMPLATE_DETALLE, contexto)


# ---------------------------------------------------------------------------
# Acciones de la mesa sobre una entrega (POST)
# ---------------------------------------------------------------------------


class _AccionDeEntregaView(MesaPermissionMixin, View):
    """Una acción POST de la mesa: llama al servicio y vuelve a donde estaba con lo que contestó.

    Vuelve al detalle, o al listado si el POST salió de ahí (``volver=listado``: un valor
    fijo, nunca una URL). Lo que el servicio rechace se traduce acá, una sola vez.
    """

    http_method_names = ["post"]
    form_class = None

    def _destino(self, request, entrega):
        if request.POST.get("volver") == VOLVER_AL_LISTADO:
            return reverse("emergencia:entregas")
        return reverse("emergencia:entrega_detalle", args=[entrega.pk])

    def post(self, request, pk):
        entrega = get_object_or_404(EntregaKit, pk=pk)
        destino = self._destino(request, entrega)
        form = self.form_class(request.POST)
        if not form.is_valid():
            messages.error(request, _errores_de(form))
            return redirect(destino)
        try:
            aviso = self.ejecutar(request, entrega, form)
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return redirect(destino)
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
            return redirect(destino)
        messages.success(request, aviso)
        return redirect(destino)


class MarcarEnCaminoView(_AccionDeEntregaView):
    form_class = EnCaminoForm

    def ejecutar(self, request, entrega, form):
        servicio.marcar_en_camino(
            entrega, request.user, transporte=form.cleaned_data["transporte"], hora=form.cleaned_data["hora"]
        )
        return f"La entrega {entrega.numero} está en camino."


class CancelarEntregaView(_AccionDeEntregaView):
    form_class = CancelarEntregaForm

    def ejecutar(self, request, entrega, form):
        servicio.cancelar_entrega(entrega, request.user, form.cleaned_data["motivo"])
        return f"Entrega {entrega.numero} cancelada."


class ObservarEntregaView(_AccionDeEntregaView):
    form_class = ObservarEntregaForm

    def ejecutar(self, request, entrega, form):
        servicio.observar_recepcion(entrega, request.user, form.cleaned_data["texto"])
        return "Observación guardada. Las cantidades recibidas no cambiaron."


# ---------------------------------------------------------------------------
# La recepción, dentro del dispositivo
# ---------------------------------------------------------------------------


class RecepcionKitsMixin(LoginRequiredMixin):
    """Las pantallas de kits de **un** dispositivo: ``emergencia.recibir_kit`` con el Equipo (RU-8, H3).

    * Sin sesión, al login.
    * Sin la capacidad sobre **ningún** dispositivo, 403: no abre esta parte del módulo, que
      es lo mismo que la API le contesta con ``SIN_MODULO``.
    * Con la capacidad en otro dispositivo, **404**: igual que un id inexistente, sin
      confirmar que la institución existe (plan §2, C2; Cambio 432).

    Deja el dispositivo en ``self.dispositivo``.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        en_alcance = dispositivos_en_alcance(request.user, CAP_RECIBIR_KIT)
        self.dispositivo = en_alcance.filter(pk=kwargs["dispositivo"]).first()
        if self.dispositivo is None:
            if not en_alcance.exists():
                raise PermissionDenied
            raise Http404("Dispositivo inexistente.")
        return super().dispatch(request, *args, **kwargs)

    def _url_pendientes(self):
        return reverse("emergencia:dispositivo_kits", args=[self.dispositivo.pk])


class KitsDelDispositivoView(RecepcionKitsMixin, View):
    """«Emergencia · Kits» del dispositivo: lo que está por llegar (o llegó sin marca de salida)."""

    def get(self, request, dispositivo):
        filas = [
            {
                "entrega": entrega,
                "items": selectores.resumen_de_items(list(entrega.lineas.all())),
                "en_camino_desde": selectores.fecha_hora(entrega.despachada_en),
                "url": reverse("emergencia:dispositivo_kit_recibir", args=[self.dispositivo.pk, entrega.pk]),
                **_estado(entrega),
            }
            for entrega in selectores.entregas_pendientes_de(self.dispositivo, request.user)
        ]
        contexto = {
            "dispositivo": self.dispositivo,
            "filas": filas,
            # Un enlace que va a rebotar no se ofrece: el detalle pide `dispositivo.ver`.
            "url_dispositivo": (
                reverse("dispositivos:detalle", args=[self.dispositivo.pk])
                if puede_operar_dispositivo(request.user, self.dispositivo, "dispositivo.ver")
                else ""
            ),
        }
        return render(request, TEMPLATE_PENDIENTES, contexto)


class RecibirKitView(RecepcionKitsMixin, View):
    """El formulario de recepción: precargado con lo enviado, más el remito y la observación."""

    def _entrega(self, pk):
        # Del dispositivo de la URL, que ya pasó el alcance: la de otro es un 404.
        return get_object_or_404(EntregaKit.objects.select_related("dispositivo"), pk=pk, dispositivo=self.dispositivo)

    def _render(self, request, entrega, form, status=200):
        contexto = {
            "dispositivo": self.dispositivo,
            "entrega": entrega,
            "form": form,
            "url_pendientes": self._url_pendientes(),
            **_estado(entrega),
        }
        return render(request, TEMPLATE_RECIBIR, contexto, status=status)

    def _ya_no_esta_abierta(self, request, entrega):
        messages.warning(request, servicio.mensaje_de_estado(entrega))
        return redirect(self._url_pendientes())

    def get(self, request, dispositivo, pk):
        entrega = self._entrega(pk)
        if not entrega.abierta:
            return self._ya_no_esta_abierta(request, entrega)
        return self._render(request, entrega, RecepcionKitForm(lineas=selectores.lineas_de(entrega)))

    def post(self, request, dispositivo, pk):
        entrega = self._entrega(pk)
        form = RecepcionKitForm(request.POST, request.FILES, lineas=selectores.lineas_de(entrega))
        if not form.is_valid():
            return self._render(request, entrega, form, status=400)
        try:
            recibida = servicio.recibir_entrega(
                entrega,
                request.user,
                form.cantidades(),
                form.cleaned_data["remito"],
                observacion=form.cleaned_data["observacion"],
            )
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return redirect(self._url_pendientes())
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._render(request, entrega, form, status=400)
        diferencias = selectores.diferencias_de(selectores.lineas_de(recibida))
        messages.success(request, f"Entrega {recibida.numero}: {selectores.texto_de_recepcion(diferencias).lower()}.")
        return redirect(self._url_pendientes())
