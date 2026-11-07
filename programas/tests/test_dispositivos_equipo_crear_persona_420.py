"""«Crear persona» y buscador con sugerencias en «Sumar persona al Equipo» (Cambio 420).

Lo que se fija acá, y cada guarda se verificó con mutación (romperla deja rojo el test que la cubre):

1. **Quién ve «Crear persona»**: quien gestiona ese Equipo **y** administra los usuarios de Dispositivos
   (``programa.usuario.administrar`` acotado al programa, ``usuario.administrar`` o superusuario). El resto ve el
   pedido al administrador. La barrera es el servidor: el POST de crear devuelve 403.
2. **Roles**: solo los que la regla del ABM de Usuarios deja dar, de Dispositivos y sin el de agente.
3. **Todo o nada**: usuario y miembro se crean en una transacción.
4. **DNI repetido**: «Esa persona ya tiene usuario…». El correo repetido no se bloquea (decisión del 13-oct).
5. **Sugerencias** de «Persona — Rol»: guarda de gestionar el Equipo, ``no-store``, tope, ``hay_mas``, sin correo.
"""

from unittest import mock

from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse

from programas.models import MiembroEquipoDispositivo
from programas.selectors.equipo_sugeridas import consulta_de_pares, sugerir_pares_equipo
from programas.services import equipo_dispositivo as equipo
from programas.tests.test_dispositivos_equipo_410 import BaseEquipo
from users.models import Profile

AJAX = {"x-requested-with": "XMLHttpRequest"}
MENSAJE_DNI = "Esa persona ya tiene usuario: dale el rol desde Usuarios."
PEDIR_ALTA = "¿No está? Pedile al administrador del programa que la dé de alta."
DNI_NUEVO = "28555111"


class BaseCrear(BaseEquipo):
    def setUp(self):
        super().setUp()
        self.rol_ver = self._rol("Operador", ("dispositivo.ver",))
        self.rol_admitir = self._rol("Admite", ("dispositivo.ver", "dispositivo.admitir"))
        self.rol_agente = self._rol("Agente", ("dispositivo.ver",), clave="dispositivos.agente_relevamiento")
        # Un rol que da administración de usuarios: un admin de programa no puede repartirlo.
        self.rol_administra = self._rol("Admin usuarios", ("dispositivo.ver", "programa.usuario.administrar"))
        self.rol_de_becas = self._rol("Rol de Becas", ("dispositivo.ver",), programa=self.becas)
        self.rol_inactivo = self._rol("Inactivo", ("dispositivo.ver",), activo=False)
        # Gestiona el Equipo (programa.configurar con alcance) y administra los usuarios de Dispositivos.
        self.rol_admin_programa = self._rol(
            "Admin Dispositivos", ("dispositivo.ver", "programa.configurar", "programa.usuario.administrar")
        )
        self.admin_programa = self._usuario("admin_programa", self.rol_admin_programa)
        # Responsable común: gestiona el Equipo pero no administra usuarios.
        self.responsable = self._usuario("responsable", self.rol_ver)
        self._miembro(self.disp_a, self.responsable, self.rol_ver, responsable=True)
        self.url_detalle = reverse("dispositivos:detalle", args=[self.disp_a.pk])
        self.url_sumar = self.url_detalle + "?tab=equipo&equipo=sumar"
        self.url_crear = reverse("dispositivos:equipo_crear_persona", args=[self.disp_a.pk])
        self.url_buscar = reverse("dispositivos:equipo_personas_buscar", args=[self.disp_a.pk])

    def _entrar(self, usuario):
        self.client.force_login(self._fresco(usuario))

    def _datos(self, **extra):
        datos = {
            "dni": DNI_NUEVO,
            "first_name": "Lucía",
            "last_name": "Ferreyra",
            "email": "lucia@example.com",
            "rol": self.rol_admitir.pk,
        }
        datos.update(extra)
        return datos

    def _crear(self, usuario=None, **extra):
        self._entrar(usuario or self.admin_programa)
        return self.client.post(self.url_crear, self._datos(**extra), headers=AJAX)

    def _sin_alta(self):
        self.assertFalse(Profile.objects.filter(dni=DNI_NUEVO).exists())
        self.assertFalse(User.objects.filter(email="lucia@example.com").exists())


