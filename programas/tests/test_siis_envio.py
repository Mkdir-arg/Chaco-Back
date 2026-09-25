"""Alta de beneficiarios aprobados en la tabla intermedia de SIIS.

Cubre el módulo puro (CUIL, dirección, catálogos, armado del payload), el
servicio con registro auditable y el comando de reintento.
"""

from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from legajos.models import Ciudadano
from programas.models import (
    AliasLocalidadSiis,
    Convocatoria,
    EnvioSIIS,
    Formulario,
    LocalidadSiis,
    PreguntaGlobal,
    ProgramaSiis,
    ProvinciaSiis,
    Relevamiento,
    Segmento,
    TipoCampo,
    ValidacionSIS,
)
from programas.services import siis_envio
from programas.services.siis import SiisCatalogError
from programas.services.siis_envio import (
    Catalogos,
    armar_payload,
    calcular_cuil,
    enviar_beneficiario_a_siis,
    mensaje_envio,
    parsear_direccion,
)
from programas.tests.test_proceso_masivo import crear_tabla_aprobados_materias


class _BaseEnvioTest(TestCase):
    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.programa = ProgramaSiis.objects.create(
            nombre="Ñachec",
            siis_programa_id=79,
            siis_programa_datos={"id": 79, "nombre": "Ñachec", "jurisdiccion_id": 28},
            siis_funcion_id=4,
            siis_funcion_nombre="Nivel Operativo",
        )
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=10, programa=self.programa)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.user = User.objects.create_user("coord", password="x")
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria, territorial=self.user, fecha_asignada=date(2026, 6, 1), zona="A"
        )
        self.ciudadano = Ciudadano.objects.create(
            dni="20301234", nombre="Juan Carlos", apellido="Perez", fecha_nacimiento=date(1995, 6, 15), genero="M"
        )
        self.formulario = Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=self.ciudadano,
            celular="3624123456",
            email_contacto="juan.perez@email.com",
            estado=Formulario.Estado.APROBADO,
            validado_renaper=True,
            data={"globales": {}, "requisitos": {}},
        )


class ModelosEnvioTests(_BaseEnvioTest):
    def test_envio_vigente_es_el_ultimo(self):
        EnvioSIIS.objects.create(
            formulario=self.formulario,
            estado=EnvioSIIS.Estado.ERROR,
            documento="20301234",
            codigo_error="ERROR_TECNICO",
        )
        ok = EnvioSIIS.objects.create(
            formulario=self.formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="20301234", siis_id=26
        )
        self.assertEqual(self.formulario.envio_siis_vigente, ok)
        self.assertTrue(self.formulario.informado_a_siis)

    def test_pregunta_con_destino(self):
        p = PreguntaGlobal.objects.create(
            texto="Localidad", tipo=TipoCampo.STRING, destino_siis=PreguntaGlobal.DestinoSiis.LOCALIDAD_ACTUAL
        )
        self.assertEqual(p.destino_siis, "loc_actual")
        self.assertEqual(self.formulario.datos_siis, {})
        self.assertFalse(self.formulario.informado_a_siis)


class CuilTests(SimpleTestCase):
    def test_prefijo_por_sexo(self):
        self.assertEqual(calcular_cuil("12345678", "M")[0], 20)
        self.assertEqual(calcular_cuil("12345678", "F")[0], 27)

    def test_digito_verificador_modulo_11(self):
        # 2,0,1,2,3,4,5,6,7,8 × 5,4,3,2,7,6,5,4,3,2 = 148; 148 % 11 = 5; 11 - 5 = 6
        self.assertEqual(calcular_cuil("12345678", "M"), (20, 6))
        # 2,7,1,2,3,4,5,6,7,8 × pesos = 176; 176 % 11 = 0; 11 - 0 = 11 → dígito 0
        self.assertEqual(calcular_cuil("12345678", "F"), (27, 0))

    def test_dni_que_da_diez_con_prefijo_20_pasa_a_23(self):
        # 20-20301234: la suma da resto 1 → verificador 10 → prefijo 23, dígito 9
        self.assertEqual(calcular_cuil("20301234", "M"), (23, 9))

    def test_resto_diez_cambia_a_23(self):
        with patch.object(siis_envio, "_verificador", return_value=10):
            self.assertEqual(calcular_cuil("1", "M"), (23, 9))
            self.assertEqual(calcular_cuil("1", "F"), (23, 4))

    def test_resto_once_es_cero(self):
        with patch.object(siis_envio, "_verificador", return_value=11):
            self.assertEqual(calcular_cuil("1", "M"), (20, 0))


class DireccionTests(SimpleTestCase):
    def test_calle_numero_piso_dpto(self):
        self.assertEqual(
            parsear_direccion("AV. 9 DE JULIO 450 (2, B)"),
            {"calle": "AV. 9 DE JULIO", "nro": 450, "piso": 2, "dpto": "B"},
        )

    def test_calle_y_numero(self):
        self.assertEqual(
            parsear_direccion("Sarmiento 100"), {"calle": "Sarmiento", "nro": 100, "piso": None, "dpto": None}
        )

    def test_sin_numero(self):
        self.assertEqual(
            parsear_direccion("Los Alamos S/N"), {"calle": "Los Alamos", "nro": None, "piso": None, "dpto": None}
        )
        self.assertEqual(parsear_direccion("S/N"), {"calle": "", "nro": None, "piso": None, "dpto": None})

    def test_solo_calle(self):
        self.assertEqual(parsear_direccion("Belgrano"), {"calle": "Belgrano", "nro": None, "piso": None, "dpto": None})

    def test_piso_y_dpto_sueltos(self):
        self.assertEqual(
            parsear_direccion("Mitre 1200 piso 3 dpto A"),
            {"calle": "Mitre", "nro": 1200, "piso": 3, "dpto": "A"},
        )

    def test_vacio(self):
        self.assertEqual(parsear_direccion(""), {"calle": "", "nro": None, "piso": None, "dpto": None})


