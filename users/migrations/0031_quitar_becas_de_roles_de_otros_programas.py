"""SEC-06 / **D-06 = No**: saca las capacidades ``becas.*`` de los roles de otro programa.

El árbol del ABM de Roles le ofrecía los trece módulos ``becas_*`` al admin de roles de
**cualquier** programa, y los gates de Becas evaluaban esas capacidades **sin alcance**.
Con eso, el admin de Dispositivos creaba un rol de Dispositivos con
``becas.programa.administrar``, se lo asignaba, y bajaba el CSV con DNI de cualquier
convocatoria y lanzaba el proceso masivo a SIIS. El catálogo ya no las ofrece
(``core/rbac.py``) y los gates ya evalúan con alcance; acá se limpia lo que haya quedado
tildado de antes.

**Esta migración QUITA accesos.** D-06 (README §2.2) registra que ningún rol de otro
programa usa capacidades de Becas a propósito, y el pre-chequeo **P-02** (README §3) es
la consulta que el PM corre en PRD **antes** de desplegar para confirmarlo: si da vacío,
esta migración no quita nada. Si no da vacío, lo que quita es exactamente lo que P-02
lista, y queda registrado en ``users_capacidadrevocada`` y en la salida del ``migrate``.

**Roles sembrados:** ninguno de los cinco roles de Becas se ve afectado —son del
programa BECAS—. Un rol **sembrado de otro programa** con capacidades de Becas no
existe: hoy el único seed que reparte ``becas.*`` es ``seed_becas``, y siempre sobre
roles de Becas. Si en una base concreta hubiera uno, aparecería en P-02 con su nombre y
el PM lo vería antes de desplegar; esta migración no hace excepciones por nombre.

**Reversa real:** cada par (rol, capacidad) que se quita queda escrito en
``users_capacidadrevocada``, así que desaplicar restituye exactamente lo que había y no
una reconstrucción aproximada (que acá sería imposible: el dato ya no está).
"""

import logging

from django.db import migrations

#: Prefijo de los codenames del dominio Becas (``becas.programa.administrar`` →
#: ``becas_programa_administrar``). El ``\\_`` escapa el comodín de ``LIKE``.
PREFIJO = "becas_"
CODIGO_BECAS = "BECAS"
#: Etiqueta con la que quedan registradas las filas en ``users_capacidadrevocada``.
MIGRACION = "users.0031"

logger = logging.getLogger(__name__)


def _roles_de_otro_programa(apps):
    """Los ``Group`` con ``RolMeta.programa`` no nulo y distinto de BECAS."""
    Group = apps.get_model("auth", "Group")
    Programa = apps.get_model("programas", "Programa")

    becas_ids = list(Programa.objects.filter(codigo=CODIGO_BECAS).values_list("pk", flat=True))
    return Group.objects.filter(meta__programa__isnull=False).exclude(meta__programa_id__in=becas_ids).order_by("name")


def quitar(apps, schema_editor):
    CapacidadRevocada = apps.get_model("users", "CapacidadRevocada")

    quitadas = []
    for grupo in _roles_de_otro_programa(apps):
        # ``startswith`` en Python y no ``codename__startswith``: la lista de permisos de
        # un rol son decenas de filas, y así el ``LIKE`` con guion bajo —que en SQL es un
        # comodín— no tiene que escaparse motor por motor.
        permisos = [p for p in grupo.permissions.all() if p.codename.startswith(PREFIJO)]
        if not permisos:
            continue
        grupo.permissions.remove(*permisos)
        for permiso in permisos:
            CapacidadRevocada.objects.get_or_create(
                grupo=grupo,
                codename=permiso.codename,
                migracion=MIGRACION,
            )
            quitadas.append((grupo.name, permiso.codename))

    if not quitadas:
        logger.info("SEC-06: ningún rol de otro programa tenía capacidades de Becas (P-02 daba vacío).")
        return
    logger.warning(
        "SEC-06 / D-06: se quitaron %s capacidades de Becas de roles de otro programa. "
        "Queda registrado en users_capacidadrevocada (migracion=%s) y la reversa lo restituye. Detalle: %s",
        len(quitadas),
        MIGRACION,
        "; ".join(f"«{rol}» → {codename}" for rol, codename in quitadas),
    )


def restituir(apps, schema_editor):
    """Devuelve a cada rol exactamente las capacidades que la ida le quitó."""
    CapacidadRevocada = apps.get_model("users", "CapacidadRevocada")
    Permission = apps.get_model("auth", "Permission")

    filas = list(CapacidadRevocada.objects.filter(migracion=MIGRACION).select_related("grupo"))
    if not filas:
        return
    por_codename = {
        permiso.codename: permiso
        for permiso in Permission.objects.filter(
            content_type__app_label="users",
            content_type__model="capacidad",
            codename__in={fila.codename for fila in filas},
        )
    }
    for fila in filas:
        permiso = por_codename.get(fila.codename)
        if permiso is not None:
            fila.grupo.permissions.add(permiso)
    CapacidadRevocada.objects.filter(migracion=MIGRACION).delete()
    logger.warning("SEC-06: se restituyeron %s capacidades de Becas al desaplicar %s.", len(filas), MIGRACION)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0030_backfill_rolmeta_clave"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("programas", "0083_sec09_upload_to_uuid"),
    ]

    operations = [
        migrations.RunPython(quitar, restituir),
    ]
