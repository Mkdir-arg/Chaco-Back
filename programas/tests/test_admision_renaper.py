"""SEC-32 · El buscador de la admisión deja de ser un oráculo de RENAPER.

`GET /dispositivos/<pk>/admisiones/nueva/?dni=…&sexo=M` consultaba el registro de
personas con solo `dispositivo.admitir`: nombre, apellido, fecha de nacimiento y
domicilio de cualquier documento, por GET, sin tope y sin dejar rastro. El alta
que viene después **ya** exigía `ciudadano.crear` (`AdmisionCreateView.post`), así
que a quien no la tiene esos datos no le servían ni para dar de alta: solo para
mirar. Ahora la consulta pide la misma capacidad que el alta, pasa por una cubeta
por operador y queda registrada.

Lo que **no** cambia: admitir a alguien que ya está en el padrón, que es el camino
normal del dispositivo, no consulta nada y no pide ninguna capacidad nueva.
"""

from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from programas.models import AsignacionDispositivo, Dispositivo, Programa, TipoDispositivo
from users.models import Capacidad, RolMeta

RESPUESTA_RENAPER = {
    "success": True,
    "data": {
        "nombre": "Ana María",
        "apellido": "Pérez",
        "fecha_nacimiento": "1990-05-04",
        "genero": "F",
        "domicilio": "San Martín 123",
    },
}


def _permiso(codigo):
    return Permission.objects.get(
        codename=rbac.codename_de(codigo), content_type=ContentType.objects.get_for_model(Capacidad)
    )


class ConsultaRenaperDesdeLaAdmisionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        tipo = TipoDispositivo.objects.create(codigo="SEC32", nombre="Hogar", maneja_camas=True)
        self.dispositivo = Dispositivo.objects.create(
            codigo="HOGAR-SEC32", nombre="Hogar", tipo=tipo, estado=Dispositivo.Estado.ACTIVO
        )
        self.url = reverse("dispositivos:admitir", args=[self.dispositivo.pk])
        self.operador = self._usuario_con("operador-sec32", ["dispositivo.ver", "dispositivo.admitir"])
        self.altas = self._usuario_con("altas-sec32", ["dispositivo.ver", "dispositivo.admitir", "ciudadano.crear"])

    def tearDown(self):
        cache.clear()

    def _usuario_con(self, username, capacidades):
        rol = Group.objects.create(name=f"Rol {username}")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        usuario = User.objects.create_user(username, password="Clave-Seg-2026x")
        usuario.groups.add(rol)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo, rol=rol)
        return usuario

    def _buscar(self, usuario, dni="30111222"):
        self.client.force_login(usuario)
        with patch(
            "programas.views.admisiones.CiudadanosService.consultar_renaper",
            return_value=RESPUESTA_RENAPER,
        ) as consulta:
            respuesta = self.client.get(self.url, {"dni": dni, "sexo": "F"})
        return respuesta, consulta

    def test_sin_ciudadano_crear_no_se_consulta_al_registro(self):
        respuesta, consulta = self._buscar(self.operador)

        self.assertEqual(respuesta.status_code, 200)
        consulta.assert_not_called()
        self.assertNotContains(respuesta, "Pérez")

    def test_con_ciudadano_crear_la_pantalla_sigue_igual(self):
        respuesta, consulta = self._buscar(self.altas)

        self.assertEqual(respuesta.status_code, 200)
        consulta.assert_called_once_with("30111222", "F")
        self.assertContains(respuesta, "Pérez")

    def test_admitir_a_alguien_del_padron_no_consulta_nada(self):
        """El camino normal del dispositivo no toca RENAPER ni pide capacidad nueva."""
        Ciudadano.objects.create(dni="30111222", nombre="Ana", apellido="Pérez")

        respuesta, consulta = self._buscar(self.operador)

        self.assertEqual(respuesta.status_code, 200)
        consulta.assert_not_called()

    def test_la_cubeta_corta_el_barrido(self):
        with self.settings(RENAPER_ADMISION_MAX_POR_HORA=3):
            for numero in range(3):
                _, consulta = self._buscar(self.altas, dni=f"3011122{numero}")
                consulta.assert_called_once()

            respuesta, consulta = self._buscar(self.altas, dni="30111229")

        self.assertEqual(respuesta.status_code, 200)
        consulta.assert_not_called()

    def test_la_cubeta_es_por_operador(self):
        """Dos personas en el mismo dispositivo comparten la salida a internet,
        no la cuota: el barrido cuesta una cuenta por tanda."""
        otro = self._usuario_con("altas2-sec32", ["dispositivo.ver", "dispositivo.admitir", "ciudadano.crear"])

        with self.settings(RENAPER_ADMISION_MAX_POR_HORA=1):
            self._buscar(self.altas, dni="30111223")
            _, agotada = self._buscar(self.altas, dni="30111224")
            _, del_otro = self._buscar(otro, dni="30111225")

        agotada.assert_not_called()
        del_otro.assert_called_once()
