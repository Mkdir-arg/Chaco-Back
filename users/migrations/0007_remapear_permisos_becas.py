"""Remapea los permisos viejos de Becas a las capacidades finas nuevas.

Antes de esta migración, todo el Programa Becas colgaba de 4 capacidades
(``becas_configurar``, ``becas_relevamientos``, ``becas_revisar``,
``becas_campo``). La migración ``0006_granularizar_permisos_becas`` ya quitó
las 3 primeras del catálogo (``Capacidad.Meta.permissions``); esta migración
de datos se asegura de que ningún ``Group`` (rol) pierda acceso en silencio:
por cada rol que tuviera una de esas 3 capacidades viejas tildada, le agrega
las capacidades finas equivalentes ANTES de borrar el permiso viejo de la
tabla ``auth_permission``. Cubre tanto los 3 roles semillados de
``seed_becas`` como cualquier rol custom creado a mano desde el ABM de Roles.

``becas_campo`` no tiene equivalente fino (queda igual) y no se toca.
"""

from django.db import migrations

# codename viejo -> [(codename nuevo, etiqueta), ...]
CODENAME_MAP = {
    "becas_configurar": [
        ("becas_programa_administrar", "Administrar el programa Becas (acceso total, asigna coordinadores)"),
        ("becas_segmento_ver", "Ver segmentos"),
        ("becas_segmento_crear", "Crear segmentos"),
        ("becas_segmento_editar", "Editar segmentos (incluye activar/desactivar)"),
        ("becas_subsegmento_ver", "Ver subsegmentos"),
        ("becas_subsegmento_crear", "Crear subsegmentos"),
        ("becas_subsegmento_editar", "Editar subsegmentos (incluye eliminar)"),
        ("becas_requisito_ver", "Ver requisitos nativos"),
        ("becas_requisito_crear", "Crear requisitos nativos"),
        ("becas_requisito_editar", "Editar requisitos nativos (incluye eliminar)"),
        ("becas_pregunta_ver", "Ver preguntas globales (cuestionario social)"),
        ("becas_pregunta_crear", "Crear preguntas globales"),
        ("becas_pregunta_editar", "Editar preguntas globales (incluye activar/desactivar/eliminar)"),
        ("becas_coordinador_ver", "Ver coordinadores asignados a segmentos"),
        ("becas_coordinador_crear", "Asignar coordinador a un segmento"),
        ("becas_coordinador_editar", "Desasignar coordinador de un segmento"),
    ],
    "becas_relevamientos": [
        ("becas_convocatoria_ver", "Ver convocatorias (incluye exportar CSV)"),
        ("becas_convocatoria_crear", "Crear convocatorias"),
        ("becas_convocatoria_editar", "Editar convocatorias (incluye activar/desactivar)"),
        ("becas_relevamiento_ver", "Ver relevamientos de Becas"),
        ("becas_relevamiento_crear", "Crear relevamientos de Becas"),
        ("becas_relevamiento_editar", "Editar relevamientos (reasignar territorial, reprogramar)"),
    ],
    "becas_revisar": [
        ("becas_revision_ver", "Ver relevamientos en revisión y sus formularios"),
        ("becas_revision_editar", "Revisar formularios de Becas (iniciar, aprobar, rechazar, terminar)"),
        ("becas_cupo_ver", "Ver ocupación y capacidad de cupo por segmento"),
        ("becas_beneficiario_ver", "Ver beneficiarios, lista de espera y pendientes"),
        ("becas_beneficiario_editar", "Dar de baja, promover y agregar a lista de espera beneficiarios"),
    ],
}


def remapear_permisos_becas(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    try:
        ct = ContentType.objects.get(app_label="users", model="capacidad")
    except ContentType.DoesNotExist:
        return

    for codename_viejo, capacidades_nuevas in CODENAME_MAP.items():
        try:
            perm_viejo = Permission.objects.get(content_type=ct, codename=codename_viejo)
        except Permission.DoesNotExist:
            continue

        grupos = list(perm_viejo.group_set.all())
        if grupos:
            permisos_nuevos = []
            for codename_nuevo, etiqueta in capacidades_nuevas:
                perm_nuevo, _ = Permission.objects.get_or_create(
                    content_type=ct, codename=codename_nuevo, defaults={"name": etiqueta}
                )
                permisos_nuevos.append(perm_nuevo)
            for grupo in grupos:
                grupo.permissions.add(*permisos_nuevos)

        perm_viejo.delete()


def noop_reverse(apps, schema_editor):
    """No reversible: no hay forma de reconstruir qué Group tenía cada
    capacidad vieja después de haberla borrado."""


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0006_granularizar_permisos_becas"),
    ]

    operations = [
        migrations.RunPython(remapear_permisos_becas, noop_reverse),
    ]
