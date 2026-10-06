"""Cálculo y persistencia transaccional del parte diario F-01."""

from django.db import IntegrityError, transaction
from django.db.models import Q

from core.utils_fechas import rango_dia_local
from programas.models import Admision, Cama, Dispositivo, RegistroDiario


def calcular_cantidades(*, dispositivo, fecha, bloquear=False):
    """Devuelve el snapshot A-E a partir de movimientos y camas reales.

    El día se acota con el rango local ``[00:00, 00:00 del día siguiente)`` y no con
    ``fecha_ingreso__date=fecha``: ese lookup se traduce a ``CONVERT_TZ`` y en ECOM
    —MariaDB sin tablas de zona horaria— devuelve NULL, así que el parte se guardaba
    con ingresos y egresos en cero (DIS-01).
    """
    inicio_del_dia, fin_del_dia = rango_dia_local(fecha)
    ingresos_del_dia = Q(fecha_ingreso__gte=inicio_del_dia, fecha_ingreso__lt=fin_del_dia)
    egresos_del_dia = Q(fecha_egreso__gte=inicio_del_dia, fecha_egreso__lt=fin_del_dia)
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
        admisiones_con_cama.filter(fecha_ingreso__lt=fin_del_dia)
        .filter(Q(fecha_egreso__isnull=True) | Q(fecha_egreso__gte=fin_del_dia))
        .count()
    )
    return {
        "camas_totales": camas_totales,
        "ingresos": admisiones_con_cama.filter(ingresos_del_dia).count(),
        "egresos": admisiones.filter(egresos_del_dia).count(),
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
