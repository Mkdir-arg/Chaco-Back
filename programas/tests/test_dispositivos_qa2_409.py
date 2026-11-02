"""Cambio 409 · QA 2 local de Dispositivos (02/11/2026) y MINOR de las auditorías de #1011 y #1012.

Lo que se fija acá, y por qué:

1. **D1 (decisión del PM): un dispositivo INACTIVO se reactiva y vuelve a ACTIVO**, con la misma capacidad que
   inactivar, el botón confirmado con el modal estándar y una línea en el historial.
2. **D2 (decisión del PM): al ingresar se liberan TODAS las reservas abiertas de la persona**, también las de otros
   dispositivos, y las plazas involucradas se bloquean de una vez y ordenadas por pk.
3. **A2-07:** validar con datos faltantes dice cuáles faltan.
4. **A2-01:** el texto de un campo propio tiene tope en el formulario.
5. **C2-04:** «Crear agente nuevo» no fabrica un homónimo de alguien que ya tiene ese correo.
6. El 403 `debe_cambiar_contrasena` de un usuario sin correo dice que hay que pedir uno al administrador.
7. El aviso de «Liberar» del mapa distingue préstamo de reserva por un dato (`es_prestamo`), no por el texto.
"""

import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.rbac import GRUPO_CIUDADANO_PORTAL
from programas.forms import ItemCampoPropioForm
from programas.models import Dispositivo, ReservaPlaza, TrazaDispositivo
from programas.services import ingreso as servicio_ingreso
from programas.services.dispositivos import (
    cerrar_dispositivo,
    inactivar_dispositivo,
    reactivar_dispositivo,
    validar_dispositivo,
)
from programas.services.estadias import reservar_plaza
from programas.services.ingreso import confirmar_ingreso
from programas.services.sectores_plazas import datos_para_el_modal
from programas.tests.test_dispositivos_crear_agente import BaseCrearAgente
from programas.tests.test_dispositivos_ingreso import BaseIngreso
from programas.tests.test_dispositivos_plazas_acciones import BaseMapa
from users.models import Profile

CAPS_EDITOR = ("dispositivo.ver", "dispositivo.editar")


class ReactivarDispositivoTests(BaseIngreso):
    def setUp(self):
        super().setUp()
        self.editor = self._operador("Editor", self.cis, CAPS_EDITOR)
        self.url = reverse("dispositivos:reactivar", args=[self.cis.pk])
        self.detalle = reverse("dispositivos:detalle", args=[self.cis.pk])

    def _inactivar(self):
        inactivar_dispositivo(self.cis, self.editor)

    def test_un_inactivo_vuelve_a_activo_y_queda_en_el_historial(self):
        self._inactivar()

        reactivado = reactivar_dispositivo(self.cis, self.editor)

        self.assertEqual(reactivado.estado, Dispositivo.Estado.ACTIVO)
        traza = TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="REACTIVADO").get()
        self.assertEqual((traza.estado_anterior, traza.estado_nuevo), ("INACTIVO", "ACTIVO"))
        self.assertEqual(traza.usuario, self.editor)

    def test_solo_se_reactiva_un_inactivo(self):
        with self.assertRaises(ValidationError):
            reactivar_dispositivo(self.cis, self.editor)  # ACTIVO
        self._inactivar()
        cerrar_dispositivo(self.cis, self.editor)
        with self.assertRaises(ValidationError):
            reactivar_dispositivo(self.cis, self.editor)  # CERRADO: el cierre es definitivo
        self.assertFalse(TrazaDispositivo.objects.filter(accion="REACTIVADO").exists())

    def test_el_post_reactiva_con_la_capacidad_de_editar(self):
        self._inactivar()
        self.client.force_login(self.editor)

        respuesta = self.client.post(self.url)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Dispositivo.objects.get(pk=self.cis.pk).estado, Dispositivo.Estado.ACTIVO)

    def test_sin_dispositivo_editar_es_403_y_no_cambia_nada(self):
        self._inactivar()
        solo_ve = self._operador("Solo ve", self.cis, ("dispositivo.ver",))
        self.client.force_login(solo_ve)

        respuesta = self.client.post(self.url)

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Dispositivo.objects.get(pk=self.cis.pk).estado, Dispositivo.Estado.INACTIVO)

    def test_el_detalle_ofrece_reactivar_con_confirmacion_solo_al_inactivo(self):
        self.client.force_login(self.editor)
        self.assertNotContains(self.client.get(self.detalle), f'data-confirm-url="{self.url}"')

        self._inactivar()
        respuesta = self.client.get(self.detalle)

        self.assertContains(respuesta, f'data-confirm-url="{self.url}"')
        self.assertContains(respuesta, "¿Reactivar dispositivo?")
        self.assertNotContains(respuesta, f'data-confirm-url="{reverse("dispositivos:inactivar", args=[self.cis.pk])}"')

    def test_el_detalle_no_ofrece_reactivar_a_quien_solo_ve(self):
        self._inactivar()
        solo_ve = self._operador("Solo ve 2", self.cis, ("dispositivo.ver",))
        self.client.force_login(solo_ve)

        self.assertNotContains(self.client.get(self.detalle), self.url)