PROVINCIAS = [{"id": 22, "nombre": "Chaco"}, {"id": 2, "nombre": "Buenos Aires"}]
LOCALIDADES = [
    {"id": 1, "nombre": "Resistencia", "id_provincia": 22},
    {"id": 37, "nombre": "Juan José Castelli", "id_provincia": 22},
    {"id": 900, "nombre": "Resistencia", "id_provincia": 2},
]
ESTADOS_CIVILES = [
    {"id": 1, "nombre": "Soltero/a"},
    {"id": 2, "nombre": "Casado/a"},
    {"id": 5, "nombre": "Conviviente"},
]


def _catalogo_falso(nombre):
    return {"provincias": PROVINCIAS, "localidades": LOCALIDADES, "estados-civiles": ESTADOS_CIVILES}[nombre]


class CatalogosTests(TestCase):
    """El respaldo por API, con el catálogo propio vacío.

    Deja de ser ``SimpleTestCase`` desde el Cambio 85: ``provincia_id`` y
    ``localidad_id`` consultan primero las tablas propias, así que necesitan
    base. Vacías, cae a la API y estos casos siguen describiendo ese camino.
    """

    def setUp(self):
        self.cat = Catalogos(cargar=_catalogo_falso)

    def test_provincia_por_nombre_normalizado(self):
        self.assertEqual(self.cat.provincia_id("chaco"), 22)
        self.assertEqual(self.cat.provincia_id("BUENOS AIRES"), 2)
        self.assertIsNone(self.cat.provincia_id("Formosa"))

    def test_localidad_acotada_a_la_provincia(self):
        self.assertEqual(self.cat.localidad_id("Resistencia", 22), 1)
        self.assertEqual(self.cat.localidad_id("Resistencia", 2), 900)
        self.assertEqual(self.cat.localidad_id("juan jose castelli", 22), 37)
        self.assertIsNone(self.cat.localidad_id("J.j castelli", 22))

    def test_localidad_sin_provincia_devuelve_solo_si_es_unica(self):
        self.assertIsNone(self.cat.localidad_id("Resistencia"))
        self.assertEqual(self.cat.localidad_id("Juan José Castelli"), 37)

    def test_estado_civil_tolera_barra_a(self):
        self.assertEqual(self.cat.estado_civil_id("Soltero/a"), 1)
        self.assertEqual(self.cat.estado_civil_id("Casada"), 2)
        self.assertEqual(self.cat.estado_civil_id("conviviente"), 5)
        self.assertIsNone(self.cat.estado_civil_id("Viudo"))

    def test_error_del_catalogo_se_propaga_como_no_disponible(self):
        def falla(nombre):
            raise SiisCatalogError("caído")

        with self.assertRaises(siis_envio.CatalogoNoDisponible):
            Catalogos(cargar=falla).provincia_id("Chaco")


class RespuestasPorDestinoRequisitosTests(_BaseEnvioTest):
    """Cambio 80: el alta también lee los requisitos del segmento marcados con destino."""

    def _requisito(self, texto, destino, **extra):
        from programas.models import RequisitoNativo

        return RequisitoNativo.objects.create(
            texto=texto, tipo=TipoCampo.STRING, segmento=self.segmento, destino_siis=destino, **extra
        )

    def test_toma_la_respuesta_de_un_requisito_del_segmento(self):
        destino = PreguntaGlobal.DestinoSiis
        r_prov = self._requisito("Provincia", destino.PROVINCIA_ACTUAL, orden=1)
        r_loc_nac = self._requisito("Localidad de nacimiento", destino.LOCALIDAD_NACIMIENTO, orden=2)
        self.formulario.data = {
            "globales": {},
            "requisitos": {str(r_prov.pk): "Chaco", str(r_loc_nac.pk): "Resistencia"},
        }
        resultado = siis_envio.respuestas_por_destino(self.formulario)
        self.assertEqual(resultado["prov_actual"], "Chaco")
        self.assertEqual(resultado["loc_nacim"], "Resistencia")

    def test_el_requisito_del_segmento_manda_sobre_la_pregunta_general(self):
        destino = PreguntaGlobal.DestinoSiis
        pregunta = PreguntaGlobal.objects.create(
            texto="Barrio", tipo=TipoCampo.STRING, destino_siis=destino.BARRIO, orden=150
        )
        requisito = self._requisito("Barrio del segmento", destino.BARRIO, orden=1)
        self.formulario.data = {
            "globales": {str(pregunta.pk): "Centro"},
            "requisitos": {str(requisito.pk): "Villa Libertad"},
        }
        self.assertEqual(siis_envio.respuestas_por_destino(self.formulario)["barrio_actual"], "Villa Libertad")

    def test_ignora_los_requisitos_de_otro_segmento(self):
        from programas.models import RequisitoNativo

        ajeno = Segmento.objects.create(nombre="Ajeno", cupo_maximo=5, programa=self.programa)
        req = RequisitoNativo.objects.create(
            texto="Barrio", tipo=TipoCampo.STRING, segmento=ajeno, destino_siis=PreguntaGlobal.DestinoSiis.BARRIO
        )
        self.formulario.data = {"globales": {}, "requisitos": {str(req.pk): "No corresponde"}}
        self.assertNotIn("barrio_actual", siis_envio.respuestas_por_destino(self.formulario))


