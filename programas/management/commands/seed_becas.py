"""Seed idempotente del Programa Becas.

Crea/asegura, sin duplicar al repetirse:
1. La instancia genérica ``Programa(codigo="BECAS")`` que ancla el alcance del
   RBAC (roles de categoría "Programa") y la futura solapa del legajo.
2. Los adjuntos obligatorios fijos del formulario, modelados como
   ``PreguntaGlobal`` tipo ARCHIVO (#73 / §7.1 del análisis).
3. Los tres roles del programa (Admin / Coordinador / Territorial) integrados al
   RBAC (Group + RolMeta categoría "Programa", acotados al Programa Becas), con
   sus capacidades (#79).

Ejecutar tras ``migrate`` (las capacidades ``becas.*`` se materializan ahí)::

    python manage.py seed_becas
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from core import rbac
from programas.models import PreguntaGlobal, Programa, TipoCampo
from users.models import Capacidad, RolMeta

PROGRAMA_BECAS_CODIGO = "BECAS"

# Roles del programa Becas. Nombre legible del Group → capacidades (códigos del
# catálogo, todas de alcance "programa"). El scoping fino por segmento del
# Coordinador lo aporta AsignacionCoordinador (ver services/autorizacion.py).
ROL_ADMIN = "Becas — Administrador"
ROL_COORDINADOR = "Becas — Coordinador"
ROL_TERRITORIAL = "Becas — Territorial"

def _capacidades_admin_becas():
    """Todas las capacidades finas de Becas salvo ``becas.campo`` (el Admin no
    opera la app de territorial, es un rol de backoffice)."""
    return [c for c in rbac.codigos_de_capacidad() if c.startswith("becas.") and c != "becas.campo"]


ROLES_BECAS = {
    ROL_ADMIN: {
        "descripcion": "Acceso total al programa Becas: configuración, relevamientos y revisión.",
        "capacidades": _capacidades_admin_becas(),
    },
    ROL_COORDINADOR: {
        "descripcion": "Gestiona relevamientos y revisa formularios solo de sus segmentos asignados.",
        "capacidades": [
            "becas.segmento.ver",
            "becas.subsegmento.ver",
            "becas.requisito.ver",
            "becas.convocatoria.ver",
            "becas.convocatoria.crear",
            "becas.convocatoria.editar",
            "becas.relevamiento.ver",
            "becas.relevamiento.crear",
            "becas.relevamiento.editar",
            "becas.revision.ver",
            "becas.revision.editar",
            "becas.cupo.ver",
            "becas.beneficiario.ver",
            "becas.beneficiario.editar",
        ],
    },
    ROL_TERRITORIAL: {
        "descripcion": "Opera la app de campo (sus relevamientos). Sin acceso al backoffice.",
        "capacidades": ["becas.campo"],
    },
}

# Adjuntos obligatorios fijos (no configurables). El CUIL lo autocompleta RENAPER
# y el CBU es opcional, por eso no se precargan acá.
ADJUNTOS_OBLIGATORIOS = [
    ("Foto DNI - Frente", 101),
    ("Foto DNI - Dorso", 102),
    ("Certificado de domicilio", 103),
    ("Constancia de estudios", 104),
    ("Convenio de confidencialidad / uso de imagen", 105),
]


def asegurar_programa_becas():
    """Devuelve la instancia genérica del Programa Becas (la crea si falta)."""
    programa, _ = Programa.objects.get_or_create(
        codigo=PROGRAMA_BECAS_CODIGO,
        defaults={
            "nombre": "Becas",
            "tipo": "BECAS",
            "descripcion": "Programa de Becas: relevamiento territorial y asignación de cupos.",
            "naturaleza": Programa.Naturaleza.PERSISTENTE,
            "estado": Programa.Estado.ACTIVO,
            "icono": "school",
            "color": "#0ea5e9",
        },
    )
    return programa


def asegurar_adjuntos_obligatorios():
    """Crea las PreguntaGlobal tipo ARCHIVO obligatorias fijas (idempotente)."""
    creados = 0
    for texto, orden in ADJUNTOS_OBLIGATORIOS:
        _, created = PreguntaGlobal.objects.get_or_create(
            texto=texto,
            defaults={
                "tipo": TipoCampo.ARCHIVO,
                "opciones": None,
                "activo": True,
                "obligatorio": True,
                "orden": orden,
            },
        )
        creados += int(created)
    return creados


def asegurar_roles_becas(programa):
    """Crea/asegura los 3 roles del programa con sus capacidades (idempotente).

    Requiere que las ``Permission`` de las capacidades ``becas.*`` existan (las
    materializa ``migrate`` desde ``Capacidad.Meta.permissions``); por las dudas
    se aseguran con get_or_create, igual que en ``seed_rbac``.
    """
    ct = ContentType.objects.get_for_model(Capacidad)
    etiquetas = dict(rbac.todas_las_capacidades())  # codename -> etiqueta

    def _perm(codigo):
        codename = rbac.codename_de(codigo)
        perm, _ = Permission.objects.get_or_create(
            content_type=ct, codename=codename, defaults={"name": etiquetas.get(codename, codigo)}
        )
        return perm

    for nombre, cfg in ROLES_BECAS.items():
        group, _ = Group.objects.get_or_create(name=nombre)
        RolMeta.objects.update_or_create(
            grupo=group,
            defaults={
                "descripcion": cfg["descripcion"],
                "categoria": rbac.CATEGORIA_PROGRAMA,
                "protegido": False,
                "activo": True,
                "programa": programa,
            },
        )
        group.permissions.set([_perm(c) for c in cfg["capacidades"]])


class Command(BaseCommand):
    help = "Siembra el Programa Becas (programa genérico + adjuntos + roles RBAC). Idempotente."

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seed Becas ===\n"))

        programa = asegurar_programa_becas()
        self.stdout.write(self.style.SUCCESS(f"  ✓ Programa: {programa.nombre} ({programa.codigo})"))

        creados = asegurar_adjuntos_obligatorios()
        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Adjuntos obligatorios asegurados ({creados} nuevos, {len(ADJUNTOS_OBLIGATORIOS)} totales)"
            )
        )

        asegurar_roles_becas(programa)
        self.stdout.write(self.style.SUCCESS(f"  ✓ Roles RBAC asegurados: {', '.join(ROLES_BECAS)}"))

        self.stdout.write(self.style.SUCCESS("\nSeed Becas completo."))
