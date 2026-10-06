"""Tests de los modelos de Becas (#73)."""

import uuid
from datetime import date
from importlib import import_module
from io import StringIO
from pathlib import Path

from django.apps import apps
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, models
from django.test import TestCase, tag

from legajos.models import Ciudadano
from programas.models import (
    AsignacionCoordinador,
    Convocatoria,
    Formulario,
    PreguntaGlobal,
    Programa,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    Subsegmento,
    TipoCampo,
    TracaFormulario,
)
from programas.services.becas import (
    coordinador_gestiona_segmento,
    es_menor,
    formulario_por_client_uuid,
    get_campos_formulario,
    get_segmentos_coordinador,
    resolver_ciudadano_offline,
)
from programas.services.inscripcion_publica import dni_en_convocatoria

#: Ratchet de RED-09: toda columna UUID del esquema, con la migración que la amplió
#: a ``char(36)``. En MariaDB 10.7+ Django 5 manda el UUID **con guiones**, así que una
#: columna ``char(32)`` da «Data too long» y un lookup contra el hex no encuentra nada
#: (incidente del 29/09/2026). La lista es literal a propósito: un ``UUIDField`` nuevo
#: tiene que pasar por acá —y por su migración— o el test de abajo se pone rojo.
#: Formato: (etiqueta del modelo, campo, tabla, columna, migración que la amplió).
COLUMNAS_UUID_AMPLIADAS = (
    ("programas.Formulario", "client_uuid", "programas_formulario", "client_uuid", "programas.0047"),
    ("programas.ValidacionSIS", "id_consulta", "programas_validacionsis", "id_consulta", "programas.0048"),
    (
        "programas.InscripcionPrograma",
        "legajo_id",
        "programas_inscripcionprograma",
        "legajo_id",
        "programas.0048",
    ),
    ("programas.Relevamiento", "token_publico", "programas_relevamiento", "token_publico", "programas.0073"),
    ("users.SolicitudCambioEmail", "token", "users_solicitudcambioemail", "token", "users.0023"),
    ("legajos.LegajoAtencion", "id", "legajos_legajoatencion", "id", "legajos.0007"),
    ("legajos.AlertaCiudadano", "legajo", "legajos_alertaciudadano", "legajo_id", "legajos.0007"),
    ("legajos.HistorialContacto", "legajo", "legajos_historialcontacto", "legajo_id", "legajos.0007"),
    ("legajos.Adjunto", "object_id", "legajos_adjunto", "object_id", "legajos.0007"),
)


def _modelos_del_repo():
    """Modelos de las apps que viven en este repo (sin admin, auth, sessions…).

    Mismo criterio que el lint hermano de ``core/tests/test_uuid_mariadb.py``: las
    columnas de las apps de Django las amplía Django, no nosotros.
    """
    raiz = Path(__file__).resolve().parent.parent.parent
    propias = {config.label for config in apps.get_app_configs() if raiz in Path(config.path).resolve().parents}
    return [modelo for modelo in apps.get_models() if modelo._meta.app_label in propias]


