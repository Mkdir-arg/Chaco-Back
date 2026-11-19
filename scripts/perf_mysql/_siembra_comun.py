"""Piezas que comparten ``escalar_emergencia.py`` y ``escalar_dispositivos.py``.

Todo lo que siembran estos scripts lleva un prefijo reconocible (``BENCH`` en códigos y
números, ``bench_`` en usuarios, DNIs en el rango ``10000000``–``10999999``) y se arma
**hasta un objetivo**: correrlos dos veces no duplica nada, completa lo que falta. No
tocan ``seed_perf`` (lo usa el CI de performance) ni borran datos de otros: solo crean.

Importar este módulo exige haber llamado antes a ``_bootstrap.cargar_django()``.
"""

import time as reloj
from datetime import time, timedelta

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.utils import timezone
from rest_framework.authtoken.models import Token

from core import rbac
from legajos.models import Ciudadano
from programas.models import (
    Dispositivo,
    MiembroEquipoDispositivo,
    Plaza,
    Programa,
    Sector,
    TipoDispositivo,
    Turno,
)
from users.models import Capacidad
from users.services.roles import asegurar_rol_sembrado

PREFIJO = "BENCH"
CLAVE_ROL = "bench."
PASSWORD = "bench-perf-2026"
LOTE = 2000
PRIMER_DNI = 10_000_000

#: Los roles del banco: clave → (nombre, programa, capacidades). El nombre es único y reconocible.
ROLES = {
    "mesa": (
        "BENCH Emergencia — Mesa",
        rbac.CODIGO_PROGRAMA_EMERGENCIA,
        ("emergencia.operar", "ciudadano.ver"),
    ),
    "supervisor": (
        "BENCH Emergencia — Supervisor",
        rbac.CODIGO_PROGRAMA_EMERGENCIA,
        ("emergencia.operar", "emergencia.supervisar", "ciudadano.ver"),
    ),
    "agente": (
        "BENCH Emergencia — Agente de campo",
        rbac.CODIGO_PROGRAMA_EMERGENCIA,
        ("emergencia.relevar", "ciudadano.ver"),
    ),
    "guardia": (
        "BENCH Dispositivos — Guardia",
        rbac.CODIGO_PROGRAMA_DISPOSITIVOS,
        (
            "dispositivo.ver",
            "dispositivo.admitir",
            "dispositivo.egresar",
            "dispositivo.bitacora",
            "emergencia.recibir_kit",
            "inspeccion.relevar",
            "ciudadano.ver",
        ),
    ),
    "admin_dispositivos": (
        "BENCH Dispositivos — Administrador",
        rbac.CODIGO_PROGRAMA_DISPOSITIVOS,
        (
            "programa.configurar",
            "dispositivo.ver",
            "dispositivo.crear",
            "dispositivo.editar",
            "dispositivo.validar",
            "dispositivo.admitir",
            "dispositivo.egresar",
            "dispositivo.bitacora",
            "emergencia.recibir_kit",
            "inspeccion.asignar",
            "edificio.ver",
            "ciudadano.ver",
        ),
    ),
    "coordinador": (
        "BENCH Dispositivos — Coordinador",
        rbac.CODIGO_PROGRAMA_DISPOSITIVOS,
        ("dispositivo.ver", "inspeccion.asignar", "edificio.ver", "ciudadano.ver"),
    ),
    "operador": (
        "BENCH Dispositivos — Operador",
        rbac.CODIGO_PROGRAMA_DISPOSITIVOS,
        ("dispositivo.ver", "dispositivo.bitacora"),
    ),
}


def ahora():
    return timezone.now()


def sin_auto_now(modelo, *campos):
    """Deja fijar a mano campos ``auto_now_add`` (la fecha de una traza, de un caso) en un ``bulk_create``.

    Solo vale para el proceso que lo llama; no toca el esquema ni el modelo en disco.
    """
    for nombre in campos:
        campo = modelo._meta.get_field(nombre)
        campo.auto_now_add = False
        campo.auto_now = False


def en_lotes(modelo, objetos, lote=LOTE):
    """``bulk_create`` por lotes y devuelve los objetos con pk (MariaDB 10.5+ los devuelve)."""
    if not connection.features.can_return_rows_from_bulk_insert:
        raise RuntimeError(
            "Los escaladores de Emergencia y Dispositivos exigen MariaDB 10.5+: necesitan que bulk_create "
            "devuelva las pk, y este motor no lo hace (MySQL 8)."
        )
    objetos = list(objetos)
    for i in range(0, len(objetos), lote):
        modelo.objects.bulk_create(objetos[i : i + lote])
    return objetos


def fecha_aleatoria(rng, desde, hasta):
    """Un ``datetime`` aware entre ``desde`` y ``hasta``."""
    return desde + timedelta(seconds=rng.randint(0, int((hasta - desde).total_seconds())))


