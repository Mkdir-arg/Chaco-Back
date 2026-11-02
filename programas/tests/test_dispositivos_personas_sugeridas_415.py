"""Sugerencias de personas para el DNI de Reservar y Prestar (Cambio 415).

Lo que se fija acá, y por qué:

1. **La compuerta es la de reservar y prestar**: `dispositivo.admitir` con alcance al
   dispositivo, más `ciudadano.ver`. Sin cualquiera de las tres cosas, 403.
2. **Solo apellido, nombre y DNI**: ni teléfono, ni correo, ni domicilio.
3. **Mínimo 3 caracteres, tope 10** y aviso de que hay más.
4. **Prefijo**, por DNI (con o sin puntos) o por apellido o nombre.
"""

from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from legajos.models import Ciudadano
from programas.selectors.personas_sugeridas import MAXIMO_RESULTADOS, _filtro, sugerir_personas
from programas.tests.test_dispositivos_estadias import BaseEstadias

CAPS_PRESTAR = ("dispositivo.ver", "dispositivo.admitir", "ciudadano.ver")


class BaseSugerencias(BaseEstadias):
    def setUp(self):
        super().setUp()
        self.url = reverse("dispositivos:personas_buscar", args=[self.cis.pk])
        self.con_alcance = self._operador("Prestador CIS", self.cis, CAPS_PRESTAR)

    def _buscar(self, q, usuario=None):
        self.client.force_login(usuario or self.con_alcance)
        return self.client.get(self.url, {"q": q})


class CompuertaTests(BaseSugerencias):
    def test_quien_puede_prestar_en_el_dispositivo_recibe_la_lista(self):
        respuesta = self._buscar("301")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([f["dni"] for f in respuesta.json()["resultados"]], ["30111222"])

    def test_sin_sesion_no_hay_respuesta_de_datos(self):
        respuesta = self.client.get(self.url, {"q": "301"})

        self.assertNotEqual(respuesta.status_code, 200)

    def test_con_un_rol_de_otro_dispositivo_es_403(self):
        ajeno = self._operador("Prestador Parador", self.parador, CAPS_PRESTAR)

        self.assertEqual(self._buscar("301", ajeno).status_code, 403)

    def test_sin_admitir_es_403(self):
        solo_ver = self._operador("Ve personas CIS", self.cis, ("dispositivo.ver", "ciudadano.ver"))

        self.assertEqual(self._buscar("301", solo_ver).status_code, 403)

    def test_sin_ver_personas_es_403(self):
        sin_padron = self._operador("Admite sin padron CIS", self.cis, ("dispositivo.ver", "dispositivo.admitir"))

        self.assertEqual(self._buscar("301", sin_padron).status_code, 403)

    def test_un_dispositivo_inexistente_es_404(self):
        self.client.force_login(self.con_alcance)

        respuesta = self.client.get(reverse("dispositivos:personas_buscar", args=[99999]), {"q": "301"})

        self.assertEqual(respuesta.status_code, 404)

    def test_solo_se_lee(self):
        self.client.force_login(self.con_alcance)

        self.assertEqual(self.client.post(self.url, {"q": "301"}).status_code, 405)


class ContenidoTests(BaseSugerencias):
    def test_cada_sugerencia_trae_solo_nombre_apellido_y_dni(self):
        Ciudadano.objects.filter(dni="30111222").update(
            telefono="3624123456", email="ana@example.com", domicilio="Calle 1"
        )

        resultados = self._buscar("30111").json()["resultados"]

        self.assertEqual(len(resultados), 1)
        self.assertEqual(set(resultados[0]), {"apellido", "nombre", "dni"})
        self.assertEqual(resultados[0], {"apellido": "Gómez", "nombre": "Ana", "dni": "30111222"})

    def test_la_respuesta_no_se_guarda_en_cache(self):
        self.assertEqual(self._buscar("301")["Cache-Control"], "no-store")

    def test_menos_de_tres_caracteres_devuelve_lista_vacia(self):
        for texto in ("", "  ", "30", "Gó", " a "):
            with self.subTest(texto=texto):
                self.assertEqual(self._buscar(texto).json(), {"resultados": [], "hay_mas": False})

    def test_por_prefijo_de_dni_con_puntos(self):
        self.assertEqual([f["dni"] for f in self._buscar("30.333").json()["resultados"]], ["30333444"])

    def test_por_prefijo_de_apellido_en_minuscula(self):
        # Los acentos los resuelve la collation de MySQL/MariaDB; SQLite no, y acá solo importa el prefijo.
        resultados = self._buscar("pér").json()["resultados"]

        self.assertEqual([f["dni"] for f in resultados], ["30333444"])

    def test_por_prefijo_de_nombre(self):
        self.assertEqual([f["dni"] for f in self._buscar("jua").json()["resultados"]], ["30333444"])

    def test_apellido_y_nombre_juntos_se_cruzan(self):
        self.assertEqual([f["dni"] for f in self._buscar("Pérez, Juan").json()["resultados"]], ["30333444"])
        self.assertEqual(self._buscar("Pérez Ana").json()["resultados"], [])

    def test_no_busca_en_el_medio_del_texto(self):
        self.assertEqual(self._buscar("111222").json()["resultados"], [])
        self.assertEqual(self._buscar("omez").json()["resultados"], [])

    def test_el_comodin_de_like_se_toma_literal(self):
        self.assertEqual(self._buscar("%%%").json()["resultados"], [])

    def test_sin_coincidencias_la_lista_esta_vacia(self):
        self.assertEqual(self._buscar("99999999").json(), {"resultados": [], "hay_mas": False})


