"""Lo que lee la guardia del dispositivo en la etapa 3 de Emergencia (alojar).

Solo lectura: nada de acá escribe ni decide una transición (eso es
``programas.services.emergencia_alojar``). Lo consumen la pantalla E6 del backoffice y, tal
cual, la API de la app (PR 8): por eso devuelven **datos planos** —dicts y listas— y no
objetos de pantalla.

Tres reglas:

* **Quién puede.** ``plazas_para_caso`` y ``llegadas_del_dispositivo`` exigen ellas mismas
  ``dispositivo.admitir`` sobre **ese** dispositivo (RU-8, RU-9): contestan sobre camas y
  familias de una institución, y no confían en que la vista se haya acordado. Sin alcance,
  ``PermissionDenied`` (la vista ya contestó 404 antes, plan C2).
* **Una sola fuente del estado de una plaza.** El estado sale de
  ``ocupacion.estado_de_plazas``, la misma lectura de «Sectores y plazas» y del asistente
  de ingreso. Acá solo se **traduce** a los cinco códigos del contrato de la app y se
  distingue, con ``EstadoPlaza.derivacion_id``, la cama guardada para *esta* familia de la
  guardada para otra.
* **Presupuesto de consultas** (``read_timeout`` de 10 s). Cada función dice cuántas hace,
  y ``programas.tests.test_emergencia_alojar`` lo fija con ``assertNumQueries`` sobre un
  dispositivo de 300 camas.
"""

from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q

from programas.models import CasoEmergencia, Derivacion, IntegranteGrupo, Plaza, Sector
from programas.services.dispositivos import puede_operar_dispositivo
from programas.services.nombre_plaza import clave_natural, plaza_con_sector
from programas.services.ocupacion import (
    ESTADO_DISPONIBLE,
    ESTADO_FUERA_SERVICIO,
    ESTADO_OCUPADA,
    LEYENDA_PLAZAS,
    estado_de_plazas,
)

CAP_ADMITIR = "dispositivo.admitir"

SIN_ALCANCE = "No formás parte del equipo de este dispositivo."

#: Los cinco estados de una cama en el contrato de la app (03 §7, ``…/plazas/?caso=``).
#: ``RESERVADA`` es la guardada para **otra** persona o familia (también la prestada): no
#: se puede elegir. ``RESERVADA_FAMILIA`` es una de las de la derivación de este caso.
PLAZA_LIBRE = "LIBRE"
PLAZA_RESERVADA_FAMILIA = "RESERVADA_FAMILIA"
PLAZA_OCUPADA = "OCUPADA"
PLAZA_FUERA_SERVICIO = "FUERA_SERVICIO"
PLAZA_RESERVADA = "RESERVADA"
ESTADOS_DE_PLAZA = (PLAZA_LIBRE, PLAZA_RESERVADA_FAMILIA, PLAZA_OCUPADA, PLAZA_FUERA_SERVICIO, PLAZA_RESERVADA)
#: Las que la guardia puede elegir para una persona de la familia.
PLAZAS_ELEGIBLES = (PLAZA_LIBRE, PLAZA_RESERVADA_FAMILIA)

#: El texto de la cama guardada para la familia que está ingresando. Es **el** portador de
#: la diferencia con la reserva ajena: las dos comparten tono e ícono (ficha
#: ``mapa_plazas.md``, «Consumidor: modo emergencia»).
TEXTO_RESERVADA_FAMILIA = "Reservada para esta familia"
TONO_RESERVADA = "warning"

#: La leyenda del mapa en modo emergencia: la de siempre más la entrada de la familia.
LEYENDA_PLAZAS_EMERGENCIA = [
    *LEYENDA_PLAZAS[:2],
    {"estado": TEXTO_RESERVADA_FAMILIA, "tono": TONO_RESERVADA},
    *LEYENDA_PLAZAS[2:],
]

#: Mismo tope por sector que el mapa de «Sectores y plazas» y el del ingreso.
TOPE_PLAZAS_POR_SECTOR = 200

#: Estados de una fila de integrante (03 §7, ``…/integrantes/``).
INTEGRANTE_SIN_CONFIRMAR = "SIN_CONFIRMAR"
INTEGRANTE_CONFIRMADA = "CONFIRMADA"
INTEGRANTE_EGRESADA = "EGRESADA"


def _exigir_alcance(usuario, dispositivo):
    if not puede_operar_dispositivo(usuario, dispositivo, CAP_ADMITIR):
        raise PermissionDenied(SIN_ALCANCE)


