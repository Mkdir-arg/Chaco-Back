"""Prepara identidades sintéticas para la campaña HTTP efímera de #262/#264."""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Prepara únicamente usuarios sintéticos para perf_http_probe en MySQL efímero."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Contraseña local de las identidades sintéticas.")
        parser.add_argument("--workers", type=int, default=8, help="Identidades de concurrencia a preparar.")

    @staticmethod
    def _assert_ephemeral_ci():
        database_name = str(connection.settings_dict.get("NAME") or "")
        if (
            os.environ.get("PERFORMANCE_CI") != "1"
            or os.environ.get("ENVIRONMENT") != "ci"
            or connection.vendor != "mysql"
            or database_name != "chaco_perf_ci"
        ):
            raise CommandError("prepare_perf_http_probe sólo puede correr en el MySQL efímero chaco_perf_ci.")

    def handle(self, *args, **options):
        self._assert_ephemeral_ci()
        if options["workers"] < 1:
            raise CommandError("--workers debe ser mayor que cero.")
        from core.management.commands.seed_perf import Command as SeedCommand
        from users.models import Profile

        SeedCommand().handle(scale=200)
        user_model = get_user_model()
        admin = user_model.objects.get(username="perf_admin")
        names = ["perf_admin", "perf_ciudadano", "perf262_api"]
        names.extend(f"perf262_conc_{index}" for index in range(options["workers"]))
        for name in names:
            user = (
                user_model.objects.get(username=name)
                if name in {"perf_admin", "perf_ciudadano"}
                else user_model.objects.create_user(name)
            )
            if name.startswith("perf262_"):
                user.is_staff = True
                user.groups.set(admin.groups.all())
            user.set_password(options["password"])
            user.is_active = True
            user.save(update_fields=["password", "is_active", "is_staff"])
            Profile.objects.get_or_create(user=user)
        self.stdout.write(self.style.SUCCESS(f"Preparadas {len(names)} identidades sintéticas."))
