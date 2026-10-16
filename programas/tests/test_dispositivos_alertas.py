"""Alertas del dispositivo por criticidad (MVP v2, etapa 3 · #699).

Lo que se fija acá, y por qué:

1. **Las reglas viven en el registro genérico** de ``core.services.vencimientos``, como
   reglas de aviso de ámbito ``dispositivos``, sin tocar las de Becas que corre el cron.
2. **Cada regla aparece cuando su origen cumple la condición y desaparece sola cuando se
   lo resuelve en el origen**: no hay alerta que se cierre a mano.
3. **Avisar nunca bloquea**: con todas las alertas encendidas, ingresar, cambiar de plaza,
   reservar y egresar funcionan igual.
4. **Severidad, origen, fecha y enlace** de cada una, y el **alcance**: un operador no ve
   las alertas de otra institución.
5. **Consultas fijas**: las alertas cuestan lo mismo con una plaza que con veinte.
"""

import json
import tempfile
from datetime import time, timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import override_settings, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from core import rbac
from core.services import vencimientos as registro
from core.services.vencimientos import Aviso, ReglaAviso, avisos, registrar_aviso
from programas.models import (
    AsignacionDispositivo,
    Dispositivo,
    Edificio,
    InspeccionEdificio,
    Plaza,
    ReservaPlaza,
    Sector,
    TrazaDispositivo,
    Turno,
)
from programas.services.alertas_dispositivos import AMBITO
from programas.services.bitacora import crear_turno
from programas.services.detalle_dispositivo import alertas_del_dispositivo
from programas.services.dispositivos import registrar_edicion_dispositivo
from programas.services.estadias import (
    cambiar_plaza,
    egresar_persona,
    ingresar_persona,
    liberar_reserva,
    reservar_plaza,
    sacar_plaza_de_servicio,
    volver_plaza_a_servicio,
)
from programas.services.inspecciones import cancelar_inspeccion, crear_inspeccion, registrar_resultado
from programas.tests.test_dispositivos_estadias import BaseEstadias, _permiso
from users.models import RolMeta

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_alertas"

SLUGS = {
    "dispositivos.reserva_vencida",
    "dispositivos.edificio_critico",
    "dispositivos.relevamiento_vencido",
    "dispositivos.sin_turnos",
    "dispositivos.plazas_fuera_de_servicio",
}
Criticidad = InspeccionEdificio.Criticidad


