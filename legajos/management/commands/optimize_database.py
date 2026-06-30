from django.core.management.base import BaseCommand

from core.performance.database_partitioning import DatabasePartitioner


class Command(BaseCommand):
    help = "Optimiza la base de datos creando particiones y archivando datos antiguos"

    def add_arguments(self, parser):
        parser.add_argument("--create-partitions", action="store_true")
        parser.add_argument("--archive-old-data", action="store_true")
        parser.add_argument("--months-ahead", type=int, default=3)
        parser.add_argument("--months-old", type=int, default=12)

    def handle(self, *args, **options):
        if options["create_partitions"]:
            self.stdout.write("Creando particiones...")
            DatabasePartitioner.create_monthly_partitions(options["months_ahead"])
            self.stdout.write(self.style.SUCCESS("Particiones creadas"))

        if options["archive_old_data"]:
            self.stdout.write("Archivando datos antiguos...")
            DatabasePartitioner.archive_old_data(options["months_old"])
            self.stdout.write(self.style.SUCCESS("Datos archivados"))
