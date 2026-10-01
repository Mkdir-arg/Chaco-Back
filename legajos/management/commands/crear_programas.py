"""Comando idempotente que garantiza los programas base (hoy, solo Becas).

Corre en cada arranque del contenedor, después de ``seed_datos_base``. Solo **crea**
el Programa Becas si falta, identificándolo por ``codigo`` (único); si ya existe no le
toca nada, porque el estado, el nombre, el color y el orden se editan desde
Configuración → Programas (Cambio 104). Antes lo buscaba por ``tipo`` —que no es
único: un segundo programa de tipo Becas tiraba ``MultipleObjectsReturned`` y el
contenedor no arrancaba— y le volvía a imponer ``estado=ACTIVO`` en cada arranque.

Los datos con que nace salen de ``seed_becas.PROGRAMA_BECAS_DEFAULTS``: una sola fuente.
"""

from django.core.management.base import BaseCommand

from programas.management.commands.seed_becas import PROGRAMA_BECAS_CODIGO, PROGRAMA_BECAS_DEFAULTS
from programas.models import Programa


class Command(BaseCommand):
    help = "Garantiza los programas base (Becas): los crea si faltan y no toca los existentes."

    def handle(self, *args, **options):
        programa, created = Programa.objects.get_or_create(
            codigo=PROGRAMA_BECAS_CODIGO, defaults=PROGRAMA_BECAS_DEFAULTS
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Creado: {programa.nombre}"))
        else:
            self.stdout.write(f"· Ya existe: {programa.nombre} (no se modifica)")
