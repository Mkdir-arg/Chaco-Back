"""Ficha propia del edificio (#1168, análisis #1164).

Lo que se fija acá:

1. Permiso y alcance: 200 para quien ve el edificio; 404 fuera de alcance, para huérfanos e inactivos si
   no es admin, y para un id que no existe (CA2, CA3). El admin abre huérfanos e inactivos (CA4).
2. Instituciones fuera de alcance no se nombran; los sectores son solo los de las instituciones que
   alcanza (CA6).
3. Sin alcance de inspección: estado y fecha, sin quién relevó, observaciones ni registro (CA7).
4. «Crear relevamiento» según CA8; «Editar edificio» solo con alcance institución (Cambio 555), y ninguna
   otra acción de escritura (desvincular, cargar, vincular).
5. El listado enlaza a la ficha.
6. El costo de la ficha no crece con relevamientos, fotos ni instituciones (``dispositivos_edificio_ficha``).
"""

import json
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import Dispositivo, Edificio, MiembroEquipoDispositivo, Plaza, Sector
from programas.tests.test_dispositivos_edificios_selector import BaseEdificios
from programas.tests.test_dispositivos_inspecciones import Criticidad

PRESUPUESTOS = Path(settings.BASE_DIR) / "scripts" / "perf_budgets.json"


def _url(edificio):
    return reverse("dispositivos:edificio_detalle", args=[edificio.pk])


class BaseFicha(BaseEdificios):
    def _get(self, usuario, edificio, **params):
        return self._cliente(usuario).get(_url(edificio), params)

    def _ficha(self, usuario, edificio):
        respuesta = self._get(usuario, edificio)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta, respuesta.context["ficha"]


class PermisoYAlcanceTests(BaseFicha):
    def test_quien_ve_el_edificio_entra(self):
        respuesta, ficha = self._ficha(self.del_parador, self.predio)

        self.assertTemplateUsed(respuesta, "programas/dispositivos/edificios/detail.html")
        self.assertEqual(ficha["codigo"], "ED-PREDIO")

    def test_fuera_de_alcance_huerfano_inactivo_e_inexistente_dan_404(self):
        for edificio in (self.edificio_cis, self.huerfano, self.inactivo):
            with self.subTest(edificio=edificio.codigo):
                self.assertEqual(self._get(self.del_parador, edificio).status_code, 404)
        respuesta = self._cliente(self.del_parador).get(reverse("dispositivos:edificio_detalle", args=[99999]))
        self.assertEqual(respuesta.status_code, 404)

    def test_ver_todos_no_abre_huerfanos_ni_inactivos(self):
        for edificio in (self.huerfano, self.inactivo):
            with self.subTest(edificio=edificio.codigo):
                self.assertEqual(self._get(self.red, edificio).status_code, 404)

    def test_el_admin_abre_huerfanos_e_inactivos(self):
        for edificio in (self.huerfano, self.inactivo):
            with self.subTest(edificio=edificio.codigo):
                self._ficha(self.admin, edificio)

    def test_sin_edificio_ver_es_403(self):
        solo_dispositivos = self._usuario("solo_disp", ("dispositivo.ver",), [self.parador])

        self.assertEqual(self._get(solo_dispositivos, self.predio).status_code, 403)


class InstitucionesYSectoresTests(BaseFicha):
    def setUp(self):
        super().setUp()
        norte = Sector.objects.create(dispositivo=self.parador, edificio=self.predio, nombre="Pabellón Norte")
        Plaza.objects.create(sector=norte, codigo="N-01")
        Plaza.objects.create(sector=norte, codigo="N-02")
        Sector.objects.create(dispositivo=self.geriatrico, edificio=self.predio, nombre="Ala geriátrica")
        Sector.objects.create(dispositivo=self.parador, edificio=self.predio, nombre="Dado de baja", activo=False)

    def test_instituciones_fuera_de_alcance_no_se_nombran(self):
        respuesta, ficha = self._ficha(self.del_parador, self.predio)

        self.assertEqual([i["nombre"] for i in ficha["instituciones"]], ["Parador"])
        self.assertEqual(ficha["otras"], 1)
        self.assertNotContains(respuesta, "Geriátrico")

    def test_sectores_activos_solo_de_las_instituciones_que_alcanza(self):
        _respuesta, ficha = self._ficha(self.del_parador, self.predio)

        self.assertEqual(
            ficha["sectores"],
            [
                {
                    "institucion": "Parador",
                    "sectores": [
                        {
                            "pk": ficha["sectores"][0]["sectores"][0]["pk"],
                            "nombre": "Pabellón Norte",
                            "tipo": "Otro",
                            "plazas": 2,
                        }
                    ],
                    "n_plazas": 2,
                }
            ],
        )

    def test_el_admin_ve_los_sectores_de_las_dos(self):
        _respuesta, ficha = self._ficha(self.admin, self.predio)

        self.assertEqual([grupo["institucion"] for grupo in ficha["sectores"]], ["Geriátrico", "Parador"])