class IngresoLiberaTodasLasReservasTests(BaseIngreso):
    """D2: una persona que ya está adentro no puede seguir bloqueando plazas en ningún dispositivo."""

    def _reserva_en_el_parador(self):
        operador_parador = self.operador_parador
        return reservar_plaza(plaza=self.plaza_parador, ciudadano=self.persona, usuario=operador_parador)

    def _confirmar_en_el_cis(self, plaza=None):
        return confirmar_ingreso(
            dispositivo=self.cis,
            usuario=self.operador_cis,
            ciudadano_id=self.persona.pk,
            datos_renaper=None,
            plaza_id=(plaza or self.plaza).pk,
        )

    def test_la_reserva_de_otro_dispositivo_se_libera_aunque_el_operador_no_tenga_alcance_ahi(self):
        reserva = self._reserva_en_el_parador()

        self._confirmar_en_el_cis()

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)
        self.assertEqual(reserva.motivo, servicio_ingreso.MOTIVO_RESERVA_CERRADA_POR_INGRESO)
        # La traza queda en el historial del dispositivo de esa plaza.
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.parador, accion="PLAZA_LIBERADA").exists())
        # Y esa plaza vuelve a estar libre para otra persona.
        reservar_plaza(plaza=self.plaza_parador, ciudadano=self.otra_persona, usuario=self.operador_parador)

    def test_se_liberan_las_de_este_dispositivo_y_las_de_otros_a_la_vez(self):
        en_cis = reservar_plaza(plaza=self.otra_plaza, ciudadano=self.persona, usuario=self.operador_cis)
        # Dos reservas simultáneas de la misma persona no las deja crear el servicio: la segunda entra directa.
        en_parador = ReservaPlaza.objects.create(
            plaza=self.plaza_parador,
            ciudadano=self.persona,
            tipo=ReservaPlaza.Tipo.RESERVA,
            estado=ReservaPlaza.Estado.VIGENTE,
            desde=timezone.now(),
            creada_por=self.operador_parador,
        )

        self._confirmar_en_el_cis()

        for reserva in (en_cis, en_parador):
            reserva.refresh_from_db()
            self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)

    def test_una_reserva_vencida_de_otro_dispositivo_tampoco_queda_abierta(self):
        ahora = timezone.now()
        vencida = ReservaPlaza.objects.create(
            plaza=self.plaza_parador,
            ciudadano=self.persona,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            estado=ReservaPlaza.Estado.VIGENTE,
            desde=ahora - timedelta(days=2),
            hasta=ahora - timedelta(days=1),
            creada_por=self.operador_parador,
        )

        self._confirmar_en_el_cis()

        vencida.refresh_from_db()
        self.assertEqual(vencida.estado, ReservaPlaza.Estado.LIBERADA)

    def test_la_reserva_de_otra_persona_en_otro_dispositivo_no_se_toca(self):
        ajena = reservar_plaza(plaza=self.plaza_parador, ciudadano=self.otra_persona, usuario=self.operador_parador)

        self._confirmar_en_el_cis()

        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, ReservaPlaza.Estado.VIGENTE)

    def test_las_plazas_se_bloquean_juntas_y_ordenadas_antes_que_las_reservas_y_la_persona(self):
        """Orden de candados del Cambio 406 (plaza, reserva, persona), con todas las plazas en un solo bloqueo."""
        reserva = self._reserva_en_el_parador()
        llamadas = []
        original = QuerySet._fetch_all

        def anotar(queryset):
            if queryset._result_cache is None and queryset.query.select_for_update:
                llamadas.append((queryset.model.__name__, str(queryset.query)))
            return original(queryset)

        with mock.patch.object(QuerySet, "_fetch_all", autospec=True, side_effect=anotar):
            self._confirmar_en_el_cis()

        modelos = [modelo for modelo, _sql in llamadas]
        primera = next(i for i, modelo in enumerate(modelos) if modelo == "Plaza")
        primera_reserva = modelos.index("ReservaPlaza")
        persona = modelos.index("Ciudadano")
        self.assertEqual(primera, 0)
        self.assertLess(primera, primera_reserva)
        self.assertLess(primera_reserva, persona)
        sql_de_las_plazas = llamadas[0][1]
        en_el_in = re.search(r'"programas_plaza"\."id" IN \(([\d, ]+)\)', sql_de_las_plazas)
        self.assertIsNotNone(en_el_in, sql_de_las_plazas)
        self.assertEqual({int(pk) for pk in en_el_in.group(1).split(",")}, {reserva.plaza_id, self.plaza.pk})
        self.assertTrue(sql_de_las_plazas.endswith("ORDER BY 1 ASC"), sql_de_las_plazas)

    def test_una_reserva_nueva_en_otro_dispositivo_mientras_se_ingresa_frena_el_ingreso(self):
        original = servicio_ingreso._bloquear_persona

        def bloquear_y_que_aparezca(ciudadano):
            original(ciudadano)
            self._reserva_en_el_parador()

        with mock.patch.object(servicio_ingreso, "_bloquear_persona", side_effect=bloquear_y_que_aparezca):
            with self.assertRaises(ValidationError) as fallo:
                self._confirmar_en_el_cis()

        self.assertEqual(fallo.exception.messages, [servicio_ingreso.RESERVA_NUEVA_DURANTE_EL_INGRESO])


