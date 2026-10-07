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

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
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


class SobreDeErrorTests(TestCase):
    """RED-39: cada consumidor sigue recibiendo el motivo en SU clave."""

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
