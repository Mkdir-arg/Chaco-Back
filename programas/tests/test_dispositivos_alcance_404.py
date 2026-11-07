"""Sin alcance sobre un dispositivo, 404 (Cambio 432).

Decisión del PM: un usuario autenticado que pide un recurso de un dispositivo sobre el que no tiene
alcance recibe el mismo 404 que con un id inexistente, para no revelar qué dispositivos existen.
La falta de **capacidad** del módulo sigue siendo 403.

Cada caso compara un id ajeno con uno inexistente: mismo código y mismo cuerpo.
"""

from django.test import Client
from django.urls import reverse

from programas.tests.test_dispositivos_bitacora_pantalla import BasePantalla, _sin
from programas.tests.test_dispositivos_relevamientos_listado import _sin_token
from programas.tests.test_dispositivos_revision import BaseRevision

INEXISTENTE = 999999


class DispositivoAjenoIgualQueInexistenteTests(BasePantalla):
    def _pedir(self, nombre, pk, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse(nombre, args=[pk]))

    def _igual(self, nombre, usuario):
        ajeno = self._pedir(nombre, self.cis.pk, usuario)
        inexistente = self._pedir(nombre, INEXISTENTE, usuario)
        self.assertEqual((ajeno.status_code, inexistente.status_code), (404, 404), nombre)
        self.assertEqual(_sin_token(ajeno.content), _sin_token(inexistente.content), nombre)

    def test_detalle_sectores_y_bitacora(self):
        intruso = self._usuario("Operador parador", self.parador)

        for nombre in ("dispositivos:detalle", "dispositivos:sectores", "dispositivos:bitacora"):
            with self.subTest(nombre):
                self._igual(nombre, intruso)

    def test_sin_la_capacidad_del_modulo_sigue_siendo_403(self):
        sin_ver = self._usuario("Sin ver", self.cis, _sin("dispositivo.ver"))

        for nombre in ("dispositivos:detalle", "dispositivos:sectores", "dispositivos:bitacora"):
            with self.subTest(nombre):
                self.assertEqual(self._pedir(nombre, self.cis.pk, sin_ver).status_code, 403)


class InformeAjenoIgualQueInexistenteTests(BaseRevision):
    def test_informe_de_relevamiento(self):
        inspeccion = self._completada()
        intruso = self._usuario("otra_institucion", ("dispositivo.ver",), [self.cis])
        cliente = Client()
        cliente.force_login(intruso)

        ajeno = cliente.get(reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk]))
        inexistente = cliente.get(reverse("dispositivos:relevamiento_informe", args=[INEXISTENTE]))

        self.assertEqual((ajeno.status_code, inexistente.status_code), (404, 404))
        self.assertEqual(_sin_token(ajeno.content), _sin_token(inexistente.content))
