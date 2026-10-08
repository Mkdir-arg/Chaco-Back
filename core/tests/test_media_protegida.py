"""`/media/` exige sesión **y pertenencia** (SEC-09, auditoría oct-2026).

**Etapa 1 (#538, Cambio 112)** cerró las dos puertas que servían los archivos sin
que Django mirara quién pedía: nginx dejó de tener `location /media/` (solo queda
`/protected-media/` como `internal`) y `PortalCiudadanoMiddleware` dejó de eximir
`/media/`, así que la sesión de un ciudadano del portal ya no baja adjuntos del
backoffice.

**Etapa 2 (este PR)** es la que faltaba: hasta acá *cualquier* cuenta de backoffice
con sesión bajaba *cualquier* archivo —el Excel del padrón de otra convocatoria, el
F-00 de un dispositivo ajeno, la foto de DNI de cualquier ciudadano— porque
`login_required` era todo el control. Ahora `core.views.media.media_protegida`
resuelve el **dueño** del archivo por el prefijo de su ruta y evalúa la capacidad
con su alcance, igual que la pantalla por la que ese archivo se ve.

Lo que estos tests fijan:

- sin sesión → login; ciudadano del portal → portal (la etapa 1 no se desarma);
- **con sesión pero sin la capacidad → 403**, que es el agujero de la etapa 2;
- alcance fino: un coordinador de Becas no baja el padrón del segmento de al lado,
  y un operador de Dispositivos no baja el F-00 de un dispositivo que no tiene
  asignado;
- un archivo sin fila en la base (huérfano en el disco) → 404 aunque sobre la
  capacidad: no hay dueño que autorice;
- la ruta no se puede escapar de `MEDIA_ROOT`;
- **los archivos ya guardados se siguen bajando**: la resolución es por el nombre
  que tiene la fila, no por el formato nuevo con UUID;
- `MEDIA_X_ACCEL` delega los bytes al servidor de adelante (`X-Accel-Redirect`) sin
  cambiar una sola decisión de autorización. Apagado —el default, que es el
  comportamiento de hoy— los entrega Django.
"""

import tempfile
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core import rbac
from users.models import Capacidad, RolMeta

RAIZ = Path(settings.BASE_DIR)
CONTENIDO = b"%PDF-contenido-del-ciudadano"


def usuario_con(*codigos, username=None, programa=None):
    """Usuario de backoffice con exactamente esas capacidades (ninguna = sin rol)."""
    usuario = User.objects.create_user(username or f"u-{'-'.join(codigos) or 'sin-rol'}", password="Clave-Seg-2026x")
    if not codigos:
        return usuario
    nombre = "Rol " + (username or "-".join(codigos))
    grupo, _ = Group.objects.get_or_create(name=nombre)
    RolMeta.objects.update_or_create(
        grupo=grupo,
        defaults={
            "categoria": rbac.CATEGORIA_PROGRAMA if programa else rbac.CATEGORIA_BACKOFFICE,
            "activo": True,
            "programa": programa,
        },
    )
    ct = ContentType.objects.get_for_model(Capacidad)
    for codigo in codigos:
        grupo.permissions.add(Permission.objects.get(codename=rbac.codename_de(codigo), content_type=ct))
    usuario.groups.add(grupo)
    return usuario


class MediaBaseTests(TestCase):
    """`MEDIA_ROOT` propio por test: los archivos se escriben de verdad."""

    def setUp(self):
        # `ignore_cleanup_errors`: `FileResponse` deja el archivo abierto hasta que
        # alguien consume o cierra la respuesta —en producción lo hace el servidor
        # WSGI—, y en Windows un archivo abierto no se puede borrar.
        self.media = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.media.cleanup)
        contexto = override_settings(MEDIA_ROOT=self.media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)

    def _cliente(self, usuario=None):
        cliente = Client()
        if usuario is not None:
            cliente.force_login(usuario)
        return cliente

    def _url(self, nombre_guardado):
        return f"/media/{nombre_guardado}"

    def _cuerpo(self, respuesta):
        return b"".join(respuesta.streaming_content) if respuesta.streaming else respuesta.content


def archivo(nombre="dni.pdf", contenido=CONTENIDO):
    return SimpleUploadedFile(nombre, contenido, content_type="application/pdf")


