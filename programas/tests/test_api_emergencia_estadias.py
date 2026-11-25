"""Cambio 597: egreso por persona y cambio de plaza de una estadía, desde la app.

La guardia opera con las mismas reglas que la web (``estadias.egresar_persona`` y ``cambiar_plaza``) y el mismo
alcance: estadía ajena o inexistente = 404; ver sin la capacidad de la acción = 403.
"""

from datetime import timedelta
from unittest import mock

from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Edificio, Estadia, MotivoEgreso, Plaza
from programas.tests.base_emergencia_api import BaseApiEmergencia, _url
from programas.tests.test_emergencia_alojar_base import GUARDIA

PLAZAS_PARA_CAMBIO = "estadia-plazas-para-cambio"


class BaseEstadias(BaseApiEmergencia):
    def setUp(self):
        super().setUp()
        edificio = Edificio.objects.create(codigo="EDI-C", nombre="Edificio del club")
        edificio.dispositivos.add(self.club)
        self.club.sectores.update(edificio=edificio)
        self.operador_sala = self._guardia("operador_sala", list(GUARDIA), [self.club])
        self.solo_admite = self._guardia("solo_admite", ["dispositivo.ver", "dispositivo.admitir"], [self.club])
        self.motivo = MotivoEgreso.objects.create(codigo="alta-e", nombre="Alta voluntaria")
        self.motivo_baja = MotivoEgreso.objects.create(codigo="viejo-e", nombre="Viejo", activo=False)

    def _alojar(self, dispositivo=None, codigo="C001"):
        dispositivo = dispositivo or self.club
        persona = Ciudadano.objects.create(dni=str(next(self._dnis)), nombre="Ana", apellido="Gómez")
        plaza = Plaza.objects.get(sector__dispositivo=dispositivo, codigo=codigo)
        return Estadia.objects.create(
            ciudadano=persona,
            dispositivo=dispositivo,
            plaza=plaza,
            fecha_ingreso=timezone.now() - timedelta(days=1),
            clave_alojamiento=Estadia.clave_para(persona),
        )

    @staticmethod
    def _plazas_del_mapa(mapa):
        assert mapa is not None and mapa["sectores"], mapa
        return {plaza["codigo"]: plaza for sector in mapa["sectores"] for plaza in sector["plazas"]}

    def _cuerpo_egreso(self, **cambios):
        cuerpo = {"motivo_egreso_id": self.motivo.pk, "destino": "Domicilio de un familiar"}
        cuerpo.update(cambios)
        return cuerpo

    def _egresar(self, estadia, usuario=None, **cambios):
        return self._como(usuario or self.operador_sala).post(
            _url("estadia-egresar", estadia.pk), self._cuerpo_egreso(**cambios), format="json"
        )


class MotivosEgresoTests(BaseEstadias):
    def test_lista_solo_los_activos(self):
        respuesta = self._como(self.operador_sala).get(_url("motivos-egreso"))
        self.assertEqual(respuesta.status_code, 200)
        ids = [m["id"] for m in respuesta.json()]
        self.assertIn(self.motivo.pk, ids)
        self.assertNotIn(self.motivo_baja.pk, ids)
        self.assertEqual(sorted(respuesta.json()[0]), ["id", "nombre"])


class EgresarTests(BaseEstadias):
    def test_egreso_feliz(self):
        estadia = self._alojar()
        respuesta = self._egresar(estadia, pertenencias_devueltas=True, observaciones="Sin novedades")
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertEqual(self._plazas_del_mapa(cuerpo["mapa"])["C001"]["estado"], "disponible")
        estadia.refresh_from_db()
        self.assertEqual(estadia.estado, Estadia.Estado.EGRESADA)
        self.assertEqual(estadia.motivo, self.motivo)
        self.assertEqual(estadia.destino_egreso, "Domicilio de un familiar")
        self.assertTrue(estadia.pertenencias_devueltas)
        self.assertEqual(estadia.egresada_por, self.operador_sala)

    def test_el_motivo_es_obligatorio(self):
        estadia = self._alojar()
        respuesta = self._egresar(estadia, motivo_egreso_id=None)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json())
        estadia.refresh_from_db()
        self.assertTrue(estadia.activa)

    def test_un_motivo_dado_de_baja_se_rechaza(self):
        estadia = self._alojar()
        respuesta = self._egresar(estadia, motivo_egreso_id=self.motivo_baja.pk)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json())

    def test_el_destino_es_obligatorio(self):
        estadia = self._alojar()
        respuesta = self._egresar(estadia, destino="  ")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("destino", respuesta.json())
        estadia.refresh_from_db()
        self.assertTrue(estadia.activa)

    def test_doble_egreso_es_400(self):
        estadia = self._alojar()
        self.assertEqual(self._egresar(estadia).status_code, 200)
        respuesta = self._egresar(estadia)
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("estado", respuesta.json())

    def test_estadia_de_otro_dispositivo_o_inexistente_es_404(self):
        """Mutación: sin el filtro de alcance de ``_estadia`` este test da 200 y el egreso se escribe."""
        ajeno = self._dispositivo("Escuela 99", camas=2)
        estadia = self._alojar(ajeno)
        respuesta = self._egresar(estadia)
        self.assertEqual(respuesta.status_code, 404)
        inexistente = self._como(self.operador_sala).post(
            _url("estadia-egresar", 999999), self._cuerpo_egreso(), format="json"
        )
        self.assertEqual(inexistente.status_code, 404)
        self.assertEqual(respuesta.json(), inexistente.json())
        estadia.refresh_from_db()
        self.assertTrue(estadia.activa)

    def test_sin_dispositivo_egresar_es_403(self):
        estadia = self._alojar()
        respuesta = self._egresar(estadia, usuario=self.solo_admite)
        self.assertEqual(respuesta.status_code, 403)
        estadia.refresh_from_db()
        self.assertTrue(estadia.activa)

    def test_un_tipo_con_formulario_de_egreso_es_409(self):
        estadia = self._alojar()
        with mock.patch("programas.api.views_emergencia_estadias.formulario_de_egreso", return_value=object()):
            respuesta = self._egresar(estadia)
        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(
            respuesta.json(),
            {"detail": "Este egreso se registra desde el backoffice.", "codigo": "EGRESO_CON_FORMULARIO"},
        )
        estadia.refresh_from_db()
        self.assertTrue(estadia.activa)


