"""RN-22 —la edad y el corte de los 18 años— escrita una sola vez (RED-50).

La cuenta estaba **cuatro** veces (``becas.es_menor``, ``condiciones.edad_en_anios``,
``siis_envio._edad`` y ``corregir_datos_siis._edad``) y tres de las cuatro resolvían
«hoy» con ``date.today()``, que es el día del **sistema**. Ni el ``Dockerfile`` ni los
compose ni ``docker/k8s/*.yaml`` definen ``TZ``: los contenedores corren en UTC, así
que entre las 21:00 y las 24:00 de Chaco ``date.today()`` ya contesta el día
siguiente. Un caso cargado a las 22:00 de la víspera del cumpleaños 18 se evaluaba
**mayor** y el formulario dejaba de pedir apoderado; lo mismo viajaba a SIIS. En los
tests no se veía, porque las máquinas de desarrollo están en hora de Argentina.

Acá «hoy» sale siempre de :func:`django.utils.timezone.localdate`, que respeta el
``TIME_ZONE`` del proyecto y no el del contenedor. Quien necesite evaluar la edad a
una fecha distinta de hoy —la revisión, que vuelve a mirar un caso cargado hace un
mes (BEC-03)— pasa ``hoy`` explícito.

El guardarraíl para que no vuelva a aparecer un cuarto cálculo es la regla ``DTZ011``
de ruff (``pyproject.toml``), que prohíbe ``date.today()`` en el código productivo.
"""

from datetime import date, datetime

from django.utils import timezone

#: RN-22: desde los 18 años cumplidos la persona ya no necesita apoderado.
MAYORIA_DE_EDAD = 18

__all__ = ["MAYORIA_DE_EDAD", "edad_en_anios", "es_menor", "fecha_o_none"]


def fecha_o_none(valor):
    """``date`` de lo que sea que haya llegado, o ``None`` si no se entiende.

    Es deliberadamente permisiva —acepta ``date``, ``datetime`` y los dos formatos
    que escriben el front y la app (``YYYY-MM-DD`` y ``dd/mm/aaaa``)— y
    deliberadamente silenciosa: el motor de condiciones la llama sobre lo que
    respondió una persona, donde «no es una fecha» es un dato posible y no un
    error. Una fecha ilegible tiene que dar ``None``, nunca una edad inventada.
    """
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        for formato in ("%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(texto, formato).date()
            except ValueError:
                continue
    return None


def edad_en_anios(fecha_nacimiento, hoy=None):
    """Años cumplidos a ``hoy`` (por defecto, la fecha **local**).

    Devuelve ``None`` si no hay fecha o es ilegible: la edad no se puede
    determinar, y eso es distinto de cero.
    """
    nacimiento = fecha_o_none(fecha_nacimiento)
    if nacimiento is None:
        return None
    hoy = hoy or timezone.localdate()
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def es_menor(fecha_nacimiento, hoy=None):
    """¿Es menor de :data:`MAYORIA_DE_EDAD` a ``hoy`` (RN-22)?

    ``None`` si no hay fecha: no se puede determinar, y el llamador tiene que
    poder distinguirlo de «es mayor».
    """
    edad = edad_en_anios(fecha_nacimiento, hoy)
    return None if edad is None else edad < MAYORIA_DE_EDAD
