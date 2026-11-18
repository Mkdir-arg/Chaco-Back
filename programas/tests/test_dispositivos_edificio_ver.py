"""Alcance de ``edificio.ver`` (#1165).

1. ``dispositivo.ver_todos`` amplía ``edificio.ver`` a toda la red, como amplía
   ``dispositivo.ver``, y no amplía ninguna capacidad de escritura.
2. Sin ``ver_todos``, ``edificio.ver`` alcanza solo los dispositivos donde la persona
   integra el Equipo con un rol que la tiene; ``dispositivo.ver`` sola no la da.
3. ``edificios_en_alcance`` con ``edificio.ver`` devuelve los edificios de ese alcance.
"""

from core import rbac
from programas.models import Edificio
from programas.services.dispositivos import CAP_VER_EDIFICIOS, dispositivos_en_alcance
from programas.services.inspecciones import edificios_en_alcance
from programas.tests.test_dispositivos_equipo_410 import BaseEquipo


class VerTodosAmpliaEdificiosTests(BaseEquipo):
    def setUp(self):
        super().setUp()
        self.edificio_a = Edificio.objects.create(codigo="ED-A", nombre="Edificio A")
        self.edificio_a.dispositivos.add(self.disp_a)
        self.edificio_b = Edificio.objects.create(codigo="ED-B", nombre="Edificio B")
        self.edificio_b.dispositivos.add(self.disp_b)

    def test_la_constante_es_la_del_catalogo(self):
        self.assertIn(CAP_VER_EDIFICIOS, rbac.codigos_de_capacidad())

    def test_ver_todos_amplia_edificio_ver_a_toda_la_red(self):
        rol = self._rol("Lector red", ["edificio.ver", "dispositivo.ver_todos"])
        usuario = self._fresco(self._usuario("lector_red", rol))

        self.assertEqual(set(dispositivos_en_alcance(usuario, "edificio.ver")), {self.disp_a, self.disp_b})
        self.assertEqual(set(edificios_en_alcance(usuario, "edificio.ver")), {self.edificio_a, self.edificio_b})

    def test_ver_todos_no_amplia_la_escritura(self):
        rol = self._rol("Lector que edita", ["edificio.ver", "dispositivo.editar", "dispositivo.ver_todos"])
        usuario = self._fresco(self._usuario("lector_edita", rol))

        self.assertFalse(dispositivos_en_alcance(usuario, "dispositivo.editar").exists())

    def test_ver_todos_sin_edificio_ver_no_da_edificios(self):
        rol = self._rol("Solo dispositivos", ["dispositivo.ver", "dispositivo.ver_todos"])
        usuario = self._fresco(self._usuario("solo_disp", rol))

        self.assertFalse(dispositivos_en_alcance(usuario, "edificio.ver").exists())
        self.assertFalse(edificios_en_alcance(usuario, "edificio.ver").exists())

    def test_sin_ver_todos_solo_los_del_equipo_con_un_rol_que_la_tiene(self):
        con = self._rol("Con edificios", ["dispositivo.ver", "edificio.ver"])
        sin = self._rol("Sin edificios", ["dispositivo.ver"])
        usuario = self._usuario("miembro", con, sin)
        self._miembro(self.disp_a, usuario, con)
        self._miembro(self.disp_b, usuario, sin)
        usuario = self._fresco(usuario)

        self.assertEqual(set(dispositivos_en_alcance(usuario, "edificio.ver")), {self.disp_a})
        self.assertEqual(set(edificios_en_alcance(usuario, "edificio.ver")), {self.edificio_a})
        self.assertEqual(set(dispositivos_en_alcance(usuario, "dispositivo.ver")), {self.disp_a, self.disp_b})
