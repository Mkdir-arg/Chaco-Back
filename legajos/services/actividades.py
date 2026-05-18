"""Servicios legacy de actividades institucionales retiradas."""


class InscripcionError(Exception):
    pass


def _actividad_retirada():
    raise InscripcionError("El modulo de actividades institucionales fue retirado.")


def inscribir_ciudadano_a_actividad(actividad, ciudadano, usuario, observaciones=""):
    _actividad_retirada()


def get_estado_inscripcion_ciudadano(actividad, ciudadano):
    return None


def validar_acceso_actividad(actividad, ciudadano):
    return False, "El modulo de actividades institucionales fue retirado."
