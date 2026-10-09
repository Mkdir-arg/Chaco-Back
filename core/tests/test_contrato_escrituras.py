"""Las escrituras críticas siguen siendo atómicas (RED-35).

Hay 39 `@transaction.atomic` en los `services/` del repo y **ninguno** estaba
afirmado por un test. El Cambio 58 registra que el decorador de
`resolver_ciudadano_offline` ya se perdió una vez, al extraer `_completar_contacto`
a su propia función: mover una escritura de módulo sin llevarse el decorador no
rompe ningún test, y en producción deja un ciudadano creado con el formulario sin
tocar —un legajo duplicado que nadie pidió—.

**La prueba es conductual, no introspectiva.** Afirmar la atomicidad con
`getattr(fn, "_atomic", False)` no sirve: `transaction.atomic` usa `@wraps` y no
deja ese atributo, así que la aserción da siempre `False`; y buscar la palabra
«atomic» en el fuente da verde con un comentario. Lo que se hace acá es hacer
fallar un paso intermedio y mirar que **no quedó nada escrito**.

Las otras cuatro escrituras que nombra la ficha entran en la **Ola 3** y son las
clases de abajo. La de `cupo` la ficha la llamaba `aprobar_formulario`: ese
nombre no existe en el código, la función es `cupo.aprobar_o_poner_en_espera`
(desvío code-first, el único de esta tanda).

Una de ellas no estaba entera, y el test que la nombra es el que lo muestra:
`padron.quitar_padron_propio` borraba y escribía `padron_archivo` sin tomar el
candado que `cargar_padron` sí toma (BEC-15), así que las dos operaciones se
intercalaban sobre el mismo relevamiento.

La otra era `admisiones.trasladar_admision`, que guardaba el F-00 del destino
**antes** de cerrar el origen y dejaba el adjunto en `media/` sin fila que lo
nombre cuando el cierre fallaba. El traslado se fue con `Admision` (MVP v2,
release A) y con él su clase de tests; lo que sigue vivo es el mecanismo que lo
arreglaba, `core.archivos.archivos_atomicos`, hoy sobre el alta y la edición de
una campaña de correo. Para que no quede sin dueño, la conducta se afirma igual:
`CampanaAtomicaTests`, al final de este módulo.

`PadronBajoCandadoTests` es la continuación de ese candado: tomarlo no alcanza si
lo que se decide adentro se leyó afuera.

El gemelo contra el motor de producción —donde el rollback es un `ROLLBACK` de
verdad y no un savepoint de SQLite— está en
`core/tests/test_motor_real.py::EscriturasAtomicasMotorRealTests`.
"""

from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from legajos.models import Ciudadano
from portal.tests.test_inscripcion_envio import _BasePaso2Test, _identificacion
from programas.models import (
    Convocatoria,
    Formulario,
    ListaEspera,
    PadronHabilitado,
    Relevamiento,
    Segmento,
    TracaFormulario,
)
from programas.services.becas import resolver_ciudadano_offline
from programas.services.cupo import aprobar_o_poner_en_espera
from programas.services.inscripcion_publica import crear_formulario_publico
from programas.services.padron import cargar_padron, quitar_padron_propio
from programas.tests.test_becas_revision import _BaseAprobacionTest

#: El caso llega por sync offline: sin legajo y con la identidad en el JSON.
DNI = "41222333"
IDENTIFICACION = {"dni": DNI, "nombre": "Lucía", "apellido": "Paz", "sexo": "F"}


