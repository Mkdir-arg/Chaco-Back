"""El contrato implícito de `user._state.fields_cache["profile"]` (RED-52).

`BackofficeSingleSessionMiddleware` hace `get_or_create` del Profile en **cada** request
autenticado y lo deja en la caché de relaciones del usuario:

    request.user._state.fields_cache["profile"] = profile

De esa línea cuelgan tres cosas que no están escritas en ningún lado:

1. `CambioContrasenaObligatorioMiddleware` lee `request.user.profile` y **no consulta**
   justamente porque ya está en la caché. Depende del orden de `MIDDLEWARE`.
2. `users/services/correo.py` y `users/services/admin.py` leen de ahí.
3. `users/signals/profiles.py::save_user_profile` guarda el Profile **entero** si lo
   encuentra en la caché, en cada `User.save()`.

Lo que (1) y (3) juntos producen es un *lost update*: el Profile que se guarda es el que
se leyó al empezar el request, con los valores de entonces. Si entre medio alguien
cambió una columna —y `backoffice_session_key` la cambia **otro login del mismo
usuario**—, ese valor se pisa con el viejo y el login nuevo pierde su sesión sin
explicación.

Borrar la línea del `fields_cache` parece una micro-optimización al revés; reordenar
`MIDDLEWARE` parece prolijidad. Las dos cosas rompen algo que ningún test miraba.

`test_user_save_no_pisa_la_clave_de_sesion_de_otro_login` está rojo
(`expectedFailure`): el arreglo —reemplazar `save_user_profile` por guardados explícitos
o acotarlo con `update_fields`— es de la **Ola 2, PR 2**.
"""

import unittest

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from users.middleware import (
    BackofficeSingleSessionMiddleware,
    CambioContrasenaObligatorioMiddleware,
)
from users.models import Profile

SINGLE_SESSION = "users.middleware.BackofficeSingleSessionMiddleware"
CAMBIO_CLAVE = "users.middleware.CambioContrasenaObligatorioMiddleware"
AUTENTICACION = "django.contrib.auth.middleware.AuthenticationMiddleware"


class OrdenMiddlewareTests(TestCase):
    def test_single_session_va_antes_que_cambio_de_clave(self):
        """Si se invierte, el gate de clave vuelve a consultar el Profile en cada
        request del backoffice: una consulta más por pantalla, en el 100 % del tráfico
        autenticado."""
        middlewares = list(settings.MIDDLEWARE)

        self.assertLess(middlewares.index(SINGLE_SESSION), middlewares.index(CAMBIO_CLAVE))

    def test_los_dos_van_despues_de_la_autenticacion(self):
        """Antes de `AuthenticationMiddleware`, `request.user` no existe todavía: los
        dos se saltearían enteros y la sesión única dejaría de aplicarse **en
        silencio**, que es el modo de falla peligroso."""
        middlewares = list(settings.MIDDLEWARE)

        self.assertLess(middlewares.index(AUTENTICACION), middlewares.index(SINGLE_SESSION))
        self.assertLess(middlewares.index(AUTENTICACION), middlewares.index(CAMBIO_CLAVE))


class ProfileEnCacheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="profile_cache",
            password="clave-de-prueba",
        )

    def _request_autenticado(self):
        peticion = RequestFactory().get("/inicio/")
        peticion.user = get_user_model().objects.get(pk=self.usuario.pk)
        peticion.session = self.client.session
        return peticion

    def test_el_primer_middleware_deja_el_profile_en_la_cache(self):
        """Control del andamio del test que sigue."""
        peticion = self._request_autenticado()

        BackofficeSingleSessionMiddleware(lambda _peticion: None)(peticion)

        self.assertIn("profile", peticion.user._state.fields_cache)

    def test_el_gate_de_clave_no_consulta_el_profile(self):
        """La promesa que el docstring del middleware hace y nadie verificaba.

        Con la caché poblada por el middleware anterior, el gate de clave resuelve
        `request.user.profile` en **cero** consultas. Borrar la línea del `fields_cache`
        agrega una consulta por request autenticado; este test lo convierte en un fallo
        en vez de en una degradación invisible.
        """
        peticion = self._request_autenticado()
        BackofficeSingleSessionMiddleware(lambda _peticion: None)(peticion)

        with self.assertNumQueries(0):
            CambioContrasenaObligatorioMiddleware(lambda _peticion: None)(peticion)

    def test_sin_la_cache_el_gate_de_clave_si_consulta(self):
        """La otra mitad: así se ve el costo que la línea evita. Si este test pasara a
        dar 0, la caché dejó de hacer falta y la ficha se puede cerrar distinto."""
        peticion = self._request_autenticado()
        peticion.user._state.fields_cache.pop("profile", None)

        with self.assertNumQueries(1):
            CambioContrasenaObligatorioMiddleware(lambda _peticion: None)(peticion)

    def test_la_api_no_pasa_por_el_gate_de_clave(self):
        """El gate se saltea **por el path**, no por el usuario.

        `/api/` usa tokens de DRF, que se resuelven dentro de la vista: en el middleware
        `request.user` suele ser anónimo. Pero la condición escrita en el código es
        `request.path.startswith("/api/")`, así que lo que hay que fijar es eso —el
        request de acá lleva un usuario autenticado con la clave provisoria marcada, el
        caso más exigente, y aun así el gate lo deja pasar—. Sin esta aserción, cambiar
        la condición a «solo si es anónimo» rompería la app de campo sin que nada lo
        avise, y el cambio de clave del backoffice se resuelve en el navegador, no
        interceptando la API.

        El `get()` fresco es lo que vuelve al test no vacuo: el objeto de
        `setUpTestData` arrastra en su `fields_cache` el Profile del alta, con
        `debe_cambiar_contrasena=False`, así que el gate salía por la otra rama y el
        test pasaba aunque se le sacara el filtro por path (RED-52 otra vez, esta vez
        mordiendo a su propio test).
        """
        Profile.objects.filter(user=self.usuario).update(debe_cambiar_contrasena=True)
        peticion = RequestFactory().get("/api/becas/relevamientos/")
        peticion.user = get_user_model().objects.get(pk=self.usuario.pk)

        respuesta = CambioContrasenaObligatorioMiddleware(lambda _peticion: "siguio")(peticion)

        self.assertEqual(respuesta, "siguio")

    def test_fuera_de_la_api_la_misma_peticion_si_redirige(self):
        """Control del test de arriba: lo único que cambia es el path. Sin esto, aquel
        podría estar pasando porque el gate no se dispara nunca."""
        Profile.objects.filter(user=self.usuario).update(debe_cambiar_contrasena=True)
        peticion = RequestFactory().get("/becas/relevamientos/")
        peticion.user = get_user_model().objects.get(pk=self.usuario.pk)

        respuesta = CambioContrasenaObligatorioMiddleware(lambda _peticion: "siguio")(peticion)

        self.assertNotEqual(respuesta, "siguio")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("users:cambiar_contrasena_obligatorio"))

    def test_con_la_clave_provisoria_el_backoffice_redirige(self):
        """El comportamiento que el gate tiene que conservar cuando la Ola 2 lo toque.

        El `get()` fresco no es cosmético: ver `test_un_login_pisa_el_flag_de_clave_
        provisoria`, abajo.
        """
        Profile.objects.filter(user=self.usuario).update(debe_cambiar_contrasena=True)
        self.client.force_login(get_user_model().objects.get(pk=self.usuario.pk))

        respuesta = self.client.get(reverse("core:inicio"))

        self.assertRedirects(
            respuesta,
            reverse("users:cambiar_contrasena_obligatorio"),
            fetch_redirect_response=False,
        )

    @unittest.expectedFailure
    def test_un_login_pisa_el_flag_de_clave_provisoria(self):
        """RED-52, segunda cara del mismo *lost update* — se invierte en la Ola 2.

        No estaba en la ficha; apareció escribiendo este módulo. El mecanismo es el
        mismo que el de `backoffice_session_key`, sobre otra columna y con un
        disparador cotidiano: **el login**. `login()` llama a `update_last_login`, que
        hace `user.save(update_fields=["last_login"])`; `save_user_profile` ve el
        Profile en la caché del objeto en memoria —lo dejó ahí `create_user_profile` al
        darlo de alta, o el middleware en un request anterior del mismo proceso— y lo
        guarda **entero**, con el `debe_cambiar_contrasena` de entonces.

        En un proceso de larga vida, cualquier objeto `User` que sobreviva a la
        escritura de otro request arrastra este problema. El arreglo (acotar el
        guardado con `update_fields`) cubre las dos caras de una.
        """
        usuario = get_user_model().objects.create_user(username="clave_pisada", password="x")
        Profile.objects.filter(user=usuario).update(debe_cambiar_contrasena=True)

        self.client.force_login(usuario)  # el mismo objeto, con su Profile en caché

        self.assertTrue(Profile.objects.get(user=usuario).debe_cambiar_contrasena)

    @unittest.expectedFailure
    def test_user_save_no_pisa_la_clave_de_sesion_de_otro_login(self):
        """RED-52 — se invierte en la Ola 2 (PR 2, usuarios).

        El escenario, con los dos actores reales:

        - La persona tiene un request en vuelo. El middleware ya leyó su Profile y lo
          dejó en `fields_cache` con `backoffice_session_key = "sesion-vieja"`.
        - Entra desde otra máquina: ese otro request escribe `"sesion-nueva"` en la
          fila.
        - El primer request hace un `user.save()` cualquiera (el ABM de usuarios, un
          cambio de nombre, `update_last_login`…). `save_user_profile` guarda el Profile
          **entero** que tenía en la caché y devuelve la columna a `"sesion-vieja"`.

        Resultado: el login nuevo queda apuntando a una sesión que ya no es la de la
        fila, y el próximo request lo saca con «Tu sesión fue reemplazada». El arreglo
        es acotar el guardado (`update_fields`) o sacarlo del `post_save`.
        """
        Profile.objects.filter(user=self.usuario).update(backoffice_session_key="sesion-vieja")
        usuario = get_user_model().objects.get(pk=self.usuario.pk)
        usuario._state.fields_cache["profile"] = usuario.profile

        # Otro login del mismo usuario, desde otra máquina.
        Profile.objects.filter(user=usuario).update(backoffice_session_key="sesion-nueva")

        usuario.first_name = "Nombre nuevo"
        usuario.save()

        self.assertEqual(
            Profile.objects.get(user=usuario).backoffice_session_key,
            "sesion-nueva",
        )

    def test_hoy_el_user_save_propaga_el_profile_entero(self):
        """El andamio del `expectedFailure`: deja escrito que el receiver existe y que
        guarda de verdad. Si mañana `save_user_profile` dejara de correr, el test de
        arriba pasaría por el motivo equivocado (y además se perdería la propagación
        que algún llamador puede estar usando)."""
        usuario = get_user_model().objects.get(pk=self.usuario.pk)
        perfil = usuario.profile
        usuario._state.fields_cache["profile"] = perfil
        perfil.backoffice_session_key = "escrita-en-memoria"

        usuario.save()

        self.assertEqual(
            Profile.objects.get(user=usuario).backoffice_session_key,
            "escrita-en-memoria",
        )

    def test_sin_profile_en_la_cache_el_user_save_no_consulta(self):
        """La optimización que el receiver sí aporta y que el arreglo de la Ola 2 tiene
        que conservar: un `User.save()` en lote no dispara un N+1 de Profiles."""
        usuario = get_user_model().objects.get(pk=self.usuario.pk)
        usuario._state.fields_cache.pop("profile", None)

        with self.assertNumQueries(1):  # solo el UPDATE del User
            usuario.save()
