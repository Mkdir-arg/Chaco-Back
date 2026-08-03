from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("programas", "0033_siis_catalogo_constraints")]

    operations = [
        migrations.AddField(
            model_name="formulario",
            name="conflicto_duplicado",
            field=models.BooleanField(default=False, db_index=True, verbose_name="Posible DNI duplicado pendiente de revisión"),
        ),
        migrations.AddField(
            model_name="formulario",
            name="conflicto_resuelto",
            field=models.BooleanField(default=False, verbose_name="Conflicto de DNI resuelto"),
        ),
        migrations.AddField(
            model_name="formulario",
            name="duplicado_de",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cargas_en_conflicto", to="programas.formulario", verbose_name="Formulario previo con el mismo DNI"),
        ),
    ]
