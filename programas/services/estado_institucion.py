"""Cerrar e inactivar una institución con lo que tiene adentro (Cambio 536).

Va aparte de `services/dispositivos.py` porque libera reservas con `estadias.liberar_reserva`, y
`estadias` ya importa de `dispositivos`: poner esto allá cerraría un ciclo de imports. La transición
de estado y la traza siguen siendo de `dispositivos._transicionar`; acá solo se deciden los
compromisos que impiden o acompañan el cambio. El conteo sale de
`selectors/compromisos_institucion.py`.
"""

from django.core.exceptions import ValidationError

from programas.selectors.compromisos_institucion import compromisos_de_la_institucion, reservas_comunes_abiertas
from programas.services.dispositivos import _transicionar
from programas.services.estadias import liberar_reserva


def _plural(cantidad, singular, plural):
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def _frases_de_compromisos(partes):
    """«3 personas alojadas, 2 reservas vigentes y 1 derivación»: solo las que no son cero."""

    frases = [frase for cantidad, frase in partes if cantidad]
    if len(frases) <= 1:
        return "".join(frases)
    return ", ".join(frases[:-1]) + " y " + frases[-1]


def _personas_alojadas(cantidad):
    return _plural(cantidad, "persona alojada", "personas alojadas")


def _reservas_vigentes(cantidad):
    return _plural(cantidad, "reserva vigente", "reservas vigentes")


def _derivaciones_en_curso(cantidad):
    return _plural(cantidad, "derivación de Emergencia en curso", "derivaciones de Emergencia en curso")


def _exigir_cierre_sin_compromisos(dispositivo):
    """Cerrar es definitivo: ni gente adentro, ni reservas, ni derivaciones de Emergencia en curso (Cambio 536)."""
    c = compromisos_de_la_institucion(dispositivo)
    if c.alojadas or c.reservas or c.derivaciones:
        detalle = _frases_de_compromisos(
            [
                (c.alojadas, _personas_alojadas(c.alojadas)),
                (c.reservas, _reservas_vigentes(c.reservas)),
                (c.derivaciones, _derivaciones_en_curso(c.derivaciones)),
            ]
        )
        raise ValidationError(f"No se puede cerrar: hay {detalle}. Resolvelo antes de cerrar la institución.")


def _exigir_inactivar_sin_compromisos(c):
    """Inactivar rechaza con gente adentro, derivaciones en curso o reservas de derivación (Cambio 536).

    Las reservas de derivación no se sueltan por detrás de Emergencia, aunque su derivación ya no esté en curso.
    """
    if c.alojadas or c.derivaciones or c.reservas_de_derivacion:
        detalle = _frases_de_compromisos(
            [
                (c.alojadas, _personas_alojadas(c.alojadas)),
                (
                    c.reservas_de_derivacion,
                    _plural(c.reservas_de_derivacion, "reserva de derivación", "reservas de derivación"),
                ),
                (c.derivaciones, _derivaciones_en_curso(c.derivaciones)),
            ]
        )
        raise ValidationError(f"No se puede inactivar: hay {detalle}. Resolvelo antes de inactivar la institución.")


def _liberar_reservas_al_inactivar(dispositivo, usuario):
    """Libera las reservas comunes de una institución que se inactiva y devuelve el texto de la traza.

    Deja la cuenta en `dispositivo.reservas_liberadas`, para el aviso de la vista. Antes exige que no
    haya nada que impida inactivar (`_exigir_inactivar_sin_compromisos`).
    """
    _exigir_inactivar_sin_compromisos(compromisos_de_la_institucion(dispositivo))
    reservas = reservas_comunes_abiertas(dispositivo)
    for reserva in reservas:
        liberar_reserva(reserva=reserva, usuario=usuario, motivo="Se inactivó la institución", verificar_alcance=False)
    dispositivo.reservas_liberadas = len(reservas)
    return _plural(len(reservas), "reserva liberada", "reservas liberadas") if reservas else ""


def inactivar_dispositivo(dispositivo, usuario):
    """Devuelve el dispositivo con `reservas_liberadas`: cuántas reservas comunes soltó al inactivarlo."""
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.ACTIVO,),
        destino=Dispositivo.Estado.INACTIVO,
        accion="INACTIVADO",
        antes_de_cambiar=lambda bloqueado: _liberar_reservas_al_inactivar(bloqueado, usuario),
    )


def cerrar_dispositivo(dispositivo, usuario):
    from programas.models import Dispositivo

    return _transicionar(
        dispositivo,
        usuario,
        origenes=(Dispositivo.Estado.ACTIVO, Dispositivo.Estado.INACTIVO, Dispositivo.Estado.RECHAZADO),
        destino=Dispositivo.Estado.CERRADO,
        accion="CERRADO",
        antes_de_cambiar=_exigir_cierre_sin_compromisos,
    )