class UUIDExternosMySQLTests(TestCase):
    """Los UUID recibidos por API deben admitir su representación con guiones."""

    def test_todo_uuidfield_nuevo_esta_en_la_lista_ampliada(self):
        """RED-09: todo ``UUIDField`` del repo tiene que estar declarado en el ratchet.

        Lo que fuerza este test es exactamente eso: que la columna esté **declarada**
        junto con la migración que la amplió. Que esa migración exista y amplíe a
        ``char(36)`` lo verifica ``test_cada_columna_uuid_declara_su_migracion_a_char36``;
        que la columna **física** mida 36 lo verifica el test de más abajo, que solo
        corre contra MySQL, y contra MariaDB lo verificará TST-01 (``--tag mysql``).

        Recorre el esquema real de las apps del repo, incluidas las FK que apuntan a un
        pk UUID (son columnas UUID igual). Corre en SQLite, que es donde corre el CI.
        """
        declaradas = {(etiqueta, campo) for etiqueta, campo, _, _, _ in COLUMNAS_UUID_AMPLIADAS}
        reales = set()
        for modelo in _modelos_del_repo():
            for campo in modelo._meta.local_fields:
                if isinstance(campo, models.UUIDField):
                    reales.add((modelo._meta.label, campo.name))
                elif campo.is_relation and isinstance(getattr(campo, "target_field", None), models.UUIDField):
                    reales.add((modelo._meta.label, campo.name))

        faltantes = sorted(reales - declaradas)
        self.assertEqual(
            faltantes,
            [],
            "UUIDField sin migración a char(36) ni entrada en COLUMNAS_UUID_AMPLIADAS: "
            f"{faltantes}. Ver el patrón de programas/migrations/0073 y buscar con q_uuid_en_texto.",
        )
        sobrantes = sorted(declaradas - reales)
        self.assertEqual(sobrantes, [], f"El ratchet nombra columnas que ya no existen: {sobrantes}")

    def test_cada_columna_uuid_declara_su_migracion_a_char36(self):
        """La migración que nombra el ratchet existe y amplía esa columna a ``char(36)``.

        Sin esto el ratchet se satisface escribiendo cualquier número de migración: lo
        que la convención de `CLAUDE.md` pide es la migración, no la línea en la lista.
        Se lee el archivo del disco y no ``MigrationLoader`` a propósito: con
        ``DJANGO_SYNCDB_PROJECT_APPS=True`` —que es como corre el CI— el loader ve las
        apps del proyecto sin migraciones (`MIGRATION_MODULES = {...: None}`).
        """
        for etiqueta, campo, tabla, columna, migracion in COLUMNAS_UUID_AMPLIADAS:
            with self.subTest(columna=f"{tabla}.{columna}"):
                app_label, _, prefijo = migracion.partition(".")
                carpeta = Path(apps.get_app_config(app_label).path) / "migrations"
                archivos = sorted(carpeta.glob(f"{prefijo}_*.py"))
                self.assertEqual(
                    len(archivos), 1, f"{etiqueta}.{campo}: {migracion} no existe o es ambigua ({archivos})"
                )
                fuente = archivos[0].read_text(encoding="utf-8")
                self.assertIn("char(36)", fuente, f"{migracion} no amplía ninguna columna a char(36)")
                self.assertIn(tabla, fuente, f"{migracion} no menciona la tabla {tabla}")
                self.assertIn(columna, fuente, f"{migracion} no menciona la columna {columna}")

    @tag("mysql")
    def test_columnas_uuid_externas_admiten_36_caracteres(self):
        """La longitud **física** de las 9 columnas, contra el motor de verdad.

        Hasta el PR R-11 este test daba `OK (skipped=1)` en todos los jobs (RED-09):
        la suite corre en SQLite. Con el tag entra al paso `--tag mysql`, que lo
        corre contra `mariadb:10.11`, `mariadb:11` y `mysql:8.0` (TST-01).
        """
        if connection.vendor != "mysql":
            self.skipTest("La longitud física comprobada corresponde a MySQL.")

        with connection.cursor() as cursor:
            for _, _, tabla, columna, _ in COLUMNAS_UUID_AMPLIADAS:
                cursor.execute(
                    """
                    SELECT CHARACTER_MAXIMUM_LENGTH
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = %s
                      AND COLUMN_NAME = %s
                    """,
                    [tabla, columna],
                )
                fila = cursor.fetchone()
                self.assertIsNotNone(fila, f"No existe {tabla}.{columna}")
                self.assertGreaterEqual(fila[0], 36, f"{tabla}.{columna} no admite UUID con guiones")


class SeedBecasCommandTests(TestCase):
    """El command seed_becas deja el programa y los adjuntos fijos (idempotente)."""

    def test_seed_crea_programa_y_adjuntos(self):
        call_command("seed_becas", stdout=StringIO())
        self.assertTrue(Programa.objects.filter(codigo="BECAS", estado="ACTIVO").exists())
        archivos = PreguntaGlobal.objects.filter(tipo=TipoCampo.ARCHIVO, obligatorio=True, activo=True)
        self.assertGreaterEqual(archivos.count(), 5)
        self.assertTrue(archivos.filter(texto="Foto DNI - Frente").exists())

    def test_seed_es_idempotente(self):
        call_command("seed_becas", stdout=StringIO())
        call_command("seed_becas", stdout=StringIO())
        self.assertEqual(Programa.objects.filter(codigo="BECAS").count(), 1)
        self.assertEqual(PreguntaGlobal.objects.filter(texto="Foto DNI - Frente").count(), 1)


class SegmentoCupoTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Producción Territorial", cupo_maximo=200)

    def test_subsegmento_dentro_de_cupo_ok(self):
        sub = Subsegmento(segmento=self.segmento, nombre="Ladrillo", cupo_maximo=120)
        sub.full_clean()  # no levanta
        sub.save()
        self.assertEqual(self.segmento.cupo_distribuido, 120)
        self.assertEqual(self.segmento.cupo_disponible, 80)

    def test_subsegmento_supera_cupo_levanta_validation_error(self):
        Subsegmento.objects.create(segmento=self.segmento, nombre="Ladrillo", cupo_maximo=120)
        carbon = Subsegmento(segmento=self.segmento, nombre="Carbón", cupo_maximo=100)
        with self.assertRaises(ValidationError) as ctx:
            carbon.full_clean()
        self.assertIn("80", str(ctx.exception))  # máximo disponible

    def test_subsegmento_completa_cupo(self):
        Subsegmento.objects.create(segmento=self.segmento, nombre="Ladrillo", cupo_maximo=120)
        carbon = Subsegmento(segmento=self.segmento, nombre="Carbón", cupo_maximo=80)
        carbon.full_clean()
        carbon.save()
        self.assertEqual(self.segmento.cupo_distribuido, 200)
        self.assertEqual(self.segmento.cupo_disponible, 0)

    def test_no_permite_bajar_cupo_por_debajo_de_lo_distribuido(self):
        Subsegmento.objects.create(segmento=self.segmento, nombre="Ladrillo", cupo_maximo=120)
        self.segmento.cupo_maximo = 100
        with self.assertRaises(ValidationError) as ctx:
            self.segmento.full_clean()
        self.assertIn("120", str(ctx.exception))

    def test_permite_cambiar_de_programa_con_subsegmentos(self):
        """El subsegmento es local: no espeja nada de SIIS, así que mover el
        segmento de programa no lo invalida a nivel modelo."""
        from programas.models import ProgramaSiis

        p1 = ProgramaSiis.objects.create(nombre="P1", siis_programa_id=41)
        p2 = ProgramaSiis.objects.create(nombre="P2", siis_programa_id=42)
        self.segmento.programa = p1
        self.segmento.save(update_fields=["programa"])
        Subsegmento.objects.create(segmento=self.segmento, nombre="Función 1", cupo_maximo=20)

        self.segmento.programa = p2
        self.segmento.full_clean()  # no debe levantar

    def test_no_permite_repetir_nombre_en_el_mismo_segmento(self):
        Subsegmento.objects.create(segmento=self.segmento, nombre="Función 1", cupo_maximo=20)
        repetido = Subsegmento(segmento=self.segmento, nombre="Función 1", cupo_maximo=20)
        with self.assertRaises(ValidationError):
            repetido.full_clean()


