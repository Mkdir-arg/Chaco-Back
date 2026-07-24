"""Reglas derivadas de ocupación para camas de Dispositivos."""

from django.core.exceptions import ValidationError
from django.db import transaction

from programas.models import Admision, Cama


def resumen_ocupacion(dispositivo):
    """Devuelve la ocupación real, calculada desde camas y estadías alojadas."""

    camas = Cama.objects.filter(dispositivo=dispositivo)
    totales = camas.count()
    fuera_servicio = camas.filter(estado=Cama.Estado.FUERA_SERVICIO).count()
    operativas = max(totales - fuera_servicio, 0)
    ocupadas = (
        Admision.objects.filter(
            dispositivo=dispositivo,
            estado=Admision.Estado.ALOJADO,
            cama__isnull=False,
        )
        .values("cama_id")
        .distinct()
        .count()
    )
    libres = max(operativas - ocupadas, 0)
    porcentaje_exacto = (ocupadas * 100) / operativas if operativas else 0
    porcentaje = round(porcentaje_exacto)
    umbral_amarillo = getattr(dispositivo.tipo, "umbral_ocupacion_amarillo", 50)
    umbral_rojo = getattr(dispositivo.tipo, "umbral_ocupacion_rojo", 80)
    semaforo = (
        "ROJO" if porcentaje_exacto >= umbral_rojo else "AMARILLO" if porcentaje_exacto >= umbral_amarillo else "VERDE"
    )

    return {
        "totales": totales,
        "ocupadas": ocupadas,
        "fuera_servicio": fuera_servicio,
        "operativas": operativas,
        "libres": libres,
        "porcentaje": porcentaje,
        "semaforo": semaforo,
    }


TRANSICIONES_PERMITIDAS = {
    Cama.Estado.DISPONIBLE: {Cama.Estado.RESERVADA, Cama.Estado.OCUPADA, Cama.Estado.FUERA_SERVICIO},
    Cama.Estado.RESERVADA: {Cama.Estado.DISPONIBLE, Cama.Estado.OCUPADA, Cama.Estado.FUERA_SERVICIO},
    Cama.Estado.OCUPADA: {Cama.Estado.DISPONIBLE},
    Cama.Estado.FUERA_SERVICIO: {Cama.Estado.DISPONIBLE},
}


def actualizar_cama(cama, *, codigo, nuevo_estado):
    """Actualiza una cama en una sola transacción y respeta sus invariantes."""

    with transaction.atomic():
        cama = Cama.objects.select_for_update().get(pk=cama.pk)
        tiene_persona_alojada = Admision.objects.filter(
            cama=cama,
            estado=Admision.Estado.ALOJADO,
        ).exists()
        if tiene_persona_alojada and nuevo_estado != Cama.Estado.OCUPADA:
            raise ValidationError("La cama tiene una persona alojada: exige reasignación previa.")
        if nuevo_estado == Cama.Estado.OCUPADA and not tiene_persona_alojada:
            raise ValidationError("La ocupación se deriva de una estadía activa, no se carga manualmente.")
        if nuevo_estado != cama.estado and nuevo_estado not in TRANSICIONES_PERMITIDAS[cama.estado]:
            raise ValidationError("La transición de estado de la cama no está permitida.")
        cama.codigo = codigo
        cama.estado = nuevo_estado
        cama.save(update_fields=["codigo", "estado", "modificado"])
        return cama


def cambiar_estado_cama(cama, nuevo_estado):
    """Compatibilidad para cambios de estado que preservan el código existente."""

    return actualizar_cama(cama, codigo=cama.codigo, nuevo_estado=nuevo_estado)


def crear_camas(dispositivo, cantidad):
    """Agrega camas disponibles con código consecutivo y sincroniza la capacidad."""

    if cantidad <= 0:
        raise ValidationError("Indicá una cantidad positiva de camas.")

    with transaction.atomic():
        dispositivo = dispositivo.__class__.objects.select_for_update().get(pk=dispositivo.pk)
        if not dispositivo.tipo.maneja_camas:
            raise ValidationError("El tipo de dispositivo no maneja camas.")

        codigos_existentes = set(Cama.objects.filter(dispositivo=dispositivo).values_list("codigo", flat=True))
        creadas = []
        numero = 1
        while len(creadas) < cantidad:
            codigo = f"C-{numero:02d}"
            if codigo not in codigos_existentes:
                creadas.append(Cama.objects.create(dispositivo=dispositivo, codigo=codigo))
                codigos_existentes.add(codigo)
            numero += 1

        dispositivo.camas_totales = len(codigos_existentes)
        dispositivo.save(update_fields=["camas_totales", "modificado"])
        return creadas
