"""El rol protegido «Administrador» recibe `inspeccion.agente.crear` (28-oct-2026).

Capacidad nueva: «Dar de alta agentes de relevamiento edilicio», desde el modal de asignar un
relevamiento de Dispositivos. Va por migración y no por `seed_rbac` por el mismo motivo que
`users.0040`: el Administrador es protegido (el ABM no lo deja editar) y en ECOM el `seed_rbac`
del arranque no corre. Solo el Administrador; el resto de los roles la tildan desde el ABM de
Roles (el PM lo hace en el rol intermedio de Dispositivos). La reversa la saca solo del
Administrador y no borra la `Permission`, que es de esta misma migración al estado.
"""

import logging

from django.db import migrations

ROL_ADMINISTRADOR = "Administrador"
CLAVE_ADMINISTRADOR = "sistema.administrador"
CAPACIDAD = ("inspeccion_agente_crear", "Dar de alta agentes de relevamiento edilicio")

logger = logging.getLogger(__name__)


def _administrador(apps):
    """El grupo del Administrador: por su clave estable y, si nadie la tiene, por el nombre."""
    Group = apps.get_model("auth", "Group")
    RolMeta = apps.get_model("users", "RolMeta")

    meta = RolMeta.objects.filter(clave=CLAVE_ADMINISTRADOR).select_related("grupo").first()
    if meta is not None:
        return meta.grupo
    return Group.objects.filter(name=ROL_ADMINISTRADOR).first()


def sembrar(apps, schema_editor):
    administrador = _administrador(apps)
    if administrador is None:
        # Base nueva: `seed_rbac` crea el Administrador con todo el catálogo.
        return
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    # `get_or_create`: en una base que migra de corrido el `post_migrate` aún no materializó la capacidad.
    content_type, _ = ContentType.objects.get_or_create(app_label="users", model="capacidad")
    permiso, _ = Permission.objects.get_or_create(
        content_type=content_type, codename=CAPACIDAD[0], defaults={"name": CAPACIDAD[1]}
    )
    # Idempotente: `add` no duplica.
    administrador.permissions.add(permiso)
    logger.info("Administrador «%s»: tiene %s.", administrador.name, permiso.codename)


def quitar(apps, schema_editor):
    """Reversa real: la capacidad sale **solo** del Administrador (los demás roles la conservan)."""
    administrador = _administrador(apps)
    if administrador is None:
        return
    Permission = apps.get_model("auth", "Permission")
    permisos = list(Permission.objects.filter(content_type__app_label="users", codename=CAPACIDAD[0]))
    administrador.permissions.remove(*permisos)


