"""Módulo Emergencia, PR 5: M1, el envío del Formulario 1 y «mis envíos».

Qué fija: **RU §6 n.° 5 / RN-1.8 / RU-16** —el mismo ``uuid_cliente`` dos veces crea **un**
caso—; **RN-1.2, 1.3, 1.9, 1.12 y RU-18** —total y prioridad del servidor, las validaciones
del paso 3, fotos solo JPEG de hasta 5 MB, dirección obligatoria y la hora del teléfono—; y el
presupuesto de ``casos/mios``. Las claves de cada respuesta están en ``base_emergencia_api``.

El test de mutación ``test_el_mismo_uuid_cliente_dos_veces_crea_un_solo_caso`` se vio en rojo
contra la regla rota antes de quedar verde; el detalle está en su docstring.
"""

import uuid
from datetime import timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext

from core.validators import ADJUNTO_MAX_BYTES, MENSAJE_ADJUNTO_TAMANIO
from legajos.models import Ciudadano
from programas.api.serializers_emergencia import (
    MENSAJE_FOTO_JPEG,
)
from programas.models import (
    AdjuntoCaso,
    CasoEmergencia,
    GrupoFamiliar,
    TrazaCaso,
)
from programas.selectors.emergencia_campo import TOPE_MIS_CASOS, casos_relevados_por
from programas.services import emergencia as servicio
from programas.services import emergencia_alta
from programas.services.emergencia_campo import RELEVADO_EN_FUTURO
from programas.tests.base_emergencia_api import (
    CLAVES_CASO_CREADO,
    CLAVES_FIJAS_DEL_400,
    CLAVES_MI_CASO,
    CLAVES_UUID_EN_USO,
    PNG,
    URL_CASOS,
    URL_MIOS,
    BaseApiEmergencia,
)
from programas.tests.test_emergencia_base import OPERAR, RELEVAR
from programas.tests.test_emergencia_casos import JPEG, T0

Estado = CasoEmergencia.Estado
Origen = CasoEmergencia.Origen
Prioridad = CasoEmergencia.Prioridad


# ---------------------------------------------------------------------------
# Enviar el Formulario 1 (M1)
# ---------------------------------------------------------------------------


