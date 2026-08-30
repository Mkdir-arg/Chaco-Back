# Cambio 58, Fase 1 — el catálogo de requisitos generales se agrupa y admite
# tres orígenes (pregunta / campo del legajo / campo del apoderado); todo
# requisito declara en qué canal se pide. Los grupos y campos protegidos los
# siembra `seed_becas` (idempotente, corre en cada arranque del pod); acá solo
# se crea el grupo por defecto y se le asignan las preguntas existentes.

import django.db.models.deletion
from django.db import migrations, models


def preguntas_al_cuestionario(apps, schema_editor):
    Grupo = apps.get_model("programas", "GrupoRequisito")
    Pregunta = apps.get_model("programas", "PreguntaGlobal")
    cuestionario, _ = Grupo.objects.get_or_create(
        clave="cuestionario",
        defaults={"nombre": "Cuestionario social", "orden": 10, "protegido": False},
    )
    Pregunta.objects.filter(grupo__isnull=True).update(grupo=cuestionario)


class Migration(migrations.Migration):

    dependencies = [
        ("programas", "0056_padron_convocatoria_identidad"),
    ]

    operations = [
        migrations.CreateModel(
            name="GrupoRequisito",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("modificado", models.DateTimeField(auto_now=True)),
                ("clave", models.SlugField(max_length=60, unique=True, verbose_name="Clave")),
                ("nombre", models.CharField(max_length=120, verbose_name="Nombre")),
                ("subtitulo", models.CharField(blank=True, max_length=240, verbose_name="Subtítulo")),
                ("orden", models.PositiveIntegerField(default=0, verbose_name="Orden")),
                ("protegido", models.BooleanField(default=False, verbose_name="Protegido")),
                ("condicion_defecto", models.JSONField(blank=True, null=True, verbose_name="Condición por defecto")),
                (
                    "canal",
                    models.CharField(
                        choices=[("ambos", "Ambos canales"), ("app", "Solo app de campo"), ("link", "Solo link público")],
                        default="ambos",
                        max_length=10,
                        verbose_name="Se pide en",
                    ),
                ),
            ],
            options={
                "verbose_name": "Grupo de requisitos",
                "verbose_name_plural": "Grupos de requisitos",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.AddField(
            model_name="preguntaglobal",
            name="grupo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="preguntas",
                to="programas.gruporequisito",
                verbose_name="Grupo",
            ),
        ),
        migrations.AddField(
            model_name="preguntaglobal",
            name="origen",
            field=models.CharField(
                choices=[
                    ("pregunta", "Pregunta"),
                    ("legajo", "Campo del legajo de la persona"),
                    ("persona_vinculada", "Campo del apoderado (persona vinculada)"),
                ],
                default="pregunta",
                max_length=20,
                verbose_name="Origen",
            ),
        ),
        migrations.AddField(
            model_name="preguntaglobal",
            name="vinculo",
            field=models.CharField(blank=True, max_length=60, verbose_name="Campo vinculado"),
        ),
        migrations.AddField(
            model_name="preguntaglobal",
            name="protegido",
            field=models.BooleanField(default=False, verbose_name="Protegido"),
        ),
        migrations.AddField(
            model_name="preguntaglobal",
            name="canal",
            field=models.CharField(
                choices=[("ambos", "Ambos canales"), ("app", "Solo app de campo"), ("link", "Solo link público")],
                default="ambos",
                max_length=10,
                verbose_name="Se pide en",
            ),
        ),
        migrations.AddField(
            model_name="requisitonativo",
            name="canal",
            field=models.CharField(
                choices=[("ambos", "Ambos canales"), ("app", "Solo app de campo"), ("link", "Solo link público")],
                default="ambos",
                max_length=10,
                verbose_name="Se pide en",
            ),
        ),
        migrations.AlterField(
            model_name="formulario",
            name="celular",
            field=models.CharField(blank=True, max_length=20, verbose_name="Celular"),
        ),
        migrations.AlterField(
            model_name="formulario",
            name="email_contacto",
            field=models.EmailField(blank=True, max_length=254, verbose_name="Correo electrónico"),
        ),
        migrations.RunPython(preguntas_al_cuestionario, migrations.RunPython.noop),
    ]
