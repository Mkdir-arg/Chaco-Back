"""Ola 2 PR 1 — G1b-02, G1b-06 y la migración de SEC-06.

PoC invertidas de `poc/test_repro_usuarios.py`:

* ``G1b02EscaladaDentroDelProgramaTests`` — (a) quien solo tenía
  ``programa.rol.administrar`` editaba **su propio rol**, se tildaba
  ``programa.usuario.administrar`` y ``programa.configurar`` y pasaba de 302 a 200 en
  ``/usuarios/``; (b) quien solo tenía ``programa.usuario.administrar`` se asignaba un rol
  del programa que traía ``programa.rol.administrar``.
* ``G1b06CapsGlobalesBorradasTests`` — el admin de programa guardaba un rol cambiándole la
  descripción y le borraba en silencio el ``ciudadano.ver`` que le había puesto el admin
  global.
"""

import logging

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from zeal import zeal_ignore

from core import rbac
from programas.models import Programa
from users.models import Capacidad, CapacidadRevocada, RolMeta


def _perm(codigo):
    ct = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct)


def _rol(nombre, capacidades, programa=None, categoria=None):
    grupo = Group.objects.create(name=nombre)
    RolMeta.objects.create(
        grupo=grupo,
        categoria=categoria or (rbac.CATEGORIA_PROGRAMA if programa else rbac.CATEGORIA_SISTEMA),
        programa=programa,
        activo=True,
    )
    for codigo in capacidades:
        grupo.permissions.add(_perm(codigo))
    return grupo


def _usuario(username, *roles):
    usuario = User.objects.create_user(username, password="Clave-Seg-2026x")
    for rol in roles:
        usuario.groups.add(rol)
    return usuario


class Base(TestCase):
    def setUp(self):
        self.becas = Programa.objects.create(codigo="BECAS", nombre="Becas")
        self.dispositivos = Programa.objects.create(codigo="DISPOSITIVOS", nombre="Dispositivos")
        # Admin global presente para que la auto-protección del RBAC no salte.
        self.root = _usuario("root-g1b02", _rol("Admins", ["usuario.administrar", "rol.administrar"]))