class ArmarPayloadTests(_BaseEnvioTest):
    def setUp(self):
        super().setUp()
        self.cat = Catalogos(cargar=_catalogo_falso)
        destino = PreguntaGlobal.DestinoSiis
        self.p_prov = PreguntaGlobal.objects.create(
            texto="Provincia", tipo=TipoCampo.STRING, destino_siis=destino.PROVINCIA_ACTUAL, orden=101
        )
        self.p_loc = PreguntaGlobal.objects.create(
            texto="Localidad", tipo=TipoCampo.STRING, destino_siis=destino.LOCALIDAD_ACTUAL, orden=102
        )
        self.p_barrio = PreguntaGlobal.objects.create(
            texto="Barrio", tipo=TipoCampo.STRING, destino_siis=destino.BARRIO, orden=103
        )
        self.p_calle = PreguntaGlobal.objects.create(
            texto="Calle y altura", tipo=TipoCampo.STRING, destino_siis=destino.CALLE_ALTURA, orden=104
        )
        self.p_civil = PreguntaGlobal.objects.create(
            texto="Estado Civil",
            tipo=TipoCampo.SELECTOR,
            opciones=["Soltero/a", "Casado/a"],
            destino_siis=destino.ESTADO_CIVIL,
            orden=105,
        )
        self.p_prov_nac = PreguntaGlobal.objects.create(
            texto="Prov nac", tipo=TipoCampo.STRING, destino_siis=destino.PROVINCIA_NACIMIENTO, orden=106
        )
        self.p_loc_nac = PreguntaGlobal.objects.create(
            texto="Loc nac", tipo=TipoCampo.STRING, destino_siis=destino.LOCALIDAD_NACIMIENTO, orden=107
        )
        self.formulario.data = {
            "globales": {
                str(self.p_prov.pk): "Chaco",
                str(self.p_loc.pk): "Resistencia",
                str(self.p_barrio.pk): "BARRIO CENTRO",
                str(self.p_calle.pk): "AV. 9 DE JULIO 450 (2, B)",
                str(self.p_civil.pk): "Soltero/a",
                str(self.p_prov_nac.pk): "Chaco",
                str(self.p_loc_nac.pk): "Resistencia",
            },
            "requisitos": {},
        }
        self.formulario.save(update_fields=["data"])

    def _respuesta(self, pregunta, valor):
        self.formulario.data["globales"][str(pregunta.pk)] = valor
        self.formulario.save(update_fields=["data"])

    def test_adulto_completo_calza_con_la_modalidad_a_del_manual(self):
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertEqual(faltantes, {})
        pref, dig = calcular_cuil("20301234", "M")
        self.assertEqual(
            payload,
            {
                "dni": 20301234,
                "tdoc": 1,
                "cuil_pref": pref,
                "cuil_dig": dig,
                "apellido": "PEREZ",
                "nombre": "JUAN CARLOS",
                "sexo": "M",
                "est_civil": 1,
                "prov_nacim": 22,
                "fecha_nacim": "1995-06-15",
                "loc_nacim": 1,
                "celular": 3624123456,
                "prov_actual": 22,
                "loc_actual": 1,
                "barrio_actual": "BARRIO CENTRO",
                "calle_actual": "AV. 9 DE JULIO",
                "nro_actual": 450,
                "piso_actual": 2,
                "dpto_actual": "B",
                "correo_electron": "juan.perez@email.com",
                "jurid": 28,
                "id_plan_soc": 79,
                "id_fun_x_plan": 4,
            },
        )

    def test_la_localidad_sin_match_falta_pero_la_altura_ya_no(self):
        """Cambio 89: sin altura el domicilio va convencional, no falta."""
        self._respuesta(self.p_loc, "J.j castelli")
        self._respuesta(self.p_calle, "Los Alamos S/N")
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertIn("loc_actual", faltantes)
        self.assertNotIn("loc_actual", payload)
        self.assertNotIn("nro_actual", faltantes)
        self.assertEqual(payload["calle_actual"], "Planta urbana sin número")
        self.assertEqual(payload["nro_actual"], 1)

    def test_barrio_numerico_se_prefija_y_barrio_corto_falta(self):
        self._respuesta(self.p_barrio, "108")
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertEqual(payload["barrio_actual"], "Barrio 108")
        self.assertNotIn("barrio_actual", faltantes)
        self._respuesta(self.p_barrio, "Sur")
        _, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertIn("barrio_actual", faltantes)

    def test_datos_siis_pisan_las_respuestas(self):
        self._respuesta(self.p_loc, "J.j castelli")
        self.formulario.datos_siis = {"loc_actual": 37, "nro_actual": 15, "barrio_actual": "Barrio Norte"}
        self.formulario.save(update_fields=["datos_siis"])
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertEqual(faltantes, {})
        self.assertEqual(payload["loc_actual"], 37)
        self.assertEqual(payload["nro_actual"], 15)
        self.assertEqual(payload["barrio_actual"], "Barrio Norte")

    def test_sin_preguntas_marcadas_faltan_los_campos_del_domicilio(self):
        """Calle y altura quedan afuera desde el Cambio 89: sin dato van
        convencionales, así que no pueden faltar nunca."""
        PreguntaGlobal.objects.exclude(destino_siis="").update(destino_siis="")
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertEqual(payload["calle_actual"], "Planta urbana sin número")
        self.assertEqual(payload["nro_actual"], 1)
        for campo in (
            "prov_actual",
            "loc_actual",
            "barrio_actual",
            "est_civil",
            "prov_nacim",
            "loc_nacim",
        ):
            self.assertIn(campo, faltantes, campo)

    def test_menor_sin_apoderado_falta_y_con_apoderado_manda_los_siete_campos(self):
        self.ciudadano.fecha_nacimiento = date(2015, 3, 10)
        self.ciudadano.save(update_fields=["fecha_nacimiento"])
        _, faltantes = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertIn("dni_apoderado", faltantes)

        self.formulario.apoderado_dni = "25999888"
        self.formulario.apoderado_nombre = "Mario"
        self.formulario.apoderado_apellido = "Tutor"
        self.formulario.apoderado_genero = "M"
        self.formulario.apoderado_fecha_nacimiento = date(1978, 10, 20)
        self.formulario.save()
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertEqual(faltantes, {})
        self.assertEqual(payload["dni_apoderado"], 25999888)
        self.assertEqual(payload["apellido_apoderado"], "TUTOR")
        self.assertEqual(payload["nombre_apoderado"], "MARIO")
        self.assertEqual(payload["sexo_apoderado"], "M")
        self.assertEqual(payload["fecha_nacim_apoderado"], "1978-10-20")
        self.assertEqual(
            (payload["cuil_pref_apoderado"], payload["cuil_dig_apoderado"]), calcular_cuil("25999888", "M")
        )

    def test_mayor_no_manda_apoderado_aunque_lo_tenga(self):
        self.formulario.apoderado_dni = "25999888"
        self.formulario.save(update_fields=["apoderado_dni"])
        payload, _ = armar_payload(self.formulario, catalogos=self.cat, hoy=date(2026, 9, 14))
        self.assertNotIn("dni_apoderado", payload)

    def test_programa_sin_funcion_ni_jurisdiccion_falta(self):
        self.programa.siis_funcion_id = None
        self.programa.siis_programa_datos = {"id": 79}
        self.programa.save()
        _, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertIn("id_fun_x_plan", faltantes)
        self.assertIn("jurid", faltantes)

    def test_los_ids_del_programa_se_pueden_corregir_desde_el_caso(self):
        """Sin programa bien configurado el caso igual se puede informar: el
        coordinador completa los tres ids a mano y el envío sale."""
        self.programa.siis_funcion_id = None
        self.programa.siis_programa_datos = {"id": 79}
        self.programa.save()
        self.formulario.datos_siis = {"jurid": 28, "id_plan_soc": 79, "id_fun_x_plan": 4}
        self.formulario.save(update_fields=["datos_siis"])

        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)

        self.assertEqual(payload["jurid"], 28)
        self.assertEqual(payload["id_plan_soc"], 79)
        self.assertEqual(payload["id_fun_x_plan"], 4)
        for campo in ("jurid", "id_plan_soc", "id_fun_x_plan"):
            self.assertNotIn(campo, faltantes)

    def test_la_correccion_pisa_lo_que_dice_el_programa(self):
        self.formulario.datos_siis = {"id_fun_x_plan": 2}
        self.formulario.save(update_fields=["datos_siis"])

        payload, _ = armar_payload(self.formulario, catalogos=self.cat)

        self.assertEqual(payload["id_fun_x_plan"], 2)

    def test_sin_programa_vinculado_los_ids_corregidos_alcanzan(self):
        """El segmento sin programa SIIS dejaba el caso sin salida: ahora la tiene."""
        self.segmento.programa = None
        self.segmento.save(update_fields=["programa"])
        self.formulario.datos_siis = {"jurid": 28, "id_plan_soc": 79, "id_fun_x_plan": 4}
        self.formulario.save(update_fields=["datos_siis"])

        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)

        self.assertEqual(payload["id_plan_soc"], 79)
        self.assertNotIn("id_plan_soc", faltantes)

    def test_sexo_no_binario_y_sin_celular(self):
        self.ciudadano.genero = "X"
        self.ciudadano.save(update_fields=["genero"])
        self.formulario.celular = ""
        self.formulario.save(update_fields=["celular"])
        payload, faltantes = armar_payload(self.formulario, catalogos=self.cat)
        self.assertIn("sexo", faltantes)
        self.assertNotIn("celular", payload)


