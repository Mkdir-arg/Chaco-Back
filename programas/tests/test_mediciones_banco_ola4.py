"""PERF-12, PERF-13 y PERF-15 · Las tres fichas que se cerraron midiendo, sin cambiar código.

Las tres pedían lo mismo: **medir primero en el banco MariaDB y recién ahí decidir**. La
medición (banco `scripts/perf_mysql/`, MariaDB 10.11, `OPTIONS` de producción, el
relevamiento público llevado a 40.000 casos y el padrón de la convocatoria a 50.000 y
100.000 filas) dijo que ninguna necesita cambio:

* **PERF-12** · `COUNT(*) … WHERE relevamiento_id = X` con 40.000 casos: **7,0-8,4 ms**,
  resuelto con `Using index`. El criterio del Cambio 91 era no denormalizar debajo de
  20 ms.
* **PERF-13** · la bandeja filtrada por un estado **raro** (400 de 40.000 en `BAJA`),
  página 10: **2,4-4,9 ms**. El índice de `estado` la resuelve a las 400 filas exactas y
  el `filesort` ordena esas 400. El índice combinado que la ficha proponía se probó en el
  banco en dos rondas A/B pareadas: no mejora nada medible y el motor directamente **no
  lo elige** en el caso caro.
* **PERF-15** · los conteos del padrón en los dos detalles: **23-48 ms** con 50.000 y con
  100.000 filas. Denormalizar agregaría un contador que se puede desincronizar para
  ahorrar milésimas contra un `read_timeout` de 10 s.

Una medición no es un test, y estas fichas igual pueden romperse: lo que las sostiene son
**premisas del código**, y eso sí se puede fijar. Este módulo fija las tres:

1. que el `count` del cupo siga filtrando por `relevamiento_id` solo (lo que lo hace
   `ref` sobre índice);
2. que la bandeja siga teniendo la forma que el índice de `estado` puede usar —columna
   desnuda en el `WHERE`, proyección de solo el pk— y que los dos índices de los que
   depende la medición sigan declarados;
3. que los conteos del padrón sigan saliendo en **una** consulta por pantalla, que es lo
   que impide que esos 23-48 ms se multipliquen.

El detalle de las mediciones está en `docs/internal/auditoria-2026-10/hallazgos/04-performance.md`
y se reproducen con `scripts/perf_mysql/medir_consultas_borde.py`.
"""

from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import Convocatoria, Formulario, PadronHabilitado, Relevamiento, Segmento
from programas.tests.base_becas import BecasPantallaTestCase


class _BaseMedicion(BecasPantallaTestCase):
    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        # Superusuario a propósito: lo que estos tests miran es la **forma** de la
        # consulta, no quién puede verla. El alcance por capacidad —incluido el de los
        # relevamientos públicos— tiene sus propios módulos.
        self.admin = User.objects.create_superuser("admin_perf_banco", "a@perf.test", "x")
        self.client.force_login(self.admin)
        self.segmento = Segmento.objects.create(nombre="Seg banco", cupo_maximo=1000)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv banco",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
            cupo_maximo=1000,
        )

    def sql_de(self, fn):
        with CaptureQueriesContext(connection) as capturadas:
            fn()
        return [q["sql"] for q in capturadas.captured_queries]


class CupoDelLinkPublicoTests(_BaseMedicion):
    """PERF-12 · El `count` del cupo se resuelve por índice, y por eso se queda."""

    def test_el_count_del_cupo_filtra_solo_por_relevamiento(self):
        """Lo que lo hace `ref=const` + `Using index` en MariaDB.

        Agregarle una condición más (un `estado`, una fecha) lo saca de
        `uniq_formulario_numero_relevamiento` y los 7 ms medidos con 40.000 casos dejan
        de valer: ahí la ficha habría que reabrirla.
        """
        consultas = self.sql_de(lambda: self.relevamiento.cupo_utilizado)

        self.assertEqual(len(consultas), 1)
        sql = consultas[0]
        self.assertIn("COUNT(*)", sql)
        self.assertIn("relevamiento_id", sql)
        self.assertNotIn("estado", sql)
        self.assertNotIn("JOIN", sql.upper())

    def test_el_cupo_anotado_no_vuelve_a_contar(self):
        """El otro camino: cuando la vista ya trajo el conteo anotado, la property no
        consulta. Si consultara, cada fila de un listado pagaría este `count`."""
        self.relevamiento.formularios_count = 7

        self.assertEqual(self.sql_de(lambda: self.relevamiento.cupo_utilizado), [])


