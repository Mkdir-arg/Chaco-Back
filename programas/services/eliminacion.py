"""Borrado lógico en cascada de la estructura de Becas.

Programa → Segmentos (y sus subsegmentos) → Convocatorias → Relevamientos. Nada se
borra de la base: cada fila de la cascada queda marcada con ``eliminado_en`` /
``eliminado_por`` y el manager por defecto deja de devolverla
(``programas.models.EliminableMixin``).

Si en la cascada hay **casos cargados** (``Formulario``, en cualquier estado) no se
elimina nada: ocultarlos descuadraría el cupo, la lista de espera y lo ya informado a
SIIS, y dejarlos visibles colgando de una convocatoria invisible tampoco sirve.

Tampoco se elimina nada si algún relevamiento de la cascada está **en campo**
(``EN_CURSO`` o ``FINALIZANDO``): la app del territorial puede tener capturas offline
sin sincronizar, que al subir encontrarían el relevamiento eliminado (404).
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from core import rbac
from programas.models import Convocatoria, Formulario, ProgramaSiis, Relevamiento, Segmento, Subsegmento
from programas.services.autorizacion import programa_becas, puede_configurar_segmento

CAP_PROGRAMA_ELIMINAR = "becas.programa.eliminar"
CAP_SEGMENTO_ELIMINAR = "becas.segmento.eliminar"
CAP_CONVOCATORIA_ELIMINAR = "becas.convocatoria.eliminar"
CAP_RELEVAMIENTO_ELIMINAR = "becas.relevamiento.eliminar"


#: Estados en los que la app puede tener capturas sin sincronizar (decisión del usuario, 18/11/2026).
ESTADOS_EN_CAMPO = (Relevamiento.Estado.EN_CURSO, Relevamiento.Estado.FINALIZANDO)


class EliminacionBloqueada(Exception):
    """La cascada tiene casos cargados o relevamientos en campo: no se elimina nada."""

    def __init__(self, casos=0, en_campo=0):
        self.casos = casos
        self.en_campo = en_campo
        super().__init__(f"{casos} caso(s) cargado(s), {en_campo} relevamiento(s) en campo")


def assert_puede_eliminar(user, capacidad):
    """403 sin la capacidad, evaluada con el alcance del Programa Becas (SEC-06)."""
    if not rbac.puede(user, capacidad, programa=programa_becas(user)):
        raise PermissionDenied("No tiene permiso para eliminar.")


def assert_alcance_programa_completo(user, programa):
    """Eliminar un programa arrastra **todos** sus segmentos: el usuario tiene que poder
    eliminar cada uno, con la misma regla que ``segmento_eliminar``.

    ``segmentos_visibles`` no alcanza: para el Coordinador Regional incluye todo segmento
    con **un** subsegmento suyo, y con eso eliminaba el programa —y lo de sus pares—
    aunque no puede eliminar ninguno de sus segmentos (SEC-30).
    """
    for segmento in Segmento.objects.filter(programa=programa):
        if not puede_configurar_segmento(user, segmento):
            raise PermissionDenied("El programa tiene segmentos fuera de su alcance.")


def _ids_de_cascada(objeto):
    """ids (no eliminados) de cada nivel que cuelga de ``objeto``, incluido él."""

    def nivel(modelo, de_los_hijos):
        if isinstance(objeto, modelo):
            return [objeto.pk]
        return list(de_los_hijos.values_list("pk", flat=True))

    programas = nivel(ProgramaSiis, ProgramaSiis.objects.none())
    segmentos = nivel(Segmento, Segmento.objects.filter(programa_id__in=programas))
    convocatorias = nivel(Convocatoria, Convocatoria.objects.filter(segmento_id__in=segmentos))
    relevamientos = nivel(Relevamiento, Relevamiento.objects.filter(convocatoria_id__in=convocatorias))
    return {
        "programas": programas,
        "segmentos": segmentos,
        "subsegmentos": list(Subsegmento.objects.filter(segmento_id__in=segmentos).values_list("pk", flat=True)),
        "convocatorias": convocatorias,
        "relevamientos": relevamientos,
    }


#: De abajo hacia arriba: el mismo orden de locks que el link público y el alta de oficio
#: (relevamiento → convocatoria). El inverso abre un deadlock con una inscripción en curso.
_ORDEN = (
    ("relevamientos", Relevamiento),
    ("convocatorias", Convocatoria),
    ("subsegmentos", Subsegmento),
    ("segmentos", Segmento),
    ("programas", ProgramaSiis),
)


@transaction.atomic
def eliminar(objeto, usuario):
    """Marca ``objeto`` y toda su cascada como eliminados. Devuelve cuántas filas marcó por nivel.

    Los ids se resuelven primero (pocas filas, y sin ``IN`` anidados en el ``FOR UPDATE``)
    y se bloquean de abajo hacia arriba. ``Formulario.save`` toma el lock del relevamiento
    al numerar: un caso que entra en paralelo espera y, al soltarse, ya no lo encuentra.
    Después de bloquear las convocatorias se vuelve a leer sus relevamientos, por si se
    creó uno entre la lectura y el lock.
    """
    ids = _ids_de_cascada(objeto)
    if not type(objeto).objects.filter(pk=objeto.pk).exists():
        raise type(objeto).DoesNotExist
    for nivel, modelo in _ORDEN:
        list(modelo.objects.select_for_update().filter(pk__in=ids[nivel]).values_list("pk", flat=True))
    if not isinstance(objeto, Relevamiento):
        ids["relevamientos"] = list(
            Relevamiento.objects.select_for_update()
            .filter(convocatoria_id__in=ids["convocatorias"])
            .values_list("pk", flat=True)
        )

    casos = Formulario.objects.filter(relevamiento_id__in=ids["relevamientos"]).count()
    en_campo = Relevamiento.objects.filter(pk__in=ids["relevamientos"], estado__in=ESTADOS_EN_CAMPO).count()
    if casos or en_campo:
        raise EliminacionBloqueada(casos=casos, en_campo=en_campo)

    ahora = timezone.now()
    marca = {"eliminado_en": ahora, "eliminado_por": usuario, "modificado": ahora}
    return {nivel: modelo.objects.filter(pk__in=ids[nivel]).update(**marca) for nivel, modelo in _ORDEN}


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
    motivos = []
    if error.casos:
        s = "s" if error.casos != 1 else ""
        motivos.append(f"tiene {error.casos} caso{s} cargado{s}")
    if error.en_campo:
        if error.en_campo == 1:
            motivos.append("tiene 1 relevamiento en curso en campo")
        else:
            motivos.append(f"tiene {error.en_campo} relevamientos en curso en campo")
    return (
        f"No se puede eliminar {que}: {' y '.join(motivos)}. Solo se puede eliminar lo que no tiene casos "
        "ni relevamientos en curso (la app puede tener datos sin sincronizar)."
    )
