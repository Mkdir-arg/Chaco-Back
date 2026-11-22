"""Emergencia · API de la app: ``es_adulto``, edificio en la derivación y el mapa, y la guarda de «Avisar a la mesa».

Relevamiento de la app móvil (22/11/2026), hallazgos A2, M4 y A4. Todo es **aditivo**: la app v1.2.30 no lee
ninguna de estas claves.

Mutaciones verificadas (cada una pone en rojo al menos un test de acá): cambiar el umbral de ``es_adulto`` o
sacar el chequeo de «confirmada» / «egresada»; que ``es_adulto`` no use la misma regla que
``adultos_de_la_familia``; sacar ``edificio`` del dict del sector o de la derivación; borrar la rama
``derivada_a_otro_edificio`` de ``buscar_por_dni``; nombrar un edificio que no es el destino.
"""

from datetime import date, timedelta

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from programas.models import Derivacion, IntegranteGrupo
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services.emergencia_confirmacion import adultos_de_la_familia
from programas.tests.base_emergencia_api import BaseApiLlegadas, _url
from programas.tests.test_emergencia_alojar_alcance_edificio import _con_alcance_edificios, _partir_en_edificios


def _hace_anios(anios, dias=0):
    hoy = timezone.localdate()
    try:
        return (hoy.replace(year=hoy.year - anios) - timedelta(days=dias)).isoformat()
    except ValueError:  # 29 de febrero
        return (date(hoy.year - anios, 2, 28) - timedelta(days=dias)).isoformat()


class EsAdultoTests(BaseApiLlegadas):
    def _integrantes(self, caso):
        cuerpo = self._como(self.guardia_centro).get(_url("caso-integrantes", caso.pk)).json()
        return {fila["n"]: fila for fila in cuerpo["integrantes"]}

    def _confirmar_nacido(self, caso, n, dni, nacimiento):
        respuesta = self._confirmar(caso, n, dni, datos_personales={"fecha_nacimiento": nacimiento})
        self.assertEqual(respuesta.status_code, 201, respuesta.content)

    def test_es_adulto_marca_solo_al_confirmado_de_18_o_mas(self):
        caso, _ = self._aceptado()
        self._confirmar_nacido(caso, 1, "30111222", _hace_anios(18))  # cumple 18 hoy
        self._confirmar_nacido(caso, 2, "55000222", _hace_anios(18, dias=-1))  # los cumple mañana
        self._confirmar_nacido(caso, 3, "55000333", _hace_anios(40))

        filas = self._integrantes(caso)

        self.assertIs(filas[1]["es_adulto"], True)
        self.assertIs(filas[2]["es_adulto"], False)
        self.assertIs(filas[3]["es_adulto"], True)
        self.assertIs(filas[4]["es_adulto"], False)  # sin confirmar: no se sabe quién es

    def test_la_egresada_no_es_adulto_responsable(self):
        caso, _ = self._aceptado()
        self._confirmar_nacido(caso, 1, "30111222", _hace_anios(40))
        IntegranteGrupo.objects.filter(grupo_id=caso.grupo_id, orden=1).update(egresado_en=timezone.now())

        self.assertIs(self._integrantes(caso)[1]["es_adulto"], False)

    def test_es_adulto_coincide_con_lo_que_el_servidor_acepta_como_adulto_responsable(self):
        caso, _ = self._aceptado()
        self._confirmar_nacido(caso, 1, "30111222", _hace_anios(40))
        self._confirmar_nacido(caso, 2, "55000222", _hace_anios(17))
        self._confirmar_nacido(caso, 3, "55000333", _hace_anios(19))

        filas = self._integrantes(caso)
        del_servidor = {a["orden"] for a in adultos_de_la_familia(caso.grupo)}

        self.assertEqual({n for n, fila in filas.items() if fila["es_adulto"]}, del_servidor)
        self.assertEqual(del_servidor, {1, 3})

    def test_el_detalle_de_la_persona_tambien_trae_es_adulto(self):
        caso, _ = self._aceptado()
        self._confirmar_nacido(caso, 1, "30111222", _hace_anios(40))

        fila = self._como(self.guardia_centro).get(_url("caso-integrante", caso.pk, 1)).json()

        self.assertIs(fila["es_adulto"], True)

    def test_es_adulto_no_suma_consultas(self):
        caso, _ = self._aceptado()
        self._confirmar_nacido(caso, 1, "30111222", _hace_anios(40))
        cliente = self._como(self.guardia_centro)
        cliente.get(_url("caso-integrantes", caso.pk))  # calienta caches de permisos

        with CaptureQueriesContext(connection) as con_uno:
            cliente.get(_url("caso-integrantes", caso.pk))
        self._confirmar_nacido(caso, 2, "55000222", _hace_anios(30))
        self._confirmar_nacido(caso, 3, "55000333", _hace_anios(30))
        with CaptureQueriesContext(connection) as con_tres:
            cliente.get(_url("caso-integrantes", caso.pk))

        self.assertEqual(len(con_tres), len(con_uno))