class PuertaDeEntradaTests(MediaBaseTests):
    """Lo que la etapa 1 dejó cerrado sigue cerrado, y la 2 cierra la pertenencia."""

    def setUp(self):
        super().setUp()
        from legajos.models import Adjunto, Ciudadano

        self.ciudadano = Ciudadano.objects.create(dni="30111222", nombre="Mirta", apellido="Quiroga")
        self.adjunto = Adjunto.objects.create(
            content_type=ContentType.objects.get_for_model(Ciudadano),
            object_id=self.ciudadano.id,
            archivo=archivo(),
            etiqueta="DNI",
        )
        self.ruta = self._url(self.adjunto.archivo.name)

    def test_anonimo_va_al_login(self):
        respuesta = self._cliente().get(self.ruta)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse(settings.LOGIN_URL), respuesta["Location"])

    def test_ciudadano_del_portal_no_descarga_media(self):
        grupo, _ = Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)
        ciudadano = User.objects.create_user("ciudadano_media", password="x")
        ciudadano.groups.add(grupo)

        respuesta = self._cliente(ciudadano).get(self.ruta)

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta["Location"], reverse("portal:home"))

    def test_backoffice_sin_rol_ya_no_descarga_el_adjunto(self):
        """El agujero de la etapa 2: `login_required` era todo el control."""
        respuesta = self._cliente(usuario_con()).get(self.ruta)

        self.assertEqual(respuesta.status_code, 403)

    def test_con_ciudadano_ver_descarga_como_attachment(self):
        respuesta = self._cliente(usuario_con("ciudadano.ver")).get(self.ruta)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._cuerpo(respuesta), CONTENIDO)
        self.assertIn("attachment", respuesta["Content-Disposition"])
        self.assertEqual(respuesta["X-Content-Type-Options"], "nosniff")

    def test_superusuario_descarga(self):
        jefe = User.objects.create_superuser("jefa_media", password="x")

        self.assertEqual(self._cliente(jefe).get(self.ruta).status_code, 200)

    def test_archivo_sin_fila_en_la_base_es_404(self):
        """Un blob huérfano no tiene dueño que lo autorice, sobre o no la capacidad."""
        suelto = Path(self.media.name) / "adjuntos" / "huerfano.pdf"
        suelto.parent.mkdir(parents=True, exist_ok=True)
        suelto.write_bytes(CONTENIDO)

        respuesta = self._cliente(usuario_con("ciudadano.ver")).get("/media/adjuntos/huerfano.pdf")

        self.assertEqual(respuesta.status_code, 404)

    def test_prefijo_desconocido_es_404(self):
        suelto = Path(self.media.name) / "loquesea.pdf"
        suelto.write_bytes(CONTENIDO)

        respuesta = self._cliente(usuario_con("ciudadano.ver")).get("/media/loquesea.pdf")

        self.assertEqual(respuesta.status_code, 404)

    def test_la_ruta_no_se_escapa_del_directorio(self):
        secreto = RAIZ / "config" / "settings.py"
        self.assertTrue(secreto.exists())

        respuesta = self._cliente(usuario_con("ciudadano.ver")).get("/media/adjuntos/../../config/settings.py")

        self.assertEqual(respuesta.status_code, 404)

    def test_un_salto_al_padre_no_pasa_por_el_prefijo(self):
        respuesta = self._cliente(usuario_con("ciudadano.ver")).get("/media/adjuntos/..%2F..%2Fmanage.py")

        self.assertEqual(respuesta.status_code, 404)

    def test_archivo_legacy_con_el_nombre_original_se_sigue_bajando(self):
        """Los blobs guardados antes del `upload_to` con UUID no se renombran.

        Una fila de 2025 quedó con `adjuntos/constancia-de-domicilio.pdf`; la
        migración es solo de estado y no toca el disco, así que se sigue bajando
        igual. La resolución del dueño es por el `name` de la fila, no por el
        formato del nombre.
        """
        from legajos.models import Adjunto, Ciudadano

        viejo = Path(self.media.name) / "adjuntos" / "constancia-de-domicilio.pdf"
        viejo.parent.mkdir(parents=True, exist_ok=True)
        viejo.write_bytes(CONTENIDO)
        legacy = Adjunto.objects.create(
            content_type=ContentType.objects.get_for_model(Ciudadano),
            object_id=self.ciudadano.id,
            archivo="adjuntos/constancia-de-domicilio.pdf",
            etiqueta="legacy",
        )

        respuesta = self._cliente(usuario_con("ciudadano.ver")).get(self._url(legacy.archivo.name))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(self._cuerpo(respuesta), CONTENIDO)

    def test_el_nombre_guardado_ya_no_es_el_que_eligio_quien_sube(self):
        """`upload_to` con UUID: la ruta deja de ser enumerable."""
        self.assertNotIn("dni", self.adjunto.archivo.name)
        self.assertTrue(self.adjunto.archivo.name.endswith(".pdf"))


