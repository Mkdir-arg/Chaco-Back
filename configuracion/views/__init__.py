"""Paquete de vistas para la app de configuracion."""

from .geografia import (
    LocalidadCreateView,
    LocalidadDeleteView,
    LocalidadListView,
    LocalidadUpdateView,
    MunicipioCreateView,
    MunicipioDeleteView,
    MunicipioListView,
    MunicipioUpdateView,
    ProvinciaCreateView,
    ProvinciaDeleteView,
    ProvinciaListView,
    ProvinciaUpdateView,
)
from .programas import (
    programa_cambiar_estado,
    programa_editar_paso1,
    programa_editar_paso2,
    programa_editar_paso3,
    programa_editar_paso4,
    programa_list,
    programa_wizard_paso1,
    programa_wizard_paso2,
    programa_wizard_paso3,
    programa_wizard_paso4,
)
from .secretaria import (
    SecretariaCreateView,
    SecretariaDeleteView,
    SecretariaListView,
    SecretariaUpdateView,
    SubsecretariaCreateView,
    SubsecretariaDeleteView,
    SubsecretariaListView,
    SubsecretariaUpdateView,
)
