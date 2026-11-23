"""Baja lógica de una plaza (Cambio 479): sale del mapa y del total, conserva su historia y se reactiva.

`Plaza.objects` esconde las dadas de baja; `Plaza.todas` las ve. Lo que se prueba acá es que eso
alcance para que ninguna pantalla ni servicio las vuelva a ofrecer, y que lo que sí necesita
verlas —el código, que no se reusa; la reactivación; la historia— las siga viendo.
"""

from datetime import timedelta

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import RequestFactory, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import Estadia, Plaza, ReservaPlaza, Sector, TrazaDispositivo
from programas.selectors.capacidad_dispositivo import TOPE_BAJAS_POR_GRUPO, plazas_dadas_de_baja, sectores_inactivos
from programas.services.estadias import egresar_persona, ingresar_persona, reservar_plaza
from programas.services.ocupacion import ocupacion_de_plazas
from programas.services.plazas import (
    agregar_plazas,
    dar_de_baja_plaza,
    editar_plaza,
    editar_sector,
    reactivar_plaza,
)
from programas.services.sectores_plazas import url_solapa_sectores
from programas.tests.test_dispositivos_capacidad import BaseCapacidad


class BaseBajaDePlaza(BaseCapacidad):
    def _total(self):
        return ocupacion_de_plazas(self.cis).de(self.cis).conteo.totales

    def _baja(self, plaza=None):
        return dar_de_baja_plaza(plaza=plaza or self.otra_plaza, usuario=self.operador_cis)

    def _url(self, nombre, plaza=None):
        return reverse(f"dispositivos:{nombre}", args=[self.cis.pk, (plaza or self.otra_plaza).pk])


class DarDeBajaPlazaTests(BaseBajaDePlaza):
    def test_la_plaza_sale_del_total_y_del_mapa_sin_borrarse(self):
        self.assertEqual(self._total(), 2)

        plaza = self._baja()

        self.assertFalse(plaza.activa)
        self.assertEqual(self._total(), 1)
        self.assertFalse(Plaza.objects.filter(pk=plaza.pk).exists())
        self.assertTrue(Plaza.todas.filter(pk=plaza.pk, activa=False).exists())
        self.assertIn(plaza.codigo, TrazaDispositivo.objects.get(dispositivo=self.cis, accion="PLAZA_BAJA").detalle)

        self.client.force_login(self.operador_cis)
        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))
        codigos = [celda["codigo"] for item in respuesta.context["sectores"] for celda in item["plazas"]]
        self.assertEqual(codigos, [self.plaza.codigo])
        self.assertNotIn(plaza.pk, respuesta.context["plazas_modal"])

    def test_una_plaza_ocupada_no_se_da_de_baja(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.otra_plaza)

        with self.assertRaises(ValidationError) as fallo:
            self._baja()

        self.assertIn("estadía activa", fallo.exception.message_dict["__all__"][0])
        self.assertTrue(Plaza.objects.get(pk=self.otra_plaza.pk).activa)

    def test_una_reserva_vencida_sin_liberar_tambien_la_bloquea(self):
        ahora = timezone.now()
        reserva = reservar_plaza(
            plaza=self.otra_plaza,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            desde=ahora,
            hasta=ahora + timedelta(hours=12),
        )
        ReservaPlaza.objects.filter(pk=reserva.pk).update(
            desde=ahora - timedelta(days=2), hasta=ahora - timedelta(days=1)
        )

        with self.assertRaises(ValidationError) as fallo:
            self._baja()

        self.assertIn("sin liberar", fallo.exception.message_dict["__all__"][0])

    def test_con_historia_cerrada_se_da_de_baja_y_la_estadia_la_sigue_viendo(self):
        estadia = ingresar_persona(
            ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.otra_plaza
        )
        egresar_persona(estadia=estadia, usuario=self.operador_cis, destino="Domicilio", motivo_egreso=self.motivo_alta)

        self._baja()

        self.assertEqual(Estadia.objects.get(pk=estadia.pk).plaza.codigo, self.otra_plaza.codigo)

    def test_no_se_puede_alojar_en_una_plaza_dada_de_baja(self):
        self._baja()

        with self.assertRaises(ValidationError):
            ingresar_persona(
                ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.otra_plaza
            )

    def test_sin_la_capacidad_no_se_da_de_baja(self):
        with self.assertRaises(PermissionDenied):
            dar_de_baja_plaza(plaza=self.otra_plaza, usuario=self.sin_editar)

    def test_el_codigo_de_la_baja_no_se_reusa_ni_choca(self):
        self._baja()

        nuevas = agregar_plazas(sector=self.sector, usuario=self.operador_cis, cantidad=1, prefijo="P")
        self.assertEqual([plaza.codigo for plaza in nuevas], ["P03"])

        with self.assertRaises(ValidationError) as fallo:
            editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo=self.otra_plaza.codigo, tipo="CAMA")
        self.assertIn("dada de baja", fallo.exception.message_dict["codigo"][0])

    def test_un_sector_inactivo_no_cuenta_sus_plazas_dadas_de_baja(self):
        self._baja()
        editar_sector(
            sector=self.sector,
            usuario=self.operador_cis,
            nombre=self.sector.nombre,
            tipo=self.sector.tipo,
            capacidad=self.sector.capacidad,
            activo=False,
        )

        self.assertEqual(sectores_inactivos(self.cis).get().cantidad_plazas, 1)

    def test_el_admin_de_consulta_muestra_las_dadas_de_baja(self):
        self._baja()
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(username="soporte", password="x")

        self.assertIn(
            self.otra_plaza.pk, admin.site._registry[Plaza].get_queryset(request).values_list("pk", flat=True)
        )


