"""`/media/`: quién puede bajar **qué** archivo (SEC-09 etapa 2).

La etapa 1 (#538) sacó `/media/` de nginx y lo dejó detrás de `login_required`.
Eso cerró lo que podía mirar cualquiera desde internet, pero adentro quedaba
todo abierto: con una sesión de backoffice —la de un territorial de Becas, la de
un operador de Merenderos, la de una cuenta recién creada sin un solo rol— se
bajaba el Excel del padrón de cualquier convocatoria, el F-00 de cualquier
dispositivo y la foto de DNI de cualquier ciudadano. `login_required` era todo
el control.

Acá se resuelve el **dueño** del archivo por el prefijo de su ruta y se evalúa
la misma capacidad, con el mismo alcance, que pide la pantalla por la que ese
archivo se ve. Las reglas están en :data:`REGLAS`, una por prefijo; un prefijo
que no está en la tabla no se sirve (404 y un aviso en el log, que es la forma
de enterarse de que un modelo nuevo se olvidó de registrarse).

Decisiones que vale la pena tener escritas:

- **Por nombre de archivo, no por id.** El dueño se busca con el `name` que tiene
  la fila (`Adjunto.objects.filter(archivo=ruta)`), así que los blobs guardados
  antes del `upload_to` con UUID se siguen bajando sin renombrar nada.
- **Sin fila, 404.** Un blob huérfano en el disco no tiene quién lo autorice.
- **Siempre `attachment` + `nosniff`,** igual que el bloque `/protected-media/`
  de nginx: es lo que evita que un archivo subido se interprete como HTML en el
  origen del sitio (la mitigación de fondo de SEC-15). Los `<img>` del detalle
  del ciudadano y de las respuestas de Becas no se ven afectados: la carga de
  subrecursos ignora `Content-Disposition`.
- **`MEDIA_X_ACCEL` cambia quién entrega los bytes, nunca quién puede.** Apagado
  —el default, que es el comportamiento de hoy— los entrega Django con
  `FileResponse`. Prendido, la respuesta sale vacía con
  `X-Accel-Redirect: /protected-media/<ruta>` y los entrega el servidor de
  adelante sin pasar por Python. Lo segundo necesita que el ingress tenga ese
  `location internal` (nginx ya lo tiene; en ECOM es D-09/H-05), por eso viene
  apagado.
"""

import logging
import posixpath
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponse
from django.utils._os import safe_join
from django.views.decorators.http import require_safe

from core import rbac
from core import rutas_media as rutas

logger = logging.getLogger(__name__)

#: Lo que nginx expone como `location internal` para `X-Accel-Redirect`.
PREFIJO_INTERNO = "/protected-media/"


def _ruta_segura(path):
    """Ruta relativa normalizada, o ``None`` si no puede ser un archivo de `media/`.

    Corta tres cosas: salir de `MEDIA_ROOT` (`../`), los separadores de Windows
    —que `safe_join` no mira en POSIX— y los caracteres de control. Los dos
    últimos importan sobre todo con `X-Accel-Redirect`: la ruta termina adentro
    de un header, y un `\\r\\n` ahí parte la respuesta en dos.
    """
    if not path:
        return None
    if any(c in path for c in "\r\n\x00"):
        return None
    normal = posixpath.normpath(path.replace("\\", "/"))
    if normal in (".", "/") or normal.startswith("/") or normal == ".." or normal.startswith("../"):
        return None
    try:
        safe_join(settings.MEDIA_ROOT, normal)
    except (SuspiciousFileOperation, ValueError):
        return None
    return normal


# --------------------------------------------------------------------------- #
# Resolución del dueño, un prefijo por superficie.
#
# Cada resolver devuelve True (puede), False (403) o None (no hay dueño → 404).
# Los imports son diferidos a propósito: `core` lo carga medio repo y no puede
# depender de `legajos` ni de `programas` al importarse.
# --------------------------------------------------------------------------- #


def _adjunto_de_legajo(user, ruta):
    from legajos.models import Adjunto

    if not Adjunto.objects.filter(archivo=ruta).exists():
        return None
    return rbac.puede(user, "ciudadano.ver")


def _foto_de_ciudadano(user, ruta):
    from legajos.models import Ciudadano

    if not Ciudadano.objects.filter(foto=ruta).exists():
        return None
    return rbac.puede(user, "ciudadano.ver")


def _archivo_de_contacto(user, ruta):
    from legajos.models import HistorialContacto

    if not HistorialContacto.objects.filter(archivo_adjunto=ruta).exists():
        return None
    return rbac.puede(user, "ciudadano.ver")


def _archivo_de_f00(user, ruta):
    """El F-00 se mira con el alcance del dispositivo, no con el del programa."""
    from programas.models import ArchivoAdmision
    from programas.services.dispositivos import CAP_VER, puede_operar_dispositivo

    archivo = ArchivoAdmision.objects.select_related("admision__dispositivo").filter(archivo=ruta).first()
    if archivo is None:
        return None
    return puede_operar_dispositivo(user, archivo.admision.dispositivo, CAP_VER)


