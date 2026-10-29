"""Piezas comunes de los buscadores de personas del modal de alta rápida.

Las usan el buscador de territoriales de Becas (``territoriales.py``) y el de agentes de
relevamiento de Dispositivos (``programas/services/inspecciones.py``): el filtro por texto y
el enmascarado de DNI y correo viven acá una sola vez, sin importar ningún programa.

* Nombre y apellido: coincidencia parcial. DNI y correo: **solo exactos**, para que el
  buscador no sirva para barrer el padrón de a pedazos.
"""

from django.db.models import Q

from core.dni import normalizar_dni

MIN_CARACTERES = 3
TOPE_RESULTADOS = 10
SIN_NOMBRE = "(sin nombre)"


def filtrar_por_texto(universo, texto):
    """DNI exacto si son solo dígitos, correo exacto si lleva ``@``, si no nombre parcial."""
    if "@" in texto:
        return universo.filter(email__iexact=texto)
    if all(ch.isdigit() or ch in ". " for ch in texto) and any(ch.isdigit() for ch in texto):
        return universo.filter(profile__dni=normalizar_dni(texto))
    for palabra in texto.split():
        universo = universo.filter(Q(first_name__icontains=palabra) | Q(last_name__icontains=palabra))
    return universo


def formatear_dni(dni):
    if not dni or not dni.isdigit():
        return dni or ""
    return f"{int(dni):,}".replace(",", ".")


def enmascarar_dni(dni):
    """``12345678`` → ``12.***.678``."""
    if not dni:
        return ""
    if len(dni) < 6:  # regla-dni: ok solo decide el enmascarado, no valida
        return "***"
    return f"{dni[:2]}.***.{dni[-3:]}"


def enmascarar_correo(email):
    """``carla@dominio.gob.ar`` → ``c***@dominio.gob.ar``."""
    if not email:
        return ""
    local, arroba, dominio = email.partition("@")
    if not arroba:
        return "***"
    return f"{local[:1]}***@{dominio}"


def nombre_para_mostrar(usuario):
    """El nombre completo; nunca el ``username``."""
    return usuario.get_full_name().strip() or SIN_NOMBRE
