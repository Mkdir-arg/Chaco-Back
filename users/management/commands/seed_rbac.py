"""
Seed idempotente del RBAC. Reemplaza a ``create_groups`` y ``setup_grupos``.

Hace, sin duplicar nada al repetirse:
1. Asegura las ``Permission`` del catálogo de capacidades (``core.rbac.CATALOGO``).
2. Crea/asegura ``RolMeta`` para cada ``Group`` existente (con su categoría).
3. Crea/asegura el rol protegido ``Administrador`` con **todas** las capacidades,
   y crea «Operador de backoffice» y «Comunicaciones» si faltan (si existen, no los toca).
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

#: Rol de Notificaciones (análisis 007) y lo que trae al crearse.
ROL_COMUNICACIONES = "Comunicaciones"
CAPS_COMUNICACIONES = ["notificacion.ver", "notificacion.gestionar", "notificacion.enviar"]


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
                grupo=group,
                defaults={
                    "categoria": categoria,
                    # El marcador de identidad del portal se protege para que no se
                    # edite/elimine/desactive desde el ABM de roles.
                    "protegido": group.name == rbac.GRUPO_CIUDADANO_PORTAL,
                },
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

        # 3b. Rol restringido "Operador de backoffice" (#59): menú acotado, sin
        # módulos operativos (Dashboard/Relevamientos/Conversaciones) ni alta de
        # ciudadanos. Se siembra **solo al crearlo** (Cambio 104): no es protegido, así
        # que la pantalla de Roles lo deja editar, desactivar y vaciar, y el arranque
        # no puede revertir eso (antes lo reactivaba con usuario/rol.administrar).
        self.stdout.write(self.style.MIGRATE_LABEL("\nRol Operador de backoffice..."))
        caps_operador = [
            "ciudadano.ver",
            # SEC-20 / D-20: la exportación del padrón es capacidad propia, sembrada a
            # quien tiene `ciudadano.ver` (el PM decidió el 08-oct-2026 que el Operador
            # la conserva). Mismo criterio que `users.0028` sobre las bases que ya
            # tienen roles; acá lo necesita la base nueva, donde la 0028 corre antes de
            # que este rol exista. Separada del ver, se le puede quitar desde el ABM.
            "ciudadano.exportar",
            "reporte.ver",
            "config.administrar",
            "usuario.administrar",
            "rol.administrar",
        ]
        op_group, op_creado = Group.objects.get_or_create(name="Operador de backoffice")
        RolMeta.objects.get_or_create(
            grupo=op_group,
            defaults={
                "descripcion": (
                    "Backoffice sin módulos operativos: sin Dashboard, Relevamientos, "
                    "Conversaciones ni alta de ciudadanos."
                ),
                "categoria": rbac.CATEGORIA_BACKOFFICE,
                "protegido": False,
                "activo": True,
            },
        )
        if op_creado:
            op_group.permissions.set([codename_a_perm[rbac.codename_de(c)] for c in caps_operador])
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Operador de backoffice creado con {len(caps_operador)} capacidades")
            )
        else:
            self.stdout.write("  · Operador de backoffice ya existe (no se tocan sus capacidades ni su estado)")

        # 3c. Rol «Comunicaciones» (análisis 007): las tres capacidades de Notificaciones.
        # Mismo criterio que el Operador: se siembra solo al crearlo, así lo que se cambie
        # desde la pantalla de Roles sobrevive al arranque. En una base que ya existía lo
        # crea `users.0030`, con el mismo nombre, la misma categoría y las mismas tres.
        self.stdout.write(self.style.MIGRATE_LABEL("\nRol Comunicaciones..."))
        com_group, com_creado = Group.objects.get_or_create(name=ROL_COMUNICACIONES)
        RolMeta.objects.get_or_create(
            grupo=com_group,
            defaults={
                "descripcion": (
                    "Arma, prueba y envía campañas de correo masivo desde Notificaciones: lista de "
                    "destinatarios en Excel y cuerpo en HTML."
                ),
                "categoria": rbac.CATEGORIA_BACKOFFICE,
                "protegido": False,
                "activo": True,
            },
        )
        if com_creado:
            com_group.permissions.set([codename_a_perm[rbac.codename_de(c)] for c in CAPS_COMUNICACIONES])
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Comunicaciones creado con {len(CAPS_COMUNICACIONES)} capacidades")
            )
        else:
            self.stdout.write("  · Comunicaciones ya existe (no se tocan sus capacidades ni su estado)")

        # 4. Asignar Administrador a los superusuarios (garantiza acceso post-deploy).
        superusers = User.objects.filter(is_superuser=True)
        for su in superusers:
            su.groups.add(admin_group)
        if superusers:
            self.stdout.write(self.style.SUCCESS(f"  ✓ Rol asignado a {superusers.count()} superusuario(s)"))
        else:
            self.stdout.write(
                self.style.WARNING(
                    "  ! No hay superusuarios: asigná el rol Administrador a un usuario "
                    "manualmente o creá un superusuario para no quedar sin acceso."
                )
            )

        self.stdout.write(self.style.SUCCESS("\nSeed RBAC completo."))
