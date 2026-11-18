"""Selector de la sección «Edificios» (#1166, análisis #1164).

Lo que se fija acá:

1. Alcance: el Equipo ve los edificios de sus instituciones; ``ver_todos``, la red; el admin, todo.
2. Inactivos y sin institución: nunca para quien no es admin, aunque pida ``situacion``; para el
   admin, solo si la pide.
3. Cada filtro (búsqueda, localidad, estado edilicio, compartido), solo y combinado.
4. Las instituciones fuera de alcance se cuentan sin nombre; el enlace va solo si puede abrirla.
5. ``url_asignar`` solo para quien coordina un edificio que admite un relevamiento nuevo.
6. ``filas_del_listado`` cuesta lo mismo con 2 que con 20 edificios.
"""

from django.db import connection
from django.test.utils import CaptureQueriesContext

from programas.models import Edificio
from programas.selectors.edificios import (
    COMPARTIDO_NO,
    COMPARTIDO_SI,
    SITUACION_INACTIVOS,
    SITUACION_SIN_INSTITUCION,
    SITUACION_TODOS,
    edificios_visibles,
    filas_del_listado,
    filtrar_edificios,
    localidades_visibles,
    para_el_listado,
)
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura
from programas.tests.test_dispositivos_inspecciones import TODAS_DE_DISPOSITIVOS, Criticidad


class BaseEdificios(BaseInfraestructura):
    """Predio (parador + geriátrico), edificio del CIS, un huérfano y un inactivo del parador."""

    def setUp(self):
        super().setUp()
        self.admin = self._usuario("admin_edificios", (*TODAS_DE_DISPOSITIVOS, "edificio.ver"))
        self.huerfano = Edificio.objects.create(codigo="ED-HUERF", nombre="Huérfano")
        self.inactivo = Edificio.objects.create(codigo="ED-INACT", nombre="Inactivo", activo=False)
        self.inactivo.dispositivos.add(self.parador)
        self.del_parador = self._usuario("del_parador", ("edificio.ver",), [self.parador])
        self.red = self._usuario("red", ("edificio.ver", "dispositivo.ver_todos"))

    def _visibles(self, usuario, **kwargs):
        return set(edificios_visibles(self._fresco(usuario), **kwargs))


class AlcanceTests(BaseEdificios):
    def test_el_equipo_ve_solo_los_edificios_de_su_institucion(self):
        self.assertEqual(self._visibles(self.del_parador), {self.predio})

    def test_ver_todos_ve_los_vigentes_de_la_red(self):
        self.assertEqual(self._visibles(self.red), {self.predio, self.edificio_cis})

    def test_el_admin_ve_los_vigentes_por_defecto(self):
        self.assertEqual(self._visibles(self.admin), {self.predio, self.edificio_cis})

    def test_sin_edificio_ver_no_ve_ninguno_aunque_vea_dispositivos(self):
        solo_dispositivos = self._usuario("solo_disp", ("dispositivo.ver",), [self.parador])

        self.assertEqual(self._visibles(solo_dispositivos), set())


class SituacionTests(BaseEdificios):
    def test_el_admin_pide_cada_situacion(self):
        self.assertEqual(self._visibles(self.admin, situacion=SITUACION_SIN_INSTITUCION), {self.huerfano})
        self.assertEqual(self._visibles(self.admin, situacion=SITUACION_INACTIVOS), {self.inactivo})
        self.assertEqual(
            self._visibles(self.admin, situacion=SITUACION_TODOS),
            {self.predio, self.edificio_cis, self.huerfano, self.inactivo},
        )

    def test_quien_no_es_admin_nunca_ve_huerfanos_ni_inactivos(self):
        for usuario in (self.del_parador, self.red):
            for situacion in (SITUACION_SIN_INSTITUCION, SITUACION_INACTIVOS, SITUACION_TODOS):
                with self.subTest(usuario=usuario.username, situacion=situacion):
                    visibles = self._visibles(usuario, situacion=situacion)
                    self.assertNotIn(self.huerfano, visibles)
                    self.assertNotIn(self.inactivo, visibles)

    def test_una_situacion_desconocida_vale_como_vigentes(self):
        self.assertEqual(self._visibles(self.admin, situacion="cualquiera"), {self.predio, self.edificio_cis})


