"""La ficha del caso: «Qué hacer ahora» y las solapas (Cambio 589, PR E del replanteo de Emergencia).

El bloque no decide nada: elige, entre las acciones que la ficha ya trae, la que corresponde al estado, y solo ofrece
las que quien mira puede usar (los mismos predicados que vuelve a exigir el servicio). Estos tests fijan esa selección
por estado y por perfil, que no se ofrezca lo que el servicio rechaza ni lo que pide una capacidad que falta, y que la
solapa correcta quede a la vista cuando un formulario vuelve con errores.
"""

import re
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from programas.models import CasoEmergencia
from programas.selectors import emergencia_mesa as mesa
from programas.services import emergencia as servicio
from programas.services import emergencia_alojar as alojar
from programas.services.configuracion_emergencia import sla_vigente
from programas.tests.test_emergencia_alojar_base import BaseAlojar
from programas.tests.test_emergencia_base import OPERAR, SUPERVISAR

Estado = CasoEmergencia.Estado
CAP = "emergencia.cerrar_reabrir"

#: Lo que ``acciones_posibles`` y los predicados de la mesa contestan, con todo apagado.
APAGADAS = {
    "puede_tomar": False,
    "puede_derivar": False,
    "puede_cancelar_derivacion": False,
    "puede_cancelar_ingreso": False,
    "puede_reabrir": False,
    "puede_actuar": False,
    "puede_cerrar": False,
    "puede_cerrar_alojado": False,
    "solo_lectura": False,
}


def _paso(urgente=False, nota=""):
    return {"texto": "Un paso", "nota": nota, "urgente": urgente}


class QueHacerAhoraPuraTests(SimpleTestCase):
    """La selección, sin base de datos: cada predicado enciende su botón y el orden es de más a menos importante."""

    def _claves(self, estado=Estado.EN_GESTION, paso=None, caso=None, **encendidas):
        caso = caso or CasoEmergencia(estado=estado)
        ahora = mesa.que_hacer_ahora(caso, {**APAGADAS, **encendidas}, paso or _paso())
        return [accion["clave"] for accion in ahora["acciones"]]

    def test_sin_ningun_permiso_el_bloque_solo_informa(self):
        self.assertEqual(self._claves(), [])

    def test_cada_predicado_enciende_solo_su_boton(self):
        casos = {
            "puede_tomar": "tomar",
            "puede_derivar": "derivar",
            "puede_cancelar_derivacion": "cancelar_derivacion",
            "puede_cancelar_ingreso": "cancelar_ingreso",
            "puede_reabrir": "reabrir",
            "puede_actuar": "contacto",
            "puede_cerrar": "cerrar",
            "puede_cerrar_alojado": "cerrar_alojado",
        }
        for predicado, clave in casos.items():
            with self.subTest(predicado):
                self.assertEqual(self._claves(**{predicado: True}), [clave])

    def test_los_botones_principales_van_primero(self):
        claves = self._claves(puede_cerrar=True, puede_actuar=True, puede_derivar=True)
        self.assertEqual(claves, ["derivar", "contacto", "cerrar"])

    def test_cancelar_la_derivacion_pasa_a_principal_solo_si_el_paso_es_urgente(self):
        normal = mesa.que_hacer_ahora(
            CasoEmergencia(estado=Estado.DERIVADO), {**APAGADAS, "puede_cancelar_derivacion": True}, _paso(False)
        )
        urgente = mesa.que_hacer_ahora(
            CasoEmergencia(estado=Estado.DERIVADO), {**APAGADAS, "puede_cancelar_derivacion": True}, _paso(True)
        )
        self.assertEqual(normal["acciones"][0]["tono"], "secondary")
        self.assertEqual(urgente["acciones"][0]["tono"], "brand")

    def test_el_contacto_es_principal_en_un_ingreso_parcial_y_de_apoyo_en_el_resto(self):
        # ``ingreso_parcial`` es una propiedad del modelo (sale de ``total_alojado`` y del grupo): se la simula.
        parcial = SimpleNamespace(estado=Estado.ALOJADO, abierto=True, ingreso_parcial=True)
        completo = SimpleNamespace(estado=Estado.ALOJADO, abierto=True, ingreso_parcial=False)
        for caso, tono in ((parcial, "brand"), (completo, "secondary")):
            ahora = mesa.que_hacer_ahora(
                caso, {**APAGADAS, "puede_actuar": True, "puede_cerrar_alojado": True}, _paso()
            )
            contacto = next(accion for accion in ahora["acciones"] if accion["clave"] == "contacto")
            self.assertEqual(contacto["tono"], tono)

    def test_un_caso_cerrado_no_repite_el_motivo_que_ya_muestra_su_aviso(self):
        paso = _paso(nota="Otro motivo")
        cerrado = mesa.que_hacer_ahora(CasoEmergencia(estado=Estado.CERRADO), dict(APAGADAS), paso)
        abierto = mesa.que_hacer_ahora(CasoEmergencia(estado=Estado.EN_GESTION), dict(APAGADAS), paso)
        self.assertEqual((cerrado["nota"], abierto["nota"]), ("", "Otro motivo"))

    def test_las_ayudas(self):
        sin_dueno = mesa.que_hacer_ahora(
            CasoEmergencia(estado=Estado.NUEVO), {**APAGADAS, "puede_tomar": True}, _paso(), tomar_para_gestionar=True
        )
        self.assertIn("derivarla o cerrar el caso", sin_dueno["ayuda"])
        derivado = mesa.que_hacer_ahora(
            CasoEmergencia(estado=Estado.DERIVADO),
            {**APAGADAS, "puede_tomar": True},
            _paso(),
            tomar_para_gestionar=False,
        )
        self.assertIn("Tomalo para hacerte cargo", derivado["ayuda"])
        self.assertNotIn("derivarla o cerrar el caso", derivado["ayuda"])
        ajeno = mesa.que_hacer_ahora(
            CasoEmergencia(estado=Estado.EN_GESTION), {**APAGADAS, "solo_lectura": True}, _paso()
        )
        self.assertIn("quien lo tiene tomado", ajeno["ayuda"])


