"""Cambio 614: ingresar a una persona en una cama desde la app de campo.

Tres extremos bajo ``/api/emergencia/dispositivos/<d>/``: ``ingreso/persona/?dni=`` (paso 1), ``ingreso/formulario/``
(paso 2) e ``ingresar/`` (paso 3). El ingreso usa el servicio de la web (``confirmar_ingreso``): acá se fija el
contrato HTTP, el alcance, las capacidades y que el alta de la persona, la estadía y las respuestas del formulario
entran juntas o no entran.

**Mutaciones vistas en rojo** (restauradas después):

* Alcance: con ``_VistaDeIngreso._dispositivo`` tomando ``Dispositivo.objects`` en vez de
  ``dispositivos_en_alcance(..., CAP_VER)``, el dispositivo ajeno deja de dar 404 y
  ``test_el_dispositivo_de_otra_institucion_es_404`` falla (en los tres extremos).
* Capacidad: sin la comprobación de ``puede_operar_dispositivo``/``puede(ciudadano.ver)`` en ``_dispositivo``,
  ``test_sin_admitir_es_403`` y ``test_sin_ciudadano_ver_es_403`` fallan.
* Tope: sin ``throttle_classes``/``check_throttles`` en ``IngresoPersonaView``, ``test_el_segundo_dni_da_429`` falla
  (la consulta por DNI del ingreso era una enumeración del padrón sin tope, SEC-25).
"""

from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone

from legajos.models import Ciudadano
from programas.api.throttles import ConsultaPersonasThrottle
from programas.models import (
    Dispositivo,
    Edificio,
    Estadia,
    ItemDiseno,
    MomentoFormulario,
    Plaza,
    ReservaPlaza,
    RespuestasIngresoEstadia,
)
from programas.services import constructor, estadias
from programas.services.formularios_tipo import crear_formulario
from programas.tests.base_emergencia_api import NO_ENCONTRADO, BaseApiEmergencia, _url

User = get_user_model()

VER, ADMITIR, CIUDADANO, CREAR = "dispositivo.ver", "dispositivo.admitir", "ciudadano.ver", "ciudadano.crear"
PERSONA_NUEVA = {
    "dni": "40111222",
    "nombre": "Lucía",
    "apellido": "Ferreyra",
    "sexo": "F",
    "fecha_nacimiento": "1990-05-17",
}