class EnviarBeneficiarioTests(ArmarPayloadTests):
    """Hereda el formulario completo de ArmarPayloadTests."""

    def setUp(self):
        super().setUp()
        self.cargar = patch("programas.services.siis_envio.cargar_beneficiario").start()
        self.addCleanup(patch.stopall)
        self.cargar.return_value = {
            "success": True,
            "siis_id": 26,
            "codigo": "",
            "reintentable": False,
            "detalles": {},
            "data": {"ids_generados": [26]},
        }

    def test_envio_exitoso_registra_enviado(self):
        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ENVIADO)
        self.assertEqual(envio.siis_id, 26)
        self.assertEqual(envio.id_programa, 79)
        self.assertEqual(envio.id_funcion, 4)
        self.assertEqual(envio.documento, "20301234")
        self.assertEqual(envio.payload["dni"], 20301234)
        self.assertEqual(envio.solicitado_por, self.user)
        self.assertEqual(mensaje_envio(envio), ("success", "Informado a SIIS (ID 26)."))

    def test_no_reenvia_si_ya_esta_enviado(self):
        enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        otro = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(self.cargar.call_count, 1)
        self.assertEqual(self.formulario.envios_sis.count(), 1)
        self.assertEqual(otro.estado, EnvioSIIS.Estado.ENVIADO)

    def test_faltantes_registran_incompleto_sin_llamar(self):
        self._respuesta(self.p_loc, "J.j castelli")
        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.INCOMPLETO)
        self.assertIn("loc_actual", envio.detalles)
        self.cargar.assert_not_called()
        self.assertEqual(mensaje_envio(envio)[0], "warning")

    def test_400_registra_rechazado_con_detalles(self):
        self.cargar.return_value = {
            "success": False,
            "codigo": "DATOS_INVALIDOS",
            "reintentable": False,
            "error": "Uno o más campos…",
            "detalles": {"barrio_actual": ["mínimo 4"]},
            "data": {"error": "DATOS_INVALIDOS"},
        }
        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.RECHAZADO)
        self.assertEqual(envio.codigo_error, "DATOS_INVALIDOS")
        self.assertEqual(envio.detalles, {"barrio_actual": ["mínimo 4"]})
        self.assertFalse(envio.reintentable)

    def test_503_registra_error_reintentable(self):
        self.cargar.return_value = {
            "success": False,
            "codigo": "ERROR_BD_LEGACY",
            "reintentable": True,
            "error": "x",
            "detalles": {},
            "data": {},
        }
        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ERROR)
        self.assertTrue(envio.reintentable)
        self.assertEqual(mensaje_envio(envio)[0], "error")

    def test_catalogo_caido_es_error_tecnico(self):
        def falla(nombre):
            raise SiisCatalogError("SIIS no está disponible temporalmente.")

        envio = enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=Catalogos(cargar=falla))
        self.assertEqual(envio.estado, EnvioSIIS.Estado.ERROR)
        self.assertEqual(envio.codigo_error, "ERROR_TECNICO")
        self.assertIn("catalogo", envio.detalles)
        self.cargar.assert_not_called()

    def test_solo_casos_aprobados(self):
        self.formulario.estado = Formulario.Estado.ENVIADO
        self.formulario.save(update_fields=["estado"])
        with self.assertRaises(ValueError):
            enviar_beneficiario_a_siis(self.formulario, self.user, catalogos=self.cat)