class CambiarPlazaTests(BaseEstadias):
    def _cambiar(self, estadia, plaza, usuario=None, **cambios):
        cuerpo = {"plaza_id": plaza.pk, "motivo": "Convivencia"}
        cuerpo.update(cambios)
        return self._como(usuario or self.operador_sala).post(
            _url("estadia-cambiar-plaza", estadia.pk), cuerpo, format="json"
        )

    def test_las_plazas_para_cambio_son_las_libres(self):
        estadia = self._alojar(codigo="C001")
        self._alojar(codigo="C002")
        respuesta = self._como(self.operador_sala).get(_url(PLAZAS_PARA_CAMBIO, estadia.pk))
        self.assertEqual(respuesta.status_code, 200)
        sectores = respuesta.json()["sectores"]
        self.assertEqual(sorted(sectores[0]), ["id", "nombre", "plazas"])
        self.assertEqual([p["codigo"] for p in sectores[0]["plazas"]], ["C003", "C004"])
        self.assertEqual(sorted(sectores[0]["plazas"][0]), ["codigo", "id", "tipo"])

    def test_cambio_feliz(self):
        estadia = self._alojar(codigo="C001")
        destino = Plaza.objects.get(sector__dispositivo=self.club, codigo="C003")
        respuesta = self._cambiar(estadia, destino)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        plazas = self._plazas_del_mapa(cuerpo["mapa"])
        self.assertEqual(plazas["C001"]["estado"], "disponible")
        self.assertEqual(plazas["C003"]["estado"], "ocupada")
        estadia.refresh_from_db()
        self.assertEqual(estadia.plaza_id, destino.pk)

    def test_plaza_ocupada_es_400(self):
        estadia = self._alojar(codigo="C001")
        self._alojar(codigo="C002")
        ocupada = Plaza.objects.get(sector__dispositivo=self.club, codigo="C002")
        respuesta = self._cambiar(estadia, ocupada)
        self.assertEqual(respuesta.status_code, 400)
        estadia.refresh_from_db()
        self.assertNotEqual(estadia.plaza_id, ocupada.pk)

    def test_el_motivo_es_obligatorio(self):
        estadia = self._alojar()
        libre = Plaza.objects.get(sector__dispositivo=self.club, codigo="C003")
        respuesta = self._cambiar(estadia, libre, motivo="")
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json())

    def test_una_plaza_de_otro_dispositivo_es_400(self):
        estadia = self._alojar()
        ajena = Plaza.objects.get(sector__dispositivo=self._dispositivo("Escuela 7", camas=1))
        respuesta = self._cambiar(estadia, ajena)
        self.assertEqual(respuesta.status_code, 400)

    def test_estadia_ajena_es_404_y_sin_admitir_es_403(self):
        ajeno = self._dispositivo("Escuela 88", camas=2)
        en_ajeno = self._alojar(ajeno)
        libre = Plaza.objects.filter(sector__dispositivo=ajeno).exclude(pk=en_ajeno.plaza_id).get()
        self.assertEqual(self._cambiar(en_ajeno, libre).status_code, 404)
        self.assertEqual(self._como(self.operador_sala).get(_url(PLAZAS_PARA_CAMBIO, en_ajeno.pk)).status_code, 404)

        propia = self._alojar()
        solo_ve = self._guardia("solo_ve", ["dispositivo.ver"], [self.club])
        destino = Plaza.objects.get(sector__dispositivo=self.club, codigo="C004")
        self.assertEqual(self._cambiar(propia, destino, usuario=solo_ve).status_code, 403)
        self.assertEqual(self._como(solo_ve).get(_url(PLAZAS_PARA_CAMBIO, propia.pk)).status_code, 403)
