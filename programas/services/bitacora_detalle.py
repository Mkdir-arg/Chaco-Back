"""Datos de la pantalla «Detalle de una novedad» de la bitácora (Cambio 427).

La vista decide quién entra (``dispositivo.ver`` con alcance al dispositivo, igual que la
bitácora) y si el usuario puede **nombrar** personas (``ciudadano.ver``). Acá solo se arma
lo que se dibuja: el texto completo, las personas, los adjuntos y la cadena de versiones.

* **Los archivos van por ``/media/``** (``core.views.media``): esa vista resuelve el
  adjunto por su ruta y exige ``dispositivo.ver`` sobre **su** dispositivo. No hay una URL
  pública ni un segundo camino para bajarlos: acá solo se arma el enlace.
* **Las personas se nombran, y se enlazan a su legajo, solo con ``ciudadano.ver``** (la
  regla del Cambio 271). Sin ella se dice cuántas son y el nombre no llega al template.
* **Costo constante:** la cadena de versiones con sus personas y adjuntos son tres
  consultas, sin importar cuántas versiones o adjuntos haya.
"""

from pathlib import Path

from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone

from programas.models import EntradaBitacora, Estadia

#: Las extensiones que el navegador dibuja en un `<img>`; el resto se ofrece para descargar.
EXTENSIONES_IMAGEN = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp"})


def _autor(usuario) -> str:
    return usuario.get_full_name() or usuario.get_username()


def _fecha_hora(momento) -> str:
    return timezone.localtime(momento).strftime("%d/%m/%Y %H:%M")


def _plural(cantidad, singular, plural):
    return f"{cantidad} {singular if cantidad == 1 else plural}"


def es_imagen(adjunto) -> bool:
    return Path((adjunto.archivo.name or "").lower()).suffix in EXTENSIONES_IMAGEN


def adjuntos_de(entrada) -> list[dict]:
    """Los adjuntos de una entrada como `{nombre, url, imagen}` (de `prefetch_related("adjuntos")`)."""

    return [
        {"nombre": str(adjunto), "url": adjunto.archivo.url, "imagen": es_imagen(adjunto)}
        for adjunto in entrada.adjuntos.all()
    ]


def _personas(entrada, *, nombrar_personas: bool) -> list[dict]:
    if not nombrar_personas:
        return []
    return [
        {
            "nombre": estadia.ciudadano.apellido_nombre,
            "url_legajo": reverse("legajos:ciudadano_detalle", args=[estadia.ciudadano_id]),
        }
        for estadia in entrada.personas.all()
    ]


def _personas_prefetch(nombrar_personas: bool):
    estadias = Estadia.objects.only("id", "ciudadano_id")
    if nombrar_personas:
        estadias = Estadia.objects.select_related("ciudadano").only(
            "id", "ciudadano", "ciudadano__nombre", "ciudadano__apellido"
        )
    return Prefetch("personas", queryset=estadias)


def detalle_entrada(entrada, *, nombrar_personas: bool) -> dict:
    """Todo lo que dibuja el detalle de `entrada` (una versión cualquiera de su cadena)."""

    versiones = list(
        entrada.versiones()
        .select_related("responsable", "turno")
        .prefetch_related(_personas_prefetch(nombrar_personas), "adjuntos")
        .order_by("version")
    )
    actual = next(version for version in versiones if version.pk == entrada.pk)
    vigente = versiones[-1]
    dispositivo_pk = entrada.dispositivo_id

    adjuntos = adjuntos_de(actual)
    cantidad_personas = len(actual.personas.all())
    cadena = [
        {
            "version": version.version,
            "autor": _autor(version.responsable),
            "fecha_hora": _fecha_hora(version.creado),
            "motivo": version.motivo_correccion,
            "texto": version.texto,
            "es_actual": version.pk == actual.pk,
            "vigente": version.pk == vigente.pk,
            "url": reverse("dispositivos:bitacora_entrada", args=[dispositivo_pk, version.pk]),
            "resumen": " · ".join(
                (
                    _plural(len(version.personas.all()), "persona", "personas"),
                    _plural(len(version.adjuntos.all()), "adjunto", "adjuntos"),
                )
            ),
        }
        for version in versiones
    ]
    url_bitacora = (
        reverse("dispositivos:bitacora", args=[dispositivo_pk])
        + f"?fecha={actual.fecha_operativa.isoformat()}&turno={actual.turno_id}"
    )
    return {
        "entrada": actual,
        "tipo_texto": actual.get_tipo_display(),
        "tono": EntradaBitacora.TONO_POR_TIPO.get(actual.tipo, ""),
        "momento_texto": _fecha_hora(actual.momento),
        "fecha_operativa_texto": actual.fecha_operativa.strftime("%d/%m/%Y"),
        "turno_texto": str(actual.turno),
        "autor": _autor(actual.responsable),
        "automatica": actual.origen == EntradaBitacora.Origen.AUTOMATICA,
        "corregida_el": _fecha_hora(actual.creado) if actual.version > 1 else "",
        "reemplazada": actual.pk != vigente.pk,
        "url_vigente": reverse("dispositivos:bitacora_entrada", args=[dispositivo_pk, vigente.pk]),
        "personas": _personas(actual, nombrar_personas=nombrar_personas),
        "cantidad_personas": cantidad_personas,
        "nombrar_personas": nombrar_personas,
        "imagenes": [
            {"url": adjunto["url"], "alt": f"Imagen adjunta: {adjunto['nombre']}", "rotulo": adjunto["nombre"]}
            for adjunto in adjuntos
            if adjunto["imagen"]
        ],
        "archivos": [adjunto for adjunto in adjuntos if not adjunto["imagen"]],
        "cantidad_adjuntos": len(adjuntos),
        "versiones": cadena,
        "url_bitacora": url_bitacora,
    }
