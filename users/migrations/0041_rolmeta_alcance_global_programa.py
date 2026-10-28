# El campo «Categoría» del rol pasa a ser «Alcance»: Global o De un programa.
#
# Los valores guardados NO se renombran: ``Backoffice`` es «Global» y ``Programa`` es «De un
# programa». Desaparecen ``Sistema``, ``Institución`` y ``Becas``, que no decidían ninguna
# autorización (el alcance lo da ``RolMeta.programa``). Esta migración los reubica
# preservando EXACTAMENTE el comportamiento actual:
#
# - ``Sistema`` e ``Institución`` -> ``Backoffice`` (eran etiquetas cosméticas de roles globales).
# - ``Becas`` con programa -> ``Programa`` (``users.selectors.roles`` ya lo trataba como de
#   programa solo cuando tenía ``programa_id``).
# - ``Becas`` sin programa -> ``Backoffice`` (hoy se comporta como global).
#
# Idempotente: filtra por el estado de origen, así que correrla dos veces (o reintentarla
# tras un corte) no cambia nada la segunda vez. El ``AlterField`` solo cambia ``choices`` y
# etiquetas: no genera SQL.
from django.db import migrations, models

CATEGORIA_CHOICES = [
    ("Backoffice", "Global"),
    ("Programa", "De un programa"),
    ("Portal", "Portal (identidad ciudadana)"),
]


def reubicar_categorias(apps, schema_editor):
    RolMeta = apps.get_model("users", "RolMeta")
    RolMeta.objects.filter(categoria__in=["Sistema", "Institución"]).update(categoria="Backoffice")
    RolMeta.objects.filter(categoria="Becas", programa__isnull=False).update(categoria="Programa")
    RolMeta.objects.filter(categoria="Becas", programa__isnull=True).update(categoria="Backoffice")


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0040_administrador_inspeccion_e_identidad"),
    ]

    operations = [
        migrations.AlterField(
            model_name="rolmeta",
            name="categoria",
            field=models.CharField(
                choices=CATEGORIA_CHOICES,
                default="Backoffice",
                max_length=20,
                verbose_name="Alcance",
            ),
        ),
        migrations.RunPython(
            reubicar_categorias,
            # REVERSA-NOOP: no se puede saber el valor original; se pierde la etiqueta
            # Sistema/Institución/Becas de cada rol, que es cosmética: la autorización no cambia.
            migrations.RunPython.noop,
        ),
    ]
