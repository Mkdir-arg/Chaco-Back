"""Contrato del JSON de ``/api/becas/`` que lee la app de campo (RED-11).

La app de campo (`Chaco-mobile`) está en producción y es **otro repo**: lo que
acá se renombra o se saca, allá no da error —el teléfono muestra el dato vacío—.
Estos tests fijan el **conjunto exacto** de claves de cada respuesta.

**Agregar una clave es seguro; renombrarla o sacarla es un release coordinado de
Chaco-mobile.** Si un cambio de serializer pone uno de estos tests en rojo, lo
que hay que revisar es el cambio, no la constante.

Dónde las lee la app:

- `src/services/relevamientoService.js` — `mapDjangoRelevamiento` (listado) y
  `mapDjangoRelevamientoDetail` (detalle, con `definicion_formulario`).
- el `id` del caso creado, para marcar el envío como sincronizado.

La forma de **cada campo** de ``definicion_formulario`` (claves, prefijos
``pg-``/``rn-``, enums) es la ficha RED-12 y tiene su propio test.
"""

from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from programas.models import (
    Formulario,
    PreguntaGlobal,
    Relevamiento,
    RequisitoNativo,
    Subsegmento,
    TipoCampo,
)
from programas.tests.test_becas_api import _BaseApiTest

CLAVES_RELEVAMIENTO_LIST = [
    "id",
    "numero",
    "nombre",
    "zona",
    "fecha_asignada",
    "fecha_hasta",
    "estado",
    "segmento",
    "localidad",
    "convocatoria_nombre",
    "fecha_finalizado",
    "formularios_count",
    "cupo_maximo",
    "cupo_disponible",
    "cupo_completo",
    "pausado",
    "pausa_motivo",
]

CLAVES_RELEVAMIENTO_DETAIL = [*CLAVES_RELEVAMIENTO_LIST, "definicion_formulario"]

CLAVES_DEFINICION = [
    "requiere_gps",
    "canal",
    "version",
    "items",
    "globales",
    "requisitos",
]

CLAVES_FORMULARIO = [
    "id",
    "numero",
    "client_uuid",
    "capturado_en",
    "relevamiento",
    "estado",
    "motivo_rechazo",
    "validado_renaper",
    "ciudadano",
    "ciudadano_dni",
    "ciudadano_nombre",
    "ciudadano_apellido",
    "datos_identificacion",
    "celular",
    "email_contacto",
    "apoderado_nombre",
    "apoderado_apellido",
    "apoderado_dni",
    "apoderado_genero",
    "apoderado_fecha_nacimiento",
    "apoderado_ciudadano",
    "gps_lat",
    "gps_lng",
    "data",
    "creado",
    "modificado",
]

CLAVES_ADJUNTO = ["id", "formulario", "pregunta_global", "requisito_nativo", "archivo", "creado"]

# La paginación de DRF: la app recorre `results` y usa `next` para traer el
# resto. Cambiar la clase de paginación le rompe la sincronización.
CLAVES_PAGINACION = ["count", "next", "previous", "results"]


