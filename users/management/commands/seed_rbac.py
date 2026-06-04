"""
Seed idempotente del RBAC. Reemplaza a ``create_groups`` y ``setup_grupos``.

Hace, sin duplicar nada al repetirse:
1. Asegura las ``Permission`` del catálogo de capacidades (``core.rbac.CATALOGO``).
2. Crea/asegura ``RolMeta`` para cada ``Group`` existente (con su categoría).
3. Crea/asegura el rol protegido ``Administrador`` con **todas** las capacidades.
4. Asigna el rol ``Administrador`` a los superusuarios (acceso garantizado).

Ejecutar tras cada ``migrate``::

    python manage.py seed_rbac
"""
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from core import rbac
from users.models import Capacidad, RolMeta

# Categoría inicial sugerida para los grupos legacy conocidos (cosmético).
_CATEGORIA_POR_GRUPO = {
    rbac.GRUPO_CIUDADANO_PORTAL: rbac.CATEGORIA_PORTAL,
    "EncargadoInstitucion": rbac.CATEGORIA_INSTITUCION,
    "AdministrativoInstitucion": rbac.CATEGORIA_INSTITUCION,
    "ProfesorInstitucion": rbac.CATEGORIA_INSTITUCION,
    rbac.ROL_ADMINISTRADOR: rbac.CATEGORIA_SISTEMA,
}


class Command(BaseCommand):
    help = "Siembra el RBAC (capacidades, RolMeta y rol Administrador). Idempotente."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seed RBAC ===\n"))

        ct = ContentType.objects.get_for_model(Capacidad)

        # 1. Capacidades (Permission). migrate ya las crea; idempotente por las dudas.
        self.stdout.write(self.style.MIGRATE_LABEL("Capacidades..."))
        codename_a_perm = {}
        for codename, etiqueta in rbac.todas_las_capacidades():
            perm, created = Permission.objects.get_or_create(
                codename=codename, content_type=ct, defaults={"name": etiqueta}
            )
            if perm.name != etiqueta:
                perm.name = etiqueta
                perm.save(update_fields=["name"])
            codename_a_perm[codename] = perm
            self.stdout.write(("  ✓ " if created else "  · ") + codename)

        # 2. RolMeta para cada grupo existente.
        self.stdout.write(self.style.MIGRATE_LABEL("\nRolMeta de grupos existentes..."))
        for group in Group.objects.all():
            categoria = _CATEGORIA_POR_GRUPO.get(group.name, rbac.CATEGORIA_BACKOFFICE)
            _, created = RolMeta.objects.get_or_create(
                grupo=group, defaults={"categoria": categoria}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  ✓ RolMeta creada: {group.name}"))

        # 3. Rol Administrador protegido con todas las capacidades.
        self.stdout.write(self.style.MIGRATE_LABEL("\nRol Administrador..."))
        admin_group, _ = Group.objects.get_or_create(name=rbac.ROL_ADMINISTRADOR)
        RolMeta.objects.update_or_create(
            grupo=admin_group,
            defaults={
                "descripcion": "Acceso total al backoffice. Rol protegido del sistema.",
                "categoria": rbac.CATEGORIA_SISTEMA,
                "protegido": True,
                "activo": True,
            },
        )
        admin_group.permissions.set(list(codename_a_perm.values()))
        self.stdout.write(self.style.SUCCESS("  ✓ Administrador con todas las capacidades"))

        # 4. Asignar Administrador a los superusuarios (garantiza acceso post-deploy).
        superusers = User.objects.filter(is_superuser=True)
        for su in superusers:
            su.groups.add(admin_group)
        if superusers:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Rol asignado a {superusers.count()} superusuario(s)"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "  ! No hay superusuarios: asigná el rol Administrador a un usuario "
                    "manualmente o creá un superusuario para no quedar sin acceso."
                )
            )

        self.stdout.write(self.style.SUCCESS("\nSeed RBAC completo."))
