"""Seed demo local para la app mobile de Becas.

Crea una estructura similar al mockup de Programa Becas:
- preguntas comunes del cuestionario social;
- segmentos, subsegmentos, convocatorias y requisitos especificos;
- 10 relevamientos asignados al usuario territorial de prueba;
- algunos formularios cargados para ver personas dentro del relevamiento.
"""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from programas.models import (
    Convocatoria,
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
)

COMMON_QUESTIONS = [
    ("Apellido y nombre", TipoCampo.STRING, None),
    ("DNI", TipoCampo.STRING, None),
    ("Fecha de nacimiento", TipoCampo.DATE, None),
    ("Sexo", TipoCampo.SELECTOR, ["Femenino", "Masculino", "X"]),
    ("Domicilio", TipoCampo.STRING, None),
    ("Localidad", TipoCampo.STRING, None),
    ("Telefono de contacto", TipoCampo.STRING, None),
    ("Correo electronico", TipoCampo.STRING, None),
    ("Estado civil", TipoCampo.SELECTOR, ["Soltero/a", "Casado/a", "Union convivencial", "Separado/a", "Viudo/a"]),
    ("Composicion del grupo familiar", TipoCampo.STRING, None),
    ("Situacion habitacional", TipoCampo.SELECTOR, ["Propia", "Alquilada", "Prestada", "Vivienda familiar", "Otra"]),
    ("Ingreso mensual del hogar", TipoCampo.INT, None),
    ("Cobertura de salud", TipoCampo.SELECTOR, ["Hospital publico", "Obra social", "Prepaga", "Otra"]),
]


SEGMENTOS = [
    {
        "nombre": "Produccion Territorial / Fuego y Barro",
        "descripcion": "Productores de ladrillo y carbon vegetal del territorio provincial.",
        "cupo": 500,
        "requiere_gps": True,
        "requisitos": [
            ("Lugar de trabajo / produccion", TipoCampo.STRING, None, True),
            ("Fotos del lugar", TipoCampo.ARCHIVO, None, True),
        ],
        "subsegmentos": [
            {
                "nombre": "Ladrillo",
                "cupo": 200,
                "requisitos": [
                    ("Cantidad de hornos", TipoCampo.INT, None, True),
                    ("Tipo de horno", TipoCampo.SELECTOR, ["Adobe", "Campana", "Intermitente"], False),
                ],
            },
            {
                "nombre": "Carbon",
                "cupo": 300,
                "requisitos": [
                    ("Metodo de produccion", TipoCampo.SELECTOR, ["Horno tradicional", "Parva", "Mixto"], True),
                ],
            },
        ],
    },
    {
        "nombre": "Nivel Superior",
        "descripcion": "Terciario y universitario, instituciones publicas y privadas.",
        "cupo": 1500,
        "requiere_gps": False,
        "requisitos": [
            ("Certificado de alumno regular", TipoCampo.ARCHIVO, None, True),
            ("Promedio del ultimo periodo", TipoCampo.INT, None, True),
            ("Institucion educativa", TipoCampo.STRING, None, True),
            ("Anio que cursa", TipoCampo.SELECTOR, ["1", "2", "3", "4", "5", "6"], True),
            ("Percibe otra beca", TipoCampo.SELECTOR, ["Si", "No"], False),
            ("Constancia de CBU", TipoCampo.ARCHIVO, None, True),
        ],
        "subsegmentos": [
            {"nombre": "Terciario", "cupo": 700, "requisitos": []},
            {
                "nombre": "Universitario",
                "cupo": 800,
                "requisitos": [("Carrera / Especialidad", TipoCampo.STRING, None, True)],
            },
        ],
    },
    {
        "nombre": "Nivel Secundario",
        "descripcion": "Estudiantes de escuelas secundarias de la provincia.",
        "cupo": 2000,
        "requiere_gps": False,
        "requisitos": [("Constancia de inscripcion", TipoCampo.ARCHIVO, None, True)],
        "subsegmentos": [
            {"nombre": "Ciclo Basico", "cupo": 1000, "requisitos": []},
            {"nombre": "Ciclo Orientado", "cupo": 1000, "requisitos": []},
        ],
    },
]


