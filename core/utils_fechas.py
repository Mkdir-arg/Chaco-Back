"""Fechas locales para consultas: rangos de ``datetime`` en vez de ``__date`` (DIS-01).

Toda la base corre con ``USE_TZ=True`` y guarda los ``DateTimeField`` en UTC. Para
preguntar «qué pasó el día X en hora argentina» hay dos caminos:

* ``campo__date=X`` o ``TruncDate(campo)``: Django se lo delega al motor, que en
  MySQL y MariaDB es ``DATE(CONVERT_TZ(campo,'UTC','America/Argentina/Buenos_Aires'))``.
  **La base de ECOM no tiene cargadas las tablas de zona horaria**, así que
  ``CONVERT_TZ`` devuelve NULL: el filtro no matchea nada, los conteos salen en cero
  y nadie se entera, porque en SQLite —donde corre la suite— el mismo lookup da bien.
  Ya costó tres incidentes (Cambios 64 y 66, y DIS-01).
* Un rango semiabierto ``[inicio_del_día_local, inicio_del_día_siguiente_local)``
  calculado **en Python**: el motor solo compara la columna contra dos parámetros,
  así que no depende de ninguna tabla del servidor y la condición es **sargable**
  —puede apoyarse en el índice de esa columna, donde lo haya; envuelta en
  ``CONVERT_TZ`` no, ni existiendo—. Es lo que hace este módulo, y es lo que ya
  hacían ``dashboard_becas._serie_semanal`` y ``dashboard.api_views.tendencias_datos``
  a mano.

La guardia que impide volver atrás es ``core/tests/test_sql_portable.py``; la forma
del SQL compilado la fija ``core/tests/test_sql_motor_real.py`` y la ejecución real
contra MariaDB sin tablas de zona horaria, ``core/tests/test_motor_real.py``.
"""

from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

__all__ = [
    "a_fecha",
    "fecha_local",
    "inicio_del_dia_local",
    "q_rango_local",
    "rango_dia_local",
    "rango_periodo_local",
]


def a_fecha(valor):
    """Normaliza a ``date``: acepta ``date``, ``datetime`` (lo pasa a hora local) o ISO.

    Devuelve ``None`` para ``None`` o cadena vacía, así el llamador puede pasar
    directo lo que vino de un ``request.GET`` sin ramificar.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return timezone.localtime(valor).date() if timezone.is_aware(valor) else valor.date()
    if isinstance(valor, date):
        return valor
    fecha = parse_date(str(valor))
    if fecha is None:
        raise ValueError(f"No es una fecha: {valor!r}")
    return fecha


def fecha_local(valor):
    """Fecha en hora local de un ``datetime`` guardado en UTC.

    Un ingreso de las 22:30 del 9/9 en Argentina está guardado como 01:30 UTC del
    10/9: ``valor.date()`` devolvería el día equivocado.
    """
    if valor is None:
        return None
    return a_fecha(valor)


def inicio_del_dia_local(fecha):
    """``datetime`` consciente de las 00:00 locales del día de ``fecha``."""
    return timezone.make_aware(datetime.combine(a_fecha(fecha), time.min), timezone.get_current_timezone())


def rango_dia_local(fecha):
    """``(inicio, fin)`` semiabierto que cubre el día local de ``fecha``.

    ``fin`` son las 00:00 del día siguiente: se compara con ``__lt``, nunca con
    ``__lte``, para no dejar afuera ni contar dos veces la medianoche.
    """
    inicio = inicio_del_dia_local(fecha)
    return inicio, inicio + timedelta(days=1)


def rango_periodo_local(desde=None, hasta=None):
    """``(inicio, fin)`` del período local ``[desde, hasta]``, con extremos opcionales.

    ``hasta`` es **inclusivo** como fecha (es lo que entiende quien completa un
    filtro «hasta el 30/09»), y se traduce a un ``fin`` exclusivo: las 00:00 del
    1/10. Cada extremo ausente devuelve ``None``.
    """
    inicio = inicio_del_dia_local(desde) if a_fecha(desde) else None
    fin = rango_dia_local(hasta)[1] if a_fecha(hasta) else None
    return inicio, fin


def q_rango_local(campo, desde=None, hasta=None):
    """``Q`` que acota un ``DateTimeField`` al período local ``[desde, hasta]``.

    Reemplazo directo de ``Q(campo__date__gte=desde, campo__date__lte=hasta)``.
    Sin extremos devuelve un ``Q()`` vacío (no filtra), igual que el código que
    reemplaza.
    """
    inicio, fin = rango_periodo_local(desde, hasta)
    condicion = Q()
    if inicio is not None:
        condicion &= Q(**{f"{campo}__gte": inicio})
    if fin is not None:
        condicion &= Q(**{f"{campo}__lt": fin})
    return condicion