class ContratoAppDeCampoTests(_BaseApiTest):
    def setUp(self):
        super().setUp()
        self.localidad = Subsegmento.objects.create(segmento=self.seg, nombre="Localidad Norte", cupo_maximo=50)
        self.conv.subsegmento = self.localidad
        self.conv.save(update_fields=["subsegmento", "modificado"])
        PreguntaGlobal.objects.create(texto="Tenencia", tipo=TipoCampo.STRING, activo=True, orden=1)
        RequisitoNativo.objects.create(texto="Actividad", tipo=TipoCampo.STRING, segmento=self.seg, orden=1)
        self.autenticar(self.terri)

    def _relevamiento_del_listado(self):
        resp = self.client.get(reverse("becas_api:relevamiento-list"))
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_lista_de_relevamientos_tiene_exactamente_estas_claves(self):
        cuerpo = self._relevamiento_del_listado()

        self.assertEqual(sorted(cuerpo), sorted(CLAVES_PAGINACION))
        self.assertEqual(sorted(cuerpo["results"][0]), sorted(CLAVES_RELEVAMIENTO_LIST))

    def test_detalle_agrega_definicion_formulario(self):
        resp = self.client.get(reverse("becas_api:relevamiento-detail", args=[self.rel.pk]))

        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.json()
        self.assertEqual(sorted(cuerpo), sorted(CLAVES_RELEVAMIENTO_DETAIL))
        self.assertEqual(sorted(cuerpo["definicion_formulario"]), sorted(CLAVES_DEFINICION))

    def test_tipos_del_contrato(self):
        """Los tipos que la app asume sin chequear: un `int` que pasa a `str`
        le rompe el contador y un `bool` que pasa a `str` es siempre verdadero.
        """
        detalle = self.client.get(reverse("becas_api:relevamiento-detail", args=[self.rel.pk])).json()

        self.assertIsInstance(detalle["id"], int)
        self.assertIsInstance(detalle["formularios_count"], int)
        self.assertIsInstance(detalle["cupo_maximo"], int)
        self.assertIsInstance(detalle["cupo_disponible"], int)
        self.assertIsInstance(detalle["cupo_completo"], bool)
        self.assertIsInstance(detalle["pausado"], bool)
        self.assertIsInstance(detalle["pausa_motivo"], str)
        self.assertIsInstance(detalle["estado"], str)
        self.assertIsInstance(detalle["nombre"], str)
        # El nombre de la convocatoria y la localidad llegan por la cadena
        # convocatoria → segmento/subsegmento: son strings, nunca ids.
        self.assertEqual(detalle["convocatoria_nombre"], self.conv.nombre)
        self.assertEqual(detalle["segmento"], self.seg.nombre)
        self.assertEqual(detalle["localidad"], self.localidad.nombre)

        definicion = detalle["definicion_formulario"]
        self.assertIsInstance(definicion, dict)
        self.assertIsInstance(definicion["requiere_gps"], bool)
        self.assertIsInstance(definicion["canal"], str)
        self.assertIsInstance(definicion["version"], int)
        for clave in ("items", "globales", "requisitos"):
            with self.subTest(clave=clave):
                self.assertIsInstance(definicion[clave], list)

    def test_el_contador_de_personas_cargadas_sale_anotado_y_cuenta(self):
        """`formularios_count` y `cupo_*` no los afirma ningún otro test: son lo
        que la app muestra como «cargadas / cupo» en cada tarjeta."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.cupo_maximo = 2
        self.rel.save(update_fields=["estado", "cupo_maximo", "modificado"])
        self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez"},
            },
            format="json",
        )

        propio = next(r for r in self._relevamiento_del_listado()["results"] if r["id"] == self.rel.pk)

        self.assertEqual(propio["formularios_count"], 1)
        self.assertEqual(propio["cupo_maximo"], 2)
        self.assertEqual(propio["cupo_disponible"], 1)
        self.assertFalse(propio["cupo_completo"])

    def test_formulario_creado_devuelve_id(self):
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {
                    "dni": "40400400",
                    "nombre": "Juan",
                    "apellido": "Perez",
                    "fecha_nacimiento": date(1990, 1, 2).isoformat(),
                },
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        cuerpo = resp.json()
        self.assertEqual(sorted(cuerpo), sorted(CLAVES_FORMULARIO))
        # Con esto la app marca el envío como sincronizado: sin `id` reintenta
        # para siempre.
        self.assertIsInstance(cuerpo["id"], int)
        self.assertEqual(cuerpo["relevamiento"], self.rel.pk)

    def test_adjunto_subido_y_listado_tienen_las_mismas_claves(self):
        """La app sube la foto y después lee `GET …/adjuntos/` para no
        reenviarla: las dos respuestas tienen que traer la misma forma."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        formulario = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")
        pregunta = PreguntaGlobal.objects.create(texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, orden=900)
        url = reverse("becas_api:formulario-adjuntos", args=[formulario.pk])

        alta = self.client.post(
            url,
            {"pregunta_global": pregunta.pk, "archivo": SimpleUploadedFile("dni.jpg", b"datos")},
            format="multipart",
        )
        listado = self.client.get(url)

        self.assertEqual(alta.status_code, 201, alta.data)
        self.assertEqual(sorted(alta.json()), sorted(CLAVES_ADJUNTO))
        self.assertEqual(listado.status_code, 200)
        self.assertEqual(sorted(listado.json()[0]), sorted(CLAVES_ADJUNTO))

    def test_el_listado_de_casos_tiene_las_mismas_claves(self):
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez"},
            },
            format="json",
        )

        resp = self.client.get(reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]))

        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.json()
        self.assertEqual(sorted(cuerpo), sorted(CLAVES_PAGINACION))
        self.assertEqual(sorted(cuerpo["results"][0]), sorted(CLAVES_FORMULARIO))
