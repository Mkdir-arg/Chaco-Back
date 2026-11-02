"""Sugerencias de personas y de agentes en el resto de los buscadores de Dispositivos (Cambio 416).

Lo que se fija acá, y por qué:

1. **El paso «Ingresar persona» usa el mismo endpoint y la misma compuerta** que Reservar y Prestar:
   el endpoint de sugerencias y el asistente usan `puede_ingresar_persona`; no hay dos reglas que puedan discrepar.
2. **El paso de ingreso ofrece las sugerencias solo a quien las puede usar** (y carga la pieza solo ahí).
3. **«Buscar agente» sugiere por nombre**: misma guarda que el buscador completo (capacidad, alcance
   al edificio), 403 JSON sin cache, mínimo 3, tope 10, `hay_mas`, prefijo `istartswith` sin `LIKE BINARY`.
4. **Nada de correo ni teléfono, y el DNI enmascarado**; ni DNI ni correo se buscan por prefijo.
5. Las consultas por columna del selector de personas dan lo mismo que el OR y mantienen el top.
"""

from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from legajos.models import Ciudadano
from programas.selectors.agentes_sugeridos import sugerir_agentes
from programas.selectors.personas_sugeridas import MAXIMO_RESULTADOS, sugerir_personas
from programas.services.estadias import puede_ingresar_persona
from programas.tests.test_dispositivos_buscar_agente import BaseBuscarAgente
from programas.tests.test_dispositivos_estadias import BaseEstadias
from users.models import Profile

CAPS_INGRESO = ("dispositivo.ver", "dispositivo.admitir", "ciudadano.ver")
CLAVES_PERSONA = {"apellido", "nombre", "dni"}


class IngresoPersonaTests(BaseEstadias):
    def setUp(self):
        super().setUp()
        self.url_ingreso = reverse("dispositivos:ingreso_persona", args=[self.cis.pk])
        self.url_sugerencias = reverse("dispositivos:personas_buscar", args=[self.cis.pk])
        self.con_alcance = self._operador("Ingresa CIS", self.cis, CAPS_INGRESO)

    def test_el_paso_ofrece_el_endpoint_y_carga_la_pieza_solo_ahi(self):
        self.client.force_login(self.con_alcance)

        respuesta = self.client.get(self.url_ingreso)

        self.assertContains(respuesta, f'data-sugerencias-url="{self.url_sugerencias}"')
        self.assertContains(respuesta, "custom/js/nodo-sugerencias.js")
        self.assertContains(respuesta, "custom/css/nodo-sugerencias.css")

    def test_el_paso_sigue_ofreciendo_las_sugerencias_tras_un_error_de_validacion(self):
        self.client.force_login(self.con_alcance)

        respuesta = self.client.post(self.url_ingreso, {"dni": "abc"})

        self.assertContains(respuesta, f'data-sugerencias-url="{self.url_sugerencias}"')

    def test_el_aviso_de_vacio_del_paso_no_manda_a_la_pantalla_en_la_que_ya_esta(self):
        self.client.force_login(self.con_alcance)

        paso = self.client.get(self.url_ingreso)
        self.assertContains(paso, "buscá el DNI para darla de alta")
        self.assertNotContains(paso, "dala de alta desde Ingresar persona")

    def test_reservar_y_prestar_conservan_su_aviso_de_vacio(self):
        from core.forms_sugerencias import MENSAJE_SUGERENCIA_SIN_PERSONA, attrs_sugerencias

        self.assertEqual(attrs_sugerencias("/x/")["data-sugerencias-vacio"], MENSAJE_SUGERENCIA_SIN_PERSONA)
        self.assertEqual(attrs_sugerencias("/x/", "Otro")["data-sugerencias-vacio"], "Otro")
        self.client.force_login(self.con_alcance)
        sectores = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))
        self.assertContains(sectores, "dala de alta desde Ingresar persona")

    def test_sin_ver_personas_el_asistente_responde_403_y_no_hay_sugerencias(self):
        sin_padron = self._operador("Admite sin padron", self.cis, ("dispositivo.ver", "dispositivo.admitir"))
        self.client.force_login(sin_padron)

        self.assertEqual(self.client.get(self.url_ingreso).status_code, 403)
        self.assertEqual(self.client.get(self.url_sugerencias, {"q": "Pérez"}).status_code, 403)

    def test_el_endpoint_de_sugerencias_y_el_asistente_comparten_la_regla(self):
        sin_admitir = self._operador("Solo ve", self.cis, ("dispositivo.ver", "ciudadano.ver"))
        de_otro = self._operador("Otro dispositivo", self.parador, CAPS_INGRESO)
        sin_rol = User.objects.create_user("sin_rol", password="x")
        for usuario in (self.con_alcance, sin_admitir, de_otro, sin_rol):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(puede_ingresar_persona(usuario, self.cis), usuario in (self.con_alcance,))
                self.client.force_login(usuario)
                asistente = self.client.get(self.url_ingreso).status_code
                endpoint = self.client.get(self.url_sugerencias, {"q": "Pérez"}).status_code
                self.assertEqual(asistente == 200, endpoint == 200)


