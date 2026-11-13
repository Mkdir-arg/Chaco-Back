"""Comando idempotente que garantiza los programas base (Becas y Emergencia).

Corre en cada arranque del contenedor, después de ``seed_datos_base``. Solo **crea**
el Programa Becas si falta, identificándolo por ``codigo`` (único); si ya existe no le
toca nada, porque el estado, el nombre, el color y el orden se editan desde
Configuración → Programas (Cambio 104). Antes lo buscaba por ``tipo`` —que no es
único: un segundo programa de tipo Becas tiraba ``MultipleObjectsReturned``— y le
volvía a imponer ``estado=ACTIVO`` en cada arranque.

Delega en ``seed_becas.asegurar_programa_becas``: una sola fuente para los datos con
que nace (``PROGRAMA_BECAS_DEFAULTS``) y para el caso inconsistente (un programa de
tipo Becas con otro código), que frena con ``CommandError`` en vez de duplicar.

Emergencia sigue la misma regla con ``seed_emergencia.asegurar_programa_emergencia``:
crea el programa EMERGENCIA y su fila de SLA si faltan, y no pisa lo configurado.
"""

from django.core.management.base import BaseCommand

from programas.management.commands.seed_becas import PROGRAMA_BECAS_CODIGO, asegurar_programa_becas
from programas.management.commands.seed_emergencia import asegurar_programa_emergencia
from programas.models import Programa


class Command(BaseCommand):
    help = "Garantiza los programas base (Becas y Emergencia): los crea si faltan y no toca los existentes."

    def handle(self, *args, **options):
        existia = Programa.objects.filter(codigo=PROGRAMA_BECAS_CODIGO).exists()
        programa = asegurar_programa_becas()
        if existia:
            self.stdout.write(f"· Ya existe: {programa.nombre} (no se modifica)")
        else:
            self.stdout.write(self.style.SUCCESS(f"✓ Creado: {programa.nombre}"))

        emergencia, creado, _sla_creada = asegurar_programa_emergencia()
        if creado:
            self.stdout.write(self.style.SUCCESS(f"✓ Creado: {emergencia.nombre}"))
        else:
            self.stdout.write(f"· Ya existe: {emergencia.nombre} (no se modifica)")
