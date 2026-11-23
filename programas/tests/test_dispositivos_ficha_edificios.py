"""La ficha de la institución muestra sus edificios (Cambio 570, PR 6 del lote «el edificio como unidad operativa»).

1. Tarjetas: una por edificio, con la ocupación del censo, los disponibles, el equipo y el enlace a la página del edificio.
2. Alcance: quien opera un edificio ve solo esa tarjeta, y los kits solo donde puede recibirlos.
3. Costo: las consultas de las tarjetas no crecen con la cantidad de edificios.
4. Aviso: un edificio sin plazas disponibles sale en una alerta de advertencia, que nombra a los que sí tienen lugar.
5. La ficha ya no ingresa personas ni lleva la bitácora, y tiene las solapas Datos, Personas alojadas, Equipo e Historial.
6. Enlaces de siempre: ``?tab=sectores|infraestructura`` redirigen a la solapa o al edificio equivalente.
"""

import json

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core import rbac
from programas.models import Edificio, Estadia, MiembroEquipoDispositivo, Plaza, Sector
from programas.services.detalle_dispositivo import SOLAPAS, normalizar_solapa
from programas.services.dispositivos import contar_miembros_por_edificio
from programas.services.ficha_edificios import aviso_sin_plazas
from programas.tests.test_dispositivos_edificio_operativo import BaseOperativo
from programas.tests.test_dispositivos_inspecciones import _permiso
from programas.tests.test_equipo_alcance_edificio import Alcance
from users.models import RolMeta

PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"


class BaseFicha(BaseOperativo):
    def _ficha(self, usuario=None, **params):
        self.client.force_login(User.objects.get(pk=(usuario or self.de_inst).pk))
        return self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]), params)

    def _tarjetas(self, usuario=None):
        respuesta = self._ficha(usuario)
        self.assertEqual(respuesta.status_code, 200)
        return {fila["pk"]: fila for fila in respuesta.context["tarjetas_edificios"]}


