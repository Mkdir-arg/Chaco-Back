from core.models import Localidad, Municipio

# El catálogo de Municipio/Localidad es nacional —lo comparte el domicilio de los
# ciudadanos— pero DATAÑACH opera una sola provincia, así que las pantallas de campo
# solo ofrecen la suya. Se resuelve por nombre y no por id porque el id depende de
# cómo se cargó el catálogo en cada ambiente. Si algún día el sistema atendiera más
# de una provincia, este es el único lugar a cambiar.
PROVINCIA_OPERATIVA = "Chaco"


def municipios_operativos():
    """Municipios de la provincia que opera el sistema, para poblar un selector."""
    return Municipio.objects.filter(provincia__nombre__iexact=PROVINCIA_OPERATIVA).order_by("nombre")


def localidades_operativas():
    """Localidades de la provincia que opera el sistema.

    Es el universo contra el que se valida una localidad elegida: el selector se
    llena por AJAX municipio por municipio, pero un POST armado a mano tiene que
    quedar acotado igual.
    """
    return (
        Localidad.objects.filter(municipio__provincia__nombre__iexact=PROVINCIA_OPERATIVA)
        .select_related("municipio")
        .order_by("nombre")
    )


def get_municipios_values(provincia_id):
    return list(Municipio.objects.filter(provincia=provincia_id).select_related("provincia").values("id", "nombre"))


def get_localidades_values(municipio_id):
    if not municipio_id:
        return []

    return list(Localidad.objects.filter(municipio=municipio_id).select_related("municipio").values("id", "nombre"))