class EdificioEnLaApiTests(BaseApiLlegadas):
    def setUp(self):
        super().setUp()
        self.edif_a, self.edif_b = _partir_en_edificios(self.centro)

    def _derivado_a(self, edificio, dni="31000001", plazas=1):
        caso = self._caso_tomado(menores_f=0, menores_m=0, dni=dni)
        return mesa.derivar_caso(caso, self.operador, self.centro, plazas, True, edificio=edificio)

    def test_la_derivacion_que_ve_la_guardia_trae_su_edificio(self):
        self._derivado_a(self.edif_b)

        cuerpo = self._como(self.guardia_centro).get(_url("dispositivo-buscar", self.centro.pk), {"dni": "31000001"})

        self.assertEqual(cuerpo.json()["derivacion"]["edificio"], {"id": self.edif_b.pk, "nombre": "Edificio B"})

    def test_la_derivacion_sin_edificio_trae_null(self):
        self._derivado(dni="30111222")

        cuerpo = self._como(self.guardia_centro).get(_url("dispositivo-buscar", self.centro.pk), {"dni": "30111222"})

        self.assertIsNone(cuerpo.json()["derivacion"]["edificio"])

    def test_cada_sector_del_mapa_trae_su_edificio(self):
        caso, _ = self._aceptado()

        cuerpo = (
            self._como(self.guardia_centro).get(_url("dispositivo-plazas", self.centro.pk), {"caso": caso.pk}).json()
        )

        por_nombre = {s["sector"]["nombre"]: s["sector"]["edificio"] for s in cuerpo["sectores"]}
        self.assertEqual(por_nombre["Anexo"], {"id": self.edif_b.pk, "nombre": "Edificio B"})
        otros = {nombre: edif for nombre, edif in por_nombre.items() if nombre != "Anexo"}
        self.assertEqual(set(map(lambda e: e["id"], otros.values())), {self.edif_a.pk})

    def test_el_sector_sin_edificio_trae_null(self):
        from programas.models import Sector

        Sector.objects.filter(dispositivo=self.centro, nombre="Anexo").update(edificio=None)

        cuerpo = self._como(self.guardia_centro).get(_url("dispositivo-plazas", self.centro.pk)).json()

        anexo = next(s["sector"] for s in cuerpo["sectores"] if s["sector"]["nombre"] == "Anexo")
        self.assertIsNone(anexo["edificio"])

    def test_con_alcance_edificios_el_mapa_solo_trae_los_suyos(self):
        guardia_b = _con_alcance_edificios(
            self._guardia("guardia_b", ["dispositivo.ver", "dispositivo.admitir"], [self.centro]),
            self.centro,
            self.edif_b,
        )

        cuerpo = self._como(guardia_b).get(_url("dispositivo-plazas", self.centro.pk)).json()

        self.assertEqual({s["sector"]["edificio"]["nombre"] for s in cuerpo["sectores"]}, {"Edificio B"})

    def test_el_mapa_no_suma_consultas_por_el_edificio(self):
        cliente = self._como(self.guardia_centro)
        cliente.get(_url("dispositivo-plazas", self.centro.pk))  # calienta caches de permisos

        with CaptureQueriesContext(connection) as consultas:
            cliente.get(_url("dispositivo-plazas", self.centro.pk))

        sueltas = [
            c["sql"] for c in consultas if "programas_edificio" in c["sql"] and "programas_plaza" not in c["sql"]
        ]
        self.assertEqual(sueltas, [], "el nombre del edificio viaja en el JOIN de las camas, sin consulta propia")


