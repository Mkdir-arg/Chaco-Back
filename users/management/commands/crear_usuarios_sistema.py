from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crear usuarios del sistema con contraseñas correctas"

    def handle(self, *args, **options):
        # Crear superusuario admin
        if not User.objects.filter(username="admin").exists():
            admin = User.objects.create_superuser(
                username="admin",
                email="admin@sisoc.gov.ar",
                password="admin123",
                first_name="Administrador",
                last_name="Principal",
            )
            self.stdout.write(self.style.SUCCESS("✅ Superusuario admin creado"))
        else:
            admin = User.objects.get(username="admin")
            admin.set_password("admin123")
            admin.save()
            self.stdout.write(self.style.WARNING("⚠️ Contraseña de admin actualizada"))

        # Crear grupos si no existen
        grupos = ["Administrador", "Responsable", "Operador", "Supervisor", "Consulta"]
        for grupo_name in grupos:
            grupo, created = Group.objects.get_or_create(name=grupo_name)
            if created:
                self.stdout.write(f"✅ Grupo {grupo_name} creado")

        # Usuarios administradores
        admin_group = Group.objects.get(name="Administrador")
        for i in range(1, 4):
            username = f"admin{i}"
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@sisoc.gov.ar",
                    password="admin123",
                    first_name=f"Admin{i}",
                    last_name="Usuario",
                    is_staff=True,
                )
                user.groups.add(admin_group)
                self.stdout.write(f"✅ Usuario {username} creado")
            else:
                user = User.objects.get(username=username)
                user.set_password("admin123")
                user.save()
                self.stdout.write(f"⚠️ Contraseña de {username} actualizada")

        # Usuarios responsables
        resp_group = Group.objects.get(name="Responsable")
        for i in range(1, 4):
            username = f"resp{i}"
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@sisoc.gov.ar",
                    password="resp123",
                    first_name=f"Responsable{i}",
                    last_name="Usuario",
                )
                user.groups.add(resp_group)
                self.stdout.write(f"✅ Usuario {username} creado")
            else:
                user = User.objects.get(username=username)
                user.set_password("resp123")
                user.save()
                self.stdout.write(f"⚠️ Contraseña de {username} actualizada")

        self.stdout.write(self.style.SUCCESS("\n🎉 Usuarios del sistema creados/actualizados correctamente"))
        self.stdout.write("📊 CREDENCIALES:")
        self.stdout.write("👤 admin / admin123")
        self.stdout.write("👥 admin1, admin2, admin3 / admin123")
        self.stdout.write("🎯 resp1, resp2, resp3 / resp123")
