"""`/health/` no sabe si el sistema sirve; `/health/ready/` sí (OPS-04, RED-59).

Es el PoC `A805HealthTests` de la auditoría dado vuelta. Lo que medía: `/health/`
resuelve a `healthcheck.views.basic`, que devuelve `HttpResponse("OK")` sin tocar nada,
y **responde 200 con la base caída**. Eso no sería grave si fuera solo una liveness
probe, pero es, al mismo tiempo:

- la sonda de `docker-compose.prod.yml` y de `docker/k8s/bootstrap-initcontainer.yaml`;
- el criterio de éxito **y el de rollback** de `scripts/deploy_prod.sh` (RED-59): con
  `/health/`, el rollback automático no se dispara nunca por un esquema roto ni por un
  `collectstatic` fallido, porque el 200 llega igual.

La decisión D-O04 deja `/health/` como está —liveness sin I/O, para no romper las sondas
de ECOM— y agrega `/health/ready/`, que sí toca la base (y, en `prd`, el cache de
sesiones). **No** se usa como readinessProbe por default: con una sola base, sacaría
todos los pods a la vez.
"""

from unittest.mock import patch

from django.db import connection
from django.db.utils import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse


class HealthLivenessTests(SimpleTestCase):
    """`/health/` no cambia: es lo que miran las sondas de ECOM y de compose."""

    def test_health_resuelve_a_nuestra_vista(self):
        coincidencia = resolve("/health/")

        self.assertEqual(coincidencia.view_name, "healthcheck:health_check")

    def test_health_responde_200_sin_tocar_la_base(self):
        with patch.object(connection, "ensure_connection", side_effect=OperationalError("down")):
            respuesta = self.client.get("/health/")

        self.assertEqual(respuesta.status_code, 200)

    def test_el_paquete_django_health_check_ya_no_monta_urls(self):
        """`health_check.urls` estaba montado en `/health/` y era inalcanzable.

        Dos apps compitiendo por la misma ruta es una trampa: el día que alguien
        reordenara `config/urls.py`, `/health/` pasaría a ser la pantalla del paquete
        —que sí toca la base— y las sondas de liveness empezarían a matar pods por una
        base lenta.

        El paquete **sigue en `INSTALLED_APPS`** a propósito: tiene una migración
        aplicada y la tabla `health_check_db_testmodel` en los ambientes. Sacarlo deja
        dos filas de `django_migrations` sin archivo y una tabla sin modelo, que es
        exactamente lo que `verificar_esquema_migraciones` frena —medido en el CI de
        este mismo PR—. Retirarlo es OPS-13, con esa limpieza.
        """
        from config import urls as config_urls

        incluidos = {
            getattr(getattr(patron, "urlconf_module", None), "__name__", "") for patron in config_urls.urlpatterns
        }

        self.assertNotIn("health_check.urls", incluidos)

    def test_health_ready_no_es_del_paquete(self):
        coincidencia = resolve("/health/ready/")

        self.assertEqual(coincidencia.func.__module__, "healthcheck.views.ready")


class HealthReadyTests(TestCase):
    """`/health/ready/`: 200 solo si la base contesta."""

    URL = "/health/ready/"

    def test_la_ruta_existe_y_tiene_nombre(self):
        self.assertEqual(reverse("healthcheck:ready"), self.URL)

    def test_responde_200_con_la_base_viva(self):
        respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["db"], "ok")

    def test_responde_503_con_la_base_caida(self):
        """El caso que `/health/` no distingue y por el que el rollback no se disparaba."""
        with patch.object(connection, "ensure_connection", side_effect=OperationalError("down")):
            respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 503)
        self.assertNotEqual(respuesta.json()["db"], "ok")

    def test_responde_503_si_el_select_falla(self):
        """`ensure_connection` puede pasar con una conexión que ya no sirve."""
        with patch.object(connection, "cursor", side_effect=OperationalError("gone away")):
            respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 503)

    def test_es_anonima(self):
        """Una sonda no tiene sesión: si pidiera login, el deploy fallaría siempre."""
        respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 200)

    def test_fuera_de_prd_no_mira_el_cache(self):
        """En dev/qa el cache es LocMem: chequearlo no diría nada del ambiente."""
        with self.settings(ENVIRONMENT="dev"):
            cuerpo = self.client.get(self.URL).json()

        self.assertNotIn("cache", cuerpo)

    def test_en_prd_mira_tambien_el_cache_de_sesiones(self):
        """En `prd` las sesiones viven en Redis: sin cache nadie puede loguearse."""
        with self.settings(ENVIRONMENT="prd"):
            cuerpo = self.client.get(self.URL).json()

        self.assertEqual(cuerpo["cache"], "ok")

    def test_en_prd_un_cache_caido_da_503(self):
        with self.settings(ENVIRONMENT="prd"):
            with patch("healthcheck.views.ready.caches") as caches:
                caches.__getitem__.return_value.get.side_effect = ConnectionError("redis down")
                respuesta = self.client.get(self.URL)

        self.assertEqual(respuesta.status_code, 503)
        self.assertNotEqual(respuesta.json()["cache"], "ok")
