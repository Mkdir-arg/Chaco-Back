"""El motivo de un error AJAX llega en la clave que el front lee (RED-39).

Cinco sobres distintos conviven en el backoffice y cada consumidor lee uno solo,
con un `||` de fallback que tapa la diferencia. Mientras la migración al sobre
único (`core/http.py`) no llegue —es de la Ola 7—, estos tests congelan **la
clave de hoy** de los dos consumidores que el usuario nota enseguida:

- el constructor de formularios (`static/custom/js/nodo-constructor.js:133` lee
  `data.message`): si el motivo se va a `detail`, el coordinador ve «No se pudo
  guardar. Recargá la página.» y no entiende por qué;
- la subida de archivos del detalle de ciudadano
  (`legajos/templates/legajos/ciudadano_detail.html` lee `data.error`): si el
  motivo se va a `message`, «Formato no permitido» se convierte en un error
  genérico.

Más los helpers nuevos, que son el destino de la migración.
"""

import json
from datetime import date
from io import StringIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core import rbac
from core.http import error_json, ok_json
from legajos.models import Ciudadano
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import Convocatoria, RequisitoNativo, Segmento, TipoCampo
from programas.services.diseno import clave_requisito, obtener_o_crear_diseno
from users.models import Capacidad, RolMeta


class SobreUnicoTests(SimpleTestCase):
    """`core/http.py`: la pieza a la que migran las vistas en la Ola 7."""

    def test_error_json_arma_el_sobre_del_constructor(self):
        cuerpo = json.loads(error_json("Falta el catálogo.").content)

        self.assertEqual(cuerpo, {"ok": False, "message": "Falta el catálogo."})

    def test_error_json_responde_400_por_defecto_y_acepta_otro_status(self):
        self.assertEqual(error_json("x").status_code, 400)
        self.assertEqual(error_json("x", status=409).status_code, 409)

    def test_error_json_suma_el_detalle_solo_cuando_lo_hay(self):
        con_detalle = json.loads(error_json("No cierra", errores=["Falta «Nivel»"]).content)
        sin_detalle = json.loads(error_json("No cierra", errores=[]).content)

        self.assertEqual(con_detalle["errores"], ["Falta «Nivel»"])
        self.assertNotIn("errores", sin_detalle)

    def test_ok_json_pone_la_bandera_y_no_se_puede_pisar(self):
        self.assertEqual(json.loads(ok_json(html="<ul></ul>").content), {"ok": True, "html": "<ul></ul>"})
        with self.assertRaises(TypeError):
            ok_json(ok=False)

    def test_las_heredadas_viajan_ademas_del_sobre(self):
        """Migrar es sumar: el front instalado sigue leyendo su clave de siempre."""
        cuerpo = json.loads(error_json("No se pudo", heredadas={"success": False, "error": "No se pudo"}).content)

        self.assertEqual(cuerpo, {"ok": False, "message": "No se pudo", "success": False, "error": "No se pudo"})

    def test_las_heredadas_tambien_valen_en_el_camino_feliz(self):
        cuerpo = json.loads(ok_json(archivos=[], heredadas={"success": True, "mensaje": "1 archivo"}).content)

        self.assertEqual(cuerpo, {"ok": True, "archivos": [], "success": True, "mensaje": "1 archivo"})

    def test_una_heredada_no_puede_pisar_el_sobre(self):
        """Si `heredadas` pudiera redefinir `message`, el sobre dejaría de ser único
        justo en la vista que se está migrando."""
        for clave in ("ok", "message"):
            with self.subTest(clave=clave):
                with self.assertRaises(TypeError):
                    error_json("x", heredadas={clave: "otra cosa"})
                with self.assertRaises(TypeError):
                    ok_json(heredadas={clave: "otra cosa"})


class SobreDeErrorTests(TestCase):
    """RED-39: cada consumidor sigue recibiendo el motivo en SU clave."""

    def setUp(self):
        # La subida feliz escribe un archivo de verdad: sin esto va al `MEDIA_ROOT`
        # real del repo y queda ahí (mismo patrón que `legajos/tests/test_adjuntos_rbac`).
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        contexto = override_settings(MEDIA_ROOT=self.media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)

    def test_el_constructor_devuelve_el_motivo_en_message(self):
        call_command("seed_becas", stdout=StringIO())
        admin = User.objects.create_user("admin-sobre", password="Clave-Seg-2026x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)
        segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo", tipo=TipoCampo.STRING, segmento=segmento, orden=1
        )
        obtener_o_crear_diseno(convocatoria)

        respuesta = self.client.post(
            reverse("becas:formulario_item_eliminar", args=[convocatoria.pk, clave_requisito(nivel)]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(respuesta.status_code, 400)
        cuerpo = respuesta.json()
        self.assertIn("catálogo", cuerpo["message"])
        self.assertIs(cuerpo["ok"], False)

    def test_subir_archivos_devuelve_el_motivo_en_error(self):
        """La clave de hoy en legajos es `error` (no `message` ni `mensaje`)."""
        agente = User.objects.create_user("agente-subida", password="Clave-Seg-2026x")
        grupo = Group.objects.create(name="Carga de archivos")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de("ciudadano.editar"), content_type=ct))
        agente.groups.add(grupo)
        self.client.force_login(agente)
        ciudadano = Ciudadano.objects.create(dni="30444555", nombre="Ema", apellido="Rios")

        respuesta = self.client.post(
            reverse("legajos:subir_archivos_ciudadano", args=[ciudadano.id]),
            {"archivo": SimpleUploadedFile("virus.exe", b"MZ")},
        )

        self.assertEqual(respuesta.status_code, 400)
        cuerpo = respuesta.json()
        self.assertIn("Formato no permitido", cuerpo["error"])
        self.assertIs(cuerpo["success"], False)

    def test_subir_archivos_exitosa_devuelve_el_resumen_en_mensaje(self):
        """Y el camino feliz usa `mensaje`, que es una quinta clave más."""
        agente = User.objects.create_user("agente-subida-ok", password="Clave-Seg-2026x")
        grupo = Group.objects.create(name="Carga de archivos OK")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de("ciudadano.editar"), content_type=ct))
        agente.groups.add(grupo)
        self.client.force_login(agente)
        ciudadano = Ciudadano.objects.create(dni="30444666", nombre="Fito", apellido="Paez")

        cuerpo = self.client.post(
            reverse("legajos:subir_archivos_ciudadano", args=[ciudadano.id]),
            {"archivo": SimpleUploadedFile("nota.pdf", b"%PDF-1.4")},
        ).json()

        self.assertIs(cuerpo["success"], True)
        self.assertIn("1 archivo(s)", cuerpo["mensaje"])


