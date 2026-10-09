"""El HTML del detalle de revisión, congelado escenario por escenario (RED-54).

``formulario_detalle.html`` eran 1.214 líneas en un solo archivo —la pantalla más
cara de Becas, la que dio 500 por timeout contra la base de ECOM— y la Ola 7 la
parte en includes. Un refactor de template no tiene red: el HTML sale distinto y
*nada* falla, porque Django no se queja de un ``{% include %}`` que renderiza
otra cosa ni de un bloque que quedó afuera.

Esto son **snapshots**: el HTML renderizado de seis casos, guardado en
``programas/tests/snapshots/formulario_detalle/`` y comparado carácter por
carácter. Se generaron con el template entero, **antes** de partirlo; si después
de la partición siguen iguales, el refactor no se llevó nada puesto.

Qué se normaliza antes de comparar (y nada más que eso):

- el token CSRF, que cambia en cada render;
- las corridas de dígitos, porque los pks, las fechas y las horas cambian entre
  corridas y entre motores (el job ``Motor real`` corre esto contra MariaDB y
  MySQL, donde las secuencias no arrancan igual que en el SQLite del CI).

Cuando una pantalla cambia **a propósito**, el snapshot se regenera:

    ACTUALIZAR_SNAPSHOTS_DETALLE=1 python manage.py test \\
        programas.tests.test_becas_revision_detalle_html

y el diff de los snapshots queda en el PR, que es justamente lo que se quiere
revisar. Regenerar sin mirar el diff es tirar la red.

La extensión es ``.snapshot`` y no ``.html`` a propósito: el repo tiene barridos
que recorren **todo** el árbol buscando ``*.html`` —`core/tests/test_submit_guard.py`
y `scripts/design_audit.py`, entre otros— y para ellos estas copias del render
serían seis pantallas más, con la deuda de diseño de la original multiplicada por
seis. No son superficie: son la salida de una que ya se audita.
"""

import os
import re
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from core import rbac
from legajos.models import Ciudadano
from programas.management.commands.seed_becas import ROL_ADMIN
from programas.models import (
    AdjuntoFormulario,
    EnvioSIIS,
    Formulario,
    ListaEspera,
    PreguntaGlobal,
    Relevamiento,
    TipoCampo,
    TracaFormulario,
    ValidacionSIS,
)
from users.models import Capacidad

from .test_becas_revision import _BaseRevisionTest

SNAPSHOTS = Path(__file__).resolve().parent / "snapshots" / "formulario_detalle"

#: El token CSRF aparece **dos veces** y con formas distintas: en el `value` del
#: input oculto de cada `<form>` y como `csrfToken: "…"` dentro del JS del shell.
#: En vez de perseguir los dos sitios se normaliza el token en sí, que es lo que
#: Django genera: 64 caracteres alfanuméricos. Va **antes** que los dígitos, o el
#: token ya vendría partido en trozos.
CSRF_RE = re.compile(r"[A-Za-z0-9]{64}")
#: El nombre con el que se guarda un adjunto lo inventa el storage y es distinto
#: en cada corrida; lo que importa para el refactor es la **ruta**, no el nombre.
MEDIA_RE = re.compile(r"(/media/[\w/.-]*?/)[^/\"'\s]+(\.\w+)")
DIGITOS_RE = re.compile(r"\d+")


def _normalizar(html):
    # `\r\n` → `\n`: `core.autocrlf` deja los templates en CRLF en un checkout de
    # Windows y en LF en el del CI, así que el render trae un final de línea u
    # otro según dónde corra. `read_text()` ya normaliza el del snapshot.
    plano = html.replace("\r\n", "\n")
    return DIGITOS_RE.sub("N", MEDIA_RE.sub(r"\1ARCHIVO\2", CSRF_RE.sub("CSRF", plano)))


