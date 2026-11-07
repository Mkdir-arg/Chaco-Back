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

    def test_el_post_ajax_ajeno_responde_json_igual_que_el_inexistente(self):
        intruso = self._usuario("Operador parador", self.parador)
        self.client.force_login(intruso)
        respuestas = [
            self.client.post(
                reverse("dispositivos:bitacora_novedad", args=[pk]),
                {"tipo": "GENERAL", "texto": "X."},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            for pk in (self.cis.pk, INEXISTENTE)
        ]

        for respuesta in respuestas:
            self.assertEqual(respuesta.status_code, 404)
            self.assertEqual(
                respuesta.json(), {"ok": False, "message": "No encontramos ese dispositivo o ya no tenés acceso."}
            )

    def test_ingreso_sin_la_capacidad_es_403_con_cualquier_id_y_sin_alcance_es_404(self):
        sin_admitir = self._usuario("Sin admitir", self.cis, _sin("dispositivo.admitir"))
        intruso = self._usuario("Operador parador", self.parador)

        self.client.force_login(sin_admitir)
        for pk in (self.cis.pk, INEXISTENTE):
            self.assertEqual(self.client.get(reverse("dispositivos:ingreso_persona", args=[pk])).status_code, 403)
        self.client.force_login(intruso)
        for pk in (self.cis.pk, INEXISTENTE):
            self.assertEqual(self.client.get(reverse("dispositivos:ingreso_persona", args=[pk])).status_code, 404)

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

    def test_crear_relevamiento_desde_un_dispositivo_ajeno_es_404_igual_que_inexistente(self):
        intruso = self._usuario("otra_institucion", ("dispositivo.ver", "inspeccion.asignar"), [self.cis])
        cliente = Client()
        cliente.force_login(intruso)

        ajeno = cliente.post(reverse("dispositivos:relevamiento_asignar_dispositivo", args=[self.parador.pk]), {})
        inexistente = cliente.post(reverse("dispositivos:relevamiento_asignar_dispositivo", args=[INEXISTENTE]), {})

        self.assertEqual((ajeno.status_code, inexistente.status_code), (404, 404))
        self.assertEqual(_sin_token(ajeno.content), _sin_token(inexistente.content))
