"""Filtros de template del backoffice de Becas."""

import json

from django import template
from django.template.defaultfilters import date as fecha_local

register = template.Library()


@register.filter
def siis_info(programa):
    """Detalle de un ``ProgramaSiis``, como literal JSON para Alpine.

    Se emite sin ``mark_safe``: el autoescape convierte las comillas en
    ``&quot;`` dentro del atributo y el navegador las devuelve al parsear, así
    que la expresión ``@click="openInfo({...})"`` recibe un objeto válido.
    """
    datos = programa.siis_programa_datos or {}
    return json.dumps(
        {
            "id": programa.siis_programa_id,
            "nombre": datos.get("nombre") or programa.nombre,
            "descripcion": datos.get("descripcion") or "",
            "jurisdiccion": datos.get("jurisdiccion_id"),
            "estadoVinculado": datos.get("estado") or "",
            "estadoActual": programa.siis_programa_estado or "",
            "bloqueado": programa.siis_bloqueado,
            "motivo": programa.siis_motivo_bloqueo,
            "vinculado": fecha_local(programa.siis_vinculado_en, "d/m/Y H:i") or "",
            "verificado": fecha_local(programa.siis_verificado_en, "d/m/Y H:i") or "",
            "controles": [
                ("Empleo público", datos.get("controla_empleo_publico")),
                ("Horas cátedra docentes", datos.get("controla_horas_docentes")),
                ("Duplicidad de beneficios", datos.get("controla_duplicidad_becas")),
                ("Tope de SMVM", datos.get("controla_smvm")),
                ("Edad mínima", datos.get("controla_edad_minima")),
            ],
            "edadMinima": datos.get("edad_minima"),
        },
        ensure_ascii=False,
    )


@register.filter
def iniciales(value):
    """Iniciales de un nombre: 1ª letra del primer y último término (máx 2),
    en mayúscula. "María García" -> "MG"; "Carlos" -> "C"."""
    if not value:
        return ""
    partes = str(value).split()
    if not partes:
        return ""
    if len(partes) == 1:
        return partes[0][:1].upper()
    return (partes[0][:1] + partes[-1][:1]).upper()