# ---------------------------------------------------------------------------
# Roles y usuarios
# ---------------------------------------------------------------------------
def asegurar_rol(clave):
    """El rol del banco ``clave`` (de ``ROLES``), con sus capacidades. Idempotente."""
    nombre, codigo_programa, capacidades = ROLES[clave]
    programa = Programa.objects.get(codigo=codigo_programa)
    group, meta, _ = asegurar_rol_sembrado(
        f"{CLAVE_ROL}{clave}",
        nombre,
        {"descripcion": "Rol del banco de performance.", "categoria": rbac.CATEGORIA_PROGRAMA, "programa": programa},
    )
    if meta.programa_id != programa.pk or meta.categoria != rbac.CATEGORIA_PROGRAMA or not meta.activo:
        meta.programa, meta.categoria, meta.activo = programa, rbac.CATEGORIA_PROGRAMA, True
        meta.save()
    ct = ContentType.objects.get_for_model(Capacidad)
    etiquetas = dict(rbac.todas_las_capacidades())
    for codigo in capacidades:
        codename = rbac.codename_de(codigo)
        permiso, _ = Permission.objects.get_or_create(
            content_type=ct, codename=codename, defaults={"name": etiquetas.get(codename, codigo)}
        )
        group.permissions.add(permiso)
    return group


def asegurar_usuarios(prefijo, cantidad, rol, *, token=False, staff=True):
    """``cantidad`` usuarios ``<prefijo>_NN`` con ``rol``. Devuelve la lista (ordenada por username)."""
    usernames = [f"{prefijo}_{i:04d}" if cantidad > 99 else f"{prefijo}_{i:02d}" for i in range(1, cantidad + 1)]
    existentes = {u.username: u for u in User.objects.filter(username__in=usernames)}
    nuevos = []
    for username in usernames:
        if username not in existentes:
            usuario = User(username=username, first_name="Bench", last_name=username, is_staff=staff, is_active=True)
            if token:
                usuario.set_password(PASSWORD)
            else:
                usuario.set_unusable_password()
            nuevos.append(usuario)
    if nuevos:
        User.objects.bulk_create(nuevos, batch_size=LOTE)
    usuarios = list(User.objects.filter(username__in=usernames).order_by("username"))
    ya_en_rol = set(
        User.groups.through.objects.filter(group=rol, user__in=[u.pk for u in usuarios]).values_list(
            "user_id", flat=True
        )
    )
    User.groups.through.objects.bulk_create(
        [User.groups.through(user_id=u.pk, group_id=rol.pk) for u in usuarios if u.pk not in ya_en_rol],
        batch_size=LOTE,
    )
    if token:
        for u in usuarios:
            Token.objects.get_or_create(user=u)
    return usuarios


# ---------------------------------------------------------------------------
# Ciudadanos
# ---------------------------------------------------------------------------
def asegurar_ciudadanos(cantidad, *, con_puntos_pct=0.7):
    """Lleva el padrón del banco a ``cantidad`` filas con DNI ``10000000 + i``.

    ``con_puntos_pct`` % de las filas se guardan con puntos («12.345.678»), el formato que
    obliga al ``REGEXP`` del alta (E-PERF-01). Devuelve las pk de las primeras ``cantidad``
    filas del banco, en orden de alta.
    """
    cada = max(1, round(100 / con_puntos_pct)) if con_puntos_pct else 0

    def dni_de(i):
        n = PRIMER_DNI + i
        return f"{n // 1_000_000}.{n // 1000 % 1000:03d}.{n % 1000:03d}" if cada and i % cada == 7 else f"{n}"

    ya = Ciudadano.objects.filter(apellido__startswith=PREFIJO, dni__gte="10", dni__lt="11").count()
    if ya < cantidad:
        existentes = set(
            Ciudadano.objects.filter(apellido__startswith=PREFIJO, dni__gte="10", dni__lt="11").values_list(
                "dni", flat=True
            )
        )
        pendientes = []
        for i in range(cantidad):
            dni = dni_de(i)
            if dni in existentes:
                continue
            pendientes.append(
                Ciudadano(dni=dni, nombre=f"Persona{i}", apellido=f"{PREFIJO}{i:06d}", genero="F" if i % 2 else "M")
            )
            if len(pendientes) >= LOTE * 5:
                Ciudadano.objects.bulk_create(pendientes, batch_size=LOTE, ignore_conflicts=True)
                pendientes = []
        if pendientes:
            Ciudadano.objects.bulk_create(pendientes, batch_size=LOTE, ignore_conflicts=True)
    print(f"ciudadanos del banco: {Ciudadano.objects.filter(apellido__startswith=PREFIJO).count()}")
    return list(
        Ciudadano.objects.filter(apellido__startswith=PREFIJO, dni__gte="10", dni__lt="11")
        .order_by("pk")
        .values_list("pk", flat=True)[:cantidad]
    )


