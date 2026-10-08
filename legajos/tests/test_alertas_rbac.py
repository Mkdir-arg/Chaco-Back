"""Alertas de ciudadanos: capacidad y alcance (SEC-18 + R0b-06, auditoría oct-2026).

Lo que el barrido de RED-89 midió el 04-oct-2026 con un usuario **sin ningún
rol**: `/legajos/alertas/` le devolvía 59 KB de HTML con el nombre del ciudadano
y el texto de la alerta, `/legajos/alertas/preview/` y `/api/legajos/alertas/`
lo mismo en JSON, y las tres entradas de cierre —`cerrar-ajax/`, `cerrar/` y
`POST /api/legajos/alertas/<id>/cerrar/`— contestaban 200 y dejaban la alerta
ajena en `activa=False`. Con `n = 1..N` eso silencia las alertas de todo el
sistema. Además, un `pk` no numérico en la ruta de DRF daba **500**.

Dos cosas lo cierran: la capacidad y el alcance (`FiltrosUsuarioService`), que ya
no cae en el fallback «todas las CRÍTICAS».

SEC-18 puso `ciudadano.ver`. El Cambio 179 (ronda 2) la subió a
**`ciudadano.sensible`** en las cuatro superficies HTTP —dashboard, contador,
preview y cierre— y en `AlertasViewSet`, por **D-11**: el mensaje de la alerta es
el mismo dato que entrega `/ws/alertas/`, y el dato sensible pide la misma
capacidad por cualquier canal. Quien pierde acceso: un rol con `ciudadano.ver` y
sin `ciudadano.sensible`, como el «Operador de backoffice» de `seed_rbac`.

La ronda 3 sumó la séptima superficie, la única que no es una API: la solapa
«Alertas activas» del detalle del ciudadano, que se arma del lado del servidor
(`AlertasEnElDetalleDelCiudadanoTests`).
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from core import rbac
from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from legajos.services import FiltrosUsuarioService
from users.models import Capacidad, RolMeta


def usuario_con(*codigos, username=None):
    """Usuario de backoffice con exactamente esas capacidades (ninguna = sin rol)."""
    usuario = User.objects.create_user(username or f"a-{'-'.join(codigos) or 'sin-rol'}", password="Clave-Seg-2026x")
    if not codigos:
        return usuario
    grupo, _ = Group.objects.get_or_create(name="Rol alertas " + "-".join(codigos))
    RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


class AlertasRbacTests(TestCase):
    """Quién puede abrir el dashboard, contar, previsualizar y cerrar."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21444555", nombre="Mirta", apellido="Quiroga")
        cls.alerta = AlertaCiudadano.objects.create(
            ciudadano=cls.mirta,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_SUICIDA,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Riesgo suicida detectado en la última entrevista",
        )

    def setUp(self):
        # `alertas_count_ajax` cachea 30 s por `user.id`, y la caché no se revierte
        # entre tests como sí lo hace la base: ver `test_alertas_dashboard`.
        cache.clear()

    def _cliente(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        return cliente

    def test_sin_rol_no_ve_el_dashboard_ni_los_endpoints(self):
        cliente = self._cliente(usuario_con())

        for nombre, args in (
            ("legajos:alertas_dashboard", []),
            ("legajos:alertas_count_ajax", []),
            ("legajos:alertas_preview_ajax", []),
        ):
            with self.subTest(ruta=nombre):
                respuesta = cliente.get(reverse(nombre, args=args), headers={"x-requested-with": "XMLHttpRequest"})
                self.assertEqual(respuesta.status_code, 403)

    def test_sin_rol_no_cierra_una_alerta_ajena(self):
        """El agujero medido: 200 y la alerta de otro quedaba en `activa=False`."""
        cliente = self._cliente(usuario_con())

        for nombre in ("legajos:cerrar_alerta_ajax", "legajos:cerrar_alerta_ciudadano"):
            with self.subTest(ruta=nombre):
                respuesta = cliente.post(
                    reverse(nombre, args=[self.alerta.id]), headers={"x-requested-with": "XMLHttpRequest"}
                )
                self.assertEqual(respuesta.status_code, 403)
                self.alerta.refresh_from_db()
                self.assertTrue(self.alerta.activa)

    def test_con_ciudadano_ver_solo_ya_no_entra_a_ninguna(self):
        """D-11: el «Operador de backoffice» (`ciudadano.ver` a secas) queda afuera.

        Es el agujero que quedaba: el mismo texto que G1c-04 le cerró por
        WebSocket seguía saliendo por estas tres rutas HTTP.
        """
        cliente = self._cliente(usuario_con("ciudadano.ver", username="operador-solo-ver"))

        for nombre in ("legajos:alertas_dashboard", "legajos:alertas_count_ajax", "legajos:alertas_preview_ajax"):
            with self.subTest(ruta=nombre):
                respuesta = cliente.get(reverse(nombre))
                self.assertIn(respuesta.status_code, (302, 403))
                if respuesta.status_code == 200:  # pragma: no cover - defensivo
                    self.fail("el operador no tiene que ver la pantalla")

    def test_con_ciudadano_ver_solo_no_lee_el_texto_de_la_alerta(self):
        """Lo que importa no es el código: es que el mensaje no viaje."""
        cliente = self._cliente(usuario_con("ciudadano.ver", username="operador-texto"))

        for nombre in ("legajos:alertas_dashboard", "legajos:alertas_preview_ajax"):
            with self.subTest(ruta=nombre):
                cuerpo = cliente.get(reverse(nombre)).content.decode(errors="ignore")
                self.assertNotIn("Riesgo suicida detectado en la última entrevista", cuerpo)
                self.assertNotIn("Quiroga", cuerpo)

    def test_con_ciudadano_ver_solo_tampoco_cierra(self):
        cliente = self._cliente(usuario_con("ciudadano.ver", username="operador-cierra"))

        for nombre in ("legajos:cerrar_alerta_ajax", "legajos:cerrar_alerta_ciudadano"):
            with self.subTest(ruta=nombre):
                respuesta = cliente.post(
                    reverse(nombre, args=[self.alerta.id]), headers={"x-requested-with": "XMLHttpRequest"}
                )
                self.assertEqual(respuesta.status_code, 403)
                self.alerta.refresh_from_db()
                self.assertTrue(self.alerta.activa)

    def test_con_ciudadano_sensible_abre_el_dashboard(self):
        """El rol «Gestión de Ciudadanos» del seed trae las dos: sigue entrando."""
        cliente = self._cliente(usuario_con("ciudadano.ver", "ciudadano.sensible"))

        self.assertEqual(cliente.get(reverse("legajos:alertas_dashboard")).status_code, 200)
        self.assertEqual(cliente.get(reverse("legajos:alertas_count_ajax")).status_code, 200)
        self.assertEqual(cliente.get(reverse("legajos:alertas_preview_ajax")).status_code, 200)

    def test_el_superusuario_abre_el_dashboard(self):
        cliente = self._cliente(User.objects.create_superuser("root-alertas", "root-a@example.test", "x"))

        self.assertEqual(cliente.get(reverse("legajos:alertas_dashboard")).status_code, 200)

    def test_el_anonimo_va_al_login(self):
        respuesta = Client().get(reverse("legajos:alertas_dashboard"))

        self.assertEqual(respuesta.status_code, 302)


class AlertasAlcanceTests(TestCase):
    """Tener `ciudadano.ver` no es ver las alertas de todo el sistema."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21444666", nombre="Mirta", apellido="Quiroga")
        cls.responsable = User.objects.create_user("resp-alertas", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.responsable)
        cls.critica = AlertaCiudadano.objects.create(
            ciudadano=cls.mirta,
            legajo=cls.legajo,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_SUICIDA,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Riesgo suicida detectado",
        )

    def test_un_usuario_sin_legajos_no_ve_las_criticas_del_sistema(self):
        """El fallback era `Q(prioridad="CRITICA")`: mostraba todas las críticas
        justo a quien no tiene un solo legajo asignado (SEC-18)."""
        sin_legajos = usuario_con("ciudadano.ver", username="ve-pero-sin-legajos")

        alertas = FiltrosUsuarioService.obtener_alertas_usuario(sin_legajos)

        self.assertEqual(list(alertas), [])
        self.assertEqual(FiltrosUsuarioService.obtener_estadisticas_usuario(sin_legajos)["criticas"], 0)

    def test_el_dashboard_de_un_usuario_sin_legajos_no_nombra_al_ciudadano(self):
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.ver", "ciudadano.sensible", username="dash-sin-legajos"))

        html = cliente.get(reverse("legajos:alertas_dashboard")).content.decode()

        self.assertNotIn("Quiroga", html)
        self.assertNotIn("Riesgo suicida detectado", html)

    def test_cerrar_una_alerta_fuera_de_alcance_no_la_cierra(self):
        """Con capacidad pero sin la alerta en su alcance: no la silencia."""
        cliente = Client()
        cliente.force_login(usuario_con("ciudadano.ver", "ciudadano.sensible", username="cierra-ajena"))

        respuesta = cliente.post(reverse("legajos:cerrar_alerta_ajax", args=[self.critica.id]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()["success"])
        self.critica.refresh_from_db()
        self.assertTrue(self.critica.activa)

    def test_el_responsable_del_legajo_si_la_cierra(self):
        cliente = Client()
        grupo, _ = Group.objects.get_or_create(name="Rol responsable alertas")
        RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
        ct = ContentType.objects.get_for_model(Capacidad)
        for codigo in ("ciudadano.ver", "ciudadano.sensible"):
            grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
        self.responsable.groups.add(grupo)
        cliente.force_login(self.responsable)

        respuesta = cliente.post(reverse("legajos:cerrar_alerta_ajax", args=[self.critica.id]))

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["success"])
        self.critica.refresh_from_db()
        self.assertFalse(self.critica.activa)
        self.assertEqual(self.critica.cerrada_por, self.responsable)

    def test_quien_administra_la_configuracion_sigue_viendo_todo(self):
        """`config.administrar` es el alcance global, previsto en `filtros_usuario`."""
        admin = usuario_con("config.administrar", "ciudadano.sensible", username="admin-global-alertas")

        self.assertEqual(list(FiltrosUsuarioService.obtener_alertas_usuario(admin)), [self.critica])

    def test_el_alcance_global_no_es_una_puerta_de_entrada(self):
        """`config.administrar` abre el alcance, no la pantalla (D-11).

        Era la segunda mitad del agujero: un rol de Configuración con
        `ciudadano.ver` leía por HTTP el texto de las alertas de **todo** el
        padrón, porque `tiene_alcance_global` mira `config.administrar`. Ahora la
        puerta es `ciudadano.sensible`, y sin ella el alcance global no se usa.
        """
        cliente = Client()
        cliente.force_login(usuario_con("config.administrar", "ciudadano.ver", username="config-sin-sensible"))

        respuesta = cliente.get(reverse("legajos:alertas_dashboard"))

        self.assertIn(respuesta.status_code, (302, 403))


class AlertasEnElDetalleDelCiudadanoTests(TestCase):
    """La séptima superficie: la solapa «Alertas activas» del legajo.

    `ciudadano_detail.html` no pasa por ninguna API: el panel se renderiza del
    lado del servidor con `alertas_ciudadano`, que `build_ciudadano_detail_context`
    sacaba de la base sin mirar la capacidad. Un rol con `ciudadano.ver` a secas
    —el «Operador de backoffice»— abría el detalle y leía ahí el mismo «Riesgo
    Suicida» que D-11 le había cerrado por las otras seis.
    """

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21444888", nombre="Mirta", apellido="Quiroga")
        cls.alerta = AlertaCiudadano.objects.create(
            ciudadano=cls.mirta,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_SUICIDA,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Riesgo suicida detectado en la última entrevista",
        )
        cls.url = reverse("legajos:ciudadano_detalle", args=[cls.mirta.pk])

    def _html(self, usuario):
        cliente = Client()
        cliente.force_login(usuario)
        respuesta = cliente.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.content.decode()

    def test_con_ciudadano_ver_solo_entra_pero_no_lee_la_alerta(self):
        html = self._html(usuario_con("ciudadano.ver", username="detalle-solo-ver"))

        self.assertNotIn("Riesgo suicida detectado en la última entrevista", html)
        self.assertNotIn(self.alerta.get_tipo_display(), html)

    def test_con_ciudadano_ver_solo_tampoco_ve_la_solapa_ni_el_contador(self):
        html = self._html(usuario_con("ciudadano.ver", username="detalle-solapa"))

        self.assertNotIn('id="tab-btn-alertas"', html)
        self.assertNotIn('id="tab-alertas"', html)
        self.assertNotIn("Alertas activas", html)

    def test_con_ciudadano_sensible_si_las_ve(self):
        html = self._html(usuario_con("ciudadano.ver", "ciudadano.sensible", username="detalle-sensible"))

        self.assertIn("Riesgo suicida detectado en la última entrevista", html)
        self.assertIn(self.alerta.get_tipo_display(), html)
        self.assertIn('id="tab-btn-alertas"', html)

    def test_sin_la_capacidad_el_selector_no_consulta_las_alertas(self):
        from legajos.selectors.ciudadanos import build_ciudadano_detail_context

        usuario = usuario_con("ciudadano.ver", username="detalle-sin-consulta")

        contexto = build_ciudadano_detail_context(self.mirta, user=usuario)

        self.assertEqual(list(contexto["alertas_ciudadano"]), [])
        self.assertNotIn("alertas", [solapa["id"] for solapa in contexto["solapas"]])


class AlertasApiTests(TestCase):
    """`AlertasViewSet`: capacidad (R0b-06) y `get_object()` (el 500 del `pk`)."""

    @classmethod
    def setUpTestData(cls):
        cls.mirta = Ciudadano.objects.create(dni="21444777", nombre="Mirta", apellido="Quiroga")
        cls.responsable = User.objects.create_user("resp-api-alertas", password="Clave-Seg-2026x")
        cls.legajo = LegajoAtencion.objects.create(responsable=cls.responsable)
        cls.alerta = AlertaCiudadano.objects.create(
            ciudadano=cls.mirta,
            legajo=cls.legajo,
            tipo=AlertaCiudadano.TipoAlerta.VIOLENCIA,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Situación de violencia reportada",
        )

    def _api(self, usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def test_sin_capacidad_no_lista_ni_cuenta(self):
        cliente = self._api(usuario_con(username="api-sin-rol"))

        for url in ("/api/legajos/alertas/", "/api/legajos/alertas/count/"):
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 403)

    def test_sin_capacidad_no_cierra(self):
        cliente = self._api(usuario_con(username="api-sin-rol-cierra"))

        respuesta = cliente.post(f"/api/legajos/alertas/{self.alerta.id}/cerrar/")

        self.assertEqual(respuesta.status_code, 403)
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.activa)

    def test_con_ciudadano_ver_solo_tampoco_lista(self):
        """D-11: `AlertasViewSet` es el cuarto canal del mismo texto."""
        cliente = self._api(usuario_con("ciudadano.ver", username="api-solo-ver"))

        for url in ("/api/legajos/alertas/", "/api/legajos/alertas/count/"):
            with self.subTest(url=url):
                self.assertEqual(cliente.get(url).status_code, 403)

    def test_con_pk_no_numerico_da_404_y_no_revienta(self):
        """Antes: `AlertasService.cerrar_alerta` recibía el `pk` crudo → 500."""
        cliente = self._api(usuario_con("ciudadano.sensible", username="api-ve-alertas"))

        respuesta = cliente.post("/api/legajos/alertas/x/cerrar/")

        self.assertEqual(respuesta.status_code, 404)

    def test_cerrar_una_alerta_fuera_de_alcance_da_404(self):
        cliente = self._api(usuario_con("ciudadano.sensible", username="api-fuera-alcance"))

        respuesta = cliente.post(f"/api/legajos/alertas/{self.alerta.id}/cerrar/")

        self.assertEqual(respuesta.status_code, 404)
        self.alerta.refresh_from_db()
        self.assertTrue(self.alerta.activa)

    def test_el_responsable_cierra_por_la_api(self):
        ct = ContentType.objects.get_for_model(Capacidad)
        grupo, _ = Group.objects.get_or_create(name="Rol api responsable")
        RolMeta.objects.get_or_create(grupo=grupo, defaults={"categoria": rbac.CATEGORIA_BACKOFFICE, "activo": True})
        for codigo in ("ciudadano.ver", "ciudadano.sensible"):
            grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
        self.responsable.groups.add(grupo)

        respuesta = self._api(self.responsable).post(f"/api/legajos/alertas/{self.alerta.id}/cerrar/")

        self.assertEqual(respuesta.status_code, 200)
        self.alerta.refresh_from_db()
        self.assertFalse(self.alerta.activa)
