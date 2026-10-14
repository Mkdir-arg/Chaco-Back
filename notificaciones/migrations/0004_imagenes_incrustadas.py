"""Cambio 292: las imágenes del .zip pasan de la URL pública a ``cid:`` (incrustadas en el correo).

Reescribe en ``html_sanitizado`` cada ``src`` de la forma ``…/notificaciones/img/<token>/<nombre>``
—la ruta pública del Cambio 285, que se retira— a ``cid:<nombre>@datanach``, **solo** cuando la
campaña tiene esa ``ImagenCampana`` (mismo token y nombre). Una URL que no corresponde a una
imagen de la campaña queda como está. ``texto_plano`` no nombra imágenes: no se toca.
"""

import re

from django.db import migrations

_SRC_PUBLICO = re.compile(r'src="https?://[^"\s]*?/notificaciones/img/([A-Za-z0-9_-]+)/([A-Za-z0-9._-]+)"')


def a_cid(apps, schema_editor):
    Campana = apps.get_model("notificaciones", "Campana")
    ImagenCampana = apps.get_model("notificaciones", "ImagenCampana")
    for campana in Campana.objects.filter(html_sanitizado__contains="/notificaciones/img/").only(
        "pk", "html_sanitizado"
    ):
        propias = set(ImagenCampana.objects.filter(campana_id=campana.pk).values_list("token", "nombre"))

        def reemplazo(match, propias=propias):
            token, nombre = match.group(1), match.group(2)
            return f'src="cid:{nombre}@datanach"' if (token, nombre) in propias else match.group(0)

        nuevo = _SRC_PUBLICO.sub(reemplazo, campana.html_sanitizado)
        if nuevo != campana.html_sanitizado:
            Campana.objects.filter(pk=campana.pk).update(html_sanitizado=nuevo)


class Migration(migrations.Migration):
    dependencies = [
        ("notificaciones", "0003_imagenes_y_reintentos"),
    ]

    operations = [
        # REVERSA-NOOP: los src quedan como cid:<nombre>@datanach. El código del Cambio 285
        # los mostraría como imágenes rotas (esperaba la URL pública, que el WAF bloquea
        # igual); para volver a la URL hay que re-subir el .zip de cada campaña «A enviar».
        migrations.RunPython(a_cid, migrations.RunPython.noop),
    ]
