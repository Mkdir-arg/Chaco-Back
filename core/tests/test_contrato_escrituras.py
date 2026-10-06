"""Las escrituras críticas siguen siendo atómicas (RED-35).

Hay 39 `@transaction.atomic` en los `services/` del repo y **ninguno** estaba
afirmado por un test. El Cambio 58 registra que el decorador de
`resolver_ciudadano_offline` ya se perdió una vez, al extraer `_completar_contacto`
a su propia función: mover una escritura de módulo sin llevarse el decorador no
rompe ningún test, y en producción deja un ciudadano creado con el formulario sin
tocar —un legajo duplicado que nadie pidió—.

**La prueba es conductual, no introspectiva.** Afirmar la atomicidad con
`getattr(fn, "_atomic", False)` no sirve: `transaction.atomic` usa `@wraps` y no
deja ese atributo, así que la aserción da siempre `False`; y buscar la palabra
«atomic» en el fuente da verde con un comentario. Lo que se hace acá es hacer
fallar un paso intermedio y mirar que **no quedó nada escrito**.

Ola 3: el mismo patrón para `cupo.aprobar_formulario`,
`inscripcion_publica.crear_formulario_publico`, `padron.quitar_padron_propio` y
`admisiones.trasladar_admision`. El gemelo contra el motor de producción —donde
el rollback es un `ROLLBACK` de verdad y no un savepoint de SQLite— está en
`core/tests/test_motor_real.py::EscriturasAtomicasMotorRealTests`.
"""

from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from legajos.models import Ciudadano
from programas.models import Convocatoria, Formulario, Relevamiento, Segmento
from programas.services.becas import resolver_ciudadano_offline

#: El caso llega por sync offline: sin legajo y con la identidad en el JSON.
DNI = "41222333"
IDENTIFICACION = {"dni": DNI, "nombre": "Lucía", "apellido": "Paz", "sexo": "F"}


class EscriturasAtomicasTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg atomic", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv atomic",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=User.objects.create_user("terri_atomic", password="x"),
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        self.formulario = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624555666",
            email_contacto="lucia@correo.com",
            datos_identificacion=dict(IDENTIFICACION),
        )

    def test_resolver_ciudadano_offline_no_deja_nada_a_medias(self):
        """Si falla un paso posterior al alta del legajo, el legajo no queda.

        `_completar_contacto` corre **después** del `get_or_create` del
        `Ciudadano` y antes de guardar el formulario: hacerlo explotar deja el
        caso justo en el medio. Sin `@transaction.atomic` sobre
        `resolver_ciudadano_offline` el ciudadano queda creado y el formulario
        sigue apuntando a su `datos_identificacion`: la próxima sincronización
        vuelve a entrar por el mismo camino y el duplicado nunca se ve.
        """
        with patch(
            "programas.services.becas._completar_contacto",
            side_effect=RuntimeError("se cayó el paso siguiente"),
        ):
            with self.assertRaises(RuntimeError):
                resolver_ciudadano_offline(self.formulario)

        self.assertFalse(
            Ciudadano.objects.filter(dni=DNI).exists(),
            "Quedó un legajo creado por una escritura que falló: `resolver_ciudadano_offline` "
            "perdió su `@transaction.atomic` (ya pasó una vez, Cambio 58).",
        )
        self.formulario.refresh_from_db()
        self.assertIsNone(self.formulario.ciudadano_id)
        self.assertEqual(self.formulario.datos_identificacion, IDENTIFICACION)

    def test_resolver_ciudadano_offline_sin_fallas_si_escribe(self):
        """Control: sin la falla inyectada la escritura sí ocurre, entera.

        Sin este par, cualquier cambio que dejara la función sin hacer nada
        pondría el test de arriba en verde por el motivo equivocado.
        """
        ciudadano = resolver_ciudadano_offline(self.formulario)

        self.assertIsNotNone(ciudadano)
        self.assertEqual(ciudadano.dni, DNI)
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.ciudadano_id, ciudadano.pk)
        self.assertIsNone(self.formulario.datos_identificacion)
        self.assertEqual(ciudadano.telefono, "3624555666")