class EnviarCasoTests(BaseApiEmergencia):
    def test_crea_el_caso_y_devuelve_las_cuatro_claves(self):
        respuesta = self._enviar(menores_f=2, mayores_m=1, telefono="3624111222", observaciones="Frente a la capilla")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.select_related("grupo").get()
        self.assertEqual(sorted(respuesta.json()), CLAVES_CASO_CREADO)
        self.assertEqual(
            respuesta.json(),
            {"id": caso.pk, "numero": caso.numero, "prioridad": "MEDIA", "total_declarado": 5},
        )
        # RN-1.10: nace NUEVO, sin tomar, de territorio, a nombre del agente.
        self.assertEqual(
            (caso.estado, caso.origen, caso.tomado_por, caso.relevado_por),
            (Estado.NUEVO, Origen.TERRITORIO, None, self.agente),
        )
        self.assertEqual(caso.situacion, {"telefono": "3624111222", "observaciones": "Frente a la capilla"})
        self.assertEqual(TrazaCaso.objects.get(caso=caso).detalle, "Relevado en territorio")

    def test_el_mismo_uuid_cliente_dos_veces_crea_un_solo_caso(self):
        """RU §6 n.° 5 / RN-1.8 / RU-16: el reenvío de la cola sin señal no duplica.

        **Mutación vista en rojo:** con la vista llamando a ``crear_caso`` sin el
        ``uuid_cliente`` —el envío deja de tener identidad— el segundo POST contesta 201 con
        otro ``numero`` y quedan dos casos. Restaurada la llamada, verde. (Romperlo en el
        servicio no alcanza para verlo rojo: sin la búsqueda previa, el ``UNIQUE`` de la
        columna devuelve igual el caso que ya estaba.)
        """
        identificador = uuid.uuid4()
        cuerpo = self._cuerpo(uuid_cliente=identificador, dni="30111222")

        primera = self._como(self.agente).post(URL_CASOS, dict(cuerpo), format="multipart")
        segunda = self._como(self.agente).post(URL_CASOS, dict(cuerpo), format="multipart")

        self.assertEqual(primera.status_code, 201, primera.content)
        self.assertEqual(segunda.status_code, 200, segunda.content)
        self.assertEqual(segunda.json(), primera.json())
        self.assertEqual(sorted(segunda.json()), CLAVES_CASO_CREADO)
        self.assertEqual(CasoEmergencia.objects.count(), 1)
        self.assertEqual(GrupoFamiliar.objects.count(), 1)
        self.assertEqual(TrazaCaso.objects.count(), 1)
        self.assertEqual(CasoEmergencia.objects.get().uuid_cliente, identificador)

    def test_el_reenvio_devuelve_el_caso_aunque_el_cuerpo_ya_no_valide(self):
        """El reintento no vuelve a validar: lo que se creó, se creó (paso 2 de ``crear_caso``)."""
        identificador = uuid.uuid4()
        primera = self._enviar(uuid_cliente=identificador)

        segunda = self._enviar(uuid_cliente=identificador, direccion="", adultos_f=0, adultos_m=0)

        self.assertEqual(segunda.status_code, 200, segunda.content)
        self.assertEqual(segunda.json(), primera.json())

    def test_el_uuid_de_otro_agente_es_409_y_no_devuelve_el_caso_ajeno(self):
        otro = self._usuario("otro_agente", [RELEVAR])
        identificador = uuid.uuid4()
        self._enviar(uuid_cliente=identificador)

        respuesta = self._enviar(otro, uuid_cliente=identificador)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(sorted(respuesta.json()), CLAVES_UUID_EN_USO)
        self.assertEqual(respuesta.json(), {"detail": servicio.UUID_EN_USO, "code": "UUID_EN_USO"})
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_el_409_sale_por_tipo_aunque_cambie_el_texto_del_mensaje(self):
        """La vista atrapa ``UuidEnUso`` por tipo, no compara el texto (hallazgo MINOR del PR #1130).

        **Mutación vista en rojo:** con la vista comparando otra vez ``errores["uuid_cliente"]``
        contra ``[UUID_EN_USO]``, el mensaje cambiado sale como 400 ``VALIDACION``. Restaurada la
        captura por tipo, verde.
        """
        otro = self._usuario("otro_agente", [RELEVAR])
        identificador = uuid.uuid4()
        self._enviar(uuid_cliente=identificador)

        with mock.patch.object(emergencia_alta, "UUID_EN_USO", "Ese identificador ya lo usó otra persona."):
            respuesta = self._enviar(otro, uuid_cliente=identificador)

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(
            respuesta.json(), {"detail": "Ese identificador ya lo usó otra persona.", "code": "UUID_EN_USO"}
        )
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_el_uuid_en_uso_sigue_siendo_un_validation_error_con_su_clave(self):
        """La mesa y los tests que lo atrapan como ``ValidationError`` lo ven igual que antes."""
        error = servicio.UuidEnUso()

        self.assertIsInstance(error, ValidationError)
        self.assertEqual(error.message_dict, {"uuid_cliente": [servicio.UUID_EN_USO]})

    def test_el_reenvio_no_revalida_lo_que_el_serializer_ya_no_rechaza(self):
        """§6: el segundo cuerpo con reglas del Formulario 1 rotas igual devuelve el caso (200).

        Una cantidad negativa y un ``traslado_otro`` de más de 120 caracteres los rechazaría el
        servicio, que no llega a validarlos; antes los frenaba el serializer con un 400.
        """
        identificador = uuid.uuid4()
        primera = self._enviar(uuid_cliente=identificador)

        segunda = self._enviar(
            uuid_cliente=identificador, adultos_f=-1, traslado=GrupoFamiliar.Traslado.OTRA, traslado_otro="x" * 200
        )

        self.assertEqual(primera.status_code, 201, primera.content)
        self.assertEqual(segunda.status_code, 200, segunda.content)
        self.assertEqual(segunda.json(), primera.json())
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_sin_uuid_cliente_es_400(self):
        cuerpo = self._cuerpo()
        del cuerpo["uuid_cliente"]

        respuesta = self._como(self.agente).post(URL_CASOS, cuerpo, format="multipart")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("uuid_cliente", respuesta.json())
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_el_400_trae_code_detail_y_el_detalle_por_campo(self):
        respuesta = self._enviar(direccion="", traslado="")

        self.assertEqual(respuesta.status_code, 400)
        cuerpo = respuesta.json()
        self.assertEqual(set(cuerpo), CLAVES_FIJAS_DEL_400 | {"direccion", "traslado"})
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertEqual(cuerpo["traslado"], ["Elegí la fuerza que traslada."])
        self.assertIsInstance(cuerpo["detail"], str)
        self.assertIn(cuerpo["detail"], cuerpo["non_field_errors"])
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_sin_direccion_no_se_envia_aunque_haya_gps(self):
        """RN-1.12: la dirección escrita es el mínimo."""
        respuesta = self._enviar(direccion="   ", latitud="-27.451", longitud="-58.986", precision_m="12")

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(
            respuesta.json()["direccion"],
            ["Escribí la dirección o una referencia: es el mínimo para ubicar a la familia."],
        )
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_sin_gps_y_con_direccion_se_envia(self):
        respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.get()
        self.assertEqual((caso.latitud, caso.longitud, caso.precision_m), (None, None, None))

    def test_el_gps_se_guarda_con_su_precision(self):
        respuesta = self._enviar(latitud="-27.4512341", longitud="-58.9867891", precision_m="12.4")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.get()
        self.assertEqual((float(caso.latitud), float(caso.longitud), caso.precision_m), (-27.451234, -58.986789, 12))

    def test_las_validaciones_del_paso_3_las_hace_el_servidor(self):
        """RN-1.3: dependientes ≤ total, mayores dependientes ≤ mayores, lactantes ≤ menores."""
        casos = (
            ({"dependientes": 3}, "dependientes"),
            ({"mayores_dependientes": 1}, "mayores_dependientes"),
            ({"lactantes": 1}, "lactantes"),
        )
        for cambios, campo in casos:
            with self.subTest(campo=campo):
                respuesta = self._enviar(**cambios)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(campo, respuesta.json())
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_traslado_otro_tiene_el_tope_del_modelo_y_no_uno_propio(self):
        """El largo de ``traslado_otro`` lo decide el modelo (120), igual que en la mesa.

        **Mutación vista en rojo:** con ``max_length=60`` de vuelta en el serializer, los 80
        caracteres dan 400 con el mensaje de DRF. Restaurado, verde.
        """
        respuesta = self._enviar(traslado=GrupoFamiliar.Traslado.OTRA, traslado_otro="G" * 80)

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(CasoEmergencia.objects.get().grupo.traslado_otro, "G" * 80)

        largo = self._enviar(traslado=GrupoFamiliar.Traslado.OTRA, traslado_otro="G" * 121)

        self.assertEqual(largo.status_code, 400, largo.content)
        cuerpo = largo.json()
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertEqual(set(cuerpo), CLAVES_FIJAS_DEL_400 | {"traslado_otro"})
        self.assertIn("120", cuerpo["traslado_otro"][0])
        self.assertEqual(CasoEmergencia.objects.count(), 1)

    def test_una_cantidad_negativa_la_rechaza_el_servicio_junto_con_los_demas_errores(self):
        """El signo lo valida ``crear_caso`` con su mensaje, en el mismo 400 que el resto.

        **Mutación vista en rojo:** con ``min_value=0`` de vuelta en ``_cantidad`` el 400 sale
        del serializer, con el mensaje de DRF y sin la clave ``direccion``. Restaurado, verde.
        """
        respuesta = self._enviar(adultos_f=-1, direccion="")

        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(set(cuerpo), CLAVES_FIJAS_DEL_400 | {"adultos_f", "direccion"})
        self.assertEqual(cuerpo["adultos_f"], ["No puede ser negativo."])
        self.assertEqual(
            cuerpo["direccion"], ["Escribí la dirección o una referencia: es el mínimo para ubicar a la familia."]
        )
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_sin_personas_no_se_envia(self):
        respuesta = self._enviar(adultos_f=0, adultos_m=0)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["total"], ["Cargá al menos una persona."])

    def test_el_total_y_la_prioridad_que_manda_la_app_se_ignoran(self):
        """RN-1.2 y RN-1.4: los dos son del servidor."""
        respuesta = self._enviar(total=99, total_declarado=99, prioridad="ALTA", estado="CERRADO", numero="X")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(respuesta.json()["total_declarado"], 2)
        self.assertEqual(respuesta.json()["prioridad"], "BAJA")
        caso = CasoEmergencia.objects.select_related("grupo").get()
        self.assertEqual((caso.grupo.total_declarado, caso.prioridad, caso.estado), (2, Prioridad.BAJA, Estado.NUEVO))

    def test_los_avisos_del_multipart_se_leen_como_booleanos(self):
        """En un formulario multipart `false` llega como texto: no puede valer como verdadero."""
        respuesta = self._enviar(embarazo="false", electrodependiente="0", medicacion_critica="", mascotas="true")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.get()
        self.assertEqual(
            caso.necesidades,
            {"embarazo": False, "electrodependiente": False, "medicacion_critica": False, "mascotas": True},
        )
        self.assertEqual(caso.prioridad, Prioridad.BAJA)

    def test_un_aviso_critico_hace_alta_la_prioridad(self):
        self.assertEqual(self._enviar(medicacion_critica="true").json()["prioridad"], "ALTA")

    def test_la_persona_que_no_esta_en_el_legajo_necesita_nombre_y_apellido(self):
        """RN-1.5: alta mínima del responsable."""
        sin_nombre = self._enviar(dni="30555666", nombre="", apellido="")
        con_nombre = self._enviar(dni="30555666", nombre="Rosa", apellido="Benítez")

        self.assertEqual(sin_nombre.status_code, 400)
        self.assertIn("nombre", sin_nombre.json())
        self.assertEqual(con_nombre.status_code, 201, con_nombre.content)
        self.assertEqual(Ciudadano.objects.get(dni="30555666").apellido, "Benítez")

    def test_tambien_acepta_json_cuando_no_hay_fotos(self):
        cuerpo = {"uuid_cliente": str(uuid.uuid4()), **self._datos(mascotas=True)}

        respuesta = self._como(self.agente).post(URL_CASOS, cuerpo, format="json")

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertTrue(CasoEmergencia.objects.get().necesidades["mascotas"])