class BaseAlertas(BaseEstadias):
    """El terreno de las estadías más un edificio por institución, un coordinador y un agente."""

    def setUp(self):
        super().setUp()
        media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(media.cleanup)
        contexto = override_settings(MEDIA_ROOT=media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)

        self.edificio_cis = Edificio.objects.create(codigo="ED-CIS", nombre="Edificio del CIS")
        self.edificio_cis.dispositivos.add(self.cis)
        self.edificio_parador = Edificio.objects.create(codigo="ED-PAR", nombre="Edificio del Parador")
        self.edificio_parador.dispositivos.add(self.parador)
        self.coordinador = self._usuario("coordinador", ("inspeccion.asignar", "dispositivo.ver"), [self.cis])
        self.coordinador_parador = self._usuario("coord_parador", ("inspeccion.asignar",), [self.parador])
        self.agente = self._usuario("agente", ("inspeccion.relevar",))
        self.vence = timezone.localdate() + timedelta(days=30)

    def _usuario(self, nombre, capacidades, dispositivos=()):
        rol = Group.objects.create(name=f"Rol {nombre}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        for dispositivo in dispositivos:
            AsignacionDispositivo.objects.create(dispositivo=dispositivo, rol=rol, activo=True)
        usuario = User.objects.create_user(username=nombre, password="x", first_name=nombre.capitalize())
        usuario.groups.add(rol)
        return User.objects.get(pk=usuario.pk)

    def _turno(self, dispositivo=None):
        """Una guardia de 24 h: hay turno vigente a cualquier hora."""

        return Turno.objects.create(
            dispositivo=dispositivo or self.cis, nombre="Guardia", hora_desde=time(8), hora_hasta=time(8)
        )

    def _prestamo_vencido(self, plaza=None, tipo=ReservaPlaza.Tipo.PRESTAMO):
        ahora = timezone.now()
        return ReservaPlaza.objects.create(
            plaza=plaza or self.otra_plaza,
            ciudadano=self.otra_persona,
            tipo=tipo,
            desde=ahora - timedelta(days=1),
            hasta=ahora - timedelta(hours=2),
            creada_por=self.operador_cis,
        )

    def _relevamiento(self, edificio=None, coordinador=None):
        return crear_inspeccion(
            coordinador or self.coordinador,
            edificio=edificio or self.edificio_cis,
            asignado_a=self.agente,
            fecha_vencimiento=self.vence,
        )

    def _vencer(self, inspeccion, dias=3):
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(
            fecha_vencimiento=timezone.localdate() - timedelta(days=dias)
        )
        inspeccion.refresh_from_db()
        return inspeccion

    def _alertas(self, dispositivo=None, regla=None, usuario=None):
        """Las alertas tal como las pide la pantalla. Sin usuario, las que dependen de una
        capacidad llegan sin enlace: es el contrato de `alertas_del_dispositivo`."""

        alertas = alertas_del_dispositivo(dispositivo or self.cis, usuario=usuario)
        if regla:
            alertas = [alerta for alerta in alertas if alerta["regla"] == regla]
        return alertas

    def _todas_encendidas(self):
        """Las cinco reglas cumplidas en el CIS, cada una por su origen."""

        self._prestamo_vencido()
        tercera = Plaza.objects.create(sector=self.sector, codigo="P3")
        sacar_plaza_de_servicio(plaza=tercera, usuario=self.operador_cis, motivo="Filtración en el techo")
        critico = self._relevamiento()
        registrar_resultado(self.agente, critico, criticidad=Criticidad.ALTA)
        otro_edificio = Edificio.objects.create(codigo="ED-CIS-2", nombre="Anexo del CIS")
        otro_edificio.dispositivos.add(self.cis)
        self._vencer(self._relevamiento(edificio=otro_edificio))
        return tercera


class RegistroTests(BaseAlertas):
    def test_las_reglas_se_registran_en_el_registro_generico_como_avisos(self):
        registradas = {regla.slug for regla in registro.AVISOS if regla.ambito == AMBITO}
        self.assertEqual(registradas, SLUGS)
        # Avisan y no aplican: el cron no las ve, y las de Becas siguen siendo las únicas que corre.
        self.assertFalse(SLUGS & {regla.slug for regla in registro.REGLAS})

    def test_una_severidad_desconocida_se_rechaza(self):
        with self.assertRaisesMessage(ValueError, "Severidad desconocida"):
            registrar_aviso(ReglaAviso(slug="x", ambito="x", descripcion="x", severidad="urgente", pendientes=list))

    def test_los_avisos_salen_de_la_mas_severa_a_la_menos(self):
        def regla(severidad):
            return ReglaAviso(
                slug=f"prueba.{severidad}",
                ambito="prueba",
                descripcion=severidad,
                severidad=severidad,
                pendientes=lambda: [Aviso(titulo=severidad, texto="", origen="", fecha=None)],
            )

        originales = registro.AVISOS
        try:
            for severidad in ("baja", "alta", "media"):
                registrar_aviso(regla(severidad))
            self.assertEqual([aviso.titulo for aviso in avisos("prueba")], ["alta", "media", "baja"])
            self.assertEqual([aviso.severidad for aviso in avisos("prueba")], ["alta", "media", "baja"])
        finally:
            registro.AVISOS = originales


class ReservaVencidaTests(BaseAlertas):
    regla = "dispositivos.reserva_vencida"

    def test_un_prestamo_vencido_sin_liberar_avisa_con_severidad_alta(self):
        prestamo = self._prestamo_vencido()

        [alerta] = self._alertas(regla=self.regla)

        self.assertEqual(alerta["severidad"], "alta")
        self.assertEqual(alerta["tono"], "danger")
        self.assertEqual(alerta["titulo"], "Préstamo vencido sin liberar")
        self.assertEqual(alerta["origen"], "Plaza P2 · Varones")
        self.assertEqual(alerta["fecha"], prestamo.hasta)
        # Al mapa de plazas, que desde el Cambio de P5 tiene la acción que la resuelve.
        self.assertEqual(alerta["enlace"], reverse("dispositivos:sectores", args=[self.cis.pk]))
        self.assertEqual(alerta["accion"], "Liberar la plaza")

    def test_una_reserva_vencida_tambien_y_con_su_titulo(self):
        self._prestamo_vencido(tipo=ReservaPlaza.Tipo.RESERVA)
        [alerta] = self._alertas(regla=self.regla)
        self.assertEqual(alerta["titulo"], "Reserva vencida sin liberar")

    def test_el_texto_no_repite_la_plaza_ni_la_fecha_que_ya_dice_el_pie(self):
        """Cada alerta ocupa una línea: lo que va en el pie no se dice dos veces."""

        prestamo = self._prestamo_vencido()

        [alerta] = self._alertas(regla=self.regla)

        cuando = date_format(timezone.localtime(prestamo.hasta), "d/m/Y H:i")
        self.assertEqual(
            alerta["texto"],
            "La plaza ya cuenta como disponible, pero el préstamo sigue abierto: falta liberarlo. "
            f"Plaza P2 · Varones · desde el {cuando}.",
        )

    def test_la_reserva_concuerda_en_femenino(self):
        self._prestamo_vencido(tipo=ReservaPlaza.Tipo.RESERVA)
        [alerta] = self._alertas(regla=self.regla)
        self.assertIn("la reserva sigue abierta: falta liberarla", alerta["texto"])

    def test_desaparece_al_liberarla_en_su_origen(self):
        prestamo = self._prestamo_vencido()
        self.assertEqual(len(self._alertas(regla=self.regla)), 1)

        liberar_reserva(reserva=prestamo, usuario=self.operador_cis)

        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_un_prestamo_que_todavia_no_vencio_no_avisa(self):
        reservar_plaza(
            plaza=self.otra_plaza,
            ciudadano=self.otra_persona,
            usuario=self.operador_cis,
            tipo=ReservaPlaza.Tipo.PRESTAMO,
            hasta=timezone.now() + timedelta(hours=12),
        )
        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_una_reserva_ya_consumida_no_avisa(self):
        prestamo = self._prestamo_vencido()
        ReservaPlaza.objects.filter(pk=prestamo.pk).update(estado=ReservaPlaza.Estado.CONSUMIDA)
        self.assertEqual(self._alertas(regla=self.regla), [])


class PlazasFueraDeServicioTests(BaseAlertas):
    regla = "dispositivos.plazas_fuera_de_servicio"

    def test_una_plaza_fuera_de_servicio_avisa_con_su_motivo_y_severidad_baja(self):
        sacar_plaza_de_servicio(plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Cama rota")

        [alerta] = self._alertas(regla=self.regla)

        self.assertEqual(alerta["severidad"], "baja")
        self.assertEqual(alerta["tono"], "info")
        self.assertEqual(alerta["titulo"], "1 plaza fuera de servicio")
        self.assertIn("P2 (Cama rota)", alerta["texto"])
        self.assertEqual(alerta["enlace"], reverse("dispositivos:sectores", args=[self.cis.pk]))

    def test_varias_plazas_son_una_sola_alerta(self):
        for plaza in (self.plaza, self.otra_plaza):
            sacar_plaza_de_servicio(plaza=plaza, usuario=self.operador_cis, motivo="Pintura")
        [alerta] = self._alertas(regla=self.regla)
        self.assertEqual(alerta["titulo"], "2 plazas fuera de servicio")

    def test_la_fecha_es_desde_cuando_pasa_y_no_la_ultima_plaza_que_se_sumo(self):
        """El pie dice «desde el …»: la alerta está encendida desde la plaza más vieja."""

        sacar_plaza_de_servicio(plaza=self.plaza, usuario=self.operador_cis, motivo="Pintura")
        primera = Plaza.objects.get(pk=self.plaza.pk).modificado
        sacar_plaza_de_servicio(plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Cama rota")
        ultima = Plaza.objects.get(pk=self.otra_plaza.pk).modificado
        self.assertGreater(ultima, primera, "la segunda plaza tiene que salir de servicio después")

        [alerta] = self._alertas(regla=self.regla)

        self.assertEqual(alerta["fecha"], primera)

    def test_desaparece_al_volver_la_plaza_a_servicio(self):
        sacar_plaza_de_servicio(plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Cama rota")

        volver_plaza_a_servicio(plaza=self.otra_plaza, usuario=self.operador_cis)

        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_un_sector_dado_de_baja_no_avisa(self):
        sacar_plaza_de_servicio(plaza=self.otra_plaza, usuario=self.operador_cis, motivo="Cama rota")
        Sector.objects.filter(pk=self.sector.pk).update(activo=False)
        self.assertEqual(self._alertas(regla=self.regla), [])


class EdificioCriticoTests(BaseAlertas):
    regla = "dispositivos.edificio_critico"

    def test_el_ultimo_relevamiento_critico_avisa_con_severidad_alta(self):
        inspeccion = registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.ALTA)

        [alerta] = self._alertas(regla=self.regla)

        self.assertEqual(alerta["severidad"], "alta")
        self.assertEqual(alerta["titulo"], "El edificio requiere intervención")
        self.assertEqual(alerta["origen"], "Relevamiento edilicio · Edificio del CIS")
        self.assertEqual(alerta["fecha"], inspeccion.realizada_en)
        self.assertIn("No bloquea la operación", alerta["texto"])
        # El edificio lo nombra el pie una sola vez: el texto no lo repite.
        self.assertEqual(alerta["texto"].count("Edificio del CIS"), 1)
        # Sin usuario no se puede decidir si el enlace a P21 corresponde: sin enlace.
        self.assertEqual((alerta["enlace"], alerta["accion"]), ("", ""))

    def test_desaparece_con_un_relevamiento_nuevo_que_no_es_critico(self):
        registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.ALTA)
        self.assertEqual(len(self._alertas(regla=self.regla)), 1)

        registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.BAJA)

        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_una_criticidad_media_no_avisa(self):
        registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.MEDIA)
        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_el_edificio_de_otra_institucion_no_avisa_aca(self):
        relevamiento = self._relevamiento(edificio=self.edificio_parador, coordinador=self.coordinador_parador)
        registrar_resultado(self.agente, relevamiento, criticidad=Criticidad.ALTA)

        self.assertEqual(self._alertas(regla=self.regla), [])
        self.assertEqual(len(self._alertas(self.parador, regla=self.regla)), 1)

    def test_un_predio_compartido_avisa_en_todas_sus_instituciones(self):
        self.edificio_cis.dispositivos.add(self.parador)
        registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.ALTA)

        self.assertEqual(len(self._alertas(regla=self.regla)), 1)
        self.assertEqual(len(self._alertas(self.parador, regla=self.regla)), 1)


