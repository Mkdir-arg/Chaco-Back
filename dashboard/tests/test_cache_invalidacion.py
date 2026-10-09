"""Los contadores de la home y quién los invalida (RED-51).

**Había** dos funciones llamadas `invalidate_dashboard_cache` —una en `dashboard/utils.py`
con cinco claves, llamada por `CiudadanosService.invalidate_ciudadanos_cache()` desde las
tres vistas de ciudadanos, y otra en `core/performance/cache_utils.py` con dos, cableada
por señales—, y un receiver colgado del modelo equivocado: `stats_legajos` se borraba al
guardar un `LegajoAtencion`, pero esa clave la escribe `contar_legajos()`, que agrega
sobre **`InscripcionPrograma`**. Una inscripción nueva no refrescaba nada; un legajo de
atención refrescaba algo que no había cambiado. Y `alertas_activas` no la borraba nadie.

Por qué importaba: la limpieza de OPS-10 (Ola 7) iba a «deduplicar» las dos funciones.
Si se quedaba con la de `core/performance` —la que tenía las señales— perdía tres claves;
si se quedaba con la de `dashboard`, los receivers. En producción el cache es Redis
compartido con TTL de 300 s, así que el síntoma es un contador viejo en la home durante
cinco minutos; en los tests es LocMem y esta familia de bugs es invisible para la suite.

**Arreglado en la Ola 4 PR 9 (Cambio 194).** `dashboard/cache.py` es la tabla única
(clave → qué la escribe → qué modelo la invalida); los dos tests que estaban en
`expectedFailure` ahora pasan en verde y `DosFuncionesTests` quedó invertido: afirma que
no vuelve a haber dos funciones con ese nombre y que la tabla no pierde claves.
"""

import ast
from pathlib import Path

from django.core.cache import cache
from django.test import TestCase

from dashboard.utils import contar_alertas_activas, contar_ciudadanos, contar_legajos
from legajos.models import AlertaCiudadano, Ciudadano, LegajoAtencion
from programas.models import InscripcionPrograma, Programa

RAIZ = Path(__file__).resolve().parents[2]


class InvalidacionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.ciudadano = Ciudadano.objects.create(nombre="Ana", apellido="Pérez", dni="20111222")
        self.programa = Programa.objects.create(nombre="Programa cache", codigo="CACHE")

    def _calentar(self):
        """Deja las tres claves escritas, como después de un render de la home."""
        contar_ciudadanos()
        contar_legajos()
        contar_alertas_activas()

    def test_el_andamio_calienta_las_tres_claves(self):
        """Control: sin esto, un `assertIsNone` pasaría porque la clave nunca existió."""
        self._calentar()

        for clave in ("contar_ciudadanos", "stats_legajos", "alertas_activas"):
            with self.subTest(clave=clave):
                self.assertIsNotNone(cache.get(clave))

    def test_ciudadano_nuevo_invalida_contar_ciudadanos(self):
        """El único de los tres que anda hoy: lo cablea `core/performance/cache_utils.py`.

        Es también el que la limpieza de OPS-10 puede romper sin querer, si «deduplica»
        quedándose con la función de `dashboard/utils.py`, que no tiene señales.

        Desde PERF-04 el borrado va en un `on_commit`: fuera de una transacción corre en
        el acto, pero dentro de un `TestCase` —que envuelve cada test— hay que soltarlo
        a mano. Lo que se afirma sigue siendo lo mismo: el alta invalida el contador.
        """
        self._calentar()

        with self.captureOnCommitCallbacks(execute=True):
            Ciudadano.objects.create(nombre="Beto", apellido="Gómez", dni="20333444")

        self.assertIsNone(cache.get("contar_ciudadanos"))

    def test_editar_un_ciudadano_no_invalida_los_contadores(self):
        """PERF-16: un `save()` que no crea ni borra no cambia ningún total, y el cruce
        del padrón llegó a disparar 26.668 `cache.delete` por ese camino. Lo que sí tiene
        que seguir invalidándose es la ficha del ciudadano tocado."""
        self._calentar()
        cache.set(f"ciudadano_{self.ciudadano.pk}", "viejo", 300)

        with self.captureOnCommitCallbacks(execute=True):
            self.ciudadano.telefono = "3624000111"
            self.ciudadano.save(update_fields=["telefono", "modificado"])

        self.assertIsNotNone(cache.get("contar_ciudadanos"))
        self.assertIsNone(cache.get(f"ciudadano_{self.ciudadano.pk}"))

    def test_borrar_un_ciudadano_si_invalida_el_contador(self):
        """`post_delete` no manda `created` y ahí el total **sí** cambió: el default del
        `get` tiene que dejarlo pasar."""
        self._calentar()

        with self.captureOnCommitCallbacks(execute=True):
            self.ciudadano.delete()

        self.assertIsNone(cache.get("contar_ciudadanos"))

    def test_usuario_nuevo_invalida_contar_usuarios(self):
        """El otro receiver cableado, por el mismo camino.

        Desde RED-51 el borrado va en un `on_commit`, como el de `Ciudadano`: invalidar
        antes del commit deja que otro request vuelva a cachear el valor **viejo**, y si
        la transacción termina en rollback se borró por nada. Dentro de un `TestCase` hay
        que soltarlo a mano; lo que se afirma es lo mismo.
        """
        from django.contrib.auth import get_user_model

        contar_usuarios_valor = cache.get("contar_usuarios")
        self.assertIsNone(contar_usuarios_valor)
        from dashboard.utils import contar_usuarios

        contar_usuarios()

        with self.captureOnCommitCallbacks(execute=True):
            get_user_model().objects.create_user(username="cache_user", password="x")

        self.assertIsNone(cache.get("contar_usuarios"))

    def test_un_usuario_nuevo_no_invalida_el_contador_de_ciudadanos(self):
        """RED-51 · el receiver de `User` borraba también `contar_ciudadanos`.

        Dar de alta a alguien del backoffice no cambia cuántos ciudadanos hay: la home
        recalculaba un total que no se había movido. La tabla de `dashboard/cache.py`
        dice qué mueve cada modelo y este test fija que `auth.user` no mueve ese.
        """
        from django.contrib.auth import get_user_model

        self._calentar()

        with self.captureOnCommitCallbacks(execute=True):
            get_user_model().objects.create_user(username="cache_user_2", password="x")

        self.assertIsNotNone(cache.get("contar_ciudadanos"))

    def test_el_login_no_invalida_los_contadores(self):
        """`update_last_login` guarda el User en cada login y no cambia ningún
        contador: el receiver lo saltea a propósito. Perder esa rama hace que la home
        recalcule todo en cada ingreso."""
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        usuario = get_user_model().objects.create_user(username="cache_login", password="x")
        self._calentar()

        usuario.last_login = timezone.now()
        usuario.save(update_fields=["last_login"])

        self.assertIsNotNone(cache.get("contar_ciudadanos"))

    def test_inscripcion_nueva_invalida_stats_legajos(self):
        """RED-51 — estaba en `expectedFailure` y la Ola 4 lo pone en verde.

        `stats_legajos` lo escribe `contar_legajos()`, que agrega sobre
        `InscripcionPrograma`; el único receiver que borraba esa clave estaba colgado de
        `LegajoAtencion`. Ahora la borra el receiver de `dashboard/signals/cache.py`, con
        el `sender` correcto. Sin eso, el número de legajos de la home quedaba viejo
        hasta que expirara el TTL.
        """
        self._calentar()
        total_antes = cache.get("stats_legajos")["total"]

        with self.captureOnCommitCallbacks(execute=True):
            InscripcionPrograma.objects.create(ciudadano=self.ciudadano, programa=self.programa)

        self.assertIsNone(
            cache.get("stats_legajos"),
            f"la clave sigue cacheada en {total_antes}: el receiver mira el modelo equivocado.",
        )

    def test_inscripcion_nueva_invalida_el_contador_del_dia(self):
        """La segunda clave que escribe el mismo modelo: `contar_seguimientos_hoy()`
        filtra `InscripcionPrograma` por `fecha_inscripcion` del día local."""
        from dashboard.cache import clave_seguimientos_hoy
        from dashboard.utils import contar_seguimientos_hoy

        contar_seguimientos_hoy()
        self.assertIsNotNone(cache.get(clave_seguimientos_hoy()))

        with self.captureOnCommitCallbacks(execute=True):
            InscripcionPrograma.objects.create(ciudadano=self.ciudadano, programa=self.programa)

        self.assertIsNone(cache.get(clave_seguimientos_hoy()))

    def test_un_legajo_de_atencion_ya_no_invalida_stats_legajos(self):
        """La otra mitad del bug: el receiver de `LegajoAtencion` refrescaba un contador
        de inscripciones que no había cambiado. Lo suyo —`stats_legajos_atencion`— lo
        sigue borrando, y eso lo fija el test de al lado."""
        self._calentar()

        with self.captureOnCommitCallbacks(execute=True):
            LegajoAtencion.objects.create()

        self.assertIsNotNone(cache.get("stats_legajos"))

    def test_un_legajo_de_atencion_invalida_su_propio_contador(self):
        """El receiver que el arreglo **no** podía perder al mover el `sender`: la
        tarjeta «Legajos activos» del inicio lee `stats_legajos_atencion` (G2-04)."""
        from dashboard.utils import contar_legajos_atencion

        contar_legajos_atencion()
        self.assertIsNotNone(cache.get("stats_legajos_atencion"))

        with self.captureOnCommitCallbacks(execute=True):
            LegajoAtencion.objects.create()

        self.assertIsNone(cache.get("stats_legajos_atencion"))

    def test_alerta_nueva_invalida_alertas_activas(self):
        """RED-51 — estaba en `expectedFailure` y la Ola 4 lo pone en verde.

        `contar_alertas_activas()` cachea `alertas_activas` 60 s y nadie borraba esa
        clave cuando nacía una alerta: solo la limpiaba el alta o la edición de un
        **ciudadano**. El badge de alertas de la home podía tardar un minuto en reflejar
        una alerta crítica nueva.
        """
        self._calentar()

        with self.captureOnCommitCallbacks(execute=True):
            AlertaCiudadano.objects.create(
                ciudadano=self.ciudadano,
                tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
                prioridad=AlertaCiudadano.Prioridad.CRITICA,
                mensaje="Alerta de prueba",
            )

        self.assertIsNone(cache.get("alertas_activas"))

    def test_cerrar_una_alerta_tambien_invalida_el_badge(self):
        """`alertas_activas` cuenta `activa=True`: bajarle la bandera a una alerta cambia
        el número igual que crearla. El receiver escucha `post_save`, no solo el alta."""
        alerta = AlertaCiudadano.objects.create(
            ciudadano=self.ciudadano,
            tipo=AlertaCiudadano.TipoAlerta.RIESGO_ALTO,
            prioridad=AlertaCiudadano.Prioridad.CRITICA,
            mensaje="Alerta de prueba",
        )
        self._calentar()

        with self.captureOnCommitCallbacks(execute=True):
            alerta.activa = False
            alerta.save(update_fields=["activa", "modificado"])

        self.assertIsNone(cache.get("alertas_activas"))

    def test_el_alta_de_un_ciudadano_si_limpia_alertas_activas(self):
        """Por dónde se limpia hoy, que es el camino que no hay que perder: la vista de
        alta de ciudadanos llama a `CiudadanosService.invalidate_ciudadanos_cache()`."""
        from legajos.services.ciudadanos import CiudadanosService

        self._calentar()

        CiudadanosService.invalidate_ciudadanos_cache()

        self.assertIsNone(cache.get("alertas_activas"))