class RelevadoEnTests(BaseApiEmergencia):
    """RU-18 / RN-1.8: ``relevado_en`` es la única hora del cliente que se guarda."""

    def _relevado_en(self, respuesta):
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        return CasoEmergencia.objects.get(pk=respuesta.json()["id"]).relevado_en

    def test_se_guarda_la_hora_del_telefono_y_creado_es_del_servidor(self):
        hace_dos_horas = T0 - timedelta(hours=2)

        respuesta = self._enviar(relevado_en=hace_dos_horas.isoformat())

        self.assertEqual(self._relevado_en(respuesta), hace_dos_horas)
        self.assertGreater(CasoEmergencia.objects.get().creado, hace_dos_horas)

    def test_un_envio_que_espero_dias_sin_senal_conserva_su_hora(self):
        hace_tres_dias = T0 - timedelta(days=3)

        self.assertEqual(self._relevado_en(self._enviar(relevado_en=hace_tres_dias.isoformat())), hace_tres_dias)

    def test_sin_relevado_en_vale_la_del_servidor(self):
        self.assertEqual(self._relevado_en(self._enviar()), T0)

    def test_dentro_de_la_tolerancia_queda_como_vino(self):
        adelantada = T0 + timedelta(minutes=3)

        self.assertEqual(self._relevado_en(self._enviar(relevado_en=adelantada.isoformat())), adelantada)

    def test_un_reloj_adelantado_unas_horas_se_recorta_a_la_hora_del_servidor(self):
        """Rechazarlo dejaría cada familia de ese teléfono en 400 hasta que le arreglen la hora."""
        adelantada = T0 + timedelta(hours=3)

        self.assertEqual(self._relevado_en(self._enviar(relevado_en=adelantada.isoformat())), T0)

    def test_una_fecha_de_mas_de_un_dia_en_el_futuro_se_rechaza(self):
        respuesta = self._enviar(relevado_en=(T0 + timedelta(days=2)).isoformat())

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["relevado_en"], [RELEVADO_EN_FUTURO])
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_una_fecha_ilegible_se_rechaza(self):
        respuesta = self._enviar(relevado_en="ayer a la tarde")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("relevado_en", respuesta.json())