class QuienVeCrearPersonaTests(BaseCrear):
    def test_el_admin_de_dispositivos_ve_el_boton_y_el_modal(self):
        self._entrar(self.admin_programa)
        respuesta = self.client.get(self.url_sumar)

        self.assertTrue(respuesta.context["puede_crear_persona"])
        self.assertContains(respuesta, "modal-crear-persona-titulo")
        self.assertContains(respuesta, self.url_crear)
        self.assertNotContains(respuesta, PEDIR_ALTA)

    def test_el_superusuario_lo_ve(self):
        superusuario = User.objects.create_superuser("super", "s@example.com", "x")
        self._entrar(superusuario)

        self.assertContains(self.client.get(self.url_sumar), "modal-crear-persona-titulo")

    def test_usuario_administrar_global_con_gestion_del_equipo_lo_ve(self):
        rol = self._rol("Global", ("dispositivo.ver", "programa.configurar", "usuario.administrar"))
        self._entrar(self._usuario("global", rol))

        self.assertContains(self.client.get(self.url_sumar), "modal-crear-persona-titulo")

    def test_un_responsable_comun_no_ve_el_boton_y_ve_el_pedido_al_administrador(self):
        self._entrar(self.responsable)
        respuesta = self.client.get(self.url_sumar)

        self.assertFalse(respuesta.context["puede_crear_persona"])
        self.assertNotIn("form_crear_persona", respuesta.context)
        self.assertNotContains(respuesta, "modal-crear-persona-titulo")
        self.assertNotContains(respuesta, self.url_crear)
        self.assertContains(respuesta, PEDIR_ALTA)

    def test_administrar_solo_los_roles_no_alcanza(self):
        rol = self._rol("Solo roles", ("dispositivo.ver", "programa.configurar", "rol.administrar"))
        self._entrar(self._usuario("solo_roles", rol))

        respuesta = self.client.get(self.url_sumar)

        self.assertFalse(respuesta.context["puede_crear_persona"])
        self.assertNotContains(respuesta, "modal-crear-persona-titulo")

    def test_administrar_usuarios_de_otro_programa_no_alcanza(self):
        rol = self._rol("Admin Becas", ("dispositivo.ver", "programa.usuario.administrar"), programa=self.becas)
        ajeno = self._usuario("admin_becas", rol, self.rol_ver)
        self._miembro(self.disp_a, ajeno, self.rol_ver, responsable=True)
        self._entrar(ajeno)

        self.assertFalse(self.client.get(self.url_sumar).context["puede_crear_persona"])

    def test_administrar_usuarios_sin_gestionar_este_equipo_no_alcanza(self):
        rol = self._rol("Solo usuarios", ("dispositivo.ver", "programa.usuario.administrar"))
        self._entrar(self._usuario("solo_usuarios", rol))

        respuesta = self.client.get(self.url_sumar)

        # Sin alcance sobre el dispositivo ni siquiera ve la pantalla: administrar usuarios no abre su Equipo.
        self.assertEqual(respuesta.status_code, 404)
        self.assertNotContains(respuesta, "modal-crear-persona-titulo", status_code=404)

    def test_el_aviso_de_sin_resultados_depende_del_permiso(self):
        self._entrar(self.admin_programa)
        con_permiso = self.client.get(self.url_sumar).context["form_equipo"]["persona"].field.widget.attrs
        self._entrar(self.responsable)
        sin_permiso = self.client.get(self.url_sumar).context["form_equipo"]["persona"].field.widget.attrs

        self.assertIn("Crear persona", con_permiso["data-sugerencias-vacio"])
        self.assertEqual(sin_permiso["data-sugerencias-vacio"], PEDIR_ALTA)

    def test_el_buscador_apunta_al_campo_oculto_que_viaja(self):
        self._entrar(self.admin_programa)
        form = self.client.get(self.url_sumar).context["form_equipo"]

        self.assertEqual(form["persona"].field.widget.attrs["data-sugerencias-destino"], form["persona_rol"].auto_id)
        self.assertEqual(form["persona_rol"].field.widget.input_type, "hidden")


