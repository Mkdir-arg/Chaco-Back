"""La pantalla de cupo pagina por pk y no abre los JSON del caso (PERF-02).

Medido contra el banco MariaDB 10.11 de `scripts/perf_mysql` con 20.000 casos en el
segmento y las `OPTIONS` de producción: la página costaba **8,99 s de SQL** —con el
`read_timeout` de ECOM en 10 s—. Las tres tablas traían las cinco columnas JSON del
formulario (~7 KB por fila) y ordenaban por una columna sin índice, así que MariaDB
arrancaba el plan por `programas_convocatoria` con «Using temporary; Using filesort» y
materializaba `programas_relevamiento` antes de recortar. Después: 167 ms.

Lo que se fija acá —lo que no puede volver a pasar ni cambiar sin que se note—:

1. La página **no pide** los cinco JSON.
2. La cantidad de consultas no crece con la cantidad de casos.
3. Los casos de la página son **los mismos y en el mismo orden** que con la consulta
   ancha anterior (`_pagina_a_la_vieja`, copia congelada del queryset de entonces).
"""

import re
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from legajos.models import Ciudadano
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import Convocatoria, Formulario, ListaEspera, Relevamiento, Segmento
from programas.tests.base_becas import BecasPantallaTestCase

JSON_DEL_CASO = ("definicion", "respuestas", "datos_siis", "datos_identificacion")


def _pagina_a_la_vieja(segmento, estado, orden, en_espera_fuera=False):
    """El queryset de página anterior a PERF-02: ancho, con los joins adentro.

    Se conserva como referencia de resultado (no de plan): los pks que devolvía son los
    que la pantalla tiene que seguir mostrando.
    """
    qs = Formulario.objects.filter(
        estado=estado,
        ciudadano__isnull=False,
        relevamiento__convocatoria__segmento=segmento,
    )
    if en_espera_fuera:
        qs = qs.exclude(
            pk__in=ListaEspera.objects.filter(segmento=segmento, promovido=False).values_list(
                "formulario_id", flat=True
            )
        )
    return list(
        qs.select_related("ciudadano", "relevamiento__convocatoria")
        .defer("data", "datos_identificacion")
        .order_by(orden)
        .values_list("pk", flat=True)
    )


class _BaseCupo(BecasPantallaTestCase):
    """Un segmento con **dos** relevamientos y casos en lista de espera."""

    def setUp(self):
        super().setUp()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin_cupo_perf", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(self.admin)
        self.segmento = Segmento.objects.create(nombre="Seg cupo perf", cupo_maximo=10_000)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv cupo perf",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        territorial = User.objects.create_user("terri_cupo_perf", password="x")
        self.relevamientos = [
            Relevamiento.objects.create(
                convocatoria=self.convocatoria,
                territorial=territorial,
                fecha_asignada=timezone.now() - timedelta(days=2),
                fecha_hasta=timezone.now() + timedelta(days=10),
                zona=f"Zona {i}",
                cupo_maximo=10_000,
            )
            for i in range(2)
        ]
        self.url = reverse("becas:cupo_segmento", args=[self.segmento.pk])

    def _caso(self, indice, estado, momento):
        """Un caso con `creado`/`modificado` **distintos** entre sí: el orden de la
        pantalla tiene que quedar determinado por los datos y no por el motor."""
        ciudadano = Ciudadano.objects.create(
            dni=f"{35_000_000 + indice}", nombre=f"N{indice}", apellido="Paz", genero="F"
        )
        caso = Formulario.objects.create(
            relevamiento=self.relevamientos[indice % 2],
            ciudadano=ciudadano,
            celular="3624000000",
            email_contacto=f"c{indice}@b.invalid",
            estado=estado,
        )
        Formulario.objects.filter(pk=caso.pk).update(creado=momento, modificado=momento)
        caso.refresh_from_db()
        return caso

    def _poblar(self, cantidad, desde=0):
        base = timezone.now() - timedelta(days=60)
        aprobados, enviados = [], []
        for indice in range(desde, desde + cantidad):
            momento = base + timedelta(minutes=indice)
            aprobados.append(self._caso(2 * indice, Formulario.Estado.APROBADO, momento))
            enviados.append(self._caso(2 * indice + 1, Formulario.Estado.ENVIADO, momento))
        return aprobados, enviados