class _Base(BaseAlojar):
    def setUp(self):
        super().setUp()
        self.jefe = self._usuario("jefe_mesa", [OPERAR, SUPERVISAR, CAP])

    # Los casos, uno por estado.
    def _alojada(self, **kwargs):
        caso, derivacion = self._aceptado(menores_f=0, menores_m=0, adultos_f=1, adultos_m=1, **kwargs)
        for orden, reserva in enumerate(self._reservas(derivacion), start=1):
            self._confirmar(caso, orden, str(45_000_100 + orden), plaza=reserva.plaza)
        return alojar.alojar_familia(caso=caso, usuario=self.guardia)

    def _cerrado(self):
        return servicio.cerrar_sin_alojamiento(self._caso_tomado(dni="30222333"), self.operador, "NO_REQUIERE")

    def _ficha(self, caso, usuario, **parametros):
        self.client.force_login(User.objects.get(pk=usuario.pk))
        return self.client.get(reverse("emergencia:caso_detalle", args=[caso.pk]), parametros)

    def _claves(self, caso, usuario):
        return [accion["clave"] for accion in self._ficha(caso, usuario).context["que_hacer"]["acciones"]]

    def _bloque(self, respuesta):
        """El HTML del bloque «Qué hacer ahora», sin el resto de la ficha (el menú «Más acciones» repite textos)."""

        html = respuesta.content.decode()
        return re.search(r'aria-labelledby="caso-ahora-titulo">(.*?)</section>', html, re.S).group(1)


