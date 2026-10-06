"""El adjunto, desde el canal que lo sube hasta la pantalla de revisión (RED-05).

El archivo que la persona sube se escribe en dos lugares distintos —
``inscripcion_publica.crear_formulario_publico`` (link público) y el ``POST
…/adjuntos/`` de la API (app de campo)— y se lee en uno solo:
``respuestas.respuestas_legibles``, que lo busca con la clave del ítem de la
**foto** de la definición (``pg-<pk>`` / ``rn-<pk>``, ``diseno.clave_pregunta``)
contra el índice que arma ``_adjuntos_por_clave``.

Hasta acá las dos mitades se probaban por separado y con datos distintos: el
alta afirmaba que la fila ``AdjuntoFormulario`` se creaba
(``portal.tests.test_inscripcion_envio``, ``programas.tests.test_becas_api``) y
la revisión se probaba con un adjunto fabricado a mano en el test
(``test_becas_revision``). Nadie cruzaba el puente. Cambiar el prefijo de la
clave en ``clave_pregunta`` sin tocar ``_adjuntos_por_clave`` hace que la foto
del DNI desaparezca de la pantalla del revisor **sin error ni log**: el revisor
la ve como «faltante» y rechaza el caso.

El tercer caso que pide la ficha —una pregunta recreada con otro pk deja el
adjunto huérfano— es el test invertido de DAT-01 y va en el PR de esa ficha.
"""

import shutil
import tempfile
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core import rbac
from portal.services import inscripcion as servicio_portal
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_TERRITORIAL
from programas.models import (
    AdjuntoFormulario,
    Convocatoria,
    Formulario,
    OrigenRequisito,
    PreguntaGlobal,
    Relevamiento,
    Segmento,
    TipoCampo,
)
from programas.services.diseno import clave_pregunta
from programas.services.padron import cargar_padron
from programas.views.relevamientos import CAP_RELEVAMIENTO_PUBLICO
from users.models import Capacidad

#: Lo que sube la persona. El contenido no importa; el nombre sí, porque la API
#: solo acepta las extensiones de ``ADJUNTO_EXTENSIONES``.
NOMBRE_ARCHIVO = "foto-dni.jpg"
CONTENIDO = b"\xff\xd8\xff fake jpeg"

FILA_PADRON = {
    "dni": "30123456",
    "sexo": "F",
    "nombre": "María Luján",
    "apellido": "Gómez",
    "fecha_nacimiento": date(1991, 3, 14),
}


