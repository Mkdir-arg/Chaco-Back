"""Filtros de E8 «Situación» (análisis 009, §3.3 y RF-009-04).

Todo viaja por GET y se aplica con «Filtrar». Un parámetro inválido no rompe la pantalla: se
ignora y vale el de por defecto (§7, «Parámetros GET inválidos»). La pertenencia del
departamento y de la localidad se valida contra las localidades del Chaco que la foto ya leyó,
así que validar no agrega consultas.
"""

from django import forms

from core.services.ubicaciones_localidades import clave
from programas.selectors.emergencia_situacion import VENTANA_7D, VENTANA_72H, VENTANA_POR_DEFECTO, FiltrosSituacion

SOLAPA_RESUMEN = "resumen"
SOLAPA_MAPA = "mapa"
SOLAPA_ABASTECIMIENTO = "abastecimiento"
SOLAPAS = (
    (SOLAPA_RESUMEN, "Resumen"),
    (SOLAPA_MAPA, "Mapa"),
    (SOLAPA_ABASTECIMIENTO, "Abastecimiento"),
)
VENTANAS = ((VENTANA_72H, "72 h"), (VENTANA_7D, "7 días"))


class FiltrosSituacionForm(forms.Form):
    """Departamento, localidad (dependiente del departamento), ventana y solapa.

    Cada campo se lee por separado: uno inválido no tira a los demás. Sin ``ventana`` en la URL, 72 h
    (decisión del PM); sin ``tab`` o con uno desconocido, Resumen.
    """

    departamento = forms.CharField(required=False, max_length=120)
    localidad = forms.IntegerField(required=False, min_value=1)
    ventana = forms.ChoiceField(required=False, choices=VENTANAS)
    tab = forms.ChoiceField(required=False, choices=SOLAPAS)

    def _valor(self, campo):
        self.is_valid()
        if campo in self.errors:
            return None
        return self.cleaned_data.get(campo) or None

    @property
    def ventana_elegida(self):
        return self._valor("ventana") or VENTANA_POR_DEFECTO

    @property
    def solapa(self):
        return self._valor("tab") or SOLAPA_RESUMEN

    def filtros(self, localidades) -> FiltrosSituacion:
        """Los filtros válidos contra ``localidades`` (``FotoSituacion.localidades``, las del Chaco).

        Un departamento que ninguna localidad tiene y una localidad que no es del Chaco se ignoran.
        Una localidad de **otro** departamento no se descarta acá: la foto la ignora y lo avisa
        (``FotoSituacion.localidad_ignorada``).
        """

        departamentos = {clave(loc.departamento): loc.departamento for loc in localidades.values() if loc.departamento}
        departamento = departamentos.get(clave(self._valor("departamento") or ""), "")
        localidad = self._valor("localidad")
        if localidad not in localidades:
            localidad = None
        return FiltrosSituacion(departamento=departamento, localidad_id=localidad, ventana=self.ventana_elegida)