class CompuertaDelPostTests(BaseCrear):
    def test_un_responsable_comun_recibe_403_y_no_se_crea_nada(self):
        respuesta = self._crear(self.responsable)

        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(respuesta.json()["ok"])
        self._sin_alta()
        self.assertEqual(MiembroEquipoDispositivo.objects.filter(dispositivo=self.disp_a).count(), 1)

    def test_el_403_sin_ajax_tambien_corta(self):
        self._entrar(self.responsable)

        self.assertEqual(self.client.post(self.url_crear, self._datos()).status_code, 403)
        self._sin_alta()

    def test_quien_administra_usuarios_pero_no_gestiona_este_equipo_recibe_404(self):
        rol = self._rol("Solo usuarios", ("dispositivo.ver", "programa.usuario.administrar"))

        self.assertEqual(self._crear(self._usuario("solo_usuarios", rol)).status_code, 404)
        self._sin_alta()

    def test_el_admin_de_usuarios_de_otro_programa_recibe_403(self):
        rol = self._rol("Admin Becas", ("dispositivo.ver", "programa.usuario.administrar"), programa=self.becas)
        ajeno = self._usuario("admin_becas", rol, self.rol_ver)
        self._miembro(self.disp_a, ajeno, self.rol_ver, responsable=True)

        self.assertEqual(self._crear(ajeno).status_code, 403)
        self._sin_alta()

    def test_solo_se_escribe_por_post(self):
        self._entrar(self.admin_programa)

        self.assertEqual(self.client.get(self.url_crear).status_code, 405)

    def test_el_servicio_tambien_exige_la_capacidad(self):
        alta = equipo.datos_de_alta_de_persona(
            actor=self.admin_programa,
            dni=DNI_NUEVO,
            nombre="Lucía",
            apellido="Ferreyra",
            correo="lucia@example.com",
            rol=self.rol_admitir,
        )
        self.assertTrue(alta.is_valid(), alta.errors)

        with self.assertRaises(Exception) as contexto:
            equipo.crear_persona_y_sumar(
                actor=self._fresco(self.responsable), dispositivo=self.disp_a, alta=alta, rol=self.rol_admitir
            )

        self.assertEqual(type(contexto.exception).__name__, "PermissionDenied")
        self._sin_alta()


class AltaTests(BaseCrear):
    def test_crea_el_usuario_con_el_rol_y_lo_suma_al_equipo(self):
        respuesta = self._crear(es_responsable="on")

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["redirect"], self.url_detalle + "?tab=equipo")
        usuario = User.objects.get(profile__dni=DNI_NUEVO)
        self.assertEqual(
            (usuario.first_name, usuario.last_name, usuario.email), ("Lucía", "Ferreyra", "lucia@example.com")
        )
        self.assertEqual(usuario.username, DNI_NUEVO)
        self.assertTrue(usuario.is_active)
        self.assertEqual(list(usuario.groups.all()), [self.rol_admitir])
        miembro = MiembroEquipoDispositivo.objects.get(dispositivo=self.disp_a, usuario=usuario)
        self.assertEqual(miembro.rol, self.rol_admitir)
        self.assertTrue(miembro.activo)
        self.assertTrue(miembro.es_responsable)

    def test_sin_la_marca_no_es_responsable(self):
        self._crear()

        miembro = MiembroEquipoDispositivo.objects.get(usuario__profile__dni=DNI_NUEVO)
        self.assertFalse(miembro.es_responsable)

    def test_la_clave_viaja_por_correo_y_no_se_pide_ni_se_muestra(self):
        mail.outbox.clear()
        respuesta = self._crear()

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["lucia@example.com"])
        self.assertNotIn("password", respuesta.content.decode().lower())
        self._entrar(self.admin_programa)
        pantalla = self.client.get(self.url_sumar).content.decode()
        self.assertNotIn('name="password"', pantalla)

    def test_un_fallo_del_correo_no_deshace_el_alta_y_avisa(self):
        with mock.patch("programas.views.dispositivos_equipo.entregar_credenciales_provisorias", side_effect=OSError):
            respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(User.objects.filter(profile__dni=DNI_NUEVO).exists())
        self.assertIn("No se pudo enviar el correo", respuesta.json()["message"])

    def test_el_dni_se_normaliza_con_puntos(self):
        self._crear(dni="28.555.111")

        self.assertTrue(Profile.objects.filter(dni=DNI_NUEVO).exists())

    def test_los_cuatro_datos_son_obligatorios(self):
        for campo in ("dni", "first_name", "last_name", "email"):
            with self.subTest(campo=campo):
                respuesta = self._crear(**{campo: ""})
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn(campo, respuesta.json()["errors"])
        self._sin_alta()

    def test_un_dni_invalido_se_rechaza_en_su_campo(self):
        respuesta = self._crear(dni="123")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("dni", respuesta.json()["errors"])

    def test_el_nombre_de_usuario_no_choca_con_otra_cuenta(self):
        User.objects.create_user(username=DNI_NUEVO, password="x")

        self._crear()

        self.assertEqual(User.objects.get(profile__dni=DNI_NUEVO).username, f"{DNI_NUEVO}-2")

    def test_un_correo_repetido_no_se_bloquea(self):
        otro = User.objects.create_user(username="otro", password="x", email="lucia@example.com")

        respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(User.objects.filter(email="lucia@example.com").count(), 2)
        self.assertTrue(User.objects.filter(pk=otro.pk).exists())


