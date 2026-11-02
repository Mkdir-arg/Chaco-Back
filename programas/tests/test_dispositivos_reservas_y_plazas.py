"""Reservas y plazas: lo que dejó la QA local de Dispositivos del 30/10/2026 (Cambio 406).

Lo que se fija acá, y por qué:

1. **B-01: ingresar a una persona consume su reserva.** La plaza que tenía guardada es elegible
   solo para ella, llega marcada en el paso de la plaza, y al confirmar la reserva queda
   CONSUMIDA. Si entra en otra plaza (o sin plaza) la reserva se cierra: no puede seguir
   bloqueando una plaza de la que la persona ya no va a hacer uso.
2. **B-02 / A-08: no se guarda una plaza para quien ya está adentro ni para quien ya tiene una.**
3. **A-07: un tipo sin plazas, o un legajo cerrado o rechazado, no admiten sectores nuevos.**
4. **B-05 y A-12: los textos dicen lo que pasó.**
"""

import re
from datetime import timedelta
from unittest import mock

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from programas.models import Dispositivo, Estadia, ReservaPlaza, Sector, TrazaDispositivo
from programas.services import ingreso as servicio_ingreso
from programas.services.estadias import ingresar_persona, reservar_plaza
from programas.services.ingreso import (
    RESERVA_NUEVA_DURANTE_EL_INGRESO,
    confirmar_ingreso,
    plazas_para_ingresar,
)
from programas.services.plazas import (
    DISPOSITIVO_RECHAZADO,
    TIPO_SIN_PLAZAS,
    agregar_plazas,
    crear_sector,
    editar_plaza,
    editar_sector,
    motivo_sin_ampliar_capacidad,
)
from programas.tests.test_dispositivos_ingreso import BaseIngreso
from programas.tests.test_dispositivos_plazas_acciones import BaseMapa