class PersonasPorColumnaTests(BaseEstadias):
    """El OR entre apellido y nombre se parte en una consulta por columna: mismo resultado, mismo orden."""

    def setUp(self):
        super().setUp()
        for apellido, nombre, dni in (
            ("Garcia", "Marta", "40000001"),
            ("Gomez", "Gabriel", "40000002"),
            ("Martinez", "Garcia", "40000003"),  # `Garcia` de nombre: entra por la otra columna
            ("Lopez", "Mario", "40000004"),
        ):
            Ciudadano.objects.create(apellido=apellido, nombre=nombre, dni=dni)

    def test_una_palabra_encuentra_por_apellido_y_por_nombre_sin_repetir_y_en_orden(self):
        resultado = sugerir_personas("gar")

        self.assertEqual([f["dni"] for f in resultado["resultados"]], ["40000001", "40000003"])

    def test_varias_palabras_se_cruzan(self):
        self.assertEqual([f["dni"] for f in sugerir_personas("Martinez Gar")["resultados"]], ["40000003"])
        self.assertEqual([f["dni"] for f in sugerir_personas("Gar Mar")["resultados"]], ["40000001", "40000003"])

    def test_el_top_se_corta_despues_de_unir_las_dos_columnas(self):
        Ciudadano.objects.bulk_create(
            [Ciudadano(apellido="Garcia", nombre=f"Ana{i:02d}", dni=f"4100{i:04d}") for i in range(MAXIMO_RESULTADOS)]
            + [Ciudadano(apellido="Aaron", nombre="Garcia", dni="42000000")]
        )

        resultado = sugerir_personas("garc")

        self.assertEqual(len(resultado["resultados"]), MAXIMO_RESULTADOS)
        self.assertTrue(resultado["hay_mas"])
        # El orden global (apellido, nombre) pone a «Aaron» primero aunque salga de la consulta por nombre.
        self.assertEqual(resultado["resultados"][0]["apellido"], "Aaron")
        self.assertEqual(set(resultado["resultados"][0]), CLAVES_PERSONA)

    def test_el_orden_de_la_union_ignora_tildes_y_mayusculas_como_la_collation_de_la_base(self):
        for apellido, nombre, dni in (
            ("Benítez", "Xiomara", "43000001"),
            ("acosta", "Xiomara", "43000002"),
            ("Ávila", "Xiomara", "43000003"),
        ):
            Ciudadano.objects.create(apellido=apellido, nombre=nombre, dni=dni)

        resultado = sugerir_personas("xio")

        # A < B por la letra base, no por el codepoint (donde «Ávila» y «acosta» irían al final): acosta, Ávila, Benítez.
        self.assertEqual([f["dni"] for f in resultado["resultados"]], ["43000002", "43000003", "43000001"])

    def test_buscar_por_palabras_son_dos_consultas_una_por_columna(self):
        with CaptureQueriesContext(connection) as consultas:
            sugerir_personas("Garcia")

        self.assertEqual(len(consultas), 2)


