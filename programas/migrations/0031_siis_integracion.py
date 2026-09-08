from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("programas", "0030_formulario_apoderado_ciudadano")]

    operations = [
        migrations.AddField(model_name="segmento", name="siis_programa_id", field=models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de programa SIIS")),
        migrations.AddField(model_name="segmento", name="siis_segmento_id", field=models.PositiveIntegerField(blank=True, null=True, verbose_name="ID de segmento SIIS")),
        migrations.CreateModel(
            name="ValidacionSIS",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("estado", models.CharField(choices=[("OK", "Compatible"), ("RECHAZADO", "Incompatible"), ("ERROR", "Error técnico")], db_index=True, max_length=15)),
                ("id_programa", models.PositiveIntegerField(blank=True, null=True)),
                ("id_segmento", models.PositiveIntegerField()),
                ("documento", models.CharField(max_length=20)),
                ("sexo", models.CharField(max_length=1)),
                ("id_consulta", models.UUIDField(blank=True, db_index=True, null=True)),
                ("fecha_validacion", models.DateTimeField(blank=True, null=True)),
                ("codigo_motivo", models.CharField(blank=True, max_length=100)),
                ("motivo", models.TextField(blank=True)),
                ("respuesta", models.JSONField(blank=True, default=dict)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("formulario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="validaciones_sis", to="programas.formulario", verbose_name="Formulario")),
                ("solicitado_por", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="validaciones_sis_solicitadas", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Validación SIIS", "verbose_name_plural": "Validaciones SIIS", "ordering": ["-creado"]},
        ),
    ]
