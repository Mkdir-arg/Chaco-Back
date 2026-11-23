"""Marca «Emergencia · Caso N» en las estadías de quienes entraron por un caso de Emergencia (Cambio 575).

1. La estadía que cuelga de un integrante de un caso lleva la marca y el caso; la de ingreso común no.
2. El número de caso enlaza a la ficha del caso solo con ``emergencia.operar`` o ``supervisar``; si no, texto plano.
3. Sin ``ciudadano.ver`` el nombre de la familia no sale en ninguna parte del HTML.
4. Aparece en la solapa Estadías del edificio, en Personas alojadas de la institución y en la ficha de la estadía.
5. El filtro «Origen: Emergencia» deja solo las de Emergencia.
6. El costo de las listas no crece con la cantidad de estadías de Emergencia.
"""

import json

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core import rbac
from legajos.models import Ciudadano
from programas.management.commands.seed_emergencia import asegurar_programa_emergencia
from programas.models import CasoEmergencia, GrupoFamiliar, IntegranteGrupo, Plaza
from programas.tests.test_dispositivos_bitacora_pantalla import MARTES, _local
from programas.tests.test_dispositivos_edificio_estadias import BaseEstadias
from programas.tests.test_emergencia_base import _permiso
from users.models import RolMeta

CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo_estadias"
PRESUPUESTOS = settings.BASE_DIR / "scripts" / "perf_budgets.json"
APELLIDO_FAMILIA = "Quiroga"
BASICAS = ("dispositivo.ver", "dispositivo.egresar", "dispositivo.admitir")
INSIGNIA = '<span class="badge badge-brand">Emergencia</span>'


class BaseMarca(BaseEstadias):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.addCleanup(cache.clear)
        self.programa_emergencia, _, _ = asegurar_programa_emergencia()
        self.caso = self._caso_de(self.estadia_ana, "C-000014", APELLIDO_FAMILIA)

    def _caso_de(self, estadia, numero, apellido):
        responsable = Ciudadano.objects.create(dni=f"2{estadia.pk:07d}", nombre="Resp", apellido=apellido)
        grupo = GrupoFamiliar.objects.create(
            responsable=responsable, traslado=GrupoFamiliar.Traslado.BOMBEROS, total_declarado=3
        )
        caso = CasoEmergencia.objects.create(
            numero=f"2026-{numero}",
            grupo=grupo,
            origen=CasoEmergencia.Origen.TERRITORIO,
            prioridad=CasoEmergencia.Prioridad.MEDIA,
            direccion="Calle 1",
            relevado_por=User.objects.get_or_create(username="relevador")[0],
            relevado_en=timezone.now(),
        )
        IntegranteGrupo.objects.create(grupo=grupo, orden=1, ciudadano=estadia.ciudadano, estadia=estadia)
        return caso

    def _con_emergencia(self, nombre, capacidad):
        """Un usuario de la institución más un rol de EMERGENCIA con ``capacidad``."""

        usuario = self._con(nombre, *BASICAS, "ciudadano.ver")
        rol = Group.objects.create(name=f"Emergencia {nombre}")
        RolMeta.objects.create(
            grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa_emergencia, activo=True
        )
        rol.permissions.add(_permiso(capacidad))
        usuario.groups.add(rol)
        cache.clear()
        return User.objects.get(pk=usuario.pk)

    def _html_edificio(self, usuario, **params):
        return self._get(usuario, self.edif_a, tab="estadias", **params)

    def _url_caso(self):
        return reverse("emergencia:caso_detalle", args=[self.caso.pk])


class MarcaEnLaSolapaDelEdificioTests(BaseMarca):
    def test_la_estadia_de_emergencia_lleva_marca_y_caso_y_la_comun_no(self):
        respuesta = self._html_edificio(self.de_inst)
        filas = {e.ciudadano_id: e for e in respuesta.context["estadias"]}

        self.assertEqual(filas[self.ana.pk].marca_emergencia["numero"], "2026-C-000014")
        self.assertIsNone(filas[self.juan.pk].marca_emergencia)
        self.assertContains(respuesta, "Caso 2026-C-000014")
        self.assertContains(respuesta, f"Familia {APELLIDO_FAMILIA}")
        self.assertContains(respuesta, INSIGNIA, count=1)

    def test_con_capacidad_de_emergencia_el_caso_es_un_enlace(self):
        for capacidad in ("emergencia.operar", "emergencia.supervisar"):
            with self.subTest(capacidad=capacidad):
                usuario = self._con_emergencia(f"con-{capacidad}", capacidad)
                respuesta = self._html_edificio(usuario)

                self.assertContains(respuesta, f'<a href="{self._url_caso()}"')

    def test_sin_capacidad_de_emergencia_el_caso_es_texto_plano(self):
        respuesta = self._html_edificio(self.de_inst)

        self.assertContains(respuesta, "Caso 2026-C-000014")
        self.assertNotContains(respuesta, self._url_caso())

    def test_un_rol_de_emergencia_sin_operar_ni_supervisar_no_enlaza(self):
        usuario = self._con_emergencia("solo-situacion", "emergencia.ver_situacion")

        self.assertNotContains(self._html_edificio(usuario), self._url_caso())

    def test_sin_ciudadano_ver_la_marca_no_revela_el_nombre_de_la_familia(self):
        sin_ver = self._con("Sin ver", *BASICAS)

        respuesta = self._html_edificio(sin_ver)
        html = respuesta.content.decode()

        self.assertContains(respuesta, "Persona alojada")
        self.assertContains(respuesta, "Caso 2026-C-000014")
        self.assertContains(respuesta, INSIGNIA)
        self.assertNotIn(APELLIDO_FAMILIA, html)
        self.assertNotIn("Familia ", html)

    def test_el_filtro_de_origen_deja_solo_las_de_emergencia(self):
        solo = self._html_edificio(self.de_inst, origen="emergencia")
        todas = self._html_edificio(self.de_inst)
        ajeno = self._html_edificio(self.de_inst, origen="otra-cosa")

        self.assertEqual(self._personas(solo), {self.ana.pk})
        self.assertEqual(self._personas(todas), {self.ana.pk, self.juan.pk})
        self.assertEqual(self._personas(ajeno), {self.ana.pk, self.juan.pk})
        self.assertEqual([p["nombre"] for p in solo.context["pildoras"]], ["estado", "sector", "origen"])
        self.assertTrue(solo.context["hay_filtros_estadias"])
        self.assertContains(solo, 'name="origen"')


