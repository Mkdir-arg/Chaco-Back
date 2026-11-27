"""Infraestructura del dispositivo como tarjetas por edificio y ficha (Cambio 439).

Lo que se fija acá: el orden del más grave al mejor, el filtro por estado, los avisos de vencimiento, el
aviso de sectores sin edificio según la capacidad, las acciones de la ficha según la capacidad y que, sin
alcance de inspección (Cambio 428), ni la tarjeta ni la ficha cuentan lo que el relevamiento dice.
"""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from programas.forms_dispositivos import AsignarRelevamientoDispositivoForm
from programas.models import Edificio, InspeccionEdificio
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura, _panel
from programas.tests.test_dispositivos_inspecciones import Criticidad

Estado = InspeccionEdificio.Estado

ACCIONES = (
    "Agregar edificio",
    "Cargar un edificio nuevo",
    "Vincular uno existente",
    "Crear relevamiento",
    "Editar edificio",
    "Desvincular",
)


class BaseTarjetas(BaseInfraestructura):
    def setUp(self):
        super().setUp()
        self.edificio_cis.dispositivos.add(self.parador)
        self.sin_relevar = Edificio.objects.create(codigo="ED-NUEVO", nombre="Anexo sin relevar")
        self.sin_relevar.dispositivos.add(self.parador)
        self._relevar(self.predio, Criticidad.MEDIA, observaciones="Faltan dos duchas")
        self._relevar(self.edificio_cis, Criticidad.ALTA, observaciones="Pérdida de gas")
        self.solo_ver = self._usuario("solo_ver", ("dispositivo.ver",), [self.parador])
        # Ve la institución (ver_todos) pero no la opera ni la coordina: sin alcance de inspección.
        self.sin_alcance = self._usuario("sin_alcance", ("dispositivo.ver", "dispositivo.ver_todos"))

    def _infra(self, usuario=None, **params):
        respuesta = self._detalle(usuario or self.admin, self.parador, tab="infraestructura", **params)
        return respuesta, respuesta.context["infraestructura"], _panel(respuesta.content.decode())


class EdificioDelFormularioTests(SimpleTestCase):
    def _form(self, n):
        edificios = [Edificio(pk=pk, codigo=f"ED-{pk}", nombre=f"Edificio {pk}") for pk in range(1, n + 1)]
        return AsignarRelevamientoDispositivoForm(edificios=edificios, agentes=get_user_model().objects.none())

    def test_con_varios_arranca_vacio_y_editable(self):
        form = self._form(2)

        self.assertFalse(form["edificio"].value())
        self.assertFalse(form.edificio_fijo)

    def test_con_uno_solo_va_fijo(self):
        form = self._form(1)

        self.assertTrue(form.edificio_fijo)
        self.assertEqual(form["edificio"].value(), "1")
