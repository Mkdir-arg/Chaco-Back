"""Lógica de dominio para gestión de cupo y lista de espera (RN-04/05, issue #78).

El cupo ocupado se calcula dinámicamente (COUNT de formularios APROBADO) para
evitar desincronización con la integración SIIS futura (#72). CupoSegmento queda
como estructura base pero no se muta aquí.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, Max, OuterRef

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


#: CMP-N1 (decisión del usuario): quien está en lista de espera se aprueba
#: promoviéndolo desde Cupo, nunca con «Aprobar». Lo comparten el servicio y el
#: pre-chequeo de la vista, que corta antes de consultar a SIIS.
MENSAJE_CASO_EN_ESPERA = "El caso está en la lista de espera: se aprueba al promoverlo desde Cupo y beneficiarios."


class CasoEnListaEspera(ValidationError):
    """El caso tiene una entrada activa en la lista de espera (CMP-N1).

    Subclase para que el proceso masivo lo cuente aparte y no como «no aprobable».
    """

    def __init__(self):
        super().__init__(MENSAJE_CASO_EN_ESPERA)


def espera_activa(formulario):
    """Entradas de lista de espera todavía activas (ni promovidas ni cerradas) del caso."""
    return ListaEspera.objects.filter(formulario=formulario, promovido=False)


def cerrar_espera_activa(formulario, user, motivo):
    """Saca al caso de toda lista de espera en la que siga activo.

    Se llama en cada camino que resuelve el caso sin promoverlo (rechazo,
    descarte por duplicado, baja): la fila activa de un caso que ya no está
    pendiente ocupa un lugar en la lista y se podía «promover» a APROBADO.

    La fila se cierra con ``promovido=True``: es la única salida que el modelo
    conoce sin migración y la que ya excluyen todos los conteos de «en espera»
    (cupo, dashboard, reportes, exportación, solapa). Lo que distingue un cierre
    de una promoción es la traza, que deja el motivo. Va dentro de la
    transacción del cambio de estado. Devuelve cuántas filas cerró.
    """
    filas = list(espera_activa(formulario).select_related("segmento"))
    for fila in filas:
        fila.promovido = True
        fila.save(update_fields=["promovido", "modificado"])
    registrar_traza(
        formulario,
        user,
        [("lista_espera", f"Posición {f.posicion} en {f.segmento.nombre}", f"Cerrada: {motivo}") for f in filas],
    )
    return len(filas)


#: Centinela: distingue "no me pasaron la validacion" de "ya la busque y no hay".
_VALIDACION_SIN_BUSCAR = object()


def motivo_bloqueo_aprobacion(formulario, validacion=_VALIDACION_SIN_BUSCAR):
    """Explica por qué un formulario todavía no puede aprobarse.

    La aprobación exige identidad validada y que la consulta a SIIS **se haya
    hecho** para el DNI y el programa actuales. Devuelve ``None`` cuando supera
    el gate.

    **El veredicto de SIIS no bloquea** (Cambio 81, decisión del PM del
    21/09/2026): la aprobación es técnica y la resuelve el revisor. Un rechazo
    de compatibilidad o un error del servicio se **advierten**
    (:func:`advertencia_aprobacion`) pero no impiden aprobar, porque la persona
    no puede quedar retenida por cómo responda un sistema externo. Lo que sí es
    obligatorio es haber consultado: sin ese registro auditable no hay
    aprobación.
    """
    if not formulario.validado_renaper:
        return "La identidad debe estar validada antes de aprobar."
    if not formulario.ciudadano_id or not formulario.ciudadano.dni:
        return "El formulario debe tener un ciudadano con DNI vinculado."

    segmento = formulario.relevamiento.convocatoria.segmento
    programa = segmento.programa
    if programa is None:
        return "El segmento no tiene un programa SIIS configurado."

    if validacion is _VALIDACION_SIN_BUSCAR:
        validacion = formulario.validaciones_sis.order_by("-creado").first()
    if validacion is None:
        return "Debe realizarse la validación SIIS antes de aprobar."
    if str(validacion.documento).strip() != str(formulario.ciudadano.dni).strip():
        return "La validación SIIS no corresponde al DNI actual del formulario."
    if validacion.id_programa != programa.siis_id_plan_soc_efectivo:
        return "La validación SIIS no corresponde al programa actual del formulario."
    return None


def advertencia_aprobacion(formulario, validacion=_VALIDACION_SIN_BUSCAR):
    """Qué conviene que el revisor sepa antes de aprobar, sin impedírselo.

    Devuelve ``None`` cuando la última validación SIIS dio compatible o cuando
    hay un motivo de bloqueo, que ya se informa por su cuenta.
    """
    if motivo_bloqueo_aprobacion(formulario, validacion) is not None:
        return None
    if validacion is _VALIDACION_SIN_BUSCAR:
        validacion = formulario.validaciones_sis.order_by("-creado").first()
    if validacion is None or validacion.estado == ValidacionSIS.Estado.OK:
        return None
    if validacion.estado == ValidacionSIS.Estado.RECHAZADO:
        motivo = (validacion.motivo or "").strip()
        detalle = f" Motivo informado: {motivo}" if motivo else ""
        return (
            "SIIS informó que la persona no es compatible con el programa."
            f"{detalle} Podés aprobar igual: la decisión es tuya y queda registrada."
        )
    return (
        "La última consulta a SIIS terminó con un error técnico, así que no hay veredicto. "
        "Podés reintentarla o aprobar igual: la decisión es tuya y queda registrada."
    )


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
    # Un APROBADO ya no debería tener espera activa, pero los datos anteriores
    # a esta regla pueden traerla colgando: la baja no la deja viva.
    cerrar_espera_activa(formulario, user, "caso dado de baja")


def promover_lista_espera(lista_espera, user):
    """Promueve una entrada de lista de espera como beneficiario (RN-04).

    Solo se promueve un caso ``ENVIADO`` (pendiente de resolución) y con cupo
    disponible. Si el caso ya se resolvió por otro camino —rechazado, aprobado,
    dado de baja—, la fila no tenía que seguir activa: se cierra y se informa
    con ``ValidationError``. El cierre se confirma aunque se lance el error; por
    eso la transacción va adentro y ese ``raise`` afuera.

    Raises ValidationError si ya fue promovido, si el caso no está pendiente o
    si no hay cupo.
    """
    if lista_espera.promovido:
        raise ValidationError("Esta entrada ya fue promovida.")

    with transaction.atomic():
        segmento = lista_espera.segmento
        # Mismo lock que agregar_a_lista_espera: sin él, dos promociones (o una
        # promoción y una aprobación) concurrentes pueden leer el mismo
        # cupo_disponible y exceder el cupo_maximo del segmento.
        Segmento.objects.select_for_update().get(pk=segmento.pk)

        # Releídos bajo el lock: la fila y el estado del caso pueden haber
        # cambiado desde que la vista los cargó (otra promoción, un rechazo).
        promovido, estado_actual = (
            ListaEspera.objects.filter(pk=lista_espera.pk).values_list("promovido", "formulario__estado").get()
        )
        if promovido:
            raise ValidationError("Esta entrada ya fue promovida.")

        formulario = lista_espera.formulario
        if estado_actual != Formulario.Estado.ENVIADO:
            estado = Formulario.Estado(estado_actual).label.lower()
            cerrar_espera_activa(formulario, user, f"el caso ya estaba {estado}")
            lista_espera.promovido = True
            error = ValidationError(
                f"El caso ya no está pendiente de resolución ({estado}): se lo sacó de la lista de espera sin aprobarlo."
            )
        else:
            stats = get_cupo_stats(segmento)
            if stats["cupo_disponible"] <= 0:
                raise ValidationError(f"No hay cupo disponible en el segmento '{segmento.nombre}'.")

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
            return
    raise error


@transaction.atomic
def aprobar_o_poner_en_espera(formulario, user):
    """Aprueba un formulario ENVIADO si hay cupo; si no, lo agrega a lista de
    espera (RN-02/03: el cupo se consume solo si hay disponibilidad).

    Bloquea el segmento antes de leer el cupo para evitar que dos aprobaciones
    concurrentes exceedan el cupo_maximo (mismo lock que agregar_a_lista_espera).
    Raises ValidationError si el formulario no está en estado ENVIADO, y
    ``CasoEnListaEspera`` si ya está en una lista de espera (CMP-N1: ese caso se
    aprueba promoviéndolo desde Cupo, no acá).

    Retorna "aprobado" o "lista_espera" según el resultado.
    """
    if formulario.estado != Formulario.Estado.ENVIADO:
        raise ValidationError("Solo se pueden aprobar formularios en estado ENVIADO.")

    validar_aprobacion(formulario)

    segmento = formulario.relevamiento.convocatoria.segmento
    Segmento.objects.select_for_update().get(pk=segmento.pk)

    # Releídos bajo el lock, que es el mismo que toman la promoción y el alta a
    # la lista: una promoción o un alta concurrentes no se cuelan entre el
    # chequeo y la aprobación. Estado y espera en una sola consulta.
    estado_actual, en_espera = (
        Formulario.objects.filter(pk=formulario.pk)
        .annotate(en_espera=Exists(ListaEspera.objects.filter(formulario=OuterRef("pk"), promovido=False)))
        .values_list("estado", "en_espera")
        .get()
    )
    if estado_actual != Formulario.Estado.ENVIADO:
        raise ValidationError("El caso ya fue resuelto por otra operación: recargá la pantalla.")
    if en_espera:
        raise CasoEnListaEspera()

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