class MarcaEnLaFichaDeLaInstitucionTests(BaseMarca):
    def _detalle(self, usuario):
        self.client.force_login(User.objects.get(pk=usuario.pk))
        return self.client.get(reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "estadias"})

    def test_personas_alojadas_lleva_la_marca(self):
        respuesta = self._detalle(self.de_inst)
        filas = {e.ciudadano_id: e for e in respuesta.context["estadias"]}

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(filas[self.ana.pk].marca_emergencia["numero"], "2026-C-000014")
        self.assertIsNone(filas[self.juan.pk].marca_emergencia)
        self.assertContains(respuesta, "Caso 2026-C-000014")

    def test_sin_ciudadano_ver_no_sale_la_familia(self):
        sin_ver = self._con("Sin ver", *BASICAS)

        html = self._detalle(sin_ver).content.decode()

        self.assertIn("Caso 2026-C-000014", html)
        self.assertNotIn(APELLIDO_FAMILIA, html)

    def test_el_enlace_exige_capacidad_de_emergencia(self):
        con = self._con_emergencia("operador", "emergencia.operar")

        self.assertContains(self._detalle(con), self._url_caso())
        self.assertNotContains(self._detalle(self.de_inst), self._url_caso())


class MarcaEnLaFichaDeLaEstadiaTests(BaseMarca):
    def _ficha(self, usuario, estadia):
        self.client.force_login(User.objects.get(pk=usuario.pk))
        return self.client.get(reverse("dispositivos:estadia_detalle", args=[self.cis.pk, estadia.pk]))

    def test_la_estadia_de_emergencia_lleva_la_marca_con_la_familia(self):
        respuesta = self._ficha(self.de_inst, self.estadia_ana)

        self.assertContains(respuesta, "Caso 2026-C-000014")
        self.assertContains(respuesta, f"Familia {APELLIDO_FAMILIA}")
        self.assertNotContains(respuesta, self._url_caso())

    def test_con_capacidad_de_emergencia_enlaza_al_caso(self):
        usuario = self._con_emergencia("operador", "emergencia.operar")

        self.assertContains(self._ficha(usuario, self.estadia_ana), self._url_caso())

    def test_la_estadia_comun_no_lleva_marca(self):
        respuesta = self._ficha(self.de_inst, self.estadia_juan)

        self.assertNotContains(respuesta, "Caso 2026-")
        self.assertIsNone(respuesta.context["marca_emergencia"])


@tag("performance")
class PresupuestoDeLaMarcaTests(BaseMarca):
    def _medir(self, url, params):
        self.client.force_login(self.de_inst)
        self.client.get(url, params)  # calienta sesión y caché
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, params)
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def _sumar_estadias_de_emergencia(self):
        for numero in range(6):
            persona = Ciudadano.objects.create(dni=f"4100000{numero}", nombre="P", apellido=f"Alojada{numero}")
            plaza = Plaza.objects.create(sector=self.sector_a, codigo=f"E-{numero}")
            estadia = self._ingresar(persona, plaza, _local(MARTES, 6 + numero))
            self._caso_de(estadia, f"C-0001{numero:02d}", f"Fam{numero}")

    def test_las_listas_cuestan_lo_mismo_con_una_que_con_muchas_estadias_de_emergencia(self):
        pedidos = {
            "edificio": (self._url(self.edif_a), {"tab": "estadias"}),
            "ficha": (reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "estadias"}),
        }
        antes = {nombre: self._medir(*pedido) for nombre, pedido in pedidos.items()}
        self._sumar_estadias_de_emergencia()
        despues = {nombre: self._medir(*pedido) for nombre, pedido in pedidos.items()}

        self.assertEqual(antes, despues)
        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertLessEqual(despues["edificio"], techo["consultas_fijas"])