class QueHacerPorEstadoYPerfilTests(_Base):
    """Qué botones ve cada perfil en cada estado: la regla de cada fila es la del servicio, no una copia."""

    def test_un_caso_nuevo_sin_dueno(self):
        nuevo = self._caso()
        self.assertEqual(self._claves(nuevo, self.operador), ["tomar"])
        self.assertEqual(self._claves(nuevo, self.supervisor), ["tomar", "contacto"])

    def test_un_caso_en_gestion(self):
        caso = self._caso_tomado()
        self.assertEqual(self._claves(caso, self.operador), ["derivar", "contacto", "cerrar"])
        self.assertEqual(self._claves(caso, self.supervisor), ["derivar", "contacto", "cerrar"])
        # Otro operador lo ve sin botones: el paso le toca a quien lo tiene tomado.
        respuesta = self._ficha(caso, self.otro_operador)
        self.assertEqual(respuesta.context["que_hacer"]["acciones"], [])
        self.assertIn("quien lo tiene tomado", respuesta.context["que_hacer"]["ayuda"])

    def test_un_caso_derivado_ofrece_cancelar_la_derivacion_y_no_derivar(self):
        caso, _ = self._derivado()
        self.assertEqual(self._claves(caso, self.operador), ["cancelar_derivacion", "contacto"])
        self.assertEqual(self._claves(caso, self.otro_operador), [])

    def test_un_ingreso_en_curso_sin_confirmados_se_cancela_solo_con_supervision(self):
        caso, _ = self._aceptado()
        self.assertEqual(self._claves(caso, self.operador), ["contacto"])
        self.assertEqual(self._claves(caso, self.supervisor), ["cancelar_ingreso", "contacto"])

    def test_un_caso_alojado_se_cierra_solo_con_la_capacidad(self):
        caso = self._alojada()
        self.assertEqual(self._claves(caso, self.operador), ["contacto"])
        self.assertEqual(self._claves(caso, self.supervisor), ["contacto"])
        self.assertEqual(self._claves(caso, self.jefe), ["contacto", "cerrar_alojado"])

    def test_un_ingreso_parcial_pone_primero_el_contacto_con_la_familia(self):
        caso, _ = self._aceptado(menores_f=0, menores_m=0, adultos_f=1, adultos_m=2)
        self._confirmar(caso, 1, "45000101")
        caso = alojar.cerrar_con_diferencia(caso=caso, usuario=self.guardia, motivo="NO_LLEGO")
        self.assertTrue(caso.ingreso_parcial)

        ahora = self._ficha(caso, self.jefe).context["que_hacer"]

        self.assertEqual([accion["clave"] for accion in ahora["acciones"]], ["contacto", "cerrar_alojado"])
        self.assertEqual(ahora["acciones"][0]["tono"], "brand")
        self.assertIn("Contactar a la familia", ahora["paso"])

    def test_un_caso_cerrado_se_reabre_solo_con_la_capacidad(self):
        caso = self._cerrado()
        self.assertEqual(self._claves(caso, self.operador), [])
        self.assertEqual(self._claves(caso, self.supervisor), [])
        self.assertEqual(self._claves(caso, self.jefe), ["reabrir"])

    def test_el_paso_es_el_de_la_columna_que_falta_de_la_bandeja(self):
        """Una sola fuente: el texto del bloque es el de ``que_falta``, el de la bandeja."""

        casos = [self._caso(), self._caso_tomado(dni="30555111"), self._derivado()[0], self._cerrado()]
        for caso in casos:
            with self.subTest(estado=caso.estado):
                anotado = mesa.casos_para_ficha().get(pk=caso.pk)
                esperado = mesa.que_falta(anotado, sla_vigente(), timezone.now())
                ficha = self._ficha(caso, self.jefe).context["que_hacer"]
                self.assertEqual(ficha["paso"], esperado["texto"])


