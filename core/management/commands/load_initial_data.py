"""
Carga todos los datos iniciales del sistema para una instalación fresca.

Uso:
    python manage.py load_initial_data

Ejecutar una sola vez al levantar el entorno por primera vez.
Para (re)sembrar el RBAC en instalaciones existentes, usar:
    python manage.py seed_rbac
"""

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from core import rbac
from users.models import RolMeta
from users.services.roles import _set_capacidades

# Roles demo con sus capacidades (alimentan una instalación de prueba funcional).
ROLES_DEMO = {
    "Operador de legajos": (
        rbac.CATEGORIA_BACKOFFICE,
        "Ve y gestiona ciudadanos, legajos y conversaciones.",
        ["ciudadano.ver", "ciudadano.crear", "ciudadano.editar", "dashboard.ver", "reporte.ver", "conversacion.operar"],
    ),
    "Configurador de programas": (
        rbac.CATEGORIA_BACKOFFICE,
        "Configura programas y la estructura organizacional.",
        ["programa.ver", "programa.operar", "programa.configurar", "config.ver", "config.administrar"],
    ),
    "Profesional": (
        rbac.CATEGORIA_BACKOFFICE,
        "Profesional con acceso a datos sensibles de sus legajos.",
        ["ciudadano.ver", "ciudadano.sensible", "relevamiento.ver"],
    ),
    "Encargado de institución": (
        rbac.CATEGORIA_INSTITUCION,
        "Gestiona su institución.",
        ["institucion.ver", "institucion.administrar"],
    ),
}

USUARIOS_DEMO = [
    # (username, first, last, password, roles, is_staff)
    ("admin", "Admin", "Sistema", "admin123", [rbac.ROL_ADMINISTRADOR], True),
    ("operador1", "Laura", "Fernández", "demo123", ["Operador de legajos"], True),
    ("configurador1", "Martín", "García", "demo123", ["Configurador de programas"], True),
    ("profesional1", "Ana", "Martínez", "demo123", ["Profesional"], True),
    ("encargado1", "Diego", "López", "demo123", ["Encargado de institución"], False),
    ("ciudadano1", "Juan", "Pérez", "demo123", [rbac.GRUPO_CIUDADANO_PORTAL], False),
]


class Command(BaseCommand):
    help = "Carga datos iniciales para instalación fresca. Solo ejecutar una vez."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Cargando datos iniciales SistemSo ===\n"))

        # 1. Fixtures de datos de referencia
        self.stdout.write(self.style.MIGRATE_LABEL("Cargando fixtures de referencia..."))
        fixtures = [
            "core/fixtures/dia.json",
            "core/fixtures/mes.json",
            "core/fixtures/sexo.json",
            "core/fixtures/localidad_municipio_provincia.json",
            "legajos/fixtures/contactos_initial_data.json",
        ]
        for fixture in fixtures:
            try:
                call_command("loaddata", fixture, verbosity=0)
                self.stdout.write(self.style.SUCCESS(f"  ✓ {fixture}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  ⚠ {fixture}: {e}"))

        self.stdout.write("")

        # 2. RBAC: capacidades + rol Administrador protegido
        self.stdout.write(self.style.MIGRATE_LABEL("Sembrando RBAC..."))
        call_command("seed_rbac", verbosity=0)

        # 3. Roles demo con capacidades
        self.stdout.write(self.style.MIGRATE_LABEL("Creando roles demo..."))
        for nombre, (categoria, descripcion, caps) in ROLES_DEMO.items():
            grupo, _ = Group.objects.get_or_create(name=nombre)
            RolMeta.objects.update_or_create(
                grupo=grupo,
                defaults={"categoria": categoria, "descripcion": descripcion, "activo": True},
            )
            _set_capacidades(grupo, caps)
            self.stdout.write(self.style.SUCCESS(f"  ✓ Rol: {nombre}"))

        # Marcador de identidad del portal (sin capacidades de backoffice)
        ciudadanos, _ = Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)
        RolMeta.objects.get_or_create(
            grupo=ciudadanos,
            defaults={
                "categoria": rbac.CATEGORIA_PORTAL,
                "descripcion": "Ciudadanos del portal.",
                "protegido": True,
            },
        )

        self.stdout.write("")

        # 4. Superusuario
        self.stdout.write(self.style.MIGRATE_LABEL("Creando usuarios demo..."))
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser("superadmin", "superadmin@sistema.gov.ar", "admin123")
            self.stdout.write(self.style.SUCCESS("  ✓ Superusuario: superadmin / admin123"))

        # 5. Usuarios demo con sus roles
        for username, first, last, pwd, roles, is_staff in USUARIOS_DEMO:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@sistema.gov.ar",
                    password=pwd,
                    first_name=first,
                    last_name=last,
                    is_staff=is_staff,
                )
                for rol_nombre in roles:
                    try:
                        user.groups.add(Group.objects.get(name=rol_nombre))
                    except Group.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"  ⚠ Rol no encontrado: {rol_nombre}"))
                self.stdout.write(self.style.SUCCESS(f"  ✓ {username} ({', '.join(roles) or 'superadmin'})"))

        # 6. Legajo (Ciudadano) demo vinculado a ciudadano1, para probar el portal
        from legajos.models import Ciudadano

        ciudadano_user = User.objects.filter(username="ciudadano1").first()
        if ciudadano_user and not Ciudadano.objects.filter(usuario=ciudadano_user).exists():
            Ciudadano.objects.create(
                usuario=ciudadano_user, dni="30111222", nombre="Juan", apellido="Perez",
                genero="Masculino", telefono="3700000000", email="ciudadano1@demo.local",
                domicilio="Calle Falsa 123", tipo_vivienda="Casa", tenencia_vivienda="Propia",
                condiciones_vivienda="Buenas", situacion_laboral="Empleado", ingreso_estimado="Medio",
                obra_social="Ninguna", nivel_educativo="Secundario", cobertura_medica="Publica",
                medicacion_habitual="Ninguna", dni_fisico="Si", estado_renaper="No verificado",
                estado_migratorio="Nacional", observaciones="Ciudadano demo",
            )
            self.stdout.write(self.style.SUCCESS("  ✓ Legajo demo para ciudadano1 (portal)"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Setup completo ==="))
        self.stdout.write("")
        self.stdout.write("Usuarios disponibles:")
        self.stdout.write("  superadmin / admin123  → acceso total (bypass)")
        self.stdout.write("  admin / admin123       → rol Administrador")
        self.stdout.write("  operador1 / demo123    → operador de legajos")
        self.stdout.write("  configurador1 / demo123 → configurador de programas")
        self.stdout.write("  profesional1 / demo123 → profesional")
        self.stdout.write("  encargado1 / demo123   → encargado institución")
        self.stdout.write("  ciudadano1 / demo123   → portal ciudadano")
