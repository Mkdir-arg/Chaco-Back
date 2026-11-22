"""Solapa Estadías de la página del edificio (Cambio 566, PR 2 del lote «el edificio como unidad operativa»).

1. Alcance: solo las estadías de **esta** institución en **este** edificio. Una estadía de otro edificio, de otra
   institución del mismo predio o sin plaza no aparece (el contador de la solapa cuenta lo mismo).
2. Acciones: ver, cambiar de plaza y registrar egreso, cada una con su capacidad sobre este edificio; sus modales se abren
   por ``?cambio=`` y ``?egreso=`` y solo para estadías de este edificio.
3. Vuelta: el egreso y el cambio de plaza vuelven a esta solapa por ``next``, validado como el del Equipo.
4. El costo de la solapa no crece con la cantidad de estadías.
"""

import json
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.models import Dispositivo, Estadia, Plaza, Sector
from programas.tests.test_dispositivos_bitacora_pantalla import MARTES, _local
from programas.tests.test_dispositivos_edificio_operativo import BaseOperativo

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo_estadias"
NEXT_AJENO = "https://sitio-ajeno.example/robo/"


class BaseEstadias(BaseOperativo):
    def setUp(self):
        super().setUp()
        self.beto = Ciudadano.objects.create(dni="30555666", nombre="Beto", apellido="Ríos")
        self.carla = Ciudadano.objects.create(dni="30777888", nombre="Carla", apellido="Sosa")
        self.dora = Ciudadano.objects.create(dni="30999000", nombre="Dora", apellido="Vega")
        # Una plaza libre en el edificio B: sin ella el modal de cambio no tiene a dónde mover a nadie.
        self.plaza_libre = Plaza.objects.create(sector=self.sector_b, codigo="B-99")
        # Beto está en el edificio B de la misma institución; Carla, sin plaza.
        self.estadia_beto = self._ingresar(self.beto, self.plaza_b, _local(MARTES, 12))
        self.estadia_carla = Estadia.objects.create(
            dispositivo=self.cis,
            ciudadano=self.carla,
            plaza=None,
            clave_alojamiento=Estadia.clave_para(self.carla),
            estado=Estadia.Estado.ACTIVA,
            fecha_ingreso=timezone.now() - timedelta(days=1),
        )
        # Dora está en otra institución del mismo predio (edificio A).
        self.otra = Dispositivo.objects.create(
            tipo=self.tipo, codigo="GER-9", nombre="Geriátrico Reservado", estado=Dispositivo.Estado.ACTIVO
        )
        self.edif_a.dispositivos.add(self.otra)
        sector = Sector.objects.create(
            dispositivo=self.otra, edificio=self.edif_a, nombre="Sector Secreto", capacidad=3
        )
        plaza = Plaza.objects.create(sector=sector, codigo="SEC-01")
        self.estadia_dora = Estadia.objects.create(
            dispositivo=self.otra,
            ciudadano=self.dora,
            plaza=plaza,
            clave_alojamiento=Estadia.clave_para(self.dora),
            estado=Estadia.Estado.ACTIVA,
            fecha_ingreso=timezone.now() - timedelta(days=2),
        )

    def _personas(self, respuesta):
        return {e.ciudadano_id for e in respuesta.context["estadias"]}


