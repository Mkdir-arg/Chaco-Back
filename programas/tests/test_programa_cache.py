"""RED-80 — ``programa_becas`` y ``programa_dispositivos`` comparten pieza e invalidación.

Antes eran dos copias del mismo patrón con distinta guarda: la clave de Becas la borraba
``seed_becas`` (y fallaba *best-effort* si el cache no respondía); la de Dispositivos
**no la borraba nadie**. Un restore que recrea la fila con otro pk —o el wizard, que deja
cambiar el código de un programa— dejaba 300 s de evaluaciones contra una fila que ya no
existe: en Dispositivos «nadie entra», en Becas un 403 (RED-56).
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from core import rbac
from core.models import Secretaria, Subsecretaria
from programas.models import Programa
from programas.services.autorizacion import _PROGRAMA_BECAS_CACHE_KEY, programa_becas
from programas.services.dispositivos import _CACHE_KEY as CLAVE_DISPOSITIVOS
from programas.services.dispositivos import programa_dispositivos
from programas.services.programa_cache import clave_de, invalidar_programa, programa_por_codigo
from users.models import Capacidad, RolMeta


class ClavesDerivadasTests(TestCase):
    def test_las_dos_claves_historicas_salen_de_la_misma_funcion(self):
        """Las claves no cambian de nombre: una base con Redis vivo no pierde lo que ya
        tiene cacheado el día del deploy."""
        self.assertEqual(clave_de("BECAS"), "programas:becas")
        self.assertEqual(clave_de("DISPOSITIVOS"), "programas:dispositivos")
        self.assertEqual(_PROGRAMA_BECAS_CACHE_KEY, "programas:becas")
        self.assertEqual(CLAVE_DISPOSITIVOS, "programas:dispositivos")


class CacheProgramaTests(TestCase):
    def setUp(self):
        cache.clear()
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.dispositivos = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")

    def test_la_consulta_se_cachea_y_la_invalidacion_la_borra(self):
        self.assertEqual(programa_por_codigo("DISPOSITIVOS"), self.dispositivos)
        self.assertEqual(cache.get("programas:dispositivos"), self.dispositivos)

        invalidar_programa("DISPOSITIVOS")

        self.assertIsNone(cache.get("programas:dispositivos"))

    def test_un_programa_que_no_esta_no_se_cachea(self):
        """Cachear el ``None`` dejaría al sistema sin ese programa durante 300 s por una
        lectura hecha en el peor momento (un pod que arranca antes del bootstrap)."""
        self.assertIsNone(programa_por_codigo("MERENDEROS"))
        self.assertIsNone(cache.get("programas:merenderos"))

        Programa.objects.create(codigo="MERENDEROS", nombre="Merenderos")

        self.assertIsNotNone(programa_por_codigo("MERENDEROS"))

    def test_el_memo_por_request_no_mezcla_programas(self):
        """El memo vive en el objeto ``user`` y antes eran dos atributos distintos; ahora
        es un dict por código y tiene que seguir distinguiéndolos."""
        usuario = User.objects.create_user("memo-red80", password="x")

        self.assertEqual(programa_becas(usuario), self.becas)
        self.assertEqual(programa_dispositivos(usuario), self.dispositivos)
        self.assertEqual(usuario._programas_por_codigo, {"BECAS": self.becas, "DISPOSITIVOS": self.dispositivos})

    def test_la_invalidacion_no_rompe_si_el_cache_no_responde(self):
        """El seed corre en el arranque del contenedor: un Redis caído no puede dejar el
        pod en CrashLoopBackOff (OPS-12)."""
        from unittest.mock import patch

        with patch("programas.services.programa_cache.cache.delete", side_effect=RuntimeError("redis caído")):
            with self.assertLogs("programas.services.programa_cache", level="WARNING") as log:
                invalidar_programa("BECAS")

        self.assertIn("programas:becas", log.output[0])


class ElWizardInvalidaTests(TestCase):
    """Quien **escribe** un ``Programa`` es quien tiene que borrar su clave.

    Desde el Cambio 197 el ``cache.delete`` va en un ``transaction.on_commit``: hacerlo
    adentro de la transacción deja que otra request lea la fila **anterior** —que hasta
    el COMMIT sigue siendo la commiteada— y la recachee 300 s, que es justo el modo de
    falla que RED-80 fue a cerrar. Dentro de un ``TestCase`` los callbacks hay que
    soltarlos a mano (``captureOnCommitCallbacks``); lo que afirma cada test es lo mismo
    que antes. Que el borrado **espere** al COMMIT lo prueba
    ``programas.tests.test_ola7_pr3.InvalidacionAlCommitTests``.
    """

    def setUp(self):
        cache.clear()
        secretaria = Secretaria.objects.create(nombre="Sec")
        self.subsecretaria = Subsecretaria.objects.create(nombre="Subsec", secretaria=secretaria)
        self.dispositivos = Programa.objects.create(
            codigo="DISPOSITIVOS",
            nombre="Dispositivos",
            subsecretaria=self.subsecretaria,
            naturaleza=Programa.Naturaleza.PERSISTENTE,
        )
        self.operador = User.objects.create_user("cfg-red80", password="Clave-Seg-2026x")
        grupo = Group.objects.create(name="Config global red80")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        grupo.permissions.add(Permission.objects.get(codename="programa_configurar", content_type=ct))
        self.operador.groups.add(grupo)
        self.client.force_login(self.operador)

    def test_cambiar_el_estado_borra_la_clave(self):
        programa_por_codigo("DISPOSITIVOS")  # la deja cacheada
        self.assertIsNotNone(cache.get("programas:dispositivos"))

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("configuracion:programa_cambiar_estado", args=[self.dispositivos.pk]),
                {"estado": Programa.Estado.SUSPENDIDO},
            )

        self.assertIsNone(cache.get("programas:dispositivos"))

    def test_cambiarle_el_codigo_borra_la_vieja_y_la_nueva(self):
        """El paso 1 del wizard deja editar el **código**: si solo se borrara la clave
        nueva, los pods seguirían resolviendo el código viejo contra la fila vieja."""
        programa_por_codigo("DISPOSITIVOS")
        cache.set("programas:dispositivos-v2", self.dispositivos, 300)
        sesion = self.client.session
        sesion[f"wizard_programa_{self.dispositivos.pk}"] = {
            "paso1": {
                "nombre": "Dispositivos v2",
                "codigo": "DISPOSITIVOS-V2",
                "descripcion": "",
                "secretaria": self.subsecretaria.secretaria_id,
                "subsecretaria": self.subsecretaria.pk,
            },
            "paso2": {"naturaleza": Programa.Naturaleza.PERSISTENTE},
            "paso3": {"cupo_maximo": None, "tiene_lista_espera": False},
        }
        sesion.save()

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("configuracion:programa_editar_paso4", args=[self.dispositivos.pk]),
                {"icono": "folder", "color": "#6366f1", "orden": "0"},
            )

        self.dispositivos.refresh_from_db()
        self.assertEqual(self.dispositivos.codigo, "DISPOSITIVOS-V2")
        self.assertIsNone(cache.get("programas:dispositivos"))
        self.assertIsNone(cache.get("programas:dispositivos-v2"))


class SenalesDeProgramaTests(TestCase):
    """RED-80, ronda 2: la invalidación va pegada al modelo, no a una pantalla.

    La resolución del PR afirmaba que el wizard «es la única pantalla que escribe un
    ``Programa``». No lo es: ``/admin/`` está ruteado (``config/urls.py``) y
    ``ProgramaAdmin`` deja cambiar el ``codigo`` y el ``estado``, y **borrar**. Con las
    señales queda cubierto cualquier camino, incluido el que no existe todavía.

    El ``captureOnCommitCallbacks`` es del Cambio 197: ver la nota de
    :class:`ElWizardInvalidaTests`.
    """

    def setUp(self):
        cache.clear()
        self.dispositivos = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")

    def test_guardar_el_programa_borra_su_clave(self):
        programa_por_codigo("DISPOSITIVOS")
        self.assertIsNotNone(cache.get("programas:dispositivos"))

        with self.captureOnCommitCallbacks(execute=True):
            self.dispositivos.estado = Programa.Estado.SUSPENDIDO
            self.dispositivos.save(update_fields=["estado"])

        self.assertIsNone(cache.get("programas:dispositivos"))

    def test_cambiarle_el_codigo_borra_la_vieja_y_la_nueva(self):
        programa_por_codigo("DISPOSITIVOS")
        cache.set("programas:otro", self.dispositivos, 300)

        with self.captureOnCommitCallbacks(execute=True):
            self.dispositivos.codigo = "OTRO"
            self.dispositivos.save()

        self.assertIsNone(cache.get("programas:dispositivos"))
        self.assertIsNone(cache.get("programas:otro"))

    def test_borrarlo_borra_su_clave(self):
        programa_por_codigo("DISPOSITIVOS")
        self.assertIsNotNone(cache.get("programas:dispositivos"))

        with self.captureOnCommitCallbacks(execute=True):
            self.dispositivos.delete()

        self.assertIsNone(cache.get("programas:dispositivos"))
        self.assertIsNone(programa_por_codigo("DISPOSITIVOS"))

    def test_el_admin_de_django_tambien(self):
        """El camino reportado: ``ProgramaAdmin.save_model``."""
        from django.contrib.admin.sites import site
        from django.test import RequestFactory

        programa_por_codigo("DISPOSITIVOS")
        self.dispositivos.codigo = "DISPOSITIVOS-ADMIN"
        admin = site._registry[Programa]

        with self.captureOnCommitCallbacks(execute=True):
            admin.save_model(RequestFactory().post("/admin/"), self.dispositivos, None, True)

        self.assertIsNone(cache.get("programas:dispositivos"))

    def test_el_alta_no_envenena_la_clave(self):
        """Un ``Programa`` nuevo no tiene código anterior y nadie cachea el ``None``."""
        self.assertIsNone(programa_por_codigo("MERENDEROS"))

        merenderos = Programa.objects.create(codigo="MERENDEROS", nombre="Merenderos")

        self.assertEqual(programa_por_codigo("MERENDEROS"), merenderos)