class ValidarDiceQueFaltaTests(BaseIngreso):
    def test_validar_nombra_los_campos_que_faltan(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(
            estado=Dispositivo.Estado.PENDIENTE_VALIDACION, area_ministerio="", domicilio=""
        )
        dispositivo = Dispositivo.objects.get(pk=self.cis.pk)

        with self.assertRaises(ValidationError) as fallo:
            validar_dispositivo(dispositivo, self.operador_cis)

        mensaje = fallo.exception.messages[0]
        self.assertIn("Completá los campos obligatorios antes de validar el dispositivo", mensaje)
        self.assertIn(str(Dispositivo._meta.get_field("area_ministerio").verbose_name), mensaje)
        self.assertIn(str(Dispositivo._meta.get_field("domicilio").verbose_name), mensaje)
        self.assertNotIn(str(Dispositivo._meta.get_field("nombre").verbose_name), mensaje)


class CampoPropioConTopeTests(BaseIngreso):
    def _form(self, texto):
        return ItemCampoPropioForm(
            {"texto": texto, "tipo": "STRING", "canal": "ambos"},
        )

    def test_una_etiqueta_larga_se_rechaza_en_el_campo(self):
        form = self._form("x" * 121)

        self.assertFalse(form.is_valid())
        self.assertIn("texto", form.errors)

    def test_una_etiqueta_de_120_pasa(self):
        self.assertTrue(self._form("x" * 120).is_valid())


class CrearAgenteNoDuplicaElCorreoTests(BaseCrearAgente):
    def test_un_correo_que_ya_existe_se_rechaza_sin_importar_las_mayusculas(self):
        existente = User.objects.create_user("ya_existe", email="Persona.Repetida@Example.com", password="x")
        antes = User.objects.count()

        respuesta = self._post(self._datos(email="persona.repetida@example.COM"))

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertIn("email", respuesta.json()["errors"])
        self.assertEqual(User.objects.count(), antes)
        self.assertNotIn(existente.username, respuesta.content.decode())

    def test_un_usuario_activo_sin_rol_de_agente_se_manda_a_sumarlo_desde_buscar_agente(self):
        # Cambio 408: ese usuario SÍ aparece en «Buscar agente» como sumable, así que no se lo manda con el admin.
        User.objects.create_user("ya_existe", email="sin.rol@example.com", password="x")

        respuesta = self._post(self._datos(email="Sin.Rol@example.com"))

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        mensaje = respuesta.json()["message"]
        self.assertIn("Buscar agente", mensaje)
        self.assertIn("Sumar como agente", mensaje)
        self.assertNotIn("administrador del programa", mensaje)
        self.assertNotIn("ya_existe", respuesta.content.decode())

    def test_un_usuario_inactivo_sin_rol_se_manda_con_el_administrador(self):
        # La búsqueda excluye a los inactivos sin rol: no hay a dónde mandarlo salvo con el admin.
        User.objects.create_user("inactivo", email="inactivo@example.com", password="x", is_active=False)

        respuesta = self._post(self._datos(email="inactivo@example.com"))

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertIn("pedile al administrador del programa que le sume el rol de agente", respuesta.json()["message"])
        self.assertNotIn("Buscar agente", respuesta.json()["message"])

    def test_un_superusuario_con_el_rol_de_agente_no_se_manda_a_buscarlo(self):
        # La búsqueda excluye a los superusuarios aunque tengan el rol: mismo universo (``universo_buscar_agente``).
        superu = User.objects.create_user("superu", email="superu@example.com", password="x", is_superuser=True)
        superu.groups.add(self.rol_agente)

        respuesta = self._post(self._datos(email="superu@example.com"))

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertIn("pedile al administrador del programa", respuesta.json()["message"])
        self.assertNotIn("Buscar agente", respuesta.json()["message"])

    def test_un_ciudadano_del_portal_se_manda_con_el_administrador(self):
        ciudadano = User.objects.create_user("ciudadano", email="ciudadano@example.com", password="x")
        ciudadano.groups.add(Group.objects.get_or_create(name=GRUPO_CIUDADANO_PORTAL)[0])

        respuesta = self._post(self._datos(email="ciudadano@example.com"))

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertIn("pedile al administrador del programa", respuesta.json()["message"])
        self.assertNotIn("Buscar agente", respuesta.json()["message"])

    def test_si_el_dueno_del_correo_es_agente_se_lo_manda_a_buscarlo(self):
        existente = User.objects.create_user("ya_agente", email="agente.previo@example.com", password="x")
        existente.groups.add(self.rol_agente)

        respuesta = self._post(self._datos(email="Agente.Previo@example.com"))

        self.assertEqual(respuesta.status_code, 409, respuesta.content)
        self.assertIn("Buscar agente", respuesta.json()["message"])
        self.assertNotIn("sume el rol de agente", respuesta.json()["message"])
        self.assertNotIn("ya_agente", respuesta.content.decode())

    def test_un_correo_nuevo_sigue_creando_al_agente(self):
        respuesta = self._post()

        self.assertEqual(respuesta.status_code, 200, respuesta.content)


class ClaveProvisoriaSinCorreoTests(BaseCrearAgente):
    def _token(self, usuario):
        return APIClient().post(
            reverse("becas_api:token"), {"username": usuario.username, "password": "Clave-Del-Admin-1"}
        )

    def _agente(self, email):
        respuesta = self._post()
        agente = User.objects.get(pk=respuesta.json()["user"]["id"])
        agente.set_password("Clave-Del-Admin-1")
        agente.email = email
        agente.save()
        self.assertTrue(Profile.objects.get(user=agente).debe_cambiar_contrasena)
        return agente

    def test_sin_correo_el_403_manda_a_pedirle_uno_al_administrador(self):
        respuesta = self._token(self._agente(""))

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(respuesta.json()["codigo"], "debe_cambiar_contrasena")
        self.assertIn("Pedile a tu administrador que te cargue un correo", respuesta.json()["detail"])

    def test_con_correo_el_detalle_es_el_de_siempre_y_el_codigo_no_cambia(self):
        respuesta = self._token(self._agente("agente@example.com"))

        self.assertEqual(respuesta.json()["codigo"], "debe_cambiar_contrasena")
        self.assertNotIn("Pedile a tu administrador", respuesta.json()["detail"])
        self.assertIn("Olvidé mi contraseña", respuesta.json()["detail"])


class AvisoDeLiberarPorDatoTests(BaseIngreso):
    def test_el_modal_marca_es_prestamo_segun_el_estado_de_la_plaza(self):
        from programas.services.ocupacion import estado_de_plazas

        estado = estado_de_plazas([self.plaza])[self.plaza.pk]
        reserva = reservar_plaza(
            plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis, tipo=ReservaPlaza.Tipo.RESERVA
        )
        reservada = estado_de_plazas([self.plaza])[self.plaza.pk]
        self.assertFalse(datos_para_el_modal(self.plaza, reservada, ["liberar"])["es_prestamo"])

        reserva.tipo = ReservaPlaza.Tipo.PRESTAMO
        reserva.hasta = timezone.now() + timedelta(hours=6)
        reserva.save()
        prestada = estado_de_plazas([self.plaza])[self.plaza.pk]
        self.assertTrue(datos_para_el_modal(self.plaza, prestada, ["liberar"])["es_prestamo"])
        self.assertFalse(datos_para_el_modal(self.plaza, estado, [])["es_prestamo"])


class SectoresDeUnDispositivoCerradoTests(BaseMapa):
    """N-01: la pantalla no ofrece lo que el servidor rechaza con «está cerrado»."""

    def _editar_sector(self):
        return f'href="?sector={self.sector.pk}"'

    def test_activo_ofrece_editar_sector_y_la_bandera_es_verdadera(self):
        respuesta = self._pantalla()

        self.assertTrue(respuesta.context["puede_configurar_plazas"])
        self.assertContains(respuesta, self._editar_sector())

    def test_cerrado_no_ofrece_editar_sector_ni_editar_plaza_ni_sacar_de_servicio(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.CERRADO)

        respuesta = self._pantalla()

        self.assertFalse(respuesta.context["puede_configurar_plazas"])
        self.assertNotContains(respuesta, self._editar_sector())
        self.assertNotContains(respuesta, "Editar sector")
        for datos in respuesta.context["plazas_modal"].values():
            self.assertNotIn("fuera_servicio", datos["acciones"])
