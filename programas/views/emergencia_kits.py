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

**«Nueva entrega» es una sola pantalla y no usa la sesión** (Cambio 586): el destino viaja en la URL (GET) y en
un oculto del formulario, y «Crear y enviar» escribe exactamente lo que ese envío trae, haya las pestañas que haya.
La columna «Le falta (estimado)» sale de las mismas reglas que la solapa Abastecimiento de Situación.
"""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from programas.forms_emergencia_kits import (
    AceptarDiferenciaForm,
    CancelarEntregaForm,
    DestinoEntregaForm,
    EnCaminoForm,
    FiltrosEntregasForm,
    NuevaEntregaForm,
    ObservarEntregaForm,
    RecepcionKitForm,
)
from programas.mixins_emergencia import MesaPermissionMixin
from programas.models import EntregaKit
from programas.selectors import kits as selectores
from programas.selectors.emergencia_abastecimiento import lecturas_de_un_dispositivo
from programas.services import kits as servicio
from programas.services.abastecimiento_emergencia import faltantes_de_un_dispositivo
from programas.services.configuracion_emergencia import catalogo_kits, sla_vigente
from programas.services.dispositivos import (
    ALCANCE_NADA,
    alcance_de_edificios,
    dispositivos_en_alcance,
    puede_operar_dispositivo,
)
from programas.services.emergencia import EstadoCambio
from programas.services.emergencia_programa import CAP_RECIBIR_KIT, puede_supervisar_la_mesa, recibe_kits
from programas.urls_seguras import destino_seguro

TEMPLATE_LISTADO = "programas/emergencia/kits/list.html"
TEMPLATE_DETALLE = "programas/emergencia/kits/detail.html"
TEMPLATE_NUEVA = "programas/emergencia/kits/nueva.html"
TEMPLATE_PENDIENTES = "programas/emergencia/kits/pendientes.html"
TEMPLATE_RECIBIR = "programas/emergencia/kits/recibir.html"

ENTREGAS_POR_PAGINA = 50
#: Filas por página de «Emergencia · Kits» del dispositivo.
PENDIENTES_POR_PAGINA = 25

#: Parámetros del listado que no son un filtro que el usuario eligió: la página, la solapa
#: y los dos que abren un modal por GET.
NO_SON_FILTRO = ("page", "solapa", "en_camino", "cancelar")

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


def _alcance_para_abrir_el_edificio(usuario, dispositivo):
    """Los edificios cuya página le abre a ``usuario``: pide ``dispositivo.ver`` sobre la institución **y** el alcance por
    edificio de esa capacidad (``alcance_de_edificios``), como la página misma. Se resuelve una vez por pantalla."""

    if not puede_operar_dispositivo(usuario, dispositivo, "dispositivo.ver"):
        return ALCANCE_NADA
    return alcance_de_edificios(usuario, dispositivo, "dispositivo.ver")


def _url_de_recepcion(entrega, dispositivo, alcance):
    """Dónde se recibe ``entrega`` (Cambio 586): la solapa Kits de su edificio, que es el lugar de la recepción.

    Sin ``dispositivo.ver`` esa página contesta 403 y fuera del alcance por edificio 404 (la guardia con solo
    ``emergencia.recibir_kit``, o con ``dispositivo.ver`` acotado a otro edificio):
    ahí, y en las entregas anteriores al Cambio 523 que no tienen edificio, va el formulario de recepción del
    dispositivo. ``alcance`` (``_alcance_para_abrir_el_edificio``) se resuelve una vez por pantalla, no por fila.
    """

    if entrega.edificio_id is not None and alcance.permite(entrega.edificio_id):
        pagina = reverse("dispositivos:edificio_operativo", args=[dispositivo.pk, entrega.edificio_id])
        return servicio.url_de_kits_del_edificio(pagina, entrega)
    return reverse("emergencia:dispositivo_kit_recibir", args=[dispositivo.pk, entrega.pk])


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

    def _fila(self, entrega, conservados, ahora):
        acciones = []
        sin_cerrar = entrega.diferencia_sin_cerrar
        if sin_cerrar:
            acciones.append(
                {
                    "texto": "Cerrar la diferencia",
                    "icono": "fa-circle-check",
                    "url": f"{reverse('emergencia:entrega_detalle', args=[entrega.pk])}#entrega-cerrar-titulo",
                }
            )
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
            "demorada": selectores.es_demorada(entrega, ahora),
            "diferencia_sin_cerrar": sin_cerrar,
            **_estado(entrega),
        }

    def _alerta_de_demoradas(self, conteos, solapa):
        """El aviso de arriba del listado: cuántas entregas llevan más de 48 h en camino sin recibirse."""

        cantidad = conteos.get(selectores.SOLAPA_DEMORADAS, 0)
        if not cantidad or solapa == selectores.SOLAPA_DEMORADAS:
            return None
        singular = cantidad == 1
        horas = EntregaKit.HORAS_PARA_DEMORADA
        return {
            "titulo": (
                f"{cantidad} entrega lleva más de {horas} horas en camino sin recibirse"
                if singular
                else f"{cantidad} entregas llevan más de {horas} horas en camino sin recibirse"
            ),
            "texto": "No se cancelan solas y no cuentan como «en camino» en lo que le falta a cada dispositivo.",
            "url": _url("emergencia:entregas", solapa=selectores.SOLAPA_DEMORADAS),
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
        ahora = timezone.now()
        pagina = Paginator(selectores.listado_de_entregas(filtros, ahora), ENTREGAS_POR_PAGINA).get_page(
            request.GET.get("page")
        )
        conservados = {"solapa": solapa, **elegidos, "page": pagina.number if pagina.number > 1 else None}
        conteos = selectores.conteos_de_solapas(ahora)
        dispositivos, localidades = selectores.destinos_con_entregas()
        contexto = {
            "page_obj": pagina,
            "alerta_demoradas": self._alerta_de_demoradas(conteos, solapa),
            "rotulo_demorada": selectores.ROTULO_DEMORADA,
            "filas": [self._fila(entrega, conservados, ahora) for entrega in pagina.object_list],
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
# E4 · «Nueva entrega» (una sola pantalla, sin sesión)
# ---------------------------------------------------------------------------


def _ultima_entrega(resumen):
    ultima = resumen["ultima_entrega"]
    if ultima is None:
        return None
    return {
        "numero": ultima["numero"],
        "fecha": selectores.fecha_hora(ultima["fecha"]),
        "con_diferencias": ultima["con_diferencias"],
    }


def _resumen_del_destino(destino):
    """Lo que la pantalla muestra del destino: nada de su operación interna más que estas cifras."""

    resumen = selectores.resumen_destino(destino)
    return {
        "nombre": destino.nombre,
        "localidad": destino.localidad,
        "alojadas": resumen["alojadas"],
        "plazas": f"{resumen['plazas_ocupadas']} de {resumen['plazas_operativas']}",
        "ultima_entrega": _ultima_entrega(resumen),
    }


def _texto_de_lo_que_no_se_repone(sin_item_activo):
    """«Colchón (3), Frazada (1)»: lo que faltó y ya no está en el catálogo activo."""

    return ", ".join(f"{nombre} ({cantidad})" for nombre, cantidad in sin_item_activo)


def _filas_para_la_tabla(filas, horas_demorada):
    """Las filas del form más lo que dibuja ``components/_tabla_cantidades.html``: ``nombre``, ``unidad`` e ``info``.

    La columna «Le falta (estimado)» es una sola celda: la cifra y, si hay, cuántos están demorados.
    """

    resultado = []
    for fila in filas:
        estimado = fila["estimado"]
        celda = {"texto": "", "nota": ""}
        if estimado:
            celda["texto"] = str(estimado.faltan)
            if estimado.demoradas:
                plural = "s" if estimado.demoradas != 1 else ""
                celda["nota"] = f"{estimado.demoradas} demorado{plural} (más de {horas_demorada} h)"
        resultado.append({**fila, "nombre": fila["item"].nombre, "unidad": fila["item"].unidad, "info": [celda]})
    return resultado


class NuevaEntregaView(MesaPermissionMixin, View):
    """«Nueva entrega»: destino, cantidades, salida y nota en una sola pantalla (Cambio 586).

    * ``GET ?dispositivo=<id>`` elige el destino y muestra la columna «Le falta (estimado)», con las mismas reglas
      que la solapa Abastecimiento de Situación (``armar_abastecimiento``).
    * ``?estimado=1`` carga lo estimado como cantidades; ``?repone=<id>`` arranca con lo que faltó en esa entrega
      (HU-4.5) y avisa de lo que ya no se puede reponer porque su ítem dejó de estar activo.
    * ``POST`` crea la entrega con ``crear_entrega``: con «Sale ahora» la crea y la marca en camino en una sola
      transacción. Lo que rechace el servicio vuelve a la pantalla.
    """

    def _original(self, pedido, destino, *, abierta=True):
        """La entrega que se repone, si la URL o el oculto la nombran, es de ese destino y (``abierta``) su diferencia
        sigue sin cerrar. Con ``abierta=False`` solo se pide que sea de ese destino: sirve para decidir los edificios de
        un reenvío, que el servicio resuelve por su cuenta (Cambio 586)."""

        if not str(pedido or "").isdecimal():
            return None
        entregas = selectores.entregas_para_detalle()
        if abierta:
            entregas = entregas.filter(selectores.q_diferencia_sin_cerrar())
        return entregas.filter(pk=pedido, dispositivo=destino).first()

    def _estimado(self, destino):
        """``({item_id: ItemDelDispositivo}, aviso)``: lo que le falta al destino y, si no se puede, por qué."""

        sla = sla_vigente()
        if sla.inicio_evento is None:
            return (
                {},
                "El inicio del evento no está cargado: no se puede estimar lo que le falta. Cargá las cantidades a mano.",
            )
        ahora = timezone.now()
        estimado = faltantes_de_un_dispositivo(
            lecturas_de_un_dispositivo(destino.pk, sla.inicio_evento, ahora), destino.pk, ahora
        )
        if not estimado:
            return (
                {},
                "Este destino no tiene personas alojadas: no hay faltante que estimar. Cargá las cantidades a mano.",
            )
        return estimado, ""

    def _pantalla(
        self,
        request,
        destino_form,
        destino=None,
        form=None,
        original=None,
        sin_item_activo=(),
        status=200,
        lectura=None,
    ):
        """``lectura`` es el ``(estimado, aviso)`` ya calculado, si la vista lo necesitó antes: se arma una sola vez."""

        contexto = {
            "destino_form": destino_form,
            "destino": None,
            "url_entregas": reverse("emergencia:entregas"),
            "url_nueva": reverse("emergencia:entrega_nueva"),
            "url_insumos": reverse("emergencia:insumos") if puede_supervisar_la_mesa(request.user) else "",
            "repone_a": original,
            "sin_item_activo_texto": _texto_de_lo_que_no_se_repone(sin_item_activo),
        }
        if destino is not None:
            estimado, aviso = lectura if lectura is not None else self._estimado(destino)
            contexto.update(
                destino=_resumen_del_destino(destino),
                form=form,
                filas=_filas_para_la_tabla(form.filas_de_cantidad(estimado), EntregaKit.HORAS_PARA_DEMORADA),
                columnas_info=["Le falta (estimado)"],
                aviso_estimado=aviso,
                # En una reposición las cantidades arrancan con lo que faltó, no con lo estimado: el botón no se ofrece.
                hay_estimado=bool(estimado) and original is None,
                horas_demorada=EntregaKit.HORAS_PARA_DEMORADA,
                url_estimado=_url(
                    "emergencia:entrega_nueva",
                    dispositivo=destino.pk,
                    repone=original.pk if original is not None else None,
                    estimado=1,
                ),
            )
        return render(request, TEMPLATE_NUEVA, contexto, status=status)

    def _form(self, destino, original, datos=None, iniciales=None):
        catalogo = list(catalogo_kits(solo_activos=True))
        edificios = selectores.edificios_a_elegir(destino, original)
        if datos is not None:
            return NuevaEntregaForm(datos, catalogo=catalogo, edificios=edificios)
        return NuevaEntregaForm(
            initial=NuevaEntregaForm.armado_nuevo({"dispositivo": destino.pk, **(iniciales or {})}),
            catalogo=catalogo,
            edificios=edificios,
        )

    def get(self, request):
        destino_form = DestinoEntregaForm(request.GET)
        destino = destino_form.destino()
        if destino is None:
            return self._pantalla(request, destino_form)
        pedido = request.GET.get("repone")
        original = self._original(pedido, destino)
        iniciales, sin_item_activo, lectura = {}, (), None
        if original is not None:
            lineas = selectores.lineas_de(original)
            iniciales = NuevaEntregaForm.iniciales_de(selectores.faltantes_de(lineas), repone_a=original)
            sin_item_activo = selectores.faltantes_sin_item_activo(lineas)
        elif pedido:
            messages.warning(request, "Esa entrega ya no tiene una diferencia para reponer.")
        elif request.GET.get("estimado"):
            lectura = self._estimado(destino)
            estimado = lectura[0]
            catalogo = list(catalogo_kits(solo_activos=True))
            iniciales = NuevaEntregaForm.iniciales_de(
                [
                    (item, estimado[item.pk].faltan)
                    for item in catalogo
                    if item.pk in estimado and estimado[item.pk].faltan > 0
                ]
            )
        form = self._form(destino, original, iniciales=iniciales)
        return self._pantalla(request, destino_form, destino, form, original, sin_item_activo, lectura=lectura)

    def post(self, request):
        pedido = request.POST.get("dispositivo", "")
        if not pedido.isdecimal():
            raise Http404("Destino inexistente.")
        destino = get_object_or_404(selectores.destinos_posibles(), pk=pedido)
        repone = request.POST.get("repone_a")
        original = self._original(repone, destino)
        destino_form = DestinoEntregaForm({"dispositivo": destino.pk})
        # Un reenvío de una reposición ya hecha: los edificios se deciden con la entrega que nombra `repone_a`, aunque su
        # diferencia ya esté cerrada; el servicio es el que la valida (y devuelve la del primer envío, si es el mismo armado).
        form = self._form(destino, original or self._original(repone, destino, abierta=False), datos=request.POST)
        if not form.is_valid():
            return self._pantalla(request, destino_form, destino, form, original, status=400)
        enviar = form.cleaned_data["salida"] == NuevaEntregaForm.SALE_AHORA
        try:
            entrega = servicio.crear_entrega(
                request.user,
                destino,
                form.lineas(),
                observacion=form.cleaned_data["observacion"],
                repone_a=form.cleaned_data["repone_a"],
                edificio=form.cleaned_data.get("edificio"),
                uuid_cliente=form.cleaned_data.get("uuid_cliente"),
                enviar=enviar,
            )
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._pantalla(request, destino_form, destino, form, original, status=400)
        if getattr(entrega, "ya_existia", False):
            # Cambio 535: el mismo armado otra vez (volver atrás y reenviar). No se creó otra.
            messages.info(request, f"La entrega {entrega.numero} ya estaba armada: no se creó otra.")
        elif enviar:
            messages.success(request, f"Entrega {entrega.numero} enviada a {destino.nombre}. Está en camino.")
        else:
            messages.success(request, f"Entrega {entrega.numero} armada para {destino.nombre}. Queda preparada.")
        return redirect("emergencia:entrega_detalle", entrega.pk)


class NuevaEntregaItemsView(MesaPermissionMixin, View):
    """La URL del paso 2 del asistente viejo: lleva a la pantalla única con el mismo destino (y ``?repone=``)."""

    def get(self, request, dispositivo):
        return redirect(_url("emergencia:entrega_nueva", dispositivo=dispositivo, repone=request.GET.get("repone")))


# ---------------------------------------------------------------------------
# E5 · Detalle
# ---------------------------------------------------------------------------


def _datos_de_cabecera(entrega):
    datos = [
        {"etiqueta": "Dispositivo destino", "valor": entrega.dispositivo.nombre},
        {"etiqueta": "Edificio destino", "valor": entrega.edificio.nombre if entrega.edificio_id else ""},
        {"etiqueta": "Localidad", "valor": entrega.dispositivo.localidad},
        {"etiqueta": "Armada por", "valor": _quien_y_cuando(entrega.armada_por, entrega.creado)},
        {"etiqueta": "En camino desde", "valor": selectores.fecha_hora(entrega.despachada_en)},
        {"etiqueta": "Transporte", "valor": entrega.transporte},
        {"etiqueta": "Recibida por", "valor": _quien_y_cuando(entrega.recibida_por, entrega.recibida_en)},
    ]
    if entrega.estado == EntregaKit.Estado.CANCELADA:
        datos.append({"etiqueta": "Motivo de la cancelación", "valor": entrega.motivo_cancelacion})
    if entrega.estado == EntregaKit.Estado.RECIBIDA_CON_DIFERENCIAS:
        datos.append({"etiqueta": "Diferencia", "valor": _como_esta_la_diferencia(entrega)})
    return datos


def _como_esta_la_diferencia(entrega):
    """«Sin cerrar», «Repuesta» o «Aceptada: <motivo>», con quién y cuándo la cerró."""

    if entrega.cierre_diferencia is None:
        return "Sin cerrar"
    quien = _quien_y_cuando(entrega.cierre_diferencia_por, entrega.cierre_diferencia_en)
    if entrega.cierre_diferencia == EntregaKit.CierreDiferencia.REPUESTA:
        return f"Repuesta · {quien}" if quien else "Repuesta"
    texto = f"Aceptada: {entrega.cierre_diferencia_motivo}" if entrega.cierre_diferencia_motivo else "Aceptada"
    return f"{texto} · {quien}" if quien else texto


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
        sin_cerrar = entrega.diferencia_sin_cerrar
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
            **_estado(entrega),
        }
        if sin_cerrar:
            sin_item_activo = selectores.faltantes_sin_item_activo(lineas)
            contexto["cerrar_diferencia"] = {
                # «Reponer» solo se ofrece si hay algo que reponer con ítems activos; se hace una sola vez.
                "url_reponer": (
                    _url("emergencia:entrega_nueva", dispositivo=entrega.dispositivo_id, repone=entrega.pk)
                    if selectores.faltantes_de(lineas)
                    else ""
                ),
                "sin_item_activo": sin_item_activo,
                "sin_item_activo_texto": (
                    "Ya no están en el catálogo activo y no se pueden cargar en una entrega nueva: "
                    f"{_texto_de_lo_que_no_se_repone(sin_item_activo)}."
                ),
            }
            contexto["form_aceptar"] = AceptarDiferenciaForm(auto_id="aceptar_%s")
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


class AceptarDiferenciaView(_AccionDeEntregaView):
    form_class = AceptarDiferenciaForm

    def ejecutar(self, request, entrega, form):
        servicio.aceptar_diferencia(entrega, request.user, form.cleaned_data["motivo"])
        return f"Diferencia de la entrega {entrega.numero} aceptada."


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
            if not recibe_kits(request.user):
                raise PermissionDenied
            raise Http404("Dispositivo inexistente.")
        return super().dispatch(request, *args, **kwargs)

    def _url_pendientes(self):
        return reverse("emergencia:dispositivo_kits", args=[self.dispositivo.pk])

    def _siguiente(self, request):
        """El ``next`` del formulario si es de este sitio (la solapa Kits del edificio); si no, ``""``. Nunca el valor crudo."""

        return destino_seguro(request, "")

    def _destino(self, request):
        """Adónde vuelve el POST: el ``next`` válido y si no, las pendientes del dispositivo."""

        return self._siguiente(request) or self._url_pendientes()


class KitsDelDispositivoView(RecepcionKitsMixin, View):
    """«Emergencia · Kits» del dispositivo: lo que está por llegar (o llegó sin marca de salida)."""

    def get(self, request, dispositivo):
        pagina = Paginator(
            selectores.entregas_pendientes_de(self.dispositivo, request.user), PENDIENTES_POR_PAGINA
        ).get_page(request.GET.get("page"))
        puede_ver = puede_operar_dispositivo(request.user, self.dispositivo, "dispositivo.ver")
        alcance = alcance_de_edificios(request.user, self.dispositivo, "dispositivo.ver") if puede_ver else ALCANCE_NADA
        filas = [
            {
                "entrega": entrega,
                "items": selectores.resumen_de_items(list(entrega.lineas.all())),
                "en_camino_desde": selectores.fecha_hora(entrega.despachada_en),
                "url": _url_de_recepcion(entrega, self.dispositivo, alcance),
                **_estado(entrega),
            }
            for entrega in pagina
        ]
        contexto = {
            "dispositivo": self.dispositivo,
            "filas": filas,
            "pagina": pagina,
            # Un enlace que va a rebotar no se ofrece: el detalle pide `dispositivo.ver`.
            "url_dispositivo": reverse("dispositivos:detalle", args=[self.dispositivo.pk]) if puede_ver else "",
        }
        return render(request, TEMPLATE_PENDIENTES, contexto)


class RecibirKitView(RecepcionKitsMixin, View):
    """El formulario de recepción: precargado con lo enviado, más el remito y la observación."""

    def _entrega(self, pk):
        # Del dispositivo de la URL y de un edificio del alcance de quien mira: la de otro es un 404.
        return get_object_or_404(selectores.entregas_de(self.dispositivo, self.request.user), pk=pk)

    def _render(self, request, entrega, form, status=200):
        contexto = {
            "dispositivo": self.dispositivo,
            "entrega": entrega,
            "form": form,
            "url_pendientes": self._url_pendientes(),
            # Si la recepción vino de la solapa Kits del edificio y el formulario vuelve con error, conserva el regreso.
            "siguiente": self._siguiente(request),
            "url_cancelar": self._destino(request),
            "suma_al_stock": servicio.suma_al_stock(self.dispositivo),
            **_estado(entrega),
        }
        return render(request, TEMPLATE_RECIBIR, contexto, status=status)

    def _ya_no_esta_abierta(self, request, entrega):
        messages.warning(request, servicio.mensaje_de_estado(entrega))
        return redirect(self._destino(request))

    def get(self, request, dispositivo, pk):
        entrega = self._entrega(pk)
        if not entrega.abierta:
            return self._ya_no_esta_abierta(request, entrega)
        alcance = _alcance_para_abrir_el_edificio(request.user, self.dispositivo)
        if entrega.edificio_id is not None and alcance.permite(entrega.edificio_id):
            # Cambio 586: la recepción se hace en la solapa Kits del edificio. Esta URL queda para el POST (que la
            # solapa usa), para las entregas anteriores al Cambio 523 (sin edificio) y para quien no puede abrir la
            # página del edificio (la guardia con solo ``emergencia.recibir_kit``): ellos reciben acá.
            return redirect(_url_de_recepcion(entrega, self.dispositivo, alcance))
        return self._render(request, entrega, self._form(entrega))

    def _form(self, entrega, *datos):
        """El formulario de la entrega; con el desplegable de edificio solo si hay que elegirlo (RN-010-07)."""

        return RecepcionKitForm(
            *datos,
            lineas=list(entrega.lineas.all()),
            edificios=servicio.edificios_para_recibir(self.request.user, entrega),
        )

    def post(self, request, dispositivo, pk):
        entrega = self._entrega(pk)
        form = self._form(entrega, request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, entrega, form, status=400)
        try:
            recibida = servicio.recibir_entrega(
                entrega,
                request.user,
                form.cantidades(),
                form.cleaned_data["remito"],
                observacion=form.cleaned_data["observacion"],
                edificio=form.edificio(),
            )
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return redirect(self._destino(request))
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._render(request, entrega, form, status=400)
        diferencias = selectores.diferencias_de(selectores.lineas_de(recibida))
        messages.success(request, f"Entrega {recibida.numero}: {selectores.texto_de_recepcion(diferencias).lower()}.")
        return redirect(self._destino(request))
