"""Definición única de los roles de Dispositivos y Emergencia que se siembran a mano.

Los recorre ``sembrar_roles_dispositivos_emergencia`` (que corre el PM en el pod de ECOM, donde
el bootstrap no corre). El agente de relevamiento lo siembra además ``seed_dispositivos`` en el
arranque: los dos leen **esta** definición, así que nombre, clave y capacidad no se repiten.

Cada rol se identifica por su ``clave`` (``RolMeta.clave``), no por el nombre: uno renombrado
desde el ABM sigue siendo el mismo. Las capacidades de acá son las **de origen**: solo se
aplican al crear el rol; el PM las edita después desde Roles y la siembra no se las devuelve.
"""

from dataclasses import dataclass

from core import rbac
from programas.services.inspecciones import CAP_RELEVAR, CLAVE_ROL_AGENTE, NOMBRE_ROL_AGENTE


@dataclass(frozen=True)
class RolSembrado:
    clave: str
    nombre: str
    descripcion: str
    capacidades: tuple
    #: Código del programa al que se ancla (categoría «Programa»).
    programa: str


DESCRIPCION_ROL_AGENTE = (
    "Releva edificios en campo: carga el resultado de los relevamientos edilicios que se le asignan."
)

_DISP = rbac.CODIGO_PROGRAMA_DISPOSITIVOS
_EMER = rbac.CODIGO_PROGRAMA_EMERGENCIA

ROL_AGENTE_RELEVAMIENTO = RolSembrado(
    clave=CLAVE_ROL_AGENTE,
    nombre=NOMBRE_ROL_AGENTE,
    descripcion=DESCRIPCION_ROL_AGENTE,
    capacidades=(CAP_RELEVAR,),
    programa=_DISP,
)

ROLES_DISPOSITIVOS_EMERGENCIA = (
    RolSembrado(
        "dispositivos.administrador",
        "Dispositivos — Administrador",
        "Administra el programa Dispositivos: configuración, usuarios, instituciones, relevamientos y plazas.",
        (
            "programa.configurar",
            "programa.usuario.administrar",
            "dispositivo.ver",
            "dispositivo.crear",
            "dispositivo.editar",
            "dispositivo.validar",
            "dispositivo.admitir",
            "dispositivo.egresar",
            "dispositivo.bitacora",
            "edificio.ver",
            "inspeccion.asignar",
            "inspeccion.agente.crear",
            "emergencia.recibir_kit",
            "ciudadano.ver",
            "stock.ver",
            "stock.entregar",
            "stock.ingresar",
            "stock.ajustar",
        ),
        _DISP,
    ),
    RolSembrado(
        "dispositivos.coordinador",
        "Dispositivos — Coordinador de institución",
        "Coordina una institución: edita el dispositivo, admite y egresa personas y da de alta agentes.",
        (
            "dispositivo.ver",
            "dispositivo.editar",
            "dispositivo.admitir",
            "dispositivo.egresar",
            "dispositivo.bitacora",
            "edificio.ver",
            "inspeccion.asignar",
            "inspeccion.agente.crear",
            "emergencia.recibir_kit",
            "ciudadano.ver",
            "stock.ver",
            "stock.entregar",
            "stock.ingresar",
            "stock.ajustar",
        ),
        _DISP,
    ),
    RolSembrado(
        "dispositivos.operador",
        "Dispositivos — Operador / Guardia",
        "Opera la guardia del dispositivo: admite, egresa, anota la bitácora y recibe kits.",
        (
            "dispositivo.ver",
            "dispositivo.admitir",
            "dispositivo.egresar",
            "dispositivo.bitacora",
            "emergencia.recibir_kit",
            "ciudadano.ver",
            "edificio.ver",
            "stock.ver",
            "stock.entregar",
        ),
        _DISP,
    ),
    RolSembrado(
        "dispositivos.consulta",
        "Dispositivos — Consulta",
        "Solo consulta dispositivos, edificios y su stock.",
        ("dispositivo.ver", "edificio.ver", "stock.ver"),
        _DISP,
    ),
    RolSembrado(
        "dispositivos.supervision_red",
        "Dispositivos — Supervisión de la red",
        "Consulta todos los dispositivos de la red y su stock, sin acotarse a una institución.",
        ("dispositivo.ver", "dispositivo.ver_todos", "edificio.ver", "stock.ver"),
        _DISP,
    ),
    ROL_AGENTE_RELEVAMIENTO,
    RolSembrado(
        "emergencia.agente_territorial",
        "Emergencia — Agente territorial",
        "Releva familias en campo desde la app de Emergencia.",
        ("emergencia.relevar",),
        _EMER,
    ),
    RolSembrado(
        "emergencia.operador_mesa",
        "Emergencia — Operador de mesa",
        "Opera la mesa de Emergencia: casos, derivaciones y entregas de kits.",
        ("emergencia.operar",),
        _EMER,
    ),
    RolSembrado(
        "emergencia.supervisor_mesa",
        "Emergencia — Supervisor de mesa",
        "Opera y supervisa la mesa de Emergencia.",
        ("emergencia.operar", "emergencia.supervisar"),
        _EMER,
    ),
    RolSembrado(
        "emergencia.autoridad",
        "Emergencia — Autoridad",
        "Ve la situación de Emergencia, sin operar.",
        ("emergencia.ver_situacion",),
        _EMER,
    ),
)
