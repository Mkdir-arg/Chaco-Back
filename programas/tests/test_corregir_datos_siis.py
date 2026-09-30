"""Corrección de datos para que un caso pueda informarse a SIIS.

Cada clase fija una de las cuatro correcciones del comando y, sobre todo, lo
que **no** hace: no toca lo que ya está bien, no inventa donde no se le pide, y
escribe en la corrección del caso sin tocar la respuesta del ciudadano.
"""

from datetime import date, timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.utils import timezone

from programas.models import AliasLocalidadSiis, Formulario, LocalidadSiis, ProvinciaSiis
from programas.tests.test_siis_envio import _BaseEnvioTest

TABLA_LOCALIDADES = "localidades_corregidas"
TABLA_RENAPER = "ciudadanos_renaper"


def crear_tabla_localidades(*filas):
    """La tabla que carga el organismo desde su planilla: ``(dni, localidad)``."""
    with connection.cursor() as cur:
        cur.execute(f"CREATE TABLE {TABLA_LOCALIDADES} (dni VARCHAR(20), localidad VARCHAR(200))")
        for dni, localidad in filas:
            cur.execute(f"INSERT INTO {TABLA_LOCALIDADES} (dni, localidad) VALUES (%s, %s)", [dni, localidad])


def crear_tabla_renaper(*filas):
    """El volcado de RENAPER, con las columnas que el comando lee."""
    with connection.cursor() as cur:
        cur.execute(f"CREATE TABLE {TABLA_RENAPER} (dni_consultado VARCHAR(20), fecha_nacimiento DATE, _ok INT)")
        for dni, fecha, ok in filas:
            cur.execute(
                f"INSERT INTO {TABLA_RENAPER} (dni_consultado, fecha_nacimiento, _ok) VALUES (%s, %s, %s)",
                [dni, fecha, ok],
            )


class _BaseCorreccionTest(_BaseEnvioTest):
    def setUp(self):
        super().setUp()
        self.provincia = ProvinciaSiis.objects.create(siis_id=1, nombre="CHACO", clave="chaco")
        self.resistencia = LocalidadSiis.objects.create(
            siis_id=1, provincia=self.provincia, nombre="RESISTENCIA", clave="resistencia"
        )
        self.machagai = LocalidadSiis.objects.create(
            siis_id=44, provincia=self.provincia, nombre="MACHAGAI", clave="machagai"
        )

    def correr(self, *args, **opciones):
        salida = StringIO()
        call_command("corregir_datos_siis", *args, stdout=salida, **opciones)
        return salida.getvalue()

    def correcciones(self):
        self.formulario.refresh_from_db()
        return self.formulario.datos_siis or {}

    def responder(self, destino, valor, texto=None):
        """Deja una respuesta del caso apuntando a un destino SIIS.

        El requisito se crea con el alcance del segmento porque
        ``respuestas_por_destino`` solo mira los que alcanzan al formulario.
        """
        from programas.models import RequisitoNativo

        requisito = RequisitoNativo.objects.filter(destino_siis=destino, segmento=self.segmento).first()
        if requisito is None:
            requisito = RequisitoNativo.objects.create(
                texto=texto or destino, tipo="STRING", destino_siis=destino, segmento=self.segmento
            )
        data = dict(self.formulario.data or {})
        data["requisitos"] = {**(data.get("requisitos") or {}), str(requisito.pk): valor}
        self.formulario.data = data
        self.formulario.save(update_fields=["data"])
        return requisito


class TablaFaltanteTests(_BaseCorreccionTest):
    def test_sin_la_tabla_de_localidades_no_corre(self):
        """Mejor cortar que correr a medias: el operador creería que ya está."""
        with self.assertRaises(CommandError) as ctx:
            self.correr()

        self.assertIn(TABLA_LOCALIDADES, str(ctx.exception))

    def test_sin_la_tabla_puede_correr_igual_si_se_pide_solo_lo_otro(self):
        self.correr("--sin-localidades", "--barrio-generico", "Sin especificar")


class EnsayoTests(_BaseCorreccionTest):
    def test_sin_aplicar_no_escribe_nada(self):
        crear_tabla_localidades((self.ciudadano.dni, "Machagai"))

        salida = self.correr()

        self.assertIn("ENSAYO", salida)
        self.assertEqual(self.correcciones(), {})