class Migration(migrations.Migration):
    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("users", "0042_retirar_capacidades_institucion"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="capacidad",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": [
                    ("ciudadano_ver", "Ver ciudadanos y legajos"),
                    ("ciudadano_crear", "Crear ciudadanos"),
                    ("ciudadano_editar", "Editar ciudadanos"),
                    ("ciudadano_sensible", "Ver datos sensibles"),
                    ("ciudadano_exportar", "Exportar el padrón de ciudadanos"),
                    ("programa_configurar", "Configurar programas"),
                    ("programa_usuario_administrar", "Administrar los usuarios de su programa"),
                    ("programa_rol_administrar", "Administrar los roles de su programa"),
                    ("dispositivo_ver", "Ver dispositivos"),
                    ("dispositivo_crear", "Crear dispositivos"),
                    ("dispositivo_editar", "Editar dispositivos"),
                    ("dispositivo_validar", "Validar dispositivos"),
                    ("dispositivo_admitir", "Admitir personas en dispositivos"),
                    ("dispositivo_egresar", "Registrar egresos de dispositivos"),
                    ("dispositivo_bitacora", "Cargar novedades en la bitácora del turno"),
                    ("inspeccion_asignar", "Crear, asignar, reasignar y cancelar relevamientos edilicios"),
                    ("inspeccion_relevar", "Cargar el resultado de los relevamientos edilicios asignados"),
                    ("inspeccion_agente_crear", "Dar de alta agentes de relevamiento edilicio"),
                    ("merendero_ver", "Ver merenderos"),
                    ("merendero_crear", "Crear merenderos"),
                    ("merendero_editar", "Editar merenderos"),
                    ("merendero_validar", "Validar merenderos"),
                    ("merendero_entregar", "Registrar entregas a merenderos"),
                    ("relevamiento_ver", "Ver relevamientos"),
                    ("relevamiento_gestionar", "Gestionar relevamientos"),
                    (
                        "becas_programa_administrar",
                        "Administrar el programa Becas (acceso total, asigna coordinadores)",
                    ),
                    ("becas_usuario_territorial", "Crear y administrar territoriales de los segmentos coordinados"),
                    ("becas_referente", "Operar como Referente dentro del alcance de su Coordinador"),
                    (
                        "becas_coordinador_regional",
                        "Operar como Coordinador Regional dentro de su subsegmento asignado",
                    ),
                    (
                        "becas_programa_proceso_masivo",
                        "Ejecutar el proceso masivo a SIIS (aprueba e informa altas en lote)",
                    ),
                    ("becas_segmento_ver", "Ver segmentos"),
                    ("becas_segmento_crear", "Crear segmentos"),
                    ("becas_segmento_editar", "Editar segmentos (incluye activar/desactivar)"),
                    ("becas_subsegmento_ver", "Ver subsegmentos"),
                    ("becas_subsegmento_crear", "Crear subsegmentos"),
                    ("becas_subsegmento_editar", "Editar subsegmentos (incluye eliminar)"),
                    ("becas_requisito_ver", "Ver requisitos nativos"),
                    ("becas_requisito_crear", "Crear requisitos nativos"),
                    ("becas_requisito_editar", "Editar requisitos nativos (incluye eliminar)"),
                    ("becas_pregunta_ver", "Ver preguntas globales (requisitos generales)"),
                    ("becas_pregunta_crear", "Crear preguntas globales"),
                    ("becas_pregunta_editar", "Editar preguntas globales (incluye activar/desactivar/eliminar)"),
                    ("becas_coordinador_ver", "Ver coordinadores asignados a segmentos"),
                    ("becas_coordinador_crear", "Asignar coordinador a un segmento"),
                    ("becas_coordinador_editar", "Desasignar coordinador de un segmento"),
                    ("becas_convocatoria_ver", "Ver convocatorias"),
                    ("becas_convocatoria_crear", "Crear convocatorias"),
                    ("becas_convocatoria_editar", "Editar convocatorias (incluye activar/desactivar)"),
                    ("becas_relevamiento_ver", "Ver relevamientos de Becas"),
                    ("becas_relevamiento_crear", "Crear relevamientos de Becas"),
                    ("becas_relevamiento_editar", "Editar relevamientos (reasignar territorial, reprogramar)"),
                    (
                        "becas_relevamiento_publico",
                        "Crear y ver relevamientos de formulario público (link de inscripción)",
                    ),
                    ("becas_revision_ver", "Ver relevamientos en revisión y sus formularios"),
                    ("becas_revision_editar", "Revisar formularios de Becas (iniciar, aprobar, rechazar, terminar)"),
                    (
                        "becas_revision_identidad",
                        "Validar la identidad de un caso: revalidar RENAPER, forzar identidad, validar padrón y corregir género",
                    ),
                    ("becas_cupo_ver", "Ver ocupación y capacidad de cupo por segmento"),
                    ("becas_beneficiario_ver", "Ver beneficiarios, lista de espera y pendientes"),
                    ("becas_beneficiario_editar", "Dar de baja, promover y agregar a lista de espera beneficiarios"),
                    ("becas_reportes_ver", "Ver reportes de Becas"),
                    ("becas_reportes_exportar", "Exportar reportes de Becas"),
                    ("becas_campo", "Operar la app de campo de Becas (territorial)"),
                    ("conversacion_operar", "Operar conversaciones"),
                    ("conversacion_configurar", "Configurar conversaciones"),
                    ("conversacion_metricas", "Ver métricas de conversaciones"),
                    ("dashboard_ver", "Ver dashboard"),
                    ("reporte_ver", "Ver reportes"),
                    ("notificacion_ver", "Ver campañas de correo y su resultado"),
                    (
                        "notificacion_gestionar",
                        "Crear, editar, duplicar y eliminar campañas de correo, y mandar pruebas",
                    ),
                    ("notificacion_enviar", "Enviar, detener y reanudar campañas de correo"),
                    ("config_ver", "Ver configuración"),
                    ("config_administrar", "Administrar configuración"),
                    ("usuario_administrar", "Administrar usuarios"),
                    ("rol_administrar", "Administrar roles"),
                ],
                "verbose_name": "Capacidad",
                "verbose_name_plural": "Capacidades",
            },
        ),
        migrations.RunPython(sembrar, quitar),
    ]