class BaseIngresoApi(BaseApiEmergencia):
    def setUp(self):
        super().setUp()
        self.edificio = Edificio.objects.create(codigo="EDI-C", nombre="Edificio del club")
        self.edificio.dispositivos.add(self.club)
        self.club.sectores.update(edificio=self.edificio)
        self.operador = self._guardia("operador", [VER, ADMITIR, CIUDADANO, CREAR], [self.club])
        self.plaza = Plaza.objects.get(sector__dispositivo=self.club, codigo="C001")
        self.otra_plaza = Plaza.objects.get(sector__dispositivo=self.club, codigo="C002")
        self.persona = Ciudadano.objects.create(dni="30111222", nombre="Rosa", apellido="Benítez")
        self.admin = User.objects.create_superuser("admin_ingreso_api", password="x")

    # --- Helpers ------------------------------------------------------------------------------

    def _ingresar(self, usuario=None, dispositivo=None, **cuerpo):
        dispositivo = dispositivo or self.club
        cuerpo.setdefault("plaza_id", self.plaza.pk)
        return self._como(usuario or self.operador).post(
            _url("dispositivo-ingresar", dispositivo.pk), cuerpo, format="json"
        )

    def _persona(self, dni, usuario=None, dispositivo=None):
        return self._como(usuario or self.operador).get(
            _url("ingreso-persona", (dispositivo or self.club).pk), {"dni": dni}
        )

    def _formulario_get(self, usuario=None, dispositivo=None):
        return self._como(usuario or self.operador).get(_url("ingreso-formulario", (dispositivo or self.club).pk))

    def _mutar(self, diseno, operacion):
        constructor.mutar(diseno, self.admin, operacion)
        diseno.refresh_from_db()

    def _con_formulario(self, *, constancia=None):
        """El formulario de INGRESO del tipo: pertenencias (número, obligatorio), observaciones (texto) y, si se
        pide, una constancia (archivo) obligatoria (``True``) u opcional (``False``)."""
        diseno = crear_formulario(self.club.tipo, MomentoFormulario.INGRESO, self.admin)
        self._mutar(
            diseno,
            lambda: constructor.crear_grupo(
                diseno, {"etiqueta": "Datos del ingreso", "subtitulo": "", "canal": "ambos"}
            ),
        )
        grupo = diseno.items.get(tipo=ItemDiseno.Tipo.GRUPO)
        campos = [("Cantidad de pertenencias", "INT", True), ("Observaciones", "STRING", False)]
        if constancia is not None:
            campos.append(("Constancia", "ARCHIVO", constancia))
        for texto, tipo, obligatorio in campos:
            propio = {"texto": texto, "tipo": tipo, "opciones": [], "presentacion": "LISTA", "obligatorio": obligatorio}
            self._mutar(diseno, lambda: constructor.crear_propio(diseno, grupo, {"propio": propio, "canal": "ambos"}))
        self.diseno = diseno
        return diseno

    def _clave(self, texto):
        return self.diseno.items.get(tipo=ItemDiseno.Tipo.CAMPO, propio__texto=texto).clave

    def _solo_ve_el_club(self, nombre):
        """Admite en otro dispositivo (abre el módulo) pero en el club solo ve: el 403 es de capacidad, no de módulo."""
        otro = self._dispositivo(f"Otro de {nombre}", camas=1)
        usuario = self._guardia(nombre, [VER, CIUDADANO], [self.club])
        return self._sumar_rol(usuario, [VER, ADMITIR, CIUDADANO], self.dispositivos, [otro])

    def _alojar(self, persona, plaza):
        return Estadia.objects.create(
            ciudadano=persona,
            dispositivo=self.club,
            plaza=plaza,
            fecha_ingreso=timezone.now() - timedelta(days=1),
            clave_alojamiento=Estadia.clave_para(persona),
        )

    @staticmethod
    def _plazas_del_mapa(mapa):
        assert mapa is not None and mapa["sectores"], mapa
        return {plaza["codigo"]: plaza for sector in mapa["sectores"] for plaza in sector["plazas"]}