class MigracionAlSobreUnicoTests(TestCase):
    """RED-39 (Ola 7): las dos primeras apps migradas hablan los dos idiomas.

    La migración es **aditiva**: `ok` y `message` entran, y las claves que el
    front de hoy lee —`success`, `error`, `mensaje`— siguen viajando. Es la única
    forma de migrar un front que no se despliega con el backend: una pantalla
    abierta durante el deploy sigue leyendo las viejas, y la app de campo es una
    build instalada en el teléfono del territorial.

    Los tests de `SobreDeErrorTests` miden la mitad vieja; estos, la nueva. Las
    dos tienen que estar en verde a la vez hasta que se mida que nadie lee las
    viejas, y recién ahí se borran los `heredadas`.
    """

    @classmethod
    def setUpTestData(cls):
        cls.agente = User.objects.create_user("agente-migrado", password="Clave-Seg-2026x")
        grupo = Group.objects.create(name="Rol migrado")
        RolMeta.objects.create(grupo=grupo, categoria=rbac.CATEGORIA_BACKOFFICE, activo=True)
        ct = ContentType.objects.get_for_model(Capacidad)
        for codigo in ("ciudadano.ver", "ciudadano.editar", "ciudadano.sensible"):
            grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
        cls.agente.groups.add(grupo)
        cls.ciudadano = Ciudadano.objects.create(dni="30555777", nombre="Ivo", apellido="Luna")

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        contexto = override_settings(MEDIA_ROOT=self.media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.client.force_login(self.agente)

    def test_el_error_de_la_subida_trae_el_sobre_nuevo_y_el_viejo(self):
        respuesta = self.client.post(
            reverse("legajos:subir_archivos_ciudadano", args=[self.ciudadano.id]),
            {"archivo": SimpleUploadedFile("virus.exe", b"MZ")},
        )

        cuerpo = respuesta.json()
        self.assertEqual(respuesta.status_code, 400)
        self.assertIs(cuerpo["ok"], False)
        self.assertEqual(cuerpo["message"], cuerpo["error"])
        self.assertIs(cuerpo["success"], False)
        self.assertIn("Formato no permitido", cuerpo["message"])

    def test_la_subida_feliz_trae_el_resumen_en_las_dos_claves(self):
        cuerpo = self.client.post(
            reverse("legajos:subir_archivos_ciudadano", args=[self.ciudadano.id]),
            {"archivo": SimpleUploadedFile("nota.pdf", b"%PDF-1.4")},
        ).json()

        self.assertIs(cuerpo["ok"], True)
        self.assertEqual(cuerpo["message"], cuerpo["mensaje"])
        self.assertIs(cuerpo["success"], True)
        self.assertIn("archivos", cuerpo)

    def test_el_metodo_no_permitido_tambien_pasa_por_el_sobre(self):
        """El 405 era un literal suelto en cada una de las cinco vistas."""
        respuesta = self.client.get(reverse("legajos:subir_archivos_ciudadano", args=[self.ciudadano.id]))

        cuerpo = respuesta.json()
        self.assertEqual(respuesta.status_code, 405)
        self.assertEqual(
            cuerpo, {"ok": False, "message": "Método no permitido", "success": False, "error": "Método no permitido"}
        )

    def test_cerrar_una_alerta_inexistente_devuelve_404_con_las_dos_banderas(self):
        respuesta = self.client.post(reverse("legajos:cerrar_alerta_ciudadano", args=[999999]))

        cuerpo = respuesta.json()
        self.assertEqual(respuesta.status_code, 404)
        self.assertIs(cuerpo["ok"], False)
        self.assertIs(cuerpo["success"], False)
        self.assertEqual(cuerpo["message"], "Alerta no encontrada")

    def test_el_constructor_ya_hablaba_el_sobre_y_lo_sigue_hablando(self):
        """`diseno.py` migró a `core/http.py` sin cambiar una sola clave: ya
        devolvía `{"ok", "message", "errores"}`. Lo que este test fija es que el
        helper no agregó ni sacó nada por el camino."""
        call_command("seed_becas", stdout=StringIO())
        admin = User.objects.create_user("admin-migrado", password="Clave-Seg-2026x")
        admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.client.force_login(admin)
        segmento = Segmento.objects.create(nombre="Salud", cupo_maximo=5)
        convocatoria = Convocatoria.objects.create(
            nombre="Becas salud",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        nivel = RequisitoNativo.objects.create(texto="Obra social", tipo=TipoCampo.STRING, segmento=segmento, orden=1)
        obtener_o_crear_diseno(convocatoria)

        cuerpo = self.client.post(
            reverse("becas:formulario_item_eliminar", args=[convocatoria.pk, clave_requisito(nivel)]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        ).json()

        self.assertEqual(set(cuerpo), {"ok", "message"})
        self.assertIs(cuerpo["ok"], False)
