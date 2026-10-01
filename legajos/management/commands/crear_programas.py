"""Comando idempotente que garantiza los programas base (hoy, solo Becas).

Corre en cada arranque del contenedor, después de ``seed_datos_base``. Solo **crea**
el Programa Becas si falta, identificándolo por ``codigo`` (único); si ya existe no le
toca nada, porque el estado, el nombre, el color y el orden se editan desde
Configuración → Programas (Cambio 104). Antes lo buscaba por ``tipo`` —que no es
único: un segundo programa de tipo Becas tiraba ``MultipleObjectsReturned``— y le
volvía a imponer ``estado=ACTIVO`` en cada arranque.

Delega en ``seed_becas.asegurar_programa_becas``: una sola fuente para los datos con
que nace (``PROGRAMA_BECAS_DEFAULTS``) y para el caso inconsistente (un programa de
tipo Becas con otro código), que frena con ``CommandError`` en vez de duplicar.
"""

from django.core.management.base import BaseCommand

from programas.management.commands.seed_becas import PROGRAMA_BECAS_CODIGO, asegurar_programa_becas
from programas.models import Programa


class Command(BaseCommand):
    help = "Garantiza los programas base (Becas): los crea si faltan y no toca los existentes."

    def handle(self, *args, **options):
        existia = Programa.objects.filter(codigo=PROGRAMA_BECAS_CODIGO).exists()
        programa = asegurar_programa_becas()
        if existia:
            self.stdout.write(f"· Ya existe: {programa.nombre} (no se modifica)")
        else:
            self.stdout.write(self.style.SUCCESS(f"✓ Creado: {programa.nombre}"))
