"""Lecturas de los formularios de un tipo de dispositivo (P17)."""

from __future__ import annotations

from django.db.models import Count, Q

from programas.models import DisenoFormulario, ItemDiseno, MomentoFormulario
from programas.services.formularios_tipo import SE_COMPLETA_EN
from programas.services.respuestas_dispositivo import anotar_tiene_respuestas, respondido

_ORDEN = {valor: posicion for posicion, valor in enumerate(MomentoFormulario.values)}


def formularios_del_tipo(tipo):
    """Los formularios del tipo para la tabla del detalle, en el orden de los
    momentos: cada uno con ``n_secciones``, ``n_campos``, ``se_completa_en``,
    ``de_baja`` y ``tiene_respuestas`` (si «Eliminar» lo borra o lo da de baja).
    Una sola consulta."""
    formularios = list(
        anotar_tiene_respuestas(
            DisenoFormulario.objects.filter(tipo_dispositivo=tipo).annotate(
                n_secciones=Count("items", filter=Q(items__tipo=ItemDiseno.Tipo.GRUPO)),
                n_campos=Count("items", filter=Q(items__tipo=ItemDiseno.Tipo.CAMPO)),
            )
        )
    )
    formularios.sort(key=lambda f: _ORDEN.get(f.momento, len(_ORDEN)))
    for formulario in formularios:
        formulario.se_completa_en = SE_COMPLETA_EN.get(formulario.momento, "")
        formulario.de_baja = formulario.dado_de_baja_en is not None
        formulario.tiene_respuestas = respondido(formulario)
    return formularios
