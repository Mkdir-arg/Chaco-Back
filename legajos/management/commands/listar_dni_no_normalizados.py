"""G1c-08 / P-17 · Qué DNI de Legajos están fuera de la regla única.

Desde este cambio ninguna puerta deja entrar un `12.345.678` ni un documento de 6 o 9
dígitos, pero las fichas que ya están cargadas así siguen ahí. Son dos problemas
distintos y el comando cuenta los dos por separado:

* **Con separadores** (`12.345.678`): cada una puede tener una **gemela** normalizada —
  la misma persona partida en dos legajos, que Becas (que normaliza) nunca encuentra—.
* **Con un largo fuera de la regla** (`core.dni.LARGOS_DNI_VALIDOS`): son las que este
  PR frena. Un caso de Becas cuyo ciudadano tenga uno de estos DNI deja de informarse a
  SIIS y queda con «El caso no tiene un ciudadano con DNI válido». Es el número que hay
  que mirar **antes del deploy**.

El comando es de **solo lectura a propósito**: unir dos legajos es mover adjuntos,
alertas, historial, inscripciones y casos de Becas, y cuál de los dos sobrevive no lo
puede decidir un script. Lo que hace es dejar la lista para que la revise el área, que
es lo que pide P-17 del plan de la auditoría.

La salida de pantalla **enmascara el documento** —alcanza para reconocer la ficha y el
id para abrirla—; el CSV lo trae entero, porque es el insumo con el que se cruzan las
fichas, y se maneja como cualquier otro export con datos personales.

    manage.py listar_dni_no_normalizados            # tabla legible, documento enmascarado
    manage.py listar_dni_no_normalizados --csv      # para pegar en una planilla
"""

import csv

from django.core.management.base import BaseCommand
from django.db.models import Q

from core.dni import LARGOS_DNI_VALIDOS, dni_valido, normalizar_dni
from legajos.models import Ciudadano

COLUMNAS = ("id", "dni_guardado", "dni_normalizado", "apellido", "nombre", "colisiona_con", "motivo")

MOTIVO_SEPARADORES = "separadores"
MOTIVO_LARGO = "largo"


def enmascarar(dni):
    """`12.345.678` → `12.***.678`: se reconoce la ficha sin imprimir el documento."""
    texto = str(dni or "")
    if len(texto) <= 4:
        return "*" * len(texto)
    return f"{texto[:2]}{'*' * (len(texto) - 4)}{texto[-2:]}"


def motivos(guardado):
    """Por qué esta ficha está fuera de la regla: puede ser por los dos."""
    limpio = normalizar_dni(guardado)
    encontrados = []
    if limpio != str(guardado or ""):
        encontrados.append(MOTIVO_SEPARADORES)
    if not dni_valido(limpio):
        encontrados.append(MOTIVO_LARGO)
    return encontrados


class Command(BaseCommand):
    help = "Lista los ciudadanos cuyo DNI está fuera de la regla única y sus posibles duplicados."

    def add_arguments(self, parser):
        parser.add_argument("--csv", action="store_true", help="Salida en CSV, con el documento completo.")

    def handle(self, *args, **opciones):
        # Dos filtros: lo que tiene algo que no es un dígito y lo que, siendo todo
        # dígitos, no mide 7 u 8. El segundo es el que el barrido anterior no veía.
        largos = Q()
        for largo in LARGOS_DNI_VALIDOS:
            largos |= Q(dni__regex=r"^[0-9]{%d}$" % largo)
        candidatos = Ciudadano.objects.exclude(largos).order_by("dni").values("id", "dni", "apellido", "nombre")

        filas = []
        for fila in candidatos:
            razones = motivos(fila["dni"])
            if not razones:
                continue
            filas.append(
                {
                    "id": fila["id"],
                    "dni_guardado": fila["dni"],
                    "dni_normalizado": normalizar_dni(fila["dni"]),
                    "apellido": fila["apellido"],
                    "nombre": fila["nombre"],
                    "colisiona_con": "",
                    "motivo": "+".join(razones),
                }
            )

        if not filas:
            self.stdout.write(self.style.SUCCESS("Ningún DNI fuera de la regla única."))
            return

        normalizados = {fila["dni_normalizado"] for fila in filas} - {""}
        gemelos = dict(Ciudadano.objects.filter(dni__in=normalizados).values_list("dni", "id"))
        for fila in filas:
            gemelo = gemelos.get(fila["dni_normalizado"])
            if gemelo and gemelo != fila["id"]:
                fila["colisiona_con"] = gemelo

        if opciones["csv"]:
            escritor = csv.DictWriter(self.stdout, fieldnames=COLUMNAS, lineterminator="\n")
            escritor.writeheader()
            escritor.writerows(filas)
            return

        for fila in filas:
            marca = f" -> colisiona con el ciudadano {fila['colisiona_con']}" if fila["colisiona_con"] else ""
            self.stdout.write(
                f"{fila['id']}\t{enmascarar(fila['dni_guardado'])}\t[{fila['motivo']}]\t"
                f"{fila['apellido']}, {fila['nombre']}{marca}"
            )

        con_separadores = sum(1 for fila in filas if MOTIVO_SEPARADORES in fila["motivo"])
        con_largo = sum(1 for fila in filas if MOTIVO_LARGO in fila["motivo"])
        colisiones = sum(1 for fila in filas if fila["colisiona_con"])
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"{len(filas)} DNI fuera de la regla única: {con_separadores} con separadores "
                f"({colisiones} con una ficha normalizada ya existente) y "
                f"{con_largo} con un largo fuera de {LARGOS_DNI_VALIDOS}. "
                "Los del segundo grupo son los que dejan de informarse a SIIS. "
                "La unificación es manual (P-17): este comando no toca nada."
            )
        )
