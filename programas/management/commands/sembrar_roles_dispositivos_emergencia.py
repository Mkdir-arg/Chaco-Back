"""Crea los roles de Dispositivos y Emergencia (y el Administrador del sistema si falta).

Lo corre el PM a mano en el pod, porque ECOM no ejecuta el bootstrap::

    python manage.py sembrar_roles_dispositivos_emergencia --dry-run   # muestra, no escribe
    python manage.py sembrar_roles_dispositivos_emergencia             # crea lo que falta

Reglas:

* Cada rol se identifica por su **clave** (``RolMeta.clave``), no por el nombre: uno renombrado
  desde Roles sigue siendo el mismo y no se duplica.
* Un Group con el mismo nombre pero sin esa clave (o con otra) cuenta como existente y **no se adopta**:
  se avisa y no se escribe nada (adoptarlo le pisaría las capacidades).
* Si el rol ya existe, **no se toca nada** (ni capacidades, ni nombre, ni estado): lo que el PM
  editó a mano sobrevive. Se informa «ya existía».
* Los roles de programa se anclan al programa (categoría «Programa»). Si el programa
  (``DISPOSITIVOS`` / ``EMERGENCIA``) no existe en la base, ese rol se **saltea con aviso**, como
  hace ``seed_dispositivos``, y el resto sigue; el comando termina igual sin error.
* El Administrador del sistema se crea solo si falta, con los mismos datos que ``seed_rbac``
  (protegido, todas las capacidades). Si ya existe no se realinea: eso lo hace ``seed_rbac``.
* El alcance de cada persona sale del Equipo del programa, no del rol.

Las definiciones viven en ``programas/services/roles_sembrados.py``.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from core import rbac
from programas.models import Programa
from programas.services.roles_sembrados import ROLES_DISPOSITIVOS_EMERGENCIA
from users.models import Capacidad, RolMeta
from users.services.roles import DEFAULTS_ADMINISTRADOR, asegurar_rol_sembrado


def _permisos(codigos, ct, etiquetas):
    """Los ``Permission`` de ``codigos``, creándolos si falta alguno (idempotente)."""
    permisos = []
    for codigo in codigos:
        codename = rbac.codename_de(codigo)
        permiso, _ = Permission.objects.get_or_create(
            content_type=ct, codename=codename, defaults={"name": etiquetas.get(codename, codigo)}
        )
        permisos.append(permiso)
    return permisos


class _NoCreado(Exception):
    """``asegurar_rol_sembrado`` encontró un rol existente: se deshace lo que escribió."""


class Command(BaseCommand):
    help = (
        "Crea los roles de Dispositivos y Emergencia y el Administrador si faltan. "
        "No toca los que ya existen (por clave ni por nombre). --dry-run no escribe."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra qué haría, sin escribir nada.")

    def _sembrar(self, clave, nombre, defaults, codigos, dry):
        """Siembra un rol. Devuelve ``"existia"``, ``"ocupado"``, ``"por_crear"`` o ``"creado"``.

        «Ocupado» es un Group con ese nombre pero sin esa clave: no se adopta (adoptarlo le
        pisaría las capacidades). El nombre se compara **contra la base**, no en Python: MariaDB
        no distingue mayúsculas ni tildes y ``get_or_create`` lo encontraría igual. Como defensa,
        la escritura va en un savepoint: si ``asegurar_rol_sembrado`` termina adoptando un rol que
        ya estaba, se revierte lo que escribió (la clave o la ``RolMeta``).
        """
        if RolMeta.objects.filter(clave=clave).exists():
            return "existia"
        if Group.objects.filter(name=nombre).exists():
            return "ocupado"
        if dry:
            return "por_crear"
        try:
            with transaction.atomic():
                group, _meta, creado = asegurar_rol_sembrado(clave, nombre, defaults)
                if not creado:
                    raise _NoCreado
                group.permissions.set(_permisos(codigos, self._ct, self._etiquetas))
        except _NoCreado:
            return "ocupado"
        return "creado"

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options["dry_run"]
        self._etiquetas = dict(rbac.todas_las_capacidades())
        self._ct = ContentType.objects.get_for_model(Capacidad)
        codigos_validos = set(rbac.codigos_de_capacidad())
        programas = {p.codigo: p for p in Programa.objects.all()}
        creados = salteados = 0

        titulo = "=== Roles de Dispositivos y Emergencia" + (" (dry-run)" if dry else "") + " ===\n"
        self.stdout.write(self.style.MIGRATE_HEADING(titulo))

        pedidos = []
        for rol in ROLES_DISPOSITIVOS_EMERGENCIA:
            faltan = [c for c in rol.capacidades if c not in codigos_validos]
            if faltan:
                raise ValueError(f"{rol.clave}: capacidades fuera del catálogo: {faltan}")
            programa = programas.get(rol.programa)
            defaults = {
                "descripcion": rol.descripcion,
                "categoria": rbac.CATEGORIA_PROGRAMA,
                "protegido": False,
                "activo": True,
                "programa": programa,
            }
            pedidos.append((rol.clave, rol.nombre, defaults, rol.capacidades, programa is not None, rol.programa))
        pedidos.append(
            (
                rbac.CLAVE_ROL_ADMINISTRADOR,
                rbac.ROL_ADMINISTRADOR,
                DEFAULTS_ADMINISTRADOR,
                rbac.codigos_de_capacidad(),
                True,
                None,
            )
        )

        for clave, nombre, defaults, codigos, hay_programa, codigo_programa in pedidos:
            if not hay_programa and not RolMeta.objects.filter(clave=clave).exists():
                salteados += 1
                self.stdout.write(
                    self.style.WARNING(f"  ! {nombre}: el programa {codigo_programa} no existe en esta base, se saltea")
                )
                continue
            estado = self._sembrar(clave, nombre, defaults, codigos, dry)
            if estado == "existia":
                self.stdout.write(f"  · {nombre}: ya existía")
            elif estado == "ocupado":
                self.stdout.write(
                    self.style.WARNING(f"  ! {nombre}: ya existe un rol con ese nombre (sin esa clave): no se toca")
                )
            elif estado == "por_crear":
                self.stdout.write(f"  + {nombre}: se crearía con {len(codigos)} capacidades")
                creados += 1
            else:
                self.stdout.write(self.style.SUCCESS(f"  ✓ {nombre}: creado con {len(codigos)} capacidades"))
                creados += 1

        resumen = f"\n{creados} por crear" if dry else f"\n{creados} creados"
        if salteados:
            resumen += f", {salteados} salteados por falta de programa"
        self.stdout.write(resumen + ("; no se escribió nada." if dry else "."))