class BandejaFiltradaPorEstadoTests(_BaseMedicion):
    """PERF-13 · La forma de la consulta es lo que hace innecesario el índice nuevo."""

    #: Los dos índices de los que depende la medición. `estado` resuelve el recorte a las
    #: filas del estado raro; `creado` sostiene la bandeja sin filtro.
    INDICES_QUE_SOSTIENEN_LA_MEDICION = (("estado",), ("creado",))

    def setUp(self):
        super().setUp()
        for n in range(3):
            Formulario.objects.create(
                relevamiento=self.relevamiento, numero=n + 1, estado=Formulario.Estado.BAJA
            )

    def test_la_bandeja_filtra_por_la_columna_desnuda_y_proyecta_solo_el_pk(self):
        """Sin función sobre la columna (gotcha de MariaDB) y sin traer la fila ancha.

        Las dos cosas juntas son las que dejan el plan en `ref` sobre el índice de
        `estado` con un `filesort` de 400 filas, que es lo que se midió en 2,4 ms.
        """
        url = reverse("becas:revision")
        consultas = self.sql_de(
            lambda: self.assertEqual(self.client.get(url, {"estado": Formulario.Estado.BAJA}).status_code, 200)
        )
        # La consulta de la página: la que recorta por estado y por los relevamientos
        # visibles. Las otras que tocan la tabla son el COUNT del paginador y la
        # hidratación por pk de las 25 filas que se muestran.
        de_la_bandeja = [
            s
            for s in consultas
            if "programas_formulario" in s and "COUNT" not in s and "relevamiento_id` IN (" in s.replace('"', "`")
        ]

        self.assertEqual(len(de_la_bandeja), 1, "la bandeja no consultó los casos una sola vez")
        sql = de_la_bandeja[0].replace('"', "`")
        self.assertIn("`estado` = ", sql)
        self.assertNotIn("UPPER(", sql.upper())
        # `only("pk")`: ni la foto de la definición ni las respuestas entran en la página.
        self.assertNotIn("definicion", sql)
        self.assertNotIn("respuestas", sql)

    def test_siguen_declarados_los_indices_sobre_los_que_se_midio(self):
        """El índice combinado de la ficha no entró **porque estos dos ya alcanzan**.

        Si alguien saca uno, la medición deja de aplicar y PERF-13 vuelve a estar
        abierta: este test es el aviso.
        """
        declarados = {tuple(indice.fields) for indice in Formulario._meta.indexes}

        for campos in self.INDICES_QUE_SOSTIENEN_LA_MEDICION:
            self.assertIn(campos, declarados, f"falta el índice {campos} sobre programas_formulario")

    def test_la_tabla_grande_no_estreno_un_indice_mas(self):
        """`programas_formulario` es la tabla más grande: cada índice se paga en cada
        alta. La medición dijo que el de `(estado, creado, relevamiento)` no se usa."""
        declarados = {tuple(indice.fields) for indice in Formulario._meta.indexes}

        self.assertNotIn(("estado", "creado", "relevamiento"), declarados)


class ConteosDelPadronTests(_BaseMedicion):
    """PERF-15 · Los conteos del padrón salen en una consulta por pantalla."""

    def setUp(self):
        super().setUp()
        PadronHabilitado.objects.bulk_create(
            [
                PadronHabilitado(
                    convocatoria=self.convocatoria,
                    dni=f"7{n:07d}",
                    sexo="F" if n % 2 else "M",
                    nombre="Nombre" if n % 2 else "",
                    apellido=f"Apellido{n}" if n % 2 else "",
                )
                for n in range(20)
            ]
        )

    def _consultas_al_padron(self, url):
        consultas = self.sql_de(lambda: self.assertEqual(self.client.get(url).status_code, 200))
        return [s for s in consultas if "programas_padronhabilitado" in s]

    def test_el_detalle_de_convocatoria_cuenta_el_padron_una_sola_vez(self):
        """Los tres números (total, con identidad y relevamientos con padrón propio)
        salen del mismo `aggregate`: 43 ms con 50.000 filas, y uno solo."""
        url = reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])

        self.assertEqual(len(self._consultas_al_padron(url)), 1)

    def test_el_detalle_de_relevamiento_cuenta_el_padron_en_la_consulta_del_relevamiento(self):
        """Los dos niveles —propio y heredado— van anotados en la **misma** consulta que
        trae el relevamiento: el padrón no suma ninguna lectura propia."""
        url = reverse("becas:relevamiento_detalle", args=[self.relevamiento.pk])

        al_padron = self._consultas_al_padron(url)
        self.assertEqual(len(al_padron), 1)
        self.assertIn("programas_relevamiento", al_padron[0])

    def test_los_conteos_no_crecen_con_el_tamano_del_padron(self):
        """Lo que importa no es cuánto tarda sino que sea **una** consulta: con un
        padrón 10× más grande tiene que seguir siendo la misma cantidad."""
        url = reverse("becas:convocatoria_detalle", args=[self.convocatoria.pk])
        self.client.get(url)  # primera visita: sesión y Profile
        con_pocas = len(self._consultas_al_padron(url))
        PadronHabilitado.objects.bulk_create(
            [
                PadronHabilitado(convocatoria=self.convocatoria, dni=f"8{n:07d}", sexo="M")
                for n in range(200)
            ]
        )

        self.assertEqual(len(self._consultas_al_padron(url)), con_pocas)