class LoQueSeOfreceLoAceptaElServicioTests(_Base):
    """Cada botón del bloque apunta a algo que la ficha ya trae armado, y el servicio lo acepta."""

    #: Qué trae el contexto de la ficha para que ese botón funcione.
    ARMADO_POR = {
        "derivar": "panel",
        "contacto": "form_contacto",
        "cancelar_derivacion": "form_cancelar",
        "cancelar_ingreso": "form_cancelar_ingreso",
        "cerrar": "form_cierre",
        "cerrar_alojado": "form_cerrar_alojado",
    }

    def _casos(self):
        return [
            self._caso(),
            self._caso_tomado(dni="30555111"),
            self._derivado()[0],
            self._aceptado(dni="30666222")[0],
            self._alojada(dni="30777333"),
            self._cerrado(),
        ]

    def test_ningun_boton_queda_sin_su_formulario_o_su_panel(self):
        casos = self._casos()
        for usuario in (self.operador, self.supervisor, self.otro_operador, self.jefe):
            for caso in casos:
                respuesta = self._ficha(caso, usuario)
                bloque = self._bloque(respuesta)
                for accion in respuesta.context["que_hacer"]["acciones"]:
                    with self.subTest(estado=caso.estado, usuario=usuario.username, accion=accion["clave"]):
                        clave = self.ARMADO_POR.get(accion["clave"])
                        if clave:
                            self.assertIn(clave, respuesta.context)
                        self.assertIn(accion["texto"], bloque)

    def test_el_bloque_dibuja_exactamente_lo_que_dice_el_contexto(self):
        caso = self._caso_tomado()
        respuesta = self._ficha(caso, self.operador)
        bloque = self._bloque(respuesta)
        for texto in ("Elegir institución", "Anotar un contacto", "Cerrar sin alojar"):
            self.assertIn(texto, bloque)
        for texto in ("Tomar el caso", "Cancelar la derivación", "Reabrir el caso", "la familia ya no está"):
            self.assertNotIn(texto, bloque)
        self.assertIn('href="#caso-derivar-titulo"', bloque)
        self.assertIn('id="caso-derivar-titulo"', respuesta.content.decode())

    def test_tomar_es_un_post_a_la_url_de_tomar(self):
        nuevo = self._caso()
        bloque = self._bloque(self._ficha(nuevo, self.operador))
        self.assertIn(f'action="{reverse("emergencia:caso_tomar", args=[nuevo.pk])}"', bloque)
        self.assertIn("Nadie tomó este caso todavía", bloque)

    def test_reabrir_confirma_con_la_url_de_reabrir_y_sin_la_capacidad_no_hay_boton(self):
        cerrado = self._cerrado()
        con = self._bloque(self._ficha(cerrado, self.jefe))
        sin = self._bloque(self._ficha(cerrado, self.supervisor))
        self.assertIn(f'data-confirm-url="{reverse("emergencia:caso_reabrir", args=[cerrado.pk])}"', con)
        self.assertNotIn("Reabrir", sin)

    def test_lo_que_ofrece_el_bloque_el_servicio_lo_acepta(self):
        derivable = self._caso_tomado(dni="30888444")
        self.client.force_login(User.objects.get(pk=self.operador.pk))
        self.assertEqual(
            self.client.post(
                reverse("emergencia:caso_contacto", args=[derivable.pk]),
                {"canal": "LLAMADA", "resultado": "ATENDIO", "observacion": ""},
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("emergencia:caso_cerrar", args=[derivable.pk]), {"motivo": "NO_REQUIERE", "observacion": ""}
            ).status_code,
            302,
        )
        self.assertEqual(CasoEmergencia.objects.get(pk=derivable.pk).estado, Estado.CERRADO)