# ---------------------------------------------------------------------------
# Camas
# ---------------------------------------------------------------------------


def _camas_del_dispositivo(dispositivo):
    """Las camas de los sectores activos, con su sector. **1 consulta.**

    Solo ``Plaza.Tipo.CAMA`` y solo si el tipo del dispositivo la admite: es lo que la mesa
    contó como plaza al derivar (``selectors.emergencia.dispositivo_elegible``).
    """

    if not dispositivo.tipo.admite_tipo_de_plaza(Plaza.Tipo.CAMA):
        return []
    return list(
        Plaza.objects.filter(sector__dispositivo=dispositivo, sector__activo=True, tipo=Plaza.Tipo.CAMA)
        .select_related("sector")
        .only(
            "id", "sector_id", "codigo", "tipo", "estado", "motivo_fuera_servicio", "sector__nombre", "sector__perfil"
        )
    )


def camas_libres(dispositivo, momento=None):
    """Las camas que se le pueden guardar a una familia **ahora**, en el orden en que se eligen (RN-3.4).

    Primero el sector con más camas libres —para que la familia quede junta—, y dentro del
    sector por código en orden natural (``B-9`` antes que ``B-10``). Los empates entre
    sectores se resuelven por nombre y por id: el orden es determinista.

    Es una **foto sin candado**, igual que la que usa la mesa al derivar: sirve para elegir,
    no garantiza. La garantía la da ``reservas_derivacion.reservar_plazas_de_derivacion``, que bloquea
    cada plaza y vuelve a mirar. No exige capacidad: la llaman los servicios, que ya la
    exigieron.

    **3 consultas**: las camas con su sector y las dos de ``estado_de_plazas``.
    """

    camas = _camas_del_dispositivo(dispositivo)
    if not camas:
        return []
    estados = estado_de_plazas(camas, momento)
    por_sector = {}
    for cama in camas:
        if estados[cama.pk].disponible:
            por_sector.setdefault(cama.sector_id, []).append(cama)
    sectores = sorted(
        por_sector.values(),
        key=lambda libres: (-len(libres), libres[0].sector.nombre.casefold(), libres[0].sector_id),
    )
    return [cama for libres in sectores for cama in sorted(libres, key=lambda c: clave_natural(c.codigo))]


def derivacion_vigente_en(caso, dispositivo):
    """El id de la derivación vigente de ``caso`` hacia ``dispositivo``, o ``None``. **1 consulta.**"""

    if caso is None:
        return None
    return (
        Derivacion.objects.filter(clave_vigente=getattr(caso, "pk", caso), dispositivo=dispositivo)
        .values_list("pk", flat=True)
        .first()
    )