class RelevamientoVencidoTests(BaseAlertas):
    regla = "dispositivos.relevamiento_vencido"

    def test_un_relevamiento_en_curso_vencido_avisa_con_severidad_media(self):
        inspeccion = self._vencer(self._relevamiento(), dias=3)

        [alerta] = self._alertas(regla=self.regla)

        self.assertEqual(alerta["severidad"], "media")
        self.assertEqual(alerta["tono"], "warning")
        self.assertEqual(alerta["titulo"], "Relevamiento edilicio vencido")
        self.assertIn("hace 3 días", alerta["texto"])
        self.assertEqual(alerta["fecha"], inspeccion.fecha_vencimiento)

    def test_desaparece_al_registrar_el_resultado(self):
        inspeccion = self._vencer(self._relevamiento())

        registrar_resultado(self.agente, inspeccion, criticidad=Criticidad.BAJA)

        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_desaparece_al_cancelarlo(self):
        inspeccion = self._vencer(self._relevamiento())

        cancelar_inspeccion(self.coordinador, inspeccion, "Se reprograma")

        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_el_dia_del_vencimiento_todavia_no_avisa(self):
        inspeccion = self._relevamiento()
        InspeccionEdificio.objects.filter(pk=inspeccion.pk).update(fecha_vencimiento=timezone.localdate())
        self.assertEqual(self._alertas(regla=self.regla), [])


