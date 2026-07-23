from django.db import migrations

PROGRAMAS = (
    {
        "codigo": "DISPOSITIVOS",
        "nombre": "Dispositivos",
        "tipo": "DISPOSITIVOS",
        "descripcion": "Programa de dispositivos institucionales, admisiones y estadías.",
        "icono": "apartment",
        "color": "#2563eb",
        "orden": 20,
    },
    {
        "codigo": "MERENDEROS",
        "nombre": "Merenderos",
        "tipo": "MERENDEROS",
        "descripcion": "Programa de merenderos y prestaciones alimentarias.",
        "icono": "restaurant",
        "color": "#ea580c",
        "orden": 21,
    },
)


def crear_programas(apps, schema_editor):
    Programa = apps.get_model("programas", "Programa")

    for datos in PROGRAMAS:
        esperados = {
            "nombre": datos["nombre"],
            "tipo": datos["tipo"],
            "naturaleza": "PERSISTENTE",
            "estado": "ACTIVO",
        }
        existente = Programa.objects.filter(codigo=datos["codigo"]).first()
        if existente:
            incompatibles = [
                campo for campo, valor_esperado in esperados.items() if getattr(existente, campo) != valor_esperado
            ]
            if incompatibles:
                raise RuntimeError(
                    f'Programa(codigo="{datos["codigo"]}") ya existe con datos incompatibles: '
                    f"{', '.join(incompatibles)}."
                )
            continue

        conflicto = Programa.objects.filter(nombre=datos["nombre"]).exclude(codigo=datos["codigo"]).first()
        if conflicto:
            raise RuntimeError(
                f'No se puede crear Programa(codigo="{datos["codigo"]}"): '
                f'el nombre "{datos["nombre"]}" pertenece al código "{conflicto.codigo}".'
            )

        defaults = {
            **datos,
            "naturaleza": "PERSISTENTE",
            "estado": "ACTIVO",
        }
        codigo = defaults.pop("codigo")
        Programa.objects.create(codigo=codigo, **defaults)


class Migration(migrations.Migration):
    dependencies = [
        ("programas", "0011_merenderos_modelos_base"),
    ]

    operations = [
        migrations.RunPython(crear_programas, reverse_code=migrations.RunPython.noop),
    ]
