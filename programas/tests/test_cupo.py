"""Las tres acepciones de «cupo disponible» (RED-49).

En el repo hay **tres** cosas distintas que se llaman `cupo_disponible`, y dos
pantallas las rotulan igual:

1. `Segmento.cupo_disponible` — el cupo del segmento **todavía no repartido**
   entre sus subsegmentos (`cupo_maximo - cupo_distribuido`). Lo muestra
   `becas/config/segmento_detail.html` y lo valida `subsegmento_form.html`.
2. `get_cupo_stats(segmento)["cupo_disponible"]` — los **lugares libres reales**
   (`cupo_maximo - formularios APROBADO`). Lo muestra `becas/cupo/segmento_detail.html`.
3. `Relevamiento.cupo_disponible` — lo que le queda **a ese relevamiento** de su
   propio tope de casos (`cupo_maximo - cupo_utilizado`); lo lee la app de campo.

No son sinónimos y no se pueden unificar al pasar: «limpiar» la property contra
`get_cupo_stats` cuando se haga PERF-02 cambia el número de la pantalla de
configuración y la validación del alta de subsegmentos. Este test fija los tres
números con los nombres de hoy; **Ola 4** renombra (`cupo_sin_distribuir`,
`cupos_libres_del_relevamiento`, y `cupo_disponible` queda solo para
`get_cupo_stats`) y actualiza este test.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from programas.models import (
    Convocatoria,
    CupoSegmento,
    Formulario,
    Relevamiento,
    Segmento,
    Subsegmento,
)
from programas.services.cupo import get_cupo_stats


class TresCuposTests(TestCase):
    def setUp(self):
        # 10 de cupo, 7 repartidos en dos subsegmentos y 6 lugares ocupados.
        self.segmento = Segmento.objects.create(nombre="Seg cupos", cupo_maximo=10)
        Subsegmento.objects.create(segmento=self.segmento, nombre="Sub A", cupo_maximo=3)
        Subsegmento.objects.create(segmento=self.segmento, nombre="Sub B", cupo_maximo=4)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv cupos",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=User.objects.create_user("terri_cupos", password="x"),
            fecha_asignada=date(2026, 6, 1),
            zona="A",
            cupo_maximo=8,
        )
        for numero in range(6):
            Formulario.objects.create(
                relevamiento=self.relevamiento,
                celular=f"362400000{numero}",
                estado=Formulario.Estado.APROBADO,
            )

    def test_las_tres_acepciones_son_distintas(self):
        self.assertEqual(
            self.segmento.cupo_disponible,
            3,
            "`Segmento.cupo_disponible` es el cupo sin distribuir en subsegmentos (10 - 3 - 4).",
        )
        self.assertEqual(
            get_cupo_stats(self.segmento)["cupo_disponible"],
            4,
            "`get_cupo_stats` son los lugares libres reales: 10 menos los 6 aprobados.",
        )
        self.assertEqual(
            self.relevamiento.cupo_disponible,
            2,
            "`Relevamiento.cupo_disponible` cuenta sus casos contra su propio tope (8 - 6).",
        )
        # Las tres difieren entre sí: si alguna «unificación» las iguala, acá se ve.
        self.assertEqual(
            len({self.segmento.cupo_disponible, get_cupo_stats(self.segmento)["cupo_disponible"]}),
            2,
            "Alguien unificó las dos acepciones del segmento: PERF-02 tiene que renombrar, no unificar.",
        )

    def test_el_contador_de_cuposegmento_no_lo_mueve_nadie(self):
        """`CupoSegmento.cupo_ocupado` es un contador que ninguna escritura
        actualiza —el ocupado se cuenta dinámicamente desde el Cambio 24— y, sin
        embargo, `Segmento.clean()` valida el cupo máximo contra él. Queda
        fijado: el día que algo lo empiece a mover, `clean()` cambia de
        comportamiento y este test lo avisa."""
        cupo = CupoSegmento.objects.create(segmento=self.segmento)

        self.assertEqual(cupo.cupo_ocupado, 0)
        self.assertEqual(get_cupo_stats(self.segmento)["cupo_ocupado"], 6)