class LaPaginaNoAbreLosJsonTests(_BaseCupo):
    def test_ninguna_consulta_de_la_pantalla_pide_los_cinco_json(self):
        self._poblar(3)

        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.status_code, 200)
        del_caso = [q["sql"] for q in capturadas.captured_queries if "programas_formulario" in q["sql"]]
        self.assertTrue(del_caso, "la pantalla dejó de consultar programas_formulario")
        for sql in del_caso:
            for columna in JSON_DEL_CASO:
                self.assertNotIn(
                    f'"{columna}"',
                    sql,
                    f"la pantalla de cupo volvió a pedir `{columna}`: son ~7 KB por fila y nadie los lee",
                )

    def test_la_pagina_se_elige_sin_join_con_relevamiento(self):
        """La raíz del plan malo: con el join adentro, MariaDB materializaba todos los
        casos del segmento antes de ordenar. El alcance baja a una lista de ids."""
        self._poblar(3)

        with CaptureQueriesContext(connection) as capturadas:
            self.client.get(self.url)

        paginas = [
            q["sql"]
            for q in capturadas.captured_queries
            if "programas_formulario" in q["sql"] and "LIMIT" in q["sql"] and "programas_listaespera" not in q["sql"]
        ]
        self.assertTrue(paginas)
        for sql in paginas:
            self.assertNotIn("programas_convocatoria", sql)
            self.assertRegex(sql, re.compile(r"relevamiento_id.{0,2}\s+IN\s"))


class ConsultasConstantesTests(_BaseCupo):
    def _consultas(self, cantidad, desde=0):
        self._poblar(cantidad, desde=desde)
        # Una pasada en vacío: la primera pantalla de Becas del proceso calienta la
        # caché del Programa (`programas:becas`) y mide dos consultas de más.
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        return len(capturadas.captured_queries)

    def test_la_pantalla_no_crece_con_la_cantidad_de_casos(self):
        con_5 = self._consultas(5)
        con_25 = self._consultas(20, desde=5)  # 25 en total: los 5 anteriores siguen ahí

        self.assertEqual(
            con_5,
            con_25,
            f"la pantalla pasó de {con_5} a {con_25} consultas al quintuplicar los casos",
        )


class MismosCasosEnElMismoOrdenTests(_BaseCupo):
    """El resultado no cambia: mismos pks, mismo orden, misma página."""

    def setUp(self):
        super().setUp()
        aprobados, enviados = self._poblar(60)
        # Dos pendientes en lista de espera: no tienen que aparecer entre los pendientes.
        for posicion, caso in enumerate(enviados[:2], start=1):
            ListaEspera.objects.create(segmento=self.segmento, formulario=caso, posicion=posicion)
        self.aprobados = aprobados

    def _pks_de_la_pagina(self, clave, pagina):
        respuesta = self.client.get(self.url, {f"{clave}_page": pagina})
        self.assertEqual(respuesta.status_code, 200)
        contexto = respuesta.context[clave]
        return [obj.pk for obj in contexto.object_list], contexto.paginator.count

    def test_beneficiarios_pagina_2_igual_que_con_la_consulta_ancha(self):
        esperados = _pagina_a_la_vieja(self.segmento, Formulario.Estado.APROBADO, "modificado")

        pks, total = self._pks_de_la_pagina("beneficiarios", 2)

        self.assertEqual(total, len(esperados))
        self.assertEqual(pks, esperados[50:100])

    def test_pendientes_pagina_1_saltea_la_lista_de_espera_igual_que_antes(self):
        esperados = _pagina_a_la_vieja(self.segmento, Formulario.Estado.ENVIADO, "creado", en_espera_fuera=True)

        pks, total = self._pks_de_la_pagina("pendientes", 1)

        self.assertEqual(total, 58, "los dos casos en lista de espera no son pendientes")
        self.assertEqual(total, len(esperados))
        self.assertEqual(pks, esperados[:50])

    def test_la_lista_de_espera_conserva_su_orden_por_posicion(self):
        respuesta = self.client.get(self.url, {"lista_espera_page": 1})

        entradas = list(respuesta.context["lista_espera"].object_list)
        self.assertEqual([e.posicion for e in entradas], [1, 2])

    def test_los_contadores_son_los_de_siempre(self):
        respuesta = self.client.get(self.url)

        self.assertEqual(respuesta.context["n_beneficiarios"], 60)
        self.assertEqual(respuesta.context["n_pendientes"], 58)
        self.assertEqual(respuesta.context["n_lista_espera"], 2)
        # El cupo ocupado se sigue midiendo sobre el segmento entero (no sobre el
        # alcance del usuario): es el cupo, no una bandeja.
        self.assertEqual(respuesta.context["stats"]["cupo_ocupado"], 60)
