"""Las tres acepciones de «cupo disponible» (RED-49), ya renombradas.

En el repo había **tres** cosas distintas que se llamaban `cupo_disponible`, y dos
pantallas las rotulaban igual. La Ola 4 renombró —no unificó—, así que hoy cada una
dice lo que es:

1. `Segmento.cupo_sin_distribuir` — el cupo del segmento **todavía no repartido**
   entre sus subsegmentos (`cupo_maximo - cupo_distribuido`). Lo muestra
   `becas/config/segmento_detail.html` y lo valida `subsegmento_form.html`.
2. `get_cupo_stats(segmento)["cupo_disponible"]` — los **lugares libres reales**
   (`cupo_maximo - formularios APROBADO`). Lo muestra `becas/cupo/segmento_detail.html`.
   Es el único que conserva el nombre viejo.
3. `Relevamiento.cupos_libres_del_relevamiento` — lo que le queda **a ese
   relevamiento** de su propio tope (`cupo_maximo - cupo_utilizado`). La app de campo
   lo sigue leyendo como `cupo_disponible`: el campo de la API no cambió, solo la
   property (ver `test_becas_api_contrato.py`).

Siguen sin ser sinónimos y siguen sin poder unificarse: «limpiar» la property contra
`get_cupo_stats` cambia el número de la pantalla de configuración y la validación del
alta de subsegmentos. Este test fija los tres números con sus nombres nuevos.
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
            self.segmento.cupo_sin_distribuir,
            3,
            "`Segmento.cupo_sin_distribuir` es el cupo sin repartir en subsegmentos (10 - 3 - 4).",
        )
        self.assertEqual(
            get_cupo_stats(self.segmento)["cupo_disponible"],
            4,
            "`get_cupo_stats` son los lugares libres reales: 10 menos los 6 aprobados.",
        )
        self.assertEqual(
            self.relevamiento.cupos_libres_del_relevamiento,
            2,
            "`cupos_libres_del_relevamiento` cuenta sus casos contra su propio tope (8 - 6).",
        )
        # Las tres difieren entre sí: si alguna «unificación» las iguala, acá se ve.
        self.assertEqual(
            len({self.segmento.cupo_sin_distribuir, get_cupo_stats(self.segmento)["cupo_disponible"]}),
            2,
            "Alguien unificó las dos acepciones del segmento: hay que renombrar, no unificar.",
        )

    def test_ninguna_de_las_tres_acepciones_se_llama_ya_cupo_disponible(self):
        """El renombre en sí (RED-49, parte Ola 4). Si alguien reintroduce la property
        —por ejemplo como alias de compatibilidad—, vuelve la ambigüedad que la ficha
        describe: dos pantallas que muestran números distintos bajo el mismo nombre."""
        self.assertFalse(hasattr(self.segmento, "cupo_disponible"))
        self.assertFalse(hasattr(self.relevamiento, "cupo_disponible"))
        self.assertIn("cupo_disponible", get_cupo_stats(self.segmento))

    def test_el_contador_de_cuposegmento_no_lo_mueve_nadie(self):
        """`CupoSegmento.cupo_ocupado` es un contador que ninguna escritura
        actualiza —el ocupado se cuenta dinámicamente desde el Cambio 24— y, sin
        embargo, `Segmento.clean()` valida el cupo máximo contra él. Queda
        fijado: el día que algo lo empiece a mover, `clean()` cambia de
        comportamiento y este test lo avisa."""
        cupo = CupoSegmento.objects.create(segmento=self.segmento)

        self.assertEqual(cupo.cupo_ocupado, 0)
        self.assertEqual(get_cupo_stats(self.segmento)["cupo_ocupado"], 6)