class FotosDelEnvioTests(BaseApiEmergencia):
    """RN-1.9: hasta dos fotos, JPEG, de hasta 5 MB."""

    def test_las_dos_fotos_quedan_en_el_caso_con_su_tipo(self):
        respuesta = self._enviar(foto_vivienda=self._foto(), foto_acceso=self._foto("acceso.jpeg"))

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        caso = CasoEmergencia.objects.get()
        adjuntos = list(AdjuntoCaso.objects.filter(caso=caso).order_by("tipo"))
        self.assertEqual([adjunto.tipo for adjunto in adjuntos], ["ACCESO", "VIVIENDA"])
        for adjunto in adjuntos:
            self.assertEqual(adjunto.cargado_por, self.agente)
            # RU-17: detrás de login, bajo la carpeta opaca del caso.
            self.assertTrue(adjunto.archivo.name.startswith(f"emergencia/casos/{caso.carpeta_media}/"))

    def test_la_respuesta_no_trae_las_fotos(self):
        """El archivo no vuelve: la app ya lo tiene y ``/media/`` va por sesión."""
        respuesta = self._enviar(foto_vivienda=self._foto())

        self.assertEqual(sorted(respuesta.json()), CLAVES_CASO_CREADO)

    def test_un_png_se_rechaza_aunque_el_modelo_lo_admita(self):
        respuesta = self._enviar(foto_vivienda=self._foto("vivienda.png", PNG, "image/png"))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["foto_vivienda"], [MENSAJE_FOTO_JPEG])
        self.assertEqual(respuesta.json()["code"], "VALIDACION")
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_un_png_renombrado_a_jpg_se_rechaza_por_la_firma(self):
        respuesta = self._enviar(foto_acceso=self._foto("acceso.jpg", PNG))

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["foto_acceso"], [MENSAJE_FOTO_JPEG])
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_un_jpeg_de_mas_de_5_mb_se_rechaza(self):
        pesada = self._foto(contenido=JPEG + b"0" * ADJUNTO_MAX_BYTES)

        respuesta = self._enviar(foto_vivienda=pesada)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["foto_vivienda"], [MENSAJE_ADJUNTO_TAMANIO])
        self.assertEqual(CasoEmergencia.objects.count(), 0)

    def test_un_jpeg_en_el_limite_entra(self):
        justa = self._foto(contenido=JPEG + b"0" * (ADJUNTO_MAX_BYTES - len(JPEG)))

        self.assertEqual(self._enviar(foto_vivienda=justa).status_code, 201)

    def test_la_foto_rechazada_no_deja_caso_ni_gasta_numero(self):
        self._enviar(foto_vivienda=self._foto("vivienda.png", PNG, "image/png"))

        respuesta = self._enviar()

        self.assertEqual(respuesta.status_code, 201)
        self.assertTrue(respuesta.json()["numero"].endswith("-000001"))


