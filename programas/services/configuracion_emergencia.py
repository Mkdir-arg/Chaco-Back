"""Configuración de la mesa de Emergencia (pantalla E7): SLA y catálogo de kits.

Todo lo que escribe pasa por acá —la vista web hoy, la API el día que la haya (RU-2)— y
cada función vuelve a exigir ``emergencia.supervisar`` **con alcance sobre el programa
EMERGENCIA**: el decorador de la vista no es la única puerta.

Reglas que viven en este módulo:

* **RN-5.5** — cada campo del SLA que cambia deja una fila de ``TrazaConfiguracion``
  (quién, cuándo, campo, antes, después). Un guardado que no cambia nada no deja traza.
* **RN-4.7** — un ``TipoKit`` se crea, se edita y se activa o desactiva. No se borra.
* El guardado de E7 es **una sola transacción**: o entran el SLA y el catálogo, o no
  entra nada. Con dos supervisores guardando a la vez gana el último y la traza tiene
  los dos cambios (la fila del SLA se toma con ``select_for_update``, así que cada uno
  compara contra lo que dejó el anterior y no contra lo que tenía en pantalla).
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from programas.models import SLAEmergencia, TipoKit, TrazaConfiguracion
from programas.services.emergencia_programa import CAP_SUPERVISAR, programa_emergencia, puede_en_programa_emergencia

#: Los campos del SLA que E7 deja editar, en el orden de la pantalla.
CAMPOS_SLA = (
    "nombre_evento",
    "objetivo_tomar_min",
    "objetivo_derivar_min",
    "objetivo_aceptar_min",
    "objetivo_alojar_min",
    "vigencia_derivacion_min",
    "sin_avance_min",
    "umbral_por_vencer_pct",
)

#: Los campos de un tipo de kit que E7 deja editar.
CAMPOS_TIPO_KIT = ("nombre", "unidad", "orden", "activo")

#: «Campo» de la traza del alta de un tipo de kit: no es una columna, es el hecho.
CAMPO_ALTA = "alta"

MENSAJE_SIN_PERMISO = "Solo quien supervisa la mesa de Emergencia puede cambiar su configuración."
MENSAJE_NOMBRE_DUPLICADO = "Ya existe un tipo de kit con ese nombre."


class ProgramaEmergenciaInexistente(RuntimeError):
    """El programa EMERGENCIA no está sembrado: no hay configuración que leer ni escribir."""


def _programa():
    programa = programa_emergencia()
    if programa is None:
        raise ProgramaEmergenciaInexistente(
            "El programa EMERGENCIA no existe en la base: corré las migraciones o `seed_emergencia`."
        )
    return programa


def _exigir_supervisar(usuario):
    if not puede_en_programa_emergencia(usuario, CAP_SUPERVISAR):
        raise PermissionDenied(MENSAJE_SIN_PERMISO)


def _texto(valor):
    """Cómo se guarda un valor en la traza: lo que leería una persona."""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    return "" if valor is None else str(valor)


def _trazar(programa, usuario, objeto, objeto_id, cambios):
    """Una fila de traza por cada ``(campo, anterior, nuevo)``."""
    for campo, anterior, nuevo in cambios:
        TrazaConfiguracion.objects.create(
            programa=programa,
            usuario=usuario,
            objeto=objeto,
            objeto_id=objeto_id,
            campo=campo,
            valor_anterior=_texto(anterior),
            valor_nuevo=_texto(nuevo),
        )


def _aplicar(instancia, campos, permitidos):
    """Asigna ``campos`` y devuelve ``[(campo, anterior, nuevo)]`` solo de lo que cambió."""
    desconocidos = set(campos) - set(permitidos)
    if desconocidos:
        raise TypeError(f"Campos que no son de la configuración: {', '.join(sorted(desconocidos))}.")
    cambios = []
    for campo in permitidos:
        if campo not in campos:
            continue
        anterior, nuevo = getattr(instancia, campo), campos[campo]
        if anterior != nuevo:
            setattr(instancia, campo, nuevo)
            cambios.append((campo, anterior, nuevo))
    return cambios


# ---------------------------------------------------------------------------
# SLA
# ---------------------------------------------------------------------------


def sla_vigente():
    """La fila de ``SLAEmergencia`` del programa. Si falta, nace con los valores de fábrica.

    Es de **lectura**: no exige capacidad. La leen el tablero, la bandeja y el detalle del
    caso para calcular el semáforo, y ahí quien mira no tiene por qué supervisar.
    """
    sla, _creada = SLAEmergencia.objects.get_or_create(programa=_programa())
    return sla


@transaction.atomic
def guardar_sla(usuario, **campos):
    """Guarda los campos del SLA que cambiaron y deja una traza por cada uno.

    Valida con los validadores del modelo (objetivos ≥ 1, vigencia ≥ 30, umbral entre 50 y
    95): un valor fuera de rango levanta ``ValidationError`` y no se guarda nada.
    """
    _exigir_supervisar(usuario)
    programa = _programa()
    SLAEmergencia.objects.get_or_create(programa=programa)
    sla = SLAEmergencia.objects.select_for_update().get(programa=programa)
    cambios = _aplicar(sla, campos, CAMPOS_SLA)
    if not cambios:
        return sla
    sla.full_clean()
    sla.save(update_fields=[campo for campo, _anterior, _nuevo in cambios] + ["modificado"])
    _trazar(programa, usuario, TrazaConfiguracion.Objeto.SLA, sla.pk, cambios)
    return sla


# ---------------------------------------------------------------------------
# Catálogo de kits
# ---------------------------------------------------------------------------


def catalogo_kits(solo_activos=False):
    """Los tipos de kit en el orden del catálogo. ``solo_activos`` es lo que ve una entrega nueva."""
    tipos = TipoKit.objects.order_by("orden", "nombre")
    return tipos.filter(activo=True) if solo_activos else tipos


def normalizar_nombre(nombre):
    """Sin espacios de más: «Agua  6 l » y «Agua 6 l» son el mismo ítem."""
    return " ".join((nombre or "").split())


def nombre_de_kit_en_uso(nombre, excluir_pk=None):
    """¿Ya hay un tipo de kit con ese nombre? Sin distinguir mayúsculas, en cualquier motor."""
    repetidos = TipoKit.objects.filter(nombre__iexact=normalizar_nombre(nombre))
    if excluir_pk is not None:
        repetidos = repetidos.exclude(pk=excluir_pk)
    return repetidos.exists()


def _validar_tipo_kit(tipo):
    if nombre_de_kit_en_uso(tipo.nombre, excluir_pk=tipo.pk):
        raise ValidationError({"nombre": MENSAJE_NOMBRE_DUPLICADO})
    tipo.full_clean()


@transaction.atomic
def crear_tipo_kit(usuario, *, nombre, unidad, orden=0, activo=True):
    """Agrega un ítem al catálogo. Deja una traza de alta."""
    _exigir_supervisar(usuario)
    tipo = TipoKit(nombre=normalizar_nombre(nombre), unidad=(unidad or "").strip(), orden=orden, activo=activo)
    _validar_tipo_kit(tipo)
    tipo.save()
    _trazar(
        _programa(),
        usuario,
        TrazaConfiguracion.Objeto.TIPO_KIT,
        tipo.pk,
        [(CAMPO_ALTA, "", str(tipo))],
    )
    return tipo


@transaction.atomic
def editar_tipo_kit(usuario, tipo, **campos):
    """Cambia nombre, unidad, orden o estado de un ítem. Una traza por campo que cambió."""
    _exigir_supervisar(usuario)
    return _editar_bloqueado(usuario, TipoKit.objects.select_for_update().get(pk=tipo.pk), campos)


def _editar_bloqueado(usuario, tipo, campos):
    """La edición sobre una fila ya tomada con ``select_for_update``."""
    campos = dict(campos)
    if "nombre" in campos:
        campos["nombre"] = normalizar_nombre(campos["nombre"])
    if "unidad" in campos:
        campos["unidad"] = (campos["unidad"] or "").strip()
    cambios = _aplicar(tipo, campos, CAMPOS_TIPO_KIT)
    if not cambios:
        return tipo
    _validar_tipo_kit(tipo)
    tipo.save(update_fields=[campo for campo, _anterior, _nuevo in cambios] + ["modificado"])
    _trazar(_programa(), usuario, TrazaConfiguracion.Objeto.TIPO_KIT, tipo.pk, cambios)
    return tipo


def cambiar_estado_tipo_kit(usuario, tipo, activo):
    """Activa o desactiva un ítem (RN-4.7): desactivado deja de ofrecerse, no desaparece."""
    return editar_tipo_kit(usuario, tipo, activo=bool(activo))


# ---------------------------------------------------------------------------
# El guardado de E7
# ---------------------------------------------------------------------------


@transaction.atomic
def guardar_configuracion(usuario, *, sla, kits):
    """Guarda la pantalla E7 entera en una transacción.

    ``sla`` es el dict de campos del SLA. ``kits`` es una lista de ``(tipo, campos)``: con
    ``tipo`` se edita ese ítem, con ``None`` se crea uno. Si algo falla no queda nada
    guardado ni ninguna traza.
    """
    _exigir_supervisar(usuario)
    guardado = guardar_sla(usuario, **sla)
    # Los ítems que se editan se toman todos juntos, en una consulta y en orden de pk: una
    # por fila sería un N+1, y dos guardados simultáneos se cruzarían los candados.
    a_editar = [tipo.pk for tipo, _campos in kits if tipo is not None]
    bloqueados = {tipo.pk: tipo for tipo in TipoKit.objects.select_for_update().filter(pk__in=a_editar).order_by("pk")}
    for tipo, campos in kits:
        if tipo is None:
            crear_tipo_kit(usuario, **campos)
        else:
            _editar_bloqueado(usuario, bloqueados[tipo.pk], campos)
    return guardado
