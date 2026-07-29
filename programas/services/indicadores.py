"""Indicadores operativos derivados del Programa Dispositivos."""

from django.utils import timezone

from programas.models import Admision, CampoTipoDispositivo, RegistroDiario
from programas.services.camas import resumen_ocupacion


def _semaforo_disponibilidad(porcentaje, umbral_verde):
    if porcentaje <= 0:
        return "ROJO"
    if porcentaje < umbral_verde:
        return "AMARILLO"
    return "VERDE"


def _semaforo_actualizacion(dias, dias_verde, dias_amarillo):
    if dias <= dias_verde:
        return "VERDE"
    if dias <= dias_amarillo:
        return "AMARILLO"
    return "ROJO"


def _semaforo_completitud(porcentaje, umbral_amarillo, umbral_verde):
    if porcentaje >= umbral_verde:
        return "VERDE"
    if porcentaje >= umbral_amarillo:
        return "AMARILLO"
    return "ROJO"


def _tiene_valor(respuestas, campo):
    valor = respuestas.get(str(campo.pk))
    if isinstance(valor, (list, tuple, dict)):
        return bool(valor)
    return valor not in (None, "")


def indicadores_dispositivo(dispositivo, hoy=None):
    """Calcula indicadores observables sin aceptar valores cargados a mano."""

    hoy = hoy or timezone.localdate()
    ocupacion = resumen_ocupacion(dispositivo)
    disponibilidad = (ocupacion["libres"] * 100 / ocupacion["operativas"]) if ocupacion["operativas"] else 0

    ultimo_registro = RegistroDiario.objects.filter(dispositivo=dispositivo).order_by("-modificado").first()
    if ultimo_registro is None:
        actualizacion = {"dias": None, "semaforo": "SIN_DATOS"}
    else:
        dias = max((hoy - ultimo_registro.modificado.date()).days, 0)
        actualizacion = {
            "dias": dias,
            "semaforo": _semaforo_actualizacion(
                dias,
                dispositivo.tipo.dias_actualizacion_verde,
                dispositivo.tipo.dias_actualizacion_amarillo,
            ),
        }

    campos = list(CampoTipoDispositivo.objects.filter(tipo_dispositivo=dispositivo.tipo, obligatorio=True))
    admisiones = Admision.objects.filter(dispositivo=dispositivo, estado=Admision.Estado.ALOJADO)
    esperados = len(campos) * admisiones.count()
    completos = sum(_tiene_valor(admision.respuestas_f00, campo) for admision in admisiones for campo in campos)
    if not admisiones.exists() or not campos:
        completitud = {"completos": completos, "esperados": esperados, "porcentaje": None, "semaforo": "SIN_DATOS"}
    else:
        porcentaje = round(completos * 100 / esperados)
        completitud = {
            "completos": completos,
            "esperados": esperados,
            "porcentaje": porcentaje,
            "semaforo": _semaforo_completitud(
                porcentaje,
                dispositivo.tipo.umbral_completitud_amarillo,
                dispositivo.tipo.umbral_completitud_verde,
            ),
        }

    return {
        "ocupacion": ocupacion,
        "disponibilidad": {
            "porcentaje": round(disponibilidad),
            "semaforo": _semaforo_disponibilidad(disponibilidad, dispositivo.tipo.umbral_disponibilidad_verde),
        },
        "actualizacion": actualizacion,
        "completitud": completitud,
    }