class RenderDelDetalleTests(_BaseRevisionTest):
    """Seis escenarios que encienden, entre todos, cada sección de la pantalla."""

    def setUp(self):
        super().setUp()
        # El escenario con adjuntos escribe un archivo de verdad: sin esto va al
        # `MEDIA_ROOT` del repo y queda ahí (mismo patrón que `test_adjuntos_rbac`).
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        contexto = override_settings(MEDIA_ROOT=self.media.name)
        contexto.enable()
        self.addCleanup(contexto.disable)
        self.ciudadano = Ciudadano.objects.create(
            dni="30123456", nombre="Ana", apellido="Gomez", fecha_nacimiento=date(1998, 4, 2), genero="F"
        )
        self.client.force_login(self.admin)

    # --- escenarios ----------------------------------------------------------

    def _con_adjuntos(self):
        """APROBADO con ciudadano, GPS, adjunto, respuesta, SIIS y traza.

        Enciende a la vez: identidad resuelta, mapa, «Respuestas» con un archivo,
        «Resultado SIIS», «Envío a SIIS» (solo existe en APROBADO), «Aviso al
        ciudadano» (solo con el caso resuelto) y «Traza de cambios».
        """
        self.form_a.ciudadano = self.ciudadano
        self.form_a.estado = Formulario.Estado.APROBADO
        self.form_a.gps_lat = -27.451
        self.form_a.gps_lng = -58.986
        pregunta = PreguntaGlobal.objects.create(texto="Foto DNI", tipo=TipoCampo.ARCHIVO, orden=1)
        texto = PreguntaGlobal.objects.create(texto="Ocupación", tipo=TipoCampo.STRING, orden=2)
        self.form_a.data = {"globales": {str(texto.pk): "Estudiante", str(pregunta.pk): None}, "requisitos": {}}
        self.form_a.save()
        AdjuntoFormulario.objects.create(
            formulario=self.form_a,
            pregunta_global=pregunta,
            archivo=SimpleUploadedFile("dni.jpg", b"imagen", content_type="image/jpeg"),
        )
        ValidacionSIS.objects.create(formulario=self.form_a, estado=ValidacionSIS.Estado.OK, solicitado_por=self.admin)
        EnvioSIIS.objects.create(
            formulario=self.form_a,
            estado=EnvioSIIS.Estado.RECHAZADO,
            documento=self.ciudadano.dni,
            codigo_error="DATOS_INVALIDOS",
            detalles={"barrio_actual": ["El campo barrio_actual debe contener al menos 4 caracteres."]},
            solicitado_por=self.admin,
        )
        TracaFormulario.objects.create(
            formulario=self.form_a, editado_por=self.admin, campo="Celular", valor_anterior="1", valor_nuevo="2"
        )
        return self.form_a

    def _sin_adjuntos(self):
        """El otro extremo: sin ciudadano, sin GPS, sin datos y en ENVIADO.

        Es el caso que deja a la vista casi todas las claves en `None`: lo que
        mide es que ninguna sección se dibuje a medias.
        """
        self.form_a.ciudadano = None
        self.form_a.estado = Formulario.Estado.ENVIADO
        self.form_a.gps_lat = None
        self.form_a.gps_lng = None
        self.form_a.data = {}
        self.form_a.save()
        return self.form_a

    def _rechazado(self):
        """Resuelto por rechazo: enciende el aviso de motivo y «Aviso al ciudadano»."""
        self.form_a.ciudadano = self.ciudadano
        self.form_a.estado = Formulario.Estado.RECHAZADO
        self.form_a.motivo_rechazo = "El domicilio está fuera de la zona de la convocatoria."
        self.form_a.save()
        return self.form_a

    def _publico(self):
        """Caso cargado por el link público: el relevamiento cambia de tipo y con
        él las migas, el origen y el badge de canal.

        `becas.relevamiento.publico` es **opt-in** (RN-P13): ni siquiera el rol
        de administración de Becas la trae sembrada, así que hay que tildarla o
        el caso da 403 antes de renderizar."""
        ct = ContentType.objects.get_for_model(Capacidad)
        Group.objects.get(name=ROL_ADMIN).permissions.add(
            Permission.objects.get(codename=rbac.codename_de("becas.relevamiento.publico"), content_type=ct)
        )
        self.rel_a.tipo = Relevamiento.Tipo.PUBLICO
        self.rel_a.territorial = None
        self.rel_a.save(update_fields=["tipo", "territorial"])
        self.form_a.ciudadano = self.ciudadano
        self.form_a.estado = Formulario.Estado.ENVIADO
        self.form_a.save()
        return self.form_a

    def _con_observaciones_de_carga(self):
        """G1-05: la alerta inline con lo que el servidor observó de la carga."""
        self.form_a.ciudadano = self.ciudadano
        self.form_a.estado = Formulario.Estado.ENVIADO
        self.form_a.observaciones_carga = (
            "La captura llegó 2 días después del cierre del relevamiento.\n"
            "  \n"
            "Faltan 1 adjunto(s) declarado(s) por la app."
        )
        self.form_a.save()
        return self.form_a

    def _en_espera(self):
        """CMP-N1: sin cupo el caso sigue en ENVIADO y la pantalla cambia entera
        (no se aprueba desde acá, se promueve desde Cupo)."""
        self.form_a.ciudadano = self.ciudadano
        self.form_a.estado = Formulario.Estado.ENVIADO
        self.form_a.save()
        ListaEspera.objects.create(formulario=self.form_a, segmento=self.seg_a, posicion=3)
        return self.form_a

    # --- comparación ---------------------------------------------------------
    #
    # Un test por escenario y no un `subTest` por cada uno: los escenarios
    # **mutan** el mismo caso y el mismo relevamiento (`_publico` lo pasa a link
    # público para siempre), así que compartir el método los encadenaría y el
    # segundo mediría el estado que dejó el primero. `setUp` los aísla.

    def _render(self, nombre):
        formulario = getattr(self, f"_{nombre}")()
        respuesta = self.client.get(reverse("becas:formulario_detalle", args=[formulario.pk]))
        self.assertEqual(respuesta.status_code, 200, f"el escenario «{nombre}» no llegó a renderizar")
        return _normalizar(respuesta.content.decode())

    def _comparar(self, nombre, *textos_esperados):
        """Compara contra el snapshot y, de paso, verifica que el escenario
        encienda la sección que viene a medir: sin eso, seis snapshots idénticos
        entre sí pasarían el test sin tocar una sola sección."""
        actual = self._render(nombre)
        for texto in textos_esperados:
            self.assertIn(_normalizar(texto), actual, f"«{texto}» no aparece en el escenario «{nombre}»")

        archivo = SNAPSHOTS / f"{nombre}.snapshot"
        if os.environ.get("ACTUALIZAR_SNAPSHOTS_DETALLE") == "1":
            SNAPSHOTS.mkdir(parents=True, exist_ok=True)
            archivo.write_text(actual, encoding="utf-8")
            return
        self.assertTrue(
            archivo.exists(), f"falta el snapshot {archivo.name}: generalo con ACTUALIZAR_SNAPSHOTS_DETALLE=1"
        )
        self.assertEqual(
            actual,
            archivo.read_text(encoding="utf-8"),
            f"el HTML del escenario «{nombre}» cambió. Si el cambio es a propósito, "
            "regenerá los snapshots y revisá el diff en el PR.",
        )

    def test_render_con_adjuntos(self):
        self._comparar("con_adjuntos", "Resultado SIIS", "Envío a SIIS", "Aviso al ciudadano", "Traza de cambios")

    def test_render_sin_adjuntos(self):
        self._comparar("sin_adjuntos", "Identidad", "Datos de contacto")

    def test_render_rechazado(self):
        self._comparar("rechazado", "Motivo de rechazo", "Aviso al ciudadano")

    def test_render_publico(self):
        self._comparar("publico", "Identidad")

    def test_render_con_observaciones_de_carga(self):
        self._comparar("con_observaciones_de_carga", "Observaciones de la carga")

    def test_render_en_espera(self):
        self._comparar("en_espera", "lista de espera")