class _FuentesDelRepo:
    """Los `.py` del proyecto, sin tests ni migraciones ni entornos virtuales."""

    APPS = ("conversaciones", "core", "dashboard", "legajos", "portal", "programas", "users", "config")

    @classmethod
    def archivos(cls):
        for app in cls.APPS:
            for ruta in (RAIZ / app).rglob("*.py"):
                partes = ruta.relative_to(RAIZ).parts
                if "migrations" in partes or "tests" in partes:
                    continue
                yield ruta


class UnaSolaFuncionTests(TestCase):
    """RED-51 invertido: la duplicación no puede volver (antes `DosFuncionesTests`)."""

    def test_no_quedan_dos_funciones_llamadas_invalidate_dashboard_cache(self):
        """El nombre homónimo desapareció del código de producción.

        No alcanza con que hoy haya una: el riesgo era que OPS-10 «dedupicara» dos
        funciones con el mismo nombre y distintas claves. Este test recorre las fuentes
        con `ast` y falla si el nombre vuelve a definirse **en cualquier lado**.
        """
        definiciones = []
        for ruta in _FuentesDelRepo.archivos():
            arbol = ast.parse(ruta.read_text(encoding="utf-8"))
            definiciones += [
                f"{ruta.relative_to(RAIZ).as_posix()}:{nodo.lineno}"
                for nodo in ast.walk(arbol)
                if isinstance(nodo, ast.FunctionDef) and nodo.name == "invalidate_dashboard_cache"
            ]

        self.assertEqual(
            definiciones,
            [],
            "`invalidate_dashboard_cache` volvió: la única función que borra los "
            "contadores de la home es `dashboard.cache.invalidar_dashboard`.\n" + "\n".join(definiciones),
        )

    def test_la_funcion_unica_borra_todas_las_claves_de_la_tabla(self):
        """El ratchet que reemplaza al de las dos funciones: la que queda borra **todo**
        lo que la tabla declara. Si alguien agrega un contador al mapa y la función deja
        de cubrirlo, acá se ve."""
        from dashboard.cache import invalidar_dashboard, todas_las_claves

        cache.clear()
        self.addCleanup(cache.clear)
        claves = todas_las_claves()
        self.assertGreaterEqual(len(claves), 6)
        for clave in claves:
            cache.set(clave, "valor", 300)

        invalidar_dashboard()

        self.assertEqual({c for c in claves if cache.get(c) is not None}, set())

    def test_la_tabla_nombra_modelos_que_existen(self):
        """Un `label_lower` mal escrito en el mapa deja la clave sin invalidar y nada
        falla: `claves_de` devuelve una tupla vacía y el receiver borra cero."""
        from django.apps import apps

        from dashboard.cache import CLAVES_POR_MODELO

        for etiqueta in CLAVES_POR_MODELO:
            with self.subTest(modelo=etiqueta):
                self.assertIsNotNone(apps.get_model(etiqueta))

    def test_cada_clave_cacheada_tiene_un_modelo_que_la_invalida(self):
        """La mitad que faltaba: todo contador de `dashboard/utils.py` que escriba una
        clave tiene que estar en la tabla. Agregar uno sin su modelo es volver al bug
        original —un número que nadie refresca— y acá queda rojo."""
        from dashboard.cache import todas_las_claves
        from dashboard.utils import (
            contar_alertas_activas,
            contar_legajos_atencion,
            contar_seguimientos_hoy,
            contar_usuarios,
        )

        cache.clear()
        self.addCleanup(cache.clear)
        for contador in (
            contar_usuarios,
            contar_ciudadanos,
            contar_legajos,
            contar_legajos_atencion,
            contar_seguimientos_hoy,
            contar_alertas_activas,
        ):
            contador()

        escritas = {c for c in todas_las_claves() if cache.get(c) is not None}

        self.assertEqual(len(escritas), len(todas_las_claves()))

    def test_el_servicio_de_ciudadanos_tiene_llamadores(self):
        """Desvío de la ficha, verificado contra el código: la ficha decía que
        `CiudadanosService.invalidate_ciudadanos_cache` no tenía llamadores. Los tiene
        —las tres vistas de ciudadanos—, así que esa limpieza **sí** se ejecuta en
        producción y borrarla no es gratis.
        """
        fuente = (RAIZ / "legajos" / "views" / "ciudadanos.py").read_text(encoding="utf-8")
        arbol = ast.parse(fuente)
        llamadas = [
            nodo
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr == "invalidate_ciudadanos_cache"
        ]

        self.assertEqual(len(llamadas), 3)
