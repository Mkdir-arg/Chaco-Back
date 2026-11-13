"""Módulo Emergencia, PR 8: la API M2 (llegada de familias) — integrantes, ficha y mapa de camas (M2-3, M2-4).

Las filas de la familia, la confirmación de cada persona (idempotente por ``uuid_cliente``), la
ficha, el mapa de camas y el 409 con el ``detail`` del servicio cuando el ingreso ya no sigue.

La base (`BaseApiLlegadas`) y las claves exactas de cada respuesta están en ``base_emergencia_api``.
"""

import uuid
from datetime import timedelta

from programas.models import (
    CasoEmergencia,
    Derivacion,
    Estadia,
    IntegranteGrupo,
    Plaza,
    TrazaCaso,
)
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests.base_emergencia_api import (
    CLAVES_CASO_RESUMEN,
    CLAVES_CONFIRMACION,
    CLAVES_FICHA_COMPLETADA,
    CLAVES_INTEGRANTE,
    CLAVES_INTEGRANTE_AGREGADO,
    CLAVES_INTEGRANTE_DETALLE,
    CLAVES_INTEGRANTES,
    CLAVES_MAPA,
    CLAVES_PERSONA_DEL_INTEGRANTE,
    CLAVES_PLAZA_DEL_INTEGRANTE,
    CLAVES_PLAZA_DEL_MAPA,
    CLAVES_SECTOR_CON_PLAZAS,
    CLAVES_SECTOR_DEL_MAPA,
    NO_ENCONTRADO,
    BaseApiLlegadas,
    _url,
)
from programas.tests.test_emergencia_alojar_base import ficha_minima

Estado = CasoEmergencia.Estado


# ---------------------------------------------------------------------------
# Integrantes (M2-3, M2-4)
# ---------------------------------------------------------------------------


