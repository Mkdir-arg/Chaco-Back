# Cambio 57 — el padrón pasa del relevamiento público a la convocatoria y trae
# identidad (nombre, apellido, fecha de nacimiento, localidad). El caso guarda
# de dónde salió su validación (origen_validacion).
#
# Escrita a mano para mover los datos que hubiera (ambientes locales / testing):
# la FK nueva nace nullable, se copia la convocatoria de cada relevamiento, se
# deduplica por (convocatoria, dni) y recién ahí se vuelve obligatoria.

import django.db.models.deletion
from django.db import migrations, models
from django.db.migrations.exceptions import IrreversibleError

import programas.models

# BARRERA-DE-REVERSA: por debajo de programas.0056 solo se vuelve con restore (RED-57).
# La migración **borra filas** del padrón (los DNI repetidos dentro de una misma
# convocatoria) y quita la FK al relevamiento: al revertir, esas filas no vuelven y el
# resto queda sin saber de qué relevamiento salió.
# Runbook D.4 de docs/internal/processes.md.
MENSAJE_BARRERA = (
    "programas.0056 es una barrera de reversa (RED-57): la ida borró filas del padrón "
    "duplicadas por convocatoria y la vuelta no las recupera, ni reconstruye de qué "
    "relevamiento venía cada fila. Volver atrás se hace con restore del dump previo al "
    "deploy: runbook D.4 de docs/internal/processes.md. No reintentar ni usar --fake."
)


def sin_cambios(apps, schema_editor):
    """La barrera no toca nada hacia adelante: solo existe para el camino de vuelta."""


def bloquear_reversa(apps, schema_editor):
    # Es la última operación de la migración, así que Django la corre **primera** al
    # desaplicar: aborta antes de cualquier DDL. Vale en todos los motores: lo que se
    # pierde son filas, y eso no depende del motor.
    raise IrreversibleError(MENSAJE_BARRERA)


def mover_padron_a_convocatoria(apps, schema_editor):
    Padron = apps.get_model("programas", "PadronHabilitado")
    Relevamiento = apps.get_model("programas", "Relevamiento")

    vistos = set()
    for fila in Padron.objects.select_related("relevamiento").order_by("id"):
        clave = (fila.relevamiento.convocatoria_id, fila.dni)
        if clave in vistos:
            # Dos relevamientos públicos de la misma convocatoria con el mismo
            # DNI: gana la primera fila cargada.
            fila.delete()
            continue
        vistos.add(clave)
        fila.convocatoria_id = fila.relevamiento.convocatoria_id
        fila.save(update_fields=["convocatoria"])

    for rel in Relevamiento.objects.exclude(padron_archivo="").exclude(padron_archivo__isnull=True).select_related(
        "convocatoria"
    ):
        convocatoria = rel.convocatoria
        if not convocatoria.padron_archivo:
            convocatoria.padron_archivo = rel.padron_archivo
            convocatoria.save(update_fields=["padron_archivo"])


def origen_validacion_inicial(apps, schema_editor):
    Formulario = apps.get_model("programas", "Formulario")
    Formulario.objects.filter(validado_renaper=True, identidad_forzada=True).update(origen_validacion="forzada")
    Formulario.objects.filter(validado_renaper=True, identidad_forzada=False).update(origen_validacion="personas")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("programas", "0055_presentacion_selector"),
    ]

    operations = [
        # ── Convocatoria: el archivo del padrón ──────────────────────────────
        migrations.AddField(
            model_name="convocatoria",
            name="padron_archivo",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to=programas.models.ruta_padron_becas,
                verbose_name="Padrón de habilitados (archivo)",
            ),
        ),
        # ── PadronHabilitado: FK nueva (nullable por ahora) + identidad ─────
        migrations.AddField(
            model_name="padronhabilitado",
            name="convocatoria",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="padron",
                to="programas.convocatoria",
                verbose_name="Convocatoria",
            ),
        ),
        migrations.AddField(
            model_name="padronhabilitado",
            name="nombre",
            field=models.CharField(blank=True, max_length=120, verbose_name="Nombre"),
        ),
        migrations.AddField(
            model_name="padronhabilitado",
            name="apellido",
            field=models.CharField(blank=True, max_length=120, verbose_name="Apellido"),
        ),
        migrations.AddField(
            model_name="padronhabilitado",
            name="fecha_nacimiento",
            field=models.DateField(blank=True, null=True, verbose_name="Fecha de nacimiento"),
        ),
        migrations.AddField(
            model_name="padronhabilitado",
            name="localidad",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="core.localidad",
                verbose_name="Localidad",
            ),
        ),
        migrations.AddField(
            model_name="padronhabilitado",
            name="localidad_texto",
            field=models.CharField(blank=True, max_length=120, verbose_name="Localidad (texto del Excel)"),
        ),
        # ── Datos: cada fila a la convocatoria de su relevamiento ───────────
        # REVERSA-NOOP: las filas del padrón que esta operación borró por duplicadas
        # (mismo DNI en dos relevamientos de la convocatoria) no vuelven, y el
        # ``padron_archivo`` copiado a la convocatoria queda ahí.
        migrations.RunPython(mover_padron_a_convocatoria, migrations.RunPython.noop),
        # ── Índice y unicidad viejos, FK vieja ──────────────────────────────
        migrations.RemoveConstraint(
            model_name="padronhabilitado",
            name="uniq_padron_dni_relevamiento",
        ),
        migrations.RemoveIndex(
            model_name="padronhabilitado",
            name="programas_p_relevam_8abf0a_idx",
        ),
        migrations.RemoveField(
            model_name="padronhabilitado",
            name="relevamiento",
        ),
        migrations.RemoveField(
            model_name="relevamiento",
            name="padron_archivo",
        ),
        # ── FK obligatoria, unicidad e índice nuevos ────────────────────────
        migrations.AlterField(
            model_name="padronhabilitado",
            name="convocatoria",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="padron",
                to="programas.convocatoria",
                verbose_name="Convocatoria",
            ),
        ),
        migrations.AddConstraint(
            model_name="padronhabilitado",
            constraint=models.UniqueConstraint(fields=("convocatoria", "dni"), name="uniq_padron_dni_convocatoria"),
        ),
        migrations.AddIndex(
            model_name="padronhabilitado",
            index=models.Index(fields=["convocatoria", "dni", "sexo"], name="programas_padron_conv_dni_idx"),
        ),
        # ── Formulario: de dónde salió la validación ────────────────────────
        migrations.AddField(
            model_name="formulario",
            name="origen_validacion",
            field=models.CharField(
                blank=True,
                choices=[
                    ("personas", "Base de Personas"),
                    ("padron", "Padrón de la convocatoria"),
                    ("scan", "Escaneo del DNI"),
                    ("forzada", "Validación manual"),
                ],
                default="",
                max_length=10,
                verbose_name="Origen de la validación de identidad",
            ),
        ),
        # REVERSA-NOOP: no queda nada inconsistente. Lo único que escribe es
        # ``origen_validacion``, la columna que la operación anterior agrega y que la
        # reversa borra enseguida.
        migrations.RunPython(origen_validacion_inicial, migrations.RunPython.noop),
        migrations.RunPython(sin_cambios, bloquear_reversa),
    ]
