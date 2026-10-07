"""G1c-08 / P-17 · Qué DNI de Legajos tienen caracteres que no son dígitos.

Desde este cambio ninguna puerta deja entrar un `12.345.678`, pero las fichas que ya
están cargadas así siguen ahí, y cada una puede tener una **gemela** normalizada: la
misma persona partida en dos legajos, que Becas (que normaliza) nunca encuentra.

El comando es de **solo lectura a propósito**: unir dos legajos es mover adjuntos,
alertas, historial, inscripciones y casos de Becas, y cuál de los dos sobrevive no lo
puede decidir un script. Lo que hace es dejar la lista para que la revise el área, que
es lo que pide P-17 del plan de la auditoría.

    manage.py listar_dni_no_normalizados            # tabla legible
    manage.py listar_dni_no_normalizados --csv      # para pegar en una planilla
"""

import csv

from django.core.management.base import BaseCommand

from core.dni import dni_valido, normalizar_dni
from legajos.models import Ciudadano

COLUMNAS = ("id", "dni_guardado", "dni_normalizado", "apellido", "nombre", "colisiona_con", "largo_valido")


class Command(BaseCommand):
    help = "Lista los ciudadanos cuyo DNI tiene caracteres no numéricos y sus posibles duplicados."

    def add_arguments(self, parser):
        parser.add_argument("--csv", action="store_true", help="Salida en CSV por stdout.")

    def handle(self, *args, **opciones):
        sucios = list(
            Ciudadano.objects.filter(dni__regex=r"[^0-9]").order_by("dni").values("id", "dni", "apellido", "nombre")
        )
        if not sucios:
            self.stdout.write(self.style.SUCCESS("Ningún DNI con caracteres no numéricos."))
            return

        normalizados = {normalizar_dni(fila["dni"]) for fila in sucios}
        gemelos = dict(
            Ciudadano.objects.filter(dni__in=normalizados - {""}).values_list("dni", "id"),
        )

        filas = []
        for fila in sucios:
            limpio = normalizar_dni(fila["dni"])
            filas.append(
                {
                    "id": fila["id"],
                    "dni_guardado": fila["dni"],
                    "dni_normalizado": limpio,
                    "apellido": fila["apellido"],
                    "nombre": fila["nombre"],
                    "colisiona_con": gemelos.get(limpio, ""),
                    "largo_valido": "si" if dni_valido(limpio) else "no",
                }
            )

        if opciones["csv"]:
            escritor = csv.DictWriter(self.stdout, fieldnames=COLUMNAS, lineterminator="\n")
            escritor.writeheader()
            escritor.writerows(filas)
            return

        colisiones = sum(1 for fila in filas if fila["colisiona_con"])
        for fila in filas:
            marca = f" -> colisiona con el ciudadano {fila['colisiona_con']}" if fila["colisiona_con"] else ""
            self.stdout.write(
                f"{fila['id']}\t{fila['dni_guardado']!r} -> {fila['dni_normalizado']}\t"
                f"{fila['apellido']}, {fila['nombre']}{marca}"
            )
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                f"{len(filas)} DNI sin normalizar, {colisiones} con una ficha normalizada ya existente. "
                "La unificación es manual (P-17): este comando no toca nada."
            )
        )
