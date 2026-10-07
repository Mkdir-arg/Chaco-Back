"""Contrato de `programas/models/__init__.py` (RED-46).

Un solo archivo de 3.252 líneas con los modelos de los **tres** productos (Becas,
Dispositivos, Merenderos) y 90 módulos que lo importan. `radon` le da índice de
mantenibilidad 0.00. Partirlo en `becas.py` / `dispositivos.py` / `merenderos.py` es
tentador y hoy no hay nada que lo cubra:

- un nombre que el `__init__.py` de compatibilidad **no re-exporte** no falla al
  importar el paquete: falla en runtime, en la pantalla que lo usa, el día que alguien
  entre;
- un modelo que cambie de app label rompe las migraciones de forma **irreversible** en
  producción, porque `django_migrations` y las tablas quedan con el label viejo.

Este módulo es el piso que vuelve seguro ese corte. No lo planifica ni lo pide: fija lo
que hay hoy para que el corte, cuando se decida, sea un movimiento de archivos y nada
más. Son tres contratos:

- **`ExportsTests`** — los nombres públicos que el paquete expone.
- **`AppLabelTests`** — app label y nombre de tabla de cada modelo.
- **`PropiedadesDeNegocioTests`** — las properties que no son datos sino reglas, con
  valores concretos: lo que un corte apurado se lleva puesto sin que nada lo marque.

Regla de este bloque de la auditoría: los tests van **antes** del refactor, y nunca en
el mismo PR que un cambio funcional.
"""

from datetime import date, datetime, time

from django.apps import apps
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

import programas.models as modelos_programas
from programas.models import (
    Convocatoria,
    Formulario,
    Relevamiento,
    Segmento,
    Subsegmento,
)

# Los 46 modelos de la app, con la tabla con la que viven hoy en la base. El mapa es
# literal a propósito: calcularlo desde `_meta` haría que el test se mueva solo y no
# detectaría nada. `AltaIntermediaSIIS` es la única con `db_table` explícita.
TABLAS = {
    "AdjuntoFormulario": "programas_adjuntoformulario",
    "Admision": "programas_admision",
    "AliasLocalidadSiis": "programas_aliaslocalidadsiis",
    "AltaIntermediaSIIS": "siis_tabla_intermedia",
    "ArchivoAdmision": "programas_archivoadmision",
    "AsignacionCoordinador": "programas_asignacioncoordinador",
    "AsignacionDispositivo": "programas_asignaciondispositivo",
    "AsignacionReferente": "programas_asignacionreferente",
    "AsignacionTerritorial": "programas_asignacionterritorial",
    "Cama": "programas_cama",
    "CampoTipoDispositivo": "programas_campotipodispositivo",
    "CatalogoSiisLocal": "programas_catalogosiislocal",
    "Convocatoria": "programas_convocatoria",
    "CorridaSiis": "programas_corridasiis",
    "CupoSegmento": "programas_cuposegmento",
    "DerivacionPrograma": "programas_derivacionprograma",
    "DisenoFormulario": "programas_disenoformulario",
    "Dispositivo": "programas_dispositivo",
    "EntregaMercaderia": "programas_entregamercaderia",
    "EnvioSIIS": "programas_enviosiis",
    "EsperaAdmision": "programas_esperaadmision",
    "Formulario": "programas_formulario",
    "GrupoRequisito": "programas_gruporequisito",
    "InscripcionPrograma": "programas_inscripcionprograma",
    "ItemDiseno": "programas_itemdiseno",
    "ListaEspera": "programas_listaespera",
    "LocalidadSiis": "programas_localidadsiis",
    "Merendero": "programas_merendero",
    "PadronHabilitado": "programas_padronhabilitado",
    "PreguntaGlobal": "programas_preguntaglobal",
    "PrestacionDiaria": "programas_prestaciondiaria",
    "PrestacionMensual": "programas_prestacionmensual",
    "Programa": "programas_programa",
    "ProgramaSiis": "programas_programasiis",
    "ProvinciaSiis": "programas_provinciasiis",
    "RegistroDiario": "programas_registrodiario",
    "RegistroPausa": "programas_registropausa",
    "Relevamiento": "programas_relevamiento",
    "RequisitoNativo": "programas_requisitonativo",
    "Segmento": "programas_segmento",
    "SolicitudMerendero": "programas_solicitudmerendero",
    "Subsegmento": "programas_subsegmento",
    "TipoDispositivo": "programas_tipodispositivo",
    "TracaFormulario": "programas_tracaformulario",
    "TrazaDispositivo": "programas_trazadispositivo",
    "ValidacionSIS": "programas_validacionsis",
}

