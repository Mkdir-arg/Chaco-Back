"""Carga inicial de tipos y campos F-00 aprobados en el análisis #128."""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from programas.models import CampoTipoDispositivo, TipoCampo, TipoDispositivo

SI_NO = ["Sí", "No"]
NIVELES_EDUCATIVOS = [
    "Sin instrucción",
    "Primario incompleto",
    "Primario completo",
    "Secundario incompleto",
    "Secundario completo",
    "Terciario / universitario",
    "Posgrado",
]


def campo(seccion, nombre, tipo_campo=TipoCampo.STRING, opciones=None):
    return {
        "seccion": seccion,
        "nombre": nombre,
        "tipo_campo": tipo_campo,
        "opciones": opciones,
        "obligatorio": False,
    }


CAMPOS_ADULTO_MAYOR = [
    campo("A. Educación y capacitación", "Nivel de instrucción", TipoCampo.SELECTOR, NIVELES_EDUCATIVOS),
    campo("A. Educación y capacitación", "Oficio"),
    campo("A. Educación y capacitación", "Capacitaciones (sí/no y cuáles)"),
    campo("A. Educación y capacitación", "Interés en formación (sí/no y cuál)"),
    campo("B. Situación laboral e ingresos", "Empleo", TipoCampo.SELECTOR, ["Formal", "Informal", "Sin empleo"]),
    campo("B. Situación laboral e ingresos", "Lugar de trabajo"),
    campo("B. Situación laboral e ingresos", "Ocupación"),
    campo("B. Situación laboral e ingresos", "Ingreso mensual", TipoCampo.INT),
    campo("B. Situación laboral e ingresos", "Plan social o beca (sí/no y cuál)"),
    campo("B. Situación laboral e ingresos", "Jubilación o pensión (sí/no y cuál)"),
    campo(
        "C. Situación institucional y habitacional",
        "Perfil de permanencia",
        TipoCampo.SELECTOR,
        ["Larga estadía", "Mediana estadía", "Tránsito-crítico"],
    ),
    campo("C. Situación institucional y habitacional", "Cantidad de años en la institución", TipoCampo.INT),
    campo(
        "C. Situación institucional y habitacional",
        "Requerimiento nutricional",
        TipoCampo.SELECTOR,
        ["General", "Adulto mayor", "Especial"],
    ),
    campo("C. Situación institucional y habitacional", "Mantiene relación familiar", TipoCampo.SELECTOR, SI_NO),
    campo("C. Situación institucional y habitacional", "Último domicilio"),
    campo("C. Situación institucional y habitacional", "Motivo de egreso del hogar"),
    campo("C. Situación institucional y habitacional", "Posee vivienda", TipoCampo.SELECTOR, SI_NO),
    campo("C. Situación institucional y habitacional", "Dónde duerme actualmente"),
    campo("C. Situación institucional y habitacional", "Observaciones"),
    campo(
        "D. Red de sostén",
        "Tipos de red",
        TipoCampo.SELECTOR_MULTIPLE,
        ["Parientes", "Institucional", "Vecinos", "ONG", "Iglesia", "Centro comunitario", "Gubernamental", "Otros"],
    ),
    campo("D. Red de sostén", "Detalle de la red de sostén"),
    campo("E. Grupo familiar", "Grupo familiar"),
    campo("F. Salud", "Grupo sanguíneo"),
    campo("F. Salud", "Tratamiento médico (sí/no y dónde)"),
    campo(
        "F. Salud",
        "Antecedentes y condiciones de salud",
        TipoCampo.SELECTOR_MULTIPLE,
        ["Tuberculosis", "Diabetes", "Cardíacos", "Respiratorios", "Salud mental", "Discapacidad", "ETS", "Otros"],
    ),
    campo("F. Salud", "Observaciones de salud"),
    campo("G. Egresos mensuales", "Alquiler", TipoCampo.INT),
    campo("G. Egresos mensuales", "Créditos", TipoCampo.INT),
    campo("G. Egresos mensuales", "Cuotas", TipoCampo.INT),
    campo("G. Egresos mensuales", "Medicamentos", TipoCampo.INT),
    campo("G. Egresos mensuales", "Transporte y otros", TipoCampo.INT),
    campo("I. Intereses", "Intereses"),
    campo(
        "J. Dependencia",
        "Grado de dependencia",
        TipoCampo.SELECTOR,
        ["Autoválido", "Semi-válido", "Postrado"],
    ),
]

