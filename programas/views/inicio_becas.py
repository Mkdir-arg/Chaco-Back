"""Índice de Becas: qué contesta ``/becas/``.

`programas.urls` no tenía ruta `""`, así que `/becas/` daba **404 a todo el
mundo** —incluido un superusuario— aunque sea el prefijo de un módulo entero y
la raíz natural a la que se llega borrando la cola de la URL (#521, QA de
testing 06/10/2026). Becas no tiene una pantalla de tablero propia: el índice es
la primera pantalla que el usuario puede ver, el mismo criterio —y el mismo
orden— que ya usa el link del sidebar colapsado
(`templates/includes/sidebar/opciones.html`). Acá no se decide nada nuevo: se
redirige a donde el menú ya lleva.
"""

from django.shortcuts import redirect

from core.rbac import puede, requiere

# Orden de preferencia del índice, igual al del link «Programas» del sidebar.
# Las capacidades van literales a propósito: importarlas de los otros módulos de
# `views/` sería una arista vista→vista, que es justo lo que el ratchet de
# `programas.tests.test_arquitectura.CapasTests` no deja crecer. Cada módulo de
# vistas declara su propia constante con el mismo código; que estas cuatro sigan
# coincidiendo con las de allá lo verifica `test_inicio_becas`.
DESTINOS = (
    ("becas.segmento.ver", "becas:segmentos"),
    ("becas.convocatoria.ver", "becas:convocatorias"),
    ("becas.relevamiento.ver", "becas:relevamientos"),
    ("becas.revision.ver", "becas:revision"),
)


@requiere(*(capacidad for capacidad, _ in DESTINOS))
def inicio(request):
    """Manda al primer listado de Becas que el usuario puede ver.

    El decorador resuelve los dos bordes con el mismo criterio que el resto de
    Becas: anónimo va al login, y un usuario de backoffice sin ninguna de las
    cuatro capacidades vuelve al inicio con el mensaje de siempre (JSON 403 si
    la petición es AJAX). Nunca un 404 ni un 500.
    """
    for capacidad, destino in DESTINOS:
        if puede(request.user, capacidad):
            return redirect(destino)
    # Inalcanzable: `@requiere` ya exigió al menos una de las cuatro.
    return redirect("core:inicio")