# ---------------------------------------------------------------------------
# Dispositivos, sectores, plazas y equipo
# ---------------------------------------------------------------------------
def asegurar_tipo():
    tipo, _ = TipoDispositivo.objects.get_or_create(
        codigo=f"{PREFIJO}_REFUGIO",
        defaults={
            "nombre": f"{PREFIJO} Refugio",
            "maneja_camas": True,
            "tipos_plaza_admitidos": ["CAMA", "CUPO", "TURNO"],
            "plaza_obligatoria_al_ingresar": True,
        },
    )
    return tipo


def asegurar_dispositivo(codigo, nombre, *, sectores, plazas_por_sector, turnos=0, tipo=None):
    """Un dispositivo ACTIVO con ``sectores`` × ``plazas_por_sector`` camas. Devuelve ``(dispositivo, creado)``.

    Si ya existe no toca nada de lo que tiene (la siembra no pisa lo que el banco ya midió).
    """
    tipo = tipo or asegurar_tipo()
    dispositivo = Dispositivo.objects.filter(codigo=codigo).first()
    if dispositivo is not None:
        return dispositivo, False
    dispositivo = Dispositivo.objects.create(
        tipo=tipo,
        codigo=codigo,
        nombre=nombre,
        domicilio="Calle Bench 123",
        localidad="Resistencia",
        camas_totales=sectores * plazas_por_sector,
        estado=Dispositivo.Estado.ACTIVO,
    )
    for s in range(sectores):
        sector = Sector.objects.create(
            dispositivo=dispositivo,
            nombre=f"Sector {s + 1}",
            tipo=Sector.Tipo.PABELLON,
            capacidad=plazas_por_sector,
        )
        Plaza.objects.bulk_create(
            [Plaza(sector=sector, codigo=f"C{p + 1:03d}", tipo=Plaza.Tipo.CAMA) for p in range(plazas_por_sector)]
        )
    for t in range(turnos):
        Turno.objects.create(
            dispositivo=dispositivo,
            nombre=("Mañana", "Tarde", "Noche")[t % 3],
            hora_desde=time(6 + 8 * t % 24, 0),
            hora_hasta=time((14 + 8 * t) % 24, 0),
            orden=t,
        )
    return dispositivo, True


def asegurar_equipo(dispositivos, usuario, rol, *, responsable=False):
    """Suma a ``usuario`` al Equipo de cada dispositivo con ``rol`` (idempotente)."""
    ya = set(MiembroEquipoDispositivo.objects.filter(usuario=usuario, rol=rol).values_list("dispositivo_id", flat=True))
    en_lotes(
        MiembroEquipoDispositivo,
        [
            MiembroEquipoDispositivo(dispositivo_id=d_id, usuario=usuario, rol=rol, es_responsable=responsable)
            for d_id in dispositivos
            if d_id not in ya
        ],
    )


def plazas_de(dispositivo_id):
    """``[(plaza_id, sector_id)]`` del dispositivo, ordenadas."""
    return list(
        Plaza.objects.filter(sector__dispositivo_id=dispositivo_id).order_by("pk").values_list("pk", "sector_id")
    )


def paso(texto):
    print(f"[{reloj.strftime('%H:%M:%S')}] {texto}", flush=True)


def asegurar_chicos(total, tipo):
    """Los dispositivos chicos ``BENCH-D-0001`` … (2 sectores × 25 camas, 1 turno); ``total`` cuenta al grande."""
    return [
        asegurar_dispositivo(
            f"BENCH-D-{i:04d}", f"BENCH Dispositivo {i:04d}", sectores=2, plazas_por_sector=25, turnos=1, tipo=tipo
        )[0]
        for i in range(1, total)
    ]


def asegurar_actores_de_dispositivos(grande, chicos):
    """Roles del banco y los tres actores de Dispositivos, cada uno en su Equipo.

    La guardia (con token) en todos los dispositivos; el administrador (con token) con alcance
    total; el coordinador, que no es admin, solo en el grande y los 40 primeros chicos.
    Devuelve ``(roles, guardia, admin, coordinador)``.
    """
    roles = {clave: asegurar_rol(clave) for clave in ROLES}
    guardia = asegurar_usuarios("bench_guardia", 1, roles["guardia"], token=True)[0]
    admin = asegurar_usuarios("bench_admin_disp", 1, roles["admin_dispositivos"], token=True)[0]
    coordinador = asegurar_usuarios("bench_coord", 1, roles["coordinador"], token=True)[0]
    asegurar_equipo([grande.pk] + [d.pk for d in chicos], guardia, roles["guardia"], responsable=True)
    asegurar_equipo([grande.pk] + [d.pk for d in chicos[:40]], coordinador, roles["coordinador"])
    return roles, guardia, admin, coordinador