class RelevamientoTests(BaseFicha):
    def setUp(self):
        super().setUp()
        self._relevar(self.predio, Criticidad.ALTA, fotos=("fachada",), observaciones="Pérdida de gas")

    def test_con_alcance_de_inspeccion_ve_el_informe_y_el_registro(self):
        respuesta, ficha = self._ficha(self.admin, self.predio)

        self.assertTrue(ficha["ve_detalle"])
        self.assertEqual(ficha["observaciones"], "Pérdida de gas")
        self.assertTrue(ficha["relevo"])
        self.assertEqual(len(ficha["eventos"]), 1)
        self.assertContains(respuesta, "Pérdida de gas")

    def test_sin_alcance_de_inspeccion_solo_estado_y_fecha(self):
        respuesta, ficha = self._ficha(self.del_parador, self.predio)

        self.assertFalse(ficha["ve_detalle"])
        self.assertEqual(ficha["estado"]["clave"], "CRITICO")
        self.assertIsNotNone(ficha["ultima_fecha"])
        self.assertEqual((ficha["observaciones"], ficha["relevo"], ficha["eventos"]), ("", "", []))
        self.assertNotContains(respuesta, "Pérdida de gas")
        self.assertNotContains(respuesta, "fachada")


class AccionesTests(BaseFicha):
    def test_crear_relevamiento_para_quien_coordina_un_edificio_libre(self):
        coordinador = self._usuario("coord_edif", ("edificio.ver", "inspeccion.asignar"), [self.parador])
        destino = f"{reverse('dispositivos:relevamientos')}?asignar={self.predio.pk}"

        self.assertContains(self._get(coordinador, self.predio), destino)
        self.assertNotContains(self._get(self.del_parador, self.predio), "?asignar=")
        self._crear()  # con uno en curso ya no se ofrece
        self.assertNotContains(self._get(coordinador, self.predio), "?asignar=")

    def test_sin_editar_no_hay_acciones_de_escritura_del_edificio(self):
        html = self._get(self.del_parador, self.predio).content.decode()

        self.assertNotIn(reverse("dispositivos:edificio_editar", args=[self.parador.pk, self.predio.pk]), html)
        for texto in ("Editar edificio", "Desvincular", "Cargar edificio", "Vincular un edificio"):
            self.assertNotIn(texto, html)

    def test_el_admin_edita_pero_la_ficha_no_desvincula_ni_carga(self):
        html = self._get(self.admin, self.predio).content.decode()

        self.assertIn("Editar edificio", html)
        for texto in ("Desvincular", "Cargar edificio", "Vincular un edificio"):
            self.assertNotIn(texto, html)

    def test_el_listado_enlaza_a_la_ficha(self):
        respuesta = self._cliente(self.del_parador).get(reverse("dispositivos:edificios"))

        self.assertContains(respuesta, _url(self.predio))


