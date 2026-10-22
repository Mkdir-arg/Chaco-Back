"""La API de campo aguanta lo que el teléfono de verdad manda (K2, K5 y K8).

Complementa a ``test_becas_api_contrato`` (que fija las claves y los ``code`` de
las respuestas):

* **K2** · un ``capturado_en`` del futuro (reloj del teléfono adelantado) ya no
  es un 400: se guarda ``ahora`` y queda una línea para el revisor. Contradice el
  criterio de G1-04 (``test_app_de_campo``), decidido por el juez por delegación
  del PM el 22-oct-2026.
* **K5** · el GPS se redondea a 6 decimales en vez de rechazarse.
* **K8** · los vectores de condiciones que la app copia a sus tests.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from programas.models import Formulario, Relevamiento
from programas.services import campo
from programas.services.condiciones import OPERADORES_POR_TIPO
from programas.services.respuestas import aplicar
from programas.tests.test_becas_api import _BaseApiTest

VECTORES = Path(__file__).resolve().parent / "fixtures" / "condiciones_vectores.json"


class _AltaBase(_BaseApiTest):
    def setUp(self):
        super().setUp()
        self.autenticar(self.terri)
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.url = reverse("becas_api:relevamiento-formularios", args=[self.rel.pk])

    def _cuerpo(self, **extra):
        cuerpo = {
            "client_uuid": str(uuid4()),
            "celular": "3624111222",
            "datos_identificacion": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez", "origen": "manual"},
            "data": {"globales": {}, "requisitos": {}},
        }
        cuerpo.update(extra)
        return cuerpo


class RelojAdelantadoTests(_AltaBase):
    def test_un_capturado_en_adelantado_se_recorta_a_ahora_y_deja_observacion(self):
        recibido = timezone.now() + timedelta(minutes=47)

        antes = timezone.now()
        resp = self.client.post(self.url, self._cuerpo(capturado_en=recibido.isoformat()), format="json")
        despues = timezone.now()

        self.assertEqual(resp.status_code, 201, resp.content)
        formulario = Formulario.objects.get(pk=resp.json()["id"])
        self.assertTrue(antes <= formulario.capturado_en <= despues)
        observaciones = formulario.observaciones_carga or ""
        self.assertIn("Reloj del teléfono adelantado 46 min", observaciones)
        self.assertIn(f"capturado_en recibido: {timezone.localtime(recibido).isoformat()}", observaciones)
        # La respuesta ya no devuelve el instante inventado por el teléfono.
        self.assertLess(timezone.localtime(formulario.capturado_en), timezone.localtime(recibido))

    def test_la_observacion_sobrevive_a_la_revision_de_la_carga(self):
        """`aplicar_revision` reescribe `observaciones_carga` entero: la línea del
        reloj tiene que estar entre las que arrastra."""
        resp = self.client.post(
            self.url, self._cuerpo(capturado_en=(timezone.now() + timedelta(hours=3)).isoformat()), format="json"
        )
        formulario = Formulario.objects.get(pk=resp.json()["id"])

        campo.aplicar_revision(formulario, campo.revisar_carga(formulario))
        formulario.refresh_from_db()

        self.assertIn(campo.PREFIJO_RELOJ_ADELANTADO, formulario.observaciones_carga or "")

    def test_hasta_cinco_minutos_de_adelanto_se_toleran_sin_observacion(self):
        resp = self.client.post(
            self.url, self._cuerpo(capturado_en=(timezone.now() + timedelta(minutes=3)).isoformat()), format="json"
        )

        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertNotIn("Reloj del teléfono", Formulario.objects.get(pk=resp.json()["id"]).observaciones_carga or "")

    def test_un_capturado_en_adelantado_no_saca_el_alta_del_periodo(self):
        """Recortado a ahora, el período se evalúa con ahora: un relevamiento ya
        cerrado sigue sin aceptar la carga."""
        fin = timezone.now() - timedelta(hours=40)
        Relevamiento.objects.filter(pk=self.rel.pk).update(
            fecha_asignada=fin - timedelta(days=1), fecha_hasta=fin, estado=Relevamiento.Estado.EN_REVISION
        )

        resp = self.client.post(
            self.url, self._cuerpo(capturado_en=(timezone.now() + timedelta(hours=2)).isoformat()), format="json"
        )

        self.assertEqual(resp.status_code, 400, resp.content)
        self.assertEqual(resp.json()["code"], "FUERA_DE_PERIODO")

    def test_iniciar_y_finalizar_aceptan_un_reloj_adelantado(self):
        adelantado = (timezone.now() + timedelta(hours=1)).isoformat()
        Relevamiento.objects.filter(pk=self.rel.pk).update(estado=Relevamiento.Estado.ASIGNADO)

        iniciar = self.client.post(
            reverse("becas_api:relevamiento-iniciar", args=[self.rel.pk]), {"capturado_en": adelantado}
        )
        finalizar = self.client.post(
            reverse("becas_api:relevamiento-finalizar", args=[self.rel.pk]), {"capturado_en": adelantado}
        )

        self.assertEqual(iniciar.status_code, 200, iniciar.content)
        self.assertEqual(finalizar.status_code, 200, finalizar.content)
        self.assertEqual(finalizar.json()["estado"], "FINALIZADO")

    def test_acotar_capturado_en(self):
        ahora = timezone.now()

        self.assertEqual(campo.acotar_capturado_en(None, ahora), (None, None))
        self.assertEqual(
            campo.acotar_capturado_en(ahora + timedelta(minutes=5), ahora), (ahora + timedelta(minutes=5), None)
        )
        valor, adelanto = campo.acotar_capturado_en(ahora + timedelta(minutes=6), ahora)
        self.assertEqual(valor, ahora)
        self.assertEqual(adelanto, timedelta(minutes=6))


class GpsTests(_AltaBase):
    def _alta(self, lat, lng):
        return self.client.post(
            self.url, self._cuerpo(capturado_en=timezone.now().isoformat(), gps_lat=lat, gps_lng=lng), format="json"
        )

    def test_mas_de_seis_decimales_se_redondean_en_vez_de_dar_400(self):
        resp = self._alta(-27.4510004999, "-58.9860005")

        self.assertEqual(resp.status_code, 201, resp.content)
        formulario = Formulario.objects.get(pk=resp.json()["id"])
        self.assertEqual(str(formulario.gps_lat), "-27.451000")
        # ROUND_HALF_UP: el 5 del séptimo decimal sube al sexto.
        self.assertEqual(str(formulario.gps_lng), "-58.986001")
        self.assertEqual(resp.json()["gps_lat"], "-27.451000")

    def test_el_redondeo_es_half_up_y_no_half_even(self):
        resp = self._alta("-27.4510025", "10.0000005")

        self.assertEqual(resp.status_code, 201, resp.content)
        formulario = Formulario.objects.get(pk=resp.json()["id"])
        self.assertEqual(str(formulario.gps_lat), "-27.451003")
        self.assertEqual(str(formulario.gps_lng), "10.000001")

    def test_las_coordenadas_nulas_o_vacias_siguen_entrando(self):
        self.assertEqual(self._alta(None, None).status_code, 201)

    def test_una_coordenada_que_no_es_un_numero_sigue_dando_400(self):
        resp = self._alta("norte", "-58.9")

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDACION")
        self.assertIn("gps_lat", resp.json())

    def test_una_coordenada_fuera_de_rango_sigue_dando_400(self):
        resp = self._alta("12345.5", "-58.9")

        self.assertEqual(resp.status_code, 400)
        self.assertIn("gps_lat", resp.json())


class VectoresDeCondicionesTests(SimpleTestCase):
    """El JSON que la app copia a sus tests tiene que decir lo que dice el motor
    **de hoy**. Si el motor cambia, se regenera con
    ``scripts/generar_vectores_condiciones.py`` y el diff del JSON es la lista de
    lo que la app tiene que replicar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vectores = json.loads(VECTORES.read_text(encoding="utf-8"))

    def test_hay_al_menos_cuarenta_casos_con_la_forma_acordada(self):
        self.assertGreaterEqual(len(self.vectores), 40)
        for caso in self.vectores:
            with self.subTest(caso["nombre"]):
                self.assertEqual(set(caso), {"nombre", "items", "respuestas", "fecha_referencia", "visibles"})
                self.assertIsInstance(caso["items"], list)
                self.assertIsInstance(caso["respuestas"], dict)
                self.assertIsInstance(caso["visibles"], list)
                date.fromisoformat(caso["fecha_referencia"])

    def test_los_visibles_son_los_que_dicta_el_motor_del_back(self):
        for caso in self.vectores:
            with self.subTest(caso["nombre"]):
                visibles, _ocultos, _efectivas = aplicar(
                    {"items": caso["items"]}, caso["respuestas"], hoy=date.fromisoformat(caso["fecha_referencia"])
                )
                self.assertEqual(set(caso["visibles"]), visibles)

    def test_cada_operador_de_cada_tipo_tiene_su_vector(self):
        usados = set()
        for caso in self.vectores:
            for grupo in caso["items"]:
                for hijo in grupo["items"]:
                    for regla in (hijo.get("condicion") or {}).get("reglas") or []:
                        usados.add(regla.get("op"))
        esperados = set().union(*OPERADORES_POR_TIPO.values())
        self.assertEqual(esperados - usados, set(), "operadores sin vector")

    def test_cubre_los_casos_borde_acordados(self):
        nombres = " | ".join(caso["nombre"] for caso in self.vectores)
        for fragmento in (
            "operador desconocido",
            "rango invertido",
            "fuente posterior",
            "condicion null",
            "coma decimal",
            "oculto cuenta como vacío",
            "grupo oculto oculta a sus hijos",
        ):
            with self.subTest(fragmento):
                self.assertIn(fragmento, nombres)