CAMPOS_ABORDAJE = [
    campo("2. Reingreso", "Observaciones"),
    campo("2. Reingreso", "Observaciones ampliadas"),
    campo("3. Educación, trabajo e ingresos", "Nivel educativo", TipoCampo.SELECTOR, NIVELES_EDUCATIVOS),
    campo("3. Educación, trabajo e ingresos", "Capacitaciones"),
    campo("3. Educación, trabajo e ingresos", "Interés en formación"),
    campo("3. Educación, trabajo e ingresos", "Ocupación"),
    campo("3. Educación, trabajo e ingresos", "Lugar de trabajo"),
    campo("3. Educación, trabajo e ingresos", "Ingreso mensual", TipoCampo.INT),
    campo("3. Educación, trabajo e ingresos", "Empleo", TipoCampo.SELECTOR, ["Formal", "Informal"]),
    campo(
        "3. Educación, trabajo e ingresos",
        "Oficio",
        TipoCampo.SELECTOR_MULTIPLE,
        [
            "Carpintería",
            "Electricista",
            "Albañilería",
            "Soldador/a",
            "Mecánica",
            "Peluquería",
            "Jardinería",
            "Panadería",
            "Artesanía",
            "Otro",
        ],
    ),
    campo("3. Educación, trabajo e ingresos", "Ayuda económica externa (sí/no y monto)"),
    campo("3. Educación, trabajo e ingresos", "Plan social o beca (sí/no y cuál)"),
    campo("3. Educación, trabajo e ingresos", "Jubilación o pensión (sí/no y cuál)"),
    campo("4. Grupo familiar", "Grupo familiar"),
    campo("5. Historia familiar", "Mantiene relación con su familia", TipoCampo.SELECTOR, SI_NO),
    campo("5. Historia familiar", "Último domicilio"),
    campo("5. Historia familiar", "Motivo de egreso del hogar"),
    campo("5. Historia familiar", "Derivación o referencia"),
    campo("5. Historia familiar", "Historia familiar"),
    campo("6. Vivienda", "Posee vivienda", TipoCampo.SELECTOR, SI_NO),
    campo("6. Vivienda", "Condición de la vivienda", TipoCampo.SELECTOR, ["Propia", "Alquilada", "Prestada"]),
    campo("6. Vivienda", "Observaciones de vivienda"),
    campo("6. Vivienda", "Localidad o barrio"),
    campo("7. Ingresos, egresos y alimentación", "Ingreso total mensual", TipoCampo.INT),
    campo(
        "7. Ingresos, egresos y alimentación",
        "Ayuda alimentaria",
        TipoCampo.SELECTOR_MULTIPLE,
        ["Comedor", "Bolsa", "Trueque", "Otro"],
    ),
    campo("7. Ingresos, egresos y alimentación", "Alquiler", TipoCampo.INT),
    campo("7. Ingresos, egresos y alimentación", "Medicamentos", TipoCampo.INT),
    campo("7. Ingresos, egresos y alimentación", "Transporte", TipoCampo.INT),
    campo("7. Ingresos, egresos y alimentación", "Créditos", TipoCampo.INT),
    campo("7. Ingresos, egresos y alimentación", "Otros egresos", TipoCampo.INT),
    campo(
        "8. Red de sostén",
        "Tipos de red",
        TipoCampo.SELECTOR_MULTIPLE,
        ["Familiares", "Vecinos", "Iglesia", "Centro comunitario", "Estado", "Otros"],
    ),
    campo("8. Red de sostén", "Detalle y referentes"),
    campo("9. Salud", "Cobertura de salud", TipoCampo.SELECTOR, SI_NO),
    campo("9. Salud", "Número de afiliado"),
    campo("9. Salud", "Problema, enfermedad, tratamiento y medicación"),
    campo(
        "9. Salud",
        "Problemas de salud",
        TipoCampo.SELECTOR_MULTIPLE,
        ["Diabetes", "Cardíacos", "Respiratorios", "Salud mental", "Discapacidad", "Otros"],
    ),
    campo(
        "10. Condición funcional",
        "Condición funcional",
        TipoCampo.SELECTOR,
        ["Autoválido", "Semi-válido", "Postrado"],
    ),
    campo(
        "11. Comidas",
        "Régimen alimentario",
        TipoCampo.SELECTOR_MULTIPLE,
        ["Normal", "Dieta blanda", "Baja en sodio", "Baja en azúcar", "Vegetariana/Vegana", "Sin gluten"],
    ),
    campo("12. Consumo de sustancias", "Consume sustancias", TipoCampo.SELECTOR, SI_NO),
    campo("12. Consumo de sustancias", "Sustancias consumidas"),
    campo(
        "12. Consumo de sustancias",
        "Tipo de tratamiento",
        TipoCampo.SELECTOR,
        ["Ambulatorio", "Internación", "Otro"],
    ),
    campo("12. Consumo de sustancias", "Derivación"),
    campo(
        "13. Situaciones registradas",
        "Situaciones registradas",
        TipoCampo.SELECTOR_MULTIPLE,
        ["Violencia", "Adicciones", "Abandono", "Migración", "Enfermedad grave", "Muerte familiar", "Otros"],
    ),
    campo("13. Situaciones registradas", "Descripción breve"),
    campo(
        "14. Necesidades observadas",
        "Necesidades observadas",
        TipoCampo.SELECTOR_MULTIPLE,
        ["Hacinamiento", "Vivienda precaria", "Falta de agua", "Niños sin escuela", "Problemas de salud"],
    ),
]

