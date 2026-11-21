"""El panel «Derivar» por edificio y la distancia desde el domicilio de la familia (Cambio 520)."""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse

from core.models import Municipio, Provincia, UbicacionLocalidad
from programas.models import CasoEmergencia, Derivacion, Edificio
from programas.selectors import emergencia_alojar, emergencia_llegadas
from programas.selectors import emergencia_derivar as derivar
from programas.selectors import emergencia_mesa as mesa_selectors
from programas.selectors.emergencia_derivar import Centroides, punto_de_la_familia, texto_de_distancia
from programas.services import emergencia as servicio
from programas.tests.test_emergencia_mesa import BaseMesa

Origen = CasoEmergencia.Origen


class PuntoDeLaFamiliaTests(BaseMesa):
    """De dónde se mide la distancia: el domicilio primero, el GPS de la toma al final."""

    def setUp(self):
        super().setUp()
        chaco = Provincia.objects.create(nombre="Chaco")
        municipio = Municipio.objects.create(nombre="Resistencia", provincia=chaco)
        self.resistencia.municipio = municipio
        self.resistencia.save()
        UbicacionLocalidad.objects.create(localidad=self.resistencia, latitud="-27.460000", longitud="-58.980000")
        self.client.force_login(self.operador)

    def _punto(self, caso):
        caso.refresh_from_db()
        return punto_de_la_familia(caso, Centroides.leer())

    def test_el_domicilio_ubicado_gana_sobre_todo(self):
        caso = self._caso(
            latitud="-27.1", longitud="-58.1", precision_m=8, domicilio_latitud="-27.5", domicilio_longitud="-58.9"
        )
        punto = self._punto(caso)
        self.assertEqual((punto.latitud, punto.longitud, punto.aproximado), (Decimal("-27.5"), Decimal("-58.9"), False))
        self.assertEqual(punto.origen, derivar.ORIGEN_DOMICILIO)

    def test_con_direccion_y_sin_ubicar_usa_la_localidad_y_no_el_gps_de_la_toma(self):
        caso = self._caso(latitud="-27.1", longitud="-58.1", precision_m=8, localidad=self.resistencia.pk)
        punto = self._punto(caso)
        self.assertTrue(punto.aproximado)
        self.assertEqual(punto.origen, derivar.ORIGEN_LOCALIDAD)
        self.assertEqual(punto.latitud, Decimal("-27.460000"))

    def test_sin_localidad_con_centroide_queda_el_gps(self):
        caso = self._caso(latitud="-27.1", longitud="-58.1", precision_m=8, localidad="")
        self.assertEqual(self._punto(caso).origen, derivar.ORIGEN_GPS)

    def test_un_caso_de_la_mesa_anterior_al_cambio_tenia_el_domicilio_en_latitud(self):
        caso = self._caso(origen=Origen.MESA, localidad="")
        CasoEmergencia.objects.filter(pk=caso.pk).update(latitud="-27.3", longitud="-58.7", precision_m=None)
        punto = self._punto(caso)
        self.assertEqual((punto.origen, punto.aproximado), (derivar.ORIGEN_DOMICILIO, False))

    def test_sin_nada_no_hay_punto(self):
        caso = self._caso(localidad="")
        self.assertIsNone(self._punto(caso))

    def test_el_texto_dice_si_la_distancia_es_aproximada(self):
        self.assertEqual(texto_de_distancia(None), "distancia desconocida")
        self.assertEqual(texto_de_distancia({"km": 3.14, "aproximada": False}), "a 3,1 km en línea recta")
        self.assertEqual(texto_de_distancia({"km": 12, "aproximada": True}), "≈ 12,0 km (por localidad)")

    def test_un_edificio_sin_coordenadas_se_ubica_por_su_localidad(self):
        caso = self._caso_tomado(domicilio_latitud="-27.460000", domicilio_longitud="-58.980000")
        self._edificio("Predio Norte", self.club)

        tarjeta = self._ficha(caso).context["panel"]["edificios"][0]

        self.assertEqual(tarjeta["distancia"], {"km": 0.0, "aproximada": True})
        self.assertEqual(tarjeta["distancia_texto"], "≈ 0,0 km (por localidad)")


class PanelPorEdificioTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def test_ordena_por_distancia_al_domicilio(self):
        caso = self._caso_tomado(domicilio_latitud="-27.451", domicilio_longitud="-58.986")
        lejos = self._dispositivo("Parroquia", camas=10)
        self._edificio("Lejos", lejos, latitud="-27.9", longitud="-59.5")
        self._edificio("Cerca", self.club, latitud="-27.452", longitud="-58.987")

        tarjetas = self._ficha(caso).context["panel"]["edificios"]

        self.assertEqual([tarjeta["nombre"] for tarjeta in tarjetas], ["Cerca", "Lejos"])
        self.assertTrue(tarjetas[0]["distancia_texto"].endswith("km en línea recta"))
        self.assertContains(self._ficha(caso), "km en línea recta")

    def test_un_edificio_de_ubicacion_reservada_no_muestra_el_domicilio(self):
        caso = self._caso_tomado()
        tipo_reservado = type(self.club.tipo).objects.get(pk=self.club.tipo_id)
        tipo_reservado.pk = None
        tipo_reservado.nombre = "Refugio"
        tipo_reservado.codigo = "REFUGIO-519"
        tipo_reservado.ubicacion_reservada = True
        tipo_reservado.save()
        refugio = self._dispositivo("Refugio", camas=4, tipo=tipo_reservado)
        self._edificio("Casa Segura", refugio, calle="Calle Oculta 123")

        tarjeta = self._ficha(caso).context["panel"]["edificios"]
        tarjeta = next(t for t in tarjeta if t["nombre"] == "Casa Segura")

        self.assertTrue(tarjeta["reservado"])
        self.assertEqual(tarjeta["localidad"], "Resistencia")
        self.assertNotContains(self._ficha(caso), "Calle Oculta")

    def test_recalcular_las_plazas_no_saca_del_edificio_elegido(self):
        caso = self._caso_tomado()
        predio = self._edificio("Predio Norte", self.club)
        respuesta = self._ficha(caso, grupo=f"e{predio.pk}")
        self.assertContains(respuesta, f'name="grupo" value="e{predio.pk}"')

    def test_una_coordenada_fuera_del_chaco_no_cuenta(self):
        caso = self._caso_tomado(domicilio_latitud="-27.451", domicilio_longitud="-58.986")
        self._edificio("Invertido", self.club, latitud="-58.98", longitud="-27.45")
        self.assertIsNone(self._ficha(caso).context["panel"]["edificios"][0]["distancia"])

    def test_solo_la_mesa_ve_los_edificios_para_derivar(self):
        caso = self._caso_tomado()
        with self.assertRaises(PermissionDenied):
            derivar.edificios_para_derivar(caso, self.agente)
        self.assertEqual(len(derivar.edificios_para_derivar(caso, self.operador)), 1)

    def test_derivar_guarda_el_edificio_y_lo_muestra(self):
        caso = self._caso_tomado()
        predio = self._edificio("Predio Norte", self.club)

        respuesta = self._post(
            "caso_derivar", caso, {"dispositivo": self.club.pk, "edificio": predio.pk, "plazas": "2"}
        )

        self.assertRedirects(respuesta, self._url("caso_detalle", caso), fetch_redirect_response=False)
        derivacion = Derivacion.objects.get()
        self.assertEqual(derivacion.edificio, predio)
        self.assertIn("(Predio Norte)", self._avisos(respuesta)[0])
        self.assertIn("Derivado a Club Sarmiento (Predio Norte)", self._trazas(caso)[-1].detalle)
        ficha = self._ficha(caso)
        self.assertEqual(ficha.context["derivacion"]["edificio"], "Predio Norte")
        self.assertContains(ficha, "Predio Norte")

    def test_las_camas_que_valen_son_las_del_edificio_elegido(self):
        caso = self._caso_tomado(menores_f=3)  # 5 personas
        norte = self._edificio("Predio Norte", self.club)  # 10 camas
        sur = Edificio.objects.create(codigo="ED-SUR", nombre="Predio Sur", localidad="Resistencia")
        sur.dispositivos.add(self.club)
        sector = self.club.sectores.create(nombre="Anexo", capacidad=2, edificio=sur)
        sector.plazas.create(codigo="S1")
        sector.plazas.create(codigo="S2")

        with self.assertRaises(servicio.FaltanPlazas):
            servicio.derivar_caso(caso, self.operador, self.club, 5, edificio=sur)
        derivacion = servicio.derivar_caso(caso, self.operador, self.club, 5, edificio=norte)
        self.assertEqual(derivacion.edificio, norte)

    def test_el_grupo_sin_edificio_cuenta_solo_sus_camas_como_el_panel(self):
        caso = self._caso_tomado(menores_f=3)  # 5 personas
        mixta = self._dispositivo("Mixta", camas=2)  # 2 camas en un sector sin edificio
        predio = Edificio.objects.create(codigo="ED-N", nombre="Predio Norte", localidad="Resistencia")
        predio.dispositivos.add(mixta)
        nuevo = mixta.sectores.create(nombre="Nuevo", capacidad=10, edificio=predio)
        for n in range(10):
            nuevo.plazas.create(codigo=f"N{n}")

        tarjetas = self._ficha(caso).context["panel"]["edificios"]
        grupo = next(t for t in tarjetas if t["pk"] == f"d{mixta.pk}")
        self.assertEqual((grupo["libres"], grupo["marca"]), (2, "FALTAN"))
        with self.assertRaises(servicio.FaltanPlazas):
            servicio.derivar_caso(caso, self.operador, mixta, 5, sin_edificio=True)
        respuesta = self._post("caso_derivar", caso, {"dispositivo": mixta.pk, "plazas": "5"})
        self.assertFalse(Derivacion.objects.exists())
        self.assertIn("2 de las 5 plazas", self._avisos(respuesta)[0])

    def test_no_se_deriva_a_un_edificio_donde_la_institucion_no_tiene_camas(self):
        caso = self._caso_tomado()
        otro = self._dispositivo("Parroquia", camas=3)
        ajeno = self._edificio("Capilla", otro)

        with self.assertRaises(ValidationError) as error:
            servicio.derivar_caso(caso, self.operador, self.club, 2, edificio=ajeno)

        self.assertIn("edificio", error.exception.message_dict)
        self.assertFalse(Derivacion.objects.exists())

    def test_la_guardia_ve_a_que_edificio_viene_la_familia(self):
        caso = self._caso_tomado()
        predio = self._edificio("Predio Norte", self.club)
        derivacion = servicio.derivar_caso(caso, self.operador, self.club, 2, edificio=predio)

        jefa = User.objects.create_superuser("jefa", "", "x")
        llegadas = emergencia_alojar.llegadas_del_dispositivo(self.club, jefa)
        filas = emergencia_llegadas.filas_de_llegadas(llegadas["pendientes"], derivacion.creado, lambda d: "")
        self.assertIn("Predio Norte", filas[0]["detalle"])


class AltaDesdeLaMesaTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def test_el_punto_del_mapa_se_guarda_como_domicilio_y_no_como_gps(self):
        self.client.post(
            reverse("emergencia:caso_nuevo"), self._formulario1(latitud="-27.451000", longitud="-58.986000")
        )

        caso = CasoEmergencia.objects.get()
        self.assertEqual((caso.domicilio_latitud, caso.domicilio_longitud), (Decimal("-27.451"), Decimal("-58.986")))
        self.assertIsNone(caso.latitud)
        self.assertFalse(caso.con_gps)


class DistanciaPorCalleTests(BaseMesa):
    """Fase 2: lo que el panel le pasa al JS y el guardado del domicilio que ubica Google."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def _config(self, caso, **parametros):
        return self._ficha(caso, **parametros).context["panel"]["distancias"]

    def test_sin_domicilio_ubicado_el_js_lo_ubica_con_la_direccion(self):
        caso = self._caso_tomado(localidad=self.resistencia.pk)
        self._edificio("Predio Norte", self.club, latitud="-27.45", longitud="-58.98")

        config = self._config(caso)

        self.assertIsNone(config["origen"])
        self.assertEqual(config["direccion"], "Av. Sarmiento 1200, Resistencia, Chaco, Argentina")
        self.assertEqual(config["destinos"], [{"clave": config["destinos"][0]["clave"], "lat": -27.45, "lng": -58.98}])
        self.assertEqual(config["ubicar_url"], self._url("caso_ubicar_domicilio", caso))

    def test_con_domicilio_ubicado_va_el_punto(self):
        caso = self._caso_tomado(domicilio_latitud="-27.451", domicilio_longitud="-58.986")
        self._edificio("Predio Norte", self.club, latitud="-27.45", longitud="-58.98")
        self.assertEqual(self._config(caso)["origen"], {"lat": -27.451, "lng": -58.986})

    def test_un_edificio_sin_coordenadas_va_por_su_direccion_y_uno_reservado_no_va(self):
        caso = self._caso_tomado()
        self._edificio("Predio Norte", self.club, calle="Av. Italia 300")
        tipo = type(self.club.tipo).objects.get(pk=self.club.tipo_id)
        tipo.pk, tipo.codigo, tipo.nombre, tipo.ubicacion_reservada = None, "REF-2", "Refugio", True
        tipo.save()
        refugio = self._dispositivo("Refugio", camas=4, tipo=tipo)
        self._edificio("Casa Segura", refugio, calle="Calle Oculta 123", latitud="-27.45", longitud="-58.98")

        config = self._config(caso)

        self.assertEqual(
            [destino.get("direccion") for destino in config["destinos"]],
            ["Av. Italia 300, Resistencia, Chaco, Argentina"],
        )
        self.assertNotIn("Oculta", str(config))

    def test_el_boton_y_el_script_van_solo_en_la_lista_de_edificios(self):
        caso = self._caso_tomado()
        predio = self._edificio("Predio Norte", self.club, latitud="-27.45", longitud="-58.98")

        lista = self._ficha(caso)
        self.assertContains(lista, "Calcular distancia por calle")
        self.assertContains(lista, 'id="derivar-distancias-config"')
        self.assertContains(lista, "nodo-derivar-distancias.js")
        adentro = self._ficha(caso, grupo=f"e{predio.pk}")
        self.assertIsNone(adentro.context["panel"]["distancias"])
        self.assertNotContains(adentro, "nodo-derivar-distancias.js")

    def test_se_pide_a_lo_sumo_a_diez_edificios(self):
        caso = self._caso_tomado()
        for numero in range(12):
            dispositivo = self._dispositivo(f"Centro {numero:02d}", camas=2)
            self._edificio(f"Edificio {numero:02d}", dispositivo, latitud="-27.45", longitud="-58.98")
        self.assertEqual(len(self._config(caso)["destinos"]), mesa_selectors.TOPE_POR_CALLE)


class UbicarDomicilioTests(BaseMesa):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.operador)

    def _ubicar(self, caso, **datos):
        return self.client.post(self._url("caso_ubicar_domicilio", caso), datos)

    def test_guarda_el_punto_y_no_pisa_uno_que_ya_esta(self):
        caso = self._caso_tomado()

        respuesta = self._ubicar(caso, latitud="-27.451234", longitud="-58.986543")

        self.assertEqual(respuesta.json(), {"guardado": True})
        caso.refresh_from_db()
        self.assertEqual(
            (caso.domicilio_latitud, caso.domicilio_longitud), (Decimal("-27.451234"), Decimal("-58.986543"))
        )
        self.assertEqual(self._ubicar(caso, latitud="-27.0", longitud="-59.0").json(), {"guardado": False})
        caso.refresh_from_db()
        self.assertEqual(caso.domicilio_latitud, Decimal("-27.451234"))

    def test_un_punto_fuera_del_chaco_o_invalido_no_se_guarda(self):
        caso = self._caso_tomado()
        for datos in ({"latitud": "-34.6", "longitud": "-58.4"}, {"latitud": "x", "longitud": "-58.9"}, {}):
            with self.subTest(datos=datos):
                respuesta = self._ubicar(caso, **datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertFalse(respuesta.json()["guardado"])
        caso.refresh_from_db()
        self.assertIsNone(caso.domicilio_latitud)

    def test_solo_la_mesa_y_solo_por_post(self):
        caso = self._caso_tomado()
        self.assertEqual(self.client.get(self._url("caso_ubicar_domicilio", caso)).status_code, 405)
        self.client.force_login(self.agente)
        self.assertNotEqual(self._ubicar(caso, latitud="-27.45", longitud="-58.98").status_code, 200)
        caso.refresh_from_db()
        self.assertIsNone(caso.domicilio_latitud)
        with self.assertRaises(PermissionDenied):
            servicio.ubicar_domicilio(caso, self.agente, Decimal("-27.45"), Decimal("-58.98"))