class IntegrantesApiTests(BaseApiLlegadas):
    def setUp(self):
        super().setUp()
        self.caso, self.derivacion = self._aceptado()

    def test_la_lista_tiene_claves_exactas_y_el_contador(self):
        self._confirmar_con_el_servicio(self.caso, 1, "30111222")

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrantes", self.caso.pk))

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_INTEGRANTES)
        self.assertEqual(sorted(cuerpo["caso"]), CLAVES_CASO_RESUMEN)
        self.assertEqual((cuerpo["confirmadas"], cuerpo["total_declarado"], cuerpo["declaradas_al_relevar"]), (1, 7, 7))
        primera, segunda = cuerpo["integrantes"][:2]
        self.assertEqual(sorted(primera), CLAVES_INTEGRANTE)
        self.assertEqual(sorted(primera["persona"]), CLAVES_PERSONA_DEL_INTEGRANTE)
        self.assertEqual(sorted(primera["plaza"]), CLAVES_PLAZA_DEL_INTEGRANTE)
        self.assertEqual((primera["n"], primera["estado"], primera["persona"]["dni"]), (1, "CONFIRMADA", "30111222"))
        self.assertEqual((segunda["estado"], segunda["persona"], segunda["plaza"]), ("SIN_CONFIRMAR", None, None))

    def test_antes_de_aceptar_es_409(self):
        caso, _derivacion = self._derivado(dni="30222333")

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrantes", caso.pk))

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["estado_actual"], Estado.DERIVADO)

    def test_cerrado_se_sigue_leyendo(self):
        """La app vuelve a M2-3 después de cerrar: ``CERRADO`` está en ``ESTADOS_CON_INTEGRANTES``."""
        CasoEmergencia.objects.filter(pk=self.caso.pk).update(estado=Estado.CERRADO, cerrado_en=self.reloj())

        lista = self._como(self.guardia_centro).get(_url("caso-integrantes", self.caso.pk))
        una = self._como(self.guardia_centro).get(_url("caso-integrante", self.caso.pk, 1))

        self.assertEqual((lista.status_code, una.status_code), (200, 200))
        self.assertEqual(lista.json()["caso"]["estado"], Estado.CERRADO)

    def test_confirmar_crea_la_estadia_y_devuelve_la_fila(self):
        respuesta = self._confirmar(self.caso, 2, "45111222")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_CONFIRMACION)
        self.assertEqual(sorted(cuerpo["integrante"]), CLAVES_INTEGRANTE)
        self.assertEqual((cuerpo["confirmadas"], cuerpo["total_declarado"], cuerpo["reserva_liberada"]), (1, 7, False))
        self.assertEqual((cuerpo["integrante"]["n"], cuerpo["integrante"]["estado"]), (2, "CONFIRMADA"))
        self.assertTrue(Estadia.objects.activas().filter(ciudadano__dni="45111222").exists())

    def test_confirmar_dos_veces_con_el_mismo_uuid_escribe_una_vez(self):
        """RU-16: el reintento de la app tras perder la respuesta."""
        identificador = uuid.uuid4()
        primera = self._confirmar(self.caso, 2, "45111222", uuid_cliente=identificador)
        estadias, trazas = Estadia.objects.count(), TrazaCaso.objects.count()

        segunda = self._confirmar(self.caso, 2, "45111222", uuid_cliente=identificador)

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200))
        self.assertEqual(segunda.json(), primera.json())
        self.assertEqual((Estadia.objects.count(), TrazaCaso.objects.count()), (estadias, trazas))

    def test_la_web_confirma_y_despues_la_app_recibe_409(self):
        self._confirmar_con_el_servicio(self.caso, 2, "45111222")
        estadias = Estadia.objects.count()

        respuesta = self._confirmar(self.caso, 2, "45111222")

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.json()["estado_actual"], Estado.INGRESO_EN_CURSO)
        self.assertEqual(Estadia.objects.count(), estadias)

    def test_la_ficha_sin_el_minimo_es_400_por_campo_y_no_escribe(self):
        antes = self._foto_del_caso(self.caso)
        cuerpo = {
            "uuid_cliente": str(uuid.uuid4()),
            "plaza_id": self._reservas(self.derivacion)[0].plaza_id,
            "ficha": {"parentesco": {"parentesco": "HIJO"}, "datos_personales": {"dni": "45111222", "nombre": "Juan"}},
        }

        respuesta = self._como(self.guardia_centro).post(
            _url("caso-integrante-confirmar", self.caso.pk, 2), cuerpo, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["code"], "VALIDACION")
        for campo in ("apellido", "sexo", "embarazo", "alergias_graves"):
            self.assertIn(campo, respuesta.json())
        self.assertEqual(self._foto_del_caso(self.caso), antes)

    def test_confirmar_sin_uuid_o_en_una_cama_ocupada_es_400(self):
        ocupada = (
            Plaza.objects.filter(sector__dispositivo=self.centro)
            .exclude(pk__in=[reserva.plaza_id for reserva in self._reservas(self.derivacion)])
            .first()
        )
        self._ocupar_esa(ocupada)
        cliente = self._como(self.guardia_centro)

        sin_uuid = cliente.post(
            _url("caso-integrante-confirmar", self.caso.pk, 2),
            {"ficha": ficha_minima("45111222"), "plaza_id": self._reservas(self.derivacion)[0].plaza_id},
            format="json",
        )
        en_ocupada = self._confirmar(self.caso, 2, "45111222", plaza=ocupada)

        self.assertEqual(sin_uuid.status_code, 400)
        self.assertIn("uuid_cliente", sin_uuid.json())
        self.assertEqual(en_ocupada.status_code, 400)
        self.assertIn("plaza", en_ocupada.json())

    def _ocupar_esa(self, plaza):
        from legajos.models import Ciudadano

        persona = Ciudadano.objects.create(dni="29000111", nombre="Otra", apellido="Persona")
        Estadia.objects.create(
            ciudadano=persona,
            dispositivo=self.centro,
            plaza=plaza,
            fecha_ingreso=self.reloj(),
            clave_alojamiento=Estadia.clave_para(persona),
        )

    def test_agregar_con_el_mismo_uuid_suma_una_sola_fila(self):
        identificador = str(uuid.uuid4())
        cliente = self._como(self.guardia_centro)

        primera = cliente.post(_url("caso-integrantes", self.caso.pk), {"uuid_cliente": identificador}, format="json")
        segunda = cliente.post(_url("caso-integrantes", self.caso.pk), {"uuid_cliente": identificador}, format="json")

        self.assertEqual((primera.status_code, segunda.status_code), (201, 200))
        self.assertEqual(sorted(primera.json()), CLAVES_INTEGRANTE_AGREGADO)
        self.assertEqual(primera.json(), segunda.json())
        self.assertEqual((primera.json()["integrante"]["n"], primera.json()["total_declarado"]), (8, 8))
        self.assertEqual(IntegranteGrupo.objects.filter(grupo_id=self.caso.grupo_id).count(), 8)

    def test_agregar_sin_uuid_es_400(self):
        respuesta = self._como(self.guardia_centro).post(_url("caso-integrantes", self.caso.pk), {}, format="json")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("uuid_cliente", respuesta.json())
        self.assertEqual(IntegranteGrupo.objects.filter(grupo_id=self.caso.grupo_id).count(), 7)

    def test_el_detalle_trae_la_ficha_sin_los_identificadores_de_envio(self):
        self._confirmar(self.caso, 2, "45111222")

        respuesta = self._como(self.guardia_centro).get(_url("caso-integrante", self.caso.pk, 2))

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_INTEGRANTE_DETALLE)
        self.assertEqual(cuerpo["ficha"]["datos_personales"]["dni"], "45111222")
        self.assertNotIn("uuid_cliente", cuerpo["ficha"])
        self.assertEqual(len(cuerpo["secciones_incompletas"]), 5)

    def test_el_detalle_de_una_persona_que_no_es_de_la_familia_es_404(self):
        respuesta = self._como(self.guardia_centro).get(_url("caso-integrante", self.caso.pk, 99))

        self.assertEqual((respuesta.status_code, respuesta.json()), (404, NO_ENCONTRADO))

    def test_completar_la_ficha_con_patch(self):
        self._confirmar(self.caso, 2, "45111222")
        secciones = {seccion: {"sin_datos": True} for seccion in servicio.SECCIONES_OPCIONALES}
        secciones["educacion"] = {"nivel_educativo": "PRIMARIO", "asiste_escuela": True}

        respuesta = self._como(self.guardia_centro).patch(
            _url("caso-integrante", self.caso.pk, 2), {"ficha": secciones}, format="json"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(sorted(respuesta.json()), CLAVES_FICHA_COMPLETADA)
        self.assertEqual(respuesta.json(), {"ficha_completa": True, "secciones_incompletas": []})
        fila = IntegranteGrupo.objects.get(grupo_id=self.caso.grupo_id, orden=2)
        self.assertTrue(fila.ficha_completa)
        self.assertEqual(fila.ficha["educacion"]["nivel_educativo"], "PRIMARIO")

    def test_completar_la_ficha_de_alguien_sin_confirmar_es_400(self):
        respuesta = self._como(self.guardia_centro).patch(
            _url("caso-integrante", self.caso.pk, 3), {"ficha": {"educacion": {"sin_datos": True}}}, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("orden", respuesta.json())


class IngresoQueYaNoSigueApiTests(BaseApiLlegadas):
    """El 409 cuando el ingreso ya no está: **el mismo** ``{detail, estado_actual}`` al leer y al escribir.

    El ``detail`` es el de ``_por_que_ya_no`` del servicio (RU-20): dice qué pasó y qué hacer.
    Lo arma ``ingreso_sin_candado`` para el GET y ``_abrir_ingreso`` —que la usa en su paso 1—
    para el POST, así que no hay un texto por vista. **Mutación vista en rojo**: con el texto
    propio que tenía la vista del GET («todavía no se aceptó o ya no sigue…»), los dos tests
    fallan en la igualdad del GET.
    """

    def _leer_y_escribir(self, caso):
        cliente = self._como(self.guardia_centro)
        return (
            cliente.get(_url("caso-integrantes", caso.pk)),
            cliente.get(_url("caso-integrante", caso.pk, 1)),
            cliente.post(_url("caso-integrantes", caso.pk), {"uuid_cliente": str(uuid.uuid4())}, format="json"),
        )

    def _afirmar_el_mismo_409(self, caso, esperado):
        antes = self._foto_del_caso(caso)

        respuestas = self._leer_y_escribir(caso)

        for respuesta in respuestas:
            with self.subTest(metodo=respuesta.request["REQUEST_METHOD"], ruta=respuesta.request["PATH_INFO"]):
                self.assertEqual(respuesta.status_code, 409, respuesta.content)
                self.assertEqual(respuesta.json(), esperado)
        self.assertEqual(self._foto_del_caso(caso), antes)

    def test_la_derivacion_vencida_dice_a_que_hora_vencio(self):
        caso, derivacion = self._derivado()
        Derivacion.objects.filter(pk=derivacion.pk).update(vence_en=derivacion.creado - timedelta(minutes=1))
        vencida = mesa.vencer_derivacion(Derivacion.objects.get(pk=derivacion.pk))
        self.assertEqual(vencida.estado, Derivacion.Estado.VENCIDA)

        self._afirmar_el_mismo_409(
            caso, {"detail": servicio.mensaje_vencida(vencida), "estado_actual": Estado.EN_GESTION}
        )

    def test_la_derivacion_cancelada_por_la_mesa_lo_dice(self):
        caso, derivacion = self._derivado()
        mesa.cancelar_derivacion(derivacion, self.operador, "La familia se fue con parientes.")

        self._afirmar_el_mismo_409(
            caso,
            {
                "detail": "La mesa canceló la derivación. Si la familia está en la puerta, avisale a la mesa.",
                "estado_actual": Estado.EN_GESTION,
            },
        )


# ---------------------------------------------------------------------------
# Mapa de plazas
# ---------------------------------------------------------------------------


class PlazasApiTests(BaseApiLlegadas):
    def test_el_mapa_marca_las_de_la_familia_y_tiene_claves_exactas(self):
        caso, derivacion = self._aceptado(plazas=3)
        Plaza.objects.filter(
            pk=Plaza.objects.filter(sector__dispositivo=self.centro).order_by("-codigo").first().pk
        ).update(estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Rota")

        respuesta = self._como(self.guardia_centro).get(_url("dispositivo-plazas", self.centro.pk), {"caso": caso.pk})

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), CLAVES_MAPA)
        self.assertEqual(cuerpo["caso"], caso.pk)
        (sector,) = cuerpo["sectores"]
        self.assertEqual(sorted(sector), CLAVES_SECTOR_CON_PLAZAS)
        self.assertEqual(sorted(sector["sector"]), CLAVES_SECTOR_DEL_MAPA)
        self.assertEqual({sorted(plaza).__repr__() for plaza in sector["plazas"]}, {repr(CLAVES_PLAZA_DEL_MAPA)})
        estados = [plaza["estado"] for plaza in sector["plazas"]]
        self.assertEqual(estados.count("RESERVADA_FAMILIA"), 3)
        self.assertEqual(estados.count("FUERA_SERVICIO"), 1)
        self.assertEqual(estados.count("LIBRE"), 5)
        self.assertEqual((sector["total"], sector["libres"], sector["reservadas_familia"]), (9, 5, 3))
        reservadas = {reserva.plaza_id for reserva in self._reservas(derivacion)}
        self.assertEqual({p["id"] for p in sector["plazas"] if p["estado"] == "RESERVADA_FAMILIA"}, reservadas)

    def test_las_de_otra_familia_salen_reservadas_sin_decir_de_quien(self):
        self._aceptado(plazas=3)
        otro, _derivacion = self._aceptado(dni="30222333", menores_f=0, menores_m=0)

        cuerpo = (
            self._como(self.guardia_centro).get(_url("dispositivo-plazas", self.centro.pk), {"caso": otro.pk}).json()
        )

        plazas = cuerpo["sectores"][0]["plazas"]
        self.assertEqual(sum(plaza["estado"] == "RESERVADA" for plaza in plazas), 3)
        self.assertEqual(sum(plaza["estado"] == "RESERVADA_FAMILIA" for plaza in plazas), 2)
        self.assertNotIn("Benítez", str([plaza for plaza in plazas if plaza["estado"] == "RESERVADA"]))

    def test_sin_caso_ninguna_es_de_la_familia_y_un_caso_ilegible_es_404(self):
        self._aceptado(plazas=3)
        cliente = self._como(self.guardia_centro)

        sin_caso = cliente.get(_url("dispositivo-plazas", self.centro.pk)).json()
        ilegible = cliente.get(_url("dispositivo-plazas", self.centro.pk), {"caso": "abc"})

        self.assertIsNone(sin_caso["caso"])
        self.assertNotIn("RESERVADA_FAMILIA", [plaza["estado"] for plaza in sin_caso["sectores"][0]["plazas"]])
        self.assertEqual(ilegible.status_code, 404)
