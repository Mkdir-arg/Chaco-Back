"""Pantallas de las campañas de correo (análisis 007). Orquestación HTTP, sin lógica de dominio.

Permisos (RN-007-12): ``notificacion.ver`` para mirar, ``notificacion.gestionar`` para
armar, probar, duplicar y borrar, ``notificacion.enviar`` para enviar, detener y
reanudar. Las pantallas (GET) sin la capacidad redirigen con aviso, como el resto del
backoffice; las acciones (POST) responden **403**: el botón no se dibuja, así que un POST
sin la capacidad es un pedido armado a mano.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import ListView

from core import rbac
from core.rbac import CapacidadRequeridaMixin, requiere
from core.services.throttle import rate_limit_excedido
from notificaciones import selectors
from notificaciones.forms import CampanaForm, PruebaForm
from notificaciones.models import Campana, Destinatario
from notificaciones.services import campanas as servicio
from notificaciones.services import envio
from notificaciones.services.exportacion import plantilla_xlsx, resultado_xlsx
from notificaciones.services.html import documento

CAP_VER = "notificacion.ver"
CAP_GESTIONAR = "notificacion.gestionar"
CAP_ENVIAR = "notificacion.enviar"

PAGINA = 25
#: RN-007-16: diez pruebas por usuario por hora.
PRUEBAS_POR_HORA = 10
CUBETA_PRUEBAS = "notif_prueba"

#: La vista previa se sirve con su propia política: nada de scripts, ni conexiones, ni
#: formularios; solo imágenes y fuentes externas por https, estilos en línea, y que la
#: pueda embeber únicamente el propio backoffice (RNF-007-04).
# Las directivas `*-src` se arman con el sufijo aparte: el literal «font-src» tiene forma
# de utilidad de Tailwind y `CssCompiladoAlDiaTests` (que lee los `.py` de las apps) lo
# tomaría por una clase usada que el build no tiene.
_FUENTES_VISTA_PREVIA = {"default": "'none'", "img": "https: data:", "style": "'unsafe-inline'", "font": "https: data:"}
_OTRAS_VISTA_PREVIA = {"frame-ancestors": "'self'", "base-uri": "'none'", "form-action": "'none'"}
CSP_VISTA_PREVIA = "; ".join(
    [
        *(f"{tipo}-src {valor}" for tipo, valor in _FUENTES_VISTA_PREVIA.items()),
        *(f"{directiva} {valor}" for directiva, valor in _OTRAS_VISTA_PREVIA.items()),
    ]
)
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _exigir(request, codigo):
    if not rbac.puede(request.user, codigo):
        raise PermissionDenied("No tiene permisos para realizar esta acción.")


def _numero(valor):
    return f"{valor:,}".replace(",", ".")


def _migas(campana=None, actual=None):
    migas = [
        {"label": "Notificaciones", "url": reverse("notificaciones:campanas")},
        {"label": "Campañas", "url": reverse("notificaciones:campanas")},
    ]
    if campana is not None:
        migas.append({"label": campana.nombre, "url": reverse("notificaciones:campana_detalle", args=[campana.pk])})
    if actual:
        migas.append({"label": actual, "url": ""})
    return migas


def _xlsx(contenido, nombre):
    respuesta = HttpResponse(contenido, content_type=XLSX)
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta


# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------
class CampanaListView(CapacidadRequeridaMixin, LoginRequiredMixin, ListView):
    capacidades_requeridas = CAP_VER
    template_name = "notificaciones/campana_list.html"
    context_object_name = "campanas"
    paginate_by = PAGINA

    def get_queryset(self):
        return selectors.campanas_listado(q=self.request.GET.get("q", ""), estado=self.request.GET.get("estado", ""))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        metricas = selectors.metricas_listado()
        ctx.update(
            {
                "estados": Campana.Estado.choices,
                "estado_actual": self.request.GET.get("estado", ""),
                "puede_crear": rbac.puede(self.request.user, CAP_GESTIONAR),
                "puede_gestionar": rbac.puede(self.request.user, CAP_GESTIONAR),
                "metricas": metricas,
                "tarjetas": {
                    "enviadas_etiqueta": f"Campañas enviadas · {metricas['mes']}",
                    "enviadas_nota": (
                        f"{metricas['con_errores_mes']} con errores" if metricas["con_errores_mes"] else ""
                    ),
                    "correos_etiqueta": f"Correos enviados · {metricas['mes']}",
                    "correos_valor": _numero(metricas["correos_enviados_mes"]),
                    "correos_nota": (
                        f"{_numero(metricas['correos_fallidos_mes'])} fallidos"
                        if metricas["correos_fallidos_mes"]
                        else ""
                    ),
                },
            }
        )
        return ctx


# ---------------------------------------------------------------------------
# Alta y edición
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_GESTIONAR)
def campana_crear(request):
    form = CampanaForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        campana = servicio.crear_campana(
            nombre=form.cleaned_data["nombre"],
            asunto=form.cleaned_data["asunto"],
            archivo_excel=form.cleaned_data["archivo_excel"],
            archivo_html=form.cleaned_data["archivo_html"],
            lectura=form.lectura,
            datos_html=form.datos_html,
            usuario=request.user,
        )
        messages.success(
            request, f"Campaña creada con {_numero(campana.total)} destinatarios. Revisala antes de enviar."
        )
        return redirect("notificaciones:campana_detalle", pk=campana.pk)
    return render(
        request,
        "notificaciones/campana_form.html",
        {"form": form, "campana": None, "migas": _migas(actual="Nueva campaña")},
    )


@login_required
@requiere(CAP_GESTIONAR)
def campana_editar(request, pk):
    campana = get_object_or_404(Campana, pk=pk)
    if not campana.editable:
        messages.error(request, "Solo se puede editar una campaña que está «A enviar».")
        return redirect("notificaciones:campana_detalle", pk=campana.pk)
    if request.method == "POST":
        form = CampanaForm(request.POST, request.FILES, campana=campana)
        if form.is_valid():
            try:
                servicio.editar_campana(
                    campana,
                    nombre=form.cleaned_data["nombre"],
                    asunto=form.cleaned_data["asunto"],
                    archivo_excel=form.cleaned_data.get("archivo_excel") or None,
                    archivo_html=form.cleaned_data.get("archivo_html") or None,
                    lectura=form.lectura,
                    datos_html=form.datos_html,
                )
            except servicio.TransicionInvalida as exc:
                messages.error(request, str(exc))
                return redirect("notificaciones:campana_detalle", pk=campana.pk)
            messages.success(request, "Campaña actualizada.")
            return redirect("notificaciones:campana_detalle", pk=campana.pk)
    else:
        form = CampanaForm(initial={"nombre": campana.nombre, "asunto": campana.asunto}, campana=campana)
    return render(
        request,
        "notificaciones/campana_form.html",
        {"form": form, "campana": campana, "migas": _migas(campana, "Editar")},
    )


@login_required
@requiere(CAP_GESTIONAR)
@require_GET
def plantilla_excel(request):
    return _xlsx(plantilla_xlsx(), "plantilla_destinatarios.xlsx")


# ---------------------------------------------------------------------------
# Detalle (previsualización y avance)
# ---------------------------------------------------------------------------
@login_required
@requiere(CAP_VER)
def campana_detalle(request, pk):
    campana = get_object_or_404(Campana.objects.select_related("creada_por", "enviada_por"), pk=pk)
    conteos = envio.contar_por_estado(campana.pk)
    q = request.GET.get("q", "")
    estado_destinatario = request.GET.get("estado", "")
    destinatarios = Paginator(selectors.destinatarios_de(campana, q=q, estado=estado_destinatario), PAGINA).get_page(
        request.GET.get("destinatarios_page")
    )
    descartados = Paginator(selectors.descartados_de(campana), PAGINA).get_page(request.GET.get("descartados_page"))

    pendientes = conteos[Destinatario.Estado.PENDIENTE]
    enviados = conteos[Destinatario.Estado.ENVIADO]
    fallidos = conteos[Destinatario.Estado.FALLIDO]
    interrumpida = campana.interrumpida
    en_curso = campana.estado == Campana.Estado.ENVIANDO and not interrumpida
    tab_por_defecto = "vista" if campana.editable else "destinatarios"
    puede_gestionar = rbac.puede(request.user, CAP_GESTIONAR)
    puede_enviar = rbac.puede(request.user, CAP_ENVIAR)

    ctx = {
        "campana": campana,
        "migas": _migas(campana),
        "tab_por_defecto": tab_por_defecto,
        "stats": {
            "total": _numero(campana.total),
            "leidas": _numero(campana.leidas),
            "invalidos": _numero(campana.invalidos),
            "duplicados": _numero(campana.duplicados),
            "enviados": _numero(enviados),
            "fallidos": _numero(fallidos),
            "pendientes": _numero(pendientes),
        },
        "hay_fallidos": fallidos > 0,
        "avance": (
            f"Van {_numero(enviados + fallidos)} de {_numero(campana.total)} correos. "
            "Podés cerrar esta pantalla y volver a ver el avance."
        ),
        "n_destinatarios": _numero(campana.total),
        "n_descartados": _numero(campana.descartados_total),
        "destinatarios": destinatarios,
        "descartados": descartados,
        "estados_destinatario": Destinatario.Estado.choices,
        "estado_destinatario_actual": estado_destinatario,
        "interrumpida": interrumpida,
        "en_curso": en_curso,
        "remitente": settings.DEFAULT_FROM_EMAIL,
        "asunto_final": envio.asunto_de(campana),
        "primer_destinatario": selectors.primer_destinatario(campana),
        "puede_gestionar": puede_gestionar and campana.editable,
        "puede_duplicar": puede_gestionar,
        "puede_enviar": puede_enviar and campana.editable,
        "puede_detener": puede_enviar and campana.estado == Campana.Estado.ENVIANDO,
        "puede_reanudar": puede_enviar and interrumpida,
        "prueba_form": PruebaForm(initial={"email": request.user.email}),
        "texto_confirmar_envio": (
            f"Se van a enviar {_numero(campana.total)} correos, uno a cada persona, con el asunto "
            f"«{campana.asunto}»."
            + (
                f" {_numero(campana.descartados_total)} filas descartadas del Excel no se envían."
                if campana.descartados_total
                else ""
            )
            + " El envío corre en segundo plano. Esta acción no se puede deshacer."
        ),
        "texto_confirmar_reanudar": (
            f"Se envía solo a los {_numero(pendientes)} pendientes: nadie recibe el correo dos veces."
        ),
    }
    return render(request, "notificaciones/campana_detail.html", ctx)


@xframe_options_sameorigin
@login_required
@requiere(CAP_VER)
@require_GET
def vista_previa_html(request, pk):
    """El correo saneado tal como llega, para el ``iframe sandbox`` del detalle (RNF-007-04).

    Nunca se inyecta en la página del backoffice: se sirve acá, aparte, con una CSP propia
    que no deja ejecutar nada ni conectarse a ningún lado, y ``X-Frame-Options: SAMEORIGIN``
    para que solo lo pueda embeber el propio sitio. El middleware de seguridad respeta la
    CSP que ya trae la respuesta (``setdefault``).
    """
    campana = get_object_or_404(Campana, pk=pk)
    respuesta = HttpResponse(documento(campana.html_sanitizado), content_type="text/html; charset=utf-8")
    respuesta["Content-Security-Policy"] = CSP_VISTA_PREVIA
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Referrer-Policy"] = "no-referrer"
    respuesta["Cache-Control"] = "no-store, private"
    return respuesta


@login_required
@requiere(CAP_VER)
@require_GET
def exportar_resultado(request, pk):
    campana = get_object_or_404(Campana, pk=pk)
    sello = timezone.localtime().strftime("%Y%m%d_%H%M")
    return _xlsx(resultado_xlsx(campana), f"campana_{campana.pk}_destinatarios_{sello}.xlsx")


# ---------------------------------------------------------------------------
# Acciones (POST)
# ---------------------------------------------------------------------------
@login_required
@require_POST
def campana_eliminar(request, pk):
    _exigir(request, CAP_GESTIONAR)
    campana = get_object_or_404(Campana, pk=pk)
    try:
        servicio.eliminar_campana(campana)
    except servicio.TransicionInvalida as exc:
        messages.error(request, str(exc))
        return redirect("notificaciones:campana_detalle", pk=campana.pk)
    messages.success(request, f"Se eliminó la campaña «{campana.nombre}».")
    return redirect("notificaciones:campanas")


@login_required
@require_POST
def campana_duplicar(request, pk):
    _exigir(request, CAP_GESTIONAR)
    campana = get_object_or_404(Campana, pk=pk)
    try:
        copia = servicio.duplicar_campana(campana, usuario=request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return redirect("notificaciones:campana_detalle", pk=campana.pk)
    messages.success(request, f"Se creó «{copia.nombre}». Revisá los datos antes de enviarla.")
    return redirect("notificaciones:campana_editar", pk=copia.pk)


@login_required
@require_POST
def campana_enviar(request, pk):
    _exigir(request, CAP_ENVIAR)
    campana = get_object_or_404(Campana, pk=pk)
    try:
        campana = envio.iniciar_envio(campana, usuario=request.user)
    except servicio.TransicionInvalida as exc:
        messages.error(request, str(exc))
        return redirect("notificaciones:campana_detalle", pk=campana.pk)
    envio.lanzar(campana)
    messages.success(request, f"Empezó el envío de {_numero(campana.total)} correos. La pantalla se actualiza sola.")
    return redirect(f"{reverse('notificaciones:campana_detalle', args=[campana.pk])}?tab=destinatarios")


@login_required
@require_POST
def campana_detener(request, pk):
    _exigir(request, CAP_ENVIAR)
    campana = get_object_or_404(Campana, pk=pk)
    try:
        cancelada = envio.pedir_detencion(campana)
    except servicio.TransicionInvalida as exc:
        messages.error(request, str(exc))
        return redirect("notificaciones:campana_detalle", pk=campana.pk)
    if cancelada:
        messages.success(request, "Se detuvo el envío. Lo enviado quedó enviado; los pendientes no se envían.")
    else:
        messages.success(request, "Se pidió detener el envío. Corta al terminar el correo que está mandando.")
    return redirect("notificaciones:campana_detalle", pk=campana.pk)


@login_required
@require_POST
def campana_reanudar(request, pk):
    _exigir(request, CAP_ENVIAR)
    campana = get_object_or_404(Campana, pk=pk)
    try:
        campana = envio.preparar_reanudacion(campana)
    except servicio.TransicionInvalida as exc:
        messages.error(request, str(exc))
        return redirect("notificaciones:campana_detalle", pk=campana.pk)
    envio.lanzar(campana)
    messages.success(request, "Se reanudó el envío con los pendientes.")
    return redirect(f"{reverse('notificaciones:campana_detalle', args=[campana.pk])}?tab=destinatarios")


@login_required
@require_POST
def campana_prueba(request, pk):
    """«Enviar prueba» desde el popup (``data-ajax``): responde con el contrato JSON del guardado AJAX."""
    _exigir(request, CAP_GESTIONAR)
    campana = get_object_or_404(Campana, pk=pk)
    if not campana.editable:
        return JsonResponse(
            {"ok": False, "message": "La prueba se manda solo mientras la campaña está «A enviar»."}, status=409
        )
    form = PruebaForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    if rate_limit_excedido(
        request, CUBETA_PRUEBAS, PRUEBAS_POR_HORA, 3600, sufijo=str(request.user.pk), incluir_ip=False
    ):
        return JsonResponse(
            {"ok": False, "message": f"Llegaste al límite de {PRUEBAS_POR_HORA} pruebas por hora. Probá más tarde."},
            status=429,
        )
    email = form.cleaned_data["email"]
    ok, error = envio.enviar_prueba(campana, email, usuario=request.user)
    if not ok:
        return JsonResponse({"ok": False, "message": f"No se pudo enviar la prueba a {email}: {error}"}, status=502)
    return JsonResponse({"ok": True, "message": f"Se envió la prueba a {email}."})
