"""Emergencia · alojar con alcance por edificio (Cambio 532; relevamiento del 22/11/2026, hallazgos 1, 4, 13, 18 y 11).

El Club se parte en dos edificios: **A** con el sector «General» (9 camas) y **B** con el «Anexo» (3 camas).
``guardia`` sigue con alcance Institución y ``guardia_b`` es del Equipo con alcance Edificios sobre B.

* 1 — aceptar una derivación a B reserva solo camas de B (si no alcanzan, faltan), y la guardia de B
  sigue el ingreso aunque lo haya aceptado otro: la reserva sobrante se libera sin su alcance y «no
  hay cama» mira las camas que ella puede elegir.
* 4 — con alcance Edificios se puede «Avisar a la mesa» y también «Ingresar igual», pero este último solo
  con camas de sus edificios (decisión del PM del 24/11/2026; antes exigía la institución entera). La
  pantalla y la API lo dicen antes del 403.
* 13 — «mis dispositivos» cuenta camas y derivaciones de sus edificios, no de la institución.
* 18 — el ingreso directo nace con el edificio de las camas que reservó.
* 11 — el Formulario 1 del backoffice lleva su ``uuid_cliente``: el mismo envío dos veces es un caso.

Mutaciones verificadas (cada una pone en rojo al menos un test de acá): sacar ``edificio_id`` de
``aceptar_derivacion``; liberar la sobrante con ``verificar_alcance=True``; ``_hay_cama_para_elegir``
sin ``usuario``; ``avisar_a_la_mesa`` con alcance de institución; sacar el filtro de edificio de
``resumen_de_llegadas``; el ingreso directo sin ``edificio_id``; no pasar ``uuid_cliente`` al servicio;
(24/11/2026) ``camas_libres`` sin el filtro por edificio del usuario: ponen en rojo los tests de «Ingresar igual»
con camas libres solo en otro edificio.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import (
    CasoEmergencia,
    Derivacion,
    Edificio,
    Estadia,
    MiembroEquipoDispositivo,
    Plaza,
    ReservaPlaza,
    Sector,
)
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.services.emergencia_confirmacion import SIN_CAMA_LIBRE
from programas.tests.base_emergencia_api import URL_MIS_DISPOSITIVOS, BaseApiLlegadas, _url
from programas.tests.test_emergencia_alojar_base import BaseAlojar, ficha_minima
from programas.tests.test_emergencia_casos import T0

Estado = CasoEmergencia.Estado

FORMULARIO1 = {
    "traslado": "BOMBEROS",
    "dni": "33444555",
    "nombre": "Marta",
    "apellido": "Ríos",
    "adultos_f": "1",
    "adultos_m": "1",
    "menores_f": "1",
}


def _partir_en_edificios(dispositivo):
    """A con los sectores que ya tiene y B con un «Anexo» nuevo de 3 camas. Devuelve ``(a, b)``."""

    edif_a = Edificio.objects.create(codigo=f"A-{dispositivo.pk}", nombre="Edificio A")
    edif_b = Edificio.objects.create(codigo=f"B-{dispositivo.pk}", nombre="Edificio B")
    edif_a.dispositivos.add(dispositivo)
    edif_b.dispositivos.add(dispositivo)
    Sector.objects.filter(dispositivo=dispositivo).update(edificio=edif_a)
    anexo = Sector.objects.create(dispositivo=dispositivo, nombre="Anexo", capacidad=3, edificio=edif_b)
    Plaza.objects.bulk_create([Plaza(sector=anexo, codigo=f"B-{n:02d}") for n in range(1, 4)])
    return edif_a, edif_b


def _con_alcance_edificios(usuario, dispositivo, *edificios):
    fila = MiembroEquipoDispositivo.objects.get(usuario=usuario, dispositivo=dispositivo)
    fila.alcance = MiembroEquipoDispositivo.Alcance.EDIFICIOS
    fila.save(update_fields=["alcance"])
    fila.edificios.set(edificios)
    return User.objects.get(pk=usuario.pk)


def _edificios_de(reservas):
    return {reserva.plaza.sector.edificio_id for reserva in reservas}


class BaseEdificios(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.edif_a, self.edif_b = _partir_en_edificios(self.club)
        self.guardia_b = _con_alcance_edificios(self._guardia("guardia_b", self.club), self.club, self.edif_b)

    def _derivado_a(self, edificio, plazas=None, **datos):
        datos = {"menores_f": 2, "menores_m": 3, "dni": "30111222", "nombre": "Rosa", "apellido": "Benítez", **datos}
        caso = self._caso_tomado(**datos)
        derivacion = mesa.derivar_caso(
            caso, self.operador, self.club, plazas or caso.grupo.total_declarado, True, edificio=edificio
        )
        return CasoEmergencia.objects.get(pk=caso.pk), derivacion

    def _ocupar_plazas(self, plazas):
        for n, plaza in enumerate(plazas):
            persona = Ciudadano.objects.create(dni=str(40_000_000 + n), nombre="Persona", apellido="Alojada")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=self.club,
                plaza=plaza,
                fecha_ingreso=T0 - timedelta(days=1),
                clave_alojamiento=Estadia.clave_para(persona),
            )


class AceptarPorEdificioTests(BaseEdificios):
    """Hallazgo 1."""

    def test_aceptar_reserva_solo_camas_del_edificio_derivado_y_si_no_alcanzan_faltan(self):
        _caso, derivacion = self._derivado_a(self.edif_b)

        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        self.assertEqual((resultado.reservadas, resultado.faltantes), (3, 4))
        self.assertEqual(_edificios_de(self._reservas(derivacion)), {self.edif_b.pk})
        self.assertIn("faltan 4 camas", resultado.mensaje)

    def test_la_guardia_del_edificio_confirma_en_la_cama_que_reservo_otro(self):
        caso, derivacion = self._derivado_a(self.edif_b, menores_f=1, menores_m=0)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)

        integrante = self._confirmar(caso, 1, "30111222", usuario=self.guardia_b)

        self.assertEqual(integrante.estadia.plaza.sector.edificio_id, self.edif_b.pk)

    def test_la_sobrante_de_otro_edificio_se_libera_al_confirmar_en_una_cama_libre(self):
        # Una derivación a B con las camas reservadas en A (como quedaron las aceptadas antes de este cambio).
        caso, derivacion = self._derivado_a(self.edif_b, menores_f=1, menores_m=0)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        camas_a = list(Plaza.objects.filter(sector__edificio=self.edif_a).order_by("pk"))
        for reserva, cama in zip(self._reservas(derivacion), camas_a, strict=False):
            ReservaPlaza.objects.filter(pk=reserva.pk).update(plaza=cama)
        reservadas = {reserva.plaza_id for reserva in self._reservas(derivacion)}
        libre_b = Plaza.objects.filter(sector__edificio=self.edif_b).exclude(pk__in=reservadas).first()

        integrante = self._confirmar(caso, 1, "30111222", plaza=libre_b, usuario=self.guardia_b)

        self.assertEqual(integrante.estadia.plaza_id, libre_b.pk)
        # 3 personas y 3 camas guardadas: al usar una libre, la sobrante (de A) se libera.
        self.assertEqual(len(self._reservas(derivacion)), 2)
        self.assertEqual(len(self._reservas(derivacion, ReservaPlaza.Estado.LIBERADA)), 1)

    def test_sin_camas_en_su_edificio_dice_que_no_hay_cama_aunque_haya_en_otro(self):
        caso, derivacion = self._derivado_a(self.edif_b, menores_f=1, menores_m=0)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        ReservaPlaza.objects.filter(derivacion=derivacion).update(estado=ReservaPlaza.Estado.LIBERADA)
        self._ocupar_plazas(Plaza.objects.filter(sector__edificio=self.edif_b).order_by("pk"))

        with self.assertRaises(ValidationError) as error:
            servicio.confirmar_integrante(
                caso=caso, orden=1, usuario=self.guardia_b, ficha=ficha_minima("30111222"), plaza=None
            )

        self.assertEqual(error.exception.message_dict["plaza"], [SIN_CAMA_LIBRE])


class SinDerivacionConAlcanceEdificiosTests(BaseEdificios):
    """Hallazgos 4 y 18 por el servicio."""

    def _datos(self, dni="33444555"):
        return {
            "traslado": "BOMBEROS",
            "dni": dni,
            "nombre": "Marta",
            "apellido": "Ríos",
            "adultos_f": 1,
            "adultos_m": 1,
            "menores_f": 1,
        }

    def test_con_alcance_edificios_avisa_a_la_mesa(self):
        caso = servicio.avisar_a_la_mesa(dispositivo=self.club, usuario=self.guardia_b, datos_formulario1=self._datos())

        self.assertEqual(caso.estado, Estado.NUEVO)
        puerta = caso.situacion[CasoEmergencia.SITUACION_EN_LA_PUERTA]
        self.assertEqual(puerta["dispositivo_id"], self.club.pk)

    def test_con_alcance_edificios_ingresa_igual_en_una_cama_de_su_edificio(self):
        caso = servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia_b, datos_formulario1=self._datos())

        derivacion = Derivacion.objects.get(caso=caso)
        self.assertEqual(derivacion.edificio_id, self.edif_b.pk)  # A tiene 9 libres, pero no son suyas
        self.assertEqual(_edificios_de(self._reservas(derivacion)), {self.edif_b.pk})
        self.assertEqual(caso.estado, Estado.INGRESO_EN_CURSO)

    def test_con_alcance_edificios_sin_camas_libres_en_su_edificio_no_ingresa_igual(self):
        self._ocupar_plazas(Plaza.objects.filter(sector__edificio=self.edif_b).order_by("pk"))  # A: 9, B: 0

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="33444555", usuario=self.guardia_b)
        self.assertEqual(resultado.plazas_libres, 0)
        with self.assertRaises(ValidationError) as error:
            servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia_b, datos_formulario1=self._datos())

        self.assertEqual(error.exception.message_dict["plazas"], [servicio.SIN_CAMAS_PARA_INGRESO_DIRECTO])
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_con_alcance_edificios_sin_edificios_vigentes_no_ingresa_igual(self):
        self.edif_b.dispositivos.remove(self.club)  # el edificio de la guardia ya no es de la institución

        self.assertFalse(servicio.puede_ingresar_igual(self.guardia_b, self.club))
        with self.assertRaises(PermissionDenied):
            servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia_b, datos_formulario1=self._datos())
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_las_camas_sin_edificio_no_se_ofrecen_a_alcance_edificios(self):
        self._ocupar_plazas(Plaza.objects.filter(sector__edificio=self.edif_b).order_by("pk"))
        Sector.objects.filter(dispositivo=self.club, edificio=self.edif_a).update(edificio=None)  # A: 9 sin edificio

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="33444555", usuario=self.guardia_b)
        self.assertEqual(resultado.plazas_libres, 0)
        with self.assertRaises(ValidationError):
            servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia_b, datos_formulario1=self._datos())
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_con_alcance_institucion_ingresa_en_camas_de_cualquier_edificio_y_sin_edificio(self):
        Sector.objects.filter(dispositivo=self.club, edificio=self.edif_a).update(
            edificio=None
        )  # 9 sin edificio, 3 en B

        caso = servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._datos())

        derivacion = Derivacion.objects.get(caso=caso)
        self.assertIsNone(derivacion.edificio_id)
        self.assertEqual(caso.reservadas, caso.grupo.total_declarado)

    def test_la_busqueda_dice_que_puede_hacer_cada_alcance(self):
        for usuario, esperado in ((self.guardia, (True, True)), (self.guardia_b, (True, True))):
            with self.subTest(usuario=usuario.username):
                resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="33444555", usuario=usuario)
                self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
                self.assertEqual((resultado.puede_ingresar_igual, resultado.puede_avisar_a_la_mesa), esperado)

    def test_el_ingreso_directo_nace_con_el_edificio_de_sus_camas(self):
        caso = servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia, datos_formulario1=self._datos())

        derivacion = Derivacion.objects.get(caso=caso)
        self.assertEqual(derivacion.edificio_id, self.edif_a.pk)  # A tiene 9 libres, B 3
        self.assertEqual(_edificios_de(self._reservas(derivacion)), {self.edif_a.pk})

    def test_el_ingreso_directo_no_mezcla_edificios_aunque_falten_camas(self):
        self._ocupar_plazas(Plaza.objects.filter(sector__edificio=self.edif_a).order_by("pk")[:8])  # A: 1, B: 3
        datos = {**self._datos(), "adultos_f": 2, "adultos_m": 2}  # 5 personas

        caso = servicio.ingreso_directo(dispositivo=self.club, usuario=self.guardia, datos_formulario1=datos)

        derivacion = Derivacion.objects.get(caso=caso)
        self.assertEqual(derivacion.edificio_id, self.edif_b.pk)
        self.assertEqual(_edificios_de(self._reservas(derivacion)), {self.edif_b.pk})
        self.assertEqual((caso.reservadas, caso.faltantes), (3, caso.grupo.total_declarado - 3))


class CasoAlojadoConAlcanceEdificiosTests(BaseEdificios):
    """Sumar personas a un caso ALOJADO acá: con alcance Edificios, solo si el ingreso es de uno de sus edificios."""

    def _alojado_en(self, edificio):
        caso, derivacion = self._derivado_a(edificio)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        CasoEmergencia.objects.filter(pk=caso.pk).update(estado=Estado.ALOJADO)
        return CasoEmergencia.objects.get(pk=caso.pk)

    def test_el_caso_alojado_en_otro_edificio_no_se_ingresa(self):
        caso = self._alojado_en(self.edif_a)

        with self.assertRaises(PermissionDenied):
            servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia_b, dni="30111222")

        self.assertEqual(CasoEmergencia.objects.get(pk=caso.pk).estado, Estado.ALOJADO)

    def test_el_caso_alojado_en_su_edificio_se_ingresa(self):
        caso = self._alojado_en(self.edif_b)

        resultado = servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia_b, dni="30111222")

        self.assertEqual(resultado.pk, caso.pk)
        self.assertEqual(CasoEmergencia.objects.get(pk=caso.pk).estado, Estado.INGRESO_EN_CURSO)

    def test_la_busqueda_no_ofrece_ingresar_con_caso_si_el_alojado_es_de_otro_edificio(self):
        self._alojado_en(self.edif_a)

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia_b)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
        self.assertIs(resultado.puede_ingresar_con_caso, False)
        institucion = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia)
        self.assertIs(institucion.puede_ingresar_con_caso, True)

    def test_la_busqueda_ofrece_ingresar_con_caso_si_el_alojado_es_de_su_edificio(self):
        self._alojado_en(self.edif_b)

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia_b)

        self.assertEqual(resultado.resultado, servicio.BUSQUEDA_SIN_DERIVACION)
        self.assertIs(resultado.puede_ingresar_con_caso, True)


class PantallaDeLlegadasConAlcanceEdificiosTests(BaseEdificios):
    """Hallazgos 4 y 11 por la web (E6)."""

    def _url(self, nombre, *args):
        return reverse(f"dispositivos:emergencia_{nombre}", args=[self.club.pk, *args])

    def test_con_alcance_edificios_ve_ingresar_igual_y_avisar_si_hay_camas_en_su_edificio(self):
        self.client.force_login(self.guardia_b)

        respuesta = self.client.get(self._url("llegadas"), {"dni": "33444555"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, self._url("ingreso_directo"))
        self.assertContains(respuesta, self._url("avisar"))

    def test_con_camas_libres_solo_en_otro_edificio_no_ve_ingresar_igual_y_si_avisar(self):
        self._ocupar_plazas(Plaza.objects.filter(sector__edificio=self.edif_b).order_by("pk"))
        self.client.force_login(self.guardia_b)

        respuesta = self.client.get(self._url("llegadas"), {"dni": "33444555"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self._url("ingreso_directo"))
        self.assertContains(respuesta, self._url("avisar"))
        self.assertContains(respuesta, "No hay camas libres")

    def test_el_post_con_camas_libres_solo_en_otro_edificio_se_rechaza(self):
        self._ocupar_plazas(Plaza.objects.filter(sector__edificio=self.edif_b).order_by("pk"))
        self.client.force_login(self.guardia_b)

        self.client.post(self._url("ingreso_directo"), FORMULARIO1)

        self.assertFalse(CasoEmergencia.objects.exists())

    def test_el_post_con_alcance_edificios_ingresa_en_su_edificio(self):
        self.client.force_login(self.guardia_b)

        self.client.post(self._url("ingreso_directo"), FORMULARIO1)

        self.assertEqual(Derivacion.objects.get().edificio_id, self.edif_b.pk)

    def test_la_familia_derivada_a_otro_edificio_no_se_invita_a_avisar_a_la_mesa(self):
        self._derivado_a(self.edif_a, dni="33444555")
        self.client.force_login(self.guardia_b)

        respuesta = self.client.get(self._url("llegadas"), {"dni": "33444555"})

        self.assertContains(
            respuesta, f"La familia ya está derivada al edificio {self.edif_a.nombre} de este dispositivo."
        )
        self.assertContains(respuesta, "Ya está derivada a ese edificio")
        self.assertNotContains(respuesta, "avisale a la mesa")
        self.assertNotContains(respuesta, self._url("avisar"))
        self.assertNotContains(respuesta, self._url("ingreso_directo"))

    def test_con_alcance_institucion_ve_los_dos_botones(self):
        self.client.force_login(self.guardia)

        respuesta = self.client.get(self._url("llegadas"), {"dni": "33444555"})

        self.assertContains(respuesta, self._url("ingreso_directo"))
        self.assertContains(respuesta, self._url("avisar"))

    def test_el_formulario_de_ingresar_igual_se_abre_con_alcance_edificios(self):
        self.client.force_login(self.guardia_b)

        respuesta = self.client.get(self._url("ingreso_directo"))

        self.assertEqual(respuesta.status_code, 200)

    def test_el_formulario_de_ingresar_igual_no_se_abre_sin_edificios_vigentes(self):
        self.edif_b.dispositivos.remove(self.club)
        self.client.force_login(self.guardia_b)

        respuesta = self.client.get(self._url("ingreso_directo"))

        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)

    def test_el_post_de_ingresar_igual_sin_alcance_conserva_el_formulario(self):
        self.edif_b.dispositivos.remove(self.club)
        self.client.force_login(self.guardia_b)

        respuesta = self.client.post(self._url("ingreso_directo"), FORMULARIO1)

        self.assertEqual(respuesta.status_code, 403)
        self.assertContains(respuesta, "Marta", status_code=403)
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_con_alcance_edificios_avisa_a_la_mesa_por_la_web(self):
        self.client.force_login(self.guardia_b)

        respuesta = self.client.post(self._url("avisar"), FORMULARIO1)

        self.assertRedirects(respuesta, self._url("llegadas"), fetch_redirect_response=False)
        self.assertEqual(CasoEmergencia.objects.get().estado, Estado.NUEVO)

    def test_el_mismo_formulario_enviado_dos_veces_es_un_solo_ingreso(self):
        self.client.force_login(self.guardia)
        envio = self.client.get(self._url("ingreso_directo")).context["form"].initial["uuid_cliente"]
        datos = {**FORMULARIO1, "uuid_cliente": str(envio)}

        primera = self.client.post(self._url("ingreso_directo"), datos, follow=True)
        segunda = self.client.post(self._url("ingreso_directo"), datos, follow=True)

        caso = CasoEmergencia.objects.get()
        self.assertEqual(primera.redirect_chain, segunda.redirect_chain)
        self.assertEqual(ReservaPlaza.objects.filter(derivacion__caso=caso).count(), caso.grupo.total_declarado)
        self.assertIn(f"Caso {caso.numero} creado", " ".join(_mensajes(primera)))
        self.assertEqual(_mensajes(segunda), [f"Ese formulario ya se había enviado: es el caso {caso.numero}."])

    def test_el_mismo_aviso_enviado_dos_veces_es_un_solo_caso(self):
        self.client.force_login(self.guardia_b)
        envio = self.client.get(self._url("avisar")).context["form"].initial["uuid_cliente"]
        datos = {**FORMULARIO1, "uuid_cliente": str(envio)}

        primera = self.client.post(self._url("avisar"), datos, follow=True)
        segunda = self.client.post(self._url("avisar"), datos, follow=True)

        caso = CasoEmergencia.objects.get()
        self.assertIn(f"Caso {caso.numero} enviado a la mesa", " ".join(_mensajes(primera)))
        self.assertEqual(_mensajes(segunda), [f"Ese formulario ya se había enviado: es el caso {caso.numero}."])


class CasoAbiertoDeEsteDispositivoConAlcanceEdificiosTests(BaseEdificios):
    """El caso abierto de este dispositivo en un edificio ajeno no se toma en ningún estado (ronda de auditoría)."""

    def _ingresando_en(self, edificio):
        caso, derivacion = self._derivado_a(edificio)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        caso = CasoEmergencia.objects.get(pk=caso.pk)
        self.assertEqual(caso.estado, Estado.INGRESO_EN_CURSO)
        return caso

    def test_el_ingreso_en_curso_de_otro_edificio_no_se_toma_por_ningun_camino(self):
        caso = self._ingresando_en(self.edif_a)

        with self.assertRaises(PermissionDenied):
            servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia_b, dni="30111222")
        with self.assertRaises(PermissionDenied):
            servicio.ingreso_directo(
                dispositivo=self.club,
                usuario=self.guardia_b,
                datos_formulario1={"traslado": "BOMBEROS", "dni": "30111222", "adultos_f": "1"},
            )

        self.assertEqual(CasoEmergencia.objects.get(pk=caso.pk).estado, Estado.INGRESO_EN_CURSO)

    def test_el_ingreso_en_curso_de_su_edificio_sigue_siendo_suyo(self):
        caso = self._ingresando_en(self.edif_b)

        resultado = servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia_b, dni="30111222")

        self.assertEqual(resultado.pk, caso.pk)

    def test_la_derivacion_pendiente_a_otro_edificio_de_este_dispositivo_no_se_toma(self):
        caso, derivacion = self._derivado_a(self.edif_a)

        with self.assertRaises(PermissionDenied):
            servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia_b, dni="30111222")

        self.assertEqual(Derivacion.objects.get(pk=derivacion.pk).estado, Derivacion.Estado.PENDIENTE)
        self.assertEqual(CasoEmergencia.objects.get(pk=caso.pk).estado, Estado.DERIVADO)

    def test_la_busqueda_no_ofrece_ingresar_con_caso_si_lo_derivado_es_de_otro_edificio(self):
        self._derivado_a(self.edif_a)

        resultado = servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia_b)

        self.assertIs(resultado.puede_ingresar_con_caso, False)

    def test_con_alcance_institucion_puede_con_el_caso_de_cualquier_edificio(self):
        caso = self._ingresando_en(self.edif_a)

        resultado = servicio.ingresar_con_caso_abierto(dispositivo=self.club, usuario=self.guardia, dni="30111222")

        self.assertEqual(resultado.pk, caso.pk)

    def test_la_busqueda_con_familia_alojada_no_repite_la_consulta_de_la_derivacion(self):
        caso, derivacion = self._derivado_a(self.edif_b)
        servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        CasoEmergencia.objects.filter(pk=caso.pk).update(estado=Estado.ALOJADO)
        servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia_b)  # calienta cachés
        with CaptureQueriesContext(connection) as capturadas:
            servicio.buscar_por_dni(dispositivo=self.club, dni="30111222", usuario=self.guardia_b)
        del_caso = [q for q in capturadas.captured_queries if 'WHERE "programas_derivacion"."caso_id" =' in q["sql"]]
        self.assertEqual(len(del_caso), 1, "la última derivación del caso se lee una sola vez")
        self.assertEqual(len(capturadas), 17)


def _mensajes(respuesta):
    """Los mensajes que mostró la pantalla a la que llevó el POST (seguido con ``follow=True``)."""
    return [str(m) for m in respuesta.context["messages"]]


class ApiConAlcanceEdificiosTests(BaseApiLlegadas):
    """Hallazgos 4 y 13 por la API de la app."""

    def setUp(self):
        super().setUp()
        self.edif_a, self.edif_b = _partir_en_edificios(self.centro)
        self.guardia_b = _con_alcance_edificios(
            self._guardia("guardia_b", ["dispositivo.ver", "dispositivo.admitir"], [self.centro]),
            self.centro,
            self.edif_b,
        )

    def _derivado_a(self, edificio, dni):
        caso = self._caso_tomado(menores_f=0, menores_m=0, dni=dni)
        return mesa.derivar_caso(caso, self.operador, self.centro, 1, True, edificio=edificio)

    def test_mis_dispositivos_cuenta_solo_lo_de_sus_edificios(self):
        self._derivado_a(self.edif_a, "31000001")
        self._derivado_a(self.edif_b, "31000002")

        def fila(usuario):
            filas = self._como(usuario).get(URL_MIS_DISPOSITIVOS).json()
            return next((f["plazas_libres"], f["derivaciones_pendientes"]) for f in filas if f["id"] == self.centro.pk)

        self.assertEqual(fila(self.guardia_b), (3, 1))
        self.assertEqual(fila(self.guardia_centro), (12, 2))

    def test_buscar_trae_las_dos_banderas(self):
        for usuario, esperado in ((self.guardia_centro, (True, True)), (self.guardia_b, (True, True))):
            with self.subTest(usuario=usuario.username):
                cuerpo = self._como(usuario).get(_url("dispositivo-buscar", self.centro.pk), {"dni": "33444555"}).json()
                self.assertEqual(cuerpo["resultado"], "SIN_DERIVACION")
                self.assertEqual((cuerpo["puede_ingresar_igual"], cuerpo["puede_avisar_a_la_mesa"]), esperado)

    def test_con_derivacion_las_banderas_vienen_en_false(self):
        _caso, _derivacion = self._derivado()

        cuerpo = self._como(self.guardia_centro).get(_url("dispositivo-buscar", self.centro.pk), {"dni": "30111222"})

        self.assertEqual(cuerpo.json()["resultado"], "DERIVACION")
        self.assertEqual(
            (cuerpo.json()["puede_ingresar_igual"], cuerpo.json()["puede_avisar_a_la_mesa"]), (False, False)
        )

    def test_con_alcance_edificios_avisa_a_la_mesa_por_la_api(self):
        respuesta = self._como(self.guardia_b).post(
            _url("dispositivo-avisar-mesa", self.centro.pk), self._cuerpo(), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.content)

    def _ocupar_edificio_b(self):
        for n, plaza in enumerate(Plaza.objects.filter(sector__edificio=self.edif_b)):
            persona = Ciudadano.objects.create(dni=str(40_000_000 + n), nombre="Persona", apellido="Alojada")
            Estadia.objects.create(
                ciudadano=persona,
                dispositivo=self.centro,
                plaza=plaza,
                fecha_ingreso=timezone.now() - timedelta(days=1),
                clave_alojamiento=Estadia.clave_para(persona),
            )

    def test_buscar_cuenta_solo_las_camas_de_sus_edificios_para_ingresar_igual(self):
        def buscar(usuario):
            return self._como(usuario).get(_url("dispositivo-buscar", self.centro.pk), {"dni": "33444555"}).json()

        self.assertEqual(buscar(self.guardia_b)["plazas_libres"], 3)
        self._ocupar_edificio_b()
        cuerpo = buscar(self.guardia_b)
        self.assertEqual((cuerpo["puede_ingresar_igual"], cuerpo["plazas_libres"]), (True, 0))
        self.assertEqual(buscar(self.guardia_centro)["plazas_libres"], 9)

    def test_ingreso_directo_con_alcance_edificios_crea_la_estadia_en_su_edificio(self):
        respuesta = self._como(self.guardia_b).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), self._cuerpo(), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        self.assertEqual(Derivacion.objects.get().edificio_id, self.edif_b.pk)

    def test_ingreso_directo_con_camas_libres_solo_en_otro_edificio_se_rechaza(self):
        self._ocupar_edificio_b()

        respuesta = self._como(self.guardia_b).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), self._cuerpo(), format="multipart"
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.content)
        self.assertFalse(CasoEmergencia.objects.exists())

    def test_ingreso_directo_sobre_el_ingreso_en_curso_de_otro_edificio_no_devuelve_personas(self):
        servicio_inicial = self._como(self.guardia_centro).post(
            _url("dispositivo-ingreso-directo", self.centro.pk), self._cuerpo(dni="33444555"), format="multipart"
        )
        self.assertEqual(servicio_inicial.status_code, 201, servicio_inicial.content)
        self.assertEqual(Derivacion.objects.get().edificio_id, self.edif_a.pk)

        respuesta = self._como(self.guardia_b).post(
            _url("dispositivo-ingreso-directo", self.centro.pk),
            self._cuerpo(dni="33444555", nombre=None, apellido=None),
            format="multipart",
        )

        self.assertEqual(respuesta.status_code, 404, respuesta.content)
        self.assertNotIn("integrantes", respuesta.json())