class AlcanceDeLasEstadiasTests(BaseEstadias):
    def test_lista_solo_las_de_este_edificio_y_esta_institucion(self):
        respuesta = self._get(self.de_inst, self.edif_a, tab="estadias")

        self.assertEqual(self._personas(respuesta), {self.ana.pk, self.juan.pk})
        for ajeno in ("Ríos", "Sosa", "Vega", "Reservado", "Secreto"):
            self.assertNotContains(respuesta, ajeno)

    def test_la_estadia_de_otro_edificio_de_la_institucion_aparece_en_el_suyo(self):
        respuesta = self._get(self.de_inst, self.edif_b, tab="estadias")

        self.assertEqual(self._personas(respuesta), {self.beto.pk})

    def test_una_estadia_sin_plaza_no_aparece_en_ningun_edificio(self):
        for edificio in (self.edif_a, self.edif_b):
            with self.subTest(edificio=edificio.codigo):
                respuesta = self._get(self.de_inst, edificio, tab="estadias")
                self.assertNotIn(self.carla.pk, self._personas(respuesta))
                self.assertNotContains(respuesta, "Sin plaza")

    def test_la_tabla_coincide_con_el_contador_de_la_solapa(self):
        for edificio in (self.edif_a, self.edif_b):
            with self.subTest(edificio=edificio.codigo):
                respuesta = self._get(self.de_inst, edificio, tab="estadias")
                self.assertEqual(
                    respuesta.context["estadias"].paginator.count, respuesta.context["contadores"]["estadias"]
                )

    def test_quien_opera_un_solo_edificio_ve_las_de_ese(self):
        respuesta = self._get(self.de_a, self.edif_a, tab="estadias")

        self.assertEqual(self._personas(respuesta), {self.ana.pk, self.juan.pk})
        self.assertEqual(self._get(self.de_a, self.edif_b, tab="estadias").status_code, 404)

    def test_el_panel_no_se_arma_con_otra_solapa_abierta(self):
        respuesta = self._get(self.de_inst, self.edif_a, tab="equipo")

        self.assertNotIn("estadias", respuesta.context)

    def test_el_filtro_por_estado_y_sector_respeta_el_edificio(self):
        self.estadia_ana.estado = Estadia.Estado.EGRESADA
        self.estadia_ana.fecha_egreso = timezone.now()
        self.estadia_ana.clave_alojamiento = None
        self.estadia_ana.save(update_fields=["estado", "fecha_egreso", "clave_alojamiento"])

        egresadas = self._get(self.de_inst, self.edif_a, tab="estadias", estado=Estadia.Estado.EGRESADA)
        todas_b = self._get(self.de_inst, self.edif_b, tab="estadias", estado="TODAS")
        # Un sector de otro edificio no filtra: se descarta y se ven todas las alojadas de este.
        con_sector_ajeno = self._get(self.de_inst, self.edif_a, tab="estadias", sector=self.sector_b.pk)

        self.assertEqual(self._personas(egresadas), {self.ana.pk})
        self.assertEqual(self._personas(todas_b), {self.beto.pk})
        self.assertEqual(self._personas(con_sector_ajeno), {self.juan.pk})
        self.assertEqual(
            [opcion[0] for opcion in con_sector_ajeno.context["pildoras"][1]["opciones"]], [self.sector_a.pk]
        )