def plazas_para_caso(dispositivo, caso, usuario, *, puede_ver_personas=False, momento=None):
    """El mapa de camas del dispositivo para alojar a la familia de ``caso`` (03 §7, M2-4).

    Devuelve una lista con un dict por **sector activo que tiene camas**, ordenados por
    nombre::

        {
            "sector": {"id": 3, "nombre": "Pabellón A", "perfil": "Familias"},
            "plazas": [
                {"id": 41, "codigo": "A-01", "nombre": "A-01 (Pabellón A)",
                 "estado": "RESERVADA_FAMILIA", "elegible": True,
                 "texto": "Reservada para esta familia", "tono": "warning", "detalle": ""},
                …
            ],
            "total": 40,               # camas del sector (``plazas`` trae a lo sumo 200)
            "libres": 12,
            "reservadas_familia": 7,
        }

    ``estado`` es uno de :data:`ESTADOS_DE_PLAZA`; ``elegible`` es «libre o guardada para
    esta familia» y es lo único que la pantalla tiene que mirar para dejar elegir. ``texto``
    y ``tono`` son los de la pieza ``_mapa_plazas`` (la app puede ignorarlos). ``detalle``
    trae el motivo de la fuera de servicio y, solo con ``puede_ver_personas`` (la vista lo
    resuelve con ``ciudadano.ver``), quién ocupa la cama.

    ``caso`` puede ser ``None`` (ingreso directo, antes de que exista el caso): ninguna cama
    sale como de la familia.

    Exige ``dispositivo.admitir`` sobre el dispositivo: sin alcance, ``PermissionDenied``.
    Una cama guardada para la familia de **otro** caso sale ``RESERVADA`` y nada más: ni de
    quién ni de qué caso (RU-9).

    **Presupuesto: 4 consultas más las del alcance** (a lo sumo dos: las capacidades del
    usuario, que ``rbac`` memoiza en el objeto, y si integra el Equipo): camas con su sector,
    las dos de ``estado_de_plazas`` y la derivación vigente del caso. No depende de cuántas
    camas haya.
    """

    _exigir_alcance(usuario, dispositivo)
    camas = _camas_del_dispositivo(dispositivo)
    estados = estado_de_plazas(camas, momento, puede_ver_personas=puede_ver_personas) if camas else {}
    derivacion_id = derivacion_vigente_en(caso, dispositivo)

    por_sector = {}
    for cama in sorted(camas, key=lambda c: clave_natural(c.codigo)):
        derivado = estados[cama.pk]
        texto, tono, detalle = derivado.estado, derivado.tono, derivado.detalle
        if derivado.estado == ESTADO_FUERA_SERVICIO:
            estado = PLAZA_FUERA_SERVICIO
        elif derivado.estado == ESTADO_OCUPADA:
            estado = PLAZA_OCUPADA
        elif derivado.estado == ESTADO_DISPONIBLE:
            estado = PLAZA_LIBRE
        elif derivacion_id is not None and derivado.derivacion_id == derivacion_id:
            estado, texto, tono, detalle = PLAZA_RESERVADA_FAMILIA, TEXTO_RESERVADA_FAMILIA, TONO_RESERVADA, ""
        else:
            # Reservada o prestada para otra persona u otra familia. El detalle de una reserva
            # de derivación nombra al responsable de **otro** caso: no cruza (RU-9).
            estado = PLAZA_RESERVADA
            if derivado.derivacion_id is not None:
                detalle = ""
        armado = por_sector.setdefault(
            cama.sector_id,
            {
                "sector": {"id": cama.sector_id, "nombre": cama.sector.nombre, "perfil": cama.sector.perfil},
                "plazas": [],
                "total": 0,
                "libres": 0,
                "reservadas_familia": 0,
            },
        )
        armado["total"] += 1
        armado["libres"] += estado == PLAZA_LIBRE
        armado["reservadas_familia"] += estado == PLAZA_RESERVADA_FAMILIA
        if len(armado["plazas"]) < TOPE_PLAZAS_POR_SECTOR:
            armado["plazas"].append(
                {
                    "id": cama.pk,
                    "codigo": cama.codigo,
                    "nombre": plaza_con_sector(cama, cama.sector.nombre),
                    "estado": estado,
                    "elegible": estado in PLAZAS_ELEGIBLES,
                    "texto": texto,
                    "tono": tono,
                    "detalle": detalle,
                }
            )
    return sorted(
        por_sector.values(), key=lambda armado: (armado["sector"]["nombre"].casefold(), armado["sector"]["id"])
    )


# ---------------------------------------------------------------------------
# Integrantes
# ---------------------------------------------------------------------------