class IngresoConsumeLaReservaTests(BaseIngreso):
    def _reservar(self, plaza, persona=None, **extra):
        return reservar_plaza(plaza=plaza, ciudadano=persona or self.persona, usuario=self.operador_cis, **extra)

    def _confirmar_en(self, plaza, persona=None):
        persona = persona or self.persona
        return confirmar_ingreso(
            dispositivo=self.cis,
            usuario=self.operador_cis,
            ciudadano_id=persona.pk,
            datos_renaper=None,
            plaza_id=plaza.pk if plaza else None,
        )

    def test_ingresar_en_la_plaza_reservada_consume_la_reserva(self):
        reserva = self._reservar(self.plaza)

        estadia = self._confirmar_en(self.plaza)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.CONSUMIDA)
        self.assertEqual(estadia.plaza, self.plaza)
        self.assertEqual(estadia.estado, Estadia.Estado.ACTIVA)

    def test_ingresar_en_la_plaza_prestada_consume_el_prestamo(self):
        reserva = self._reservar(
            self.plaza, tipo=ReservaPlaza.Tipo.PRESTAMO, hasta=timezone.now() + timedelta(hours=12)
        )

        self._confirmar_en(self.plaza)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.CONSUMIDA)

    def test_ingresar_en_otra_plaza_cierra_la_reserva_y_deja_la_traza(self):
        reserva = self._reservar(self.plaza)

        estadia = self._confirmar_en(self.otra_plaza)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)
        self.assertEqual(estadia.plaza, self.otra_plaza)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="PLAZA_LIBERADA").exists())
        # La plaza reservada vuelve a estar libre para cualquiera.
        ingresar_persona(ciudadano=self.otra_persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

    def test_ingresar_sin_plaza_cierra_la_reserva(self):
        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.save()
        reserva = self._reservar(self.plaza)

        self._confirmar_en(None)

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.LIBERADA)

    def test_una_reserva_vencida_no_se_consume_pero_tampoco_queda_abierta(self):
        ahora = timezone.now()
        vencida = ReservaPlaza.objects.create(
            plaza=self.plaza,
            ciudadano=self.persona,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            estado=ReservaPlaza.Estado.VIGENTE,
            desde=ahora - timedelta(days=2),
            hasta=ahora - timedelta(days=1),
            creada_por=self.operador_cis,
        )

        self._confirmar_en(self.plaza)

        vencida.refresh_from_db()
        self.assertEqual(vencida.estado, ReservaPlaza.Estado.LIBERADA)

    def test_la_reserva_de_otra_persona_sigue_bloqueando_su_plaza(self):
        self._reservar(self.plaza, persona=self.otra_persona)

        with self.assertRaises(ValidationError) as fallo:
            self._confirmar_en(self.plaza)

        self.assertIn("plaza", fallo.exception.message_dict)
        self.assertEqual(ReservaPlaza.objects.get(plaza=self.plaza).estado, ReservaPlaza.Estado.VIGENTE)

    def test_si_el_ingreso_falla_la_reserva_sigue_vigente(self):
        reserva = self._reservar(self.plaza)
        # Fecha futura: el servicio la rechaza después de haber leído la reserva.
        with self.assertRaises(ValidationError):
            confirmar_ingreso(
                dispositivo=self.cis,
                usuario=self.operador_cis,
                ciudadano_id=self.persona.pk,
                datos_renaper=None,
                plaza_id=self.otra_plaza.pk,
                fecha_ingreso=timezone.now() + timedelta(days=1),
            )

        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.VIGENTE)

    def test_el_mapa_ofrece_la_plaza_reservada_solo_a_su_persona(self):
        self._reservar(self.plaza)

        _sectores, elegibles = plazas_para_ingresar(self.cis)
        self.assertNotIn(self.plaza.pk, elegibles)

        sectores, elegibles = plazas_para_ingresar(self.cis, plaza_propia_id=self.plaza.pk)
        self.assertIn(self.plaza.pk, elegibles)
        [item] = sectores
        propia = next(p for p in item["plazas"] if p["pk"] == self.plaza.pk)
        self.assertTrue(propia["propia"])
        self.assertEqual(propia["estado"], "Reservada")
        # No suma a los disponibles del sector: son los de cualquier otra persona.
        self.assertEqual(item["disponibles"], 1)

    def test_el_asistente_marca_la_plaza_reservada_y_la_consume_al_confirmar(self):
        reserva = self._reservar(self.plaza)
        self.client.post(self.url_persona, {"dni": self.persona.dni})

        pantalla = self.client.get(self.url_plaza)
        self.assertEqual(pantalla.status_code, 200)
        self.assertContains(pantalla, "Guardada para esta persona")
        # Llega preseleccionada: lo que el navegador devuelve ya trae la plaza.
        ocultos = self._campos_ocultos(pantalla)
        self.assertEqual(ocultos.get("plaza"), str(self.plaza.pk))
        self.assertRedirects(self.client.post(self.url_plaza, ocultos), self.url_confirmar)

        respuesta = self._confirmar()

        self.assertRedirects(
            respuesta, reverse("dispositivos:detalle", args=[self.cis.pk]), fetch_redirect_response=False
        )
        reserva.refresh_from_db()
        self.assertEqual(reserva.estado, ReservaPlaza.Estado.CONSUMIDA)
        self.assertTrue(Estadia.objects.filter(ciudadano=self.persona, plaza=self.plaza).exists())

    def test_otra_persona_en_el_asistente_no_ve_esa_plaza_elegible(self):
        self._reservar(self.plaza)
        self.client.post(self.url_persona, {"dni": self.otra_persona.dni})

        respuesta = self.client.get(f"{self.url_plaza}?elegir={self.plaza.pk}")

        self.assertContains(respuesta, "Esa plaza ya no está disponible")

    def test_una_reserva_que_aparece_mientras_se_ingresa_frena_el_ingreso(self):
        """Con la persona ya bloqueada se relee: si le guardaron otra plaza en el medio, se rechaza."""
        original = servicio_ingreso._bloquear_persona

        def bloquear_y_que_aparezca_una_reserva(ciudadano):
            original(ciudadano)
            ReservaPlaza.objects.create(
                plaza=self.otra_plaza,
                ciudadano=ciudadano,
                tipo=ReservaPlaza.Tipo.RESERVA,
                estado=ReservaPlaza.Estado.VIGENTE,
                desde=timezone.now(),
                creada_por=self.operador_cis,
            )

        with mock.patch.object(servicio_ingreso, "_bloquear_persona", side_effect=bloquear_y_que_aparezca_una_reserva):
            with self.assertRaises(ValidationError) as fallo:
                self._confirmar_en(self.plaza)

        self.assertEqual(fallo.exception.messages, [RESERVA_NUEVA_DURANTE_EL_INGRESO])
        self.assertFalse(Estadia.objects.filter(ciudadano=self.persona).exists())
        # Todo corre en una transacción: la reserva que apareció a mitad también se deshace.
        self.assertFalse(ReservaPlaza.objects.filter(ciudadano=self.persona).exists())

    def test_las_otras_reservas_se_cierran_antes_de_ingresar(self):
        self._reservar(self.otra_plaza)
        orden = []
        liberar = servicio_ingreso.liberar_reserva
        ingresar = servicio_ingreso.ingresar_persona

        def liberar_anotando(*args, **kwargs):
            orden.append("liberar")
            return liberar(*args, **kwargs)

        def ingresar_anotando(*args, **kwargs):
            orden.append("ingresar")
            return ingresar(*args, **kwargs)

        with (
            mock.patch.object(servicio_ingreso, "liberar_reserva", side_effect=liberar_anotando),
            mock.patch.object(servicio_ingreso, "ingresar_persona", side_effect=ingresar_anotando),
        ):
            self._confirmar_en(self.plaza)

        self.assertEqual(orden, ["liberar", "ingresar"])


