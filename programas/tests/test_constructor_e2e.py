"""Punta a punta del constructor de formularios (Cambio 58, task #351).

El recorrido que pide QA, con las vistas reales y sin atajos de servicio:

1. el equipo arma el formulario de la convocatoria en el constructor;
2. una persona se inscribe por el link público, en sus dos pasos;
3. el revisor abre el caso y lo ve desde la **foto** de lo que la persona tuvo
   delante;
4. el equipo cambia el formulario (renombra un requisito y agrega un campo
   propio);
5. el caso viejo **no cambia** (D3) y una inscripción nueva sí ve lo nuevo.

Cada pieza tiene su test unitario en su módulo (ver el mapa de #351); este
existe para que una regresión en la costura entre el constructor, el link y la
revisión no pueda pasar con todos los unitarios en verde.
"""

import json
import shutil
import tempfile
from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django import forms
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings, tag
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core import rbac
from portal.services import inscripcion as servicio_inscripcion
from programas.management.commands.seed_becas import ROL_ADMIN, ROL_COORDINADOR, ROL_TERRITORIAL
from programas.models import (
    AsignacionCoordinador,
    Convocatoria,
    DisenoFormulario,
    Formulario,
    GrupoRequisito,
    ItemDiseno,
    OrigenRequisito,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TipoCampo,
)
from programas.services.autorizacion import CAP_RELEVAMIENTO_PUBLICO
from programas.services.diseno import clave_pregunta, clave_requisito, obtener_o_crear_diseno
from users.models import Capacidad

PERSONAS = {
    "30123456": {"nombre": "María Luján", "apellido": "Gómez", "fecha_nacimiento": "1991-03-14"},
    "28111222": {"nombre": "Ana", "apellido": "Ruiz", "fecha_nacimiento": "1995-07-02"},
}


def _base_de_personas(dni, sexo):
    """La Base de Personas simulada: encuentra a las dos personas del test."""
    return {"success": True, "data": {"dni": dni, "sexo": sexo, **PERSONAS[dni]}}


