"""Lógica de dominio para gestión de cupo y lista de espera (RN-04/05, issue #78).

El cupo ocupado se calcula dinámicamente (COUNT de formularios APROBADO) para
evitar desincronización con la integración SIIS futura (#72). CupoSegmento queda
como estructura base pero no se muta aquí.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from programas.models import Formulario, ListaEspera, Segmento, ValidacionSIS
from programas.services.becas import registrar_traza


def get_cupo_stats(segmento):
    """Retorna dict con cupo_maximo, cupo_ocupado (dinámico) y cupo_disponible."""
    cupo_ocupado = Formulario.objects.filter(
        estado=Formulario.Estado.APROBADO,
        relevamiento__convocatoria__segmento=segmento,
    ).count()
    cupo_maximo = segmento.cupo_maximo
    return {
        "cupo_maximo": cupo_maximo,
        "cupo_ocupado": cupo_ocupado,
        "cupo_disponible": max(cupo_maximo - cupo_ocupado, 0),
    }


def motivo_bloqueo_aprobacion(formulario):
    """Explica por qué un formulario todavía no puede aprobarse.

    La aprobación exige identidad validada y la última consulta SIIS compatible
    para el DNI y programa actuales. Devuelve ``None`` cuando supera el gate.
    """
    if not formulario.validado_renaper:
        return "La identidad debe estar validada antes de aprobar."
    if not formulario.ciudadano_id or not formulario.ciudadano.dni:
        return "El formulario debe tener un ciudadano con DNI vinculado."

    segmento = formulario.relevamiento.convocatoria.segmento
    programa = segmento.programa
    if programa is None:
        return "El segmento no tiene un programa SIIS configurado."

    validacion = formulario.validaciones_sis.order_by("-creado").first()
    if validacion is None:
        return "Debe realizarse la validación SIIS antes de aprobar."
    if validacion.estado == ValidacionSIS.Estado.RECHAZADO:
        return "La última validación SIIS indicó que la persona no es compatible."
    if validacion.estado == ValidacionSIS.Estado.ERROR:
        return "La última validación SIIS tuvo un error técnico; debe reintentarse."
    if validacion.estado != ValidacionSIS.Estado.OK:
        return "La última validación SIIS no tiene un resultado válido para aprobar."
    if str(validacion.documento).strip() != str(formulario.ciudadano.dni).strip():
        return "La validación SIIS no corresponde al DNI actual del formulario."
    if validacion.id_programa != programa.siis_programa_id:
        return "La validación SIIS no corresponde al programa actual del formulario."
    return None


def validar_aprobacion(formulario):
    motivo = motivo_bloqueo_aprobacion(formulario)
    if motivo:
        raise ValidationError(motivo)


def estado_relevante_becas(estados, en_espera):
    """Determina ``(texto, color)`` del estado más relevante de un ciudadano en
    Becas a partir de sus estados de formulario y si tiene lista de espera activa.

    ``color`` es el sufijo semántico (success/warning/danger/gray) usado tanto
    por las clases ``badge-*`` como por los tokens de color del punto de la
    solapa; cada consumidor lo adapta a su propio contrato de renderizado.
    """
    estados = set(estados)
    if Formulario.Estado.APROBADO in estados:
        return "Beneficiario", "success"
    if en_espera:
        return "Lista de espera", "warning"
    if Formulario.Estado.RECHAZADO in estados:
        return "Rechazado", "danger"
    if Formulario.Estado.BAJA in estados:
        return "Dado de baja", "gray"
    return "Pendiente", "gray"


@transaction.atomic
def dar_baja_beneficiario(formulario, user):
    """Da de baja a un beneficiario (RN-05): cambia estado a BAJA.

    Raises ValidationError si el formulario no está en estado APROBADO.
    """
    if formulario.estado != Formulario.Estado.APROBADO:
        raise ValidationError("Solo se puede dar de baja a un beneficiario con estado APROBADO.")

    estado_anterior = formulario.estado
    formulario.estado = Formulario.Estado.BAJA
    formulario.save(update_fields=["estado", "modificado"])
    registrar_traza(formulario, user, [("estado", estado_anterior, Formulario.Estado.BAJA)])


@transaction.atomic
def promover_lista_espera(lista_espera, user):
    """Promueve una entrada de lista de espera como beneficiario (RN-04).

    Valida que haya cupo disponible antes de promover.
    Raises ValidationError si ya fue promovido o si no hay cupo.
    """
    if lista_espera.promovido:
        raise ValidationError("Esta entrada ya fue promovida.")

    segmento = lista_espera.segmento
    # Mismo lock que agregar_a_lista_espera: sin él, dos promociones (o una
    # promoción y una aprobación) concurrentes pueden leer el mismo
    # cupo_disponible y exceder el cupo_maximo del segmento.
    Segmento.objects.select_for_update().get(pk=segmento.pk)

    stats = get_cupo_stats(segmento)
    if stats["cupo_disponible"] <= 0:
        raise ValidationError(f"No hay cupo disponible en el segmento '{segmento.nombre}'.")

    formulario = lista_espera.formulario
    validar_aprobacion(formulario)
    estado_anterior = formulario.estado
    formulario.estado = Formulario.Estado.APROBADO
    formulario.save(update_fields=["estado", "modificado"])

    lista_espera.promovido = True
    lista_espera.save(update_fields=["promovido", "modificado"])

    registrar_traza(
        formulario,
        user,
        [
            ("estado", estado_anterior, Formulario.Estado.APROBADO),
            ("lista_espera.promovido", "False", "True"),
        ],
    )


@transaction.atomic
def aprobar_o_poner_en_espera(formulario, user):
    """Aprueba un formulario ENVIADO si hay cupo; si no, lo agrega a lista de
    espera (RN-02/03: el cupo se consume solo si hay disponibilidad).

    Bloquea el segmento antes de leer el cupo para evitar que dos aprobaciones
    concurrentes exceedan el cupo_maximo (mismo lock que agregar_a_lista_espera).
    Raises ValidationError si el formulario no está en estado ENVIADO.

    Retorna "aprobado" o "lista_espera" según el resultado.
    """
    if formulario.estado != Formulario.Estado.ENVIADO:
        raise ValidationError("Solo se pueden aprobar formularios en estado ENVIADO.")

    validar_aprobacion(formulario)

    segmento = formulario.relevamiento.convocatoria.segmento
    Segmento.objects.select_for_update().get(pk=segmento.pk)

    if get_cupo_stats(segmento)["cupo_disponible"] > 0:
        estado_anterior = formulario.estado
        formulario.estado = Formulario.Estado.APROBADO
        formulario.motivo_rechazo = ""
        formulario.save(update_fields=["estado", "motivo_rechazo", "modificado"])
        registrar_traza(formulario, user, [("estado", estado_anterior, Formulario.Estado.APROBADO)])
        return "aprobado"

    agregar_a_lista_espera(formulario, segmento, user)
    return "lista_espera"


@transaction.atomic
def agregar_a_lista_espera(formulario, segmento, user):
    """Agrega manualmente un formulario ENVIADO a la lista de espera del segmento.

    Asigna la siguiente posición disponible. Raises ValidationError si el
    formulario ya tiene una entrada activa en la lista de espera.
    """
    if formulario.estado != Formulario.Estado.ENVIADO:
        raise ValidationError("Solo se pueden agregar formularios en estado ENVIADO a la lista de espera.")

    ya_en_espera = ListaEspera.objects.filter(
        formulario=formulario,
        segmento=segmento,
        promovido=False,
    ).exists()
    if ya_en_espera:
        raise ValidationError("Este formulario ya está en la lista de espera de este segmento.")

    # Serializa altas concurrentes en el mismo segmento: sin este lock, dos
    # requests simultáneos pueden leer el mismo Max("posicion") y crear
    # entradas con la misma posición.
    Segmento.objects.select_for_update().get(pk=segmento.pk)

    max_pos = ListaEspera.objects.filter(segmento=segmento, promovido=False).aggregate(m=Max("posicion"))["m"] or 0
    posicion = max_pos + 1

    ListaEspera.objects.create(
        formulario=formulario,
        segmento=segmento,
        posicion=posicion,
    )
    registrar_traza(
        formulario,
        user,
        [("lista_espera", "", f"Posición {posicion} en {segmento.nombre}")],
    )
