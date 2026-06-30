from core.models import Localidad, Municipio


def get_municipios_values(provincia_id):
    return list(Municipio.objects.filter(provincia=provincia_id).select_related("provincia").values("id", "nombre"))


def get_localidades_values(municipio_id):
    if not municipio_id:
        return []

    return list(Localidad.objects.filter(municipio=municipio_id).select_related("municipio").values("id", "nombre"))
