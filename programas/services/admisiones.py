"""Operaciones atómicas del circuito de admisiones de Dispositivos."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from programas.models import Admision, ArchivoAdmision, Cama, Dispositivo, EsperaAdmision, InscripcionPrograma, Programa


def _programa_dispositivos():
    return Programa.objects.get(codigo=Programa.TipoPrograma.DISPOSITIVOS)


def _membresia_activa(ciudadano, usuario):
    programa = _programa_dispositivos()
    try:
        with transaction.atomic():
            membresia, _ = InscripcionPrograma.objects.select_for_update().get_or_create(
                ciudadano=ciudadano, programa=programa, defaults={"responsable": usuario}
            )
    except IntegrityError:
        membresia = InscripcionPrograma.objects.select_for_update().get(ciudadano=ciudadano, programa=programa)
    if membresia.estado != InscripcionPrograma.Estado.ACTIVO:
        membresia.estado = InscripcionPrograma.Estado.ACTIVO
        membresia.fecha_inicio = timezone.localdate()
        membresia.fecha_cierre = None
        membresia.save(update_fields=["estado", "fecha_inicio", "fecha_cierre", "modificado"])
    return membresia


def _guardar_f00(admision, respuestas_f00=None, archivos_f00=None):
    admision.respuestas_f00 = respuestas_f00 or {}
    admision.save(update_fields=["respuestas_f00", "modificado"])
    for campo, archivo in (archivos_f00 or {}).items():
        if archivo:
            ArchivoAdmision.objects.update_or_create(admision=admision, campo=campo, defaults={"archivo": archivo})


def _es_reingreso(ciudadano, dispositivo):
    return Admision.objects.filter(
        ciudadano=ciudadano,
        dispositivo=dispositivo,
        estado__in=[Admision.Estado.EGRESADO, Admision.Estado.TRASLADADO],
    ).exists()


def _crear_admision_alojada(
    *, ciudadano, dispositivo, cama, usuario, respuestas_f00=None, archivos_f00=None, origen=None
):
    if cama.dispositivo_id != dispositivo.pk:
        raise ValidationError("La cama debe pertenecer al dispositivo seleccionado.")
    if cama.estado != Cama.Estado.DISPONIBLE:
        raise ValidationError("La cama seleccionada no está disponible.")
    if (
        Admision.objects.select_for_update()
        .filter(ciudadano=ciudadano, dispositivo=dispositivo, estado=Admision.Estado.ALOJADO)
        .exists()
    ):
        raise ValidationError("La persona ya tiene una estadía activa en este dispositivo.")

    admision = Admision(
        ciudadano=ciudadano,
        dispositivo=dispositivo,
        cama=cama,
        inscripcion_programa=_membresia_activa(ciudadano, usuario),
        fecha_ingreso=timezone.now(),
        estado=Admision.Estado.ALOJADO,
        es_reingreso=_es_reingreso(ciudadano, dispositivo),
        origen_traslado=origen,
    )
    admision.full_clean()
    admision.save()
    cama.estado = Cama.Estado.OCUPADA
    cama.save(update_fields=["estado", "modificado"])
    _guardar_f00(admision, respuestas_f00, archivos_f00)
    return admision


@transaction.atomic
def admitir_ciudadano(*, ciudadano, dispositivo, cama, usuario, respuestas_f00=None, archivos_f00=None):
    """Crea una estadía alojada bloqueando el recurso de cama compartido."""
    dispositivo = Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
    if dispositivo.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError("Solo se admiten personas en dispositivos activos.")
    cama = Cama.objects.select_for_update().get(pk=cama.pk)
    return _crear_admision_alojada(
        ciudadano=ciudadano,
        dispositivo=dispositivo,
        cama=cama,
        usuario=usuario,
        respuestas_f00=respuestas_f00,
        archivos_f00=archivos_f00,
    )


@transaction.atomic
def poner_en_espera(*, ciudadano, dispositivo, usuario, respuestas_f00=None, archivos_f00=None, origen=None):
    dispositivo = Dispositivo.objects.select_for_update().get(pk=dispositivo.pk)
    if dispositivo.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError("Solo se admiten personas en dispositivos activos.")
    if (
        Admision.objects.select_for_update()
        .filter(ciudadano=ciudadano, dispositivo=dispositivo, estado=Admision.Estado.LISTA_ESPERA)
        .exists()
    ):
        raise ValidationError("La persona ya está en lista de espera de este dispositivo.")
    admision = Admision.objects.create(
        ciudadano=ciudadano,
        dispositivo=dispositivo,
        inscripcion_programa=_membresia_activa(ciudadano, usuario),
        fecha_ingreso=timezone.now(),
        estado=Admision.Estado.LISTA_ESPERA,
        origen_traslado=origen,
    )
    ultima = (
        EsperaAdmision.objects.select_for_update()
        .filter(admision__dispositivo=dispositivo, promovida=False)
        .aggregate(maxima=Max("posicion"))["maxima"]
        or 0
    )
    EsperaAdmision.objects.create(admision=admision, posicion=ultima + 1)
    _guardar_f00(admision, respuestas_f00, archivos_f00)
    return admision


@transaction.atomic
def egresar_admision(*, admision, usuario, fecha_egreso, motivo, destino):
    admision = Admision.objects.select_for_update().select_related("cama", "inscripcion_programa").get(pk=admision.pk)
    if admision.estado != Admision.Estado.ALOJADO:
        raise ValidationError("Solo se puede egresar una admisión alojada.")
    if fecha_egreso < admision.fecha_ingreso:
        raise ValidationError("La fecha de egreso no puede ser anterior al ingreso.")

    if admision.cama_id:
        cama = Cama.objects.select_for_update().get(pk=admision.cama_id)
        cama.estado = Cama.Estado.DISPONIBLE
        cama.save(update_fields=["estado", "modificado"])

    admision.estado = Admision.Estado.EGRESADO
    admision.fecha_egreso = fecha_egreso
    admision.motivo_egreso = (motivo or "").strip()
    admision.destino_egreso = (destino or "").strip()
    admision.responsable_egreso = usuario
    admision.save(
        update_fields=["estado", "fecha_egreso", "motivo_egreso", "destino_egreso", "responsable_egreso", "modificado"]
    )
    membresia = admision.inscripcion_programa
    if (
        membresia
        and not Admision.objects.filter(inscripcion_programa=membresia, estado=Admision.Estado.ALOJADO).exists()
    ):
        membresia.estado = InscripcionPrograma.Estado.CERRADO
        membresia.fecha_cierre = timezone.localdate()
        membresia.save(update_fields=["estado", "fecha_cierre", "modificado"])
    return admision


def _cerrar_origen_por_traslado(origen, usuario, destino):
    origen = Admision.objects.select_for_update().get(pk=origen.pk)
    if origen.estado != Admision.Estado.ALOJADO:
        raise ValidationError("La estadía de origen ya no está alojada.")
    cama_origen = Cama.objects.select_for_update().get(pk=origen.cama_id)
    cama_origen.estado = Cama.Estado.DISPONIBLE
    cama_origen.save(update_fields=["estado", "modificado"])
    origen.estado = Admision.Estado.TRASLADADO
    origen.fecha_egreso = timezone.now()
    origen.motivo_egreso = "Traslado"
    origen.destino_egreso = destino.nombre
    origen.responsable_egreso = usuario
    origen.save(
        update_fields=["estado", "fecha_egreso", "motivo_egreso", "destino_egreso", "responsable_egreso", "modificado"]
    )
    return origen


@transaction.atomic
def trasladar_admision(*, admision, destino, cama, usuario, respuestas_f00=None, archivos_f00=None):
    """Abre destino antes de cerrar origen; sin cama, conserva origen y encola destino."""
    ids = sorted({admision.dispositivo_id, destino.pk})
    dispositivos = {obj.pk: obj for obj in Dispositivo.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    origen_dispositivo = dispositivos[admision.dispositivo_id]
    destino = dispositivos[destino.pk]
    admision = Admision.objects.select_for_update().get(pk=admision.pk)
    if admision.estado != Admision.Estado.ALOJADO:
        raise ValidationError("Solo se puede trasladar una admisión alojada.")
    if origen_dispositivo.pk == destino.pk:
        raise ValidationError("El dispositivo de destino debe ser distinto al origen.")
    if destino.estado != Dispositivo.Estado.ACTIVO:
        raise ValidationError("El dispositivo de destino no está activo.")

    if cama is None:
        return poner_en_espera(
            ciudadano=admision.ciudadano,
            dispositivo=destino,
            usuario=usuario,
            respuestas_f00=respuestas_f00,
            archivos_f00=archivos_f00,
            origen=admision,
        )
    cama = Cama.objects.select_for_update().get(pk=cama.pk)
    nueva = _crear_admision_alojada(
        ciudadano=admision.ciudadano,
        dispositivo=destino,
        cama=cama,
        usuario=usuario,
        respuestas_f00=respuestas_f00,
        archivos_f00=archivos_f00,
        origen=admision,
    )
    _cerrar_origen_por_traslado(admision, usuario, destino)
    return nueva


@transaction.atomic
def promover_espera(*, espera, cama, usuario):
    espera = EsperaAdmision.objects.select_for_update().select_related("admision__origen_traslado").get(pk=espera.pk)
    if espera.promovida or espera.admision.estado != Admision.Estado.LISTA_ESPERA:
        raise ValidationError("La admisión ya no está en espera.")
    admision = Admision.objects.select_for_update().get(pk=espera.admision_id)
    cama = Cama.objects.select_for_update().get(pk=cama.pk)
    if cama.dispositivo_id != admision.dispositivo_id or cama.estado != Cama.Estado.DISPONIBLE:
        raise ValidationError("La cama seleccionada no está disponible.")
    admision.cama = cama
    admision.estado = Admision.Estado.ALOJADO
    admision.fecha_ingreso = timezone.now()
    admision.inscripcion_programa = _membresia_activa(admision.ciudadano, usuario)
    admision.save(update_fields=["cama", "estado", "fecha_ingreso", "inscripcion_programa", "modificado"])
    cama.estado = Cama.Estado.OCUPADA
    cama.save(update_fields=["estado", "modificado"])
    espera.promovida = True
    espera.save(update_fields=["promovida", "modificado"])
    if admision.origen_traslado_id:
        _cerrar_origen_por_traslado(admision.origen_traslado, usuario, admision.dispositivo)
    return admision