class ConsultaTests(BaseSugerencias):
    def test_el_prefijo_de_dni_no_se_traduce_a_like_binary_en_mysql(self):
        """`startswith` en MySQL/MariaDB es `LIKE BINARY`: no usa bien el índice (224 ms en 200k filas)."""

        from django.db.backends.mysql.base import DatabaseWrapper

        conexion = DatabaseWrapper(
            {
                "NAME": "x",
                "USER": "x",
                "PASSWORD": "x",
                "HOST": "x",
                "PORT": "",
                "OPTIONS": {},
                "TIME_ZONE": None,
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": False,
                "AUTOCOMMIT": True,
                "ATOMIC_REQUESTS": False,
                "TEST": {},
            }
        )
        for texto in ("30111", "Gómez", "Pérez Juan"):
            with self.subTest(texto=texto):
                consulta = Ciudadano.objects.filter(_filtro(texto)).query
                sql, _ = consulta.get_compiler(connection=conexion).as_sql()
                self.assertNotIn("LIKE BINARY", sql)
                self.assertIn("LIKE", sql)

    def test_lo_tecleado_se_acota_a_cien_caracteres_y_cinco_palabras(self):
        largo = "30111" + "9" * 500
        self.assertEqual(sugerir_personas(largo), {"resultados": [], "hay_mas": False})
        # Las palabras de más no cuentan: la sexta contradice el nombre y aun así encuentra.
        self.assertEqual(
            [f["dni"] for f in sugerir_personas("Pérez Juan Juan Juan Juan zzzz")["resultados"]], ["30333444"]
        )
        # Pasados los 100 caracteres se corta: el prefijo útil sigue buscándose.
        self.assertEqual([f["dni"] for f in sugerir_personas("Pérez" + " " * 200 + "zzzz")["resultados"]], ["30333444"])

    def test_los_atributos_del_campo_vienen_del_modulo_neutral(self):
        from core.forms_sugerencias import attrs_sugerencias

        self.assertEqual(attrs_sugerencias(None), {})
        self.assertEqual(
            set(attrs_sugerencias("/x/")),
            {"data-sugerencias-url", "data-sugerencias-vacio", "data-sugerencias-hay-mas"},
        )


class TopeTests(BaseSugerencias):
    def _crear(self, cantidad):
        Ciudadano.objects.bulk_create(
            Ciudadano(dni=f"4000{i:04d}", nombre=f"Nombre{i:02d}", apellido="Lopez") for i in range(cantidad)
        )

    def test_con_exactamente_el_tope_no_avisa_que_hay_mas(self):
        self._crear(MAXIMO_RESULTADOS)

        datos = self._buscar("4000").json()

        self.assertEqual(len(datos["resultados"]), MAXIMO_RESULTADOS)
        self.assertFalse(datos["hay_mas"])

    def test_pasado_el_tope_devuelve_diez_y_avisa_que_hay_mas(self):
        self._crear(MAXIMO_RESULTADOS + 5)

        datos = self._buscar("4000").json()

        self.assertEqual(len(datos["resultados"]), MAXIMO_RESULTADOS)
        self.assertTrue(datos["hay_mas"])

    def test_el_orden_es_apellido_y_nombre(self):
        self._crear(3)

        nombres = [f["nombre"] for f in self._buscar("Lopez").json()["resultados"]]

        self.assertEqual(nombres, sorted(nombres))


@tag("performance")
class CostoTests(BaseSugerencias):
    def test_una_sola_consulta_a_la_base_para_buscar(self):
        with CaptureQueriesContext(connection) as consultas:
            sugerir_personas("301")

        self.assertEqual(len(consultas), 1)
        sql = consultas[0]["sql"].upper()
        # Prefijo sobre la columna tal cual: sin función en el WHERE que impida el índice.
        self.assertNotIn("UPPER(", sql.split("WHERE", 1)[1].replace("ORDER BY", ""))
        self.assertNotIn("CAST(", sql.split("WHERE", 1)[1])


class IntegracionConElModalTests(BaseSugerencias):
    """El campo solo se ofrece sugerencias a quien las puede usar."""

    def test_el_campo_dni_lleva_la_url_para_quien_puede_prestar(self):
        self.client.force_login(self.con_alcance)

        # `dispositivo.editar` da acceso al mapa; el que solo admite también lo ve.
        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))

        self.assertContains(respuesta, f'data-sugerencias-url="{self.url}"')
        self.assertContains(respuesta, "custom/js/nodo-sugerencias.js")

    def test_sin_ver_personas_el_campo_queda_como_siempre(self):
        sin_padron = self._operador("Admite sin padron CIS", self.cis, ("dispositivo.ver", "dispositivo.admitir"))
        self.client.force_login(sin_padron)

        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))

        self.assertNotContains(respuesta, "data-sugerencias-url")
