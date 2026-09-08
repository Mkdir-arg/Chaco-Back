from django.db import migrations, models


def crear_perfiles_faltantes(apps, schema_editor):
    User = apps.get_model("auth", "User")
    Profile = apps.get_model("users", "Profile")
    existentes = set(Profile.objects.values_list("user_id", flat=True))
    faltantes = User.objects.exclude(pk__in=existentes).values_list("pk", flat=True)
    Profile.objects.bulk_create(Profile(user_id=user_id) for user_id in faltantes)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0012_profile_datos_personales"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="backoffice_session_key",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=40,
                null=True,
                verbose_name="Sesión activa de Backoffice",
            ),
        ),
        migrations.RunPython(crear_perfiles_faltantes, migrations.RunPython.noop),
    ]