class IngresarTests(BaseIngresoApi):
    # --- Felices ---------------------------------------------------------------------------

    def test_ingresa_a_una_persona_del_padron(self):
        respuesta = self._ingresar(ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(sorted(cuerpo), ["estadia_id", "mapa", "ok"])
        self.assertTrue(cuerpo["ok"])
        estadia = Estadia.objects.get(pk=cuerpo["estadia_id"])
        self.assertEqual((estadia.ciudadano, estadia.plaza, estadia.dispositivo), (self.persona, self.plaza, self.club))
        self.assertTrue(estadia.activa)
        self.assertEqual(estadia.ingresada_por, self.operador)
        celda = self._plazas_del_mapa(cuerpo["mapa"])["C001"]
        self.assertEqual(celda["estado"], "ocupada")
        self.assertEqual(celda["persona"]["dni"], "30111222")
        self.assertNotIn("ingresar", celda["acciones"])

    def test_da_de_alta_a_la_persona_nueva_con_sexo_y_fecha(self):
        respuesta = self._ingresar(persona_nueva=PERSONA_NUEVA)
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        ciudadano = Ciudadano.objects.get(dni="40111222")
        self.assertEqual((ciudadano.nombre, ciudadano.apellido), ("Lucía", "Ferreyra"))
        self.assertEqual(ciudadano.genero, "F")
        self.assertEqual(ciudadano.fecha_nacimiento, date(1990, 5, 17))
        self.assertEqual(ciudadano.estado_renaper, "")
        estadia = Estadia.objects.get(pk=respuesta.json()["estadia_id"])
        self.assertEqual(estadia.ciudadano, ciudadano)

    def test_el_alta_acepta_la_persona_sin_sexo_ni_fecha(self):
        """Lo que el modelo exige es DNI, nombre y apellido; sexo y fecha de nacimiento son opcionales."""
        nueva = {"dni": "40111222", "nombre": "Lucía", "apellido": "Ferreyra"}
        respuesta = self._ingresar(persona_nueva=nueva)
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        ciudadano = Ciudadano.objects.get(dni="40111222")
        self.assertEqual(ciudadano.genero, "")
        self.assertIsNone(ciudadano.fecha_nacimiento)

    def test_persona_nueva_con_dni_del_padron_usa_ese_legajo(self):
        """Un DNI que ya está en el padrón no se duplica ni se pisa con los datos que manda la app."""
        antes = Ciudadano.objects.count()
        nueva = {**PERSONA_NUEVA, "dni": "30.111.222", "nombre": "Otra", "apellido": "Persona"}
        respuesta = self._ingresar(persona_nueva=nueva)
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(Ciudadano.objects.count(), antes)
        self.persona.refresh_from_db()
        self.assertEqual((self.persona.nombre, self.persona.apellido), ("Rosa", "Benítez"))
        self.assertEqual(Estadia.objects.get(pk=respuesta.json()["estadia_id"]).ciudadano, self.persona)

    def test_la_persona_nueva_usa_el_legajo_aunque_no_pueda_crear(self):
        """Dar de alta pide ``ciudadano.crear``; usar un legajo que ya existe, no."""
        sin_crear = self._guardia("sin_crear", [VER, ADMITIR, CIUDADANO], [self.club])
        respuesta = self._ingresar(usuario=sin_crear, persona_nueva={**PERSONA_NUEVA, "dni": "30111222"})
        self.assertEqual(respuesta.status_code, 201, respuesta.content)

    def test_la_cama_guardada_para_la_persona_es_suya(self):
        estadias.reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador)
        respuesta = self._ingresar(ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertFalse(ReservaPlaza.objects.abiertas().filter(plaza=self.plaza).exists())

    # --- Formulario de ingreso ---------------------------------------------------------------

    def test_sin_formulario_no_se_exige_ninguno(self):
        respuesta = self._ingresar(ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())

    def test_con_formulario_guarda_las_respuestas(self):
        diseno = self._con_formulario()
        respuesta = self._ingresar(
            ciudadano_id=self.persona.pk,
            formulario={
                "version": diseno.version,
                "respuestas": {
                    self._clave("Cantidad de pertenencias"): 3,
                    self._clave("Observaciones"): "Llega con mochila",
                },
            },
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        guardadas = RespuestasIngresoEstadia.objects.get(estadia_id=respuesta.json()["estadia_id"])
        self.assertEqual(guardadas.diseno, diseno)
        self.assertEqual(guardadas.version, diseno.version)
        self.assertEqual(str(guardadas.respuestas[self._clave("Cantidad de pertenencias")]), "3")
        self.assertEqual(guardadas.respuestas[self._clave("Observaciones")], "Llega con mochila")

    def test_un_obligatorio_sin_responder_es_400_y_no_escribe_nada(self):
        diseno = self._con_formulario()
        respuesta = self._ingresar(
            persona_nueva=PERSONA_NUEVA,
            formulario={"version": diseno.version, "respuestas": {self._clave("Observaciones"): "Sin dato"}},
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertIn(self._clave("Cantidad de pertenencias"), cuerpo["claves"])
        self.assertFalse(Estadia.objects.exists())
        self.assertFalse(Ciudadano.objects.filter(dni="40111222").exists())

    def test_sin_el_bloque_del_formulario_tambien_se_exigen_los_obligatorios(self):
        self._con_formulario()
        respuesta = self._ingresar(ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertFalse(Estadia.objects.exists())

    def test_un_valor_de_tipo_invalido_es_400(self):
        diseno = self._con_formulario()
        respuesta = self._ingresar(
            ciudadano_id=self.persona.pk,
            formulario={"version": diseno.version, "respuestas": {self._clave("Cantidad de pertenencias"): "muchas"}},
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertIn(self._clave("Cantidad de pertenencias"), respuesta.json()["claves"])

    def test_la_version_vieja_del_formulario_es_409(self):
        diseno = self._con_formulario()
        respuesta = self._ingresar(
            ciudadano_id=self.persona.pk,
            formulario={
                "version": diseno.version - 1,
                "respuestas": {self._clave("Cantidad de pertenencias"): 3},
            },
        )
        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "FORMULARIO_CAMBIO")
        self.assertFalse(Estadia.objects.exists())

    def test_mandar_un_formulario_que_el_tipo_ya_no_tiene_es_409(self):
        respuesta = self._ingresar(ciudadano_id=self.persona.pk, formulario={"version": 1, "respuestas": {}})
        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "FORMULARIO_CAMBIO")

    def test_un_archivo_obligatorio_manda_el_ingreso_al_backoffice(self):
        diseno = self._con_formulario(constancia=True)
        respuesta = self._ingresar(
            ciudadano_id=self.persona.pk,
            formulario={"version": diseno.version, "respuestas": {self._clave("Cantidad de pertenencias"): 3}},
        )
        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertEqual(
            respuesta.json(), {"detail": "Este ingreso se hace desde el backoffice.", "code": "INGRESO_CON_ARCHIVO"}
        )
        self.assertFalse(Estadia.objects.exists())

    def test_un_archivo_opcional_se_omite(self):
        diseno = self._con_formulario(constancia=False)
        respuesta = self._ingresar(
            ciudadano_id=self.persona.pk,
            formulario={
                "version": diseno.version,
                "respuestas": {
                    self._clave("Cantidad de pertenencias"): 3,
                    # Aunque la app diga «lo adjunté», no hay archivo: no se guarda esa clave.
                    self._clave("Constancia"): {"archivo_adjunto": True, "nombre": "c.pdf"},
                },
            },
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        guardadas = RespuestasIngresoEstadia.objects.get(estadia_id=respuesta.json()["estadia_id"])
        self.assertNotIn(self._clave("Constancia"), guardadas.respuestas)

    # --- Reglas de fondo -----------------------------------------------------------------------

    def test_la_cama_ocupada_es_400_y_no_deja_legajo_huerfano(self):
        self._alojar(Ciudadano.objects.create(dni="30999888", nombre="Ana", apellido="Gómez"), self.plaza)
        respuesta = self._ingresar(persona_nueva=PERSONA_NUEVA)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertIn("plaza_id", cuerpo)
        self.assertFalse(Ciudadano.objects.filter(dni="40111222").exists())

    def test_la_cama_de_otro_dispositivo_es_400(self):
        otro = self._dispositivo("Otro club", camas=2)
        plaza_ajena = Plaza.objects.filter(sector__dispositivo=otro).first()
        respuesta = self._ingresar(ciudadano_id=self.persona.pk, plaza_id=plaza_ajena.pk)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertIn("plaza_id", respuesta.json())
        self.assertFalse(Estadia.objects.exists())

    def test_la_cama_reservada_para_otra_persona_es_400(self):
        otra = Ciudadano.objects.create(dni="30777666", nombre="Luz", apellido="Reyes")
        estadias.reservar_plaza(plaza=self.plaza, ciudadano=otra, usuario=self.operador)
        respuesta = self._ingresar(ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertIn("plaza_id", respuesta.json())

    def test_la_persona_ya_alojada_es_400_con_un_mensaje_claro(self):
        self._alojar(self.persona, self.otra_plaza)
        respuesta = self._ingresar(ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertIn("ya figura alojada", cuerpo["detail"])
        self.assertEqual(Estadia.objects.filter(ciudadano=self.persona).count(), 1)

    def test_si_falla_a_mitad_no_queda_ni_el_legajo_ni_la_estadia(self):
        """El alta, la estadía y las respuestas son una sola transacción."""
        diseno = self._con_formulario()
        cuerpo = {
            "persona_nueva": PERSONA_NUEVA,
            "formulario": {"version": diseno.version, "respuestas": {self._clave("Cantidad de pertenencias"): 3}},
        }
        with mock.patch("programas.services.ingreso.guardar_respuestas_ingreso", side_effect=ValidationError("falló")):
            respuesta = self._ingresar(**cuerpo)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertFalse(Ciudadano.objects.filter(dni="40111222").exists())
        self.assertFalse(Estadia.objects.exists())
        self.assertFalse(RespuestasIngresoEstadia.objects.exists())
        self.assertEqual(self._ingresar(**cuerpo).status_code, 201)

    # --- Errores del cuerpo ---------------------------------------------------------------------

    def test_sin_persona_es_400(self):
        respuesta = self._ingresar()
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertIn("ciudadano_id", respuesta.json())

    def test_las_dos_formas_de_indicar_a_la_persona_es_400(self):
        respuesta = self._ingresar(ciudadano_id=self.persona.pk, persona_nueva=PERSONA_NUEVA)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)

    def test_una_persona_inexistente_es_400(self):
        respuesta = self._ingresar(ciudadano_id=999999)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertIn("ciudadano_id", respuesta.json())

    def test_los_errores_del_alta_van_por_campo(self):
        casos = {
            "dni": {**PERSONA_NUEVA, "dni": "123"},
            "apellido": {**PERSONA_NUEVA, "apellido": ""},
            "nombre": {key: valor for key, valor in PERSONA_NUEVA.items() if key != "nombre"},
            "sexo": {**PERSONA_NUEVA, "sexo": "Z"},
            "fecha_nacimiento": {**PERSONA_NUEVA, "fecha_nacimiento": (date.today() + timedelta(days=3)).isoformat()},
        }
        for campo, nueva in casos.items():
            with self.subTest(campo=campo):
                respuesta = self._ingresar(persona_nueva=nueva)
                self.assertEqual(respuesta.status_code, 400, respuesta.content)
                self.assertEqual(respuesta.json()["code"], "VALIDACION")
                self.assertIn(campo, respuesta.json())
        self.assertFalse(Estadia.objects.exists())

    # --- Alcance y capacidades -----------------------------------------------------------------

    def test_sin_admitir_es_403(self):
        solo_ve = self._solo_ve_el_club("solo_ve")
        respuesta = self._ingresar(usuario=solo_ve, ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 403, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "SIN_PERMISO")
        self.assertFalse(Estadia.objects.exists())

    def test_sin_ciudadano_ver_es_403(self):
        sin_ver_personas = self._guardia("sin_ver_personas", [VER, ADMITIR], [self.club])
        respuesta = self._ingresar(usuario=sin_ver_personas, ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 403, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "SIN_PERMISO")

    def test_dar_de_alta_sin_ciudadano_crear_es_403_y_no_escribe(self):
        sin_crear = self._guardia("sin_crear", [VER, ADMITIR, CIUDADANO], [self.club])
        respuesta = self._ingresar(usuario=sin_crear, persona_nueva=PERSONA_NUEVA)
        self.assertEqual(respuesta.status_code, 403, respuesta.content)
        self.assertFalse(Ciudadano.objects.filter(dni="40111222").exists())
        self.assertFalse(Estadia.objects.exists())

    def test_el_dispositivo_de_otra_institucion_es_404(self):
        otro = self._dispositivo("Otro club", camas=2)
        plaza_ajena = Plaza.objects.filter(sector__dispositivo=otro).first()
        respuesta = self._ingresar(dispositivo=otro, ciudadano_id=self.persona.pk, plaza_id=plaza_ajena.pk)
        self.assertEqual(respuesta.status_code, 404, respuesta.content)
        self.assertEqual(respuesta.json(), NO_ENCONTRADO)
        inexistente = self._como(self.operador).post(_url("dispositivo-ingresar", 999999), {}, format="json")
        self.assertEqual(inexistente.status_code, 404)
        self.assertEqual(inexistente.json(), respuesta.json())
        self.assertEqual(self._persona("30111222", dispositivo=otro).status_code, 404)
        self.assertEqual(self._formulario_get(dispositivo=otro).status_code, 404)
        self.assertFalse(Estadia.objects.exists())

    def test_un_dispositivo_que_no_esta_activo_se_rechaza(self):
        Dispositivo.objects.filter(pk=self.club.pk).update(estado=Dispositivo.Estado.INACTIVO)
        respuesta = self._ingresar(ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "VALIDACION")
        self.assertIn("dispositivo", respuesta.json())
        self.assertFalse(Estadia.objects.exists())

    def test_un_rol_de_becas_no_abre_el_ingreso(self):
        respuesta = self._ingresar(usuario=self.territorial_becas, ciudadano_id=self.persona.pk)
        self.assertEqual(respuesta.status_code, 403, respuesta.content)
        self.assertEqual(respuesta.json()["code"], "SIN_MODULO")


class IngresoPersonaTopeTests(BaseIngresoApi):
    """SEC-25: la consulta de un DNI descuenta de la cubeta ``personas_campo``, la de la consulta de identidad."""

    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_el_segundo_dni_da_429(self, _rate):
        self.assertEqual(self._persona("30111222").status_code, 200)

        segunda = self._persona("40111222")

        self.assertEqual(segunda.status_code, 429)
        self.assertIn("Retry-After", segunda)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_lo_que_se_rechaza_no_gasta_la_cubeta(self, _rate):
        for dni in ("", "abc", "123"):
            self.assertEqual(self._persona(dni).status_code, 400)
        self.assertEqual(
            self._persona("30111222", dispositivo=self._dispositivo("Otro club", camas=1)).status_code, 404
        )

        self.assertEqual(self._persona("30111222").status_code, 200)

    @mock.patch.object(ConsultaPersonasThrottle, "get_rate", return_value="1/hour")
    def test_la_cubeta_es_por_usuario(self, _rate):
        self.assertEqual(self._persona("30111222").status_code, 200)
        self.assertEqual(self._persona("30111222").status_code, 429)
        otro = self._guardia("operador_tope", [VER, ADMITIR, CIUDADANO, CREAR], [self.club])
        self.assertEqual(self._persona("30111222", usuario=otro).status_code, 200)


class IngresoPersonaTests(BaseIngresoApi):
    def test_no_esta_en_el_padron(self):
        respuesta = self._persona("40111222")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json(), {"encontrada": False})

    def test_esta_en_el_padron(self):
        respuesta = self._persona("30.111.222")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(
            respuesta.json(),
            {
                "encontrada": True,
                "persona": {"id": self.persona.pk, "dni": "30111222", "nombre_completo": "Rosa Benítez"},
                "alojada": False,
                "alojamiento": None,
                "plaza_reservada_id": None,
            },
        )

    def test_dice_donde_esta_alojada(self):
        self._alojar(self.persona, self.otra_plaza)
        cuerpo = self._persona("30111222").json()
        self.assertTrue(cuerpo["alojada"])
        self.assertTrue(cuerpo["alojamiento"]["dentro_del_alcance"])
        self.assertEqual(cuerpo["alojamiento"]["dispositivo"], "Club Sarmiento")
        self.assertEqual(cuerpo["alojamiento"]["plaza"], "C002")
        self.assertIn("ya figura alojada", cuerpo["alojamiento"]["mensaje"])

    def test_una_estadia_fuera_del_alcance_no_cuenta_donde(self):
        otro = self._dispositivo("Otro club", camas=2)
        Estadia.objects.create(
            ciudadano=self.persona,
            dispositivo=otro,
            plaza=Plaza.objects.filter(sector__dispositivo=otro).first(),
            fecha_ingreso=timezone.now() - timedelta(days=1),
            clave_alojamiento=Estadia.clave_para(self.persona),
        )
        cuerpo = self._persona("30111222").json()
        self.assertTrue(cuerpo["alojada"])
        self.assertFalse(cuerpo["alojamiento"]["dentro_del_alcance"])
        self.assertEqual(cuerpo["alojamiento"]["dispositivo"], "")
        self.assertNotIn("Otro club", str(cuerpo))

    def test_trae_la_cama_que_la_persona_tiene_guardada(self):
        estadias.reservar_plaza(plaza=self.otra_plaza, ciudadano=self.persona, usuario=self.operador)
        self.assertEqual(self._persona("30111222").json()["plaza_reservada_id"], self.otra_plaza.pk)

    def test_un_dni_invalido_es_400(self):
        for dni in ("", "abc", "123"):
            with self.subTest(dni=dni):
                respuesta = self._persona(dni)
                self.assertEqual(respuesta.status_code, 400, respuesta.content)
                self.assertEqual(respuesta.json()["code"], "VALIDACION")
                self.assertIn("dni", respuesta.json())

    def test_sin_capacidad_es_403_y_no_dice_si_existe(self):
        solo_ve = self._solo_ve_el_club("solo_ve")
        existente = self._persona("30111222", usuario=solo_ve)
        inexistente = self._persona("40111222", usuario=solo_ve)
        self.assertEqual((existente.status_code, inexistente.status_code), (403, 403))
        self.assertEqual(existente.json(), inexistente.json())


class IngresoFormularioTests(BaseIngresoApi):
    def test_sin_formulario(self):
        respuesta = self._formulario_get()
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json(), {"formulario": None})

    def test_con_formulario_viaja_en_el_formato_de_los_relevamientos(self):
        diseno = self._con_formulario()
        cuerpo = self._formulario_get().json()["formulario"]
        self.assertEqual(sorted(cuerpo), ["definicion", "requiere_archivo", "version"])
        self.assertEqual(cuerpo["version"], diseno.version)
        self.assertEqual(sorted(cuerpo["definicion"]), ["canal", "destinos_siis", "items", "version"])
        claves = [campo["clave"] for grupo in cuerpo["definicion"]["items"] for campo in grupo["items"]]
        self.assertEqual(claves, [self._clave("Cantidad de pertenencias"), self._clave("Observaciones")])
        self.assertFalse(cuerpo["requiere_archivo"])

    def test_avisa_si_pide_un_archivo_obligatorio(self):
        self._con_formulario(constancia=True)
        self.assertTrue(self._formulario_get().json()["formulario"]["requiere_archivo"])

    def test_un_archivo_opcional_no_lo_manda_al_backoffice(self):
        self._con_formulario(constancia=False)
        self.assertFalse(self._formulario_get().json()["formulario"]["requiere_archivo"])

    def test_sin_capacidad_es_403(self):
        solo_ve = self._solo_ve_el_club("solo_ve")
        self.assertEqual(self._formulario_get(usuario=solo_ve).status_code, 403)


class AccionEnElMapaTests(BaseIngresoApi):
    def _acciones(self, usuario, codigo="C001"):
        respuesta = self._como(usuario).get(_url("edificio-mapa", self.club.pk, self.edificio.pk))
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        return self._plazas_del_mapa(respuesta.json())[codigo]["acciones"]

    def test_la_cama_disponible_ofrece_ingresar(self):
        self.assertIn("ingresar", self._acciones(self.operador))

    def test_la_cama_ocupada_no_la_ofrece(self):
        self._alojar(self.persona, self.plaza)
        self.assertNotIn("ingresar", self._acciones(self.operador))

    def test_sin_ciudadano_ver_no_la_ofrece(self):
        sin_ver_personas = self._guardia("sin_ver_personas", [VER, ADMITIR], [self.club])
        self.assertNotIn("ingresar", self._acciones(sin_ver_personas))

    def test_con_el_dispositivo_suspendido_no_la_ofrece(self):
        Dispositivo.objects.filter(pk=self.club.pk).update(estado=Dispositivo.Estado.INACTIVO)
        self.assertNotIn("ingresar", self._acciones(self.operador))