@override_settings(PERSONAS_API_ACTIVA=False)
class AdjuntoLlegaALaRevisionTests(TestCase):
    """Un archivo subido por cada canal tiene que verse en ``formulario_detalle``."""

    @classmethod
    def setUpClass(cls):
        # Los adjuntos van a un `media/` descartable: el almacenamiento no se
        # revierte con la transacción del test y, si no, cada corrida deja
        # archivos sueltos en el `media/` del repo.
        cls._media = tempfile.mkdtemp(prefix="adjuntos-red05-")
        cls.addClassCleanup(shutil.rmtree, cls._media, ignore_errors=True)
        cls._media_override = override_settings(MEDIA_ROOT=cls._media)
        cls._media_override.enable()
        cls.addClassCleanup(cls._media_override.disable)
        super().setUpClass()

    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.segmento = Segmento.objects.create(nombre="Seg", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        # La pregunta ARCHIVO que el revisor tiene que ver resuelta. Entra al
        # diseño de la convocatoria por ser una pregunta general activa.
        self.pregunta = PreguntaGlobal.objects.create(
            texto="Foto del DNI",
            tipo=TipoCampo.ARCHIVO,
            obligatorio=False,
            orden=900,
        )
        self.clave = clave_pregunta(self.pregunta)
        # `seed_becas` siembra cinco requisitos ARCHIVO obligatorios (foto de
        # DNI frente y dorso, domicilio, estudios, confidencialidad). El test
        # mira un solo campo: los demás salen del diseño para no tener que
        # subir cinco archivos por envío.
        PreguntaGlobal.objects.filter(tipo=TipoCampo.ARCHIVO).exclude(pk=self.pregunta.pk).update(activo=False)
        self.revisor = User.objects.create_user("admin_becas", password="x")
        rol_admin = Group.objects.get(name=ROL_ADMIN)
        self.revisor.groups.add(rol_admin)
        # RN-P13: sin `becas.relevamiento.publico` un relevamiento del link no
        # existe para el usuario, ni siquiera para el Administrador del programa.
        rol_admin.permissions.add(
            Permission.objects.get(
                codename=rbac.codename_de(CAP_RELEVAMIENTO_PUBLICO),
                content_type=ContentType.objects.get_for_model(Capacidad),
            )
        )

    # ── Aserción común a los dos canales ────────────────────────────────────

    def _assert_el_adjunto_se_ve_en_la_revision(self, formulario):
        """El puente: la clave del ítem de la foto encuentra el adjunto guardado.

        Afirma las dos puntas (fila en la base y bloque renderizado) y que el
        HTML trae la URL del archivo, que es lo que el revisor abre.
        """
        adjunto = AdjuntoFormulario.objects.get(formulario=formulario)

        self.client.force_login(self.revisor)
        resp = self.client.get(reverse("becas:formulario_detalle", args=[formulario.pk]))

        self.assertEqual(resp.status_code, 200)
        bloques = resp.context["bloques"]
        self.assertIsNotNone(
            bloques,
            "El caso quedó sin foto de la definición: la revisión cae al camino viejo por pk y el puente no se prueba.",
        )
        filas = [fila for bloque in bloques for fila in bloque["items"] if fila.get("clave") == self.clave]
        self.assertEqual(len(filas), 1, f"El ítem {self.clave} no llegó a la pantalla de revisión.")
        fila = filas[0]
        self.assertTrue(fila["es_archivo"], "El campo ARCHIVO dejó de reconocerse como tal.")
        self.assertIsNotNone(
            fila["adjunto"],
            f"El adjunto existe (pk={adjunto.pk}) pero la revisión lo resuelve en None: "
            "la clave del ítem y el índice de `_adjuntos_por_clave` dejaron de coincidir.",
        )
        self.assertEqual(fila["adjunto"].pk, adjunto.pk)
        self.assertEqual(fila["adjunto"].pregunta_global_id, self.pregunta.pk)
        self.assertTrue(adjunto.archivo.name.endswith(".jpg"), adjunto.archivo.name)
        with adjunto.archivo.open("rb") as guardado:
            self.assertEqual(guardado.read(), CONTENIDO)
        self.assertContains(resp, adjunto.archivo.url)

    # ── Canal 1: el link público ────────────────────────────────────────────

    def _relevamiento_publico(self):
        return Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )

    def test_el_archivo_subido_por_el_link_se_ve_en_la_revision(self):
        relevamiento = self._relevamiento_publico()
        # Con el padrón como fuente de identidad el paso 1 no sale a la red.
        cargar_padron(self.convocatoria, None, [FILA_PADRON])

        sesion = self.client.session
        sesion[servicio_portal.SESSION_KEY_CAPTCHA] = 7
        sesion[servicio_portal.SESSION_KEY_CAPTCHA_PREGUNTA] = "¿Cuánto es 3 + 4?"
        sesion.save()
        paso1 = self.client.post(
            reverse("portal:inscripcion_paso1", kwargs={"token": relevamiento.token_publico}),
            {"dni": "30123456", "sexo": "F", "captcha": "7"},
        )
        self.assertEqual(paso1.status_code, 302, "El paso 1 no identificó a la persona.")

        url_paso2 = reverse("portal:inscripcion_paso2", kwargs={"token": relevamiento.token_publico})
        # El GET fija la huella del formulario en la sesión (Cambio 58): sin él
        # el POST contesta «el formulario cambió» y no ingesta nada.
        self.assertEqual(self.client.get(url_paso2).status_code, 200)
        paso2 = self.client.post(url_paso2, self._datos_paso2(), follow=False)
        self.assertEqual(paso2.status_code, 302, getattr(paso2, "context", None) and paso2.context["form"].errors)

        formulario = Formulario.objects.get(relevamiento=relevamiento)
        self._assert_el_adjunto_se_ve_en_la_revision(formulario)

    def _datos_paso2(self):
        """Contacto, apoderado y el archivo, cada uno por su clave de ítem."""

        def clave(origen, vinculo):
            return clave_pregunta(PreguntaGlobal.objects.get(origen=origen, vinculo=vinculo))

        datos = {
            clave(OrigenRequisito.LEGAJO, "telefono"): "3624123456",
            clave(OrigenRequisito.LEGAJO, "email"): "maria@correo.com",
            clave(OrigenRequisito.PERSONA_VINCULADA, "nombre"): "Ana",
            clave(OrigenRequisito.PERSONA_VINCULADA, "apellido"): "Gómez",
            clave(OrigenRequisito.PERSONA_VINCULADA, "dni"): "20111222",
            clave(OrigenRequisito.PERSONA_VINCULADA, "genero"): "F",
            clave(OrigenRequisito.PERSONA_VINCULADA, "fecha_nacimiento"): "1980-05-05",
            self.clave: SimpleUploadedFile(NOMBRE_ARCHIVO, CONTENIDO, content_type="image/jpeg"),
        }
        return datos

    # ── Canal 2: la app de campo ────────────────────────────────────────────

    def test_el_archivo_subido_por_la_app_se_ve_en_la_revision(self):
        territorial = User.objects.create_user("terri", password="secret123")
        territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=territorial,
            fecha_asignada=timezone.localdate(),
            zona="Centro",
            estado=Relevamiento.Estado.EN_CURSO,
        )

        token, _ = Token.objects.get_or_create(user=territorial)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        alta = api.post(
            reverse("becas_api:relevamiento-formularios", args=[relevamiento.pk]),
            {
                "celular": "3624111222",
                "email_contacto": "campo@demo.local",
                "datos_identificacion": {"dni": "40400400", "sexo": "F"},
                "data": {"globales": {}, "requisitos": {}},
            },
            format="json",
        )
        self.assertEqual(alta.status_code, 201, alta.data)
        formulario_pk = alta.data["id"]

        subida = api.post(
            reverse("becas_api:formulario-adjuntos", args=[formulario_pk]),
            {
                "pregunta_global": self.pregunta.pk,
                "archivo": SimpleUploadedFile(NOMBRE_ARCHIVO, CONTENIDO, content_type="image/jpeg"),
            },
            format="multipart",
        )
        self.assertEqual(subida.status_code, 201, subida.data)

        self._assert_el_adjunto_se_ve_en_la_revision(Formulario.objects.get(pk=formulario_pk))