class XAccelRedirectTests(MediaBaseTests):
    """`MEDIA_X_ACCEL` cambia **quién entrega los bytes**, nunca quién puede."""

    def setUp(self):
        super().setUp()
        from legajos.models import Adjunto, Ciudadano

        self.ciudadano = Ciudadano.objects.create(dni="30111333", nombre="Hugo", apellido="Paz")
        self.adjunto = Adjunto.objects.create(
            content_type=ContentType.objects.get_for_model(Ciudadano),
            object_id=self.ciudadano.id,
            archivo=archivo(),
        )
        self.ruta = self._url(self.adjunto.archivo.name)

    def test_apagado_el_default_los_entrega_django(self):
        self.assertFalse(settings.MEDIA_X_ACCEL)

        respuesta = self._cliente(usuario_con("ciudadano.ver")).get(self.ruta)

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotIn("X-Accel-Redirect", respuesta)
        self.assertEqual(self._cuerpo(respuesta), CONTENIDO)

    @override_settings(MEDIA_X_ACCEL=True)
    def test_prendido_delega_en_protected_media(self):
        respuesta = self._cliente(usuario_con("ciudadano.ver")).get(self.ruta)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta["X-Accel-Redirect"], f"/protected-media/{self.adjunto.archivo.name}")
        self.assertEqual(self._cuerpo(respuesta), b"")

    @override_settings(MEDIA_X_ACCEL=True)
    def test_prendido_sigue_negando_al_que_no_puede(self):
        respuesta = self._cliente(usuario_con()).get(self.ruta)

        self.assertEqual(respuesta.status_code, 403)
        self.assertNotIn("X-Accel-Redirect", respuesta)

    @override_settings(MEDIA_X_ACCEL=True)
    def test_un_nombre_legacy_con_espacios_y_acentos_sale_escapado(self):
        """El header es una URI: sin escapar, nginx corta en el espacio."""
        from legajos.models import Adjunto, Ciudadano

        nombre = "adjuntos/constancia de domicilio ñ.pdf"
        destino = Path(self.media.name) / "adjuntos"
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "constancia de domicilio ñ.pdf").write_bytes(CONTENIDO)
        Adjunto.objects.create(
            content_type=ContentType.objects.get_for_model(Ciudadano),
            object_id=self.ciudadano.id,
            archivo=nombre,
        )

        respuesta = self._cliente(usuario_con("ciudadano.ver")).get(self._url(nombre))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            respuesta["X-Accel-Redirect"],
            "/protected-media/adjuntos/constancia%20de%20domicilio%20%C3%B1.pdf",
        )

    @override_settings(MEDIA_X_ACCEL=True)
    def test_el_header_no_se_puede_partir_con_un_salto_de_linea(self):
        respuesta = self._cliente(usuario_con("ciudadano.ver")).get("/media/adjuntos/a%0D%0AX-Inyectado:%20si.pdf")

        self.assertEqual(respuesta.status_code, 404)


class DebugNoAbreMediaTests(MediaBaseTests):
    """R0b-07: `static(MEDIA_URL)` servía `/media/` sin sesión con `DEBUG=True`."""

    @override_settings(DEBUG=True)
    def test_con_debug_el_anonimo_sigue_yendo_al_login(self):
        from legajos.models import Adjunto, Ciudadano

        ciudadano = Ciudadano.objects.create(dni="30111444", nombre="Eva", apellido="Soto")
        adjunto = Adjunto.objects.create(
            content_type=ContentType.objects.get_for_model(Ciudadano),
            object_id=ciudadano.id,
            archivo=archivo(),
        )

        respuesta = self._cliente().get(self._url(adjunto.archivo.name))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn(reverse(settings.LOGIN_URL), respuesta["Location"])


