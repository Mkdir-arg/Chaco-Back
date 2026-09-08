from django.core.management.base import BaseCommand

from legajos.models import Ciudadano

PERSONAS = [
    ("Ana", "Acosta"),
    ("Bruno", "Benítez"),
    ("Carla", "Cáceres"),
    ("Diego", "Domínguez"),
    ("Elena", "Escobar"),
    ("Facundo", "Fernández"),
    ("Gabriela", "Gómez"),
    ("Hugo", "Herrera"),
    ("Inés", "Ibarra"),
    ("Javier", "Juárez"),
    ("Karina", "López"),
    ("Lucas", "Martínez"),
    ("Mariana", "Núñez"),
    ("Nicolás", "Ortiz"),
    ("Olga", "Pérez"),
    ("Pablo", "Quiroga"),
    ("Rocío", "Ramírez"),
    ("Sergio", "Sánchez"),
    ("Tamara", "Torres"),
    ("Ulises", "Valdez"),
    ("Valeria", "Vega"),
    ("Walter", "Zárate"),
    ("Ximena", "Almirón"),
    ("Yanina", "Bustamante"),
    ("Zoe", "Cardozo"),
]


class Command(BaseCommand):
    help = "Crea ciudadanos locales para probar el límite del desplegable de búsqueda."

    def handle(self, *args, **options):
        for numero, (nombre, apellido) in enumerate(PERSONAS, start=1):
            Ciudadano.objects.update_or_create(
                dni=f"31530{numero:03d}",
                defaults={"nombre": nombre, "apellido": apellido, "genero": "X", "activo": True},
            )
        self.stdout.write(self.style.SUCCESS(f"{len(PERSONAS)} ciudadanos creados. Buscar por DNI: 31530"))
