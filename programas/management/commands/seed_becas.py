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
from programas.models import (
    VINCULOS_LEGAJO,
    CanalFormulario,
    GrupoRequisito,
    OrigenRequisito,
    PreguntaGlobal,
    Programa,
    TipoCampo,
)
from users.models import Capacidad, RolMeta

PROGRAMA_BECAS_CODIGO = "BECAS"

# Roles del programa Becas. Nombre legible del Group → capacidades (códigos del
# catálogo, todas de alcance "programa"). El scoping fino por segmento del
# Coordinador lo aporta AsignacionCoordinador (ver services/autorizacion.py).
ROL_ADMIN = "Becas — Administrador"
ROL_COORDINADOR = "Becas — Coordinador"
ROL_COORDINADOR_REGIONAL = "Becas — Coordinador Regional"
ROL_REFERENTE = "Becas — Referente"
ROL_TERRITORIAL = "Becas — Territorial"


def _capacidades_admin_becas():
    """Capacidades del Administrador: todas las finas de Becas salvo ``becas.campo``
    (no opera la app del territorial, es un rol de backoffice), más el alcance
    transversal sobre los ABM de Usuarios y Roles del programa.

    Las transversales van explícitas porque ``becas.programa.administrar`` ya no las
    confiere (ver ``rbac.CAPS_ADMIN_PROGRAMA_*``). Sin ellas el Administrador no vería
    los usuarios ni los roles de Becas, y como ``asegurar_roles_becas`` usa
    ``permissions.set()``, una corrida del seed revertiría el traspaso de ``users.0020``.
    """
    # becas.relevamiento.publico se excluye a propósito (RN-P13, análisis #289):
    # el lanzamiento del formulario público está gateado y la capacidad se
    # asigna manualmente desde la pantalla de Roles, nunca por seed.
    excluidas = ("becas.campo", "becas.relevamiento.publico")
    finas = [c for c in rbac.codigos_de_capacidad() if c.startswith("becas.") and c not in excluidas]
    return finas + list(rbac.CAPS_ADMIN_PROGRAMA)