class ComandoReenvioTests(_BaseEnvioTest):
    def setUp(self):
        super().setUp()
        self.enviar = patch("programas.management.commands.reenviar_siis_pendientes.enviar_beneficiario_a_siis").start()
        self.addCleanup(patch.stopall)
        self.enviar.side_effect = lambda f, u, **kw: EnvioSIIS(formulario=f, estado=EnvioSIIS.Estado.ENVIADO, siis_id=1)

    def test_reintenta_solo_errores_tecnicos(self):
        EnvioSIIS.objects.create(
            formulario=self.formulario, estado=EnvioSIIS.Estado.ERROR, documento="1", codigo_error="ERROR_BD_LEGACY"
        )
        otro = Formulario.objects.create(
            relevamiento=self.relevamiento,
            ciudadano=self.ciudadano,
            celular="1",
            email_contacto="a@b.c",
            estado=Formulario.Estado.APROBADO,
        )
        EnvioSIIS.objects.create(formulario=otro, estado=EnvioSIIS.Estado.INCOMPLETO, documento="1")
        salida = StringIO()
        call_command("reenviar_siis_pendientes", stdout=salida)
        self.assertEqual(self.enviar.call_count, 1)
        self.assertEqual(self.enviar.call_args.args[0].pk, self.formulario.pk)
        self.assertIn("1 reintentado", salida.getvalue())

    def test_dry_run_no_envia(self):
        EnvioSIIS.objects.create(formulario=self.formulario, estado=EnvioSIIS.Estado.ERROR, documento="1")
        call_command("reenviar_siis_pendientes", "--dry-run", stdout=StringIO())
        self.enviar.assert_not_called()

    def test_sin_envios_no_hace_nada(self):
        call_command("reenviar_siis_pendientes", stdout=StringIO())
        self.enviar.assert_not_called()


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class ComandoEnvioMasivoTests(_BaseEnvioTest):
    """``enviar_casos_siis``: el alta en lotes, con los ids configurados."""

    def setUp(self):
        super().setUp()
        crear_tabla_aprobados_materias("20301234")
        self.enviar = patch("programas.management.commands.enviar_casos_siis.enviar_beneficiario_a_siis").start()
        self.addCleanup(patch.stopall)
        self.enviar.side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1", siis_id=1
        )
        # Un caso que nadie revisó y uno que la provincia rechazó.
        self.sin_revisar = Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=Formulario.Estado.ENVIADO
        )
        self.rechazado = Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=Formulario.Estado.RECHAZADO
        )

    def _correr(self, *args):
        salida = StringIO()
        call_command("enviar_casos_siis", *args, stdout=salida)
        return salida.getvalue()

    def test_sin_aplicar_no_llama_a_siis(self):
        salida = self._correr()
        self.enviar.assert_not_called()
        self.assertIn("ENSAYO", salida)

    def test_por_defecto_solo_manda_aprobados(self):
        self._correr("--aplicar")
        self.assertEqual([c.args[0].pk for c in self.enviar.call_args_list], [self.formulario.pk])

    def test_un_estado_sin_aprobar_exige_confirmacion_explicita(self):
        with self.assertRaises(CommandError) as ctx:
            self._correr("--estados", "APROBADO,ENVIADO", "--aplicar")
        self.assertIn("--si-entiendo", str(ctx.exception))
        self.enviar.assert_not_called()

    def test_con_si_entiendo_manda_los_estados_nombrados(self):
        self._correr("--estados", "APROBADO,ENVIADO", "--si-entiendo", "--aplicar")
        enviados = sorted(c.args[0].pk for c in self.enviar.call_args_list)
        self.assertEqual(enviados, sorted([self.formulario.pk, self.sin_revisar.pk]))
        # El rechazado no se nombró: no viaja.
        self.assertNotIn(self.rechazado.pk, enviados)

    def test_si_entiendo_sobre_aprobado_no_levanta_la_guarda_del_servicio(self):
        """La guarda se levanta por los estados pedidos, no por el flag suelto."""
        self._correr("--si-entiendo", "--aplicar")
        self.assertTrue(self.enviar.call_args.kwargs["exigir_aprobado"])

    def test_un_estado_inexistente_falla_antes_de_tocar_siis(self):
        with self.assertRaises(CommandError) as ctx:
            self._correr("--estados", "PENDIENTE", "--aplicar")
        self.assertIn("PENDIENTE", str(ctx.exception))
        self.enviar.assert_not_called()

    def test_no_repite_un_caso_ya_enviado(self):
        EnvioSIIS.objects.create(formulario=self.formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        salida = self._correr("--aplicar")
        self.enviar.assert_not_called()
        self.assertIn("No hay casos que informar", salida)

    def test_retoma_incompletos_y_errores(self):
        EnvioSIIS.objects.create(formulario=self.formulario, estado=EnvioSIIS.Estado.INCOMPLETO, documento="1")
        self._correr("--aplicar")
        self.assertEqual(self.enviar.call_count, 1)

    def test_los_rechazados_por_siis_solo_con_el_flag(self):
        EnvioSIIS.objects.create(formulario=self.formulario, estado=EnvioSIIS.Estado.RECHAZADO, documento="1")
        self._correr("--aplicar")
        self.enviar.assert_not_called()
        self._correr("--reintentar-rechazados", "--aplicar")
        self.assertEqual(self.enviar.call_count, 1)

    def test_el_limite_acota(self):
        self._correr("--estados", "APROBADO,ENVIADO", "--si-entiendo", "--limite", "1", "--aplicar")
        self.assertEqual(self.enviar.call_count, 1)

    def test_cada_lote_se_trae_por_pk_en_orden_y_con_sus_relaciones(self):
        """Primero salen los ids; el caso completo se trae recién al procesar su
        lote, con las relaciones que lee el armado del payload ya cargadas."""
        otro = Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=Formulario.Estado.APROBADO
        )
        salida = self._correr("--aplicar", "--lote", "1")
        recibidos = [c.args[0] for c in self.enviar.call_args_list]
        self.assertEqual([f.pk for f in recibidos], sorted([self.formulario.pk, otro.pk]))
        for caso in recibidos:
            self.assertTrue(Formulario.ciudadano.is_cached(caso))
            self.assertTrue(Formulario.relevamiento.is_cached(caso))
            self.assertTrue(Relevamiento.convocatoria.is_cached(caso.relevamiento))
        self.assertIn("2 APROBADO", salida)
        self.assertIn(f"casos {self.formulario.pk}-{self.formulario.pk}", salida)
        self.assertIn(f"casos {otro.pk}-{otro.pk}", salida)


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class ComandoCircuitoCompletoTests(_BaseEnvioTest):
    """``procesar_casos_siis``: validar → aprobar → enviar, en lotes."""

    def setUp(self):
        super().setUp()
        crear_tabla_aprobados_materias("20301234")
        # El circuito vive en el servicio desde que lo comparten el comando y
        # la pantalla del proceso masivo: los parches apuntan ahí.
        base = "programas.services.proceso_masivo."
        self.validar = patch(base + "validar_formulario_en_siis").start()
        self.aprobar = patch(base + "aprobar_o_poner_en_espera").start()
        self.enviar = patch(base + "enviar_beneficiario_a_siis").start()
        self.avisar = patch(base + "enviar_aviso_resolucion").start()
        self.addCleanup(patch.stopall)
        self.validar.side_effect = lambda f, u: ValidacionSIS.objects.create(
            formulario=f, estado=ValidacionSIS.Estado.OK, documento="1", id_programa=79
        )
        self.aprobar.side_effect = lambda f, u: "aprobado"
        self.enviar.side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1", siis_id=1
        )
        # El caso de la base nace APROBADO; agrego uno pendiente de resolución.
        self.pendiente = Formulario.objects.create(
            relevamiento=self.relevamiento, ciudadano=self.ciudadano, estado=Formulario.Estado.ENVIADO
        )

    def _correr(self, *args):
        salida = StringIO()
        call_command("procesar_casos_siis", *args, stdout=salida)
        return salida.getvalue()

    def test_sin_aplicar_no_toca_nada(self):
        salida = self._correr()
        self.validar.assert_not_called()
        self.aprobar.assert_not_called()
        self.enviar.assert_not_called()
        self.assertIn("ENSAYO", salida)

    def test_corre_los_tres_pasos_en_orden(self):
        self._correr("--aplicar", "--total", "1")
        self.assertEqual(self.validar.call_count, 1)
        self.assertEqual(self.enviar.call_count, 1)

    def test_solo_aprueba_los_que_estan_pendientes(self):
        """El caso ya APROBADO se valida y se envía, pero no se re-aprueba."""
        self._correr("--aplicar")
        aprobados = [c.args[0].pk for c in self.aprobar.call_args_list]
        self.assertEqual(aprobados, [self.pendiente.pk])
        self.assertEqual(self.enviar.call_count, 2)

    def test_el_correo_al_ciudadano_va_apagado(self):
        self._correr("--aplicar")
        self.avisar.assert_not_called()

    def test_con_avisar_manda_el_correo(self):
        self._correr("--aplicar", "--avisar")
        self.assertEqual(self.avisar.call_count, 1)

    def test_sin_cupo_no_se_informa_a_siis(self):
        self.aprobar.side_effect = lambda f, u: "lista_espera"
        salida = self._correr("--aplicar", "--total", "50")
        # Solo viaja el que ya estaba aprobado; el de lista de espera no.
        enviados = [c.args[0].pk for c in self.enviar.call_args_list]
        self.assertEqual(enviados, [self.formulario.pk])
        self.assertIn("lista de espera", salida)

    def test_no_reprocesa_un_caso_ya_informado(self):
        EnvioSIIS.objects.create(formulario=self.formulario, estado=EnvioSIIS.Estado.ENVIADO, documento="1")
        self._correr("--aplicar")
        enviados = [c.args[0].pk for c in self.enviar.call_args_list]
        self.assertNotIn(self.formulario.pk, enviados)

    def test_solo_enviar_saltea_validacion_y_aprobacion(self):
        self._correr("--aplicar", "--solo-enviar")
        self.validar.assert_not_called()
        self.aprobar.assert_not_called()
        self.assertEqual(self.enviar.call_count, 1)

    def test_el_total_acota(self):
        self._correr("--aplicar", "--total", "1")
        self.assertEqual(self.enviar.call_count, 1)

    def test_frena_tras_errores_tecnicos_seguidos(self):
        self.enviar.side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
            formulario=f, estado=EnvioSIIS.Estado.ERROR, documento="1", codigo_error="ERROR_TECNICO"
        )
        with self.assertRaises(SystemExit):
            self._correr("--aplicar", "--max-errores", "1")

    def test_solo_completos_descarta_los_que_tienen_faltantes(self):
        # El circuito vive en el servicio desde que lo comparten el comando y
        # la pantalla del proceso masivo: los parches apuntan ahí.
        base = "programas.services.proceso_masivo."
        with patch(base + "armar_payload") as armar:
            # El primero sale limpio; el segundo, sin altura de domicilio.
            armar.side_effect = [({}, {}), ({}, {"nro_actual": "Falta la altura."})]
            salida = self._correr("--aplicar", "--solo-completos")
        self.assertEqual(self.enviar.call_count, 1)
        self.assertIn("Descartados por datos incompletos: 1", salida)
        self.assertIn("nro_actual", salida)

    def test_solo_completos_junta_hasta_el_total_pedido(self):
        # El circuito vive en el servicio desde que lo comparten el comando y
        # la pantalla del proceso masivo: los parches apuntan ahí.
        base = "programas.services.proceso_masivo."
        with patch(base + "armar_payload") as armar:
            armar.return_value = ({}, {})
            self._correr("--aplicar", "--solo-completos", "--total", "1")
        self.assertEqual(self.enviar.call_count, 1)

    def test_un_caso_con_duplicado_sin_resolver_se_saltea(self):
        self.pendiente.conflicto_duplicado = True
        self.pendiente.conflicto_resuelto = False
        self.pendiente.save(update_fields=["conflicto_duplicado", "conflicto_resuelto"])
        self._correr("--aplicar")
        self.aprobar.assert_not_called()


