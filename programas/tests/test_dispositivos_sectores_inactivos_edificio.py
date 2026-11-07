"""Sectores inactivos sin edificio y el edificio en el mapa (Cambio 435, dos pedidos de QA).

A: cada inactivo del listado ofrece «Editar» (el mismo modal «Editar sector»), y desde ahí se
elige un edificio y se activa en el mismo guardado. B: el encabezado de cada sector del mapa y
cada fila de inactivos dicen el edificio («Sin edificio» si no tiene), sin una consulta por sector.
"""

from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import Sector
from programas.services.plazas import crear_sector, editar_sector, reactivar_sector
from programas.tests.test_dispositivos_sector_edificio import BaseSectorEdificio

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class _Base(BaseSectorEdificio):
    def _url_mapa(self):
        return reverse("dispositivos:sectores", args=[self.cis.pk])

    def _url_editar(self, sector):
        return reverse("dispositivos:sector_editar", args=[self.cis.pk, sector.pk])

    def _post_editar(self, sector, **extra):
        datos = {"nombre": sector.nombre, "tipo": sector.tipo, "capacidad": 0, **extra}
        return self.client.post(self._url_editar(sector), datos, **AJAX)


class EditarDesdeInactivosTests(_Base):
    def test_cada_inactivo_ofrece_editar_y_abre_el_modal_con_su_edificio(self):
        sector = self._sector(None, nombre="Sin edificio", activo=False)
        self.client.force_login(self.operador_cis)

        listado = self.client.get(self._url_mapa(), {"inactivos": "1"})
        modal = self.client.get(self._url_mapa(), {"inactivos": "1", "sector": sector.pk})

        self.assertContains(listado, f"?inactivos=1&amp;sector={sector.pk}")
        self.assertContains(modal, "Editar sector")
        self.assertContains(modal, "Este sector está dado de baja")
        self.assertEqual(
            set(modal.context["form_sector"].fields["edificio"].queryset), {self.edificio_a, self.edificio_b}
        )

    def test_elegir_edificio_y_activar_en_el_mismo_guardado_lo_devuelve_al_mapa(self):
        sector = self._sector(None, nombre="Vuelve", activo=False)
        plaza = sector.plazas.create(codigo="V-01")
        self.client.force_login(self.operador_cis)

        respuesta = self._post_editar(sector, edificio=self.edificio_b.pk, activo="on")

        self.assertEqual(respuesta.status_code, 200)
        sector.refresh_from_db()
        self.assertTrue(sector.activo)
        self.assertEqual(sector.edificio, self.edificio_b)
        mapa = self.client.get(self._url_mapa())
        self.assertIn(sector.pk, [i["sector"].pk for i in mapa.context["sectores"]])
        self.assertContains(mapa, "Vuelve · Predio B")
        self.assertTrue(sector.plazas.filter(pk=plaza.pk).exists())

    def test_activar_sin_elegir_edificio_se_rechaza_y_sigue_inactivo(self):
        sector = self._sector(None, nombre="Sigue", activo=False)
        self.client.force_login(self.operador_cis)

        respuesta = self._post_editar(sector, activo="on")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("edificio", respuesta.json()["errors"])
        self.assertFalse(Sector.objects.get(pk=sector.pk).activo)

    def test_un_edificio_desvinculado_cuenta_como_sin_edificio(self):
        sector = self._sector(self.edificio_a, nombre="Desvinculado", activo=False)
        self.edificio_a.dispositivos.remove(self.cis)
        self.client.force_login(self.operador_cis)

        # Ni con el campo vacío ni con el edificio desvinculado se activa.
        vacio = self._post_editar(sector, activo="on")
        viejo = self._post_editar(sector, edificio=self.edificio_a.pk, activo="on")
        listado = self.client.get(self._url_mapa(), {"inactivos": "1"})

        self.assertEqual(vacio.status_code, 400)
        self.assertEqual(viejo.status_code, 400)
        self.assertFalse(Sector.objects.get(pk=sector.pk).activo)
        self.assertContains(listado, "Sin edificio")
        self.assertNotContains(listado, "Predio A")
        # Y con uno vinculado, sí.
        self.assertEqual(self._post_editar(sector, edificio=self.edificio_b.pk, activo="on").status_code, 200)
        self.assertTrue(Sector.objects.get(pk=sector.pk).activo)

    def test_sin_edificios_vinculados_el_modal_dice_donde_vincularlo(self):
        self.edificio_a.dispositivos.remove(self.cis)
        self.edificio_b.dispositivos.remove(self.cis)
        sector = self._sector(None, nombre="Huérfano", activo=False)
        self.client.force_login(self.operador_cis)

        pagina = self.client.get(self._url_mapa(), {"inactivos": "1", "sector": sector.pk})

        self.assertContains(pagina, "Vinculá un edificio al dispositivo desde la solapa Infraestructura")

    def test_nombre_duplicado_al_activar_da_el_mismo_mensaje_que_reactivar(self):
        inactivo = self._sector(self.edificio_a, nombre="Repetido", activo=False)
        self._sector(self.edificio_a, nombre="Repetido")

        with self.assertRaises(ValidationError) as por_reactivar:
            reactivar_sector(sector=inactivo, usuario=self.operador_cis)
        with self.assertRaises(ValidationError) as por_editar:
            editar_sector(
                sector=inactivo,
                usuario=self.operador_cis,
                nombre="Repetido",
                tipo=inactivo.tipo,
                edificio=self.edificio_a,
                activo=True,
            )

        self.assertEqual(por_editar.exception.message_dict, por_reactivar.exception.message_dict)
        self.assertIn("ya hay un sector activo llamado", por_editar.exception.message_dict["nombre"][0])
        self.assertFalse(Sector.objects.get(pk=inactivo.pk).activo)

    def test_la_pantalla_bloquea_el_nombre_duplicado_al_activar_desde_editar(self):
        inactivo = self._sector(self.edificio_a, nombre="Repetido", activo=False)
        self._sector(self.edificio_a, nombre="Repetido")
        self.client.force_login(self.operador_cis)

        respuesta = self._post_editar(inactivo, edificio=self.edificio_a.pk, activo="on")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("No se puede reactivar", respuesta.json()["errors"]["nombre"][0])
        self.assertFalse(Sector.objects.get(pk=inactivo.pk).activo)

    def test_sin_permiso_de_edicion_no_hay_boton_ni_endpoint(self):
        sector = self._sector(None, nombre="Protegido", activo=False)
        self.client.force_login(self.sin_editar)

        pagina = self.client.get(self._url_mapa(), {"inactivos": "1"})
        post = self._post_editar(sector, edificio=self.edificio_a.pk, activo="on")

        self.assertNotContains(pagina, f"?inactivos=1&amp;sector={sector.pk}")
        self.assertEqual(post.status_code, 403)
        self.client.force_login(self.operador_parador)
        self.assertEqual(self._post_editar(sector, edificio=self.edificio_a.pk, activo="on").status_code, 404)
        self.assertFalse(Sector.objects.get(pk=sector.pk).activo)

    def test_el_alta_con_nombre_repetido_conserva_su_mensaje(self):
        self._sector(self.edificio_a, nombre="Dup")

        with self.assertRaises(ValidationError) as fallo:
            crear_sector(dispositivo=self.cis, usuario=self.operador_cis, **self._datos(nombre="Dup"))

        self.assertIn("Ya hay un sector activo con ese nombre", fallo.exception.message_dict["nombre"][0])


