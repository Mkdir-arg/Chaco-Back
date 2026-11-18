"""Borrado lógico en cascada de la estructura de Becas.

Programa → Segmentos (y sus subsegmentos) → Convocatorias → Relevamientos. Nada se
borra de la base: cada fila de la cascada queda marcada con ``eliminado_en`` /
``eliminado_por`` y el manager por defecto deja de devolverla
(``programas.models.EliminableMixin``).

Si en la cascada hay **casos cargados** (``Formulario``, en cualquier estado) no se
elimina nada: ocultarlos descuadraría el cupo, la lista de espera y lo ya informado a
SIIS, y dejarlos visibles colgando de una convocatoria invisible tampoco sirve.
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from core import rbac
from programas.models import Convocatoria, Formulario, ProgramaSiis, Relevamiento, Segmento, Subsegmento
from programas.services.autorizacion import programa_becas, segmentos_visibles

CAP_PROGRAMA_ELIMINAR = "becas.programa.eliminar"
CAP_SEGMENTO_ELIMINAR = "becas.segmento.eliminar"
CAP_CONVOCATORIA_ELIMINAR = "becas.convocatoria.eliminar"
CAP_RELEVAMIENTO_ELIMINAR = "becas.relevamiento.eliminar"


class EliminacionBloqueada(Exception):
    """La cascada tiene casos cargados: no se elimina nada."""

    def __init__(self, casos):
        self.casos = casos
        super().__init__(f"{casos} caso(s) cargado(s)")


def assert_puede_eliminar(user, capacidad):
    """403 sin la capacidad, evaluada con el alcance del Programa Becas (SEC-06)."""
    if not rbac.puede(user, capacidad, programa=programa_becas(user)):
        raise PermissionDenied("No tiene permiso para eliminar.")


def assert_alcance_programa_completo(user, programa):
    """Eliminar un programa arrastra **todos** sus segmentos: tienen que ser todos del usuario."""
    fuera = Segmento.objects.filter(programa=programa).exclude(pk__in=segmentos_visibles(user).values("pk"))
    if fuera.exists():
        raise PermissionDenied("El programa tiene segmentos fuera de su alcance.")


def _cascada(objeto):
    """Querysets (no eliminados) de cada nivel que cuelga de ``objeto``, incluido él."""
    if isinstance(objeto, ProgramaSiis):
        segmentos = Segmento.objects.filter(programa=objeto)
        convocatorias = Convocatoria.objects.filter(segmento__in=segmentos)
    elif isinstance(objeto, Segmento):
        segmentos = Segmento.objects.filter(pk=objeto.pk)
        convocatorias = Convocatoria.objects.filter(segmento=objeto)
    else:
        segmentos = Segmento.objects.none()
        convocatorias = (
            Convocatoria.objects.filter(pk=objeto.pk)
            if isinstance(objeto, Convocatoria)
            else Convocatoria.objects.none()
        )
    if isinstance(objeto, Relevamiento):
        relevamientos = Relevamiento.objects.filter(pk=objeto.pk)
    else:
        relevamientos = Relevamiento.objects.filter(convocatoria__in=convocatorias)
    return {
        "programas": (
            ProgramaSiis.objects.filter(pk=objeto.pk)
            if isinstance(objeto, ProgramaSiis)
            else ProgramaSiis.objects.none()
        ),
        "segmentos": segmentos,
        "subsegmentos": Subsegmento.objects.filter(segmento__in=segmentos),
        "convocatorias": convocatorias,
        "relevamientos": relevamientos,
    }


def casos_en_cascada(objeto):
    """Cuántos casos (``Formulario``) cuelgan de ``objeto`` y bloquean su eliminación."""
    return Formulario.objects.filter(relevamiento__in=_cascada(objeto)["relevamientos"]).count()


@transaction.atomic
def eliminar(objeto, usuario):
    """Marca ``objeto`` y toda su cascada como eliminados. Devuelve cuántas filas marcó por nivel.

    Los relevamientos se bloquean antes de contar casos: ``Formulario.save`` toma el
    mismo lock al numerar, así que un caso que entra en paralelo espera y, al soltarse
    el lock, ya no encuentra el relevamiento.
    """
    modelo = type(objeto)
    objeto = modelo.objects.select_for_update().get(pk=objeto.pk)
    cascada = _cascada(objeto)
    relevamientos_ids = list(cascada["relevamientos"].select_for_update().values_list("pk", flat=True))
    casos = Formulario.objects.filter(relevamiento_id__in=relevamientos_ids).count()
    if casos:
        raise EliminacionBloqueada(casos)

    ahora = timezone.now()
    marca = {"eliminado_en": ahora, "eliminado_por": usuario, "modificado": ahora}
    # De abajo hacia arriba: los filtros de cada nivel leen el de arriba todavía vivo.
    marcados = {"relevamientos": Relevamiento.objects.filter(pk__in=relevamientos_ids).update(**marca)}
    for nivel in ("convocatorias", "subsegmentos", "segmentos", "programas"):
        ids = list(cascada[nivel].values_list("pk", flat=True))
        marcados[nivel] = cascada[nivel].model.objects.filter(pk__in=ids).update(**marca)
    return marcados


def resumen_cascada(marcados):
    """Texto para el mensaje de éxito: qué más se eliminó junto con el elemento."""
    etiquetas = (
        ("segmentos", "segmento", "segmentos"),
        ("subsegmentos", "subsegmento", "subsegmentos"),
        ("convocatorias", "convocatoria", "convocatorias"),
        ("relevamientos", "relevamiento", "relevamientos"),
    )
    partes = [
        f"{n} {singular if n == 1 else plural}" for clave, singular, plural in etiquetas if (n := marcados.get(clave))
    ]
    return f" También se eliminaron: {', '.join(partes)}." if partes else ""


def mensaje_bloqueo(error, que):
    return (
        f"No se puede eliminar {que}: tiene {error.casos} caso{'s' if error.casos != 1 else ''} "
        f"cargado{'s' if error.casos != 1 else ''}. Solo se puede eliminar lo que no tiene casos."
    )