class CatalogoGeograficoPropioTests(TestCase):
    """Cambio 85: provincia y localidad salen del catálogo propio, no de la API.

    ``cargar`` devuelve listas vacías a propósito: si un test pasa, es porque
    resolvió sin la API, que es justo lo que se quiere demostrar.
    """

    def setUp(self):
        call_command("seed_catalogo_siis", stdout=StringIO())
        self.catalogos = Catalogos(cargar=lambda nombre: [])

    def test_carga_el_catalogo_del_repo(self):
        self.assertEqual(ProvinciaSiis.objects.count(), 30)
        self.assertEqual(LocalidadSiis.objects.count(), 275)
        chaco = ProvinciaSiis.objects.get(siis_id=1)
        self.assertEqual(chaco.nombre, "CHACO")
        self.assertTrue(chaco.localidades.filter(siis_id=64, nombre="JUAN JOSE CASTELLI").exists())

    def test_seed_es_idempotente(self):
        call_command("seed_catalogo_siis", stdout=StringIO())
        self.assertEqual(LocalidadSiis.objects.count(), 275)
        self.assertEqual(AliasLocalidadSiis.objects.filter(clave="saenz pena").count(), 1)

    def test_resuelve_la_provincia_sin_la_api(self):
        self.assertEqual(self.catalogos.provincia_id("Chaco"), 1)
        self.assertEqual(self.catalogos.provincia_id("CHACO"), 1)

    def test_resuelve_la_localidad_ignorando_acentos_y_mayusculas(self):
        """El caso 6394 de testing: la API lo daba sin coincidencia."""
        self.assertEqual(self.catalogos.localidad_id("Juan José Castelli", 1), 64)
        self.assertEqual(self.catalogos.localidad_id("JUAN JOSE CASTELLI", 1), 64)

    def test_la_equivalencia_traduce_el_nombre_cargado(self):
        self.assertEqual(self.catalogos.localidad_id("Sáenz Peña", 1), 42)
        self.assertEqual(self.catalogos.localidad_id("General José de San Martín", 1), 27)
        self.assertEqual(self.catalogos.localidad_id("Presidencia de la Plaza", 1), 19)
        self.assertEqual(self.catalogos.localidad_id("Castelli", 1), 64)

    def test_una_equivalencia_sin_destino_no_resuelve(self):
        """«San Fernando» es un departamento: se revisó y no hay localidad."""
        self.assertIsNone(self.catalogos.localidad_id("San Fernando", 1))
        self.assertIsNone(self.catalogos.localidad_id("Sin Informar", 1))

    def test_la_localidad_se_acota_a_su_provincia(self):
        # MERCEDES existe en Corrientes (2) y en Buenos Aires (21), con ids distintos.
        self.assertEqual(self.catalogos.localidad_id("Mercedes", 2), 11)
        self.assertEqual(self.catalogos.localidad_id("Mercedes", 21), 32)

    def test_un_nombre_repetido_dentro_de_la_provincia_no_resuelve(self):
        """TRES HORQUETAS está dos veces en Chaco (129 y 174): lo decide una persona."""
        self.assertIsNone(self.catalogos.localidad_id("Tres Horquetas", 1))

    def test_un_nombre_que_no_esta_no_inventa_nada(self):
        self.assertIsNone(self.catalogos.localidad_id("Localidad Inexistente", 1))