class AlcanceBecasTests(MediaBaseTests):
    """Padrones y adjuntos de Becas: el alcance es el de la pantalla que los muestra."""

    def setUp(self):
        super().setUp()
        from io import StringIO

        from django.core.management import call_command

        from programas.models import AsignacionCoordinador, Convocatoria, Programa, Segmento
        from programas.services.autorizacion import invalidar_programa_becas

        call_command("seed_becas", stdout=StringIO())
        invalidar_programa_becas()
        self.becas = Programa.objects.get(codigo="BECAS")
        self.seg_a = Segmento.objects.create(nombre="Segmento A", cupo_maximo=100)
        self.seg_b = Segmento.objects.create(nombre="Segmento B", cupo_maximo=100)
        self.conv_a = Convocatoria.objects.create(
            nombre="Conv A",
            segmento=self.seg_a,
            fecha_inicio="2026-01-01",
            fecha_fin="2026-12-31",
            padron_archivo=SimpleUploadedFile("padron.xlsx", b"PK\x03\x04padron"),
        )

        from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR

        self.admin = User.objects.create_user("admin_becas_media", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.coord_a = User.objects.create_user("coord_a_media", password="x")
        self.coord_a.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.seg_a, coordinador=self.coord_a)
        self.coord_b = User.objects.create_user("coord_b_media", password="x")
        self.coord_b.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.seg_b, coordinador=self.coord_b)

        self.ruta_padron = self._url(self.conv_a.padron_archivo.name)

    def test_el_admin_del_programa_baja_el_padron(self):
        self.assertEqual(self._cliente(self.admin).get(self.ruta_padron).status_code, 200)

    def test_el_coordinador_de_la_convocatoria_baja_su_padron(self):
        self.assertEqual(self._cliente(self.coord_a).get(self.ruta_padron).status_code, 200)

    def test_el_coordinador_del_segmento_de_al_lado_no_lo_baja(self):
        """Mismo rol, otro alcance: el padrón es la lista de habilitados completa."""
        self.assertEqual(self._cliente(self.coord_b).get(self.ruta_padron).status_code, 403)

    def test_un_usuario_de_otro_programa_no_baja_el_padron(self):
        self.assertEqual(self._cliente(usuario_con("ciudadano.ver")).get(self.ruta_padron).status_code, 403)


class AlcanceDispositivosTests(MediaBaseTests):
    """El F-00 se baja con el alcance del dispositivo, no con la sesión."""

    def setUp(self):
        super().setUp()
        from legajos.models import Ciudadano
        from programas.models import (
            Admision,
            ArchivoAdmision,
            CampoTipoDispositivo,
            Dispositivo,
            Programa,
            TipoCampo,
            TipoDispositivo,
        )

        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")
        self.dispositivo = Dispositivo.objects.create(
            codigo="HOGAR-01", nombre="Hogar Norte", tipo=tipo, estado=Dispositivo.Estado.ACTIVO
        )
        campo = CampoTipoDispositivo.objects.create(
            tipo_dispositivo=tipo, seccion="Datos", nombre="Constancia", tipo_campo=TipoCampo.ARCHIVO, orden=1
        )
        ciudadano = Ciudadano.objects.create(dni="30222111", nombre="Juan", apellido="Rito")
        admision = Admision.objects.create(
            ciudadano=ciudadano, dispositivo=self.dispositivo, fecha_ingreso=timezone.now()
        )
        self.archivo_f00 = ArchivoAdmision.objects.create(admision=admision, campo=campo, archivo=archivo("f00.pdf"))
        self.ruta = self._url(self.archivo_f00.archivo.name)

    def test_sin_capacidad_de_dispositivos_es_403(self):
        self.assertEqual(self._cliente(usuario_con()).get(self.ruta).status_code, 403)

    def test_el_administrador_del_programa_baja_el_f00(self):
        admin = usuario_con("dispositivo.ver", "programa.configurar", username="admin_disp", programa=self.programa)

        self.assertEqual(self._cliente(admin).get(self.ruta).status_code, 200)

    def test_el_operador_sin_asignacion_al_dispositivo_no_lo_baja(self):
        """Mismo rol, otro dispositivo: el alcance fino es la asignación."""
        operador = usuario_con("dispositivo.ver", username="operador_disp", programa=self.programa)

        self.assertEqual(self._cliente(operador).get(self.ruta).status_code, 403)

    def test_el_operador_asignado_al_dispositivo_lo_baja(self):
        from programas.models import AsignacionDispositivo

        operador = usuario_con("dispositivo.ver", username="operador_asignado", programa=self.programa)
        AsignacionDispositivo.objects.create(dispositivo=self.dispositivo, rol=operador.groups.first(), activo=True)

        self.assertEqual(self._cliente(operador).get(self.ruta).status_code, 200)