class EditarEdificioTests(BaseFicha):
    """«Editar edificio» (Cambio 555): lleva al modal de Infraestructura de una institución que el usuario edita."""

    def _destino(self, dispositivo):
        return f"{reverse('dispositivos:detalle', args=[dispositivo.pk])}?tab=infraestructura&edificio={self.predio.pk}"

    def _miembro_que_edita(self, nombre, dispositivo, alcance=None, edificios=()):
        usuario = self._usuario(nombre, ("edificio.ver", "dispositivo.ver", "dispositivo.editar"), [dispositivo])
        if alcance:
            fila = MiembroEquipoDispositivo.objects.get(usuario=usuario, dispositivo=dispositivo)
            fila.alcance = alcance
            fila.save(update_fields=["alcance"])
            fila.edificios.set(edificios)
        return usuario

    def test_quien_edita_su_institucion_ve_el_boton_hacia_esa_institucion(self):
        editor = self._miembro_que_edita("editor_geriatrico", self.geriatrico)

        respuesta = self._get(editor, self.predio)

        self.assertContains(respuesta, "Editar edificio")
        self.assertEqual(respuesta.context["ficha"]["url_editar"], self._destino(self.geriatrico))

    def test_el_enlace_abre_el_modal_de_edicion_del_edificio(self):
        editor = self._miembro_que_edita("editor_parador", self.parador)

        respuesta = self._cliente(editor).get(self._get(editor, self.predio).context["ficha"]["url_editar"])

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["edificio_en_edicion"], self.predio)

    def test_sin_dispositivo_editar_no_hay_boton(self):
        lector = self._usuario("lector", ("edificio.ver", "dispositivo.ver"), [self.parador])

        self.assertEqual(self._get(lector, self.predio).context["ficha"]["url_editar"], "")

    def test_con_alcance_edificios_no_hay_boton_aunque_el_edificio_este_en_su_alcance(self):
        limitado = self._miembro_que_edita(
            "limitado", self.parador, MiembroEquipoDispositivo.Alcance.EDIFICIOS, [self.predio]
        )

        respuesta = self._get(limitado, self.predio)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["ficha"]["url_editar"], "")
        self.assertNotContains(respuesta, "Editar edificio")

    def test_en_un_dispositivo_cerrado_no_hay_boton(self):
        editor = self._miembro_que_edita("editor_cerrado", self.parador)
        Dispositivo.objects.filter(pk=self.parador.pk).update(estado=Dispositivo.Estado.CERRADO)

        self.assertEqual(self._get(editor, self.predio).context["ficha"]["url_editar"], "")

    def test_el_servidor_rechaza_editar_sin_capacidad_o_desde_otra_institucion(self):
        lector = self._usuario("lector_post", ("edificio.ver", "dispositivo.ver"), [self.parador])
        ajeno = self._miembro_que_edita("editor_cis", self.cis)
        limitado = self._miembro_que_edita(
            "limitado_post", self.parador, MiembroEquipoDispositivo.Alcance.EDIFICIOS, [self.predio]
        )
        datos = {"codigo": "ED-PREDIO", "nombre": "Cambiado"}

        casos = (
            (lector, self.parador, {403}),
            (ajeno, self.parador, {403, 404}),
            (ajeno, self.cis, {404}),  # el predio no es de su institución
            (limitado, self.parador, {403, 404}),
        )
        for usuario, desde, esperados in casos:
            with self.subTest(usuario=usuario.username, desde=desde.codigo):
                url = reverse("dispositivos:edificio_editar", args=[desde.pk, self.predio.pk])
                respuesta = self._cliente(usuario).post(url, datos, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                self.assertIn(respuesta.status_code, esperados)
                self.predio.refresh_from_db()
                self.assertEqual(self.predio.nombre, "Predio Resistencia")

    def test_quien_edita_su_institucion_guarda_el_cambio(self):
        editor = self._miembro_que_edita("editor_guarda", self.parador)
        url = reverse("dispositivos:edificio_editar", args=[self.parador.pk, self.predio.pk])

        respuesta = self._cliente(editor).post(
            url, {"codigo": "ED-PREDIO", "nombre": "Predio Norte", "calle": "Av. Sarmiento", "numero": "1234"}
        )

        self.assertEqual(respuesta.status_code, 302)
        self.predio.refresh_from_db()
        self.assertEqual(self.predio.nombre, "Predio Norte")

    def test_el_nombre_vacio_se_rechaza_con_error_de_campo(self):
        editor = self._miembro_que_edita("editor_vacio", self.parador)
        url = reverse("dispositivos:edificio_editar", args=[self.parador.pk, self.predio.pk])

        respuesta = self._cliente(editor).post(
            url, {"codigo": "ED-PREDIO", "nombre": ""}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.predio.refresh_from_db()
        self.assertEqual(self.predio.nombre, "Predio Resistencia")


@tag("performance")
class PresupuestoTests(BaseFicha):
    def _medir(self):
        cliente = self._cliente(self.admin)
        cliente.get(_url(self.predio))  # calienta sesión y caché del programa, igual en las dos mediciones
        with CaptureQueriesContext(connection) as consultas:
            respuesta = cliente.get(_url(self.predio))
        return len(respuesta.context["ficha"]["eventos"]), len(consultas)

    def test_la_ficha_cuesta_lo_mismo_con_uno_que_con_muchos(self):
        Sector.objects.create(dispositivo=self.parador, edificio=self.predio, nombre="Norte")
        self._relevar(self.predio, Criticidad.MEDIA, fotos=("fachada",))
        eventos_antes, antes = self._medir()

        for numero in range(5):
            Sector.objects.create(dispositivo=self.geriatrico, edificio=self.predio, nombre=f"Sector {numero}")
        self.predio.dispositivos.add(self.cis)
        Edificio.objects.filter(pk=self.predio.pk).update(localidad="Resistencia")
        for dias in range(1, 7):
            self._relevar(self.predio, Criticidad.BAJA, fotos=("patio", "techo"), dias_atras=dias)
        eventos_despues, despues = self._medir()

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"]["dispositivos_edificio_ficha"]
        self.assertEqual((eventos_antes, eventos_despues), (1, 7))
        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, techo["consultas_fijas"])

    def test_el_peor_caso_con_un_relevamiento_en_curso_entra_en_el_techo(self):
        Sector.objects.create(dispositivo=self.parador, edificio=self.predio, nombre="Norte")
        self._relevar(self.predio, Criticidad.MEDIA, fotos=("fachada",))
        self._crear()  # asignado y sin resultado: suma la consulta de quién ve la asignación
        _eventos, antes = self._medir()
        for numero in range(3):
            Sector.objects.create(dispositivo=self.geriatrico, edificio=self.predio, nombre=f"Sector {numero}")
        self.predio.dispositivos.add(self.cis)
        _eventos, con_en_curso = self._medir()

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"]["dispositivos_edificio_ficha"]
        self.assertEqual(antes, con_en_curso)
        self.assertEqual(con_en_curso, techo["consultas_fijas"])


class VolverDelInformeTests(BaseFicha):
    """Cambio 487: el informe abierto desde la ficha del edificio vuelve a la ficha."""

    def setUp(self):
        super().setUp()
        self.inspeccion = self._relevar(self.predio, Criticidad.MEDIA, fotos=("fachada",))
        self.informe = reverse("dispositivos:relevamiento_informe", args=[self.inspeccion.pk])

    def test_el_registro_de_la_ficha_enlaza_al_informe_con_el_edificio(self):
        _respuesta, ficha = self._ficha(self.admin, self.predio)

        self.assertEqual(ficha["eventos"][0]["enlace"], f"{self.informe}?edificio={self.predio.pk}")

    def test_el_informe_vuelve_a_la_ficha_del_edificio(self):
        respuesta = self._cliente(self.admin).get(self.informe, {"edificio": self.predio.pk})

        self.assertEqual(respuesta.context["volver_url"], _url(self.predio))
        self.assertEqual(respuesta.context["volver_label"], "Predio Resistencia")

    def test_revisado_vuelve_al_informe_conservando_el_edificio(self):
        respuesta = self._cliente(self.admin).get(self.informe, {"edificio": self.predio.pk})

        self.assertIn(f"edificio={self.predio.pk}", respuesta.context["url_revisar"])
        self.assertIn("origen=informe", respuesta.context["url_revisar"])

    def test_sin_edificio_ver_el_edificio_de_la_url_no_arma_el_volver(self):
        """El coordinador ve el relevamiento pero no la sección Edificios: vuelve a Relevamientos."""

        respuesta = self._cliente(self.coordinador).get(self.informe, {"edificio": self.predio.pk})

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.context["volver_url"].startswith(reverse("dispositivos:relevamientos")))

    def test_un_edificio_que_no_ve_no_arma_el_volver(self):
        respuesta = self._cliente(self.admin).get(self.informe, {"edificio": 99999})

        self.assertNotEqual(respuesta.context["volver_url"], _url(self.predio))
        self.assertNotIn("edificios/99999", respuesta.context["volver_url"])

    def test_un_id_que_no_es_decimal_ascii_no_rompe_el_volver(self):
        respuesta = self._cliente(self.admin).get(self.informe, {"edificio": "²"})

        self.assertEqual(respuesta.status_code, 200)
