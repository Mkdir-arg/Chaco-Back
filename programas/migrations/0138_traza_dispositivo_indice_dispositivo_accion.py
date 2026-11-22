# Cambio 573: índice (dispositivo, accion) para el feed del historial, que cuenta y filtra las trazas por
# dispositivo y acción (full scan sobre 120k trazas, ~0,7 s). La reversa es la del AddIndex.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0137_traza_dispositivo_edificio"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="trazadispositivo",
            index=models.Index(fields=["dispositivo", "accion"], name="traza_disp_dispositivo_accion"),
        ),
    ]