class TarjetasTests(BaseFicha):
    def test_una_tarjeta_por_edificio_con_ocupacion_disponibles_y_enlace(self):
        tarjetas = self._tarjetas()

        self.assertEqual(set(tarjetas), {self.edif_a.pk, self.edif_b.pk})
        a, b = tarjetas[self.edif_a.pk], tarjetas[self.edif_b.pk]
        # A tiene sus dos plazas ocupadas (Ana y Juan); B tiene la suya libre.
        self.assertEqual((a["ocupacion"]["valor"], a["ocupacion"]["maximo"], a["disponibles"]), (2, 2, 0))
        self.assertEqual((b["ocupacion"]["valor"], b["ocupacion"]["maximo"], b["disponibles"]), (0, 1, 1))
        self.assertEqual(a["url_abrir"], reverse("dispositivos:edificio_operativo", args=[self.cis.pk, self.edif_a.pk]))

    def test_la_seccion_y_la_tarjeta_se_dibujan_con_el_enlace_al_edificio(self):
        respuesta = self._ficha()

        self.assertContains(respuesta, "Edificios · 2")
        self.assertContains(respuesta, "data-tarjeta-edificio", count=2)
        self.assertContains(respuesta, "Abrir edificio")
        self.assertContains(respuesta, reverse("dispositivos:edificio_operativo", args=[self.cis.pk, self.edif_a.pk]))

    def test_el_equipo_cuenta_a_la_institucion_y_a_quien_lista_el_edificio(self):
        tarjetas = self._tarjetas()

        # Operador y «De institución» valen en los dos; «De A» solo en A.
        self.assertEqual(tarjetas[self.edif_a.pk]["equipo"]["texto"], "3 personas")
        self.assertEqual(tarjetas[self.edif_b.pk]["equipo"]["texto"], "2 personas")

    def test_quien_opera_un_edificio_ve_solo_esa_tarjeta(self):
        self.assertEqual(set(self._tarjetas(self.de_a)), {self.edif_a.pk})

    def test_los_kits_solo_donde_se_pueden_recibir(self):
        sin_kits = self._con("Sin kits", "dispositivo.ver")

        self.assertIsNone(self._tarjetas(sin_kits)[self.edif_a.pk]["kits"])
        con_kits = self._con("Con kits", "dispositivo.ver", "emergencia.recibir_kit")
        self.assertEqual(self._tarjetas(con_kits)[self.edif_a.pk]["kits"]["texto"], "0 por recibir")

    def test_los_kits_se_cortan_por_edificio_cuando_el_alcance_de_recibirlos_es_acotado(self):
        """Ve toda la institución, pero recibe kits solo en A: la fila Kits sale en la tarjeta de A y no en la de B."""

        usuario = self._con("Kits solo en A", "dispositivo.ver")
        usuario.groups.add(rol_kits := self._rol_de("Recibe kits", "emergencia.recibir_kit"))
        fila = MiembroEquipoDispositivo.objects.create(
            dispositivo=self.cis,
            usuario=usuario,
            rol=rol_kits,
            alcance=Alcance.EDIFICIOS,
        )
        fila.edificios.set([self.edif_a])

        tarjetas = self._tarjetas(usuario)

        self.assertEqual(set(tarjetas), {self.edif_a.pk, self.edif_b.pk})
        self.assertEqual(tarjetas[self.edif_a.pk]["kits"]["texto"], "0 por recibir")
        self.assertIsNone(tarjetas[self.edif_b.pk]["kits"])

    def test_sin_dispositivo_editar_la_seccion_no_ofrece_editar_desvincular_ni_agregar(self):
        solo_ver = self._con("Solo ver edificios", "dispositivo.ver")

        respuesta = self._ficha(solo_ver)
        tarjetas = self._tarjetas(solo_ver)

        for tarjeta in tarjetas.values():
            self.assertEqual((tarjeta["url_editar"], tarjeta["url_desvincular"]), ("", ""))
        self.assertNotContains(respuesta, "?edificio=vincular")
        self.assertNotContains(respuesta, "?edificio=nuevo")
        self.assertNotContains(respuesta, "Agregar edificio")

    def test_con_dispositivo_editar_la_seccion_ofrece_las_tres_acciones(self):
        editor = self._con("Editor de edificios", "dispositivo.ver", "dispositivo.editar")

        respuesta = self._ficha(editor)
        tarjeta = self._tarjetas(editor)[self.edif_a.pk]

        self.assertEqual(
            tarjeta["url_editar"], f"{reverse('dispositivos:detalle', args=[self.cis.pk])}?edificio={self.edif_a.pk}"
        )
        self.assertEqual(
            tarjeta["url_desvincular"], reverse("dispositivos:edificio_desvincular", args=[self.cis.pk, self.edif_a.pk])
        )
        self.assertContains(respuesta, "?edificio=vincular")
        self.assertContains(respuesta, "?edificio=nuevo")

    def _rol_de(self, nombre, *capacidades):
        """Un rol de Programa con solo esas capacidades."""

        rol = Group.objects.create(name=nombre)
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        return rol

    def test_un_tipo_sin_plazas_no_dibuja_barra_ni_disponibles(self):
        self.tipo.plaza_obligatoria_al_ingresar = False
        self.tipo.save(update_fields=["plaza_obligatoria_al_ingresar"])

        tarjeta = self._tarjetas()[self.edif_a.pk]

        self.assertIsNone(tarjeta["ocupacion"])
        self.assertIsNone(tarjeta["disponibles"])


@tag("performance")
class PresupuestoFichaTests(BaseFicha):
    def test_el_costo_no_crece_con_la_cantidad_de_edificios(self):
        self.de_inst.is_superuser = True
        self.de_inst.save(update_fields=["is_superuser"])
        self._ficha()  # calienta cachés (contenttypes, permisos)
        with CaptureQueriesContext(connection) as con_dos:
            self._ficha()
        for n in range(3, 8):
            edificio = self._edificio(f"ED-{n}")
            sector = Sector.objects.create(dispositivo=self.cis, nombre=f"Sector {n}", capacidad=2, edificio=edificio)
            Plaza.objects.create(sector=sector, codigo=f"S{n}-01")
        with CaptureQueriesContext(connection) as con_siete:
            respuesta = self._ficha()

        self.assertEqual(len(respuesta.context["tarjetas_edificios"]), 7)
        self.assertEqual(len(con_siete), len(con_dos))
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"]["dispositivos_detalle_con_edificios"]
        self.assertLessEqual(len(con_siete), techo["consultas_fijas"])