class DomicilioSinAlturaTests(ArmarPayloadTests):
    """Cambio 89: sin altura, el domicilio viaja como aproximado.

    SIIS exige un entero en ``nro_actual`` y el 38% de los casos relevados no lo
    tiene: la gente contestó «S/N», «0», «Planta Urbana» o el nombre de la calle
    sin número. Decisión del PM: en vez de dejarlos sin informar, van con una
    calle convencional y altura 1.
    """

    def _con_calle(self, texto):
        self.formulario.data["globales"][str(self.p_calle.pk)] = texto
        self.formulario.save(update_fields=["data"])
        return armar_payload(self.formulario, catalogos=self.cat)

    def test_sin_nada_usable_va_la_calle_convencional(self):
        for texto in ("S/N", "0", "00", "sin número", "-", "SN", "Planta Urbana"):
            with self.subTest(texto=texto):
                payload, faltantes = self._con_calle(texto)
                self.assertEqual(payload["calle_actual"], "Planta urbana sin número")
                self.assertEqual(payload["nro_actual"], 1)
                self.assertNotIn("nro_actual", faltantes)
                self.assertNotIn("calle_actual", faltantes)

    def test_la_altura_cero_no_es_una_altura(self):
        """«SAN MARTIN 0» salia con nro_actual: 0, que SIIS guarda como altura real."""
        for texto in ("SAN MARTIN 0", "Sarmiento 00", "AV BELGRANO 0"):
            with self.subTest(texto=texto):
                payload, faltantes = self._con_calle(texto)
                self.assertEqual(payload["calle_actual"], "Planta urbana sin número")
                self.assertEqual(payload["nro_actual"], 1)
                self.assertNotIn("nro_actual", faltantes)

    def test_la_altura_cero_corregida_a_mano_tampoco(self):
        self.formulario.datos_siis = {"nro_actual": 0}
        self.formulario.save(update_fields=["datos_siis"])
        payload, _ = self._con_calle("SAN MARTIN 0")
        self.assertEqual(payload["nro_actual"], 1)

    def test_una_altura_real_no_se_toca(self):
        payload, _ = self._con_calle("SAN MARTIN 1")
        self.assertEqual(payload["calle_actual"], "SAN MARTIN")
        self.assertEqual(payload["nro_actual"], 1)

    def test_una_calle_real_sin_altura_tambien_va_convencional(self):
        """Uniforme por decisión del PM: el nombre de la calle no viaja."""
        payload, _ = self._con_calle("Los Alamos S/N")
        self.assertEqual(payload["calle_actual"], "Planta urbana sin número")
        self.assertEqual(payload["nro_actual"], 1)

    def test_con_altura_no_se_toca_nada(self):
        payload, _ = self._con_calle("Sarmiento 100")
        self.assertEqual(payload["calle_actual"], "Sarmiento")
        self.assertEqual(payload["nro_actual"], 100)

    def test_la_correccion_del_coordinador_gana(self):
        """Si alguien escribió la calle a mano, esa no se pisa."""
        self.formulario.datos_siis = {"calle_actual": "Belgrano"}
        self.formulario.save(update_fields=["datos_siis"])
        payload, _ = self._con_calle("S/N")
        self.assertEqual(payload["calle_actual"], "Belgrano")
        self.assertEqual(payload["nro_actual"], 1)

    def test_la_altura_corregida_manda_sobre_la_convencion(self):
        self.formulario.datos_siis = {"nro_actual": 742}
        self.formulario.save(update_fields=["datos_siis"])
        payload, _ = self._con_calle("Los Alamos S/N")
        self.assertEqual(payload["nro_actual"], 742)
        self.assertEqual(payload["calle_actual"], "Los Alamos")