@override_settings(PERSONAS_API_ACTIVA=True)
@patch("programas.services.identidad.consultar_persona", side_effect=_base_de_personas)
class ConstructorDePuntaAPuntaTests(TestCase):
    @classmethod
    def setUpClass(cls):
        # Los adjuntos del paso 2 van a un `media/` descartable (mismo patrón que
        # `test_adjunto_punta_a_punta`): el almacenamiento no se revierte con la
        # transacción del test.
        cls._media = tempfile.mkdtemp(prefix="constructor-e2e-")
        cls.addClassCleanup(shutil.rmtree, cls._media, ignore_errors=True)
        cls._media_override = override_settings(MEDIA_ROOT=cls._media)
        cls._media_override.enable()
        cls.addClassCleanup(cls._media_override.disable)
        super().setUpClass()

    def setUp(self):
        cache.clear()
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin-e2e", password="x")
        rol_admin = Group.objects.get(name=ROL_ADMIN)
        self.admin.groups.add(rol_admin)
        # RN-P13: sin `becas.relevamiento.publico` un caso del link no existe
        # para el usuario, ni siquiera para el Administrador del programa.
        rol_admin.permissions.add(
            Permission.objects.get(
                codename=rbac.codename_de(CAP_RELEVAMIENTO_PUBLICO),
                content_type=ContentType.objects.get_for_model(Capacidad),
            )
        )
        # Dos navegadores: el backoffice y el de la persona que se inscribe.
        self.backoffice = Client()
        self.backoffice.force_login(self.admin)

        self.segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario"],
            segmento=self.segmento,
            obligatorio=True,
            orden=1,
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )
        self.k_nivel = clave_requisito(self.nivel)

    # ── backoffice: constructor ──────────────────────────────────────────────
    def _constructor(self, nombre, *args):
        return reverse(f"becas:{nombre}", args=[self.convocatoria.pk, *args])

    def _mutar(self, nombre, data, *args):
        resp = self.backoffice.post(self._constructor(nombre, *args), data, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json()["ok"], resp.content)
        return resp

    def _version(self):
        return DisenoFormulario.objects.get(convocatoria=self.convocatoria).version

    def _armar_formulario(self):
        """El equipo abre el constructor y suma un grupo con un campo propio."""
        resp = self.backoffice.get(self._constructor("convocatoria_formulario"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Nivel educativo", resp.content.decode())
        self._mutar("formulario_grupo_crear", {"etiqueta": "Situación laboral", "canal": "ambos"})
        grupo = DisenoFormulario.objects.get(convocatoria=self.convocatoria).items.get(etiqueta="Situación laboral")
        self._mutar(
            "formulario_propio_crear",
            {
                "padre": grupo.clave,
                "texto": "¿Trabajás?",
                "tipo": "SELECTOR",
                "opciones_texto": "Sí\nNo",
                "presentacion": "LISTA",
                "obligatorio": "on",
                "canal": "ambos",
            },
        )
        self.grupo_laboral = grupo.clave
        self.k_trabaja = grupo.hijos.get(tipo=ItemDiseno.Tipo.CAMPO).clave

    def _cambiar_formulario(self):
        """Después de la primera inscripción: se renombra el requisito del
        catálogo (solo en este diseño) y se agrega otro campo propio."""
        self._mutar("formulario_item_editar", {"etiqueta": "Máximo nivel alcanzado"}, self.k_nivel)
        self._mutar(
            "formulario_propio_crear",
            {
                "padre": self.grupo_laboral,
                "texto": "Cantidad de hijos",
                "tipo": "INT",
                "obligatorio": "on",
                "canal": "ambos",
            },
        )
        diseno = DisenoFormulario.objects.get(convocatoria=self.convocatoria)
        self.k_hijos = diseno.items.get(tipo=ItemDiseno.Tipo.CAMPO, propio__texto="Cantidad de hijos").clave

    # ── link público: los dos pasos ──────────────────────────────────────────
    def _token(self):
        return {"token": self.relevamiento.token_publico}

    def _clave_vinculo(self, origen, vinculo):
        return clave_pregunta(PreguntaGlobal.objects.get(origen=origen, vinculo=vinculo))

    def _inscribirse(self, dni, extra):
        """Paso 1 (DNI + sexo + captcha) y paso 2 (el formulario del diseño).
        Devuelve el caso creado y la pantalla del paso 2 que vio la persona."""
        persona = Client()
        sesion = persona.session
        sesion[servicio_inscripcion.SESSION_KEY_CAPTCHA] = 7
        sesion[servicio_inscripcion.SESSION_KEY_CAPTCHA_PREGUNTA] = "¿Cuánto es 3 + 4?"
        sesion.save()
        resp = persona.post(
            reverse("portal:inscripcion_paso1", kwargs=self._token()), {"dni": dni, "sexo": "F", "captcha": "7"}
        )
        self.assertRedirects(
            resp, reverse("portal:inscripcion_paso2", kwargs=self._token()), fetch_redirect_response=False
        )

        paso2 = persona.get(reverse("portal:inscripcion_paso2", kwargs=self._token()))
        self.assertEqual(paso2.status_code, 200)
        form = paso2.context["form"]
        datos = {
            self._clave_vinculo(OrigenRequisito.LEGAJO, "telefono"): "3624123456",
            self._clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "nombre"): "Rosa",
            self._clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "apellido"): "Gómez",
            self._clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "dni"): "20111222",
            self._clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "genero"): "F",
            self._clave_vinculo(OrigenRequisito.PERSONA_VINCULADA, "fecha_nacimiento"): "1965-05-05",
            self.k_nivel: "Secundario",
            **extra,
        }
        # Los adjuntos obligatorios del catálogo de Becas: uno por campo de archivo.
        for nombre, campo in form.fields.items():
            if isinstance(campo, forms.FileField):
                datos[nombre] = SimpleUploadedFile(f"{nombre}.png", b"\x89PNG\r\n\x1a\nfake", content_type="image/png")
        resp = persona.post(reverse("portal:inscripcion_paso2", kwargs=self._token()), datos)
        self.assertEqual(resp.status_code, 302, getattr(resp.context and resp.context.get("form"), "errors", ""))
        caso = Formulario.objects.get(relevamiento=self.relevamiento, ciudadano__dni=dni)
        return caso, paso2

    # ── backoffice: revisión ─────────────────────────────────────────────────
    def _revision(self, caso):
        resp = self.backoffice.get(reverse("becas:formulario_detalle", args=[caso.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.context["bloques"], "el caso tiene que leerse desde su foto")
        filas = {i["clave"]: i for b in resp.context["bloques"] for i in b["items"] if i.get("tipo") == "campo"}
        return resp.content.decode(), filas

    # ── el recorrido ─────────────────────────────────────────────────────────
    def test_cambiar_el_formulario_no_reescribe_lo_que_respondio_un_caso_viejo(self, _consulta):
        self._armar_formulario()
        version_inicial = self._version()

        # La persona ve el formulario armado y lo responde.
        # De paso, un intento de pisar la identidad que validó el paso 1: esas
        # claves no son campos del paso 2 y lo que llegue para ellas se ignora.
        k_nombre = self._clave_vinculo(OrigenRequisito.LEGAJO, "nombre")
        viejo, paso2 = self._inscribirse("30123456", {self.k_trabaja: "Sí", k_nombre: "Nombre Inventado"})
        self.assertIn(f'name="{self.k_trabaja}"', paso2.content.decode())
        self.assertNotIn(f'name="{k_nombre}"', paso2.content.decode())
        self.assertEqual(viejo.estado, Formulario.Estado.ENVIADO)
        self.assertEqual(viejo.definicion["version"], version_inicial)
        self.assertEqual(viejo.respuestas[self.k_trabaja], "Sí")
        self.assertEqual(viejo.respuestas[self.k_nivel], "Secundario")
        self.assertEqual(viejo.respuestas[k_nombre], "María Luján")
        self.assertEqual(viejo.ciudadano.nombre, "María Luján")
        foto_original = json.loads(json.dumps(viejo.definicion))

        # El revisor lo ve desde la foto.
        html, filas = self._revision(viejo)
        self.assertEqual(filas[self.k_nivel]["label"], "Nivel educativo")
        self.assertEqual(filas[self.k_nivel]["valor"], "Secundario")
        self.assertEqual(filas[self.k_trabaja]["label"], "¿Trabajás?")
        self.assertEqual(filas[self.k_trabaja]["valor"], "Sí")
        self.assertIn("Nivel educativo", html)

        # El equipo cambia el formulario.
        self._cambiar_formulario()
        self.assertGreater(self._version(), version_inicial)

        # El caso viejo no se movió: ni su foto ni lo que muestra la revisión.
        viejo.refresh_from_db()
        self.assertEqual(viejo.definicion, foto_original)
        html, filas = self._revision(viejo)
        self.assertEqual(filas[self.k_nivel]["label"], "Nivel educativo")
        self.assertEqual(filas[self.k_nivel]["valor"], "Secundario")
        self.assertNotIn(self.k_hijos, filas)
        self.assertNotIn("Cantidad de hijos", html)
        self.assertNotIn("Máximo nivel alcanzado", html)

        # Una inscripción nueva sí ve lo nuevo, y la revisión se lo muestra.
        nuevo, paso2 = self._inscribirse("28111222", {self.k_trabaja: "No", self.k_hijos: "2"})
        self.assertIn(f'name="{self.k_hijos}"', paso2.content.decode())
        self.assertIn("Máximo nivel alcanzado", paso2.content.decode())
        self.assertEqual(nuevo.definicion["version"], self._version())
        html, filas = self._revision(nuevo)
        self.assertEqual(filas[self.k_nivel]["label"], "Máximo nivel alcanzado")
        self.assertEqual(filas[self.k_hijos]["label"], "Cantidad de hijos")
        self.assertEqual(filas[self.k_hijos]["valor"], "2")

    def test_el_campo_nuevo_obligatorio_no_se_le_exige_al_caso_viejo(self, _consulta):
        """La contracara en la edición: el revisor guarda el contacto de un caso
        viejo y eso no le agrega el campo que nació después ni le cambia la foto."""
        self._armar_formulario()
        viejo, _ = self._inscribirse("30123456", {self.k_trabaja: "Sí"})
        self._cambiar_formulario()
        foto_original = Formulario.objects.get(pk=viejo.pk).definicion

        resp = self.backoffice.post(
            reverse("becas:formulario_detalle", args=[viejo.pk]),
            {"celular": "3629999999", "email_contacto": "maria@correo.com"},
        )
        self.assertEqual(resp.status_code, 302)
        viejo.refresh_from_db()
        self.assertEqual(viejo.definicion, foto_original)
        self.assertNotIn(self.k_hijos, viejo.respuestas)
        self.assertEqual(viejo.respuestas[self.k_trabaja], "Sí")
        self.assertEqual(viejo.respuestas[self._clave_vinculo(OrigenRequisito.LEGAJO, "telefono")], "3629999999")


class PayloadViejoDeLaAppTests(TestCase):
    """El mismo recorrido por el otro canal: la app de campo instalada, que no
    conoce el constructor y sigue mandando el contrato anterior (TC-351-04).

    El backend lo traduce: el caso queda con respuestas por clave, la foto del
    diseño **vigente** al momento del alta y el apoderado vinculado a su legajo.
    El servidor no acepta una foto mandada por el cliente (``definicion`` no es
    un campo del serializer): guarda siempre la suya y anota la versión que dice
    la app en ``version_capturada`` (G1-16).
    """

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin-app-e2e", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.backoffice = Client()
        self.backoffice.force_login(self.admin)
        self.territorial = User.objects.create_user("terri-app-e2e", password="x")
        self.territorial.groups.add(Group.objects.get(name=ROL_TERRITORIAL))
        self.app = APIClient()
        token, _ = Token.objects.get_or_create(user=self.territorial)
        self.app.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario"],
            segmento=segmento,
            orden=1,
        )
        self.tenencia = PreguntaGlobal.objects.create(
            texto="Tenencia de la vivienda", tipo=TipoCampo.SELECTOR, opciones=["Propia", "Alquilada"], orden=600
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=self.territorial,
            fecha_asignada=timezone.localdate(),
            zona="Centro",
            estado=Relevamiento.Estado.EN_CURSO,
        )

    def _renombrar_nivel(self, etiqueta):
        if not DisenoFormulario.objects.filter(convocatoria=self.convocatoria).exists():
            self.assertEqual(
                self.backoffice.get(reverse("becas:convocatoria_formulario", args=[self.convocatoria.pk])).status_code,
                200,
            )
        resp = self.backoffice.post(
            reverse("becas:formulario_item_editar", args=[self.convocatoria.pk, clave_requisito(self.nivel)]),
            {"etiqueta": etiqueta},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200, resp.content)

    def _payload_de_la_app_instalada(self):
        """Exactamente lo que manda la app de hoy: columnas fijas y ``data`` por
        pk, sin ``respuestas`` ni ``definicion``."""
        menor = (timezone.localdate() - timedelta(days=10 * 365)).isoformat()
        return {
            "client_uuid": "6a1f0c1e-3b7a-4d43-9a43-0b3f2a7c5e11",
            "capturado_en": timezone.now().isoformat(),
            "datos_identificacion": {
                "dni": "45111222",
                "nombre": "Lucas",
                "apellido": "Benítez",
                "sexo": "M",
                "fecha_nacimiento": menor,
            },
            "celular": "3624555666",
            "email_contacto": "familia@correo.com",
            "apoderado_nombre": "Laura",
            "apoderado_apellido": "Benítez",
            "apoderado_dni": "27333444",
            "apoderado_genero": "F",
            "apoderado_fecha_nacimiento": "1985-05-10",
            "gps_lat": "-27.451000",
            "gps_lng": "-58.986000",
            "data": {
                "globales": {str(self.tenencia.pk): "Alquilada"},
                "requisitos": {str(self.nivel.pk): "Primario"},
            },
        }

    def test_la_app_vieja_queda_con_respuestas_foto_vigente_y_apoderado(self):
        self._renombrar_nivel("Nivel que cursa")
        version = DisenoFormulario.objects.get(convocatoria=self.convocatoria).version

        resp = self.app.post(
            reverse("becas_api:relevamiento-formularios", args=[self.relevamiento.pk]),
            self._payload_de_la_app_instalada(),
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        caso = Formulario.objects.get(pk=resp.data["id"])
        # Respuestas por clave, traducidas desde `data` y las columnas fijas.
        self.assertEqual(caso.respuestas[clave_pregunta(self.tenencia)], "Alquilada")
        self.assertEqual(caso.respuestas[clave_requisito(self.nivel)], "Primario")
        telefono = clave_pregunta(PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="telefono"))
        apoderado_dni = clave_pregunta(
            PreguntaGlobal.objects.get(origen=OrigenRequisito.PERSONA_VINCULADA, vinculo="dni")
        )
        self.assertEqual(caso.respuestas[telefono], "3624555666")
        self.assertEqual(caso.respuestas[apoderado_dni], "27333444")
        # La foto es la del diseño vigente, con su versión y su etiqueta.
        self.assertEqual(caso.definicion["version"], version)
        campo_nivel = next(
            c
            for g in caso.definicion["items"]
            for c in g.get("items", [])
            if c.get("clave") == clave_requisito(self.nivel)
        )
        self.assertEqual(campo_nivel["texto"], "Nivel que cursa")
        # El apoderado queda vinculado a su propio legajo.
        self.assertEqual(caso.apoderado_ciudadano.dni, "27333444")

        # Cambia el diseño: el caso de la app tampoco se reinterpreta.
        foto_original = caso.definicion
        self._renombrar_nivel("Otro nombre")
        caso.refresh_from_db()
        self.assertEqual(caso.definicion, foto_original)
        resp = self.backoffice.get(reverse("becas:formulario_detalle", args=[caso.pk]))
        self.assertEqual(resp.status_code, 200)
        filas = {i["clave"]: i for b in resp.context["bloques"] for i in b["items"] if i.get("tipo") == "campo"}
        self.assertEqual(filas[clave_requisito(self.nivel)]["label"], "Nivel que cursa")
        self.assertEqual(filas[clave_requisito(self.nivel)]["valor"], "Primario")


@tag("performance")
class PresupuestoConDiezYCuarentaItemsTests(TestCase):
    """TC-350-04 / TC-351-03: el constructor (que es también la vista previa:
    la vista previa se dibuja en el navegador con los datos que trae esta misma
    pantalla, no tiene pedido propio) y el paso 2 del link cuestan lo mismo con
    10 ítems que con 40, con condiciones en la misma proporción."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="constructor-presupuesto-")
        cls.addClassCleanup(shutil.rmtree, cls._media, ignore_errors=True)
        cls._media_override = override_settings(MEDIA_ROOT=cls._media)
        cls._media_override.enable()
        cls.addClassCleanup(cls._media_override.disable)
        super().setUpClass()

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        self.admin = User.objects.create_user("admin-presupuesto", password="x")
        self.admin.groups.add(Group.objects.get(name=ROL_ADMIN))
        self.backoffice = Client()
        self.backoffice.force_login(self.admin)

    def _escenario(self, cantidad):
        """Una convocatoria con ``cantidad`` requisitos propios de su segmento;
        uno de cada dos depende del anterior («completo»)."""
        segmento = Segmento.objects.create(nombre=f"Seg {cantidad}", cupo_maximo=1000)
        convocatoria = Convocatoria.objects.create(
            nombre=f"Conv {cantidad}", segmento=segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        requisitos = [
            RequisitoNativo.objects.create(
                texto=f"Pregunta {orden}", tipo=TipoCampo.STRING, segmento=segmento, obligatorio=False, orden=orden
            )
            for orden in range(1, cantidad + 1)
        ]
        diseno, _ = obtener_o_crear_diseno(convocatoria)
        for anterior, dependiente in zip(requisitos[::2], requisitos[1::2]):
            diseno.items.filter(clave=clave_requisito(dependiente)).update(
                condicion={
                    "modo": "todas",
                    "reglas": [{"fuente": clave_requisito(anterior), "op": "completo", "valor": None}],
                }
            )
        relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=timezone.now() - timedelta(days=1),
            fecha_hasta=timezone.now() + timedelta(days=10),
        )
        return convocatoria, relevamiento, requisitos

    #: Medido con Python 3.12 + Django 5.2 sobre SQLite (el par del CI). Si una
    #: mejora los baja, se bajan acá; si un cambio los sube, el test dice
    #: cuántas consultas paga de más y en cuál de los dos tamaños.
    CONSULTAS_CONSTRUCTOR = 23
    CONSULTAS_PASO2 = 9

    def _medir(self, cantidad, dni):
        convocatoria, relevamiento, _ = self._escenario(cantidad)
        url_constructor = reverse("becas:convocatoria_formulario", args=[convocatoria.pk])
        # El primer pedido de la sesión registra la sesión única de backoffice
        # (un UPDATE que no tiene nada que ver con los ítems): fuera de la medición.
        self.backoffice.get(url_constructor)
        cache.clear()
        with self.assertNumQueries(self.CONSULTAS_CONSTRUCTOR):
            resp = self.backoffice.get(url_constructor)
        self.assertEqual(resp.status_code, 200)
        campos = [i for i in resp.context["datos"]["items"] if i["clave"].startswith("rn-")]
        self.assertEqual(len(campos), cantidad)

        persona = Client()
        sesion = persona.session
        sesion[servicio_inscripcion.clave_sesion(relevamiento)] = {
            "dni": dni,
            "sexo": "F",
            "datos": {"nombre": "María", "apellido": "Gómez", "fecha_nacimiento": "1991-03-14"},
            "origen": "personas",
            "client_uuid": f"00000000-0000-4000-8000-0000{dni}",
        }
        sesion.save()
        cache.clear()
        with self.assertNumQueries(self.CONSULTAS_PASO2):
            resp = persona.get(reverse("portal:inscripcion_paso2", kwargs={"token": relevamiento.token_publico}))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len([p for p in resp.context["planos"] if p["clave"].startswith("rn-")]), cantidad)

    def test_con_10_items(self):
        self._medir(10, "30111222")

    def test_con_40_items(self):
        self._medir(40, "30333444")


class PermisosDelCatalogoYDelDisenoTests(TestCase):
    """TC-351-05: el coordinador del segmento arma el formulario de su
    convocatoria (orden, etiquetas, condiciones), pero el texto y las opciones
    del catálogo son del administrador: editarlos le da 403. El superusuario
    pasa.

    Cambio 334 (decisión del PM, 17/10/2026): el Coordinador sembrado suma
    ``becas.requisito.editar``, así que los requisitos **de su segmento** ya los
    corrige él. Siguen siendo del administrador las preguntas generales y los
    requisitos del programa."""

    def setUp(self):
        call_command("seed_becas", stdout=StringIO())
        cache.clear()
        self.segmento = Segmento.objects.create(nombre="Educación", cupo_maximo=100)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Becas 2026", segmento=self.segmento, fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 12, 31)
        )
        self.nivel = RequisitoNativo.objects.create(
            texto="Nivel educativo",
            tipo=TipoCampo.SELECTOR,
            opciones=["Primario", "Secundario"],
            segmento=self.segmento,
            orden=1,
        )
        self.tenencia = PreguntaGlobal.objects.create(
            texto="Tenencia de la vivienda", tipo=TipoCampo.SELECTOR, opciones=["Propia", "Alquilada"], orden=600
        )
        self.coordinador = User.objects.create_user("coord-e2e", password="x")
        self.coordinador.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(segmento=self.segmento, coordinador=self.coordinador)

    # Las dos ediciones van por AJAX, como las manda el modal de la pantalla:
    # sin la capacidad, `requiere` contesta 403 (a un POST común lo redirige al
    # inicio con un mensaje, que también es «no»).
    def _editar_requisito(self):
        return self.client.post(
            reverse("becas:requisito_editar", args=[self.nivel.pk]),
            {"texto": "Otro texto", "tipo": "SELECTOR", "opciones_texto": "A\nB", "obligatorio": "True"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def _editar_pregunta(self):
        return self.client.post(
            reverse("becas:pregunta_editar", args=[self.tenencia.pk]),
            {"texto": "Otro texto", "tipo": "SELECTOR", "opciones_texto": "A\nB", "obligatorio": "True", "orden": 600},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

    def test_el_coordinador_arma_el_diseno_pero_no_toca_el_catalogo(self):
        self.client.force_login(self.coordinador)
        # El diseño de su convocatoria, sí.
        self.assertEqual(
            self.client.get(reverse("becas:convocatoria_formulario", args=[self.convocatoria.pk])).status_code, 200
        )
        resp = self.client.post(
            reverse("becas:formulario_item_editar", args=[self.convocatoria.pk, clave_requisito(self.nivel)]),
            {"etiqueta": "Nivel que cursa", "tipo": "INT"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        # El requisito de su segmento, sí (Cambio 334).
        self.assertEqual(self._editar_requisito().status_code, 200)
        self.nivel.refresh_from_db()
        self.assertEqual((self.nivel.texto, self.nivel.opciones), ("Otro texto", ["A", "B"]))
        # La pregunta general del catálogo, no.
        self.assertEqual(self._editar_pregunta().status_code, 403)
        self.tenencia.refresh_from_db()
        self.assertEqual(
            (self.tenencia.texto, self.tenencia.opciones), ("Tenencia de la vivienda", ["Propia", "Alquilada"])
        )

    def test_el_superusuario_edita_el_catalogo(self):
        self.client.force_login(User.objects.create_superuser("super-e2e", password="x"))
        resp = self._editar_requisito()
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self._editar_pregunta()
        self.assertEqual(resp.status_code, 200, resp.content)
        self.nivel.refresh_from_db()
        self.tenencia.refresh_from_db()
        self.assertEqual((self.nivel.texto, self.nivel.opciones), ("Otro texto", ["A", "B"]))
        self.assertEqual((self.tenencia.texto, self.tenencia.opciones), ("Otro texto", ["A", "B"]))

    def test_el_coordinador_no_reordena_ni_agrupa_el_catalogo(self):
        """El drag & drop del catálogo y sus grupos son del catálogo, no del
        diseño: con sesión pero sin `becas.pregunta.editar`, 403 y nada cambia.
        (El test de `test_catalogo_drag` solo cubría al anónimo.)"""
        self.client.force_login(self.coordinador)
        cuestionario = GrupoRequisito.objects.get(clave="cuestionario")
        ordenes = dict(PreguntaGlobal.objects.values_list("pk", "orden"))
        resp = self.client.post(
            reverse("becas:preguntas_reordenar"),
            data=json.dumps({"grupos": [{"id": cuestionario.pk, "preguntas": [self.tenencia.pk]}]}),
            content_type="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(dict(PreguntaGlobal.objects.values_list("pk", "orden")), ordenes)
        resp = self.client.post(
            reverse("becas:grupo_crear"), {"nombre": "Nuevo grupo"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(GrupoRequisito.objects.filter(nombre="Nuevo grupo").exists())

    def test_el_coordinador_de_otro_segmento_no_abre_ni_cambia_el_diseno(self):
        otro = User.objects.create_user("coord-otro-e2e", password="x")
        otro.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        AsignacionCoordinador.objects.create(
            segmento=Segmento.objects.create(nombre="Otro", cupo_maximo=10), coordinador=otro
        )
        diseno, _ = obtener_o_crear_diseno(self.convocatoria)
        version = diseno.version
        self.client.force_login(otro)
        resp = self.client.get(reverse("becas:convocatoria_formulario", args=[self.convocatoria.pk]))
        self.assertIn(resp.status_code, (403, 404))
        resp = self.client.post(
            reverse("becas:formulario_item_editar", args=[self.convocatoria.pk, clave_requisito(self.nivel)]),
            {"etiqueta": "Intruso"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertIn(resp.status_code, (403, 404))
        diseno.refresh_from_db()
        self.assertEqual(diseno.version, version)
        self.assertEqual(diseno.items.get(clave=clave_requisito(self.nivel)).etiqueta, "")