class SinTurnosTests(BaseAlertas):
    regla = "dispositivos.sin_turnos"

    def test_un_dispositivo_activo_sin_turnos_avisa_con_severidad_media(self):
        [alerta] = self._alertas(regla=self.regla)
        self.assertEqual(alerta["severidad"], "media")
        self.assertEqual(alerta["titulo"], "Sin turnos configurados")
        self.assertIn("bitácora", alerta["texto"])

    def test_desaparece_al_configurar_un_turno(self):
        crear_turno(
            dispositivo=self.cis, usuario=self.operador_cis, nombre="Mañana", hora_desde=time(6), hora_hasta=time(14)
        )
        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_un_turno_dado_de_baja_no_cuenta(self):
        Turno.objects.create(
            dispositivo=self.cis, nombre="Viejo", hora_desde=time(6), hora_hasta=time(14), activo=False
        )
        self.assertEqual(len(self._alertas(regla=self.regla)), 1)

    def test_un_dispositivo_que_no_esta_activo_no_avisa(self):
        Dispositivo.objects.filter(pk=self.cis.pk).update(estado=Dispositivo.Estado.INACTIVO)
        self.cis.refresh_from_db()
        self.assertEqual(self._alertas(regla=self.regla), [])

    def test_la_fecha_es_la_de_la_validacion_y_no_la_de_la_ultima_edicion(self):
        """La traza de una edición guarda `estado_nuevo=ACTIVO`: filtrar por el estado la tomaría.

        El contrato de la fecha es «desde cuándo pasa esto», y lo que pasa es que el
        dispositivo quedó activo sin turnos: editarle el teléfono después no mueve ese día.
        """

        validado = timezone.now() - timedelta(days=5)
        with mock.patch("django.utils.timezone.now", return_value=validado):
            TrazaDispositivo.objects.create(
                dispositivo=self.cis,
                usuario=self.operador_cis,
                accion="VALIDADO",
                estado_anterior="PENDIENTE_VALIDACION",
                estado_nuevo=Dispositivo.Estado.ACTIVO,
            )
        registrar_edicion_dispositivo(self.cis, self.operador_cis, {"camas_totales": {"anterior": 0, "nuevo": 10}})

        [alerta] = self._alertas(regla=self.regla)
        self.assertEqual(alerta["fecha"], validado)