class SolapasDeLaFichaTests(_Base):
    def _tab(self, respuesta):
        return re.search(r"x-data=\"\{ tab: '([^']*)'", respuesta.content.decode()).group(1)

    def test_las_cinco_solapas_con_su_aria(self):
        caso = self._caso_tomado()
        html = self._ficha(caso, self.operador).content.decode()
        self.assertIn('role="tablist" aria-label="Secciones del caso"', html)
        for clave in mesa.SOLAPAS_DE_LA_FICHA:
            with self.subTest(clave):
                self.assertIn(f'id="tab-{clave}" aria-controls="panel-{clave}"', html)
                self.assertIn(f'role="tabpanel" id="panel-{clave}" aria-labelledby="tab-{clave}"', html)
        self.assertEqual(html.count('role="tab"'), 5)

    def test_abre_en_familia_y_respeta_la_solapa_de_la_url(self):
        caso = self._caso_tomado()
        self.assertEqual(self._tab(self._ficha(caso, self.operador)), "familia")
        for clave in mesa.SOLAPAS_DE_LA_FICHA:
            with self.subTest(clave):
                respuesta = self._ficha(caso, self.operador, tab=clave)
                self.assertEqual((respuesta.context["solapa"], self._tab(respuesta)), (clave, clave))

    def test_una_solapa_que_no_existe_cae_en_familia_y_no_se_cuela_al_html(self):
        caso = self._caso_tomado()
        respuesta = self._ficha(caso, self.operador, tab="'});alert(1);({'")
        self.assertEqual(self._tab(respuesta), "familia")
        self.assertNotContains(respuesta, "alert(1)")

    def test_los_numeros_de_las_solapas_salen_de_lo_que_hay(self):
        caso = self._caso_tomado()
        self.client.force_login(User.objects.get(pk=self.operador.pk))
        self.client.post(
            reverse("emergencia:caso_contacto", args=[caso.pk]),
            {"canal": "LLAMADA", "resultado": "ATENDIO", "observacion": "Esperan"},
        )
        conteos = self._ficha(caso, self.operador).context["conteos"]
        self.assertEqual(conteos["contactos"], 1)
        self.assertEqual(conteos["personas"], caso.grupo.total_declarado)
        self.assertEqual(conteos["fotos"], 0)
        self.assertGreaterEqual(conteos["historial"], 2)

    def test_un_contacto_con_errores_vuelve_con_la_solapa_de_contactos_a_la_vista(self):
        caso = self._caso_tomado()
        self.client.force_login(User.objects.get(pk=self.operador.pk))

        respuesta = self.client.post(
            reverse("emergencia:caso_contacto", args=[caso.pk]), {"canal": "", "resultado": ""}
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual((respuesta.context["solapa"], self._tab(respuesta)), ("contactos", "contactos"))
        self.assertEqual(self._tab(self._ficha(caso, self.operador)), "familia")

    def test_otro_formulario_con_errores_conserva_su_modal_y_no_toca_la_solapa(self):
        caso = self._caso_tomado()
        self.client.force_login(User.objects.get(pk=self.operador.pk))

        respuesta = self.client.post(reverse("emergencia:caso_cerrar", args=[caso.pk]), {"motivo": ""})

        self.assertEqual((respuesta.status_code, respuesta.context["modal_abierto"]), (400, "cerrar"))
        self.assertEqual(self._tab(respuesta), "familia")
        self.assertIn("modalCerrar: true", respuesta.content.decode())

    def test_registrar_un_contacto_lleva_a_su_solapa(self):
        caso = self._caso_tomado()
        self.client.force_login(User.objects.get(pk=self.operador.pk))
        respuesta = self.client.post(
            reverse("emergencia:caso_contacto", args=[caso.pk]),
            {"canal": "LLAMADA", "resultado": "ATENDIO", "observacion": ""},
        )
        self.assertRedirects(
            respuesta,
            reverse("emergencia:caso_detalle", args=[caso.pk]) + "?tab=contactos",
            fetch_redirect_response=False,
        )

    def test_el_modal_de_derivar_por_url_sigue_abriendo(self):
        caso = self._caso_tomado()
        respuesta = self._ficha(caso, self.operador, derivar=self.club.pk)
        self.assertIn("panel", respuesta.context)
        self.assertEqual(self._tab(respuesta), "familia")