class ReactivarPlazaTests(BaseBajaDePlaza):
    def test_reactivar_la_devuelve_al_total_y_deja_la_traza(self):
        self._baja()

        plaza = reactivar_plaza(plaza=Plaza.todas.get(pk=self.otra_plaza.pk), usuario=self.operador_cis)

        self.assertTrue(plaza.activa)
        self.assertEqual(self._total(), 2)
        self.assertTrue(TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="PLAZA_REACTIVADA").exists())

    def test_no_se_reactiva_en_un_sector_inactivo(self):
        self._baja()
        Sector.objects.filter(pk=self.sector.pk).update(activo=False)

        with self.assertRaises(ValidationError):
            reactivar_plaza(plaza=Plaza.todas.get(pk=self.otra_plaza.pk), usuario=self.operador_cis)

    def test_una_plaza_activa_no_se_reactiva(self):
        with self.assertRaises(ValidationError):
            reactivar_plaza(plaza=self.otra_plaza, usuario=self.operador_cis)


class VistasDeBajaDePlazaTests(BaseBajaDePlaza):
    def test_la_baja_desde_el_modal_redirige_al_mapa(self):
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(self._url("plaza_baja"))

        self.assertRedirects(respuesta, url_solapa_sectores(self.cis.pk))
        self.assertFalse(Plaza.todas.get(pk=self.otra_plaza.pk).activa)

    def test_la_plaza_tomada_vuelve_con_el_motivo(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.otra_plaza)
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(self._url("plaza_baja"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")

        self.assertEqual(respuesta.status_code, 400)
        self.assertTrue(Plaza.objects.get(pk=self.otra_plaza.pk).activa)

    def test_sin_la_capacidad_responde_403(self):
        self.client.force_login(self.sin_editar)

        self.assertEqual(self.client.post(self._url("plaza_baja")).status_code, 403)
        self.assertTrue(Plaza.objects.get(pk=self.otra_plaza.pk).activa)

    def test_la_plaza_ajena_o_inexistente_da_404(self):
        self.client.force_login(self.operador_cis)

        ajena = self.client.post(self._url("plaza_baja", self.plaza_parador))
        inexistente = self.client.post(reverse("dispositivos:plaza_baja", args=[self.cis.pk, 99999]))

        self.assertEqual(ajena.status_code, 404)
        self.assertEqual(inexistente.status_code, 404)

    def test_otra_institucion_da_404(self):
        self.client.force_login(self.operador_parador)

        self.assertEqual(self.client.post(self._url("plaza_baja")).status_code, 404)

    def test_solo_post(self):
        self.client.force_login(self.operador_cis)

        self.assertEqual(self.client.get(self._url("plaza_baja")).status_code, 405)
        self.assertEqual(self.client.get(self._url("plaza_reactivar")).status_code, 405)

    def test_el_filtro_de_inactivos_lista_la_baja_y_la_reactiva(self):
        self._baja()
        self.client.force_login(self.operador_cis)
        mapa = reverse("dispositivos:sectores", args=[self.cis.pk])

        sin_filtro = self.client.get(mapa)
        con_filtro = self.client.get(mapa, {"inactivos": "1"})

        self.assertNotIn("plazas_dadas_de_baja", sin_filtro.context)
        grupos = con_filtro.context["plazas_dadas_de_baja"].grupos
        self.assertEqual([[p.pk for p in grupo.visibles] for grupo in grupos], [[self.otra_plaza.pk]])
        self.assertContains(con_filtro, self._url("plaza_reactivar"))

        respuesta = self.client.post(self._url("plaza_reactivar"))

        self.assertRedirects(respuesta, url_solapa_sectores(self.cis.pk))
        self.assertTrue(Plaza.objects.filter(pk=self.otra_plaza.pk).exists())

    def test_reactivar_una_plaza_activa_da_404(self):
        self.client.force_login(self.operador_cis)

        self.assertEqual(self.client.post(self._url("plaza_reactivar")).status_code, 404)

    def test_el_modal_trae_la_url_y_el_bloqueo_de_la_baja(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))

        modal = respuesta.context["plazas_modal"]
        self.assertIn("estadía activa", modal[self.plaza.pk]["bloqueo_baja"])
        self.assertEqual(modal[self.otra_plaza.pk]["bloqueo_baja"], "")
        self.assertIn("/plazas/__pk__/baja/", respuesta.context["urls_plaza"]["baja"])
        self.assertContains(respuesta, "Dar de baja")

    def test_sin_configurar_plazas_no_se_ofrece_la_baja(self):
        self.client.force_login(self.sin_editar)

        respuesta = self.client.get(reverse("dispositivos:sectores", args=[self.cis.pk]))

        self.assertNotContains(respuesta, "Sí, dar de baja")


class BajasAgrupadasPorSectorTests(BaseBajaDePlaza):
    """«Plazas dadas de baja» agrupadas por sector (Cambio 582): lo agrupa el selector, no el template."""

    ABIERTO = '<details class="border-t border-light" open>'

    def setUp(self):
        super().setUp()
        self.sector_b = Sector.objects.create(dispositivo=self.cis, nombre="Pabellón B", capacidad=4)
        self.sector_c = Sector.objects.create(dispositivo=self.cis, nombre="Anexo", capacidad=4)
        self.mapa = reverse("dispositivos:sectores", args=[self.cis.pk])

    def _bajas(self, sector, cantidad, prefijo):
        return [
            Plaza.objects.create(sector=sector, codigo=f"{prefijo}-{n:02d}", activa=False)
            for n in range(1, cantidad + 1)
        ]

    def _cargar(self):
        """El sector del terreno con 25 bajas, B con 3 y el Anexo sin ninguna."""

        self._bajas(self.sector, 25, "A")
        self._bajas(self.sector_b, 3, "B")

    def test_agrupa_por_sector_con_su_cantidad_y_el_total_general(self):
        self._cargar()

        bajas = plazas_dadas_de_baja(self.cis)

        self.assertEqual((bajas.total, bajas.cantidad_sectores), (28, 2))
        self.assertEqual(
            [(g.sector.nombre, g.cantidad) for g in bajas.grupos], [("Pabellón B", 3), (self.sector.nombre, 25)]
        )
        self.assertEqual([nombre for _pk, nombre in bajas.opciones], ["Pabellón B", self.sector.nombre])

    def test_cada_grupo_muestra_las_primeras_veinte_y_deja_el_resto_plegado(self):
        self._cargar()

        grande = plazas_dadas_de_baja(self.cis).grupos[1]

        self.assertEqual(TOPE_BAJAS_POR_GRUPO, 20)
        self.assertEqual(len(grande.visibles), 20)
        self.assertEqual(len(grande.restantes), 5)
        # Orden natural, sin perder ninguna: las visibles y las restantes son las 25.
        self.assertEqual([p.codigo for p in grande.visibles + grande.restantes], [f"A-{n:02d}" for n in range(1, 26)])

    def test_un_grupo_de_exactamente_veinte_no_ofrece_ver_restantes(self):
        self._bajas(self.sector_b, 20, "B")

        self.assertEqual(plazas_dadas_de_baja(self.cis).grupos[0].restantes, [])

    def test_los_grupos_llegan_cerrados_salvo_el_pedido(self):
        self._cargar()

        self.assertEqual([g.abierto for g in plazas_dadas_de_baja(self.cis).grupos], [False, False])
        self.assertEqual(
            [g.abierto for g in plazas_dadas_de_baja(self.cis, abierto_id=self.sector_b.pk).grupos], [True, False]
        )

    def test_el_filtro_deja_solo_ese_grupo_abierto_y_conserva_las_opciones(self):
        self._cargar()

        bajas = plazas_dadas_de_baja(self.cis, sector_id=self.sector_b.pk)

        self.assertEqual(bajas.filtro, self.sector_b.pk)
        self.assertEqual([(g.sector, g.abierto) for g in bajas.grupos], [(self.sector_b, True)])
        self.assertEqual((bajas.total, len(bajas.opciones)), (28, 2))

    def test_un_filtro_ajeno_inexistente_o_sin_bajas_se_ignora(self):
        self._cargar()
        for pedido in (self.plaza_parador.sector_id, 999999, self.sector_c.pk, None):
            with self.subTest(pedido=pedido):
                bajas = plazas_dadas_de_baja(self.cis, sector_id=pedido)

                self.assertIsNone(bajas.filtro)
                self.assertEqual(len(bajas.grupos), 2)

    def test_el_sector_inactivo_y_el_de_otra_institucion_no_aparecen(self):
        self._cargar()
        self._bajas(self.sector_c, 2, "X")
        Sector.objects.filter(pk=self.sector_c.pk).update(activo=False)
        self._bajas(self.plaza_parador.sector, 2, "Z")

        bajas = plazas_dadas_de_baja(self.cis)

        self.assertEqual(bajas.total, 28)
        self.assertNotIn(self.sector_c.pk, [pk for pk, _nombre in bajas.opciones])

    def test_es_una_consulta_y_no_crece_con_los_sectores_ni_las_plazas(self):
        self._cargar()
        with CaptureQueriesContext(connection) as pocas:
            plazas_dadas_de_baja(self.cis)
        for n in range(6):
            self._bajas(Sector.objects.create(dispositivo=self.cis, nombre=f"Extra {n}", capacidad=2), 30, f"E{n}")
        with CaptureQueriesContext(connection) as muchas:
            plazas_dadas_de_baja(self.cis, sector_id=self.sector_b.pk)

        self.assertEqual((len(pocas), len(muchas)), (1, 1))

    @tag("performance")
    def test_la_pantalla_con_inactivos_cuesta_lo_mismo_con_dos_sectores_que_con_ocho(self):
        self._cargar()
        self.client.force_login(self.operador_cis)
        self.client.get(self.mapa, {"inactivos": "1"})  # calienta sesión y cachés
        with CaptureQueriesContext(connection) as antes:
            self.client.get(self.mapa, {"inactivos": "1"})
        for n in range(6):
            self._bajas(Sector.objects.create(dispositivo=self.cis, nombre=f"Extra {n}", capacidad=2), 25, f"E{n}")
        with CaptureQueriesContext(connection) as despues:
            self.client.get(self.mapa, {"inactivos": "1"})

        # Los sectores nuevos suman consultas del mapa solo si crece algo por sector: no debe.
        self.assertEqual(len(antes), len(despues))

    def test_la_pantalla_dice_el_total_agrupa_y_ofrece_ver_las_restantes(self):
        self._cargar()
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(self.mapa, {"inactivos": "1"})

        self.assertContains(respuesta, "28 plazas dadas de baja en 2 sectores")
        self.assertContains(respuesta, f"{self.sector.nombre} · 25 plazas dadas de baja")
        self.assertContains(respuesta, "Pabellón B · 3 plazas dadas de baja")
        self.assertContains(respuesta, "Ver las 5 restantes")
        self.assertNotContains(respuesta, self.ABIERTO)
        # El select conserva «Ver inactivos» y su valor llega a la vista.
        self.assertContains(respuesta, '<input type="hidden" name="inactivos" value="1">')
        self.assertContains(respuesta, 'name="baja_sector"')

    def test_la_pantalla_con_el_filtro_deja_un_solo_grupo_abierto(self):
        self._cargar()
        self.client.force_login(self.operador_cis)

        respuesta = self.client.get(self.mapa, {"inactivos": "1", "baja_sector": self.sector_b.pk})

        self.assertContains(respuesta, self.ABIERTO, count=1)
        self.assertContains(respuesta, "Pabellón B · 3 plazas dadas de baja")
        self.assertNotContains(respuesta, f"{self.sector.nombre} · 25 plazas dadas de baja")
        self.assertContains(respuesta, f'<option value="{self.sector_b.pk}" selected>')
        # Un filtro ajeno se ignora: vuelven los dos grupos, cerrados.
        ajeno = self.client.get(self.mapa, {"inactivos": "1", "baja_sector": self.plaza_parador.sector_id})
        self.assertContains(ajeno, "Pabellón B · 3 plazas dadas de baja")
        self.assertContains(ajeno, f"{self.sector.nombre} · 25 plazas dadas de baja")
        self.assertNotContains(ajeno, self.ABIERTO)

    def test_reactivar_vuelve_con_el_mismo_filtro_y_el_grupo_abierto(self):
        self._cargar()
        plaza = Plaza.todas.get(sector=self.sector_b, codigo="B-01")
        self.client.force_login(self.operador_cis)
        pantalla = self.client.get(self.mapa, {"inactivos": "1", "baja_sector": self.sector_b.pk})
        url = self._url("plaza_reactivar", plaza)
        # El botón lleva a dónde vuelve: el filtro y el grupo de la plaza.
        self.assertContains(
            pantalla, f'data-confirm-url="{url}?baja_sector={self.sector_b.pk}&amp;baja_abierto={self.sector_b.pk}"'
        )

        respuesta = self.client.post(f"{url}?baja_sector={self.sector_b.pk}&baja_abierto={self.sector_b.pk}")

        destino = f"{self.mapa}?inactivos=1&baja_sector={self.sector_b.pk}&baja_abierto={self.sector_b.pk}"
        self.assertRedirects(respuesta, destino, fetch_redirect_response=False)
        vuelta = self.client.get(destino)
        self.assertContains(vuelta, "Pabellón B · 2 plazas dadas de baja")
        self.assertContains(vuelta, self.ABIERTO, count=1)

    def test_reactivar_sin_filtro_abre_el_grupo_de_la_plaza(self):
        self._cargar()
        plaza = Plaza.todas.get(sector=self.sector_b, codigo="B-01")
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(f"{self._url('plaza_reactivar', plaza)}?baja_abierto={self.sector_b.pk}")

        destino = f"{self.mapa}?inactivos=1&baja_abierto={self.sector_b.pk}"
        self.assertRedirects(respuesta, destino, fetch_redirect_response=False)
        grupos = self.client.get(destino).context["plazas_dadas_de_baja"].grupos
        self.assertEqual([g.abierto for g in grupos], [True, False])

    def test_un_id_de_miles_de_digitos_se_ignora_y_no_da_500(self):
        """``int()`` de más de 4300 dígitos levanta ``ValueError``: con una URL armada a mano era un 500."""

        self._baja()
        self.client.force_login(self.operador_cis)
        enorme = "9" * 5000

        pantalla = self.client.get(self.mapa, {"inactivos": "1", "baja_sector": enorme, "baja_abierto": enorme})
        respuesta = self.client.post(f"{self._url('plaza_reactivar')}?baja_sector={enorme}&baja_abierto={enorme}")

        self.assertEqual(pantalla.status_code, 200)
        self.assertRedirects(respuesta, url_solapa_sectores(self.cis.pk), fetch_redirect_response=False)

    def test_un_parametro_de_vuelta_que_no_es_un_numero_no_llega_a_la_url(self):
        self._baja()
        self.client.force_login(self.operador_cis)

        respuesta = self.client.post(f"{self._url('plaza_reactivar')}?baja_sector=x&baja_abierto=https://otro.example")

        self.assertRedirects(respuesta, url_solapa_sectores(self.cis.pk), fetch_redirect_response=False)
