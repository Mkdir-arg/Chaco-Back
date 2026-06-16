from legajos.models_programas import Programa


def build_institucion_detail_context(institucion):
    solapas = [
        {
            "id": "resumen",
            "nombre": "Resumen",
            "icono": "dashboard",
            "color": None,
            "estatica": True,
            "orden": 0,
        },
        {
            "id": "actividades",
            "nombre": "Actividades",
            "icono": "event",
            "color": None,
            "estatica": True,
            "orden": 25,
            "badge": 0,
        },
    ]

    return {
        "solapas": solapas,
        "personal": [],
        "evaluaciones": [],
        "planes": Programa.objects.none(),
        "indicadores": [],
        "total_programas_activos": 0,
        "total_derivaciones_pendientes": 0,
        "total_casos_activos": 0,
    }


def build_actividad_detail_context(actividad):
    return {
        "staff": [],
        "derivaciones": [],
        "nomina": [],
        "total_staff_activo": 0,
        "total_inscriptos_activos": 0,
        "cupo_disponible": True,
        "cupos_restantes": None,
    }
