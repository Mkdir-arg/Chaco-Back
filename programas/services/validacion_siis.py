"""Persistencia de consultas de compatibilidad contra SIIS."""

import uuid

from django.utils.dateparse import parse_datetime

from programas.models import ValidacionSIS
from programas.services.siis import motivos_de_rechazo, validar_compatibilidad


def _uuid_o_none(valor):
    """``id_consulta`` es un ``UUIDField``: lo que no lo sea no se guarda (SIIS-11)."""
    try:
        return uuid.UUID(str(valor))
    except (TypeError, ValueError, AttributeError):
        return None


def _fecha_o_none(valor):
    """``parse_datetime`` lanza ``ValueError`` con una fecha bien formada pero imposible."""
    try:
        return parse_datetime(str(valor or ""))
    except ValueError:
        return None


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
        programa.siis_id_plan_soc_efectivo,
        ciudadano.fecha_nacimiento.isoformat() if ciudadano.fecha_nacimiento else None,
    )
    data = resultado.get("data") or {}
    if not isinstance(data, dict):
        # SIIS contestó algo que no es un objeto: el intento igual se registra
        # —es la constancia de que contestó cualquier cosa—, con los campos
        # estructurados vacíos en vez de un 500 al guardar (SIIS-11).
        data = {}
    estado = ValidacionSIS.Estado.ERROR
    if resultado.get("success"):
        estado = ValidacionSIS.Estado.OK if resultado.get("compatible") else ValidacionSIS.Estado.RECHAZADO
    motivos = motivos_de_rechazo(data.get("validaciones"))
    return ValidacionSIS.objects.create(
        formulario=formulario,
        estado=estado,
        id_programa=programa.siis_id_plan_soc_efectivo,
        documento=ciudadano.dni,
        id_consulta=_uuid_o_none(data.get("id_consulta")),
        fecha_validacion=_fecha_o_none(data.get("fecha_hora")),
        codigo_motivo=", ".join(bandera for bandera, _ in motivos)[:100],
        motivo=" ".join(texto for _, texto in motivos) or str(resultado.get("error") or ""),
        respuesta=data,
        solicitado_por=solicitado_por,
    )
