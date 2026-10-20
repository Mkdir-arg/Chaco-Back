"""Lecturas de los formularios de un tipo de dispositivo (P17)."""

from __future__ import annotations

from django.db.models import Count, Q

from programas.models import DisenoFormulario, ItemDiseno, MomentoFormulario
from programas.services.formularios_tipo import SE_COMPLETA_EN

_ORDEN = {valor: posicion for posicion, valor in enumerate(MomentoFormulario.values)}


def formularios_del_tipo(tipo):
    """Los formularios del tipo para la tabla del detalle, en el orden de los
    momentos: cada uno con ``n_secciones``, ``n_campos`` y ``se_completa_en``.
    Una sola consulta."""
    formularios = list(
        DisenoFormulario.objects.filter(tipo_dispositivo=tipo).annotate(
            n_secciones=Count("items", filter=Q(items__tipo=ItemDiseno.Tipo.GRUPO)),
            n_campos=Count("items", filter=Q(items__tipo=ItemDiseno.Tipo.CAMPO)),
        )
    )
    formularios.sort(key=lambda f: _ORDEN.get(f.momento, len(_ORDEN)))
    for formulario in formularios:
        formulario.se_completa_en = SE_COMPLETA_EN.get(formulario.momento, "")
    return formularios