class DniDuplicadoTests(BaseCrear):
    def test_un_dni_que_ya_tiene_usuario_manda_a_darle_el_rol_desde_usuarios(self):
        existente = User.objects.create_user(username="ya_existe", password="x", email="otro@example.com")
        Profile.objects.update_or_create(user=existente, defaults={"dni": DNI_NUEVO})

        respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.json()["errors"]["dni"], [MENSAJE_DNI])
        self.assertEqual(User.objects.filter(profile__dni=DNI_NUEVO).count(), 1)
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=existente).exists())

    def test_el_texto_del_abm_no_cambia(self):
        from users.views.quick_create import MENSAJES_DNI_DUPLICADO

        self.assertEqual(MENSAJES_DNI_DUPLICADO["equipo"], MENSAJE_DNI)


class RolesTests(BaseCrear):
    def test_el_admin_de_programa_solo_puede_dar_roles_activos_de_dispositivos_sin_agente_ni_administracion(self):
        nombres = set(equipo.roles_para_crear_persona(self._fresco(self.admin_programa)).values_list("name", flat=True))

        self.assertIn("Operador", nombres)
        self.assertIn("Admite", nombres)
        self.assertNotIn("Agente", nombres)
        self.assertNotIn("Admin usuarios", nombres)
        self.assertNotIn("Rol de Becas", nombres)
        self.assertNotIn("Inactivo", nombres)
        self.assertNotIn("Admin Dispositivos", nombres)

    def test_es_la_regla_del_abm_de_usuarios_y_no_una_paralela(self):
        from users.selectors.usuarios import roles_asignables

        actor = self._fresco(self.admin_programa)
        with mock.patch("users.selectors.usuarios.roles_asignables", wraps=roles_asignables) as espia:
            equipo.roles_para_crear_persona(actor)

        espia.assert_called_once_with(actor)

    def test_un_rol_que_el_actor_no_puede_asignar_se_rechaza_y_no_crea_nada(self):
        respuesta = self._crear(rol=self.rol_administra.pk)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("rol", respuesta.json()["errors"])
        self._sin_alta()

    def test_el_rol_de_agente_se_rechaza(self):
        respuesta = self._crear(rol=self.rol_agente.pk)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("rol", respuesta.json()["errors"])
        self._sin_alta()

    def test_un_rol_de_otro_programa_o_inactivo_se_rechaza(self):
        for rol in (self.rol_de_becas, self.rol_inactivo):
            with self.subTest(rol=rol.name):
                self.assertEqual(self._crear(rol=rol.pk).status_code, 400)
        self._sin_alta()

    def test_el_combo_del_modal_no_ofrece_roles_que_no_se_pueden_dar(self):
        self._entrar(self.admin_programa)
        opciones = [
            rol.name for rol in self.client.get(self.url_sumar).context["form_crear_persona"].fields["rol"].queryset
        ]

        self.assertIn("Admite", opciones)
        self.assertNotIn("Agente", opciones)
        self.assertNotIn("Admin usuarios", opciones)

    def test_el_servicio_rechaza_un_rol_fuera_de_la_regla_aunque_el_formulario_lo_deje_pasar(self):
        from django.contrib.auth.models import Group

        from users.forms import UserCreationForm

        actor = self._fresco(self.admin_programa)
        alta = equipo.datos_de_alta_de_persona(
            actor=actor,
            dni=DNI_NUEVO,
            nombre="Lucía",
            apellido="Ferreyra",
            correo="lucia@example.com",
            rol=self.rol_admitir,
        )
        # Un formulario que sí acepta el rol (como si la regla del formulario se hubiera aflojado): el servicio
        # no se apoya en él. `Admin usuarios` pasa `sumar_miembro` (es de Dispositivos y no es el de agente), pero
        # el actor no puede asignarlo según el ABM de Usuarios.
        alta = UserCreationForm(data=alta.data, operador=actor, roles_acotados=Group.objects.all())
        alta.data = alta.data.copy()
        alta.data.setlist("groups", [str(self.rol_administra.pk)])
        self.assertTrue(alta.is_valid(), alta.errors)

        with self.assertRaises(ValidationError) as contexto:
            equipo.crear_persona_y_sumar(actor=actor, dispositivo=self.disp_a, alta=alta, rol=self.rol_administra)

        self.assertIn("rol", contexto.exception.message_dict)

        self._sin_alta()

    def test_un_superusuario_puede_dar_cualquier_rol_activo_de_dispositivos_menos_el_de_agente(self):
        superusuario = User.objects.create_superuser("super", "s@example.com", "x")

        nombres = set(equipo.roles_para_crear_persona(superusuario).values_list("name", flat=True))

        self.assertIn("Admin usuarios", nombres)
        self.assertNotIn("Agente", nombres)
        self.assertNotIn("Rol de Becas", nombres)