# Lo que el paquete expone además de los modelos: mixins, querysets, managers, enums,
# constantes del dominio y `BloqueoSiis`, que es una clase plana (duck-type de
# `PausableMixin`, no un modelo). `Ciudadano`, `Group`, `User`, `Path`, `TimeStamped`,
# `ValidationError` y los dos validadores son **imports que se filtran** al namespace;
# hoy nadie los importa desde acá (se verificó sobre los 320 `from … import` del repo),
# así que un corte puede dejarlos afuera a propósito. Si este test se pone rojo por uno
# de ellos, la pregunta es si fue deliberado, no si hay que agregarlo de vuelta.
OTROS_NOMBRES_PUBLICOS = {
    "BloqueoSiis",
    "CARACTERES_SIN_TEXTO",
    "CanalFormulario",
    "Ciudadano",
    "Group",
    "MaxValueValidator",
    "MinValueValidator",
    "OrigenRequisito",
    "PadronHabilitadoQuerySet",
    "Path",
    "PausableMixin",
    "PresentacionCampo",
    "SIN_TEXTO_REGEX",
    "TimeStamped",
    "TipoCampo",
    "TrazaDispositivoManager",
    "TrazaDispositivoQuerySet",
    "User",
    "VINCULOS_LEGAJO",
    "ValidationError",
}

NOMBRES_PUBLICOS = set(TABLAS) | OTROS_NOMBRES_PUBLICOS


def _nombres_publicos_de_hoy():
    return {n for n in dir(modelos_programas) if n[:1].isupper() and not n.startswith("_")}


class ExportsTests(SimpleTestCase):
    def test_nombres_publicos_estables(self):
        actuales = _nombres_publicos_de_hoy()

        faltan = sorted(NOMBRES_PUBLICOS - actuales)
        self.assertEqual(
            faltan,
            [],
            "nombres que `programas.models` dejó de exponer: "
            f"{faltan}. Si el archivo se partió, el `__init__.py` de compatibilidad "
            "tiene que re-exportarlos; si no, el import no falla y el error aparece "
            "en runtime, en la pantalla que los usa.",
        )

    def test_los_nombres_nuevos_entran_a_la_lista(self):
        """La otra dirección: un modelo nuevo que nadie agregó acá. No es un error de
        producción, es un recordatorio de que el contrato se escribe a mano."""
        nuevos = sorted(_nombres_publicos_de_hoy() - NOMBRES_PUBLICOS)

        self.assertEqual(
            nuevos,
            [],
            f"nombres públicos nuevos en `programas.models` sin registrar acá: {nuevos}. "
            "Agregarlos a TABLAS (si son modelos) o a OTROS_NOMBRES_PUBLICOS.",
        )

    def test_cada_modelo_se_importa_por_su_nombre_desde_el_paquete(self):
        """`dir()` ve también lo que llegó por un `import *`; esto prueba el acceso real."""
        for nombre in sorted(TABLAS):
            with self.subTest(modelo=nombre):
                self.assertTrue(hasattr(modelos_programas, nombre))


