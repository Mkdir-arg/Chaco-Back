"""Alta y reactivación de la inscripción de un ciudadano a un programa.

``InscripcionPrograma`` tiene ``unique_together = [ciudadano, programa]``: hay **una
sola fila por par**, viva o muerta. Hasta la auditoría oct-2026 las tres vías de alta
hacían ``create`` —el formulario de derivación, ``DerivacionPrograma.aceptar`` y
``SolapasService.crear_inscripcion_directa``—, así que reinscribir a alguien con una
inscripción CERRADA, DADA DE BAJA o SUSPENDIDA reventaba contra el índice único:
``IntegrityError`` y 500 en la vista (LEG-02).

``activar_inscripcion`` es la puerta única: toma la fila que ya existe bajo candado y
la revive. Lo que ya está vigente (ACTIVO o EN_SEGUIMIENTO) **no se toca**: devolverlo
tal cual evita pisar la vía de ingreso y las notas de una inscripción en curso.
"""

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import InscripcionPrograma

#: Estados que ya cuentan como inscripción vigente: no se reactivan ni se reescriben.
ESTADOS_VIGENTES = (
    InscripcionPrograma.Estado.ACTIVO,
    InscripcionPrograma.Estado.EN_SEGUIMIENTO,
)


def tomar_inscripcion(ciudadano, programa, *, defaults):
    """``get_or_create`` bajo ``select_for_update``, tolerante a la carrera.

    Dos procesos que dan de alta a la misma persona en el mismo programa a la vez: el
    que pierde recibe el ``IntegrityError`` del índice único y relee la fila del otro.
    (El ``get_or_create`` de Django ya intenta esa relectura por su cuenta; la rama de
    rescate de acá es para cuando tampoco él la ve, que es lo que pasa bajo
    REPEATABLE READ si la otra transacción todavía no commiteó.)

    **Las dos ramas abren su propia transacción, y hace falta que sea así.** La rama
    feliz se envuelve sola, pero la de rescate corre *después* de que ese ``atomic``
    se cerró: sin uno nuevo, el ``select_for_update`` quedaba pedido en autocommit y
    MySQL y MariaDB contestan ``TransactionManagementError`` —500— en cuanto el
    llamador no venga envuelto en su propio ``atomic``. En SQLite no se ve, porque
    ahí ``select_for_update`` es un no-op (``has_select_for_update = False``).

    **El candado no sobrevive a la llamada por sí solo:** si el llamador no tiene su
    propio ``atomic``, la transacción de acá commitea al salir y lo libera. Eso es
    correcto para los dos usos actuales: ``activar_inscripcion`` **sí** es atómico y
    muta la fila bajo su candado, y ``_obtener_membresia`` solo la lee.
    """
    try:
        with transaction.atomic():
            return InscripcionPrograma.objects.select_for_update().get_or_create(
                ciudadano=ciudadano, programa=programa, defaults=defaults
            )
    except IntegrityError:
        with transaction.atomic():
            fila = InscripcionPrograma.objects.select_for_update().get(ciudadano=ciudadano, programa=programa)
        return fila, False


@transaction.atomic
def activar_inscripcion(ciudadano, programa, *, via, usuario=None, notas=""):
    """Deja al ciudadano ACTIVO en el programa, creando o reviviendo su inscripción.

    :param via: valor de ``InscripcionPrograma.ViaIngreso`` con el que entra ahora.
    :param usuario: responsable del alta; en una reactivación solo se escribe si la
        fila no tenía responsable (el original manda).
    :param notas: si viene, reemplaza las notas de la inscripción revivida.
    """
    hoy = timezone.localdate()
    inscripcion, creada = tomar_inscripcion(
        ciudadano,
        programa,
        defaults={
            "estado": InscripcionPrograma.Estado.ACTIVO,
            "via_ingreso": via,
            "fecha_inicio": hoy,
            "responsable": usuario,
            "notas": notas or "",
        },
    )
    if creada or inscripcion.estado in ESTADOS_VIGENTES:
        return inscripcion

    campos = ["estado", "fecha_inicio", "fecha_cierre", "motivo_cierre", "via_ingreso", "modificado"]
    inscripcion.estado = InscripcionPrograma.Estado.ACTIVO
    inscripcion.fecha_inicio = hoy
    inscripcion.fecha_cierre = None
    inscripcion.motivo_cierre = ""
    inscripcion.via_ingreso = via
    if notas:
        inscripcion.notas = notas
        campos.append("notas")
    if usuario is not None and inscripcion.responsable_id is None:
        inscripcion.responsable = usuario
        campos.append("responsable")
    inscripcion.save(update_fields=campos)
    return inscripcion
