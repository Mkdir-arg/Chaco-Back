"""Carga los centroides de las localidades del Chaco en ``core.UbicacionLocalidad``.

    python manage.py cargar_ubicaciones_localidades             # carga y reporta
    python manage.py cargar_ubicaciones_localidades --simular   # reporta sin escribir

Lee ``core/data/localidades_chaco_georef.csv`` (BAHRA/Georef) y concilia por nombre y
municipio normalizados contra las localidades de la provincia operativa (ver
``core.services.ubicaciones_localidades``). Es idempotente: correrlo otra vez con el
mismo CSV no crea ni cambia filas. Imprime el reporte de conciliación: las ambiguas con
sus candidatos y las no conciliadas, que quedan sin punto en el mapa.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.selectors.geografia import localidades_operativas
from core.services.ubicaciones_localidades import RUTA_CSV, cargar_ubicaciones, leer_csv


def _lugar(localidad, conservadas):
    municipio = localidad.municipio.nombre if localidad.municipio else "sin municipio"
    texto = f"{localidad.nombre} — municipio {municipio} (id {localidad.pk})"
    if localidad.pk in conservadas:
        texto += f" · conserva ubicación anterior (id_fuente {conservadas[localidad.pk]})"
    return texto


def _orden(localidad):
    return (localidad.municipio.nombre if localidad.municipio else "", localidad.nombre, localidad.pk)


class Command(BaseCommand):
    help = "Carga los centroides de localidades desde el CSV versionado de BAHRA/Georef."

    def add_arguments(self, parser):
        parser.add_argument("--archivo", default=str(RUTA_CSV), help="CSV a leer (por defecto, el versionado).")
        parser.add_argument("--simular", action="store_true", help="Concilia y reporta sin escribir en la base.")

    def handle(self, *args, **opciones):
        try:
            filas = leer_csv(opciones["archivo"])
        except (FileNotFoundError, ValueError) as error:
            raise CommandError(str(error)) from error

        localidades = list(localidades_operativas())
        with transaction.atomic():
            resultado = cargar_ubicaciones(localidades, filas)
            if opciones["simular"]:
                transaction.set_rollback(True)

        c = resultado.conciliacion
        prefijo = "[simulación] " if opciones["simular"] else ""
        self.stdout.write(
            f"{prefijo}Localidades del catálogo: {len(localidades)} · filas del CSV: {len(filas)}\n"
            f"Conciliadas: {len(c.asignadas)} (creadas {resultado.creadas}, actualizadas "
            f"{resultado.actualizadas}, sin cambios {resultado.sin_cambios})\n"
            f"Ambiguas: {len(c.ambiguas)} · No conciliadas: {len(c.no_conciliadas)}"
        )
        ambiguas = sorted(c.ambiguas, key=lambda par: _orden(par[0]))
        if ambiguas:
            self.stdout.write(
                "\nAmbiguas (no se asignan; sin punto en el mapa salvo que conserven una ubicación anterior):"
            )
            for localidad, candidatas in ambiguas:
                opciones_csv = "; ".join(
                    f"{f.id_fuente} {f.nombre} / {f.municipio} / {f.departamento}" for f in candidatas
                )
                self.stdout.write(f"  - {_lugar(localidad, resultado.conservadas)} · candidatos: {opciones_csv}")
        if c.no_conciliadas:
            self.stdout.write("\nNo conciliadas (sin punto en el mapa salvo que conserven una ubicación anterior):")
            for localidad in sorted(c.no_conciliadas, key=_orden):
                self.stdout.write(f"  - {_lugar(localidad, resultado.conservadas)}")
