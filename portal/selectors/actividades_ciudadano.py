"""Selectors legacy de actividades del portal.

El modulo de actividades institucionales fue retirado. Se conservan estas
funciones para que imports historicos no rompan, devolviendo resultados vacios.
"""


def get_actividades_accesibles(ciudadano, institucion=None):
    return []


def get_inscripciones_ciudadano(ciudadano):
    return []


def get_asistencia_ciudadano_en_actividad(ciudadano, actividad_pk):
    return None