class ReservarExigeUnaPersonaLibreTests(BaseIngreso):
    def test_no_se_guarda_una_plaza_para_quien_ya_esta_alojada(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)

        with self.assertRaises(ValidationError) as fallo:
            reservar_plaza(plaza=self.otra_plaza, ciudadano=self.persona, usuario=self.operador_cis)

        self.assertIn("ciudadano", fallo.exception.message_dict)
        self.assertFalse(ReservaPlaza.objects.exists())

    def test_alojada_en_otro_dispositivo_tambien_se_rechaza(self):
        operador = self._operador("Operador doble", self.parador, ("dispositivo.admitir", "dispositivo.ver"))
        ingresar_persona(ciudadano=self.persona, dispositivo=self.parador, usuario=operador, plaza=self.plaza_parador)

        with self.assertRaises(ValidationError) as fallo:
            reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        self.assertIn("ciudadano", fallo.exception.message_dict)

    def test_no_se_guardan_dos_plazas_para_la_misma_persona_en_el_dispositivo(self):
        reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        with self.assertRaises(ValidationError) as fallo:
            reservar_plaza(
                plaza=self.otra_plaza,
                ciudadano=self.persona,
                usuario=self.operador_cis,
                tipo=ReservaPlaza.Tipo.PRESTAMO,
                hasta=timezone.now() + timedelta(hours=12),
            )

        self.assertIn("P1", fallo.exception.message_dict["ciudadano"][0])
        self.assertEqual(ReservaPlaza.objects.count(), 1)

    def test_liberada_la_primera_se_puede_guardar_otra(self):
        from programas.services.estadias import liberar_reserva

        primera = reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)
        liberar_reserva(reserva=primera, usuario=self.operador_cis)

        reservar_plaza(plaza=self.otra_plaza, ciudadano=self.persona, usuario=self.operador_cis)

        self.assertEqual(ReservaPlaza.objects.filter(estado=ReservaPlaza.Estado.VIGENTE).count(), 1)

    def test_una_persona_distinta_si_puede_reservar(self):
        reservar_plaza(plaza=self.plaza, ciudadano=self.persona, usuario=self.operador_cis)

        reservar_plaza(plaza=self.otra_plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)

        self.assertEqual(ReservaPlaza.objects.count(), 2)


