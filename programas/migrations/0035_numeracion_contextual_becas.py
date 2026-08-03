from django.db import migrations, models


def numerar_existentes(apps, schema_editor):
    Relevamiento = apps.get_model("programas", "Relevamiento")
    Formulario = apps.get_model("programas", "Formulario")

    for convocatoria_id in Relevamiento.objects.values_list("convocatoria_id", flat=True).distinct():
        relevamientos = Relevamiento.objects.filter(convocatoria_id=convocatoria_id).order_by("creado", "pk")
        for numero, relevamiento in enumerate(relevamientos, start=1):
            Relevamiento.objects.filter(pk=relevamiento.pk).update(numero=numero, nombre=f"Relevamiento {numero:03d}")

    for relevamiento_id in Formulario.objects.values_list("relevamiento_id", flat=True).distinct():
        formularios = Formulario.objects.filter(relevamiento_id=relevamiento_id).order_by("creado", "pk")
        for numero, formulario in enumerate(formularios, start=1):
            Formulario.objects.filter(pk=formulario.pk).update(numero=numero)


class Migration(migrations.Migration):
    dependencies = [("programas", "0034_formulario_conflicto_duplicado")]

    operations = [
        migrations.AddField(
            model_name="relevamiento",
            name="numero",
            field=models.PositiveIntegerField(editable=False, null=True, verbose_name="Número dentro de la convocatoria"),
        ),
        migrations.AddField(
            model_name="formulario",
            name="numero",
            field=models.PositiveIntegerField(editable=False, null=True, verbose_name="Número dentro del relevamiento"),
        ),
        migrations.RunPython(numerar_existentes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="relevamiento",
            name="numero",
            field=models.PositiveIntegerField(editable=False, verbose_name="Número dentro de la convocatoria"),
        ),
        migrations.AlterField(
            model_name="formulario",
            name="numero",
            field=models.PositiveIntegerField(editable=False, verbose_name="Número dentro del relevamiento"),
        ),
        migrations.AddConstraint(
            model_name="relevamiento",
            constraint=models.UniqueConstraint(fields=("convocatoria", "numero"), name="uniq_relevamiento_numero_convocatoria"),
        ),
        migrations.AddConstraint(
            model_name="formulario",
            constraint=models.UniqueConstraint(fields=("relevamiento", "numero"), name="uniq_formulario_numero_relevamiento"),
        ),
    ]