class AccionesDeLaFilaTests(BaseEstadias):
    def _filas(self, usuario):
        respuesta = self._get(usuario, self.edif_a, tab="estadias")
        return {e.ciudadano_id: e for e in respuesta.context["estadias"]}

    def test_con_todas_las_capacidades_la_fila_ofrece_ver_cambiar_y_egresar(self):
        fila = self._filas(self.de_inst)[self.ana.pk]

        self.assertTrue(fila.url_ver)
        self.assertIn(f"cambio={fila.pk}", fila.url_cambiar)
        self.assertTrue(fila.url_cambiar.startswith(self._url(self.edif_a)))
        self.assertIn(f"egreso={fila.pk}", fila.url_modal_egreso)

    def test_cada_accion_exige_su_capacidad(self):
        sin_egresar = self._con("Sin egresar", "dispositivo.ver", "dispositivo.admitir", "ciudadano.ver")
        sin_admitir = self._con("Sin admitir", "dispositivo.ver", "dispositivo.egresar", "ciudadano.ver")
        sin_ciudadano = self._con("Sin ciudadano", "dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar")

        a = self._filas(sin_egresar)[self.ana.pk]
        b = self._filas(sin_admitir)[self.ana.pk]
        c = self._filas(sin_ciudadano)[self.ana.pk]

        self.assertTrue(a.url_cambiar)
        self.assertFalse(hasattr(a, "url_egresar"))
        self.assertTrue(b.url_egresar)
        self.assertFalse(hasattr(b, "url_cambiar"))
        self.assertFalse(hasattr(c, "url_ver"))
        self.assertEqual(c.persona_visible, "Persona alojada")

    def test_el_modal_de_egreso_se_abre_por_url_y_vuelve_a_esta_solapa(self):
        respuesta = self._get(self.de_inst, self.edif_a, egreso=self.estadia_ana.pk)

        self.assertEqual(respuesta.context["tab"], "estadias")
        self.assertEqual(respuesta.context["estadia_egreso"], self.estadia_ana)
        self.assertContains(respuesta, f'name="next" value="{self._url(self.edif_a)}?tab=estadias"')

    def test_el_modal_de_cambio_se_abre_por_url_y_vuelve_a_esta_solapa(self):
        respuesta = self._get(self.de_inst, self.edif_a, cambio=self.estadia_ana.pk)

        self.assertEqual(respuesta.context["estadia_cambio"], self.estadia_ana)
        self.assertContains(respuesta, f'name="next" value="{self._url(self.edif_a)}?tab=estadias"')

    def test_el_modal_de_una_estadia_de_otro_edificio_o_institucion_da_404(self):
        for pedida in (self.estadia_beto, self.estadia_carla, self.estadia_dora):
            for parametro in ("egreso", "cambio"):
                with self.subTest(estadia=pedida.pk, parametro=parametro):
                    respuesta = self._get(self.de_inst, self.edif_a, **{parametro: pedida.pk})
                    self.assertEqual(respuesta.status_code, 404)

    def test_el_modal_sin_capacidad_da_403(self):
        sin_egresar = self._con("Sin egresar", "dispositivo.ver", "dispositivo.admitir", "ciudadano.ver")

        self.assertEqual(self._get(sin_egresar, self.edif_a, egreso=self.estadia_ana.pk).status_code, 403)


class VueltaAEstaSolapaTests(BaseEstadias):
    def _volver(self):
        return f"{self._url(self.edif_a)}?tab=estadias"

    def _egresar(self, **extra):
        self.client.force_login(self.de_inst)
        url = reverse("dispositivos:egresar", args=[self.cis.pk, self.estadia_ana.pk])
        datos = {"fecha_egreso": timezone.localtime().strftime("%Y-%m-%dT%H:%M"), "motivo": "", **extra}
        return self.client.post(url, datos)

    def _cambiar(self, **extra):
        self.client.force_login(self.de_inst)
        url = reverse("dispositivos:cambiar_plaza", args=[self.cis.pk, self.estadia_ana.pk])
        return self.client.post(url, {"plaza": self.plaza_libre.pk, **extra})

    def test_el_egreso_vuelve_a_la_solapa_del_edificio(self):
        respuesta = self._egresar(next=self._volver())

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], self._volver())

    def test_el_cambio_de_plaza_vuelve_a_la_solapa_del_edificio(self):
        respuesta = self._cambiar(next=self._volver())

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], self._volver())

    def test_un_next_ajeno_se_descarta(self):
        for hacer in (self._egresar, self._cambiar):
            with self.subTest(accion=hacer.__name__):
                respuesta = hacer(next=NEXT_AJENO)
                self.assertNotIn("sitio-ajeno", respuesta["Location"])


@tag("performance")
class PresupuestoDeLaSolapaTests(BaseEstadias):
    def _medir(self):
        self.client.force_login(self.de_inst)
        url = self._url(self.edif_a)
        self.client.get(url, {"tab": "estadias"})  # calienta sesión y caché, igual en las dos mediciones
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, {"tab": "estadias"})
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def test_la_solapa_cuesta_lo_mismo_con_dos_que_con_muchas_estadias(self):
        antes = self._medir()
        for numero in range(8):
            persona = Ciudadano.objects.create(dni=f"4000000{numero}", nombre="P", apellido=f"Alojada{numero}")
            plaza = Plaza.objects.create(sector=self.sector_a, codigo=f"M-{numero}")
            self._ingresar(persona, plaza, _local(MARTES, 6 + numero))
        despues = self._medir()

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, techo["consultas_fijas"])
