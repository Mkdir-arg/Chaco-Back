"""Siembra el catálogo protegido en las bases que ya existían (Cambio 58).

Los grupos Datos personales, Contacto y Apoderado y sus campos vinculados al
legajo los creaba solo ``seed_becas``. Desde la fase 4 el formulario del portal
se arma **desde el catálogo**: sin estos campos no se pediría la identidad, el
contacto ni el apoderado. Esta migración los deja sembrados aunque nadie corra
el comando en el deploy.

Es un **snapshot**: la lista de acá es la que valía al escribir la migración y
no se toca aunque el catálogo cambie después. Idempotente — la identidad de un
campo protegido es ``(origen, vinculo)``, y lo que el operador haya renombrado,
movido o reordenado no se pisa.
"""

from django.db import migrations

CONDICION_APODERADO = {
    "modo": "todas",
    "reglas": [{"fuente": "legajo:fecha_nacimiento", "op": "edad_menor", "valor": 18}],
}

# (clave, nombre, subtítulo, orden, condición, [(origen, vínculo, etiqueta, obligatorio)])
CATALOGO_PROTEGIDO = [
    (
        "datos_personales",
        "Datos personales",
        "Tomamos estos datos de tu identificación.",
        0,
        None,
        [
            ("legajo", "nombre", "Nombre", True),
            ("legajo", "apellido", "Apellido", True),
            ("legajo", "dni", "DNI", True),
            ("legajo", "fecha_nacimiento", "Fecha de nacimiento", True),
            ("legajo", "genero", "Sexo", True),
        ],
    ),
    (
        "contacto",
        "Contacto",
        "",
        1,
        None,
        [
            ("legajo", "telefono", "Celular", True),
            ("legajo", "email", "Correo electrónico", False),
        ],
    ),
    (
        "apoderado",
        "Apoderado",
        "Como sos menor de 18, necesitamos los datos de un adulto responsable.",
        2,
        CONDICION_APODERADO,
        [
            ("persona_vinculada", "nombre", "Nombre del apoderado", True),
            ("persona_vinculada", "apellido", "Apellido del apoderado", True),
            ("persona_vinculada", "dni", "DNI del apoderado", True),
            ("persona_vinculada", "genero", "Sexo del apoderado", False),
            ("persona_vinculada", "fecha_nacimiento", "Fecha de nacimiento del apoderado", False),
        ],
    ),
]
GRUPO_CUESTIONARIO = ("cuestionario", "Cuestionario social", "", 10)

# Tipo y opciones de cada vínculo: los dicta el legajo, no el operador (RN-4).
# Mismo valor que `VINCULOS_LEGAJO`: `None` en los que no son selector (no `[]`,
# para que la fila quede idéntica a la que siembra `seed_becas`).
TIPOS = {
    "nombre": ("STRING", None),
    "apellido": ("STRING", None),
    "dni": ("STRING", None),
    "fecha_nacimiento": ("DATE", None),
    "genero": ("SELECTOR", ["F", "M"]),
    "telefono": ("STRING", None),
    "email": ("STRING", None),
}


def sembrar(apps, schema_editor):
    Grupo = apps.get_model("programas", "GrupoRequisito")
    Pregunta = apps.get_model("programas", "PreguntaGlobal")

    ordenes_usados = set(Pregunta.objects.values_list("orden", flat=True))

    def orden_libre(desde):
        while desde in ordenes_usados:
            desde += 1
        ordenes_usados.add(desde)
        return desde

    for clave, nombre, subtitulo, orden, condicion, campos in CATALOGO_PROTEGIDO:
        grupo, _ = Grupo.objects.get_or_create(
            clave=clave,
            defaults={
                "nombre": nombre,
                "subtitulo": subtitulo,
                "orden": orden,
                "protegido": True,
                "condicion_defecto": condicion,
            },
        )
        if not grupo.protegido:
            grupo.protegido = True
            grupo.save(update_fields=["protegido", "modificado"])
        for indice, (origen, vinculo, etiqueta, obligatorio) in enumerate(campos):
            tipo, opciones = TIPOS[vinculo]
            Pregunta.objects.get_or_create(
                origen=origen,
                vinculo=vinculo,
                defaults={
                    "texto": etiqueta,
                    "tipo": tipo,
                    "opciones": opciones,
                    "grupo": grupo,
                    "protegido": True,
                    "obligatorio": obligatorio,
                    "activo": True,
                    "canal": "ambos",
                    # Desde 1000: el rango bajo queda para lo que carga el operador.
                    "orden": orden_libre(1000 + orden * 10 + indice + 1),
                },
            )

    clave, nombre, subtitulo, orden = GRUPO_CUESTIONARIO
    cuestionario, _ = Grupo.objects.get_or_create(
        clave=clave, defaults={"nombre": nombre, "subtitulo": subtitulo, "orden": orden}
    )
    Pregunta.objects.filter(grupo__isnull=True).update(grupo=cuestionario)


def revertir(apps, schema_editor):
    """No borra nada: los campos pueden tener respuestas asociadas."""


class Migration(migrations.Migration):
    dependencies = [("programas", "0059_formulario_respuestas_definicion")]

    operations = [migrations.RunPython(sembrar, revertir)]