class AgentesSugeridosTests(BaseBuscarAgente):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.url_sugerir = reverse("users:usuario_sugerir_agente")

    def _sugerir(self, q, edificio=None, usuario=None, **extra):
        parametros = {"q": q}
        if edificio is not False:
            parametros["edificio_id"] = (edificio or self.predio).pk
        parametros.update(extra)
        return self._cliente(usuario or self.creador).get(self.url_sugerir, parametros)

    def test_sugiere_por_prefijo_de_nombre_y_de_apellido_sin_distinguir_mayusculas(self):
        for texto in ("qui", "CARL", "carla qui", "Quiroga, Carla"):
            with self.subTest(texto):
                respuesta = self._sugerir(texto)
                self.assertEqual(respuesta.status_code, 200, respuesta.content)
                filas = respuesta.json()["resultados"]
                self.assertEqual([(f["apellido"], f["nombre"]) for f in filas], [("Quiroga", "Carla")])

    def test_no_busca_en_el_medio_del_texto(self):
        self.assertEqual(self._sugerir("iroga").json()["resultados"], [])

    def test_solo_nombre_apellido_dni_enmascarado_y_el_valor_del_campo(self):
        respuesta = self._sugerir("Quiroga")
        fila = respuesta.json()["resultados"][0]

        self.assertEqual(set(fila), {"apellido", "nombre", "dni", "valor"})
        self.assertEqual(fila["dni"], "30.***.222")
        self.assertEqual(fila["valor"], "Carla Quiroga")
        cuerpo = respuesta.content.decode()
        self.assertNotIn("example.com", cuerpo)
        self.assertNotIn("30111222", cuerpo)
        self.assertNotIn("email", cuerpo)

    def test_dni_y_correo_no_se_buscan_por_prefijo_ni_se_ofrecen(self):
        for texto in ("3011", "30111222", "carla@exam", "carla@example.com"):
            with self.subTest(texto):
                self.assertEqual(self._sugerir(texto).json(), {"ok": True, "resultados": [], "hay_mas": False})

    def test_menos_de_tres_caracteres_devuelve_lista_vacia(self):
        self.assertEqual(self._sugerir("Qu").json()["resultados"], [])

    def test_el_tope_es_diez_y_avisa_que_hay_mas(self):
        for n in range(11):
            self._con_rol_de_agente(f"sug{n}", "Mara", f"Lopez{n:02d}", f"3055{n:04d}", f"sug{n}@example.com")
        cuerpo = self._sugerir("Lopez").json()
        self.assertEqual(len(cuerpo["resultados"]), 10)
        self.assertTrue(cuerpo["hay_mas"])
        apellidos = [f["apellido"] for f in cuerpo["resultados"]]
        self.assertEqual(apellidos, sorted(apellidos))

    def test_con_exactamente_el_tope_no_avisa_que_hay_mas(self):
        for n in range(10):
            self._con_rol_de_agente(f"top{n}", "Mara", f"Lopez{n:02d}", f"3066{n:04d}", f"top{n}@example.com")
        self.assertFalse(self._sugerir("Lopez").json()["hay_mas"])

    def test_el_universo_es_el_del_buscador_completo(self):
        self.carla.is_superuser = True
        self.carla.save()
        self.assertEqual(self._sugerir("Quiroga").json()["resultados"], [])
        # El sumable (cuenta activa sin el rol) aparece, igual que en «Buscar agente»; el inactivo sin rol no.
        sin_rol = self._persona("sinrol", "Sandra", "Quiroga", "30111444", "sinrol@example.com")
        self.assertEqual([f["nombre"] for f in self._sugerir("Quiroga").json()["resultados"]], ["Sandra"])
        sin_rol.is_active = False
        sin_rol.save()
        self.assertEqual(self._sugerir("Quiroga").json()["resultados"], [])

    def test_sin_la_capacidad_es_403_json_sin_cache(self):
        sin_cap = self._usuario("sin_cap_sug", ("dispositivo.ver",), [self.parador])
        respuesta = self._sugerir("Quiroga", usuario=sin_cap)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta["Content-Type"], "application/json")
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        self.assertFalse(respuesta.json()["ok"])
        self.assertNotIn("Quiroga", respuesta.content.decode())

    def test_con_alcance_al_edificio_pero_sin_la_capacidad_de_crear_agente_es_403(self):
        # Asignar da alcance al edificio: lo único que falta es `inspeccion.agente.crear`, la guarda del buscador.
        asigna = self._usuario("asigna_sug", ("inspeccion.asignar", "dispositivo.ver"), [self.parador])
        respuesta = self._sugerir("Quiroga", usuario=asigna)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        self.assertEqual(self._buscar("Quiroga", usuario=asigna).status_code, 403)

    def test_la_capacidad_en_otro_programa_es_403(self):
        rol = self._con_capacidad_en_otro_programa("sug")
        ajeno = User.objects.create_user("ajeno_sug", password="x")
        ajeno.groups.add(rol)
        self.assertEqual(self._sugerir("Quiroga", usuario=User.objects.get(pk=ajeno.pk)).status_code, 403)

    def test_un_edificio_fuera_de_alcance_es_403(self):
        respuesta = self._sugerir("Quiroga", edificio=self.edificio_cis)
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta["Cache-Control"], "no-store")

    def test_sin_edificio_es_400_y_anonimo_no_entra(self):
        self.assertEqual(self._sugerir("Quiroga", edificio=False).status_code, 400)
        self.assertIn(Client().get(self.url_sugerir, {"q": "Quiroga"}).status_code, (302, 401, 403))

    def test_solo_get(self):
        self.assertEqual(self._cliente(self.creador).post(self.url_sugerir, {"q": "Quiroga"}).status_code, 405)

    def test_respuesta_sin_cache(self):
        self.assertEqual(self._sugerir("Quiroga")["Cache-Control"], "no-store")

    def test_el_limite_por_operador_es_propio_y_no_gasta_el_del_boton(self):
        with mock.patch("users.views.quick_create.SUGERENCIAS_POR_MINUTO", 2):
            self.assertEqual(self._sugerir("Quiroga").status_code, 200)
            self.assertEqual(self._sugerir("Quiroga").status_code, 200)
            respuesta = self._sugerir("Quiroga")
        self.assertEqual(respuesta.status_code, 429)
        self.assertEqual(respuesta["Cache-Control"], "no-store")
        # La cubeta del botón «Buscar» no se gasta con las sugerencias.
        self.assertEqual(self._buscar("Quiroga").status_code, 200)

    def _foto(self):
        return (
            User.objects.count(),
            Profile.objects.count(),
            set(Group.objects.values_list("pk", "name")),
            {(u.pk, frozenset(u.groups.values_list("pk", flat=True))) for u in User.objects.all()},
        )

    def test_no_crea_ni_modifica_nada(self):
        antes = self._foto()
        self._sugerir("Quiroga")
        self.assertEqual(antes, self._foto())

    def test_el_prefijo_de_nombre_no_se_traduce_a_like_binary_en_mysql(self):
        """`startswith` en MySQL/MariaDB es `LIKE BINARY`: no usa índice. El selector usa `istartswith`."""

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
        from django.db.models import Q

        from programas.selectors import agentes_sugeridos

        consulta = User.objects.filter(Q(first_name__istartswith="Ca") | Q(last_name__istartswith="Ca")).query
        sql, _ = consulta.get_compiler(connection=conexion).as_sql()
        self.assertNotIn("LIKE BINARY", sql)
        # El selector no usa `startswith` en ninguna de sus formas.
        fuente = open(agentes_sugeridos.__file__, encoding="utf-8").read()
        self.assertIn("istartswith", fuente)
        self.assertNotIn("__startswith", fuente.replace("__istartswith", ""))

    def test_es_una_sola_consulta_sin_funcion_sobre_la_columna(self):
        with CaptureQueriesContext(connection) as consultas:
            sugerir_agentes("Quir")

        self.assertEqual(len(consultas), 1)
        donde = consultas[0]["sql"].upper().split("WHERE", 1)[1].split("ORDER BY")[0]
        self.assertNotIn("UPPER(", donde)

    def test_lo_tecleado_se_acota(self):
        self.assertEqual(sugerir_agentes("Quiroga" + "a" * 500)["resultados"], [])
        self.assertEqual(len(sugerir_agentes("Quiroga" + " " * 200 + "zzz")["resultados"]), 1)


