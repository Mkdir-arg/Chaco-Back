"""Context processors del portal ciudadano."""

import re

from django.conf import settings

# Un contenedor de GTM es «GTM-» más letras y números. Cualquier otra cosa en
# la variable se descarta: el ID va a un <script> y a un atributo sin más
# escape que este.
CONTENEDOR_GTM = re.compile(r"^GTM-[A-Z0-9]+$")


def gtm(request):
    """El contenedor de Google Tag Manager de las pantallas públicas de
    inscripción (Cambio 68). Vacío = no se renderiza nada: los entornos sin
    ``GTM_CONTAINER_ID`` no mandan datos a Google."""
    contenedor = (getattr(settings, "GTM_CONTAINER_ID", "") or "").strip()
    return {"gtm_container_id": contenedor if CONTENEDOR_GTM.match(contenedor) else ""}
