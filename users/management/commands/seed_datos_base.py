"""
Seed idempotente de datos base del sistema. Pensado para correr en cada
arranque del contenedor (bootstrap del ``docker-entrypoint.sh``).

Hace, sin duplicar nada al repetirse:
1. Asegura los grupos **funcionales** que el código usa por nombre:
   ``Responsable`` (responsable de legajo) y ``Ciudadanos`` (marcador de
   identidad del portal). Siempre por **nombre** (``get_or_create``), nunca
   por pk.
2. Corre ``seed_rbac`` (capacidades, RolMeta, roles Administrador y Operador
   de backoffice) y ``seed_becas`` (Programa Becas + sus 3 roles de programa:
   Administrador / Coordinador / Territorial + adjuntos obligatorios).
3. Crea los **roles de menú** (uno por sección del sidebar) con sus
   capacidades y RolMeta. Solo al crearlos: si el rol ya existe no se le
   tocan las capacidades, para respetar lo editado desde el ABM de Roles.
   La sección Becas no tiene rol de menú: sus roles son los de programa
   que crea ``seed_becas``.
4. Carga los catálogos base (sexo, día, mes, localidades) solo si la tabla
   correspondiente está vacía.

Ejecutar manualmente::

    python manage.py seed_datos_base
"""

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand

from core import rbac
from users.models import Capacidad, RolMeta

# Grupos que el código referencia por nombre (sin capacidades propias).
_GRUPOS_FUNCIONALES = ["Responsable", rbac.GRUPO_CIUDADANO_PORTAL]

# Roles de menú: (nombre, categoría, descripción, capacidades).
# Un rol por sección del sidebar; "Inicio" no necesita rol (lo ve cualquier
# usuario autenticado del backoffice).
_ROLES_MENU = [
    (
        "Dashboard",
        rbac.CATEGORIA_BACKOFFICE,
        "Acceso a la sección Dashboard.",
        ["dashboard.ver"],
    ),
    (
        "Gestión de Ciudadanos",
        rbac.CATEGORIA_BACKOFFICE,
        "Acceso completo a la sección Ciudadanos (legajos).",
        ["ciudadano.ver", "ciudadano.crear", "ciudadano.editar", "ciudadano.eliminar", "ciudadano.sensible"],
    ),
    (
        "Reportes",
        rbac.CATEGORIA_BACKOFFICE,
        "Acceso a la sección Reportes.",
        ["reporte.ver"],
    ),
    (
        "Configuración",
        rbac.CATEGORIA_SISTEMA,
        "Acceso a la sección Configuración.",
        ["config.ver", "config.administrar"],
    ),
    (
        "Administración",
        rbac.CATEGORIA_SISTEMA,
        "Acceso a la sección Administración (usuarios y roles).",
        ["usuario.administrar", "rol.administrar"],
    ),
]

# Catálogos: se cargan con loaddata solo si el modelo guía está vacío.
# (modelo, fixture)
_CATALOGOS = [
    ("core.Sexo", "sexo"),
    ("core.Dia", "dia"),
    ("core.Mes", "mes"),
    ("core.Localidad", "localidad_municipio_provincia"),
]


class Command(BaseCommand):
    help = "Siembra grupos funcionales, RBAC, roles de menú y catálogos base. Idempotente (apto bootstrap)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seed de datos base ==="))

        self.stdout.write(self.style.MIGRATE_LABEL("Grupos funcionales..."))
        for nombre in _GRUPOS_FUNCIONALES:
            _, created = Group.objects.get_or_create(name=nombre)
            self.stdout.write(("  ✓ " if created else "  · ") + nombre)

        self.stdout.write(self.style.MIGRATE_LABEL("RBAC..."))
        call_command("seed_rbac")

        self.stdout.write(self.style.MIGRATE_LABEL("Programa Becas..."))
        call_command("seed_becas")

        self.stdout.write(self.style.MIGRATE_LABEL("Roles de menú..."))
        ct = ContentType.objects.get_for_model(Capacidad)
        for nombre, categoria, descripcion, capacidades in _ROLES_MENU:
            group, created = Group.objects.get_or_create(name=nombre)
            if created:
                perms = Permission.objects.filter(
                    content_type=ct, codename__in=[rbac.codename_de(c) for c in capacidades]
                )
                group.permissions.set(perms)
            RolMeta.objects.get_or_create(
                grupo=group,
                defaults={"descripcion": descripcion, "categoria": categoria, "activo": True},
            )
            self.stdout.write(("  ✓ " if created else "  · ") + f"{nombre} ({len(capacidades)} capacidades)")

        self.stdout.write(self.style.MIGRATE_LABEL("Catálogos base..."))
        for model_label, fixture in _CATALOGOS:
            model = apps.get_model(model_label)
            if model.objects.exists():
                self.stdout.write(f"  · {fixture} (ya hay datos, se omite)")
                continue
            call_command("loaddata", fixture, verbosity=0)
            self.stdout.write(self.style.SUCCESS(f"  ✓ {fixture} cargado"))

        self.stdout.write(self.style.SUCCESS("Seed de datos base completo."))