class ModalDeAgentesTests(BaseBuscarAgente):
    def test_el_modal_lleva_la_url_de_sugerencias_y_la_pantalla_de_dispositivos_carga_la_pieza(self):
        respuesta = self._cliente(self.creador).get(
            reverse("dispositivos:relevamientos"), {"asignar": self.edificio_cis.pk}
        )

        self.assertContains(respuesta, 'id="quick-user-modal"')
        self.assertContains(respuesta, 'data-action-agente-sugerir="' + reverse("users:usuario_sugerir_agente"))
        self.assertContains(respuesta, "custom/js/nodo-sugerencias.js")
        self.assertContains(respuesta, "custom/css/nodo-sugerencias.css")


class HelpersCompartidosTests(BaseEstadias):
    def test_sin_cache_deja_exactamente_no_store(self):
        from django.http import JsonResponse

        from core.http_cache import sin_cache

        respuesta = sin_cache(JsonResponse({}))

        self.assertEqual(respuesta["Cache-Control"], "no-store")

    def test_el_filtro_por_palabras_es_prefijo_de_una_columna_o_de_la_otra(self):
        from users.services.busqueda import normalizar_tecleado, palabras_del_tecleado, q_prefijo_por_palabras

        self.assertEqual(normalizar_tecleado(None), "")
        self.assertEqual(len(normalizar_tecleado("a" * 500)), 100)
        self.assertEqual(palabras_del_tecleado("Perez, Juan  a b c d e"), ["Perez", "Juan", "a", "b", "c"])
        self.assertEqual(str(q_prefijo_por_palabras([], "apellido", "nombre")), "(AND: )")
        Ciudadano.objects.create(apellido="Zúñiga", nombre="Juan", dni="44000001")
        Ciudadano.objects.create(apellido="Juan", nombre="Zúñiga", dni="44000002")
        Ciudadano.objects.create(apellido="Zúñiga", nombre="Pedro", dni="44000003")
        encontrados = Ciudadano.objects.filter(q_prefijo_por_palabras(["Zúñiga", "Jua"], "apellido", "nombre"))
        self.assertEqual(sorted(encontrados.values_list("dni", flat=True)), ["44000001", "44000002"])
