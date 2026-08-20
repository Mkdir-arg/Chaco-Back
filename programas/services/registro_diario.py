"""Cálculo y persistencia transaccional del parte diario F-01."""

from datetime import datetime, time

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from programas.models import Admision, Cama, Dispositivo, RegistroDiario


def _fin_del_dia(fecha):
    return timezone.make_aware(datetime.combine(fecha, time.max), timezone.get_current_timezone())


def calcular_cantidades(*, dispositivo, fecha, bloquear=False):
    """Devuelve el snapshot A-E a partir de movimientos y camas reales."""
    fin_del_dia = _fin_del_dia(fecha)
    admisiones = Admision.objects.filter(dispositivo=dispositivo)
    camas = dispositivo.camas.all()
    if bloquear:
        # Mantiene un snapshot consistente con egresos/promociones, que bloquean primero la admisión y luego la cama.
        list(admisiones.select_for_update().values_list("pk", flat=True))
        list(camas.select_for_update().values_list("pk", flat=True))
    camas_totales = camas.count()
    fuera_servicio = camas.filter(estado=Cama.Estado.FUERA_SERVICIO).count()
    admisiones_con_cama = admisiones.filter(cama__isnull=False)
    ocupacion_nocturna = (
        admisiones_con_cama.filter(fecha_ingreso__lte=fin_del_dia)
        .filter(Q(fecha_egreso__isnull=True) | Q(fecha_egreso__gt=fin_del_dia))
        .count()
    )
    return {
        "camas_totales": camas_totales,
        "ingresos": admisiones_con_cama.filter(fecha_ingreso__date=fecha).count(),
        "egresos": admisiones.filter(fecha_egreso__date=fecha).count(),
        "ocupacion_nocturna": ocupacion_nocturna,
        "camas_disponibles": max(camas_totales - ocupacion_nocturna - fuera_servicio, 0),
    }


@transaction.atomic
def registrar_parte_diario(*, dispositivo, fecha, turno, usuario, observaciones=None, observaciones_generales=""):
    """Crea o actualiza el único parte de un turno, recalculando sus métricas."""
    if turno not in RegistroDiario.Turno.values:
        raise ValueError("El turno debe ser mañana, tarde o noche.")
    dispositivo = Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
    if dispositivo.estado != Dispositivo.Estado.ACTIVO:
        raise ValueError("El dispositivo debe estar activo para registrar el parte diario.")
    defaults = {
        **calcular_cantidades(dispositivo=dispositivo, fecha=fecha, bloquear=True),
        "observaciones": observaciones or {},
        "observaciones_generales": observaciones_generales,
        "firmado_por": usuario,
    }
    try:
        with transaction.atomic():
            parte, creado = RegistroDiario.objects.get_or_create(
                dispositivo=dispositivo, fecha=fecha, turno=turno, defaults=defaults
            )
    except IntegrityError:
        parte = RegistroDiario.objects.get(dispositivo=dispositivo, fecha=fecha, turno=turno)
        creado = False
    if not creado:
        for campo, valor in defaults.items():
            setattr(parte, campo, valor)
        parte.save(update_fields=[*defaults.keys(), "modificado"])
    return parte
