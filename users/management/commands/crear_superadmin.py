from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Crea el superusuario admin si no existe"

    def handle(self, *args, **options):
        username = "admin"
        password = "mkdir123"

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'✓ Superusuario "{username}" ya existe'))
        else:
            User.objects.create_superuser(username=username, password=password, email="admin@sistema.com")
            self.stdout.write(self.style.SUCCESS(f'✓ Superusuario "{username}" creado exitosamente'))