class EnlaceDeResolucionTests(BaseAlertas):
    """Dónde se resuelve cada alerta, y para quién.

    El enlace depende de quién mira porque la pantalla de destino tiene su propia
    capacidad: ofrecérselo a quien va a rebotar con un 403 sería anunciarle una puerta
    cerrada. Qué alertas hay **no** depende de quién mira.
    """

    def setUp(self):
        super().setUp()
        self.url_p21 = reverse("dispositivos:relevamientos")
        self.url_turnos = f"{reverse('dispositivos:bitacora', args=[self.cis.pk])}?turnos=1"

    def _con(self, usuario, regla):
        # Recargado: `rbac` memoiza las capacidades en el objeto, y el usuario pudo pasar
        # por el cliente de prueba antes de llegar acá.
        return self._alertas(regla=regla, usuario=User.objects.get(pk=usuario.pk))

    def test_el_edificio_critico_lleva_a_relevamientos_con_inspeccion_asignar(self):
        registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.ALTA)

        [alerta] = self._con(self.coordinador, "dispositivos.edificio_critico")

        self.assertEqual((alerta["enlace"], alerta["accion"]), (self.url_p21, "Ver relevamientos"))

    def test_sin_inspeccion_asignar_la_alerta_sigue_pero_sin_enlace(self):
        """El operador del dispositivo ve la alerta; P21 le da 403, así que no se le ofrece."""

        registrar_resultado(self.agente, self._relevamiento(), criticidad=Criticidad.ALTA)
        self.assertEqual(self.client.get(self.url_p21).status_code, 302)
        self.client.force_login(self.operador_cis)
        self.assertEqual(self.client.get(self.url_p21).status_code, 403)

        [alerta] = self._con(self.operador_cis, "dispositivos.edificio_critico")

        self.assertEqual(alerta["titulo"], "El edificio requiere intervención")
        self.assertEqual((alerta["enlace"], alerta["accion"]), ("", ""))

    def test_el_relevamiento_vencido_lleva_a_relevamientos_con_la_misma_regla(self):
        self._vencer(self._relevamiento())

        con = self._con(self.coordinador, "dispositivos.relevamiento_vencido")
        sin = self._con(self.operador_cis, "dispositivos.relevamiento_vencido")

        self.assertEqual(con[0]["enlace"], self.url_p21)
        self.assertEqual(sin[0]["enlace"], "")

    def test_sin_turnos_lleva_a_la_bitacora_con_el_modal_abierto_con_dispositivo_editar(self):
        [alerta] = self._con(self.operador_cis, "dispositivos.sin_turnos")

        self.assertEqual((alerta["enlace"], alerta["accion"]), (self.url_turnos, "Configurar turnos"))
        # El destino abre el modal de turnos de verdad, no una bitácora cualquiera.
        self.client.force_login(self.operador_cis)
        self.assertTrue(self.client.get(alerta["enlace"]).context["abrir_modal_turnos"])

    def test_sin_dispositivo_editar_la_alerta_de_turnos_sigue_pero_sin_enlace(self):
        mirón = self._usuario("miron", ("dispositivo.ver",), [self.cis])

        [alerta] = self._alertas(regla="dispositivos.sin_turnos", usuario=mirón)

        self.assertEqual(alerta["titulo"], "Sin turnos configurados")
        self.assertEqual((alerta["enlace"], alerta["accion"]), ("", ""))
        self.client.force_login(mirón)
        self.assertFalse(self.client.get(self.url_turnos).context["abrir_modal_turnos"])

    def test_el_alcance_es_al_dispositivo_y_no_al_programa(self):
        """`dispositivo.editar` en otra institución no habilita el enlace de esta."""

        ajeno = self._usuario("editor_parador", ("dispositivo.ver", "dispositivo.editar"), [self.parador])

        [alerta] = self._alertas(regla="dispositivos.sin_turnos", usuario=ajeno)

        self.assertEqual((alerta["enlace"], alerta["accion"]), ("", ""))


