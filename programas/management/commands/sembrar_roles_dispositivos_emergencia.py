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


class Command(BaseCommand):
    help = (
        "Crea los roles de Dispositivos y Emergencia y el Administrador si faltan. "
        "No toca los que ya existen (por clave ni por nombre). --dry-run no escribe."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra qué haría, sin escribir nada.")

    def _nombre_ocupado(self, nombre):
        self.stdout.write(
            self.style.WARNING(f"  ! {nombre}: ya existe un rol con ese nombre (sin esa clave): no se toca")
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options["dry_run"]
        etiquetas = dict(rbac.todas_las_capacidades())
        codigos_validos = set(rbac.codigos_de_capacidad())
        ct = ContentType.objects.get_for_model(Capacidad)
        programas = {p.codigo: p for p in Programa.objects.all()}
        existentes = set(RolMeta.objects.exclude(clave__isnull=True).values_list("clave", flat=True))
        nombres = set(Group.objects.values_list("name", flat=True))
        creados = salteados = 0

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "=== Roles de Dispositivos y Emergencia" + (" (dry-run)" if dry else "") + " ===\n"
            )
        )

        for rol in ROLES_DISPOSITIVOS_EMERGENCIA:
            if rol.clave in existentes:
                self.stdout.write(f"  · {rol.nombre}: ya existía")
                continue
            if rol.nombre in nombres:
                self._nombre_ocupado(rol.nombre)
                continue
            programa = programas.get(rol.programa)
            if programa is None:
                salteados += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  ! {rol.nombre}: el programa {rol.programa} no existe en esta base, se saltea"
                    )
                )
                continue
            faltan = [c for c in rol.capacidades if c not in codigos_validos]
            if faltan:
                raise ValueError(f"{rol.clave}: capacidades fuera del catálogo: {faltan}")
            if dry:
                self.stdout.write(f"  + {rol.nombre}: se crearía con {len(rol.capacidades)} capacidades")
                creados += 1
                continue
            group, _meta, creado = asegurar_rol_sembrado(
                rol.clave,
                rol.nombre,
                {
                    "descripcion": rol.descripcion,
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "protegido": False,
                    "activo": True,
                    "programa": programa,
                },
            )
            if not creado:  # carrera: apareció entre la lectura y la escritura
                self._nombre_ocupado(rol.nombre)
                continue
            group.permissions.set(_permisos(rol.capacidades, ct, etiquetas))
            self.stdout.write(self.style.SUCCESS(f"  ✓ {rol.nombre}: creado con {len(rol.capacidades)} capacidades"))
            creados += 1

        if rbac.CLAVE_ROL_ADMINISTRADOR in existentes:
            self.stdout.write(f"  · {rbac.ROL_ADMINISTRADOR}: ya existía")
        elif rbac.ROL_ADMINISTRADOR in nombres:
            self._nombre_ocupado(rbac.ROL_ADMINISTRADOR)
        elif dry:
            self.stdout.write(f"  + {rbac.ROL_ADMINISTRADOR}: se crearía con todas las capacidades")
            creados += 1
        else:
            group, _meta, creado = asegurar_rol_sembrado(
                rbac.CLAVE_ROL_ADMINISTRADOR, rbac.ROL_ADMINISTRADOR, DEFAULTS_ADMINISTRADOR
            )
            if creado:
                group.permissions.set(_permisos(rbac.codigos_de_capacidad(), ct, etiquetas))
                self.stdout.write(self.style.SUCCESS(f"  ✓ {rbac.ROL_ADMINISTRADOR}: creado con todas las capacidades"))
                creados += 1
            else:
                self._nombre_ocupado(rbac.ROL_ADMINISTRADOR)

        resumen = f"\n{creados} por crear" if dry else f"\n{creados} creados"
        if salteados:
            resumen += f", {salteados} salteados por falta de programa"
        self.stdout.write(resumen + ("; no se escribió nada." if dry else "."))
