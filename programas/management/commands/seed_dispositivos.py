"""Siembra los roles de programa de Dispositivos. Idempotente (apto bootstrap).

Hoy es uno: «Dispositivos — Agente de relevamiento» (clave ``dispositivos.agente_relevamiento``),
el rol que se le da a quien se da de alta desde el botón «Crear agente» del modal de asignar un
relevamiento edilicio. Lleva solo ``inspeccion.relevar``.

Reglas de siembra (Cambio 104, igual que ``seed_becas``):

* Se identifica por **clave** (``asegurar_rol_sembrado``): un rol renombrado desde el ABM sigue
  siendo el mismo y no se crea un duplicado.
* Nombre, descripción y estado activo son del ABM: solo se aplican al crear.
* A un rol que ya existe se le **asegura** la capacidad base pero no se le quita nada de lo que
  el PM haya tildado.
* Si el programa DISPOSITIVOS no existe en la base, no hace nada (no falla).
"""

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from core import rbac
from programas.models import Programa
from programas.services.inspecciones import CAP_RELEVAR, CLAVE_ROL_AGENTE, NOMBRE_ROL_AGENTE
from users.models import Capacidad
from users.services.roles import asegurar_rol_sembrado

DESCRIPCION_ROL_AGENTE = (
    "Releva edificios en campo: carga el resultado de los relevamientos edilicios que se le asignan."
)


def asegurar_roles_dispositivos():
    """Crea/asegura el rol de agente. Devuelve ``(group, creado)`` o ``None`` sin programa."""

    programa = Programa.objects.filter(codigo=rbac.CODIGO_PROGRAMA_DISPOSITIVOS).first()
    if programa is None:
        return None
    ct = ContentType.objects.get_for_model(Capacidad)
    etiquetas = dict(rbac.todas_las_capacidades())
    codename = rbac.codename_de(CAP_RELEVAR)
    permiso, _ = Permission.objects.get_or_create(
        content_type=ct, codename=codename, defaults={"name": etiquetas.get(codename, CAP_RELEVAR)}
    )
    group, meta, creado = asegurar_rol_sembrado(
        CLAVE_ROL_AGENTE,
        NOMBRE_ROL_AGENTE,
        {
            "descripcion": DESCRIPCION_ROL_AGENTE,
            "categoria": rbac.CATEGORIA_PROGRAMA,
            "protegido": False,
            "activo": True,
            "programa": programa,
        },
    )
    if meta.categoria != rbac.CATEGORIA_PROGRAMA or meta.programa_id != programa.pk:
        meta.categoria = rbac.CATEGORIA_PROGRAMA
        meta.programa = programa
        meta.save(update_fields=["categoria", "programa"])
    group.permissions.add(permiso)
    return group, creado


class Command(BaseCommand):
    help = "Siembra los roles de programa de Dispositivos (agente de relevamiento). Idempotente."

    @transaction.atomic
    def handle(self, *args, **options):
        resultado = asegurar_roles_dispositivos()
        if resultado is None:
            self.stdout.write("  · Programa DISPOSITIVOS inexistente: no se siembran roles.")
            return
        group, creado = resultado
        self.stdout.write(("  ✓ " if creado else "  · ") + group.name)
