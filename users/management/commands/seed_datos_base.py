"""
Seed idempotente de datos base del sistema. Pensado para correr en cada
arranque del contenedor (bootstrap del ``docker-entrypoint.sh``).

Hace, sin duplicar nada al repetirse:
1. Asegura los grupos **funcionales** que el código usa por nombre:
   ``Responsable`` (responsable de legajo) y ``Ciudadanos`` (marcador de
   identidad del portal). Siempre por **nombre** (``get_or_create``), nunca
   por pk.
2. Corre ``seed_rbac`` (capacidades, RolMeta, roles Administrador y Operador
   de backoffice) y ``seed_becas`` (Programa Becas + sus 5 roles de programa:
   Administrador / Coordinador / Coordinador Regional / Referente / Territorial
   + adjuntos obligatorios). Como ``seed_becas`` **sincroniza las capacidades
   base** de cada rol, correr esto en cada arranque es lo que mantiene los roles
   alineados con el código; un bootstrap que lo omita los deja congelados en el
   estado en que se sembró la base. Lo que la pantalla de Roles deja editar —nombre,
   descripción, activo y las capacidades opt-in como ``becas.relevamiento.publico``—
   sobrevive al arranque (Cambio 104).
3. Crea los **roles de menú** (uno por sección del sidebar) con sus
   capacidades y RolMeta. Solo al crearlos: si el rol ya existe no se le
   tocan las capacidades, para respetar lo editado desde el ABM de Roles.
   Se identifican por su ``RolMeta.clave`` (``asegurar_rol_sembrado``), así que
   renombrar uno desde el ABM no hace que el arranque siguiente cree un
   duplicado con el nombre canónico. La sección Becas no tiene rol de menú:
   sus roles son los de programa que crea ``seed_becas``.
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
from users.models import Capacidad
from users.services.roles import asegurar_rol_sembrado

# Grupos que el código referencia por nombre (sin capacidades propias).
_GRUPOS_FUNCIONALES = ["Responsable", rbac.GRUPO_CIUDADANO_PORTAL]

# Roles de menú: (clave estable, nombre, categoría, descripción, capacidades).
# Un rol por sección del sidebar; "Inicio" no necesita rol (lo ve cualquier
# usuario autenticado del backoffice).
#
# La **clave** es lo que identifica al rol (OPS-06 fase 2): el nombre lo deja
# renombrar el ABM, y sin clave el arranque siguiente creaba un segundo rol con el
# nombre canónico al lado del que la gente usa. Estos cinco se sumaron en la ronda 2
# del Cambio 193 —la fase 2 cubría solo los siete de `seed_rbac` y `seed_becas`— y su
# backfill es `users.0032`.
_ROLES_MENU = [
    (
        "menu.dashboard",
        "Dashboard",
        rbac.CATEGORIA_BACKOFFICE,
        "Acceso a la sección Dashboard.",
        ["dashboard.ver"],
    ),
    (
        "menu.ciudadanos",
        "Gestión de Ciudadanos",
        rbac.CATEGORIA_BACKOFFICE,
        "Acceso completo a la sección Ciudadanos (legajos).",
        # SEC-20 / D-20: `ciudadano.exportar` va con `ciudadano.ver`, igual que la
        # siembra de users.0028 sobre las bases que ya tienen roles. En una base nueva
        # la 0028 corre antes de que exista este rol, así que lo trae el seed.
        [
            "ciudadano.ver",
            "ciudadano.crear",
            "ciudadano.editar",
            "ciudadano.sensible",
            "ciudadano.exportar",
        ],
    ),
    (
        "menu.reportes",
        "Reportes",
        rbac.CATEGORIA_BACKOFFICE,
        "Acceso a la sección Reportes.",
        ["reporte.ver"],
    ),
    (
        "menu.configuracion",
        "Configuración",
        rbac.CATEGORIA_SISTEMA,
        "Acceso a la sección Configuración.",
        ["config.ver", "config.administrar"],
    ),
    (
        "menu.administracion",
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
        for clave, nombre, categoria, descripcion, capacidades in _ROLES_MENU:
            group, _meta, created = asegurar_rol_sembrado(
                clave,
                nombre,
                {"descripcion": descripcion, "categoria": categoria, "activo": True},
            )
            if created:
                perms = Permission.objects.filter(
                    content_type=ct, codename__in=[rbac.codename_de(c) for c in capacidades]
                )
                group.permissions.set(perms)
            self.stdout.write(("  ✓ " if created else "  · ") + f"{group.name} ({len(capacidades)} capacidades)")

        self.stdout.write(self.style.MIGRATE_LABEL("Catálogos base..."))
        for model_label, fixture in _CATALOGOS:
            model = apps.get_model(model_label)
            if model.objects.exists():
                self.stdout.write(f"  · {fixture} (ya hay datos, se omite)")
                continue
            call_command("loaddata", fixture, verbosity=0)
            self.stdout.write(self.style.SUCCESS(f"  ✓ {fixture} cargado"))

        self.stdout.write(self.style.SUCCESS("Seed de datos base completo."))