# ---------------------------------------------------------------------------
# Mis envíos
# ---------------------------------------------------------------------------


class MisCasosTests(BaseApiEmergencia):
    def test_trae_solo_los_del_agente_del_mas_nuevo_al_mas_viejo(self):
        otro = self._usuario("otro_agente", [RELEVAR])
        primero = self._caso(adultos_f=3)
        self.reloj.avanzar(minutes=5)
        segundo = self._caso()
        self._caso(usuario=otro)

        respuesta = self._como(self.agente).get(URL_MIOS)

        self.assertEqual(respuesta.status_code, 200)
        filas = respuesta.json()
        self.assertEqual([fila["numero"] for fila in filas], [segundo.numero, primero.numero])
        for fila in filas:
            self.assertEqual(sorted(fila), CLAVES_MI_CASO)
        self.assertEqual(filas[1]["total_declarado"], 4)
        self.assertEqual(filas[1]["estado"], "NUEVO")
        self.assertEqual(self._como(otro).get(URL_MIOS).json()[0]["numero"][-1], "3")

    def test_el_estado_sigue_al_caso(self):
        caso = self._caso()
        servicio.tomar_caso(caso, self.operador)

        self.assertEqual(self._como(self.agente).get(URL_MIOS).json()[0]["estado"], "EN_GESTION")

    def test_lo_que_el_mismo_usuario_cargo_desde_la_mesa_no_es_un_envio(self):
        """``relevado_por`` también es quien carga en la mesa: «Mis envíos» son los de territorio."""
        doble = self._sumar_rol(self.agente, [OPERAR], self.programa)
        self._caso(origen=Origen.MESA, usuario=doble)
        de_territorio = self._caso(usuario=doble)

        filas = self._como(doble).get(URL_MIOS).json()

        self.assertEqual([fila["numero"] for fila in filas], [de_territorio.numero])

    def test_sin_envios_es_una_lista_vacia(self):
        self.assertEqual(self._como(self.agente).get(URL_MIOS).json(), [])

    @tag("performance")
    def test_trae_como_mucho_cincuenta_en_una_consulta(self):
        for _ in range(TOPE_MIS_CASOS + 3):
            self._caso()

        with self.assertNumQueries(1):
            casos = list(casos_relevados_por(self.agente))
            totales = [caso.grupo.total_declarado for caso in casos]

        self.assertEqual(len(casos), TOPE_MIS_CASOS)
        self.assertEqual(totales, [2] * TOPE_MIS_CASOS)

    @tag("performance")
    def test_el_endpoint_no_crece_con_los_casos(self):
        cliente = self._como(self.agente)
        self._caso()
        cliente.get(URL_MIOS)  # deja memoizado el programa, que es una clave de proceso
        with CaptureQueriesContext(connection) as con_uno:
            cliente.get(URL_MIOS)
        for _ in range(12):
            self._caso()

        with self.assertNumQueries(len(con_uno)):
            self.assertEqual(len(cliente.get(URL_MIOS).json()), 13)
