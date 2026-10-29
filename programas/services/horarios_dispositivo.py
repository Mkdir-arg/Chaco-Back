"""Horario de atención del dispositivo: franjas por día y su resumen en texto (P3).

El legajo guarda las franjas en `HorarioDispositivo` y conserva `Dispositivo.horarios` como
**resumen derivado** («Lunes 09:00–12:00 y 13:00–18:00 · Martes 15:00–16:00»), que es lo que
leen el detalle (P4) y el padrón importado. Un texto que vino del padrón antes de que
existieran las franjas no se pisa hasta que se carga la primera.

Las reglas viven acá y no en el formulario: el form las usa para pintar el error al lado
de la franja, y `reemplazar_franjas` las vuelve a exigir antes de escribir.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import time

from django.core.exceptions import ValidationError
from django.db import transaction

#: Tope de franjas por día. Una institución con más cortes que esto en un mismo día está
#: describiendo turnos de trabajo, que son otra cosa (`Turno`, bitácora).
MAX_FRANJAS_POR_DIA = 4

MENSAJE_FIN_ANTERIOR = "La hora «Hasta» tiene que ser posterior a «Desde»."
MENSAJE_TOPE_POR_DIA = f"Un día admite hasta {MAX_FRANJAS_POR_DIA} franjas."


@dataclass(frozen=True, order=True)
class Franja:
    dia: int
    desde: time
    hasta: time


def _dias():
    from programas.models import HorarioDispositivo

    return dict(HorarioDispositivo.Dia.choices)


def _hora(valor):
    return f"{valor:%H:%M}"


def errores_de_franjas(franjas):
    """Lo que está mal en una lista de franjas, como `(posición, campo, mensaje)`.

    La posición es la de la franja en la lista recibida, para que el formulario pinte el
    error en su fila. Dos franjas del mismo día que solo se tocan (12:00 / 12:00) no se
    superponen.
    """
    dias = _dias()
    errores = []
    por_dia = defaultdict(list)
    for posicion, franja in enumerate(franjas):
        if franja.dia not in dias:
            errores.append((posicion, "dia", "Elegí un día de la semana."))
        elif franja.desde >= franja.hasta:
            errores.append((posicion, "hora_hasta", MENSAJE_FIN_ANTERIOR))
        else:
            por_dia[franja.dia].append((posicion, franja))
    for dia, del_dia in por_dia.items():
        del_dia.sort(key=lambda item: (item[1].desde, item[1].hasta))
        # Contra la que termina más tarde de las anteriores, no solo contra la previa:
        # 09–18, 10–11 y 12–13 superponen la tercera con la primera.
        mayor = del_dia[0][1]
        for posicion, franja in del_dia[1:]:
            if franja.desde < mayor.hasta:
                errores.append(
                    (
                        posicion,
                        "hora_desde",
                        f"Se superpone con la franja del {dias[dia].lower()} "
                        f"de {_hora(mayor.desde)} a {_hora(mayor.hasta)}.",
                    )
                )
            if franja.hasta > mayor.hasta:
                mayor = franja
        for posicion, _franja in del_dia[MAX_FRANJAS_POR_DIA:]:
            errores.append((posicion, "dia", MENSAJE_TOPE_POR_DIA))
    return sorted(errores)


def validar_franjas(franjas):
    errores = errores_de_franjas(franjas)
    if errores:
        raise ValidationError([mensaje for _posicion, _campo, mensaje in errores])


def resumen_de_franjas(franjas):
    """El texto de `Dispositivo.horarios`: un día por bloque, en orden de lunes a domingo."""
    dias = _dias()
    por_dia = defaultdict(list)
    for franja in sorted(franjas):
        por_dia[franja.dia].append(f"{_hora(franja.desde)}–{_hora(franja.hasta)}")
    partes = []
    for dia, rangos in sorted(por_dia.items()):
        texto = rangos[0] if len(rangos) == 1 else f"{', '.join(rangos[:-1])} y {rangos[-1]}"
        partes.append(f"{dias[dia]} {texto}")
    return " · ".join(partes)


def franjas_del_dispositivo(dispositivo):
    """Las franjas guardadas, en una sola lectura."""
    if not dispositivo.pk:
        return []
    return [
        Franja(dia, desde, hasta)
        for dia, desde, hasta in dispositivo.franjas_horarias.order_by("dia", "hora_desde").values_list(
            "dia", "hora_desde", "hora_hasta"
        )
    ]


def reemplazar_franjas(dispositivo, franjas):
    """Deja el dispositivo con exactamente estas franjas y su resumen en `horarios`.

    Corre dentro del guardado del legajo (la vista ya abrió la transacción y, en la
    edición, bloqueó la fila del dispositivo). Si el conjunto no cambió no escribe nada.
    Devuelve `{"anterior", "nuevo"}` del texto de `horarios` si cambió, para la traza.

    Sin franjas, el texto depende de dónde venía: si el dispositivo tenía franjas, el
    texto era el resumen y queda vacío; si no tenía, es un horario cargado antes de las
    franjas (padrón, versión anterior del formulario) y se conserva.
    """
    from programas.models import HorarioDispositivo

    if franjas is None:
        # El POST no trajo el bloque de franjas: no se tocan, ni ellas ni su resumen.
        return None
    franjas = sorted(franjas)
    validar_franjas(franjas)
    with transaction.atomic():
        actuales = franjas_del_dispositivo(dispositivo)
        if actuales != franjas:
            dispositivo.franjas_horarias.all().delete()
            HorarioDispositivo.objects.bulk_create(
                HorarioDispositivo(dispositivo=dispositivo, dia=f.dia, hora_desde=f.desde, hora_hasta=f.hasta)
                for f in franjas
            )
        if franjas:
            nuevo = resumen_de_franjas(franjas)
        elif actuales:
            nuevo = ""
        else:
            nuevo = dispositivo.horarios
        anterior = dispositivo.horarios
        if nuevo == anterior:
            return None
        dispositivo.horarios = nuevo
        dispositivo.save(update_fields=["horarios", "modificado"])
    return {"anterior": anterior, "nuevo": nuevo}
