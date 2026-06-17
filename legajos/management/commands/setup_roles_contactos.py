from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from legajos.models.contactos import HistorialContacto, VinculoFamiliar


class Command(BaseCommand):
    help = "Configura grupos y permisos para el sistema de contactos activo."

    def handle(self, *args, **options):
        roles = [
            "Psicologo",
            "Psiquiatra",
            "Medico",
            "Trabajador Social",
            "Operador Socioterapeutico",
            "Coordinador",
            "Director",
            "Enfermero",
            "Terapista Ocupacional",
            "Abogado",
        ]

        for rol in roles:
            group, created = Group.objects.get_or_create(name=rol)
            self.stdout.write(f"Grupo {'creado' if created else 'existente'}: {rol}")

        modelos_contactos = [HistorialContacto, VinculoFamiliar]
        grupos_con_acceso = [
            "Coordinador",
            "Director",
            "Psicologo",
            "Trabajador Social",
            "Operador Socioterapeutico",
        ]

        for modelo in modelos_contactos:
            content_type = ContentType.objects.get_for_model(modelo)
            for permiso in ("view", "add", "change"):
                perm_codename = f"{permiso}_{modelo._meta.model_name}"
                try:
                    permission = Permission.objects.get(
                        codename=perm_codename,
                        content_type=content_type,
                    )
                except Permission.DoesNotExist:
                    self.stdout.write(f"Permiso no encontrado: {perm_codename}")
                    continue

                for grupo_nombre in grupos_con_acceso:
                    Group.objects.get(name=grupo_nombre).permissions.add(permission)

        permisos_delete = Permission.objects.filter(
            codename__startswith="delete_",
            content_type__in=[ContentType.objects.get_for_model(m) for m in modelos_contactos],
        )

        for grupo_nombre in ["Coordinador", "Director"]:
            grupo = Group.objects.get(name=grupo_nombre)
            for permiso in permisos_delete:
                grupo.permissions.add(permiso)

        self.stdout.write(self.style.SUCCESS("Configuracion de roles y permisos completada"))