class FechaDelApoderadoTests(_BaseCorreccionTest):
    def setUp(self):
        super().setUp()
        crear_tabla_localidades()
        self.ciudadano.fecha_nacimiento = date(2009, 5, 1)
        self.ciudadano.save(update_fields=["fecha_nacimiento"])
        self.formulario.apoderado_dni = self.ciudadano.dni
        self.formulario.apoderado_fecha_nacimiento = date(2009, 5, 1)
        self.formulario.save()

    def test_corrige_la_fecha_del_apoderado_que_es_el_propio_alumno(self):
        salida = self.correr("--fecha-apoderado", "1990-01-01", "--aplicar")

        self.assertEqual(self.correcciones()["fecha_nacim_apoderado"], "1990-01-01")
        self.assertIn("apoderado con el DNI del propio alumno", salida)

    def test_no_toca_el_legajo_del_apoderado(self):
        """La corrección viaja a SIIS; lo que declaró la persona queda intacto."""
        self.correr("--fecha-apoderado", "1990-01-01", "--aplicar")

        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.apoderado_fecha_nacimiento, date(2009, 5, 1))

    def test_sin_la_opcion_no_corrige_ninguna_fecha(self):
        salida = self.correr("--aplicar")

        self.assertNotIn("fecha_nacim_apoderado", self.correcciones())
        self.assertIn("Sin --fecha-apoderado", salida)

    def test_una_fecha_que_no_llega_a_18_se_rechaza_antes_de_escribir(self):
        """Con esa fecha SIIS rechazaría igual: mejor decirlo que hacer el trabajo dos veces."""
        reciente = (timezone.localdate() - timedelta(days=365)).isoformat()

        with self.assertRaises(CommandError) as ctx:
            self.correr("--fecha-apoderado", reciente, "--aplicar")

        self.assertIn("18", str(ctx.exception))

    def test_al_apoderado_mayor_de_edad_no_lo_toca(self):
        self.formulario.apoderado_dni = "25999888"
        self.formulario.apoderado_fecha_nacimiento = date(1980, 2, 2)
        self.formulario.save()

        self.correr("--fecha-apoderado", "1990-01-01", "--aplicar")

        self.assertNotIn("fecha_nacim_apoderado", self.correcciones())


class LocalidadTests(_BaseCorreccionTest):
    def _responder(self, texto_localidad, texto_provincia="Chaco"):
        """Deja el caso con la localidad y la provincia declaradas."""
        self.responder("prov_actual", texto_provincia, texto="Provincia")
        self.responder("loc_actual", texto_localidad, texto="Localidad")

    def test_toma_la_localidad_de_la_planilla_cuando_la_declarada_no_cruza(self):
        self._responder("Machagay del sur")
        crear_tabla_localidades((self.ciudadano.dni, "Machagai"))

        self.correr("--aplicar")

        self.assertEqual(self.correcciones()["loc_actual"], 44)

    def test_la_que_ya_cruza_no_se_toca_aunque_este_en_la_planilla(self):
        self._responder("Resistencia")
        crear_tabla_localidades((self.ciudadano.dni, "Machagai"))

        salida = self.correr("--aplicar")

        self.assertNotIn("loc_actual", self.correcciones())
        self.assertIn("localidad que ya cruzaba", salida)

    def test_le_saca_el_nombre_de_la_provincia_pegado_al_final(self):
        """«Barranqueras chaco» es la localidad bien escrita más texto de más."""
        self._responder("Resistencia chaco")
        crear_tabla_localidades()

        self.correr("--aplicar")

        self.assertEqual(self.correcciones()["loc_actual"], 1)

    def test_no_inventa_cuando_no_hay_de_donde(self):
        self._responder("Un lugar que no existe")
        crear_tabla_localidades()

        salida = self.correr("--aplicar")

        self.assertEqual(self.correcciones(), {})
        self.assertIn("no cruza y su DNI no está en la planilla", salida)