ROLES_BECAS = {
    ROL_ADMIN: {
        "descripcion": "Acceso total al programa Becas: configuración, relevamientos y revisión.",
        "capacidades": _capacidades_admin_becas(),
    },
    ROL_COORDINADOR: {
        "descripcion": "Gestiona relevamientos y revisa formularios solo de sus segmentos asignados.",
        "capacidades": [
            "becas.usuario.territorial",
            "becas.segmento.ver",
            "becas.subsegmento.ver",
            "becas.requisito.ver",
            "becas.requisito.crear",
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
            "becas.reportes.ver",
            "becas.reportes.exportar",
        ],
    },
    ROL_COORDINADOR_REGIONAL: {
        "descripcion": (
            "Opera únicamente los subsegmentos que tiene a cargo: convocatorias, relevamientos y "
            "territoriales. Ve el segmento como contexto, pero no lo configura."
        ),
        "capacidades": [
            "becas.coordinador_regional",
            "becas.usuario.territorial",
            "becas.segmento.ver",
            "becas.subsegmento.ver",
            "becas.convocatoria.ver",
            "becas.convocatoria.crear",
            "becas.convocatoria.editar",
            "becas.relevamiento.ver",
            "becas.relevamiento.crear",
            "becas.relevamiento.editar",
            "becas.cupo.ver",
            "becas.reportes.ver",
            "becas.reportes.exportar",
        ],
    },
    ROL_REFERENTE: {
        "descripcion": "Asiste a un Coordinador y administra Territoriales de sus segmentos, sin pausar ni crear roles.",
        "capacidades": [
            "becas.referente",
            "becas.usuario.territorial",
            "becas.segmento.ver",
            "becas.subsegmento.ver",
            "becas.convocatoria.ver",
            "becas.relevamiento.ver",
            "becas.revision.ver",
            "becas.cupo.ver",
            "becas.reportes.ver",
            "becas.reportes.exportar",
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
    # Evita conservar una instancia con PK obsoleta entre recreaciones de la
    # base de test o ejecuciones idempotentes del seed.
    from django.core.cache import cache

    cache.delete("programas:becas")
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


# Catálogo protegido (Cambio 58, D5): los bloques que antes eran fijos en el
# código pasan a ser requisitos generales agrupados y vinculados al legajo.
# Cada grupo: (clave, nombre, subtítulo, orden, condición por defecto, campos);
# cada campo: (origen, vínculo, etiqueta, obligatorio). El tipo y las opciones
# salen de VINCULOS_LEGAJO, nunca de acá.
CONDICION_APODERADO = {
    "modo": "todas",
    "reglas": [{"fuente": "legajo:fecha_nacimiento", "op": "edad_menor", "valor": 18}],
}
CATALOGO_PROTEGIDO = [
    (
        "datos_personales",
        "Datos personales",
        "Los datos de la persona que se inscribe.",
        0,
        None,
        [
            (OrigenRequisito.LEGAJO, "nombre", "Nombre", True),
            (OrigenRequisito.LEGAJO, "apellido", "Apellido", True),
            (OrigenRequisito.LEGAJO, "dni", "DNI", True),
            (OrigenRequisito.LEGAJO, "fecha_nacimiento", "Fecha de nacimiento", True),
            (OrigenRequisito.LEGAJO, "genero", "Sexo", True),
        ],
    ),
    (
        "contacto",
        "Contacto",
        "",
        1,
        None,
        [
            (OrigenRequisito.LEGAJO, "telefono", "Celular", True),
            (OrigenRequisito.LEGAJO, "email", "Correo electrónico", False),
        ],
    ),
    (
        "apoderado",
        "Apoderado",
        "Como sos menor de 18, necesitamos los datos de un adulto responsable.",
        2,
        CONDICION_APODERADO,
        [
            (OrigenRequisito.PERSONA_VINCULADA, "nombre", "Nombre del apoderado", True),
            (OrigenRequisito.PERSONA_VINCULADA, "apellido", "Apellido del apoderado", True),
            (OrigenRequisito.PERSONA_VINCULADA, "dni", "DNI del apoderado", True),
            (OrigenRequisito.PERSONA_VINCULADA, "genero", "Sexo del apoderado", False),
            (OrigenRequisito.PERSONA_VINCULADA, "fecha_nacimiento", "Fecha de nacimiento del apoderado", False),
        ],
    ),
]
GRUPO_CUESTIONARIO = ("cuestionario", "Cuestionario social", "", 10)


def asegurar_catalogo_protegido():
    """Siembra los grupos protegidos con sus campos vinculados y manda al
    «Cuestionario social» toda pregunta que no tenga grupo. Idempotente: la
    identidad de un campo protegido es (origen, vínculo); el texto, el grupo y
    el orden se pueden haber cambiado desde el backoffice y no se pisan."""
    creados = 0
    ordenes_usados = set(PreguntaGlobal.objects.values_list("orden", flat=True))

    def orden_libre(desde):
        while desde in ordenes_usados:
            desde += 1
        ordenes_usados.add(desde)
        return desde

    for clave, nombre, subtitulo, orden, condicion, campos in CATALOGO_PROTEGIDO:
        grupo, _ = GrupoRequisito.objects.get_or_create(
            clave=clave,
            defaults={
                "nombre": nombre,
                "subtitulo": subtitulo,
                "orden": orden,
                "protegido": True,
                "condicion_defecto": condicion,
            },
        )
        if not grupo.protegido:
            grupo.protegido = True
            grupo.save(update_fields=["protegido", "modificado"])
        for indice, (origen, vinculo, etiqueta, obligatorio) in enumerate(campos):
            info = VINCULOS_LEGAJO[vinculo]
            _, created = PreguntaGlobal.objects.get_or_create(
                origen=origen,
                vinculo=vinculo,
                defaults={
                    "texto": etiqueta,
                    "tipo": info["tipo"],
                    "opciones": info["opciones"],
                    "grupo": grupo,
                    "protegido": True,
                    "obligatorio": obligatorio,
                    "activo": True,
                    "canal": CanalFormulario.AMBOS,
                    # Desde 1000: el rango bajo queda libre para las preguntas que
                    # carga el operador (el orden del catálogo es único, Cambio 23).
                    "orden": orden_libre(1000 + orden * 10 + indice + 1),
                },
            )
            creados += int(created)

    clave, nombre, subtitulo, orden = GRUPO_CUESTIONARIO
    cuestionario, _ = GrupoRequisito.objects.get_or_create(
        clave=clave, defaults={"nombre": nombre, "subtitulo": subtitulo, "orden": orden}
    )
    PreguntaGlobal.objects.filter(grupo__isnull=True).update(grupo=cuestionario)
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

        protegidos = asegurar_catalogo_protegido()
        self.stdout.write(
            self.style.SUCCESS(
                f"  ✓ Catálogo protegido asegurado ({protegidos} campos nuevos; "
                f"grupos {', '.join(c[1] for c in CATALOGO_PROTEGIDO)} + {GRUPO_CUESTIONARIO[1]})"
            )
        )

        asegurar_roles_becas(programa)
        self.stdout.write(self.style.SUCCESS(f"  ✓ Roles RBAC asegurados: {', '.join(ROLES_BECAS)}"))

        self.stdout.write(self.style.SUCCESS("\nSeed Becas completo."))