@override_settings(SIIS_API_CLIENT_ID="id-de-prueba", SIIS_API_CLIENT_SECRET="secreto-de-prueba")
class FiltroMateriasEnComandosTests(_BaseEnvioTest):
    """Cambio 90 en los dos comandos: sin tabla no corren, y el flag lo salta."""

    def setUp(self):
        super().setUp()
        self.enviar = patch("programas.services.proceso_masivo.enviar_beneficiario_a_siis").start()
        self.enviar_directo = patch(
            "programas.management.commands.enviar_casos_siis.enviar_beneficiario_a_siis"
        ).start()
        self.addCleanup(patch.stopall)
        for parche in (self.enviar, self.enviar_directo):
            parche.side_effect = lambda f, u, **kw: EnvioSIIS.objects.create(
                formulario=f, estado=EnvioSIIS.Estado.ENVIADO, documento="1", siis_id=1
            )

    def test_procesar_sin_tabla_no_corre(self):
        with self.assertRaises(CommandError) as ctx:
            call_command("procesar_casos_siis", "--aplicar", "--solo-enviar", stdout=StringIO())
        self.assertIn("aprobados_materias", str(ctx.exception))
        self.enviar.assert_not_called()

    def test_procesar_con_el_flag_manda_igual(self):
        call_command("procesar_casos_siis", "--aplicar", "--solo-enviar", "--sin-filtro-materias", stdout=StringIO())
        self.assertEqual(self.enviar.call_count, 1)

    def test_procesar_informa_que_el_filtro_esta_puesto(self):
        """Informa el tamaño de la tabla, que ya está en memoria.

        Antes decía cuántos quedaban afuera, pero eso costaba dos ``count()``
        sobre un queryset con ``distinct()`` y subconsulta correlacionada, y
        contra la base de ECOM no entraban en su ``read_timeout`` de 10 s.
        """
        crear_tabla_aprobados_materias("11111111", "22222222")  # ninguno de los casos
        salida = StringIO()
        call_command("procesar_casos_siis", "--solo-enviar", stdout=salida)
        self.assertIn("Filtro por aprobados_materias", salida.getvalue())
        self.assertIn("2 DNI cargados", salida.getvalue())
        self.assertIn("No hay casos que procesar", salida.getvalue())

    def test_enviar_sin_tabla_no_corre(self):
        with self.assertRaises(CommandError):
            call_command("enviar_casos_siis", "--aplicar", stdout=StringIO())
        self.enviar_directo.assert_not_called()

    def test_enviar_respeta_la_tabla(self):
        crear_tabla_aprobados_materias("11111111")
        call_command("enviar_casos_siis", "--aplicar", stdout=StringIO())
        self.enviar_directo.assert_not_called()

    def test_enviar_con_el_flag_manda_igual(self):
        call_command("enviar_casos_siis", "--aplicar", "--sin-filtro-materias", stdout=StringIO())
        self.assertEqual(self.enviar_directo.call_count, 1)