class ContarMiembrosTests(BaseFicha):
    def test_cuenta_como_la_pagina_del_edificio(self):
        cuentas = contar_miembros_por_edificio(self.cis, [self.edif_a.pk, self.edif_b.pk])

        self.assertEqual(cuentas, {self.edif_a.pk: 3, self.edif_b.pk: 2})

    def test_una_fila_sin_alcance_cargado_vale_en_toda_la_institucion(self):
        MiembroEquipoDispositivo.objects.filter(usuario=self.de_a).update(alcance=None)

        cuentas = contar_miembros_por_edificio(self.cis, [self.edif_a.pk, self.edif_b.pk])

        self.assertEqual(cuentas, {self.edif_a.pk: 3, self.edif_b.pk: 3})

    def test_sin_edificios_no_consulta(self):
        with self.assertNumQueries(0):
            self.assertEqual(contar_miembros_por_edificio(self.cis, []), {})

    def test_son_dos_consultas_sin_importar_cuantos_edificios(self):
        ids = [self.edif_a.pk, self.edif_b.pk] + [self._edificio(f"ED-{n}").pk for n in range(3, 8)]

        with self.assertNumQueries(2):
            contar_miembros_por_edificio(self.cis, ids)


class AvisoSinPlazasTests(BaseFicha):
    def _aviso(self):
        return self._ficha().context["aviso_sin_plazas"]

    def test_un_edificio_lleno_se_nombra_y_sugiere_el_que_tiene_lugar(self):
        aviso = self._aviso()

        self.assertEqual(aviso["tono"], "warning")
        self.assertEqual(aviso["titulo"], "Edificio ED-A no tiene plazas disponibles")
        self.assertIn("abrí el Edificio ED-B", aviso["texto"])
        self.assertEqual(aviso["accion_url"], self._url(self.edif_a))

    def test_se_dibuja_en_la_ficha(self):
        self.assertContains(self._ficha(), "Edificio ED-A no tiene plazas disponibles")

    def test_si_todos_estan_llenos_es_un_solo_aviso_resumen(self):
        persona = self._persona("30999000")
        self._ingresar(persona, self.plaza_b, self._momento())

        aviso = self._aviso()

        self.assertEqual(aviso["titulo"], "2 edificios no tienen plazas disponibles")
        self.assertEqual(aviso["accion_url"], "")
        self.assertIn("Ninguno de los edificios tiene lugar", aviso["texto"])

    def test_con_muchos_llenos_nombra_hasta_tres_y_cuenta_el_resto(self):
        filas = [
            {"nombre": f"Edificio {n}", "tiene_plazas": True, "disponibles": 0, "url_abrir": f"/e/{n}/"}
            for n in range(1, 6)
        ]

        aviso = aviso_sin_plazas(filas, self.cis)

        self.assertEqual(aviso["titulo"], "5 edificios no tienen plazas disponibles")
        self.assertTrue(aviso["texto"].startswith("Edificio 1, Edificio 2, Edificio 3 y 2 más."))
        self.assertNotIn("Edificio 4", aviso["texto"])

    def test_sin_edificio_lleno_no_hay_aviso(self):
        Estadia.objects.filter(pk=self.estadia_ana.pk).update(plaza=None)

        self.assertIsNone(self._aviso())

    def test_un_edificio_sin_plazas_cargadas_no_es_un_edificio_lleno(self):
        Estadia.objects.filter(plaza=self.plaza_a).update(plaza=None)
        Plaza.todas.filter(sector=self.sector_a).update(activa=False)

        self.assertIsNone(self._aviso())

    def test_una_institucion_que_no_esta_activa_no_lo_muestra(self):
        self.cis.estado = self.cis.Estado.INACTIVO
        self.cis.save(update_fields=["estado"])

        self.assertIsNone(self._aviso())

    def _persona(self, dni):
        from legajos.models import Ciudadano

        return Ciudadano.objects.create(dni=dni, nombre="Eva", apellido="Soto")

    def _momento(self):
        from programas.tests.test_dispositivos_bitacora_pantalla import MARTES, _local

        return _local(MARTES, 12)


class QueNoEstaTests(BaseFicha):
    def test_la_ficha_ya_no_ingresa_personas_ni_lleva_la_bitacora(self):
        respuesta = self._ficha()

        self.assertNotContains(respuesta, "Ingresar persona")
        self.assertNotContains(respuesta, "Bitácora del turno")
        self.assertNotContains(respuesta, reverse("dispositivos:ingreso_persona", args=[self.cis.pk]))

    def test_las_solapas_son_cuatro(self):
        self.assertEqual(SOLAPAS, ("datos", "estadias", "equipo", "historial"))
        respuesta = self._ficha()

        for rotulo in ("Datos", "Personas alojadas", "Equipo", "Historial"):
            self.assertContains(respuesta, rotulo)
        self.assertNotContains(respuesta, "Sectores y plazas")

    def test_una_solapa_que_se_fue_o_no_existe_cae_en_la_de_siempre(self):
        for pedida in ("sectores", "infraestructura", "inexistente", ""):
            with self.subTest(pedida=pedida):
                self.assertEqual(normalizar_solapa(pedida), "datos")
        self.assertEqual(normalizar_solapa("estadias"), "estadias")