class NuncaBloqueaTests(BaseAlertas):
    """Con las cinco alertas encendidas, ninguna acción deja de poder completarse."""

    def test_con_todas_las_alertas_las_operaciones_se_completan(self):
        self._todas_encendidas()
        self.assertEqual({alerta["regla"] for alerta in self._alertas()}, SLUGS)

        estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza
        )
        nueva = Plaza.objects.create(sector=self.sector, codigo="P4")
        cambiar_plaza(estadia=estadia, plaza=nueva, usuario=self.operador_cis, motivo="Pidió cambio")
        reserva = reservar_plaza(plaza=self.plaza, ciudadano=self.otra_persona, usuario=self.operador_cis)
        liberar_reserva(reserva=reserva, usuario=self.operador_cis)
        egresar_persona(destino="Domicilio", estadia=estadia, usuario=self.operador_cis, motivo_egreso=self.motivo_alta)

        estadia.refresh_from_db()
        self.assertFalse(estadia.activa)
        # Las alertas siguen ahí: ninguna de esas acciones las resolvía.
        self.assertEqual({alerta["regla"] for alerta in self._alertas()}, SLUGS)

    def test_el_detalle_ofrece_ingresar_aunque_haya_alertas(self):
        self._todas_encendidas()
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]))

        self.assertContains(respuesta, "Préstamo vencido sin liberar")
        self.assertContains(respuesta, reverse("dispositivos:ingreso_persona", args=[self.cis.pk]))