class EscriturasAtomicasTests(TestCase):
    def setUp(self):
        self.segmento = Segmento.objects.create(nombre="Seg atomic", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv atomic",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            territorial=User.objects.create_user("terri_atomic", password="x"),
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        self.formulario = Formulario.objects.create(
            relevamiento=self.relevamiento,
            celular="3624555666",
            email_contacto="lucia@correo.com",
            datos_identificacion=dict(IDENTIFICACION),
        )

    def test_resolver_ciudadano_offline_no_deja_nada_a_medias(self):
        """Si falla un paso posterior al alta del legajo, el legajo no queda.

        `_completar_contacto` corre **después** del `get_or_create` del
        `Ciudadano` y antes de guardar el formulario: hacerlo explotar deja el
        caso justo en el medio. Sin `@transaction.atomic` sobre
        `resolver_ciudadano_offline` el ciudadano queda creado y el formulario
        sigue apuntando a su `datos_identificacion`: la próxima sincronización
        vuelve a entrar por el mismo camino y el duplicado nunca se ve.
        """
        with patch(
            "programas.services.becas._completar_contacto",
            side_effect=RuntimeError("se cayó el paso siguiente"),
        ):
            with self.assertRaises(RuntimeError):
                resolver_ciudadano_offline(self.formulario)

        self.assertFalse(
            Ciudadano.objects.filter(dni=DNI).exists(),
            "Quedó un legajo creado por una escritura que falló: `resolver_ciudadano_offline` "
            "perdió su `@transaction.atomic` (ya pasó una vez, Cambio 58).",
        )
        self.formulario.refresh_from_db()
        self.assertIsNone(self.formulario.ciudadano_id)
        self.assertEqual(self.formulario.datos_identificacion, IDENTIFICACION)

    def test_resolver_ciudadano_offline_sin_fallas_si_escribe(self):
        """Control: sin la falla inyectada la escritura sí ocurre, entera.

        Sin este par, cualquier cambio que dejara la función sin hacer nada
        pondría el test de arriba en verde por el motivo equivocado.
        """
        ciudadano = resolver_ciudadano_offline(self.formulario)

        self.assertIsNotNone(ciudadano)
        self.assertEqual(ciudadano.dni, DNI)
        self.formulario.refresh_from_db()
        self.assertEqual(self.formulario.ciudadano_id, ciudadano.pk)
        self.assertIsNone(self.formulario.datos_identificacion)
        self.assertEqual(ciudadano.telefono, "3624555666")


class AprobacionAtomicaTests(_BaseAprobacionTest):
    """`cupo.aprobar_o_poner_en_espera`: el estado y su traza van juntos o no van.

    La traza es lo último que escribe la aprobación, y es la única prueba de
    quién resolvió el caso y cuándo. Sin la transacción, un error ahí —una traza
    con un usuario borrado, un `JSONField` que no serializa— deja el caso
    APROBADO **sin registro de la aprobación**: consume cupo, el beneficiario
    sale en el reporte y no hay forma de saber quién lo aprobó.

    Se hace fallar `registrar_traza`, que es el paso siguiente al cambio de
    estado, igual que `_completar_contacto` arriba.
    """

    def _aprobar_con_la_traza_rota(self):
        with patch("programas.services.cupo.registrar_traza", side_effect=RuntimeError("se cayó la traza")):
            with self.assertRaises(RuntimeError):
                aprobar_o_poner_en_espera(self.form_a, self.coord_a)

    def test_aprobar_no_deja_el_caso_aprobado_sin_su_traza(self):
        self._aprobar_con_la_traza_rota()

        self.form_a.refresh_from_db()
        self.assertEqual(
            self.form_a.estado,
            Formulario.Estado.ENVIADO,
            "El caso quedó APROBADO por una escritura que falló: `aprobar_o_poner_en_espera` "
            "perdió su `@transaction.atomic` y el cupo se consumió sin registro.",
        )
        self.assertFalse(TracaFormulario.objects.filter(formulario=self.form_a, campo="estado").exists())

    def test_sin_cupo_tampoco_queda_la_fila_de_espera(self):
        """La otra rama: sin cupo deriva a la lista, que es otra escritura.

        Esta la sostienen las **dos** transacciones (la de
        `agregar_a_lista_espera` y la de afuera); la de arriba es la que depende
        solo del decorador de `aprobar_o_poner_en_espera`.
        """
        self.seg_a.cupo_maximo = 0
        self.seg_a.save(update_fields=["cupo_maximo"])

        self._aprobar_con_la_traza_rota()

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.ENVIADO)
        self.assertFalse(ListaEspera.objects.filter(formulario=self.form_a).exists())

    def test_sin_la_falla_inyectada_la_aprobacion_ocurre_entera(self):
        """Control: si la función dejara de escribir, los de arriba darían verde."""
        self.assertEqual(aprobar_o_poner_en_espera(self.form_a, self.coord_a), "aprobado")

        self.form_a.refresh_from_db()
        self.assertEqual(self.form_a.estado, Formulario.Estado.APROBADO)
        self.assertEqual(TracaFormulario.objects.filter(formulario=self.form_a, campo="estado").count(), 1)