def integrantes_de(caso):
    """Las filas de la familia como las muestra M2-3 / E6-integrantes (03 §7, ``…/integrantes/``).

    Devuelve::

        {
            "integrantes": [
                {"n": 1, "estado": "CONFIRMADA", "ficha_completa": False,
                 "persona": {"id": 9, "nombre": "Pérez, Juan", "dni": "30111222"},
                 "plaza": {"id": 41, "codigo": "B-12", "nombre": "B-12 (Pabellón B)", "sector_id": 3},
                 "parentesco": "Jefe/a de hogar",
                 "confirmada_en": datetime, "egresado_en": None, "estadia_id": 77},
                {"n": 2, "estado": "SIN_CONFIRMAR", "ficha_completa": False,
                 "persona": None, "plaza": None, "parentesco": "",
                 "confirmada_en": None, "egresado_en": None, "estadia_id": None},
                …
            ],
            "confirmadas": 1,            # el contador «1 de 7 confirmadas»
            "total_declarado": 7,        # filas de la familia (crece con «Agregar persona»)
            "declaradas_al_relevar": 7,  # lo que dijo el Formulario 1 («llegaron 8 sobre 7»)
            "con_ficha_incompleta": 1,
        }

    ``estado`` es ``SIN_CONFIRMAR``, ``CONFIRMADA`` o ``EGRESADA`` (confirmada que ya se fue).
    ``plaza`` es la que la estadía tiene **hoy** —si la cambiaron de cama desde el mapa, la
    nueva—, o ``None`` si no tiene. No exige capacidad: la abren la guardia del dispositivo
    del caso (la vista lo exigió) y la ficha de la mesa, que ve todos los casos.

    **Presupuesto: 1 consulta** (los integrantes con persona, estadía, plaza y sector), más
    una si ``caso`` llegó sin su grupo cargado.
    """

    grupo = caso.grupo
    filas = (
        IntegranteGrupo.objects.filter(grupo_id=grupo.pk)
        .select_related("ciudadano", "estadia__plaza__sector")
        .order_by("orden")
    )
    integrantes = []
    confirmadas = incompletas = 0
    for fila in filas:
        if not fila.confirmada:
            estado = INTEGRANTE_SIN_CONFIRMAR
        elif fila.egresado_en is not None:
            estado = INTEGRANTE_EGRESADA
        else:
            estado = INTEGRANTE_CONFIRMADA
        confirmadas += fila.confirmada
        incompletas += fila.confirmada and not fila.ficha_completa
        persona = plaza = None
        if fila.ciudadano_id:
            persona = {"id": fila.ciudadano_id, "nombre": fila.ciudadano.apellido_nombre, "dni": fila.ciudadano.dni}
        if fila.estadia_id and fila.estadia.plaza_id:
            cama = fila.estadia.plaza
            plaza = {
                "id": cama.pk,
                "codigo": cama.codigo,
                "nombre": plaza_con_sector(cama, cama.sector.nombre),
                "sector_id": cama.sector_id,
            }
        parentesco = fila.get_parentesco_display() if fila.parentesco else ""
        if fila.parentesco == IntegranteGrupo.Parentesco.OTRO and fila.parentesco_otro:
            parentesco = fila.parentesco_otro
        integrantes.append(
            {
                "n": fila.orden,
                "estado": estado,
                "ficha_completa": fila.ficha_completa,
                "persona": persona,
                "plaza": plaza,
                "parentesco": parentesco,
                "confirmada_en": fila.confirmada_en,
                "egresado_en": fila.egresado_en,
                "estadia_id": fila.estadia_id,
            }
        )
    return {
        "integrantes": integrantes,
        "confirmadas": confirmadas,
        "total_declarado": grupo.total_declarado,
        "declaradas_al_relevar": grupo.suma_de_cantidades(),
        "con_ficha_incompleta": incompletas,
    }


# ---------------------------------------------------------------------------
# Llegadas del dispositivo
# ---------------------------------------------------------------------------


def llegadas_del_dispositivo(dispositivo, usuario):
    """Lo que la guardia tiene por recibir: derivaciones pendientes e ingresos en curso de **ese** dispositivo.

    Devuelve ``{"pendientes": [...], "en_curso": [...]}``; cada elemento es la ``Derivacion``
    con ``caso``, ``caso.grupo``, ``caso.grupo.responsable`` y ``derivada_por`` ya cargados, y
    la anotación ``confirmadas`` (cuántas fichas confirmó ya la guardia). Las pendientes van
    por vencimiento —la que vence antes, arriba— y las en curso por cuándo se aceptaron.

    Solo las de casos ``DERIVADO`` (pendientes) o ``INGRESO_EN_CURSO`` (aceptadas): una
    familia ya alojada no es una llegada. Nunca trae nada de otro dispositivo (RU-9).

    Exige ``dispositivo.admitir`` sobre el dispositivo: sin alcance, ``PermissionDenied``.

    **Presupuesto: 1 consulta más las del alcance.**
    """

    _exigir_alcance(usuario, dispositivo)
    derivaciones = (
        Derivacion.objects.filter(dispositivo=dispositivo)
        .filter(
            Q(estado=Derivacion.Estado.PENDIENTE, caso__estado=CasoEmergencia.Estado.DERIVADO)
            | Q(estado=Derivacion.Estado.ACEPTADA, caso__estado=CasoEmergencia.Estado.INGRESO_EN_CURSO)
        )
        .select_related("caso__grupo__responsable", "derivada_por")
        .annotate(
            confirmadas=Count(
                "caso__grupo__integrantes", filter=Q(caso__grupo__integrantes__confirmada_en__isnull=False)
            )
        )
        .order_by("vence_en", "id")
    )
    pendientes, en_curso = [], []
    for derivacion in derivaciones:
        (pendientes if derivacion.estado == Derivacion.Estado.PENDIENTE else en_curso).append(derivacion)
    en_curso.sort(key=lambda derivacion: (derivacion.respondida_en or derivacion.creado, derivacion.pk))
    return {"pendientes": pendientes, "en_curso": en_curso}


def sectores_del_dispositivo(dispositivo):
    """Los sectores activos del dispositivo, por nombre: las opciones de «Sector / ala» de M2-5. **1 consulta.**"""

    return Sector.objects.filter(dispositivo=dispositivo, activo=True).order_by("nombre")