class PantallaTests(BaseAlertas):
    def setUp(self):
        super().setUp()
        self.url = reverse("dispositivos:detalle", args=[self.cis.pk])
        self.client.force_login(self.operador_cis)

    def test_las_alertas_se_dibujan_con_la_pieza_su_enlace_y_por_severidad(self):
        self._todas_encendidas()

        html = self.client.get(self.url).content.decode()

        self.assertIn('aria-label="Alertas del dispositivo"', html)
        url_mapa = reverse("dispositivos:sectores", args=[self.cis.pk])
        self.assertIn(f'href="{url_mapa}"', html)
        self.assertIn("Ver plazas", html)
        orden = [
            html.index("Préstamo vencido sin liberar"),
            html.index("Relevamiento edilicio vencido"),
            html.index("plaza fuera de servicio"),
        ]
        self.assertEqual(orden, sorted(orden), "alta, media y baja, en ese orden")
        self.assertIn("bg-danger-soft", html)

    def test_sin_alertas_no_hay_seccion(self):
        self._turno()
        self.assertNotContains(self.client.get(self.url), 'aria-label="Alertas del dispositivo"')

    def test_otra_institucion_no_ve_las_alertas_de_esta(self):
        self._prestamo_vencido()
        self._turno(self.parador)
        self.client.force_login(self.operador_parador)

        self.assertEqual(self.client.get(self.url).status_code, 403)
        propia = self.client.get(reverse("dispositivos:detalle", args=[self.parador.pk]))
        self.assertNotContains(propia, "Préstamo vencido sin liberar")
        self.assertNotContains(propia, 'aria-label="Alertas del dispositivo"')


@tag("performance")
class AlertasPresupuestoTests(BaseAlertas):
    """Las alertas cuestan lo mismo con un origen de cada regla que con veinte."""

    def setUp(self):
        super().setUp()
        # El peor caso: un usuario que **no** es admin del programa, así que el alcance al
        # dispositivo del enlace de turnos se resuelve con una consulta.
        self.mira = self._usuario("mira_alertas", ("dispositivo.ver", "dispositivo.editar"), [self.cis])

    def _medir(self):
        with CaptureQueriesContext(connection) as medida:
            alertas = alertas_del_dispositivo(self.cis, usuario=self.mira)
        return len(medida), alertas

    def test_las_alertas_respetan_el_presupuesto_y_no_crecen_con_los_origenes(self):
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]["consultas_fijas"]
        self._todas_encendidas()
        # Las capacidades del usuario y el programa se memoizan por request (`core.rbac`):
        # se calientan antes de medir, como en una petición real donde el mixin ya las pidió.
        self._medir()
        pocas, alertas = self._medir()
        self.assertEqual({alerta["regla"] for alerta in alertas}, SLUGS)

        plazas = Plaza.objects.bulk_create(Plaza(sector=self.sector, codigo=f"F{n}") for n in range(20))
        Plaza.objects.filter(pk__in=[plaza.pk for plaza in plazas]).update(
            estado=Plaza.Estado.FUERA_SERVICIO, motivo_fuera_servicio="Obra"
        )
        for plaza in Plaza.objects.bulk_create(Plaza(sector=self.sector, codigo=f"R{n}") for n in range(10)):
            self._prestamo_vencido(plaza=plaza)
        for n in range(5):
            edificio = Edificio.objects.create(codigo=f"ED-{n}", nombre=f"Edificio {n}")
            edificio.dispositivos.add(self.cis)
            registrar_resultado(self.agente, self._relevamiento(edificio=edificio), criticidad=Criticidad.ALTA)
        muchas, alertas = self._medir()

        self.assertEqual(muchas, pocas, "una consulta por plaza, reserva o edificio sería un N+1")
        self.assertLessEqual(muchas, techo)
        self.assertGreater(len(alertas), 15)
