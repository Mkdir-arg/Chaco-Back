from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from conversaciones.services import AsignadorAutomatico, MetricasService


class Command(BaseCommand):
    help = "Configura el sistema de conversaciones con operadores y métricas"

    def add_arguments(self, parser):
        parser.add_argument("--operadores", nargs="+", help="Lista de usernames de operadores a configurar")
        parser.add_argument(
            "--max-conversaciones", type=int, default=5, help="Máximo de conversaciones por operador (default: 5)"
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Configurando sistema de conversaciones...")

        # Crear grupos si no existen
        grupos_creados = self.crear_grupos()

        # Configurar operadores
        operadores_configurados = self.configurar_operadores(
            options.get("operadores", []), options["max_conversaciones"]
        )

        # Actualizar métricas
        self.actualizar_metricas()

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Sistema configurado exitosamente:\n"
                f"   - Grupos creados: {grupos_creados}\n"
                f"   - Operadores configurados: {operadores_configurados}\n"
                f"   - Métricas actualizadas"
            )
        )

    def crear_grupos(self):
        """Crea los grupos necesarios para conversaciones"""
        grupos = ["Conversaciones", "OperadorCharla"]
        creados = 0

        for nombre_grupo in grupos:
            grupo, created = Group.objects.get_or_create(name=nombre_grupo)
            if created:
                creados += 1
                self.stdout.write(f"   ✓ Grupo creado: {nombre_grupo}")
            else:
                self.stdout.write(f"   - Grupo existente: {nombre_grupo}")

        return creados

    def configurar_operadores(self, usernames, max_conversaciones):
        """Configura operadores en el sistema de cola"""
        configurados = 0

        if not usernames:
            # Si no se especifican operadores, configurar todos los del grupo
            operadores = User.objects.filter(groups__name__in=["Conversaciones", "OperadorCharla"]).distinct()
        else:
            # Configurar operadores específicos
            operadores = User.objects.filter(username__in=usernames)

        for operador in operadores:
            # Agregar al grupo si no está
            grupo_conversaciones, _ = Group.objects.get_or_create(name="Conversaciones")
            if not operador.groups.filter(name="Conversaciones").exists():
                operador.groups.add(grupo_conversaciones)
                self.stdout.write(f"   ✓ Usuario {operador.username} agregado al grupo Conversaciones")

            # Configurar en la cola
            cola = AsignadorAutomatico.configurar_operador(operador, max_conversaciones, activo=True)

            configurados += 1
            self.stdout.write(
                f"   ✓ Operador configurado: {operador.username} "
                f"(max: {cola.max_conversaciones}, activo: {cola.activo})"
            )

        return configurados

    def actualizar_metricas(self):
        """Actualiza todas las métricas del sistema"""
        try:
            # Actualizar métricas de operadores
            MetricasService.actualizar_todas_las_metricas()

            # Actualizar contadores de cola
            AsignadorAutomatico.actualizar_todas_las_colas()

            self.stdout.write("   ✓ Métricas actualizadas")

        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠ Error al actualizar métricas: {e}"))