def _documentacion_de_merendero(user, ruta):
    from programas.models import SolicitudMerendero
    from programas.services.merenderos import puede_en_merenderos

    if not SolicitudMerendero.objects.filter(documentacion=ruta).exists():
        return None
    return puede_en_merenderos(user, "merendero.ver")


def _adjunto_de_becas(user, ruta):
    from programas.models import AdjuntoFormulario
    from programas.services.autorizacion import assert_alcance_formulario

    adjunto = (
        AdjuntoFormulario.objects.select_related("formulario__relevamiento__segmento").filter(archivo=ruta).first()
    )
    if adjunto is None:
        return None
    try:
        assert_alcance_formulario(user, adjunto.formulario)
    except PermissionDenied:
        return False
    return True


def _padron_de_becas(user, ruta):
    """El padrón es la lista de habilitados completa: mismo alcance que su carga.

    La ficha proponía `es_admin_becas`, pero el que lo **sube** es quien edita la
    convocatoria o el relevamiento (`convocatorias_visibles` /
    `assert_alcance_relevamiento`), que incluye al Coordinador: pedir admin para
    bajarlo dejaba afuera a quien lo cargó. Se usa el guard de la carga.
    """
    from programas.models import Convocatoria, Relevamiento
    from programas.services.autorizacion import assert_alcance_relevamiento, convocatorias_visibles

    convocatoria = Convocatoria.objects.filter(padron_archivo=ruta).first()
    if convocatoria is not None:
        try:
            return convocatorias_visibles(user).filter(pk=convocatoria.pk).exists()
        except PermissionDenied:
            return False
    relevamiento = (
        Relevamiento.objects.select_related("convocatoria__segmento", "segmento").filter(padron_archivo=ruta).first()
    )
    if relevamiento is None:
        return None
    try:
        assert_alcance_relevamiento(user, relevamiento)
    except PermissionDenied:
        return False
    return True


#: Prefijo -> resolver, uno por cada prefijo de :mod:`core.rutas_media`. El orden
#: importa: gana el primero que matchea, así que los más largos van primero. Un
#: `FileField` nuevo entra acá o su archivo no se puede bajar (lo fija
#: `test_media_protegida.CoberturaDePrefijosTests`).
REGLAS = (
    (rutas.PREFIJO_ADJUNTO_BECAS, _adjunto_de_becas),
    (rutas.PREFIJO_PADRON_BECAS, _padron_de_becas),
    (rutas.PREFIJO_ADJUNTO_LEGAJO, _adjunto_de_legajo),
    (rutas.PREFIJO_FOTO_CIUDADANO, _foto_de_ciudadano),
    (rutas.PREFIJO_CONTACTO, _archivo_de_contacto),
    (rutas.PREFIJO_F00, _archivo_de_f00),
    (rutas.PREFIJO_SOLICITUD_MERENDERO, _documentacion_de_merendero),
)


def _autorizar(user, ruta):
    for prefijo, resolver in REGLAS:
        if ruta.startswith(prefijo):
            return resolver(user, ruta)
    logger.warning("media: prefijo sin regla de pertenencia (%s)", ruta.split("/", 1)[0])
    return None


@require_safe
@login_required
def media_protegida(request, path):
    """Sirve `media/<path>` si el usuario puede ver **ese** archivo."""
    ruta = _ruta_segura(path)
    if ruta is None:
        raise Http404("Archivo inexistente.")

    try:
        permitido = _autorizar(request.user, ruta)
    except PermissionDenied:
        # `programa_becas()` y compañía levantan esto cuando el programa no está
        # configurado: eso es una denegación, no un 500.
        permitido = False
    if permitido is None:
        raise Http404("Archivo inexistente.")
    if not permitido:
        raise PermissionDenied("No tiene acceso a este archivo.")

    if settings.MEDIA_X_ACCEL:
        respuesta = HttpResponse()
        # `Content-Type` vacío: lo pone el servidor de adelante al servir el
        # archivo. Si lo mandáramos nosotros, nginx lo respeta y volvemos a
        # adivinar el tipo desde la extensión.
        del respuesta["Content-Type"]
        # `quote`: el header es una **URI**, no un nombre de archivo. Los nombres
        # nuevos son UUID en hex, pero los legacy conservan el original —con
        # espacios y acentos—, y ahí sin escapar nginx recorta en el primer
        # espacio y Django ni siquiera puede armar el header (los headers son
        # latin-1). nginx lo decodifica antes de buscar el `location`.
        respuesta["X-Accel-Redirect"] = f"{PREFIJO_INTERNO}{quote(ruta)}"
    else:
        try:
            completa = safe_join(settings.MEDIA_ROOT, ruta)
            respuesta = FileResponse(open(completa, "rb"), as_attachment=True)
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError, SuspiciousFileOperation, OSError) as exc:
            raise Http404("Archivo inexistente.") from exc
    respuesta["X-Content-Type-Options"] = "nosniff"
    return respuesta
