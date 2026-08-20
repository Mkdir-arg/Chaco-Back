from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from users.models import Profile


class Command(BaseCommand):
    help = "Verifica y repara usuarios con problemas de grupos o perfiles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reparar",
            action="store_true",
            help="Repara automáticamente los problemas encontrados",
        )
        parser.add_argument(
            "--usuario",
            type=str,
            help="Verifica un usuario específico",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("=== VERIFICACIÓN DE USUARIOS ==="))

        if options["usuario"]:
            self.verificar_usuario_especifico(options["usuario"], options["reparar"])
        else:
            self.verificar_todos_usuarios(options["reparar"])

    def verificar_usuario_especifico(self, username, reparar):
        try:
            usuario = User.objects.get(username=username)
            self.mostrar_info_usuario(usuario)

            if reparar:
                self.reparar_usuario(usuario)

        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Usuario "{username}" no encontrado'))

    def verificar_todos_usuarios(self, reparar):
        # select_related + annotate: evita el N+1 de perfil y de groups.count().
        usuarios = list(User.objects.select_related("profile").annotate(n_groups=Count("groups")))
        self.stdout.write(f"Total de usuarios: {len(usuarios)}")

        problemas = 0

        for usuario in usuarios:
            tiene_problemas = False

            # Verificar perfil
            try:
                usuario.profile
            except Profile.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Usuario {usuario.username}: Sin perfil"))
                tiene_problemas = True
                if reparar:
                    Profile.objects.create(user=usuario)
                    self.stdout.write(self.style.SUCCESS(f"  → Perfil creado para {usuario.username}"))

            # Verificar grupos (n_groups anotado en la query)
            if usuario.n_groups == 0 and not usuario.is_superuser:
                self.stdout.write(self.style.WARNING(f"Usuario {usuario.username}: Sin grupos asignados"))
                tiene_problemas = True

            if tiene_problemas:
                problemas += 1

        if problemas == 0:
            self.stdout.write(self.style.SUCCESS("No se encontraron problemas"))
        else:
            self.stdout.write(self.style.WARNING(f"Se encontraron {problemas} usuarios con problemas"))

    def mostrar_info_usuario(self, usuario):
        self.stdout.write(f"\n--- Usuario: {usuario.username} ---")
        self.stdout.write(f"Email: {usuario.email}")
        self.stdout.write(f"Nombre: {usuario.first_name} {usuario.last_name}")
        self.stdout.write(f"Activo: {usuario.is_active}")

        # Grupos
        grupos = usuario.groups.all()
        if grupos:
            self.stdout.write(f"Grupos: {', '.join([g.name for g in grupos])}")
        else:
            self.stdout.write(self.style.WARNING("Grupos: Ninguno"))

        # Perfil
        try:
            usuario.profile
            self.stdout.write("Perfil: OK")
        except Profile.DoesNotExist:
            self.stdout.write(self.style.ERROR("Perfil: No existe"))

    def reparar_usuario(self, usuario):
        with transaction.atomic():
            # Crear perfil si no existe
            perfil, created = Profile.objects.get_or_create(user=usuario)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Perfil creado para {usuario.username}"))