RELEVAMIENTOS = [
    (
        "Convocatoria Becas 2026 - Carbon",
        "Produccion Territorial / Fuego y Barro",
        "Carbon",
        "Resistencia - Zona Norte",
        0,
        Relevamiento.Estado.ASIGNADO,
        "Acceso por camino vecinal; coordinar con referente local.",
    ),
    (
        "Convocatoria Becas 2026 - Carbon",
        "Produccion Territorial / Fuego y Barro",
        "Carbon",
        "Pcia. Roque Saenz Pena",
        1,
        Relevamiento.Estado.EN_CURSO,
        "Operativo con referentes barriales.",
    ),
    (
        "Convocatoria Becas 2026 - Carbon",
        "Produccion Territorial / Fuego y Barro",
        "Carbon",
        "Villa Angela",
        2,
        Relevamiento.Estado.ASIGNADO,
        "Operativo conjunto con Desarrollo Social.",
    ),
    (
        "Convocatoria Becas 2026 - Ladrillo",
        "Produccion Territorial / Fuego y Barro",
        "Ladrillo",
        "Charata",
        3,
        Relevamiento.Estado.ASIGNADO,
        "Productores ladrilleros zona oeste.",
    ),
    (
        "Convocatoria Becas 2026 - Ladrillo",
        "Produccion Territorial / Fuego y Barro",
        "Ladrillo",
        "Quitilipi",
        4,
        Relevamiento.Estado.EN_CURSO,
        "Relevar predios productivos familiares.",
    ),
    (
        "Becas Superior 2026 - Universitario",
        "Nivel Superior",
        "Universitario",
        "Resistencia - Centro",
        0,
        Relevamiento.Estado.ASIGNADO,
        "Instituciones universitarias del microcentro.",
    ),
    (
        "Becas Superior 2026 - Universitario",
        "Nivel Superior",
        "Universitario",
        "Barranqueras",
        1,
        Relevamiento.Estado.EN_CURSO,
        "Turno tarde con estudiantes universitarios.",
    ),
    (
        "Becas Superior 2026 - Terciario",
        "Nivel Superior",
        "Terciario",
        "Fontana",
        2,
        Relevamiento.Estado.ASIGNADO,
        "Institutos terciarios y anexos.",
    ),
    (
        "Becas Secundario 2026 - Ciclo Basico",
        "Nivel Secundario",
        "Ciclo Basico",
        "General San Martin",
        3,
        Relevamiento.Estado.ASIGNADO,
        "Escuelas secundarias de ciclo basico.",
    ),
    (
        "Becas Secundario 2026 - Ciclo Orientado",
        "Nivel Secundario",
        "Ciclo Orientado",
        "Machagai",
        4,
        Relevamiento.Estado.ASIGNADO,
        "Escuelas secundarias de ciclo orientado.",
    ),
]


PERSONAS = [
    ("12345678", "Juan", "Perez"),
    ("23456789", "Marta", "Gimenez"),
    ("34567890", "Ramon", "Acosta"),
    ("45678901", "Lucia", "Sosa"),
    ("56789012", "Pedro", "Maidana"),
    ("67890123", "Ana", "Benitez"),
    ("78901234", "Diego", "Cabrera"),
    ("89012345", "Sofia", "Ledesma"),
]


def asegurar_preguntas_comunes():
    for index, (texto, tipo, opciones) in enumerate(COMMON_QUESTIONS, start=1):
        PreguntaGlobal.objects.update_or_create(
            texto=texto,
            defaults={
                "tipo": tipo,
                "opciones": opciones,
                "activo": True,
                "obligatorio": True,
                "orden": index,
            },
        )


def asegurar_requisito(segmento, subsegmento, orden, item):
    texto, tipo, opciones, obligatorio = item
    RequisitoNativo.objects.update_or_create(
        texto=texto,
        segmento=segmento,
        subsegmento=subsegmento,
        defaults={
            "tipo": tipo,
            "opciones": opciones,
            "orden": orden,
            "obligatorio": obligatorio,
        },
    )


def asegurar_segmentos():
    segmentos = {}
    subsegmentos = {}
    for cfg in SEGMENTOS:
        segmento, _ = Segmento.objects.update_or_create(
            nombre=cfg["nombre"],
            defaults={
                "descripcion": cfg["descripcion"],
                "cupo_maximo": cfg["cupo"],
                "requiere_gps": cfg["requiere_gps"],
                "activo": True,
            },
        )
        segmentos[segmento.nombre] = segmento
        for orden, requisito in enumerate(cfg["requisitos"], start=1):
            asegurar_requisito(segmento, None, orden, requisito)
        for sub_cfg in cfg["subsegmentos"]:
            sub, _ = Subsegmento.objects.update_or_create(
                segmento=segmento,
                nombre=sub_cfg["nombre"],
                defaults={"cupo_maximo": sub_cfg["cupo"]},
            )
            subsegmentos[(segmento.nombre, sub.nombre)] = sub
            for orden, requisito in enumerate(sub_cfg["requisitos"], start=100):
                asegurar_requisito(segmento, sub, orden, requisito)
    return segmentos, subsegmentos