class AppLabelTests(SimpleTestCase):
    def test_todos_los_modelos_siguen_en_programas(self):
        for nombre in sorted(TABLAS):
            with self.subTest(modelo=nombre):
                modelo = getattr(modelos_programas, nombre)
                self.assertEqual(
                    modelo._meta.app_label,
                    "programas",
                    f"{nombre} cambió de app label. Eso mueve la tabla y las filas de "
                    "`django_migrations`: en producción no se vuelve atrás.",
                )

    def test_ningun_modelo_cambia_de_tabla(self):
        for nombre, tabla in sorted(TABLAS.items()):
            with self.subTest(modelo=nombre):
                self.assertEqual(getattr(modelos_programas, nombre)._meta.db_table, tabla)

    def test_la_app_no_tiene_modelos_sin_registrar(self):
        vivos = {m.__name__ for m in apps.get_app_config("programas").get_models()}

        self.assertEqual(sorted(vivos), sorted(TABLAS))


class PropiedadesDeNegocioTests(TestCase):
    """Las properties del archivo son reglas de negocio, no accesos a campos.

    Un corte que las deje en la clase equivocada —o que pierda una herencia— devuelve
    números plausibles y distintos. Acá van con valores concretos.
    """

    @classmethod
    def setUpTestData(cls):
        # 10 de cupo con 7 repartidos: quedan 3 sin distribuir. Sin `programa`: ese
        # campo apunta a `ProgramaSiis`, no a `Programa` (la cadena de
        # `pausa_efectiva` del segmento termina en `None` y es lo que se quiere acá).
        cls.segmento = Segmento.objects.create(nombre="Seg contrato", cupo_maximo=10)
        Subsegmento.objects.create(segmento=cls.segmento, nombre="Sub A", cupo_maximo=3)
        Subsegmento.objects.create(segmento=cls.segmento, nombre="Sub B", cupo_maximo=4)
        cls.convocatoria = Convocatoria.objects.create(
            nombre="Conv contrato",
            segmento=cls.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        cls.relevamiento = Relevamiento.objects.create(
            convocatoria=cls.convocatoria,
            territorial=User.objects.create_user("terri_contrato", password="x"),
            fecha_asignada=timezone.make_aware(datetime(2026, 6, 1, 8, 0)),
            fecha_hasta=timezone.make_aware(datetime(2026, 6, 30, 20, 0)),
            zona="A",
            cupo_maximo=8,
        )
        for numero in range(6):
            Formulario.objects.create(
                relevamiento=cls.relevamiento,
                celular=f"362411000{numero}",
                estado=Formulario.Estado.APROBADO,
            )

    def test_segmento_cupo_disponible_es_lo_no_distribuido(self):
        self.assertEqual(self.segmento.cupo_distribuido, 7)
        self.assertEqual(self.segmento.cupo_disponible, 3)

    def test_relevamiento_cuenta_sus_casos_contra_su_propio_tope(self):
        self.assertEqual(self.relevamiento.cupo_utilizado, 6)
        self.assertEqual(self.relevamiento.cupo_disponible, 2)
        self.assertFalse(self.relevamiento.cupo_completo)

    def test_el_cupo_del_relevamiento_no_se_va_a_negativo(self):
        """`max(..., 0)`: con el tope pasado, «disponible» es 0 y «completo» es True."""
        self.relevamiento.cupo_maximo = 4

        self.assertEqual(self.relevamiento.cupo_disponible, 0)
        self.assertTrue(self.relevamiento.cupo_completo)

    def test_cupo_utilizado_usa_la_anotacion_si_viene(self):
        """La property prefiere `formularios_count` cuando el queryset lo anotó: es lo
        que evita el N+1 de los listados. Un corte que la reescriba sin esa rama
        multiplica las consultas sin que ningún test de valores lo note."""
        relevamiento = Relevamiento.objects.filter(pk=self.relevamiento.pk).first()
        relevamiento.formularios_count = 99

        self.assertEqual(relevamiento.cupo_utilizado, 99)

    def test_convocatoria_hereda_la_pausa_efectiva(self):
        """`Convocatoria` sale de `PausableMixin` y resuelve en cadena: ella misma, su
        segmento, su subsegmento. Perder el mixin en el corte deja el `AttributeError`
        en la pantalla, no en el import."""
        self.assertIsNone(self.convocatoria.pausa_efectiva)

        self.convocatoria.pausado = True
        self.assertEqual(self.convocatoria.pausa_efectiva, self.convocatoria)

        self.convocatoria.pausado = False
        self.segmento.pausado = True
        self.convocatoria.segmento = self.segmento
        self.assertEqual(self.convocatoria.pausa_efectiva, self.segmento)

    def test_el_relevamiento_pausado_hereda_la_pausa_de_la_convocatoria(self):
        self.convocatoria.pausado = True
        self.relevamiento.convocatoria = self.convocatoria

        self.assertEqual(self.relevamiento.pausa_efectiva, self.convocatoria)

    def test_habilitado_en_acepta_date_y_datetime(self):
        """`habilitado_en` recibe las dos cosas según el llamador: un `date` lo
        convierte a las 00:00 locales. Es la diferencia entre «el día 1 cuenta» y «el
        día 1 no cuenta», y con `USE_TZ` se arrastra el huso.
        """
        dentro = timezone.make_aware(datetime(2026, 6, 15, 12, 0))
        self.assertTrue(self.relevamiento.habilitado_en(dentro))
        self.assertTrue(self.relevamiento.habilitado_en(date(2026, 6, 15)))

        fuera = timezone.make_aware(datetime(2026, 7, 1, 12, 0))
        self.assertFalse(self.relevamiento.habilitado_en(fuera))
        self.assertFalse(self.relevamiento.habilitado_en(date(2026, 7, 1)))

    def test_habilitado_en_con_date_toma_las_cero_horas_locales(self):
        """El borde exacto: el relevamiento abre a las 08:00 del 1/6. Pasarle el `date`
        del 1/6 lo evalúa a las 00:00 de ese día, o sea **antes** de la apertura."""
        self.assertFalse(self.relevamiento.habilitado_en(date(2026, 6, 1)))
        self.assertTrue(
            self.relevamiento.habilitado_en(timezone.make_aware(datetime.combine(date(2026, 6, 1), time(9, 0))))
        )

    def test_un_relevamiento_pausado_no_esta_habilitado_nunca(self):
        self.relevamiento.pausado = True

        self.assertFalse(self.relevamiento.habilitado_en(timezone.make_aware(datetime(2026, 6, 15, 12, 0))))

    def test_dni_titular_actual_sin_ciudadano_sale_de_la_identificacion_offline(self):
        formulario = Formulario(
            relevamiento=self.relevamiento,
            datos_identificacion={"dni": "30123456"},
        )

        self.assertEqual(formulario._dni_titular_actual(), "30123456")

    def test_dni_titular_actual_con_ciudadano_cargado_gana_el_del_ciudadano(self):
        from legajos.models import Ciudadano

        ciudadano = Ciudadano.objects.create(nombre="Ana", apellido="Pérez", dni="20111222")
        formulario = Formulario(
            relevamiento=self.relevamiento,
            ciudadano=ciudadano,
            datos_identificacion={"dni": "30123456"},
        )

        self.assertEqual(formulario._dni_titular_actual(), "20111222")

    def test_dni_titular_actual_sin_nada_devuelve_lo_que_ya_tenia(self):
        formulario = Formulario(relevamiento=self.relevamiento, dni_titular="99999999")

        self.assertEqual(formulario._dni_titular_actual(), "99999999")

    def test_dni_titular_actual_no_consulta_la_base_por_un_ciudadano_no_cargado(self):
        """Documentado en la propia property: con el ciudadano asignado **por id** y sin
        cargar, no se dispara la consulta. Un corte que lo «simplifique» a
        `self.ciudadano.dni` agrega un N+1 en el guardado masivo de casos."""
        from legajos.models import Ciudadano

        ciudadano = Ciudadano.objects.create(nombre="Beto", apellido="Gómez", dni="20333444")
        formulario = Formulario(
            relevamiento=self.relevamiento,
            ciudadano_id=ciudadano.pk,
            dni_titular="11111111",
        )

        with self.assertNumQueries(0):
            self.assertEqual(formulario._dni_titular_actual(), "11111111")