class AtomicidadTests(BaseCrear):
    def test_si_falla_sumar_al_equipo_no_queda_el_usuario(self):
        with mock.patch.object(equipo, "sumar_miembro", side_effect=ValidationError("no se pudo sumar")):
            respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 400)
        self._sin_alta()
        self.assertFalse(User.objects.filter(username=DNI_NUEVO).exists())
        self.assertEqual(MiembroEquipoDispositivo.objects.filter(dispositivo=self.disp_a).count(), 1)

    def test_si_falla_la_creacion_no_queda_el_miembro(self):
        with mock.patch(
            "users.services.admin.UsuariosAdminService._sync_profile", side_effect=ValidationError("falló el perfil")
        ):
            respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 400)
        self._sin_alta()
        self.assertFalse(User.objects.filter(username=DNI_NUEVO).exists())
        self.assertEqual(MiembroEquipoDispositivo.objects.filter(dispositivo=self.disp_a).count(), 1)


class BuscadorDeParesTests(BaseCrear):
    """El campo «Persona y rol» de «Sumar persona»: sugerencias y validación del par al guardar."""

    def setUp(self):
        super().setUp()
        self.ana = self._usuario("ana", self.rol_ver, self.rol_admitir)
        User.objects.filter(pk=self.ana.pk).update(first_name="Ana", last_name="Gómez", email="ana@example.com")
        self.ana.refresh_from_db()

    def _sugerir(self, q, usuario=None):
        self._entrar(usuario or self.admin_programa)
        return self.client.get(self.url_buscar, {"q": q})

    def test_sin_gestionar_el_equipo_con_alcance_es_403_json(self):
        # Con alcance sobre el dispositivo pero sin gestionar su Equipo: es una falta de permiso, 403.
        solo_ve = self._usuario("solo_ve", self.rol_ver)
        self._miembro(self.disp_a, solo_ve, self.rol_ver)
        for usuario in (solo_ve,):
            respuesta = self._sugerir("ana", usuario)
            self.assertEqual(respuesta.status_code, 403)
            self.assertFalse(respuesta.json()["ok"])
            self.assertEqual(respuesta["Cache-Control"], "no-store")

    def test_un_responsable_de_otro_dispositivo_es_404(self):
        ajeno = self._usuario("ajeno", self.rol_ver)
        self._miembro(self.disp_b, ajeno, self.rol_ver, responsable=True)

        self.assertEqual(self._sugerir("ana", ajeno).status_code, 404)

    def test_quien_gestiona_recibe_los_pares_persona_rol_con_valor_y_etiqueta(self):
        respuesta = self._sugerir("ana")

        self.assertEqual(respuesta.status_code, 200)
        filas = respuesta.json()["resultados"]
        self.assertEqual(
            [(f["etiqueta"], f["valor"]) for f in filas],
            [
                ("Ana Gómez — Admite", f"{self.ana.pk}:{self.rol_admitir.pk}"),
                ("Ana Gómez — Operador", f"{self.ana.pk}:{self.rol_ver.pk}"),
            ],
        )

    def test_un_responsable_comun_tambien_busca(self):
        self.assertEqual(self._sugerir("ana", self.responsable).status_code, 200)

    def test_la_respuesta_no_se_guarda_en_cache(self):
        self.assertEqual(self._sugerir("ana")["Cache-Control"], "no-store")

    def test_no_trae_correo_telefono_ni_dni(self):
        Profile.objects.update_or_create(user=self.ana, defaults={"dni": "30111222", "telefono": "3624123456"})

        fila = self._sugerir("ana").json()["resultados"][0]

        self.assertEqual(set(fila), {"apellido", "nombre", "rol", "valor", "etiqueta"})
        contenido = self._sugerir("ana").content.decode()
        for dato in ("ana@example.com", "3624123456", "30111222"):
            self.assertNotIn(dato, contenido)

    def test_menos_de_tres_caracteres_devuelve_lista_vacia(self):
        for texto in ("", "  ", "an", " a "):
            with self.subTest(texto=texto):
                self.assertEqual(self._sugerir(texto).json(), {"resultados": [], "hay_mas": False})

    def test_es_por_prefijo_de_nombre_o_apellido_y_las_palabras_se_cruzan(self):
        self.assertTrue(self._sugerir("góm").json()["resultados"])
        self.assertTrue(self._sugerir("Gómez, Ana").json()["resultados"])
        self.assertEqual(self._sugerir("Gómez Juan").json()["resultados"], [])
        self.assertEqual(self._sugerir("mez").json()["resultados"], [])

    def test_el_comodin_de_like_se_toma_literal(self):
        self.assertEqual(self._sugerir("%%%").json()["resultados"], [])

    def test_no_ofrece_al_agente_ni_roles_de_otro_programa_ni_inactivos(self):
        yo = self._usuario("anabel", self.rol_agente, self.rol_de_becas, self.rol_inactivo)
        User.objects.filter(pk=yo.pk).update(first_name="Anabel", last_name="Ruiz")

        self.assertEqual(self._sugerir("anabel").json()["resultados"], [])

    def test_no_ofrece_a_los_inactivos(self):
        User.objects.filter(pk=self.ana.pk).update(is_active=False)

        self.assertEqual(self._sugerir("ana").json()["resultados"], [])

    def test_no_ofrece_a_quien_ya_esta_en_el_equipo_con_ese_rol(self):
        self._miembro(self.disp_a, self.ana, self.rol_ver)

        etiquetas = [f["etiqueta"] for f in self._sugerir("ana").json()["resultados"]]

        self.assertEqual(etiquetas, ["Ana Gómez — Admite"])

    def test_el_tope_es_diez_y_con_mas_avisa_hay_mas(self):
        for n in range(11):
            usuario = self._usuario(f"mar{n:02d}", self.rol_ver)
            User.objects.filter(pk=usuario.pk).update(first_name="Mar", last_name=f"Pérez{n:02d}")

        datos = self._sugerir("mar").json()

        self.assertEqual(len(datos["resultados"]), 10)
        self.assertTrue(datos["hay_mas"])

    def test_con_exactamente_el_tope_no_avisa_que_hay_mas(self):
        for n in range(10):
            usuario = self._usuario(f"mar{n:02d}", self.rol_ver)
            User.objects.filter(pk=usuario.pk).update(first_name="Mar", last_name=f"Pérez{n:02d}")

        datos = self._sugerir("mar").json()

        self.assertEqual(len(datos["resultados"]), 10)
        self.assertFalse(datos["hay_mas"])

    def test_el_selector_corta_la_entrada_larga_sin_buscar(self):
        self.assertEqual(sugerir_pares_equipo(self.disp_a, "x" * 500)["resultados"], [])

    def test_el_prefijo_no_se_traduce_a_like_binary_en_mysql(self):
        """`startswith` en MySQL/MariaDB es `LIKE BINARY`: no usa bien el índice."""

        from django.db.backends.mysql.base import DatabaseWrapper

        conexion = DatabaseWrapper(
            {
                "NAME": "x",
                "USER": "x",
                "PASSWORD": "x",
                "HOST": "x",
                "PORT": "",
                "OPTIONS": {},
                "TIME_ZONE": None,
                "CONN_MAX_AGE": 0,
                "CONN_HEALTH_CHECKS": False,
                "AUTOCOMMIT": True,
                "ATOMIC_REQUESTS": False,
                "TEST": {},
            }
        )
        for palabras in (["ana"], ["Gómez"], ["Gómez", "Ana"]):
            with self.subTest(palabras=palabras):
                sql, _ = consulta_de_pares(self.disp_a, palabras).query.get_compiler(connection=conexion).as_sql()
                self.assertNotIn("LIKE BINARY", sql)
                self.assertIn("LIKE", sql)

    def test_el_par_elegido_se_valida_al_guardar_con_el_campo_oculto(self):
        self._entrar(self.admin_programa)
        respuesta = self.client.post(
            reverse("dispositivos:equipo_sumar", args=[self.disp_a.pk]),
            {"persona": "Ana Gómez — Admite", "persona_rol": f"{self.ana.pk}:{self.rol_admitir.pk}"},
            headers=AJAX,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(
            MiembroEquipoDispositivo.objects.filter(
                dispositivo=self.disp_a, usuario=self.ana, rol=self.rol_admitir, activo=True
            ).exists()
        )

    def test_un_par_inventado_o_el_texto_solo_no_suma_a_nadie(self):
        self._entrar(self.admin_programa)
        url = reverse("dispositivos:equipo_sumar", args=[self.disp_a.pk])
        for valor in (
            "",
            "ana",
            "x:y",
            f"{self.ana.pk}:99999",
            f"99999:{self.rol_ver.pk}",
            f"{self.ana.pk}:{self.rol_agente.pk}",
        ):
            with self.subTest(valor=valor):
                respuesta = self.client.post(url, {"persona": "Ana", "persona_rol": valor}, headers=AJAX)
                self.assertEqual(respuesta.status_code, 400)
                self.assertIn("persona_rol", respuesta.json()["errors"])
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.ana).exists())

    def test_quien_ya_esta_en_el_equipo_con_ese_rol_se_rechaza_en_su_campo(self):
        self._miembro(self.disp_a, self.ana, self.rol_ver)
        self._entrar(self.admin_programa)

        respuesta = self.client.post(
            reverse("dispositivos:equipo_sumar", args=[self.disp_a.pk]),
            {"persona_rol": f"{self.ana.pk}:{self.rol_ver.pk}"},
            headers=AJAX,
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("persona_rol", respuesta.json()["errors"])


class CargaDeLaPiezaTests(BaseCrear):
    def test_el_modal_trae_la_pieza_de_sugerencias_y_el_aviso_para_el_responsable(self):
        self._entrar(self.responsable)
        respuesta = self.client.get(self.url_sumar)

        self.assertContains(respuesta, "nodo-sugerencias.js")
        self.assertContains(respuesta, "nodo-sugerencias.css")
        self.assertContains(respuesta, 'data-sugerencias-destino="equipo_persona_rol"')
        self.assertContains(respuesta, self.url_buscar)
        # Desde la solapa sin el modal, la página no pide ni arma nada de esto.
        sin_modal = self.client.get(self.url_detalle + "?tab=equipo")
        self.assertNotIn("form_equipo", sin_modal.context)

    def test_el_javascript_vacia_el_oculto_al_teclear_de_nuevo(self):
        from pathlib import Path

        js = Path("static/custom/js/nodo-sugerencias.js").read_text(encoding="utf-8")

        self.assertIn("data-sugerencias-destino", js)
        self.assertIn("if (oculto && !eligiendo) oculto.value = ''", js)

    def tearDown(self):
        cache.clear()
        super().tearDown()
