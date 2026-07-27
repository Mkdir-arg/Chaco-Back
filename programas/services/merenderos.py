"""Reglas transaccionales del circuito operativo de Merenderos."""

from calendar import monthrange

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from programas.models import EntregaMercaderia, Merendero, PrestacionDiaria, PrestacionMensual, SolicitudMerendero

_DATOS_SOLICITUD_REQUERIDOS = (
    "codigo",
    "nombre",
    "domicilio",
    "zona",
    "barrio",
    "dias_horarios",
    "responsable_nombre",
)


def aprobar_solicitud(solicitud, usuario):
    """Aprueba una solicitud documentada y crea una única vez su legajo activo."""

    with transaction.atomic():
        solicitud = SolicitudMerendero.objects.select_for_update().get(pk=solicitud.pk)
        if solicitud.estado == SolicitudMerendero.Estado.APROBADA and solicitud.merendero_id:
            return solicitud.merendero
        if solicitud.estado != SolicitudMerendero.Estado.EN_REVISION:
            raise ValidationError("Solo se pueden aprobar solicitudes en revisión.")
        if not solicitud.documentacion:
            raise ValidationError("La documentación respaldatoria es obligatoria para aprobar.")

        faltantes = [campo for campo in _DATOS_SOLICITUD_REQUERIDOS if not getattr(solicitud, campo).strip()]
        if faltantes:
            raise ValidationError("La solicitud no tiene todos los datos institucionales requeridos.")
        if Merendero.objects.select_for_update().filter(codigo=solicitud.codigo).exists():
            raise ValidationError("Ya existe un merendero con ese código institucional.")

        merendero = Merendero.objects.create(
            codigo=solicitud.codigo,
            nombre=solicitud.nombre,
            domicilio=solicitud.domicilio,
            zona=solicitud.zona,
            barrio=solicitud.barrio,
            dias_horarios=solicitud.dias_horarios,
            telefono=solicitud.telefono,
            responsable_nombre=solicitud.responsable_nombre,
            responsable_documento=solicitud.responsable_documento,
            responsable_email=solicitud.responsable_email,
            estado=Merendero.Estado.ACTIVO,
        )
        solicitud.merendero = merendero
        solicitud.estado = SolicitudMerendero.Estado.APROBADA
        solicitud.validada_por = usuario
        solicitud.validada_en = timezone.now()
        solicitud.save(update_fields=["merendero", "estado", "validada_por", "validada_en", "modificado"])
        return merendero


def resolver_solicitud(solicitud, *, estado, observaciones, usuario):
    """Observa o rechaza una solicitud en revisión dejando trazabilidad."""

    if estado not in (SolicitudMerendero.Estado.OBSERVADA, SolicitudMerendero.Estado.RECHAZADA):
        raise ValueError("El estado de resolución no es válido.")
    if not observaciones or not observaciones.strip():
        raise ValidationError("Indicá el motivo de la resolución.")
    with transaction.atomic():
        solicitud = SolicitudMerendero.objects.select_for_update().get(pk=solicitud.pk)
        if solicitud.estado != SolicitudMerendero.Estado.EN_REVISION:
            raise ValidationError("Solo se pueden resolver solicitudes en revisión.")
        solicitud.estado = estado
        solicitud.observaciones = observaciones.strip()
        solicitud.validada_por = usuario
        solicitud.validada_en = timezone.now()
        solicitud.save(update_fields=["estado", "observaciones", "validada_por", "validada_en", "modificado"])
        return solicitud


def reenviar_solicitud(solicitud):
    """Devuelve una solicitud observada al circuito de revisión sin crear un legajo."""

    with transaction.atomic():
        solicitud = SolicitudMerendero.objects.select_for_update().get(pk=solicitud.pk)
        if solicitud.estado != SolicitudMerendero.Estado.OBSERVADA:
            raise ValidationError("Solo se pueden reenviar solicitudes observadas.")
        solicitud.estado = SolicitudMerendero.Estado.EN_REVISION
        solicitud.save(update_fields=["estado", "modificado"])
        return solicitud


def registrar_entrega(merendero, *, fecha, cantidad_kits, servicio, responsable_receptor, observaciones):
    if merendero.estado != Merendero.Estado.ACTIVO:
        raise ValidationError("Solo se pueden registrar entregas en merenderos activos.")
    return EntregaMercaderia.objects.create(
        merendero=merendero,
        fecha=fecha,
        cantidad_kits=cantidad_kits,
        servicio=servicio,
        responsable_receptor=responsable_receptor,
        observaciones=observaciones,
    )


def guardar_prestacion(merendero, *, anio, mes, raciones, usuario, observaciones=None):
    """Crea o reabre una única grilla mensual, con totales siempre derivados."""

    if merendero.estado != Merendero.Estado.ACTIVO:
        raise ValidationError("Solo se puede cargar prestación en merenderos activos.")
    try:
        ultimo_dia = monthrange(anio, mes)[1]
    except (TypeError, ValueError) as error:
        raise ValidationError("Mes o año inválido.") from error
    observaciones = observaciones or {}
    servicios = [valor for valor, _etiqueta in PrestacionDiaria.Servicio.choices]

    with transaction.atomic():
        prestacion, _creada = PrestacionMensual.objects.select_for_update().get_or_create(
            merendero=merendero,
            anio=anio,
            mes=mes,
            defaults={"servicios": servicios},
        )
        if prestacion.anulada:
            raise ValidationError("La prestación mensual está anulada.")
        existentes = {
            (linea.dia, linea.servicio): linea
            for linea in PrestacionDiaria.objects.select_for_update().filter(prestacion=prestacion)
        }
        nuevas, actualizadas = [], []
        ahora = timezone.now()
        for dia in range(1, ultimo_dia + 1):
            valores_dia = raciones.get(dia, {})
            for servicio in servicios:
                valor = valores_dia.get(servicio, 0)
                if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
                    raise ValidationError("Las raciones deben ser números enteros mayores o iguales a cero.")
                linea = existentes.get((dia, servicio))
                if linea is None:
                    nuevas.append(
                        PrestacionDiaria(
                            prestacion=prestacion,
                            dia=dia,
                            servicio=servicio,
                            raciones=valor,
                            firmado_por=usuario,
                            anulada=False,
                        )
                    )
                    continue
                linea.raciones = valor
                linea.firmado_por = usuario
                linea.anulada = False
                linea.modificado = ahora
                actualizadas.append(linea)
        if nuevas:
            PrestacionDiaria.objects.bulk_create(nuevas)
        if actualizadas:
            PrestacionDiaria.objects.bulk_update(actualizadas, ["raciones", "firmado_por", "anulada", "modificado"])
        prestacion.observaciones_por_dia = {
            str(dia): texto.strip()
            for dia, texto in observaciones.items()
            if 1 <= int(dia) <= ultimo_dia and texto and texto.strip()
        }
        prestacion.save(update_fields=["servicios", "observaciones_por_dia", "modificado"])
        return prestacion
