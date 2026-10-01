"""SEC-29 / D-29 (auditoría oct-2026) — desactiva las cuentas de ciudadano del portal.

El portal ciudadano quedó apagado (``portal/urls.py`` ya no publica ``mi-perfil/*``),
pero las cuentas que creó el registro siguen existiendo y son credenciales válidas:
mientras la API acepte Basic auth, una de esas cuentas sigue sirviendo para entrar.

**Esto no va en una migración de datos a propósito** (decisión D-29): desactivar
usuarios es una operación sobre datos reales que tiene que decidir y ejecutar quien
opera la base, después de contar cuántas cuentas activas hay en producción (P-08).
Por eso el comando es explícito y su default es ``--dry-run``: sin ``--aplicar`` no
escribe nada.

    python manage.py desactivar_usuarios_portal              # solo cuenta
    python manage.py desactivar_usuarios_portal --aplicar    # desactiva

Un usuario que además pertenece a algún grupo de backoffice **no se toca**: es
alguien que opera el sistema y desactivarlo lo dejaría afuera.
"""

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand

from core.rbac import GRUPO_CIUDADANO_PORTAL


class Command(BaseCommand):
    LOTE = 1000

    help = (
        "Desactiva las cuentas del grupo 'Ciudadanos' del portal (SEC-29). "
        "Por defecto solo cuenta: hace falta --aplicar para escribir."
    )

    def add_arguments(self, parser):
        grupo = parser.add_mutually_exclusive_group()
        grupo.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo informa cuántas cuentas se desactivarían (comportamiento por defecto).",
        )
        grupo.add_argument(
            "--aplicar",
            action="store_true",
            help="Desactiva de verdad las cuentas (is_active=False).",
        )

    def handle(self, *args, **options):
        aplicar = options["aplicar"]

        # Solo las cuentas que son *únicamente* de portal: quien también tiene un
        # grupo de backoffice opera el sistema y se deja como está. exclude() sobre
        # una relación multivaluada descarta al usuario si alguno de sus grupos
        # entra en el subquery, que es exactamente lo que se busca acá.
        otros_grupos = Group.objects.exclude(name=GRUPO_CIUDADANO_PORTAL).values("name")
        candidatos = (
            User.objects.filter(is_active=True, groups__name=GRUPO_CIUDADANO_PORTAL)
            .exclude(is_superuser=True)
            .exclude(groups__name__in=otros_grupos)
            .distinct()
        )
        total = candidatos.count()

        if not aplicar:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] {total} cuenta(s) del grupo '{GRUPO_CIUDADANO_PORTAL}' quedarían desactivadas. "
                    "No se escribió nada: volvé a correrlo con --aplicar para hacerlo efectivo."
                )
            )
            return

        # Por lotes y sobre una lista de pks: el queryset tiene joins y distinct(), y
        # en PRD (MariaDB, read_timeout de 10 s) un UPDATE de golpe sobre miles de
        # filas es justo lo que no conviene mantener abierto.
        pks = list(candidatos.values_list("pk", flat=True))
        desactivadas = 0
        for inicio in range(0, len(pks), self.LOTE):
            desactivadas += User.objects.filter(pk__in=pks[inicio : inicio + self.LOTE]).update(is_active=False)
        self.stdout.write(
            self.style.SUCCESS(
                f"{desactivadas} cuenta(s) del grupo '{GRUPO_CIUDADANO_PORTAL}' quedaron desactivadas (is_active=False)."
            )
        )
