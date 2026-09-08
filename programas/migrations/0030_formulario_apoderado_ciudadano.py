from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("programas", "0029_formulario_captura_mobile")]

    operations = [
        migrations.AddField(
            model_name="formulario",
            name="apoderado_dni",
            field=models.CharField(blank=True, db_index=True, max_length=20, verbose_name="DNI del apoderado"),
        ),
        migrations.AddField(
            model_name="formulario",
            name="apoderado_genero",
            field=models.CharField(blank=True, choices=[("M", "Masculino"), ("F", "Femenino"), ("X", "No binario")], max_length=1, verbose_name="Sexo del apoderado"),
        ),
        migrations.AddField(
            model_name="formulario",
            name="apoderado_ciudadano",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="formularios_becas_como_apoderado", to="legajos.ciudadano", verbose_name="Ciudadano apoderado"),
        ),
    ]