class AlcanceMerenderosTests(MediaBaseTests):
    """La documentación respaldatoria de una solicitud pide `merendero.ver`."""

    def setUp(self):
        super().setUp()
        from programas.models import Programa, SolicitudMerendero

        self.programa, _ = Programa.objects.get_or_create(
            codigo="MERENDEROS",
            defaults={"nombre": "Merenderos", "tipo": Programa.TipoPrograma.MERENDEROS},
        )
        self.solicitud = SolicitudMerendero.objects.create(
            nombre="Merendero Los Pinos", documentacion=archivo("acta.pdf")
        )
        self.ruta = self._url(self.solicitud.documentacion.name)

    def test_sin_capacidad_es_403(self):
        self.assertEqual(self._cliente(usuario_con()).get(self.ruta).status_code, 403)

    def test_una_capacidad_de_otro_programa_no_alcanza(self):
        self.assertEqual(self._cliente(usuario_con("ciudadano.ver")).get(self.ruta).status_code, 403)

    def test_con_merendero_ver_descarga(self):
        operador = usuario_con("merendero.ver", username="op_merenderos", programa=self.programa)

        self.assertEqual(self._cliente(operador).get(self.ruta).status_code, 200)


class CoberturaDePrefijosTests(SimpleTestCase):
    """Ningún `FileField` del repo puede quedar sin regla de pertenencia."""

    def test_cada_prefijo_declarado_tiene_su_resolver(self):
        from core import rutas_media
        from core.views.media import REGLAS

        declarados = {v for k, v in vars(rutas_media).items() if k.startswith("PREFIJO_")}
        con_regla = {prefijo for prefijo, _ in REGLAS}

        self.assertEqual(
            sorted(declarados - con_regla),
            [],
            "prefijos de `core.rutas_media` sin regla en `media_protegida`: sus archivos dan 404.",
        )

    def test_los_upload_to_del_repo_caen_en_un_prefijo_conocido(self):
        """Un `upload_to` literal nuevo (sin pasar por `core.rutas_media`) se ve acá."""
        from django.apps import apps
        from django.db.models import FileField

        from core.views.media import REGLAS

        prefijos = tuple(prefijo for prefijo, _ in REGLAS)
        huerfanos = []
        for modelo in apps.get_models():
            for campo in modelo._meta.get_fields():
                if not isinstance(campo, FileField):
                    continue
                # `generate_filename` normaliza con `os.path`, que en Windows
                # devuelve `\`; lo guardado en la base siempre lleva `/`.
                ruta = campo.generate_filename(None, "x.pdf").replace("\\", "/")
                if not ruta.startswith(prefijos):
                    huerfanos.append(f"{modelo._meta.label}.{campo.name} -> {ruta}")

        self.assertEqual(huerfanos, [], "campos de archivo sin regla en `media_protegida`")


class NginxNoSirveMediaTests(SimpleTestCase):
    """Camino nginx (icore-srv/DEV): el contrato vive en los archivos de despliegue."""

    def setUp(self):
        self.nginx = (RAIZ / "nginx.conf").read_text(encoding="utf-8")

    def test_nginx_no_tiene_location_media(self):
        self.assertNotIn("location /media/", self.nginx)

    def test_nginx_expone_protected_media_como_internal(self):
        bloques = [b for b in self.nginx.split("location ") if b.startswith("/protected-media/")]
        # Un bloque por server (:80 y :443).
        self.assertEqual(len(bloques), 2)
        for bloque in bloques:
            cuerpo = bloque.split("}")[0]
            self.assertIn("internal;", cuerpo)
            self.assertIn("alias /media/;", cuerpo)

    def test_los_textos_de_despliegue_dicen_lo_que_pasa_de_verdad(self):
        """R0b-08: seguían diciendo que `/media/` lo sirve nginx y que el
        middleware lo exime. Las dos cosas son falsas desde la etapa 1."""
        for ruta in (".env.qa.example", "docs/client/architecture.md", "docker/k8s/README.md"):
            texto = (RAIZ / ruta).read_text(encoding="utf-8")
            self.assertNotIn("SERVE_MEDIA", texto, ruta)

        arquitectura = (RAIZ / "docs/client/architecture.md").read_text(encoding="utf-8")
        self.assertNotIn("excepto `/static/` y `/media/`", arquitectura)
        self.assertIn("media_protegida", arquitectura)

    def test_el_compose_de_prod_ya_no_necesita_un_flag_para_servir_media(self):
        """La ruta existe siempre: un flag que la apague deja `/media/` en 404."""
        compose = (RAIZ / "docker-compose.prod.yml").read_text(encoding="utf-8")

        self.assertNotIn("- SERVE_MEDIA=", compose)

    def test_x_accel_viene_apagado_en_el_repo(self):
        """Prenderlo necesita el `location internal`; en ECOM es D-09/H-05."""
        compose = (RAIZ / "docker-compose.prod.yml").read_text(encoding="utf-8")

        self.assertNotIn("\n      - MEDIA_X_ACCEL=True", compose)
        self.assertFalse(settings.MEDIA_X_ACCEL)