class BarrioTests(_BaseCorreccionTest):
    def setUp(self):
        super().setUp()
        crear_tabla_localidades()

    def _barrio(self, valor):
        self.responder("barrio_actual", valor, texto="Barrio")

    def test_un_barrio_corto_con_nombre_real_conserva_el_nombre(self):
        self._barrio("Sur")

        self.correr("--barrio-generico", "Sin especificar", "--aplicar")

        self.assertEqual(self.correcciones()["barrio_actual"], "Barrio Sur")

    def test_un_marcador_de_sin_dato_va_al_generico(self):
        self._barrio("-")

        self.correr("--barrio-generico", "Sin especificar", "--aplicar")

        self.assertEqual(self.correcciones()["barrio_actual"], "Sin especificar")

    def test_un_generico_demasiado_corto_se_rechaza(self):
        """SIIS pide 4 caracteres: un genérico de 2 no arregla nada."""
        with self.assertRaises(CommandError):
            self.correr("--barrio-generico", "NN", "--aplicar")


class FechaDeNacimientoTests(_BaseCorreccionTest):
    def setUp(self):
        super().setUp()
        crear_tabla_localidades()

    def test_corrige_la_fecha_futura_con_renaper(self):
        futura = timezone.localdate() + timedelta(days=30)
        self.ciudadano.fecha_nacimiento = futura
        self.ciudadano.save(update_fields=["fecha_nacimiento"])
        crear_tabla_renaper((self.ciudadano.dni, "2008-04-11", 1))

        salida = self.correr("--fecha-nacimiento-renaper", "--aplicar")

        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.fecha_nacimiento, date(2008, 4, 11))
        self.assertIn("fecha de nacimiento futura corregida", salida)

    def test_no_pisa_una_fecha_plausible(self):
        """Solo lo imposible: una fecha creíble no se toca ni con RENAPER en contra."""
        crear_tabla_renaper((self.ciudadano.dni, "2008-04-11", 1))

        self.correr("--fecha-nacimiento-renaper", "--aplicar")

        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.fecha_nacimiento, date(1995, 6, 15))

    def test_sin_fila_en_renaper_no_inventa(self):
        futura = timezone.localdate() + timedelta(days=30)
        self.ciudadano.fecha_nacimiento = futura
        self.ciudadano.save(update_fields=["fecha_nacimiento"])
        crear_tabla_renaper(("99999999", "2008-04-11", 1))

        salida = self.correr("--fecha-nacimiento-renaper", "--aplicar")

        self.ciudadano.refresh_from_db()
        self.assertEqual(self.ciudadano.fecha_nacimiento, futura)
        self.assertIn("RENAPER no puede corregir", salida)


class IdempotenciaTests(_BaseCorreccionTest):
    def test_correrlo_dos_veces_no_cambia_nada_la_segunda(self):
        crear_tabla_localidades()
        self.ciudadano.fecha_nacimiento = date(2009, 5, 1)
        self.ciudadano.save(update_fields=["fecha_nacimiento"])
        self.formulario.apoderado_dni = self.ciudadano.dni
        self.formulario.apoderado_fecha_nacimiento = date(2009, 5, 1)
        self.formulario.save()

        self.correr("--fecha-apoderado", "1990-01-01", "--aplicar")
        primero = self.correcciones()
        salida = self.correr("--fecha-apoderado", "1980-01-01", "--aplicar")

        self.assertEqual(self.correcciones(), primero)
        self.assertIn("apoderado ya corregido antes", salida)


class NoTocaLosYaInformadosTests(_BaseCorreccionTest):
    def test_un_caso_con_alta_en_siis_queda_fuera(self):
        """Ya está en SIIS: corregirlo acá no cambiaría nada allá y confunde."""
        from programas.models import EnvioSIIS

        crear_tabla_localidades((self.ciudadano.dni, "Machagai"))
        EnvioSIIS.objects.create(
            formulario=self.formulario, estado=EnvioSIIS.Estado.ENVIADO, documento=self.ciudadano.dni, siis_id=5
        )

        salida = self.correr("--aplicar")

        self.assertEqual(self.correcciones(), {})
        self.assertIn("No hay casos pendientes", salida)


class AliasDeLocalidadTests(_BaseCorreccionTest):
    def test_la_equivalencia_cargada_resuelve_el_texto(self):
        AliasLocalidadSiis.objects.create(
            provincia=self.provincia, clave="machagay", localidad=self.machagai, texto="Machagay"
        )
        crear_tabla_localidades((self.ciudadano.dni, "Machagay"))
        self.responder("prov_actual", "Chaco", texto="Provincia")
        self.responder("loc_actual", "No existe", texto="Localidad")

        self.correr("--aplicar")

        self.assertEqual(self.correcciones()["loc_actual"], 44)