class ReservarDesdeElMapaTests(BaseMapa):
    def _post_ajax(self, accion, datos, plaza=None):
        self.client.force_login(self.con_personas)
        url = reverse(f"dispositivos:plaza_{accion}", args=[self.cis.pk, (plaza or self.plaza).pk])
        return self.client.post(url, datos, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_el_error_de_la_persona_cae_en_el_campo_del_dni(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.otra_plaza)

        respuesta = self._post_ajax("reservar", {"dni": self.persona.dni})

        self.assertEqual(respuesta.status_code, 400)
        errores = respuesta.json()["errors"]
        self.assertIn("dni", errores)
        self.assertNotIn("__all__", errores)
        self.assertFalse(ReservaPlaza.objects.exists())


class SectoresSoloDondeHayPlazasTests(BaseMapa):
    def _tipo_sin_plazas(self):
        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.tipos_plaza_admitidos = []
        self.tipo.save()
        self.cis.refresh_from_db()

    def test_un_tipo_sin_plazas_no_admite_sectores_nuevos(self):
        self._tipo_sin_plazas()

        with self.assertRaises(ValidationError) as fallo:
            crear_sector(dispositivo=self.cis, usuario=self.operador_cis, nombre="Nuevo", tipo=Sector.Tipo.PABELLON)

        self.assertEqual(fallo.exception.message_dict, {"__all__": [TIPO_SIN_PLAZAS]})
        self.assertFalse(Sector.objects.filter(nombre="Nuevo").exists())

    def test_un_tipo_sin_plazas_no_admite_lotes(self):
        self._tipo_sin_plazas()

        with self.assertRaises(ValidationError) as fallo:
            agregar_plazas(sector=self.sector, usuario=self.operador_cis, cantidad=1)

        self.assertIn("__all__", fallo.exception.message_dict)

    def test_el_post_del_alta_en_un_tipo_sin_plazas_da_error_general(self):
        self._tipo_sin_plazas()
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(
            reverse("dispositivos:sector_crear", args=[self.cis.pk]),
            {"nombre": "Nuevo", "tipo": Sector.Tipo.PABELLON, "capacidad": 2},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(list(respuesta.json()["errors"]), ["__all__"])

    def test_un_dispositivo_rechazado_no_admite_sectores_y_el_error_es_general(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.RECHAZADO)
        self.cis.refresh_from_db()

        with self.assertRaises(ValidationError) as fallo:
            crear_sector(dispositivo=self.cis, usuario=self.operador_cis, nombre="Nuevo", tipo=Sector.Tipo.PABELLON)

        self.assertEqual(fallo.exception.message_dict, {"__all__": [DISPOSITIVO_RECHAZADO]})
        self.assertEqual(motivo_sin_ampliar_capacidad(self.cis), DISPOSITIVO_RECHAZADO)

    def test_un_dispositivo_rechazado_si_deja_corregir_sectores_y_plazas(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.RECHAZADO)
        self.cis.refresh_from_db()

        editar_sector(
            sector=self.sector, usuario=self.operador_cis, nombre="Corregido", tipo=self.sector.tipo, capacidad=2
        )
        editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo="Z-9", tipo=self.plaza.tipo)

        self.sector.refresh_from_db()
        self.plaza.refresh_from_db()
        self.assertEqual(self.sector.nombre, "Corregido")
        self.assertEqual(self.plaza.codigo, "Z-9")
        with self.assertRaises(ValidationError):
            agregar_plazas(sector=self.sector, usuario=self.operador_cis, cantidad=1)

    def test_el_boton_solo_aparece_donde_el_alta_es_posible(self):
        self.tipo.plaza_obligatoria_al_ingresar = True
        self.tipo.save()
        self.client.force_login(self.operador_cis)
        pantalla = self.client.get(self.url)
        self.assertTrue(pantalla.context["puede_ampliar_capacidad"])
        self.assertContains(pantalla, "Nuevo sector")

        self._tipo_sin_plazas()
        pantalla = self.client.get(self.url)
        self.assertFalse(pantalla.context["puede_ampliar_capacidad"])
        self.assertNotContains(pantalla, "Nuevo sector")
        self.assertNotIn("form_sector_nuevo", pantalla.context)

    def test_un_tipo_que_maneja_plazas_sigue_creando_sectores(self):
        self.tipo.plaza_obligatoria_al_ingresar = True
        self.tipo.save()
        self.cis.refresh_from_db()

        sector = crear_sector(
            dispositivo=self.cis, usuario=self.operador_cis, nombre="Nuevo", tipo=Sector.Tipo.PABELLON
        )

        self.assertEqual(sector.nombre, "Nuevo")


class MensajesDelMapaTests(BaseMapa):
    def test_volver_a_servicio_una_plaza_operativa_dice_que_ya_estaba(self):
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:plaza_volver_servicio", args=[self.cis.pk, self.plaza.pk])

        respuesta = self.client.post(url, {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("ya estaba en servicio", respuesta.json()["message"])
        self.assertFalse(TrazaDispositivo.objects.filter(accion="PLAZA_EN_SERVICIO").exists())

    def test_volver_a_servicio_una_fuera_de_servicio_sigue_diciendo_que_volvio(self):
        from programas.services.estadias import sacar_plaza_de_servicio

        sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Rota")
        self.client.force_login(self.operador_cis)
        url = reverse("dispositivos:plaza_volver_servicio", args=[self.cis.pk, self.plaza.pk])

        respuesta = self.client.post(url, {}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertIn("de nuevo en servicio", respuesta.json()["message"])
        self.assertEqual(TrazaDispositivo.objects.filter(accion="PLAZA_EN_SERVICIO").count(), 1)

    def test_el_modal_de_liberar_distingue_prestamo_de_reserva(self):
        self.client.force_login(self.operador_cis)

        html = self.client.get(self.url).content.decode()

        self.assertIn("El préstamo queda registrado como liberado", html)
        self.assertIn("La reserva queda registrada como liberada", html)
        self.assertTrue(re.search(r"x-show=\"plazasModal\[plazaSel\]\?\.estado === 'Prestada'\"", html))