class InscripcionPublicaAtomicaTests(_BasePaso2Test):
    """`inscripcion_publica.crear_formulario_publico`, que tiene **dos** mitades.

    Adentro del candado del relevamiento va lo que decide si el caso entra
    (idempotencia, cupo, duplicado, padrón) y el insert; afuera, los adjuntos y
    el legajo, a propósito, porque cada milisegundo adentro lo pagan en cola los
    que vienen atrás y a los 10 s el `read_timeout` les devuelve un 500
    (Cambio 91).

    Las dos mitades tienen su contrato y acá se prueban las dos: adentro, que un
    paso que falle no deje medio caso escrito; afuera, que lo que no llegó a
    completarse lo termine el reintento de la persona —que es lo que la convierte
    en una decisión defendible y no en una escritura a medias—.
    """

    def _form_valido(self, identificacion):
        form = self._form(identificacion=identificacion)
        self.assertTrue(form.is_valid(), form.errors)
        return form

    def test_una_falla_despues_del_insert_no_deja_el_caso_escrito(self):
        """Si mañana se agrega un paso después del insert, tiene que volver atrás."""
        from programas.services import inscripcion_publica

        ident = _identificacion()
        real = inscripcion_publica._insertar_formulario

        def insertar_y_fallar(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError("se cayó el paso siguiente al insert")

        with patch.object(inscripcion_publica, "_insertar_formulario", insertar_y_fallar):
            with self.assertRaises(RuntimeError):
                crear_formulario_publico(
                    self.relevamiento,
                    identificacion=ident,
                    form=self._form_valido(ident),
                    client_uuid=ident["client_uuid"],
                )

        self.assertEqual(
            self.relevamiento.formularios.count(),
            0,
            "Quedó un caso de una inscripción que falló: el `with transaction.atomic()` "
            "de `crear_formulario_publico` dejó de envolver al insert.",
        )

    def test_si_falla_el_legajo_el_caso_queda_y_el_reintento_lo_completa(self):
        """Lo de afuera del candado **no** vuelve atrás, y está bien que así sea.

        La persona ya vio su comprobante: borrarle el caso porque falló la
        resolución del legajo sería peor. El contrato que lo sostiene es que el
        reintento con el mismo `client_uuid` completa lo que faltó.
        """
        ident = _identificacion()
        with patch(
            "programas.services.inscripcion_publica.resolver_ciudadano_offline",
            side_effect=RuntimeError("se cayó la resolución del legajo"),
        ):
            with self.assertRaises(RuntimeError):
                crear_formulario_publico(
                    self.relevamiento,
                    identificacion=ident,
                    form=self._form_valido(ident),
                    client_uuid=ident["client_uuid"],
                )

        formulario = self.relevamiento.formularios.get()
        self.assertIsNone(formulario.ciudadano_id)
        self.assertFalse(Ciudadano.objects.filter(dni=ident["dni"]).exists())

        reintento, creado = crear_formulario_publico(
            self.relevamiento,
            identificacion=ident,
            form=self._form_valido(ident),
            client_uuid=ident["client_uuid"],
        )

        self.assertFalse(creado)
        self.assertEqual(reintento.pk, formulario.pk)
        self.assertEqual(reintento.ciudadano.dni, ident["dni"])
        self.assertEqual(self.relevamiento.formularios.count(), 1)


class _BasePadronConExcel(TestCase):
    """Un relevamiento público con padrón propio y su Excel ya guardado."""

    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ajustes = override_settings(MEDIA_ROOT=temporal.name)
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.segmento = Segmento.objects.create(nombre="Seg padrón atómico", cupo_maximo=10)
        self.convocatoria = Convocatoria.objects.create(
            nombre="Conv padrón atómico",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=self.convocatoria,
            tipo=Relevamiento.Tipo.PUBLICO,
            fecha_asignada=date(2026, 6, 1),
            fecha_hasta=date(2026, 6, 30),
        )
        with self.captureOnCommitCallbacks(execute=True):
            cargar_padron(
                self.relevamiento,
                SimpleUploadedFile("propio.xlsx", b"no importa el contenido"),
                [{"dni": "30111222", "sexo": "F"}],
            )
        self.relevamiento.refresh_from_db()
        self.excel = self.relevamiento.padron_archivo.name
        self.storage = self.relevamiento.padron_archivo.storage

    def _carga_concurrente(self):
        """Otra carga sobre el mismo relevamiento, por una referencia distinta.

        Es lo que pasa de verdad mientras la operación de este test espera el
        candado: el Excel de la base pasa a ser otro y el que tiene en memoria el
        objeto que llegó por parámetro ya no existe en el storage.
        """
        otra = Relevamiento.objects.get(pk=self.relevamiento.pk)
        with self.captureOnCommitCallbacks(execute=True):
            cargar_padron(
                otra,
                SimpleUploadedFile("propio.xlsx", b"la carga que entro en el medio"),
                [{"dni": "30111222", "sexo": "F"}],
            )
        otra.refresh_from_db()
        vigente = otra.padron_archivo.name
        self.assertNotEqual(vigente, self.excel)
        self.assertFalse(self.storage.exists(self.excel))
        return vigente


class QuitarPadronAtomicoTests(_BasePadronConExcel):
    """`padron.quitar_padron_propio`: las filas y el Excel se van juntos.

    Un padrón propio vacío no es un estado neutro: `padron_de` cae al de la
    convocatoria y, si la convocatoria no tiene, el link queda **abierto para
    cualquier DNI** (RN-P14). Así que borrar las filas y no llegar a sacar el
    Excel —o al revés— es exactamente el estado que no puede quedar.
    """

    def test_si_falla_al_guardar_el_relevamiento_las_filas_siguen_estando(self):
        with self.captureOnCommitCallbacks(execute=True):
            with patch.object(Relevamiento, "save", side_effect=RuntimeError("se cayó el guardado")):
                with self.assertRaises(RuntimeError):
                    quitar_padron_propio(self.relevamiento)

        self.relevamiento.refresh_from_db()
        self.assertEqual(
            PadronHabilitado.objects.filter(relevamiento=self.relevamiento).count(),
            1,
            "El padrón propio quedó vacío con el Excel puesto: `quitar_padron_propio` perdió "
            "su `@transaction.atomic` y el link pasó a admitir cualquier DNI (RN-P14).",
        )
        self.assertEqual(self.relevamiento.padron_archivo.name, self.excel)
        self.assertTrue(self.storage.exists(self.excel), "el Excel se borró en una operación que falló")

    def test_sin_la_falla_inyectada_se_van_las_filas_y_el_excel(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(quitar_padron_propio(self.relevamiento), 1)

        self.relevamiento.refresh_from_db()
        self.assertEqual(PadronHabilitado.objects.filter(relevamiento=self.relevamiento).count(), 0)
        self.assertFalse(self.relevamiento.padron_archivo)
        self.assertFalse(self.storage.exists(self.excel))


class PadronBajoCandadoTests(_BasePadronConExcel):
    """Lo que se decide adentro del candado se lee adentro del candado.

    Las dos operaciones del padrón reciben un objeto que el llamador leyó antes,
    y recién después esperan el `select_for_update`. Si en esa espera entró otra
    carga, el `padron_archivo` en memoria es una foto vieja: su archivo ya lo
    borró la otra carga y el que está en `media/` es el nuevo. Programar el
    borrado del nombre viejo no rompe nada visible —borrar lo que no está es un
    no-op— pero deja el Excel vigente colgado, con el padrón de miles de personas
    y sin ninguna fila que lo nombre. Por eso el valor se relee bajo el candado.
    """

    def test_quitar_borra_el_excel_vigente_y_no_el_de_la_foto_vieja(self):
        vigente = self._carga_concurrente()

        with self.captureOnCommitCallbacks(execute=True):
            quitar_padron_propio(self.relevamiento)

        self.relevamiento.refresh_from_db()
        self.assertFalse(self.relevamiento.padron_archivo)
        self.assertFalse(
            self.storage.exists(vigente),
            "`quitar_padron_propio` borró el Excel de la foto vieja: el vigente quedó en media/ "
            "sin ninguna fila que lo nombre. El `padron_archivo` se relee bajo el candado.",
        )

    def test_cargar_borra_el_excel_vigente_y_no_el_de_la_foto_vieja(self):
        vigente = self._carga_concurrente()

        with self.captureOnCommitCallbacks(execute=True):
            cargar_padron(
                self.relevamiento,
                SimpleUploadedFile("propio.xlsx", b"la carga que llega despues"),
                [{"dni": "30111222", "sexo": "F"}],
            )

        self.relevamiento.refresh_from_db()
        self.assertTrue(self.storage.exists(self.relevamiento.padron_archivo.name))
        self.assertFalse(
            self.storage.exists(vigente),
            "`cargar_padron` borró el Excel de la foto vieja: el que reemplazó quedó en media/ "
            "sin ninguna fila que lo nombre. El `padron_archivo` se relee bajo el candado.",
        )


class CampanaAtomicaTests(TestCase):
    """RED-35 sobre la escritura con archivos que quedó viva: la campaña de correo.

    El mecanismo —`core.archivos.archivos_atomicos`— lo descubrió el traslado de una
    admisión, que guardaba el F-00 del destino antes de cerrar el origen y dejaba el
    adjunto en `media/` cuando el cierre fallaba. El traslado se fue con `Admision`
    (MVP v2, release A) y con él su test; el decorador sigue puesto en `crear_campana`
    y `editar_campana`, así que la conducta se afirma acá y no se queda sin dueño.
    """

    def setUp(self):
        temporal = TemporaryDirectory()
        self.addCleanup(temporal.cleanup)
        ajustes = override_settings(MEDIA_ROOT=temporal.name)
        ajustes.enable()
        self.addCleanup(ajustes.disable)
        self.media = temporal.name

    def _archivos_en_media(self):
        from pathlib import Path

        return [str(ruta) for ruta in Path(self.media).rglob("*") if ruta.is_file()]

    def test_una_falla_despues_de_escribir_los_archivos_no_deja_ninguno(self):
        from notificaciones.models import Campana
        from notificaciones.tests.utils import crear_campana

        with patch(
            "notificaciones.services.campanas._guardar_lista",
            side_effect=RuntimeError("la lista no se pudo guardar"),
        ):
            with self.assertRaises(RuntimeError):
                crear_campana(emails=["a@ejemplo.com"])

        self.assertFalse(Campana.objects.exists())
        self.assertEqual(
            self._archivos_en_media(),
            [],
            "la campaña no quedó escrita y su Excel y su HTML sí: `media/` no tiene transacción "
            "y por eso la escritura va con `@archivos_atomicos`.",
        )

    def test_sin_la_falla_inyectada_la_campana_guarda_sus_dos_archivos(self):
        """Control: sin este par, borrar la escritura dejaría el otro test verde."""
        from notificaciones.models import Campana
        from notificaciones.tests.utils import crear_campana

        campana = crear_campana(emails=["a@ejemplo.com"])

        self.assertTrue(Campana.objects.filter(pk=campana.pk).exists())
        self.assertEqual(len(self._archivos_en_media()), 2)
