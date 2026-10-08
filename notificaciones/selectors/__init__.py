"""Lecturas de las campañas: listado, métricas y las tablas del detalle. Sin lógica de negocio.

Las métricas del mes van por **rango de fechas**, nunca con ``Trunc*`` sobre un
``DateTimeField``: la base de ECOM no tiene tablas de zona horaria y ``CONVERT_TZ``
devuelve ``NULL`` solo en producción (RNF-007-11).
"""

from __future__ import annotations

from datetime import datetime

from django.db.models import Count, Q
from django.utils import timezone

from notificaciones.models import Campana, Destinatario

MESES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def campanas_listado(*, q="", estado=""):
    """Las campañas del listado, filtradas por texto (nombre o asunto) y estado."""
    campanas = Campana.objects.select_related("creada_por", "enviada_por").defer("html_sanitizado", "texto_plano")
    q = (q or "").strip()
    if q:
        campanas = campanas.filter(Q(nombre__icontains=q) | Q(asunto__icontains=q))
    if estado in Campana.Estado.values:
        campanas = campanas.filter(estado=estado)
    return campanas.order_by("-creado", "-pk")


def rango_del_mes(ahora=None):
    """``(inicio, fin)`` del mes en curso en hora local, como ``datetime`` con zona."""
    local = timezone.localtime(ahora)
    inicio = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    siguiente = datetime(inicio.year + (inicio.month // 12), inicio.month % 12 + 1, 1)
    fin = timezone.make_aware(siguiente, inicio.tzinfo)
    return inicio, fin


def metricas_listado(ahora=None):
    """Los cuatro números de arriba del listado, en tres consultas."""
    inicio, fin = rango_del_mes(ahora)
    terminadas = (Campana.Estado.ENVIADA, Campana.Estado.ENVIADA_CON_ERRORES)
    por_estado = Campana.objects.aggregate(
        a_enviar=Count("pk", filter=Q(estado=Campana.Estado.A_ENVIAR)),
        enviando=Count("pk", filter=Q(estado=Campana.Estado.ENVIANDO)),
        enviadas_mes=Count("pk", filter=Q(estado__in=terminadas, finalizada_en__gte=inicio, finalizada_en__lt=fin)),
        con_errores_mes=Count(
            "pk",
            filter=Q(estado=Campana.Estado.ENVIADA_CON_ERRORES, finalizada_en__gte=inicio, finalizada_en__lt=fin),
        ),
    )
    correos = Destinatario.objects.aggregate(
        enviados=Count("pk", filter=Q(estado=Destinatario.Estado.ENVIADO, enviado_en__gte=inicio, enviado_en__lt=fin)),
        fallidos=Count("pk", filter=Q(estado=Destinatario.Estado.FALLIDO, modificado__gte=inicio, modificado__lt=fin)),
    )
    return {
        **por_estado,
        "correos_enviados_mes": correos["enviados"],
        "correos_fallidos_mes": correos["fallidos"],
        "mes": MESES[inicio.month - 1],
    }


def destinatarios_de(campana, *, q="", estado=""):
    destinatarios = Destinatario.objects.filter(campana=campana)
    q = (q or "").strip().lower()
    if q:
        destinatarios = destinatarios.filter(email__icontains=q)
    if estado in Destinatario.Estado.values:
        destinatarios = destinatarios.filter(estado=estado)
    return destinatarios.order_by("fila_excel", "pk")


def descartados_de(campana):
    return campana.descartados.order_by("fila_excel", "pk")


def primer_destinatario(campana):
    return (
        Destinatario.objects.filter(campana=campana)
        .order_by("fila_excel", "pk")
        .values_list("email", flat=True)
        .first()
    )