class EnlacesViejosTests(BaseFicha):
    def _redirige(self, usuario=None, **params):
        respuesta = self._ficha(usuario, **params)
        self.assertEqual(respuesta.status_code, 302, params)
        return respuesta.url

    def _pagina(self, edificio, **consulta):
        from django.utils.http import urlencode

        return f"{self._url(edificio)}?{urlencode(consulta)}"

    def test_ver_edificio_va_al_estado_edilicio_de_ese_edificio(self):
        url = self._redirige(tab="infraestructura", ver_edificio=self.edif_a.pk)

        self.assertEqual(url, self._pagina(self.edif_a, tab="edilicio"))

    def test_agregar_persona_va_al_alta_del_equipo_del_edificio(self):
        url = self._redirige(tab="infraestructura", agregar_persona=self.edif_b.pk)

        self.assertEqual(url, self._pagina(self.edif_b, tab="equipo", equipo="sumar"))

    def test_el_edificio_ajeno_no_redirige_a_un_404(self):
        # «De A» no ve B: el enlace cae en la ficha, igual que un id que no existe.
        for edificio in (self.edif_b.pk, 99999):
            with self.subTest(edificio=edificio):
                self.assertEqual(self._ficha(self.de_a, tab="infraestructura", ver_edificio=edificio).status_code, 200)

    def test_los_modales_del_edificio_siguen_en_la_ficha(self):
        for params in (
            {"tab": "infraestructura"},
            {"tab": "infraestructura", "edificio": "nuevo"},
            {"edificio": "nuevo"},
        ):
            with self.subTest(params=params):
                self.assertEqual(self._ficha(**params).status_code, 200)
        self.assertContains(self._ficha(edificio="nuevo"), reverse("dispositivos:edificio_crear", args=[self.cis.pk]))

    def test_sectores_con_un_edificio_pedido_va_a_su_pagina(self):
        url = self._redirige(tab="sectores", sectores_edificio=self.edif_b.pk)

        self.assertEqual(url, self._pagina(self.edif_b, tab="sectores"))

    def test_sectores_con_un_solo_edificio_a_la_vista_va_a_su_pagina(self):
        url = self._redirige(self.de_a, tab="sectores")

        self.assertEqual(url, self._pagina(self.edif_a, tab="sectores"))

    def test_sectores_con_varios_edificios_va_a_la_pantalla_de_siempre(self):
        url = self._redirige(tab="sectores")

        self.assertEqual(url, reverse("dispositivos:sectores", args=[self.cis.pk]))

    def test_un_modal_del_mapa_va_a_la_pantalla_de_sectores_con_su_parametro(self):
        url = self._redirige(tab="sectores", editar_plaza=self.plaza_a.pk, sectores_edificio=self.edif_a.pk)

        self.assertTrue(url.startswith(reverse("dispositivos:sectores", args=[self.cis.pk])), url)
        self.assertIn(f"editar_plaza={self.plaza_a.pk}", url)

    def test_editar_sector_viaja_como_sector(self):
        url = self._redirige(tab="sectores", editar_sector=self.sector_a.pk)

        self.assertIn(f"sector={self.sector_a.pk}", url)
        self.assertNotIn("editar_sector", url)

    def test_las_solapas_que_quedan_no_redirigen(self):
        for tab in ("datos", "estadias", "equipo", "historial"):
            with self.subTest(tab=tab):
                self.assertEqual(self._ficha(tab=tab).status_code, 200)

    def test_el_destino_no_copia_crudo_el_pedido(self):
        url = self._redirige(tab="sectores", editar_plaza="1&next=http://malo.example")

        self.assertNotIn("malo.example", url.replace("%3A%2F%2Fmalo.example", ""))
        self.assertTrue(url.startswith("/"), url)


class EdificioFueraDeAlcanceTests(BaseFicha):
    def test_un_edificio_desvinculado_no_tiene_tarjeta(self):
        Edificio.objects.get(pk=self.edif_b.pk).dispositivos.remove(self.cis)

        self.assertEqual(set(self._tarjetas()), {self.edif_a.pk})

    def test_con_alcance_edificios_la_cuenta_de_equipo_sigue_la_regla_del_edificio(self):
        otro = self._con("Otro de B", "dispositivo.ver", alcance=Alcance.EDIFICIOS, edificios=[self.edif_b])

        self.assertEqual(self._tarjetas(otro)[self.edif_b.pk]["equipo"]["texto"], "3 personas")