def convocatoria_fechas(nombre):
    if "Carbon" in nombre:
        return date(2026, 3, 1), date(2026, 4, 30)
    if "Ladrillo" in nombre:
        return date(2026, 4, 1), date(2026, 5, 20)
    if "Superior" in nombre:
        return date(2026, 3, 1), date(2026, 5, 15)
    return date(2026, 3, 15), date(2026, 6, 15)


def asegurar_convocatorias(segmentos, subsegmentos):
    convocatorias = {}
    usados = set((nombre, segmento, sub) for nombre, segmento, sub, *_ in RELEVAMIENTOS)
    for nombre, segmento_nombre, subsegmento_nombre in usados:
        desde, hasta = convocatoria_fechas(nombre)
        segmento = segmentos[segmento_nombre]
        subsegmento = subsegmentos[(segmento_nombre, subsegmento_nombre)]
        convocatoria, _ = Convocatoria.objects.update_or_create(
            nombre=nombre,
            defaults={
                "segmento": segmento,
                "subsegmento": subsegmento,
                "fecha_inicio": desde,
                "fecha_fin": hasta,
                "descripcion": f"Demo local para app mobile: {nombre}.",
                "activo": True,
            },
        )
        convocatorias[nombre] = convocatoria
    return convocatorias


def asegurar_territorial(username, segmento=None):
    User = get_user_model()
    territorial, created = User.objects.get_or_create(username=username, defaults={"is_active": True})
    if created:
        territorial.set_password("terri123")
        territorial.save(update_fields=["password"])

    group = Group.objects.filter(name__icontains="Becas").filter(name__icontains="Territorial").first()
    if group:
        territorial.groups.add(group)
    if segmento is not None:
        # Un territorial → un segmento (obligatorio con el rol); el demo usa el principal.
        from programas.models import AsignacionTerritorial

        AsignacionTerritorial.objects.update_or_create(territorial=territorial, defaults={"segmento": segmento})
    return territorial


def asegurar_relevamientos(convocatorias, territorial):
    base_date = timezone.localdate()
    relevamientos = []
    for nombre_conv, _segmento, _subsegmento, zona, offset, estado, observaciones in RELEVAMIENTOS:
        rel, _ = Relevamiento.objects.update_or_create(
            convocatoria=convocatorias[nombre_conv],
            territorial=territorial,
            zona=zona,
            defaults={
                "fecha_asignada": base_date + timedelta(days=offset),
                "estado": estado,
                "observaciones": observaciones,
                "fecha_finalizado": None,
            },
        )
        relevamientos.append(rel)
    return relevamientos


def asegurar_formularios(relevamientos, territorial):
    persona_index = 0
    for rel_index, rel in enumerate(relevamientos[:6]):
        cantidad = rel_index % 3
        for _ in range(cantidad):
            dni, nombre, apellido = PERSONAS[persona_index % len(PERSONAS)]
            persona_index += 1
            payload = {
                "estado": Formulario.Estado.ENVIADO,
                "validado_renaper": rel_index % 2 == 0,
                "celular": f"3624{dni[-6:]}",
                "email_contacto": f"{nombre.lower()}.{apellido.lower()}@demo.local",
                "datos_identificacion": {
                    "dni": dni,
                    "nombre": nombre,
                    "apellido": apellido,
                    "fecha_nacimiento": "1998-04-12",
                    "origen": "seed_demo_mobile",
                },
                "data": {
                    "globales": {
                        "Composicion del grupo familiar": "4 integrantes",
                        "Situacion habitacional": "Vivienda familiar",
                        "Ingreso mensual del hogar": 410000,
                        "Cobertura de salud": "Hospital publico",
                    },
                    "requisitos": {},
                },
                "created_by": territorial,
            }
            formulario = Formulario.objects.filter(
                relevamiento=rel,
                datos_identificacion__dni=dni,
            ).first()
            if formulario:
                for field, value in payload.items():
                    setattr(formulario, field, value)
                formulario.save()
            else:
                Formulario.objects.create(relevamiento=rel, **payload)


class Command(BaseCommand):
    help = "Carga datos demo de Becas para probar la app mobile con relevamientos asignados."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("seed_becas", verbosity=0)
        asegurar_preguntas_comunes()
        segmentos, subsegmentos = asegurar_segmentos()
        convocatorias = asegurar_convocatorias(segmentos, subsegmentos)
        territorial = asegurar_territorial("terri", segmento=segmentos.get("Produccion Territorial / Fuego y Barro"))
        relevamientos = asegurar_relevamientos(convocatorias, territorial)
        asegurar_formularios(relevamientos, territorial)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed demo mobile Becas completo: {len(relevamientos)} relevamientos asignados a {territorial.username}."
            )
        )