class AvisarALaMesaConDerivacionEnOtroEdificioTests(BaseApiLlegadas):
    """A4: la familia ya derivada a otro edificio del mismo dispositivo no se avisa a la mesa."""

    def setUp(self):
        super().setUp()
        self.edif_a, self.edif_b = _partir_en_edificios(self.centro)
        self.guardia_a = _con_alcance_edificios(
            self._guardia("guardia_a", ["dispositivo.ver", "dispositivo.admitir"], [self.centro]),
            self.centro,
            self.edif_a,
        )
        caso = self._caso_tomado(menores_f=0, menores_m=0, dni="31000002")
        self.derivacion = mesa.derivar_caso(caso, self.operador, self.centro, 1, True, edificio=self.edif_b)

    def _buscar(self, usuario, dni="31000002"):
        return self._como(usuario).get(_url("dispositivo-buscar", self.centro.pk), {"dni": dni}).json()

    def test_la_guardia_del_otro_edificio_no_puede_avisar_a_la_mesa_y_ve_donde_esta(self):
        cuerpo = self._buscar(self.guardia_a)

        self.assertEqual(cuerpo["resultado"], "SIN_DERIVACION")  # la app v1.2.30 sigue entendiendo el resultado
        self.assertIs(cuerpo["puede_avisar_a_la_mesa"], False)
        self.assertIs(cuerpo["puede_ingresar_igual"], False)
        self.assertIs(cuerpo["derivada_a_otro_edificio"], True)
        self.assertEqual(cuerpo["edificio_derivado"], {"id": self.edif_b.pk, "nombre": "Edificio B"})
        self.assertIn("Edificio B", cuerpo["mensaje"])
        self.assertIsNone(cuerpo["derivacion"])

    def test_la_derivacion_aceptada_en_otro_edificio_tambien_cuenta(self):
        servicio.aceptar_derivacion(derivacion=self.derivacion, usuario=self.guardia_centro)

        self.assertIs(self._buscar(self.guardia_a)["derivada_a_otro_edificio"], True)

    def test_quien_tiene_el_edificio_destino_sigue_viendo_la_derivacion(self):
        cuerpo = self._buscar(self.guardia_centro)  # toda la institución

        self.assertEqual(cuerpo["resultado"], "DERIVACION")
        self.assertIs(cuerpo["derivada_a_otro_edificio"], False)
        self.assertIsNone(cuerpo["edificio_derivado"])

    def test_sin_derivacion_nada_cambia(self):
        cuerpo = self._buscar(self.guardia_a, "33444555")

        self.assertEqual(cuerpo["resultado"], "SIN_DERIVACION")
        self.assertIs(cuerpo["puede_avisar_a_la_mesa"], True)
        self.assertIs(cuerpo["derivada_a_otro_edificio"], False)
        self.assertIsNone(cuerpo["edificio_derivado"])

    def test_la_derivacion_a_otro_dispositivo_sigue_sin_nombrarse(self):
        caso = self._caso_tomado(menores_f=0, menores_m=0, dni="31000003")
        mesa.derivar_caso(caso, self.operador, self.escuela, 1, True)

        cuerpo = self._buscar(self.guardia_a, "31000003")

        self.assertIs(cuerpo["derivada_a_otro_edificio"], False)
        self.assertIsNone(cuerpo["edificio_derivado"])
        self.assertIs(cuerpo["puede_avisar_a_la_mesa"], True)

    def test_la_derivacion_vencida_en_otro_edificio_no_bloquea_el_aviso(self):
        Derivacion.objects.filter(pk=self.derivacion.pk).update(vence_en=self.derivacion.creado - timedelta(minutes=1))
        mesa.vencer_derivacion(Derivacion.objects.get(pk=self.derivacion.pk))

        cuerpo = self._buscar(self.guardia_a)

        self.assertIs(cuerpo["derivada_a_otro_edificio"], False)
        self.assertIs(cuerpo["puede_avisar_a_la_mesa"], True)
