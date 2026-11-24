"""Crea los roles de Dispositivos y Emergencia (y el Administrador del sistema si falta).

Lo corre el PM a mano en el pod, porque ECOM no ejecuta el bootstrap::

    python manage.py sembrar_roles_dispositivos_emergencia --dry-run   # muestra, no escribe
    python manage.py sembrar_roles_dispositivos_emergencia             # crea lo que falta

Reglas:

* Cada rol se identifica por su **clave** (``RolMeta.clave``), no por el nombre: uno renombrado
  desde Roles sigue siendo el mismo y no se duplica.
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

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from core import rbac
from programas.models import Programa
from programas.services.roles_sembrados import ROLES_DISPOSITIVOS_EMERGENCIA
from users.management.commands.seed_rbac import CLAVE_ADMINISTRADOR, DEFAULTS_ADMINISTRADOR
from users.models import Capacidad, RolMeta
from users.services.roles import asegurar_rol_sembrado


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
        "No toca los que ya existen. --dry-run no escribe."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra qué haría, sin escribir nada.")

    @transaction.atomic
    def handle(self, *args, **options):
        dry = options["dry_run"]
        etiquetas = dict(rbac.todas_las_capacidades())
        codigos_validos = set(rbac.codigos_de_capacidad())
        ct = ContentType.objects.get_for_model(Capacidad)
        programas = {p.codigo: p for p in Programa.objects.all()}
        existentes = set(RolMeta.objects.exclude(clave__isnull=True).values_list("clave", flat=True))
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
            group, meta, _creado = asegurar_rol_sembrado(
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
            group.permissions.set(_permisos(rol.capacidades, ct, etiquetas))
            self.stdout.write(self.style.SUCCESS(f"  ✓ {rol.nombre}: creado con {len(rol.capacidades)} capacidades"))
            creados += 1

        if CLAVE_ADMINISTRADOR in existentes:
            self.stdout.write(f"  · {rbac.ROL_ADMINISTRADOR}: ya existía")
        elif dry:
            self.stdout.write(f"  + {rbac.ROL_ADMINISTRADOR}: se crearía con todas las capacidades")
            creados += 1
        else:
            group, _meta, _ = asegurar_rol_sembrado(CLAVE_ADMINISTRADOR, rbac.ROL_ADMINISTRADOR, DEFAULTS_ADMINISTRADOR)
            group.permissions.set(_permisos(rbac.codigos_de_capacidad(), ct, etiquetas))
            self.stdout.write(self.style.SUCCESS(f"  ✓ {rbac.ROL_ADMINISTRADOR}: creado con todas las capacidades"))
            creados += 1

        resumen = f"\n{creados} por crear" if dry else f"\n{creados} creados"
        if salteados:
            resumen += f", {salteados} salteados por falta de programa"
        self.stdout.write(resumen + ("; no se escribió nada." if dry else "."))
