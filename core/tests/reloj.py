"""Congelar el reloj en un instante concreto, para los tests que dependen de «hoy».

Nace con el PR R-20 (TST-02/R0-03 y el flake de medianoche de DIS-01). El repo no
tiene `freezegun` y no se agrega una dependencia por esto: alcanza con parchear
`django.utils.timezone.now`, que es de donde salen `localtime()`, `localdate()` y
`timezone.now()` —las tres lo resuelven como global del mismo módulo—.

Para qué sirve, en concreto:

* Probar que un test no vuelve a depender de una fecha literal que vence
  (`programas.tests.test_becas_relevamientos.ConvocatoriaTests`, R0-03).
* Probar los bordes de día local sin esperar a la medianoche: un instante «hace
  cinco minutos» a las 00:02 ART es **ayer**, y eso ponía rojo un test una vez por
  día durante cinco minutos (`programas.tests.test_fechas_locales_dispositivos`).

No reemplaza a las pruebas de zona horaria del motor real: acá el reloj es de
Python, la base sigue siendo la de los tests.
"""

import zoneinfo
from contextlib import contextmanager
from unittest.mock import patch

#: La zona en la que opera el sistema (la misma de `settings.TIME_ZONE`).
ART = zoneinfo.ZoneInfo("America/Argentina/Buenos_Aires")


@contextmanager
def reloj_en(instante):
    """Congela `timezone.now()` —y con él `localtime()`/`localdate()`— en `instante`.

    `instante` tiene que ser un `datetime` **con** zona horaria: con `USE_TZ`
    activo, un naive haría estallar `localtime()` con el mismo error que en
    producción.
    """
    if instante.tzinfo is None:
        raise ValueError("reloj_en() necesita un datetime con zona horaria (USE_TZ está activo)")
    with patch("django.utils.timezone.now", return_value=instante):
        yield instante
