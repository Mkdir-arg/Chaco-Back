"""Una familia, un caso abierto (Cambio 579): el punto único que busca duplicados y lo que hacen sus tres usuarios.

``crear_caso`` (mesa y territorio), «Ingresar igual» y «Avisar a la mesa» suman al caso que la familia ya tiene
en vez de abrir otro. Cada regla tiene su test; la carrera entre dos altas está en
``test_emergencia_concurrencia.py`` (los dos primeros usan el mismo candado del numerador).
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from programas.models import CasoEmergencia, Derivacion, IntegranteGrupo, ReservaPlaza, TrazaCaso
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services import emergencia_sin_derivacion as sin_derivacion
from programas.services.emergencia_familia import caso_abierto_de_la_familia, resumen_del_caso_abierto
from programas.tests.base_emergencia_api import BaseApiLlegadas, _url
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_casos import Origen

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion

DNI = "33444555"


class BaseFamiliaAbierta(BaseAlojar):
    def _formulario(self, dni=DNI, **cambios):
        datos = self._datos(dni=dni, nombre="Rosa", apellido="Benítez", adultos_f=1, adultos_m=1, menores_f=1)
        del datos["direccion"]
        datos.update(cambios)
        return datos

    def _ingreso(self, dispositivo=None, usuario=None, **cambios):
        dispositivo = dispositivo or self.club
        return servicio.ingreso_directo(
            dispositivo=dispositivo,
            usuario=usuario or (self.guardia if dispositivo == self.club else self.guardia_escuela),
            datos_formulario1=self._formulario(**cambios),
        )

    def _aviso(self, dispositivo=None, usuario=None, **cambios):
        dispositivo = dispositivo or self.club
        return servicio.avisar_a_la_mesa(
            dispositivo=dispositivo,
            usuario=usuario or (self.guardia if dispositivo == self.club else self.guardia_escuela),
            datos_formulario1=self._formulario(**cambios),
        )

    def _alojado_en(self, dispositivo, dni=DNI):
        """Un caso ALOJADO de 2 adultos en ``dispositivo`` (ingreso directo, dos confirmaciones y alojar)."""

        caso = self._ingreso(dispositivo, dni=dni, menores_f=0)
        derivacion = Derivacion.objects.get(caso=caso)
        usuario = self.guardia if dispositivo == self.club else self.guardia_escuela
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza, usuario=usuario)
        servicio.alojar_familia(caso=caso, usuario=usuario)
        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        return CasoEmergencia.objects.get(pk=caso.pk)

    def _casos(self):
        return CasoEmergencia.objects.count()


class DeteccionTests(BaseFamiliaAbierta):
    def test_el_responsable_tiene_su_caso_abierto(self):
        caso = self._caso(dni=DNI)

        self.assertEqual(caso_abierto_de_la_familia(caso.grupo.responsable), caso)

    def test_un_integrante_confirmado_tambien(self):
        caso, _ = self._aceptado(dni="30111222")
        self._confirmar(caso, 1, "45000777")
        integrante = IntegranteGrupo.objects.get(grupo=caso.grupo, orden=1).ciudadano

        self.assertEqual(caso_abierto_de_la_familia(integrante), caso)

    def test_un_caso_cerrado_no_cuenta(self):
        caso = self._caso(dni=DNI)
        CasoEmergencia.objects.filter(pk=caso.pk).update(estado=Estado.CERRADO, cerrado_en=timezone.now())

        self.assertIsNone(caso_abierto_de_la_familia(caso.grupo.responsable))

    def test_sin_caso_o_sin_persona_no_hay_caso_abierto(self):
        self.assertIsNone(caso_abierto_de_la_familia(None))

    def test_el_resumen_trae_solo_lo_que_la_guardia_puede_ver(self):
        caso, _ = self._derivado(self.escuela, dni=DNI)

        resumen = resumen_del_caso_abierto(caso, self.club)

        self.assertEqual(
            set(resumen),
            {
                "id",
                "numero",
                "familia",
                "personas",
                "estado",
                "estado_texto",
                "derivada_a",
                "derivada_en",
                "en_este_dispositivo",
            },
        )
        self.assertEqual((resumen["derivada_a"], resumen["en_este_dispositivo"]), ("Escuela 12", False))
        self.assertEqual(resumen["personas"], caso.grupo.total_declarado)


class CrearCasoTests(BaseFamiliaAbierta):
    def test_el_segundo_alta_de_la_misma_familia_no_crea_otro_caso(self):
        self._caso(dni=DNI)

        with self.assertRaises(mesa.CasoAbiertoDeLaFamilia):
            self._caso(dni=DNI, origen=Origen.MESA)

        self.assertEqual(self._casos(), 1)

    def test_la_mesa_puede_forzar_un_caso_nuevo_con_motivo_y_queda_en_el_historial(self):
        primero = self._caso(dni=DNI)

        segundo = self._caso_forzado(dni=DNI)

        self.assertNotEqual(primero.pk, segundo.pk)
        self.assertEqual(self._casos(), 2)
        # El motivo queda en el historial de los dos casos.
        self.assertIn("La familia se separó", self._trazas(segundo)[0].detalle)
        anterior = next(t for t in self._trazas(primero) if t.accion == Accion.CASO_NUEVO_DE_LA_FAMILIA)
        self.assertIn("La familia se separó", anterior.detalle)
        self.assertIn(segundo.numero, anterior.detalle)

    def test_forzar_sin_motivo_se_rechaza(self):
        self._caso(dni=DNI)

        for motivo in ("", "   "):
            with self.subTest(motivo=motivo), self.assertRaises(ValidationError) as error:
                mesa.crear_caso(
                    usuario=self.operador,
                    origen=Origen.MESA,
                    datos_formulario1=self._datos(dni=DNI),
                    forzar_nuevo_motivo=motivo,
                )
            self.assertIn(mesa.MOTIVO_NUEVO_OBLIGATORIO, str(error.exception))
        self.assertEqual(self._casos(), 1)

    def test_el_territorio_no_puede_forzar(self):
        self._caso(dni=DNI)

        with self.assertRaises(PermissionDenied):
            mesa.crear_caso(
                usuario=self.agente,
                origen=Origen.TERRITORIO,
                datos_formulario1=self._datos(dni=DNI),
                forzar_nuevo_motivo="Otra situación",
            )

        self.assertEqual(self._casos(), 1)

    def test_el_caso_cerrado_deja_abrir_otro_sin_forzar(self):
        caso = self._caso(dni=DNI)
        CasoEmergencia.objects.filter(pk=caso.pk).update(estado=Estado.CERRADO, cerrado_en=timezone.now())

        otro = self._caso(dni=DNI, origen=Origen.MESA)

        self.assertNotEqual(otro.pk, caso.pk)


class IngresoDirectoConCasoAbiertoTests(BaseFamiliaAbierta):
    def test_ingresar_igual_se_suma_al_caso_sin_tomar_de_la_mesa_y_no_abre_otro(self):
        caso = self._caso(dni=DNI, origen=Origen.MESA)

        ingresado = self._ingreso()

        self.assertEqual(ingresado.pk, caso.pk)
        self.assertEqual(self._casos(), 1)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)
        derivacion = Derivacion.objects.get(caso=caso)
        self.assertEqual((derivacion.dispositivo, derivacion.estado), (self.club, Derivacion.Estado.ACEPTADA))
        self.assertTrue(self._reservas(derivacion))

    def test_con_la_derivacion_pendiente_a_otra_institucion_se_cancela_y_se_libera(self):
        caso, derivacion = self._derivado(self.escuela, dni=DNI)

        ingresado = self._ingreso()

        self.assertEqual(ingresado.pk, caso.pk)
        self.assertEqual(self._casos(), 1)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.CANCELADA)
        self.assertEqual(self._reservas(derivacion), [])
        self.assertEqual(
            ReservaPlaza.objects.filter(derivacion=derivacion, estado=ReservaPlaza.Estado.VIGENTE).count(), 0
        )
        nueva = Derivacion.objects.get(caso=caso, estado=Derivacion.Estado.ACEPTADA)
        self.assertEqual(nueva.dispositivo, self.club)
        acciones = [t.accion for t in self._trazas(caso)]
        self.assertIn(Accion.DERIVACION_CANCELADA, acciones)
        self.assertIn(Accion.INGRESO_DIRECTO, acciones)
        self.assertIn(
            "Escuela 12", next(t for t in self._trazas(caso) if t.accion == Accion.DERIVACION_CANCELADA).detalle
        )

    def test_el_caso_alojado_en_este_dispositivo_suma_a_los_que_llegan_despues(self):
        """Decisión 8."""

        caso = self._alojado_en(self.club)
        antes = caso.grupo.total_declarado

        sumado = self._ingreso(adultos_f=1, adultos_m=2, menores_f=0)

        self.assertEqual(sumado.pk, caso.pk)
        self.assertEqual(self._casos(), 1)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)
        caso.grupo.refresh_from_db()
        self.assertGreater(caso.grupo.total_declarado, antes)
        self.assertEqual(IntegranteGrupo.objects.filter(grupo=caso.grupo).count(), caso.grupo.total_declarado)
        self.assertIn(Accion.PERSONAS_SUMADAS, [t.accion for t in self._trazas(caso)])

    def test_alojado_en_otra_institucion_no_se_ingresa_aca(self):
        caso = self._alojado_en(self.escuela)

        with self.assertRaises(servicio.CasoAbiertoEnOtraInstitucion) as error:
            self._ingreso()

        self.assertEqual(error.exception.caso.pk, caso.pk)
        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        self.assertEqual(self._casos(), 1)

    def test_el_ingreso_en_curso_en_otra_institucion_no_se_toca(self):
        caso = self._ingreso(self.escuela)

        with self.assertRaises(servicio.CasoAbiertoEnOtraInstitucion):
            self._ingreso()

        derivacion = Derivacion.objects.get(caso=caso)
        self.assertEqual((derivacion.dispositivo, derivacion.estado), (self.escuela, Derivacion.Estado.ACEPTADA))

    def test_a_recibir_en_este_dispositivo_se_acepta_en_vez_de_ingresar_igual(self):
        self._derivado(self.club, dni=DNI)

        with self.assertRaises(ValidationError) as error:
            self._ingreso()

        self.assertIn(sin_derivacion.A_RECIBIR_NO_SE_INGRESA_IGUAL, str(error.exception))

    def test_sin_camas_libres_no_se_cancela_la_derivacion(self):
        caso, derivacion = self._derivado(self.escuela, dni=DNI)
        self._ocupar(self.club, 9)

        with self.assertRaises(ValidationError):
            self._ingreso()

        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._estado(caso), Estado.DERIVADO)

    def test_ingresar_con_caso_resuelve_por_dni_y_sin_caso_abierto_se_rechaza(self):
        caso = self._caso(dni=DNI, origen=Origen.MESA)

        ingresado = servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia, dni=DNI)
        self.assertEqual(ingresado.pk, caso.pk)

        with self.assertRaises(ValidationError) as error:
            servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia, dni="29999999")
        self.assertIn(sin_derivacion.SIN_CASO_ABIERTO, str(error.exception))

    def test_ingresar_con_caso_sin_alcance_se_rechaza(self):
        self._caso(dni=DNI, origen=Origen.MESA)

        with self.assertRaises(PermissionDenied):
            servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia_escuela, dni=DNI)


class AvisoALaMesaConCasoAbiertoTests(BaseFamiliaAbierta):
    def test_avisar_se_suma_al_caso_y_no_abre_otro(self):
        caso = self._caso(dni=DNI, origen=Origen.MESA)

        avisado = self._aviso()

        self.assertEqual(avisado.pk, caso.pk)
        self.assertEqual(self._casos(), 1)
        self.assertTrue(avisado.familia_ya_tenia_caso)
        self.assertEqual(self._fila(caso)["situacion"]["en_la_puerta_de"]["dispositivo_id"], self.club.pk)
        self.assertEqual(self._trazas(caso)[-1].accion, Accion.AVISO_A_LA_MESA)

    def test_avisar_con_la_derivacion_pendiente_a_otra_institucion_la_cancela_y_vuelve_a_la_mesa(self):
        caso, derivacion = self._derivado(self.escuela, dni=DNI)

        self._aviso()

        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.CANCELADA)
        self.assertEqual(self._estado(caso), Estado.EN_GESTION)
        caso = CasoEmergencia.objects.get(pk=caso.pk)
        self.assertTrue(caso.esperando_en_la_puerta, "la mesa no ve a la familia esperando en la puerta")
        self.assertTrue(CasoEmergencia.objects.filter(CasoEmergencia.q_esperando_en_la_puerta(), pk=caso.pk).exists())
        acciones = [t.accion for t in self._trazas(caso)]
        self.assertEqual(acciones[-2:], [Accion.DERIVACION_CANCELADA, Accion.AVISO_A_LA_MESA])

    def test_no_se_avisa_si_la_derivacion_ya_es_de_este_dispositivo(self):
        caso, _ = self._derivado(self.club, dni=DNI)

        with self.assertRaises(ValidationError) as error:
            self._aviso()

        self.assertIn("No la avises a la mesa", str(error.exception))
        self.assertEqual(self._estado(caso), Estado.DERIVADO)

    def test_avisar_un_caso_alojado_en_otra_institucion_deja_la_marca_sin_tocar_su_estado(self):
        caso = self._alojado_en(self.escuela)

        self._aviso()

        self.assertEqual(self._estado(caso), Estado.ALOJADO)
        self.assertEqual(self._casos(), 1)

    def test_avisar_con_caso_resuelve_por_dni(self):
        caso = self._caso(dni=DNI, origen=Origen.MESA)

        avisado = servicio.avisar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia, dni=DNI)

        self.assertEqual(avisado.pk, caso.pk)
        with self.assertRaises(ValidationError):
            servicio.avisar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia, dni="29999999")


# ---------------------------------------------------------------------------
# La API (la app móvil): campos opcionales nuevos, nada que rompa a la versión en producción
# ---------------------------------------------------------------------------

CLAVES_CASO_ABIERTO = [
    "derivada_a",
    "derivada_en",
    "en_este_dispositivo",
    "estado",
    "estado_texto",
    "familia",
    "id",
    "numero",
    "personas",
]


class ApiFamiliaAbiertaTests(BaseApiLlegadas):
    def _puerta(self, **cambios):
        cuerpo = self._cuerpo(**cambios)
        cuerpo.pop("direccion", None)
        return cuerpo

    def _post(self, ruta, dispositivo=None, usuario=None, **cambios):
        return self._como(usuario or self.guardia_centro).post(
            _url(ruta, (dispositivo or self.centro).pk), self._puerta(**cambios), format="multipart"
        )

    def test_la_busqueda_trae_el_caso_abierto_con_las_claves_exactas_y_nada_mas(self):
        caso, _ = self._derivado(self.escuela, dni=DNI)

        respuesta = self._como(self.guardia_centro).get(_url("dispositivo-buscar", self.centro.pk), {"dni": DNI})

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["resultado"], "SIN_DERIVACION")  # la app en producción sigue entendiendo el resultado
        self.assertEqual(sorted(cuerpo["caso_abierto"]), CLAVES_CASO_ABIERTO)
        self.assertEqual(cuerpo["caso_abierto"]["id"], caso.pk)
        self.assertEqual(cuerpo["caso_abierto"]["derivada_a"], "Escuela 12")
        self.assertIs(cuerpo["puede_ingresar_con_caso"], True)
        self.assertIsNone(cuerpo["derivacion"], "no se filtra la derivación de otra institución")

    def test_sin_caso_abierto_la_busqueda_no_cambia(self):
        respuesta = self._como(self.guardia_centro).get(_url("dispositivo-buscar", self.centro.pk), {"dni": "29000111"})

        self.assertIsNone(respuesta.json()["caso_abierto"])
        self.assertIs(respuesta.json()["puede_ingresar_con_caso"], False)

    def test_ingresar_igual_con_caso_abierto_es_201_con_ya_tenia_caso_y_cancela_la_derivacion(self):
        caso, derivacion = self._derivado(self.escuela, dni=DNI)

        respuesta = self._post("dispositivo-ingreso-directo", dni=DNI)

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        cuerpo = respuesta.json()
        self.assertIs(cuerpo["ya_tenia_caso"], True)
        self.assertEqual(cuerpo["caso"]["id"], caso.pk)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.CANCELADA)

    def test_ingresar_igual_de_una_familia_nueva_dice_ya_tenia_caso_false(self):
        respuesta = self._post("dispositivo-ingreso-directo", dni="29000111", nombre="Ana", apellido="Paz")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertIs(respuesta.json()["ya_tenia_caso"], False)

    def test_ingresar_con_el_caso_alojado_en_otra_institucion_es_400_con_el_caso_abierto(self):
        caso, derivacion = self._aceptado(dispositivo=self.escuela, dni=DNI)
        CasoEmergencia.objects.filter(pk=caso.pk).update(estado=Estado.ALOJADO)

        respuesta = self._post("dispositivo-ingreso-directo", dni=DNI)

        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertEqual(sorted(cuerpo["caso_abierto"]), CLAVES_CASO_ABIERTO)
        self.assertEqual(cuerpo["caso_abierto"]["id"], caso.pk)
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_avisar_con_caso_abierto_es_201_y_suma_el_aviso_al_caso(self):
        caso, _ = self._derivado(self.escuela, dni=DNI)

        respuesta = self._post("dispositivo-avisar-mesa", dni=DNI)

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertIs(respuesta.json()["ya_tenia_caso"], True)
        self.assertEqual(respuesta.json()["caso"]["id"], caso.pk)
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_el_territorio_que_releva_dos_veces_a_la_familia_recibe_el_caso_existente_y_queda_la_traza(self):
        primera = self._enviar(dni=DNI)
        casos = CasoEmergencia.objects.count()

        segunda = self._enviar(dni=DNI)

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200), segunda.content)
        self.assertIs(segunda.json()["ya_tenia_caso"], True)
        self.assertEqual(segunda.json()["id"], primera.json()["id"])
        self.assertEqual(CasoEmergencia.objects.count(), casos)
        caso = CasoEmergencia.objects.get(pk=primera.json()["id"])
        self.assertIn(Accion.RELEVAMIENTO_REPETIDO, [t.accion for t in TrazaCaso.objects.filter(caso=caso)])

    def test_el_primer_relevamiento_dice_ya_tenia_caso_false(self):
        self.assertIs(self._enviar(dni=DNI).json()["ya_tenia_caso"], False)


# ---------------------------------------------------------------------------
# La web de la guardia: el modal «Esta familia ya tiene un caso abierto»
# ---------------------------------------------------------------------------


class ModalDeLlegadasTests(BaseFamiliaAbierta):
    def _url(self, nombre, *args, dispositivo=None):
        return reverse(f"dispositivos:emergencia_{nombre}", args=[(dispositivo or self.club).pk, *args])

    def _buscar(self, usuario=None):
        self.client.force_login(usuario or self.guardia)
        return self.client.get(self._url("llegadas"), {"dni": DNI})

    def test_con_un_caso_abierto_la_busqueda_muestra_el_modal_con_sus_dos_salidas(self):
        caso, _ = self._derivado(self.escuela, dni=DNI)

        respuesta = self._buscar()

        self.assertContains(respuesta, "Esta familia ya tiene un caso abierto")
        self.assertContains(respuesta, caso.numero)
        self.assertContains(respuesta, "Ingresar con este caso")
        self.assertContains(respuesta, "Avisar a la mesa")
        self.assertContains(respuesta, self._url("ingresar_con_caso"))
        self.assertContains(respuesta, self._url("avisar_con_caso"))
        self.assertNotContains(respuesta, self._url("ingreso_directo"), msg_prefix="el atajo de cargar otro caso")

    def test_sin_caso_abierto_no_hay_modal(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self._url("llegadas"), {"dni": "29000111"})

        self.assertNotContains(respuesta, "Esta familia ya tiene un caso abierto")

    def test_el_modal_dice_donde_esta_derivada_pero_no_muestra_nada_de_la_ficha(self):
        self._derivado(self.escuela, dni=DNI, telefono="3624999999")

        respuesta = self._buscar()

        self.assertContains(respuesta, "Escuela 12")
        self.assertNotContains(respuesta, "3624999999")

    def test_ingresar_con_este_caso_ingresa_a_la_familia_y_lleva_a_las_fichas(self):
        caso, derivacion = self._derivado(self.escuela, dni=DNI)
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self._url("ingresar_con_caso"), {"dni": DNI})

        self.assertRedirects(respuesta, self._url("integrantes", caso.pk), fetch_redirect_response=False)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.CANCELADA)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        self.assertEqual(self._estado(caso), Estado.INGRESO_EN_CURSO)

    def test_avisar_con_este_caso_vuelve_a_llegadas_sin_abrir_otro_caso(self):
        caso, _ = self._derivado(self.escuela, dni=DNI)
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self._url("avisar_con_caso"), {"dni": DNI})

        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        self.assertTrue(CasoEmergencia.objects.get(pk=caso.pk).esperando_en_la_puerta)

    def test_las_salidas_reciben_el_dni_y_no_un_id_de_caso(self):
        """Un id armado a mano no puede sumar a la guardia a un caso que no es el de la familia."""
        ajeno, derivacion = self._derivado(self.escuela, dni="30222333")
        self.client.force_login(self.guardia)

        respuesta = self.client.post(self._url("ingresar_con_caso"), {"dni": DNI, "caso": ajeno.pk, "id": ajeno.pk})

        self.assertEqual(respuesta.status_code, 302)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.PENDIENTE)
        self.assertEqual(self._estado(ajeno), Estado.DERIVADO)

    def test_una_guardia_sin_alcance_no_ingresa_con_el_caso(self):
        caso = self._caso(dni=DNI, origen=Origen.MESA)
        self.client.force_login(self.guardia_escuela)

        respuesta = self.client.post(self._url("ingresar_con_caso"), {"dni": DNI})

        self.assertIn(respuesta.status_code, (302, 403, 404))
        self.assertEqual(self._estado(caso), Estado.EN_GESTION)

    def test_el_formulario_de_ingresar_igual_con_una_familia_con_caso_se_suma_a_ese_caso(self):
        caso, derivacion = self._derivado(self.escuela, dni=DNI)
        self.client.force_login(self.guardia)

        respuesta = self.client.post(
            self._url("ingreso_directo"),
            {"traslado": "BOMBEROS", "dni": DNI, "adultos_f": "1", "adultos_m": "1", "menores_f": "0"},
        )

        self.assertRedirects(respuesta, self._url("integrantes", caso.pk), fetch_redirect_response=False)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        derivacion.refresh_from_db()
        self.assertEqual(derivacion.estado, Derivacion.Estado.CANCELADA)