class FiltrosTests(BaseEdificios):
    def setUp(self):
        super().setUp()
        Edificio.objects.filter(pk=self.predio.pk).update(localidad="Resistencia", calle="Av. Sarmiento")
        Edificio.objects.filter(pk=self.edificio_cis.pk).update(localidad="Barranqueras")
        self.otro = Edificio.objects.create(codigo="ED-OTRO", nombre="Otro", localidad="Resistencia")
        self.otro.dispositivos.add(self.geriatrico)
        self._relevar(self.predio, Criticidad.MEDIA, dias_atras=10)
        self._relevar(self.predio, Criticidad.ALTA)
        self._relevar(self.edificio_cis, Criticidad.BAJA)

    def _filtrar(self, **filtros):
        return set(filtrar_edificios(edificios_visibles(self._fresco(self.admin)), **filtros))

    def test_busqueda_por_codigo_nombre_y_calle(self):
        self.assertEqual(self._filtrar(q="ed-cis"), {self.edificio_cis})
        self.assertEqual(self._filtrar(q="predio"), {self.predio})
        self.assertEqual(self._filtrar(q="sarmiento"), {self.predio})

    def test_localidad_exacta(self):
        self.assertEqual(self._filtrar(localidad="Resistencia"), {self.predio, self.otro})

    def test_cada_estado_sale_de_la_ultima_realizada(self):
        self.assertEqual(self._filtrar(estado="CRITICO"), {self.predio})
        self.assertEqual(self._filtrar(estado="REGULAR"), set())
        self.assertEqual(self._filtrar(estado="BUENO"), {self.edificio_cis})
        self.assertEqual(self._filtrar(estado="SIN_RELEVAR"), {self.otro})

    def test_compartido(self):
        self.assertEqual(self._filtrar(compartido=COMPARTIDO_SI), {self.predio})
        self.assertEqual(self._filtrar(compartido=COMPARTIDO_NO), {self.edificio_cis, self.otro})

    def test_combinados(self):
        self.assertEqual(self._filtrar(localidad="Resistencia", estado="SIN_RELEVAR"), {self.otro})
        self.assertEqual(self._filtrar(localidad="Resistencia", compartido=COMPARTIDO_SI, q="predio"), {self.predio})

    def test_un_valor_desconocido_no_filtra(self):
        todos = {self.predio, self.edificio_cis, self.otro}
        self.assertEqual(self._filtrar(estado="OTRO"), todos)
        self.assertEqual(self._filtrar(compartido="tal vez"), todos)

    def test_las_localidades_son_las_del_alcance(self):
        self.assertEqual(localidades_visibles(self._fresco(self.admin)), ["Barranqueras", "Resistencia"])
        self.assertEqual(localidades_visibles(self._fresco(self.del_parador)), ["Resistencia"])


class FilasTests(BaseEdificios):
    def _filas(self, usuario, queryset=None):
        usuario = self._fresco(usuario)
        return {
            fila["pk"]: fila
            for fila in filas_del_listado(usuario, para_el_listado(queryset or edificios_visibles(usuario)))
        }

    def test_instituciones_fuera_de_alcance_se_cuentan_sin_nombre(self):
        fila = self._filas(self.del_parador)[self.predio.pk]

        self.assertEqual([i["nombre"] for i in fila["instituciones"]], ["Parador"])
        self.assertEqual(fila["otras"], 1)
        self.assertTrue(fila["compartido"])

    def test_el_enlace_va_solo_si_puede_abrir_la_institucion(self):
        sin_ver = self._filas(self.del_parador)[self.predio.pk]["instituciones"][0]
        con_ver = self._usuario("con_ver", ("edificio.ver", "dispositivo.ver"), [self.parador])
        abrible = self._filas(con_ver)[self.predio.pk]["instituciones"][0]

        self.assertEqual(sin_ver["url"], "")
        self.assertTrue(abrible["url"].endswith(f"/dispositivos/{self.parador.pk}/"))

    def test_estado_y_fecha_de_la_ultima(self):
        inspeccion = self._relevar(self.predio, Criticidad.ALTA)
        filas = self._filas(self.admin)

        self.assertEqual(filas[self.predio.pk]["estado"]["clave"], "CRITICO")
        self.assertEqual(filas[self.predio.pk]["ultima_fecha"], inspeccion.realizada_en)
        self.assertEqual(filas[self.edificio_cis.pk]["estado"]["clave"], "SIN_RELEVAR")
        self.assertIsNone(filas[self.edificio_cis.pk]["ultima_fecha"])

    def test_url_asignar_solo_para_quien_coordina_un_edificio_libre(self):
        coordinador = self._usuario("coord_edif", ("edificio.ver", "inspeccion.asignar"), [self.parador])

        self.assertIn(f"?asignar={self.predio.pk}", self._filas(coordinador)[self.predio.pk]["url_asignar"])
        self.assertEqual(self._filas(self.del_parador)[self.predio.pk]["url_asignar"], "")
        self._crear()  # el predio queda con un relevamiento en curso
        self.assertEqual(self._filas(coordinador)[self.predio.pk]["url_asignar"], "")

    def test_misma_cantidad_de_consultas_con_2_y_con_20_edificios(self):
        def medir():
            usuario = self._fresco(self.admin)
            pagina = list(para_el_listado(edificios_visibles(usuario)))
            with CaptureQueriesContext(connection) as consultas:
                filas_del_listado(usuario, pagina)
            return len(pagina), len(consultas)

        # Con al menos una realizada, para que las dos mediciones incluyan la consulta de las últimas.
        self._relevar(self.predio, Criticidad.MEDIA)
        filas_antes, consultas_antes = medir()
        for numero in range(18):
            edificio = Edificio.objects.create(codigo=f"ED-N{numero}", nombre=f"Nuevo {numero}")
            edificio.dispositivos.add(self.cis, self.geriatrico)
            if numero % 2:
                self._relevar(edificio, Criticidad.BAJA)
        filas_despues, consultas_despues = medir()

        self.assertEqual((filas_antes, filas_despues), (2, 20))
        self.assertEqual(consultas_antes, consultas_despues)