class ConvocatoriaTests(TestCase):
    def setUp(self):
        self.seg_a = Segmento.objects.create(nombre="Segmento A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(nombre="Segmento B", cupo_maximo=100)
        self.sub_b = Subsegmento.objects.create(segmento=self.seg_b, nombre="Sub B", cupo_maximo=50)

    def test_subsegmento_de_otro_segmento_invalido(self):
        conv = Convocatoria(
            nombre="Conv 1",
            segmento=self.seg_a,
            subsegmento=self.sub_b,  # pertenece a seg_b
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        with self.assertRaises(ValidationError):
            conv.full_clean()

    def test_subsegmento_del_segmento_correcto_ok(self):
        conv = Convocatoria(
            nombre="Conv 2",
            segmento=self.seg_b,
            subsegmento=self.sub_b,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        conv.full_clean()
        conv.save()
        self.assertEqual(conv.segmento, self.seg_b)


class RelevamientoTests(TestCase):
    def setUp(self):
        self.territorial = User.objects.create_user("terri")
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=50)
        self.conv = Convocatoria.objects.create(
            nombre="Conv",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )

    def test_estados_definidos(self):
        valores = {c[0] for c in Relevamiento.Estado.choices}
        self.assertEqual(
            valores,
            {"ASIGNADO", "EN_CURSO", "FINALIZANDO", "FINALIZADO", "EN_REVISION", "TERMINADO"},
        )

    def test_nombre_autogenerado(self):
        rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Centro",
        )
        self.assertEqual(rel.nombre, "Relevamiento 001 · Conv")
        self.assertEqual(rel.numero, 1)
        self.assertEqual(rel.estado, Relevamiento.Estado.ASIGNADO)

    def test_numeracion_es_independiente_por_convocatoria(self):
        otra_conv = Convocatoria.objects.create(
            nombre="Otra",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        primero = Relevamiento.objects.create(
            convocatoria=self.conv, territorial=self.territorial, fecha_asignada=date(2026, 6, 1), zona="A"
        )
        segundo = Relevamiento.objects.create(
            convocatoria=self.conv, territorial=self.territorial, fecha_asignada=date(2026, 6, 2), zona="B"
        )
        primero_otra = Relevamiento.objects.create(
            convocatoria=otra_conv, territorial=self.territorial, fecha_asignada=date(2026, 6, 1), zona="C"
        )
        self.assertEqual((primero.numero, segundo.numero, primero_otra.numero), (1, 2, 1))
        self.assertEqual(primero.nombre, "Relevamiento 001 · Conv")
        self.assertEqual(segundo.nombre, "Relevamiento 002 · Conv")
        self.assertEqual(primero_otra.nombre, "Relevamiento 001 · Otra")


class CamposFormularioTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.sub = Subsegmento.objects.create(segmento=self.segmento, nombre="Sub", cupo_maximo=40)
        # requisito del segmento (heredable) y del subsegmento (propio)
        self.req_seg = RequisitoNativo.objects.create(
            texto="Actividad productiva", tipo=TipoCampo.STRING, segmento=self.segmento, orden=1
        )
        self.req_sub = RequisitoNativo.objects.create(
            texto="Tipo de horno", tipo=TipoCampo.STRING, segmento=self.segmento, subsegmento=self.sub, orden=2
        )
        self.conv_sin_sub = Convocatoria.objects.create(
            nombre="Sin sub",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.conv_con_sub = Convocatoria.objects.create(
            nombre="Con sub",
            segmento=self.segmento,
            subsegmento=self.sub,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )

    def test_pregunta_inactiva_no_aparece(self):
        activa = PreguntaGlobal.objects.create(texto="Tenencia", tipo=TipoCampo.STRING, activo=True, orden=1)
        inactiva = PreguntaGlobal.objects.create(texto="Vieja", tipo=TipoCampo.STRING, activo=False, orden=2)
        globales, _ = get_campos_formulario(self.conv_sin_sub)
        self.assertIn(activa, globales)
        self.assertNotIn(inactiva, globales)

    def test_requisito_segmento_aplica_a_segmento_y_subsegmento(self):
        _, req_sin_sub = get_campos_formulario(self.conv_sin_sub)
        _, req_con_sub = get_campos_formulario(self.conv_con_sub)
        # El requisito del segmento aparece en ambos
        self.assertIn(self.req_seg, req_sin_sub)
        self.assertIn(self.req_seg, req_con_sub)
        # El requisito del subsegmento solo en la convocatoria con subsegmento
        self.assertNotIn(self.req_sub, req_sin_sub)
        self.assertIn(self.req_sub, req_con_sub)


class AsignacionCoordinadorTests(TestCase):
    def setUp(self):
        self.coord = User.objects.create_user("coord")
        self.seg_a = Segmento.objects.create(nombre="A", cupo_maximo=10)
        self.seg_b = Segmento.objects.create(nombre="B", cupo_maximo=10)
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord)

    def test_gestiona_segmento_asignado(self):
        self.assertTrue(coordinador_gestiona_segmento(self.coord, self.seg_a))

    def test_no_gestiona_segmento_no_asignado(self):
        self.assertFalse(coordinador_gestiona_segmento(self.coord, self.seg_b))

    def test_get_segmentos_coordinador(self):
        segs = get_segmentos_coordinador(self.coord)
        self.assertIn(self.seg_a, segs)
        self.assertNotIn(self.seg_b, segs)


class FormularioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("op")
        self.territorial = User.objects.create_user("terri")
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=50)
        self.conv = Convocatoria.objects.create(
            nombre="Conv",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 1),
            zona="Centro",
        )

    def test_client_uuid_se_encuentra_con_y_sin_guiones(self):
        """La clave idempotente se busca por igualdad (usa el índice único) y
        encuentra la fila tanto si quedó guardada sin guiones como con guiones."""
        client_uuid = uuid.uuid4()
        form = Formulario.objects.create(relevamiento=self.rel, client_uuid=client_uuid)
        self.assertEqual(formulario_por_client_uuid(self.rel, client_uuid), form)

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE programas_formulario SET client_uuid = %s WHERE id = %s",
                [str(client_uuid), form.pk],
            )
        self.assertEqual(formulario_por_client_uuid(self.rel, client_uuid), form)

        otro_rel = Relevamiento.objects.create(
            convocatoria=self.conv,
            territorial=self.territorial,
            fecha_asignada=date(2026, 6, 2),
            zona="Norte",
        )
        self.assertIsNone(formulario_por_client_uuid(otro_rel, client_uuid))
        self.assertIsNone(formulario_por_client_uuid(self.rel, uuid.uuid4()))

    def test_dni_titular_sigue_a_la_identificacion_y_al_ciudadano(self):
        """La columna indexada (Cambio 91) nace de ``datos_identificacion`` y,
        cuando el legajo queda vinculado y cargado, del ciudadano."""
        form = Formulario.objects.create(relevamiento=self.rel, datos_identificacion={"dni": "30111222", "sexo": "F"})
        self.assertEqual(form.dni_titular, "30111222")
        resolver_ciudadano_offline(form)
        form.refresh_from_db()
        self.assertIsNone(form.datos_identificacion)
        self.assertEqual(form.dni_titular, "30111222")
        # Un DNI corregido en el legajo se refleja al guardar el formulario con
        # el ciudadano cargado, aunque ``update_fields`` no lo nombre.
        form.ciudadano.dni = "30111223"
        form.ciudadano.save(update_fields=["dni"])
        form.save(update_fields=["celular"])
        form.refresh_from_db()
        self.assertEqual(form.dni_titular, "30111223")

    def test_dni_en_convocatoria_busca_por_indice(self):
        Formulario.objects.create(relevamiento=self.rel, datos_identificacion={"dni": "30111222"})
        ciudadano = Ciudadano.objects.create(dni="20222333", nombre="Ana", apellido="Paz")
        Formulario.objects.create(relevamiento=self.rel, ciudadano=ciudadano)
        self.assertTrue(dni_en_convocatoria(self.conv, "30111222"))
        self.assertTrue(dni_en_convocatoria(self.conv, "20222333"))
        self.assertFalse(dni_en_convocatoria(self.conv, "99999999"))
        self.assertFalse(dni_en_convocatoria(self.conv, ""))
        # El DNI corregido en el legajo después de la inscripción también cuenta.
        Ciudadano.objects.filter(pk=ciudadano.pk).update(dni="20222334")
        self.assertTrue(dni_en_convocatoria(self.conv, "20222334"))
        otra = Convocatoria.objects.create(
            nombre="Otra",
            segmento=self.segmento,
            fecha_inicio=date(2027, 1, 1),
            fecha_fin=date(2027, 12, 31),
        )
        self.assertFalse(dni_en_convocatoria(otra, "30111222"))
        with self.assertNumQueries(2):
            dni_en_convocatoria(self.conv, "99999999")

    def test_la_migracion_rellena_dni_titular(self):
        con_identificacion = Formulario.objects.create(relevamiento=self.rel, datos_identificacion={"dni": "30111222"})
        ciudadano = Ciudadano.objects.create(dni="20222333", nombre="Ana", apellido="Paz")
        con_legajo = Formulario.objects.create(relevamiento=self.rel, ciudadano=ciudadano)
        sin_nada = Formulario.objects.create(relevamiento=self.rel)
        Formulario.objects.update(dni_titular="")

        migracion = import_module("programas.migrations.0072_formulario_dni_titular")
        migracion.poblar_dni_titular(apps, None)

        self.assertEqual(Formulario.objects.get(pk=con_identificacion.pk).dni_titular, "30111222")
        self.assertEqual(Formulario.objects.get(pk=con_legajo.pk).dni_titular, "20222333")
        self.assertEqual(Formulario.objects.get(pk=sin_nada.pk).dni_titular, "")

    def test_data_guarda_estructura(self):
        form = Formulario.objects.create(
            relevamiento=self.rel,
            celular="3624100200",
            email_contacto="a@b.com",
            data={"globales": {"1": "Propia"}, "requisitos": {"5": "Ladrillo"}},
        )
        form.refresh_from_db()
        self.assertEqual(form.data["globales"]["1"], "Propia")
        self.assertEqual(form.data["requisitos"]["5"], "Ladrillo")

    def test_traza_edicion(self):
        form = Formulario.objects.create(
            relevamiento=self.rel,
            celular="3624100100",
            email_contacto="a@b.com",
        )
        TracaFormulario.objects.create(
            formulario=form,
            editado_por=self.user,
            campo="celular",
            valor_anterior="3624100100",
            valor_nuevo="3624200200",
        )
        traza = form.trazas.get()
        self.assertEqual(traza.valor_anterior, "3624100100")
        self.assertEqual(traza.valor_nuevo, "3624200200")
        self.assertEqual(traza.editado_por, self.user)

    def test_sync_offline_crea_ciudadano(self):
        form = Formulario.objects.create(
            relevamiento=self.rel,
            celular="3624100200",
            email_contacto="a@b.com",
            ciudadano=None,
            datos_identificacion={
                "dni": "99887766",
                "nombre": "Juan",
                "apellido": "Pérez",
                "fecha_nacimiento": "1990-01-15",
                "sexo": "M",
                "origen": "manual",
            },
        )
        resolver_ciudadano_offline(form)
        form.refresh_from_db()
        self.assertIsNotNone(form.ciudadano)
        self.assertEqual(form.ciudadano.dni, "99887766")
        self.assertEqual(form.ciudadano.genero, "M")
        self.assertIsNone(form.datos_identificacion)
        self.assertTrue(Ciudadano.objects.filter(dni="99887766").exists())

    def test_sync_offline_linkea_ciudadano_existente_sin_modificar(self):
        existente = Ciudadano.objects.create(dni="55554444", nombre="Ana", apellido="López")
        form = Formulario.objects.create(
            relevamiento=self.rel,
            celular="3624100200",
            email_contacto="a@b.com",
            ciudadano=None,
            datos_identificacion={"dni": "55554444", "nombre": "OTRO", "apellido": "OTRO"},
        )
        resolver_ciudadano_offline(form)
        form.refresh_from_db()
        existente.refresh_from_db()
        self.assertEqual(form.ciudadano_id, existente.id)
        # No se modifican los datos del ciudadano existente
        self.assertEqual(existente.nombre, "Ana")
        self.assertEqual(existente.apellido, "López")

    def test_sync_offline_completa_sexo_faltante_sin_pisar_uno_existente(self):
        sin_genero = Ciudadano.objects.create(dni="55554445", nombre="Ana", apellido="López")
        form = Formulario.objects.create(
            relevamiento=self.rel,
            celular="3624100200",
            email_contacto="a@b.com",
            datos_identificacion={"dni": sin_genero.dni, "sexo": "F"},
        )
        resolver_ciudadano_offline(form)
        sin_genero.refresh_from_db()
        self.assertEqual(sin_genero.genero, "F")

        con_genero = Ciudadano.objects.create(dni="55554446", nombre="Luis", apellido="Pérez", genero="M")
        otro_form = Formulario.objects.create(
            relevamiento=self.rel,
            celular="3624100201",
            email_contacto="c@d.com",
            datos_identificacion={"dni": con_genero.dni, "sexo": "F"},
        )
        resolver_ciudadano_offline(otro_form)
        con_genero.refresh_from_db()
        self.assertEqual(con_genero.genero, "M")


class HelpersTests(TestCase):
    def test_es_menor(self):
        ref = date(2026, 6, 23)
        self.assertTrue(es_menor(date(2015, 1, 1), referencia=ref))
        self.assertFalse(es_menor(date(1990, 1, 1), referencia=ref))
        self.assertIsNone(es_menor(None))


class ProgramasGenericosIntactosTests(TestCase):
    """No se rompen los modelos genéricos preexistentes."""

    def test_modelos_genericos_funcionan(self):
        from programas.models import DerivacionPrograma, InscripcionPrograma  # noqa: F401

        prog = Programa.objects.create(codigo="X1", nombre="Otro", estado="ACTIVO")
        ciud = Ciudadano.objects.create(dni="11112222", nombre="N", apellido="A")
        insc = InscripcionPrograma.objects.create(ciudadano=ciud, programa=prog)
        self.assertTrue(insc.codigo)  # se autogenera
