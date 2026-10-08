"""APIs JSON del legajo: `ciudadano.ver` como piso (SEC-11, auditoría oct-2026).

El barrido de RED-89 midió que un usuario **sin ningún rol** recibía 200 en
`timeline`, `alertas`, `prediccion-riesgo`, `actividades`, `evolucion` y el
historial de contactos. El tipo de alerta que sale ahí es «Riesgo Suicida».

Las seis llevan ahora `@requiere("ciudadano.ver")`. Para tres de ellas
—`timeline_ciudadano_api`, `alertas_ciudadano_api` y `prediccion_riesgo_api`—
`ciudadano.ver` es un **piso**, no la capacidad definitiva: la fina es
`ciudadano.sensible` y la sube la Ola 2 cuando se resuelva D-11. El piso es lo
que permite que ninguna quede abierta mientras tanto.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano, LegajoAtencion
from users.models import Capacidad, RolMeta


def usuario_con(*codigos, username=None):
    usuario = User.objects.create_user(username or f"c-{'-'.join(codigos) or 'sin-rol'}", password="Clave-Seg-2026x")
    if not codigos:
        return usuario
    grupo, _ = Group.objects.get_or_create(name="Rol contactos " + "-".join(codigos))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


class ContactosApiRbacTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21555666", nombre="Mirta", apellido="Quiroga")
        cls.responsable = User.objects.create_user("resp-contactos", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.responsable)

    def _rutas_sensibles(self):
        """Las tres que D-11 subió a `ciudadano.sensible` (SEC-11, Ola 2)."""
        return [
            reverse("legajos:alertas_ciudadano", args=[self.mirta.id]),
            reverse("legajos:timeline_ciudadano", args=[self.mirta.id]),
            reverse("legajos:prediccion_riesgo", args=[self.mirta.id]),
        ]

    def _rutas_de_ver(self):
        """Las tres en que `ciudadano.ver` es la capacidad definitiva."""
        return [
            reverse("legajos:actividades_ciudadano", args=[self.mirta.id]),
            reverse("legajos:evolucion_legajo", args=[self.legajo.id]),
            reverse("legajos:historial_contactos", args=[self.legajo.id]),
        ]

    def _rutas(self):
        return self._rutas_de_ver() + self._rutas_sensibles()

    def test_sin_rol_ninguna_contesta(self):
        cliente = Client()
        cliente.force_login(usuario_con())

        for url in self._rutas():
            with self.subTest(url=url):
                respuesta = cliente.get(url, headers={"x-requested-with": "XMLHttpRequest"})
                self.assertEqual(respuesta.status_code, 403)

    def test_sin_el_encabezado_ajax_el_rebote_es_el_redirect_al_inicio(self):
        """Contrato de `_respuesta_sin_permiso`, el mismo que fijó RED-73."""
        cliente = Client()
        cliente.force_login(usuario_con(username="sin-rol-navegando"))

        respuesta = cliente.get(reverse("legajos:timeline_ciudadano", args=[self.mirta.id]))

        self.assertRedirects(respuesta, reverse("core:inicio"))

    def test_con_ciudadano_ver_contestan_las_tres_no_sensibles(self):
        """Un usuario que hoy usa Legajos con su rol normal sigue pudiendo."""
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.ver", username="ve-legajos"))

        for url in self._rutas_de_ver():
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 200)

    def test_con_ciudadano_ver_las_tres_sensibles_ya_no_contestan(self):
        """D-11 = Sí: timeline, alertas y predicción de riesgo piden `ciudadano.sensible`.

        R-19 les había puesto `ciudadano.ver` como **piso** para que ninguna
        quedara abierta mientras se decidía; este es el ascenso que faltaba.
        """
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.ver", username="ve-pero-no-sensible"))

        for url in self._rutas_sensibles():
            with self.subTest(url=url):
                respuesta = cliente.get(url, headers={"x-requested-with": "XMLHttpRequest"})
                self.assertEqual(respuesta.status_code, 403)

    def test_con_ciudadano_sensible_las_tres_contestan(self):
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.sensible", username="ve-lo-sensible"))

        for url in self._rutas_sensibles():
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 200)

    def test_el_superusuario_pasa(self):
        cliente = Client()
        cliente.force_login(User.objects.create_superuser("root-contactos", "root-c@example.test", "x"))

        for url in self._rutas():
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 200)

    def test_el_anonimo_va_al_login(self):
        cliente = Client()

        for url in self._rutas():
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 302)

    def test_el_ciudadano_del_portal_no_entra(self):
        portal = User.objects.create_user("30222555", password="Clave-Seg-2026x")
        portal.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        cliente = Client()
        cliente.force_login(portal)

        for url in self._rutas():
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 302)