class G1b02EscaladaDentroDelProgramaTests(Base):
    def test_admin_roles_no_se_da_admin_usuarios_editando_su_rol(self):
        """La PoC (a) invertida. Dos candados independientes la cierran: el rol propio
        no se edita, y las dos transversales no están entre las delegables."""
        rol = _rol("RA Becas", ["programa.rol.administrar"], self.becas)
        operador = _usuario("solo-roles", rol)
        self.client.force_login(operador)
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 302)

        with zeal_ignore():
            respuesta = self.client.post(
                reverse("users:rol_editar", args=[rol.pk]),
                {
                    "name": "RA Becas",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.becas.pk),
                    "capacidades": [
                        "programa.rol.administrar",
                        "programa.usuario.administrar",
                        "programa.configurar",
                    ],
                },
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("users:roles"))
        operador = User.objects.get(pk=operador.pk)
        self.assertFalse(rbac.puede(operador, "programa.usuario.administrar"))
        self.assertFalse(rbac.puede(operador, "programa.configurar"))
        self.assertEqual(rbac.capacidades_de_grupo(rol), ["programa.rol.administrar"])
        self.client.force_login(operador)
        self.assertEqual(self.client.get(reverse("users:usuarios")).status_code, 302)

    def test_el_rol_propio_tampoco_se_borra_ni_se_desactiva(self):
        """La otra mitad de ``puede_editar_rol``: no alcanza con frenar el guardado."""
        rol = _rol("RA Becas borrar", ["programa.rol.administrar"], self.becas)
        self.client.force_login(_usuario("solo-roles-borra", rol))

        self.assertEqual(
            self.client.post(reverse("users:rol_eliminar", args=[rol.pk]))["Location"], reverse("users:roles")
        )
        self.assertTrue(Group.objects.filter(pk=rol.pk).exists())
        self.client.post(reverse("users:rol_toggle", args=[rol.pk]))
        self.assertTrue(RolMeta.objects.get(grupo=rol).activo)

    def test_pero_sigue_viendo_su_propio_rol(self):
        """Ver no es editar: la ficha del rol propio se abre, y el listado lo muestra
        sin las acciones."""
        rol = _rol("RA Becas ver", ["programa.rol.administrar"], self.becas)
        self.client.force_login(_usuario("solo-roles-ve", rol))

        self.assertEqual(self.client.get(reverse("users:rol_detalle", args=[rol.pk])).status_code, 200)

        listado = self.client.get(reverse("users:roles"))
        editables = {it["group"].name: it["puede_editar"] for it in listado.context["items"]}
        self.assertEqual(editables, {"RA Becas ver": False})

    def test_y_si_edita_otro_rol_del_programa_tampoco_delega_la_administracion(self):
        rol_admin = _rol("RA Becas delega", ["programa.rol.administrar"], self.becas)
        otro = _rol("Operativo Becas", ["becas.segmento.ver"], self.becas)
        self.client.force_login(_usuario("solo-roles-delega", rol_admin))

        with zeal_ignore():
            self.client.post(
                reverse("users:rol_editar", args=[otro.pk]),
                {
                    "name": "Operativo Becas",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.becas.pk),
                    "capacidades": ["becas.segmento.ver", "becas.convocatoria.ver"],
                },
            )

        # Lo operativo sí lo puede componer: ese es su trabajo.
        self.assertEqual(
            sorted(rbac.capacidades_de_grupo(otro)),
            ["becas.convocatoria.ver", "becas.segmento.ver"],
        )
        self.assertNotIn("programa.usuario.administrar", rbac.capacidades_delegables(self.becas))
        self.assertNotIn("programa.rol.administrar", rbac.capacidades_delegables(self.becas))

    def test_admin_becas_no_puede_tildar_programa_configurar(self):
        """SEC-07 punto 3: queda solo para DISPOSITIVOS, que es el único programa que la
        evalúa con alcance."""
        self.assertNotIn("programa.configurar", rbac.capacidades_delegables(self.becas))
        self.assertIn("programa.configurar", rbac.capacidades_delegables(self.dispositivos))

    def test_admin_usuarios_no_se_asigna_rol_con_mas_capacidades(self):
        """La PoC (b) invertida: el combo del ABM de Usuarios dejaba elegir un rol que
        traía ``programa.rol.administrar``."""
        rol_ua = _rol("UA Becas", ["programa.usuario.administrar"], self.becas)
        rol_full = _rol(
            "Admin completo Becas",
            ["programa.rol.administrar", "becas.programa.administrar"],
            self.becas,
        )
        operador = _usuario("solo-usuarios", rol_ua)
        self.client.force_login(operador)
        self.assertEqual(self.client.get(reverse("users:roles")).status_code, 302)

        respuesta = self.client.post(
            reverse("users:usuario_editar", args=[operador.pk]),
            {
                "username": operador.username,
                "first_name": "",
                "last_name": "",
                "email": "",
                "groups": [str(rol_ua.pk), str(rol_full.pk)],
                "is_active": "on",
            },
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("groups", respuesta.context["form"].errors)
        operador = User.objects.get(pk=operador.pk)
        self.assertFalse(rbac.puede(operador, "programa.rol.administrar"))
        self.assertFalse(rbac.puede(operador, "becas.programa.administrar"))

    def test_admin_global_sigue_asignando_cualquier_rol(self):
        """El recorte es solo para el operador **no global**."""
        rol_full = _rol("Admin completo Becas 2", ["programa.rol.administrar"], self.becas)
        objetivo = _usuario("objetivo-global")
        self.client.force_login(self.root)

        respuesta = self.client.post(
            reverse("users:usuario_editar", args=[objetivo.pk]),
            {
                "username": objetivo.username,
                "first_name": "",
                "last_name": "",
                "email": "",
                "groups": [str(rol_full.pk)],
                "is_active": "on",
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(objetivo.groups.filter(pk=rol_full.pk).exists())


class OperadorDeVariosProgramasTests(Base):
    """Ronda 2: el candado (1) de SEC-06 no cubría al operador de **2 o más** programas.

    ``programa_fijo`` solo se setea con un único programa administrable, así que el
    árbol caía a ``capacidades_delegables(None)`` —el catálogo de programa entero— y le
    ofrecía los trece módulos ``becas_*`` a un operador de Dispositivos y Merenderos. No
    había escalada (el ``clean`` filtraba por el programa posteado), pero lo tildado
    desaparecía sin mensaje.
    """

    def setUp(self):
        super().setUp()
        self.merenderos = Programa.objects.create(codigo="MERENDEROS", nombre="Merenderos")
        self.operador = _usuario(
            "adm-roles-disp-mere",
            _rol("RA Dispositivos", ["programa.rol.administrar"], self.dispositivos),
            _rol("RA Merenderos", ["programa.rol.administrar"], self.merenderos),
        )

    def _form(self, data=None, instance=None):
        from users.forms.roles import RolForm

        return RolForm(data, instance=instance, operador=self.operador)

    def test_el_arbol_no_ofrece_los_modulos_de_un_programa_ajeno(self):
        form = self._form()

        modulos = {m["modulo"] for m in form.arbol_capacidades()}
        codigos = {codigo for codigo, _ in form.fields["capacidades"].choices}

        self.assertFalse({m for m in modulos if m.startswith("becas")}, modulos)
        self.assertNotIn("becas.programa.administrar", codigos)
        self.assertIn("dispositivo.ver", codigos)
        self.assertIn("merendero.ver", codigos)

    def test_tampoco_en_el_arbol_por_tabs(self):
        form = self._form()

        modulos = {m["modulo"] for tab in form.arbol_por_tabs() for m in tab["modulos"]}

        self.assertFalse({m for m in modulos if m.startswith("becas")}, modulos)

    def test_una_capacidad_de_su_otro_programa_no_se_descarta_en_silencio(self):
        """Lo delegable de Merenderos **sí** está entre los choices (es suyo), pero no
        corresponde a un rol de Dispositivos: antes se guardaba el rol sin ella."""
        form = self._form(
            {
                "name": "Operativo Dispositivos",
                "categoria": rbac.CATEGORIA_PROGRAMA,
                "programa": str(self.dispositivos.pk),
                "capacidades": ["dispositivo.ver", "merendero.ver"],
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("capacidades", form.errors)
        self.assertIn("merendero.ver", form.errors["capacidades"][0])
        self.assertFalse(Group.objects.filter(name="Operativo Dispositivos").exists())

    def test_y_la_pantalla_lo_dice(self):
        self.client.force_login(self.operador)

        with zeal_ignore():
            respuesta = self.client.post(
                reverse("users:rol_crear"),
                {
                    "name": "Operativo Dispositivos 2",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.dispositivos.pk),
                    "capacidades": ["dispositivo.ver", "merendero.ver"],
                },
            )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("capacidades", respuesta.context["form"].errors)
        self.assertFalse(Group.objects.filter(name="Operativo Dispositivos 2").exists())

    def test_lo_que_sí_corresponde_se_guarda(self):
        form = self._form(
            {
                "name": "Operativo Dispositivos 3",
                "categoria": rbac.CATEGORIA_PROGRAMA,
                "programa": str(self.dispositivos.pk),
                "capacidades": ["dispositivo.ver"],
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["capacidades"], ["dispositivo.ver"])


class MoverUnRolDeProgramaTests(Base):
    """Ronda 2: cambiarle el programa a un rol dejaba las capacidades del anterior."""

    def test_al_moverlo_pierde_las_capacidades_del_programa_viejo(self):
        rol = _rol(
            "Operativo Becas movido",
            ["becas.programa.administrar", "becas.segmento.ver", "dispositivo.ver"],
            self.becas,
        )
        self.client.force_login(self.root)

        with zeal_ignore():
            respuesta = self.client.post(
                reverse("users:rol_editar", args=[rol.pk]),
                {
                    "name": "Operativo Becas movido",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.dispositivos.pk),
                    "capacidades": ["dispositivo.ver"],
                },
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(rbac.capacidades_de_grupo(rol), ["dispositivo.ver"])

    def test_tambien_cuando_las_conserva_la_regla_de_g1b06(self):
        """El caso medido: un operador **no global** no ve las ``becas.*``, así que
        ``(actuales − permitidas)`` se las devolvía al rol."""
        rol = _rol("Operativo Becas g1b06", ["becas.segmento.ver", "dispositivo.ver"], self.becas)
        operador = _usuario(
            "adm-roles-becas-disp",
            _rol("RA Becas mueve", ["programa.rol.administrar"], self.becas),
            _rol("RA Disp mueve", ["programa.rol.administrar"], self.dispositivos),
        )
        self.client.force_login(operador)

        with zeal_ignore():
            respuesta = self.client.post(
                reverse("users:rol_editar", args=[rol.pk]),
                {
                    "name": "Operativo Becas g1b06",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.dispositivos.pk),
                    "capacidades": ["dispositivo.ver"],
                },
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(rbac.capacidades_de_grupo(rol), ["dispositivo.ver"])

    def test_un_rol_de_programa_no_pierde_las_capacidades_globales(self):
        """El recorte es de las capacidades **de programa** ajenas: `ciudadano.ver` no
        pertenece a ningún programa y se queda donde el admin global la puso."""
        rol = _rol("Operativo Becas global", ["becas.segmento.ver"], self.becas)
        rol.permissions.add(_perm("ciudadano.ver"))
        self.client.force_login(self.root)

        with zeal_ignore():
            self.client.post(
                reverse("users:rol_editar", args=[rol.pk]),
                {
                    "name": "Operativo Becas global",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.dispositivos.pk),
                    "capacidades": ["ciudadano.ver", "dispositivo.ver"],
                },
            )

        self.assertEqual(
            sorted(rbac.capacidades_de_grupo(rol)),
            ["ciudadano.ver", "dispositivo.ver"],
        )


class G1b06CapsGlobalesBorradasTests(Base):
    def test_el_admin_de_programa_no_borra_las_caps_globales_del_rol(self):
        """La PoC invertida: ``ciudadano.ver`` sobrevive al guardado."""
        rol = _rol("Operador Becas", ["becas.segmento.ver"], self.becas)
        rol.permissions.add(_perm("ciudadano.ver"))  # la agregó el admin global
        rol_ra = _rol("RA Becas g1b06", ["programa.rol.administrar"], self.becas)
        self.client.force_login(_usuario("adm-roles-becas", rol_ra))

        with zeal_ignore():
            respuesta = self.client.post(
                reverse("users:rol_editar", args=[rol.pk]),
                {
                    "name": "Operador Becas",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.becas.pk),
                    "descripcion": "cambio de texto",
                    # Lo que el navegador reenvía: el árbol no le muestra `ciudadano.ver`.
                    "capacidades": ["becas.segmento.ver"],
                },
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("ciudadano.ver", rbac.capacidades_de_grupo(rol))
        self.assertIn("becas.segmento.ver", rbac.capacidades_de_grupo(rol))
        self.assertEqual(RolMeta.objects.get(grupo=rol).descripcion, "cambio de texto")

    def test_el_admin_de_programa_si_destilda_lo_que_si_ve(self):
        """La contracara: lo que el árbol **sí** le muestra se sigue pudiendo quitar.
        Sin esto, el fix convertiría el ABM en «solo agregar»."""
        rol = _rol("Operador Becas 2", ["becas.segmento.ver", "becas.convocatoria.ver"], self.becas)
        rol_ra = _rol("RA Becas g1b06b", ["programa.rol.administrar"], self.becas)
        self.client.force_login(_usuario("adm-roles-becas-2", rol_ra))

        with zeal_ignore():
            self.client.post(
                reverse("users:rol_editar", args=[rol.pk]),
                {
                    "name": "Operador Becas 2",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.becas.pk),
                    "capacidades": ["becas.segmento.ver"],
                },
            )

        self.assertEqual(rbac.capacidades_de_grupo(rol), ["becas.segmento.ver"])

    def test_el_admin_global_sigue_reemplazando_el_conjunto_entero(self):
        rol = _rol("Operador Becas 3", ["becas.segmento.ver"], self.becas)
        rol.permissions.add(_perm("ciudadano.ver"))
        self.client.force_login(self.root)

        with zeal_ignore():
            self.client.post(
                reverse("users:rol_editar", args=[rol.pk]),
                {
                    "name": "Operador Becas 3",
                    "categoria": rbac.CATEGORIA_PROGRAMA,
                    "programa": str(self.becas.pk),
                    "capacidades": ["becas.segmento.ver"],
                },
            )

        self.assertEqual(rbac.capacidades_de_grupo(rol), ["becas.segmento.ver"])


class AsegurarAdminRestanteTests(Base):
    """Nadie puede quedar sin admin: la guarda sigue en pie después del PR."""

    def test_no_se_puede_dejar_un_programa_sin_administrador(self):
        rol_admin = _rol("Admin Becas unico", list(rbac.CAPS_ADMIN_PROGRAMA), self.becas)
        _usuario("unico-adm-becas", rol_admin)
        # El superusuario de emergencia cuenta como admin de cualquier programa, así que
        # para medir la guarda real no puede haber ninguno activo.
        User.objects.filter(is_superuser=True).update(is_active=False)
        self.client.force_login(self.root)

        respuesta = self.client.post(reverse("users:rol_toggle", args=[rol_admin.pk]))

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(RolMeta.objects.get(grupo=rol_admin).activo)

    def test_no_se_puede_dejar_el_sistema_sin_administrador(self):
        User.objects.filter(is_superuser=True).update(is_active=False)
        self.client.force_login(self.root)

        with zeal_ignore():
            self.client.post(
                reverse("users:rol_editar", args=[self.root.groups.first().pk]),
                {"name": "Admins", "categoria": rbac.CATEGORIA_SISTEMA, "capacidades": []},
            )

        self.assertIn("usuario.administrar", rbac.capacidades_de_grupo(self.root.groups.first()))


class Migracion0031Tests(Base):
    """SEC-06 / D-06: la migración de datos, su log y su reversa."""

    def test_quita_y_restituye_exactamente_lo_mismo(self):
        import importlib

        modulo = importlib.import_module("users.migrations.0031_quitar_becas_de_roles_de_otros_programas")
        rol_disp = _rol("Escalada Disp", ["dispositivo.ver", "becas.programa.administrar"], self.dispositivos)
        rol_becas = _rol("Coord Becas mig", ["becas.segmento.ver"], self.becas)
        rol_global = _rol("Global mig", ["ciudadano.ver"])

        from django.apps import apps

        with self.assertLogs(modulo.logger.name, level=logging.WARNING) as log:
            modulo.quitar(apps, None)

        self.assertEqual(rbac.capacidades_de_grupo(rol_disp), ["dispositivo.ver"])
        self.assertEqual(rbac.capacidades_de_grupo(rol_becas), ["becas.segmento.ver"])  # Becas no se toca
        self.assertEqual(rbac.capacidades_de_grupo(rol_global), ["ciudadano.ver"])  # sin programa, tampoco
        # Loguea cada rol y cada capacidad que quita (lo que el PM lee del `migrate`).
        self.assertIn("Escalada Disp", log.output[0])
        self.assertIn("becas_programa_administrar", log.output[0])
        # Y queda registrado para que la reversa sea exacta.
        self.assertEqual(
            list(CapacidadRevocada.objects.values_list("grupo__name", "codename", "migracion")),
            [("Escalada Disp", "becas_programa_administrar", "users.0031")],
        )

        modulo.restituir(apps, None)

        self.assertEqual(
            sorted(rbac.capacidades_de_grupo(rol_disp)),
            ["becas.programa.administrar", "dispositivo.ver"],
        )
        self.assertFalse(CapacidadRevocada.objects.exists())

    def test_sin_la_fila_becas_no_toca_a_nadie(self):
        """Ronda 2: sin el ancla, el «otro programa» es *todos* y la migración vaciaba
        las ``becas.*`` de los cinco roles de Becas, opt-in incluida. Ahora frena."""
        import importlib

        from django.apps import apps

        modulo = importlib.import_module("users.migrations.0031_quitar_becas_de_roles_de_otros_programas")
        rol_becas = _rol("Becas — Referente mig", ["becas.segmento.ver", "becas.relevamiento.publico"], self.becas)
        rol_disp = _rol("Escalada Disp sin ancla", ["dispositivo.ver", "becas.programa.administrar"], self.dispositivos)
        # El escenario de RED-56: el restore dejó la fila con otro código (borrarla no se
        # puede, los roles la referencian), así que `codigo="BECAS"` no existe.
        Programa.objects.filter(pk=self.becas.pk).update(codigo="BECAS_VIEJO")

        with self.assertLogs(modulo.logger.name, level=logging.WARNING) as log:
            modulo.quitar(apps, None)

        self.assertIn("falta el programa", log.output[0])
        self.assertIn("P-02", log.output[0])
        self.assertEqual(
            sorted(rbac.capacidades_de_grupo(rol_becas)),
            ["becas.relevamiento.publico", "becas.segmento.ver"],
        )
        # Tampoco quita lo que sí correspondería: sin el ancla no se decide nada.
        self.assertEqual(
            sorted(rbac.capacidades_de_grupo(rol_disp)),
            ["becas.programa.administrar", "dispositivo.ver"],
        )
        self.assertFalse(CapacidadRevocada.objects.exists())

    def test_sin_nada_que_quitar_no_escribe_nada(self):
        """Es el caso que P-02 confirma antes del deploy: si da vacío, no pasa nada."""
        import importlib

        from django.apps import apps

        modulo = importlib.import_module("users.migrations.0031_quitar_becas_de_roles_de_otros_programas")
        _rol("Solo Dispositivos", ["dispositivo.ver"], self.dispositivos)

        with self.assertLogs(modulo.logger.name, level=logging.INFO) as log:
            modulo.quitar(apps, None)

        self.assertIn("P-02", log.output[0])
        self.assertFalse(CapacidadRevocada.objects.exists())
