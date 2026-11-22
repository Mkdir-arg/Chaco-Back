"""Desvincular un edificio no puede dejar a nadie del Equipo con alcance por edificio y cero edificios (Cambio 551).

Con alcance Edificios, un alcance sin edificios vigentes no ve nada (Cambio 523, decisión 7) y nadie se entera.
La regla vive en `edificios.desvincular_edificio`: se rechaza nombrando a las personas, o se le quita a cada
miembro solo ese edificio de su alcance, todo en la misma transacción.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from programas.models import MiembroEquipoDispositivo, TrazaDispositivo
from programas.services import equipo_dispositivo as equipo
from programas.services.edificios import desvincular_edificio
from programas.tests.test_equipo_alcance_edificio import Alcance, BaseAlcance

AJAX = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}


class _Base(BaseAlcance):
    def setUp(self):
        super().setUp()
        # A y B tienen sectores activos (el servicio ya los protege); C no tiene ninguno.
        self.edif_c = self._edificio("ED-C")
        self.actor = User.objects.get(pk=self.de_inst.pk)
        self.admin_equipo = User.objects.create_superuser(username="super_equipo", password="x")

    def _desvincular(self, edificio=None):
        return desvincular_edificio(edificio=edificio or self.edif_c, dispositivo=self.cis, usuario=self.actor)

    def _fila(self, usuario):
        return MiembroEquipoDispositivo.objects.get(usuario=usuario, dispositivo=self.cis)

    def _ids(self, usuario):
        return set(self._fila(usuario).edificios.values_list("pk", flat=True))

    def _vinculado(self, edificio=None):
        return self.cis.edificios.filter(pk=(edificio or self.edif_c).pk).exists()

    def _rechazada(self, edificio=None):
        trazas = TrazaDispositivo.objects.count()
        with self.assertRaises(ValidationError) as error:
            self._desvincular(edificio)
        self.assertTrue(self._vinculado(edificio))
        self.assertEqual(TrazaDispositivo.objects.count(), trazas)
        return error.exception.message_dict["__all__"][0]


class RegeTests(_Base):
    def test_el_unico_edificio_de_un_miembro_bloquea_y_nombra_a_la_persona(self):
        solo_c = self._miembro("Solo en C", Alcance.EDIFICIOS, [self.edif_c])

        mensaje = self._rechazada()

        self.assertIn("Lucía Méndez", mensaje)
        self.assertEqual(self._ids(solo_c), {self.edif_c.pk})

    def test_le_quedan_otros_edificios_se_desvincula_y_se_le_quita_solo_ese(self):
        a_y_c = self._miembro("En A y C", Alcance.EDIFICIOS, [self.edif_a, self.edif_c])

        self._desvincular()

        self.assertFalse(self._vinculado())
        self.assertEqual(self._ids(a_y_c), {self.edif_a.pk})
        self.assertEqual(self._ids(self.de_a), {self.edif_a.pk})

    def test_el_otro_edificio_ya_desvinculado_no_cuenta_como_vigente(self):
        # Un alcance con un edificio huérfano (ya no vinculado) sigue sin ver nada: no puede salvar al miembro.
        huerfano = self._edificio("ED-H")
        c_y_huerfano = self._miembro("En C y huerfano", Alcance.EDIFICIOS, [self.edif_c, huerfano])
        self.cis.edificios.remove(huerfano)

        self._rechazada()

        self.assertEqual(self._ids(c_y_huerfano), {self.edif_c.pk, huerfano.pk})

    def test_inactivo_o_de_baja_no_bloquea(self):
        baja = self._miembro("De baja", Alcance.EDIFICIOS, [self.edif_c])
        MiembroEquipoDispositivo.objects.filter(usuario=baja).update(activo=False)

        self._desvincular()

        self.assertFalse(self._vinculado())
        self.assertEqual(self._ids(baja), set())

    def test_alcance_institucion_o_sin_alcance_no_le_afecta(self):
        sin_alcance = self._miembro("Sin alcance", Alcance.INSTITUCION)
        MiembroEquipoDispositivo.objects.filter(usuario=sin_alcance).update(alcance=None)
        # Una fila con edificios cargados pero alcance Institución: los edificios no cuentan.
        self._fila(self.de_inst).edificios.set([self.edif_c])

        self._desvincular()

        self.assertFalse(self._vinculado())

    def test_dos_miembros_uno_sin_edificios_y_otro_no_se_rechaza_sin_tocar_nada(self):
        queda_sin = self._miembro("Sin nada", Alcance.EDIFICIOS, [self.edif_c])
        le_queda = self._miembro("Le queda A", Alcance.EDIFICIOS, [self.edif_a, self.edif_c])

        self._rechazada()

        self.assertEqual(self._ids(queda_sin), {self.edif_c.pk})
        self.assertEqual(self._ids(le_queda), {self.edif_a.pk, self.edif_c.pk})

    def test_dos_afectados_se_nombran_en_plural(self):
        self._miembro("Uno", Alcance.EDIFICIOS, [self.edif_c])
        self._miembro("Dos", Alcance.EDIFICIOS, [self.edif_c])

        mensaje = self._rechazada()

        self.assertIn("Lucía Méndez, Lucía Méndez", mensaje)
        self.assertIn("tienen alcance", mensaje)

    def test_el_edificio_no_estaba_en_el_alcance_de_nadie_sigue_igual(self):
        trazas = TrazaDispositivo.objects.count()

        with CaptureQueriesContext(connection) as consultas:
            self._desvincular()

        self.assertFalse(self._vinculado())
        self.assertEqual(TrazaDispositivo.objects.count(), trazas + 1)
        self.assertEqual(self._ids(self.de_a), {self.edif_a.pk})
        # Solo suma la lectura de «quién lo tiene en el alcance».
        self.assertEqual(sum('"usuario_id" AS "usuario_id"' in c["sql"] for c in consultas), 1)

    def test_otra_fila_de_la_misma_persona_con_toda_la_institucion_la_salva(self):
        usuario = self._miembro("Dos filas", Alcance.EDIFICIOS, [self.edif_c])
        self._segunda_fila(usuario, "Rol 2", Alcance.INSTITUCION)

        self._desvincular()

        self.assertFalse(self._vinculado())

    def test_otra_fila_edificios_con_otro_edificio_la_salva(self):
        usuario = self._miembro("Dos filas ed", Alcance.EDIFICIOS, [self.edif_c])
        self._segunda_fila(usuario, "Rol 3", Alcance.EDIFICIOS, [self.edif_a])

        self._desvincular()

        self.assertFalse(self._vinculado())


class OrdenConAltasDelEquipoTests(_Base):
    """Las dos órdenes posibles de una alta concurrente.

    `desvincular_edificio` y `equipo.sumar_miembro` hacen `select_for_update` sobre el `Dispositivo` antes de
    leer o escribir nada, así que el motor las serializa y solo existen estos dos órdenes. Un test con hilos
    necesita bloqueo de filas real (MySQL/MariaDB, tests `mysql`); en SQLite en memoria no hay y no probaría nada.
    """

    def _nuevo(self, nombre):
        """Una persona con rol de Dispositivos que todavía no está en el Equipo del CIS."""

        usuario = self._usuario(nombre, self.parador)
        return usuario, self._fila_de(usuario, self.parador).rol

    def _fila_de(self, usuario, dispositivo):
        return MiembroEquipoDispositivo.objects.get(usuario=usuario, dispositivo=dispositivo)

    def test_el_alta_primero_la_desvinculacion_la_ve_y_rechaza(self):
        usuario, rol = self._nuevo("alta_primero")
        equipo.sumar_miembro(
            actor=self.admin_equipo,
            dispositivo=self.cis,
            usuario=usuario,
            rol=rol,
            alcance=Alcance.EDIFICIOS,
            edificios=[self.edif_c],
        )

        self._rechazada()

    def test_la_desvinculacion_primero_el_alta_ya_no_puede_elegir_ese_edificio(self):
        usuario, rol = self._nuevo("desvincula_primero")
        self._desvincular()

        with self.assertRaises(ValidationError):
            equipo.sumar_miembro(
                actor=self.admin_equipo,
                dispositivo=self.cis,
                usuario=usuario,
                rol=rol,
                alcance=Alcance.EDIFICIOS,
                edificios=[self.edif_c],
            )
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=usuario, dispositivo=self.cis).exists())


class VistaTests(_Base):
    def test_la_vista_muestra_el_mensaje_con_el_nombre_y_no_desvincula(self):
        self._miembro("Solo en C", Alcance.EDIFICIOS, [self.edif_c])
        self.client.force_login(self.actor)
        url = reverse("dispositivos:edificio_desvincular", args=[self.cis.pk, self.edif_c.pk])

        respuesta = self.client.post(url, **AJAX)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Lucía Méndez", respuesta.json()["errors"]["__all__"][0])
        self.assertTrue(self._vinculado())