class EdificioEnElMapaTests(_Base):
    def test_el_encabezado_del_sector_y_la_fila_del_inactivo_dicen_el_edificio(self):
        self._sector(self.edificio_a, nombre="Pabellón 9")
        self._sector(None, nombre="Viejo")
        self._sector(self.edificio_b, nombre="Baja", activo=False)
        self._sector(None, nombre="Baja sin", activo=False)
        self.client.force_login(self.operador_cis)

        pagina = self.client.get(self._url_mapa(), {"inactivos": "1"})

        self.assertContains(pagina, "Pabellón 9 · Predio A")
        self.assertContains(pagina, "Viejo · Sin edificio")
        self.assertContains(pagina, "Predio B")
        self.assertContains(pagina, "Sin edificio · 0 plazas")

    def test_quien_solo_ve_el_mapa_tambien_lo_ve(self):
        self._sector(self.edificio_a, nombre="Pabellón 9")
        self.client.force_login(self.sin_editar)

        self.assertContains(self.client.get(self._url_mapa()), "Pabellón 9 · Predio A")

    def test_cambiar_el_edificio_desde_editar_lo_refleja_el_mapa(self):
        sector = self._sector(self.edificio_a, nombre="Pabellón 9")
        self.client.force_login(self.operador_cis)

        self._post_editar(sector, edificio=self.edificio_b.pk, activo="on")

        self.assertContains(self.client.get(self._url_mapa()), "Pabellón 9 · Predio B")

    def test_las_consultas_no_crecen_con_la_cantidad_de_sectores(self):
        self._sector(self.edificio_a, nombre="S0")
        self.client.force_login(self.operador_cis)
        url = self._url_mapa()
        self.client.get(url, {"inactivos": "1"})

        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                self.client.get(url, {"inactivos": "1"})
            return len(capturadas)

        antes = consultas()
        for n in range(1, 4):
            self._sector(self.edificio_b, nombre=f"S{n}")
            self._sector(self.edificio_b, nombre=f"I{n}", activo=False)

        self.assertEqual(consultas(), antes)
