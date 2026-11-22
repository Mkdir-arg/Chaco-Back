"""Lo que las pantallas de Dispositivos comparten para leer parámetros de una URL sin confiar en ellos.

Vive fuera de `programas/views/` y no importa nada de vistas: lo usan servicios, selectores y vistas por igual.
`programas.views.ajax_utils` re-exporta `destino_seguro` y `con_parametro` para los consumidores de siempre.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.utils.http import url_has_allowed_host_and_scheme


def destino_seguro(request, defecto, *, desde=("POST",), prefijo=""):
    """El ``next`` de la request, solo si vuelve a este sitio; si no, ``defecto``.

    Un link preparado con ``next=https://malo.tld`` no puede sacar al operador del backoffice: se descarta lo que
    apunte a otro host o esquema (``//malo.tld/x``, ``javascript:...``). ``desde`` dice dónde se busca (``POST``,
    ``GET`` o las dos, en ese orden: la primera que lo traiga) y ``prefijo``, si se pide, acota además la ruta a una
    parte del sistema (``"/becas/"``). Es la única copia: la usan Equipo, convocatorias, la revisión de Becas, Kits
    y las acciones de Sectores y plazas.
    """

    for origen in desde:
        candidato = getattr(request, origen).get("next") or ""
        if candidato:
            break
    else:
        return defecto
    if not url_has_allowed_host_and_scheme(
        candidato, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return defecto
    if prefijo and not candidato.startswith(prefijo):
        return defecto
    return candidato


def con_parametro(url, nombre, valor):
    """``url`` con ``nombre=valor`` en su query (reemplaza el que hubiera); el resto de la URL queda igual."""

    partes = urlsplit(url)
    consulta = [(k, v) for k, v in parse_qsl(partes.query, keep_blank_values=True) if k != nombre]
    consulta.append((nombre, str(valor)))
    return urlunsplit(partes._replace(query=urlencode(consulta)))


def entero_de_parametro(valor, max_digitos=None):
    """El id de un parámetro GET, o `None`. Solo dígitos ASCII: un superíndice o un dígito
    arábigo pasan `isdigit()` y rompen `int()`. ``max_digitos`` descarta lo que no cabe en una columna."""

    texto = str(valor or "").strip()
    if not (texto.isascii() and texto.isdecimal()):
        return None
    if max_digitos is not None and len(texto) > max_digitos:
        return None
    return int(texto)