CONFIGURACIONES = [
    {
        "codigo": "ADULTO_MAYOR",
        "nombre": "Adulto Mayor",
        "descripcion": "Dispositivo residencial para personas adultas mayores.",
        "maneja_camas": True,
        "campos": CAMPOS_ADULTO_MAYOR,
    },
    {
        "codigo": "ABORDAJE_PSICOSOCIAL",
        "nombre": "Abordaje Psicosocial",
        "descripcion": "Dispositivo de abordaje y acompañamiento psicosocial.",
        "maneja_camas": True,
        "campos": CAMPOS_ABORDAJE,
    },
]


class Command(BaseCommand):
    help = "Instala la configuración inicial de Adulto Mayor y Abordaje Psicosocial."

    @transaction.atomic
    def handle(self, *args, **options):
        if len(CAMPOS_ADULTO_MAYOR) != 33 or len(CAMPOS_ABORDAJE) != 45:
            raise CommandError("La definición versionada debe contener exactamente 33 y 45 campos.")

        creados = 0
        existentes = 0
        for definicion in CONFIGURACIONES:
            nombre_en_otro_codigo = (
                TipoDispositivo.objects.filter(nombre=definicion["nombre"]).exclude(codigo=definicion["codigo"]).first()
            )
            if nombre_en_otro_codigo is not None:
                raise CommandError(
                    f'El nombre "{definicion["nombre"]}" ya pertenece al código '
                    f"{nombre_en_otro_codigo.codigo}; no se sobrescribió configuración ajena."
                )
            tipo, _ = TipoDispositivo.objects.get_or_create(
                codigo=definicion["codigo"],
                defaults={
                    "nombre": definicion["nombre"],
                    "descripcion": definicion["descripcion"],
                    "maneja_camas": definicion["maneja_camas"],
                },
            )
            if tipo.nombre != definicion["nombre"]:
                raise CommandError(
                    f'El código {tipo.codigo} ya pertenece a "{tipo.nombre}"; no se sobrescribió configuración ajena.'
                )

            for orden, definicion_campo in enumerate(definicion["campos"], start=1):
                _, creado = CampoTipoDispositivo.objects.get_or_create(
                    tipo_dispositivo=tipo,
                    seccion=definicion_campo["seccion"],
                    nombre=definicion_campo["nombre"],
                    defaults={
                        "tipo_campo": definicion_campo["tipo_campo"],
                        "opciones": definicion_campo["opciones"],
                        "obligatorio": definicion_campo["obligatorio"],
                        "orden": orden,
                    },
                )
                creados += int(creado)
                existentes += int(not creado)

        self.stdout.write(
            self.style.SUCCESS(
                f"Configuración de Dispositivos lista: {creados} campos creados, {existentes} ya existentes."
            )
        )
