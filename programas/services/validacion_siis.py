"""Persistencia de consultas de compatibilidad contra SIIS."""

from django.utils.dateparse import parse_datetime

from programas.models import ValidacionSIS
from programas.services.siis import motivos_de_rechazo, validar_compatibilidad


def validar_formulario_en_siis(formulario, solicitado_por):
    """Consulta SIIS de forma síncrona y registra siempre el intento auditable."""
    programa = formulario.relevamiento.convocatoria.segmento.programa
    ciudadano = formulario.ciudadano
    if programa is None:
        raise ValueError("El segmento no tiene configurado el programa correspondiente de SIIS.")
    if ciudadano is None or not ciudadano.dni:
        raise ValueError("El formulario no tiene un ciudadano con DNI vinculado.")

    resultado = validar_compatibilidad(
        ciudadano.dni,
        programa.siis_programa_id,
        ciudadano.fecha_nacimiento.isoformat() if ciudadano.fecha_nacimiento else None,
    )
    data = resultado.get("data") or {}
    estado = ValidacionSIS.Estado.ERROR
    if resultado.get("success"):
        estado = ValidacionSIS.Estado.OK if resultado.get("compatible") else ValidacionSIS.Estado.RECHAZADO
    motivos = motivos_de_rechazo(data.get("validaciones"))
    return ValidacionSIS.objects.create(
        formulario=formulario,
        estado=estado,
        id_programa=programa.siis_programa_id,
        documento=ciudadano.dni,
        id_consulta=data.get("id_consulta") or None,
        fecha_validacion=parse_datetime(str(data.get("fecha_hora") or "")),
        codigo_motivo=", ".join(bandera for bandera, _ in motivos)[:100],
        motivo=" ".join(texto for _, texto in motivos) or str(resultado.get("error") or ""),
        respuesta=data,
        solicitado_por=solicitado_por,
    )
