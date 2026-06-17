"""Comando idempotente para garantizar programas base en desarrollo local."""
from django.core.management.base import BaseCommand

from programas.models import Programa


class Command(BaseCommand):
    help = 'Garantiza el programa base ÑACHEC para el entorno local'

    def handle(self, *args, **options):
        programas_data = [
            {
                'codigo': 'ÑACHEC',
                'nombre': 'ÑACHEC',
                'tipo': 'ÑACHEC',
                'descripcion': 'Programa de ÑACHEC',
                'icono': 'shield-alt',
                'color': '#10B981',
                'orden': 1
            },
        ]

        created_count = 0
        updated_count = 0

        for data in programas_data:
            programa, created = Programa.objects.update_or_create(
                tipo=data['tipo'],
                defaults={
                    'codigo': data['codigo'],
                    'nombre': data['nombre'],
                    'descripcion': data['descripcion'],
                    'icono': data['icono'],
                    'color': data['color'],
                    'orden': data['orden'],
                    'estado': Programa.Estado.ACTIVO,
                    'naturaleza': Programa.Naturaleza.PERSISTENTE,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Creado: {programa.nombre}')
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Actualizado: {programa.nombre}')
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✓ Proceso completado: {created_count} creados, {updated_count} actualizados'
            )
        )
