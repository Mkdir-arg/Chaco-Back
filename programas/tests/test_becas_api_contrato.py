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

from datetime import date, timedelta

from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

from programas.management.commands.seed_becas import ROL_COORDINADOR
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
    "sincronizado_tarde",
    "version_capturada",
    "data",
    "creado",
    "modificado",
]

# G1-03: el **listado** de casos de un relevamiento sirve lo mismo menos `data`,
# que es el JSON de respuestas del contrato anterior (~7 KB por caso) y de esta
# lista la app no lo lee. `datos_identificacion` se queda: es de donde salen el
# nombre y el DNI mientras el caso todavía no tiene legajo, que es el estado
# normal de una carga offline recién sincronizada (`RelevamientoDetailScreen.js`,
# la lista de personas, y `dniYaRelevado` en `relevamientoService.js`).
CLAVES_FORMULARIO_LISTADO = [clave for clave in CLAVES_FORMULARIO if clave != "data"]

CLAVES_ADJUNTO = ["id", "formulario", "pregunta_global", "requisito_nativo", "archivo", "creado"]

#: El sobre que arma `PageNumberPagination`. Acá no es un contrato: es
#: exactamente lo que **no** tiene que salir de las dos listas de la API de campo
#: (G1-03). La app nunca siguió `next` —`relevamientoService.js` hace
#: `Array.isArray(payload?.results) ? payload.results : (Array.isArray(payload) ? payload : [])`
#: y se queda con la primera página—, así que la paginación global de DRF, que
#: corta en 10, le escondía los casos del 11 en adelante y los relevamientos
#: vigentes a partir del 11. Lo afirma `test_ninguna_de_las_dos_listas_pagina`.
CLAVES_DEL_SOBRE_DE_PAGINACION = {"count", "next", "previous", "results"}


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

        # G1-03: lista plana, no el sobre de paginación.
        self.assertIsInstance(cuerpo, list)
        self.assertEqual(sorted(cuerpo[0]), sorted(CLAVES_RELEVAMIENTO_LIST))

    def test_la_agenda_no_se_corta_en_la_decima_fila(self):
        """G1-03: con la paginación global de DRF (`PAGE_SIZE: 10`) el
        territorial con 12 relevamientos vigentes veía 10, y la caché offline
        del teléfono guardaba esos 10. La app no sigue `next`."""
        for dia in range(1, 12):
            Relevamiento.objects.create(
                convocatoria=self.conv,
                territorial=self.terri,
                fecha_asignada=timezone.localdate() + timedelta(days=dia),
                zona=f"Zona {dia}",
            )

        cuerpo = self._relevamiento_del_listado()

        self.assertEqual(len(cuerpo), 12)

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

        propio = next(r for r in self._relevamiento_del_listado() if r["id"] == self.rel.pk)

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
        self.assertIsInstance(cuerpo, list)
        self.assertEqual(sorted(cuerpo[0]), sorted(CLAVES_FORMULARIO_LISTADO))
        # Lo que la app lee de esta lista, nombrado: sin esto, «lo mismo menos
        # `data`» es una frase y no un contrato.
        caso = cuerpo[0]
        self.assertEqual(caso["ciudadano_dni"], "40400400")
        self.assertEqual(caso["estado"], "ENVIADO")
        self.assertIn("datos_identificacion", caso)

    def test_el_listado_de_casos_no_se_corta_en_la_decima_fila(self):
        """G1-03: con 15 casos cargados, `dniYaRelevado` solo veía los 10 más
        nuevos y la app dejaba cargar de nuevo a alguien ya relevado; el
        servidor marcaba el caso como `conflicto_duplicado` y alguien lo tenía
        que descartar a mano desde el backoffice."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.cupo_maximo = 50
        self.rel.save(update_fields=["estado", "cupo_maximo", "modificado"])
        for numero in range(15):
            Formulario.objects.create(
                relevamiento=self.rel,
                datos_identificacion={"dni": f"4040{numero:04d}"},
                celular="1",
                email_contacto="a@b.com",
            )

        resp = self.client.get(reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()), 15)

    def test_el_listado_de_casos_no_arrastra_el_json_de_respuestas(self):
        """G1-03: `data` pesa ~7 KB por caso. Sin paginación, servirlo por fila
        es lo que pone este listado contra el `read_timeout` de 10 s."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        Formulario.objects.create(
            relevamiento=self.rel,
            datos_identificacion={"dni": "40400400"},
            data={"globales": {"1": "x" * 5000}},
            celular="1",
            email_contacto="a@b.com",
        )

        resp = self.client.get(reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]))

        self.assertNotIn("data", resp.json()[0])
        # El detalle del caso, en cambio, sigue trayéndolo: es el contrato con
        # el que la app rehidrata un formulario.
        detalle = self.client.get(reverse("becas_api:formulario-detail", args=[self.rel.formularios.first().pk]))
        self.assertIn("data", detalle.json())
        self.assertEqual(detalle.json()["data"]["globales"]["1"], "x" * 5000)

    def test_la_raiz_de_la_api_responde_con_el_token_de_la_app(self):
        """R0-04: desde SEC-01 la raíz del router quedó con la autenticación por
        defecto y un `Authorization: Token` —el único que usa la app— recibía
        403 mientras todo lo que cuelga de ella respondía 200. La app en
        producción **no** la consulta (`Chaco-mobile@a66c2d3`: su
        `initializeWafSession` pide `/`, la raíz del sitio), así que esto no
        cambia nada para el teléfono; lo que arregla es la contradicción."""
        resp = self.client.get("/api/becas/")

        self.assertEqual(resp.status_code, 200)
        self.assertIn("relevamientos", resp.json())

    def test_ninguna_de_las_dos_listas_pagina(self):
        """G1-03, dicho como contrato y no como comentario: si alguien vuelve a
        poner `pagination_class`, la app se queda con las diez primeras filas y
        no lo nota —no hay error, solo faltan datos—."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        Formulario.objects.create(
            relevamiento=self.rel, datos_identificacion={"dni": "40400400"}, celular="1", email_contacto="a@b.com"
        )

        for nombre, url in (
            ("agenda", reverse("becas_api:relevamiento-list")),
            ("casos", reverse("becas_api:relevamiento-formularios", args=[self.rel.pk])),
        ):
            with self.subTest(lista=nombre):
                cuerpo = self.client.get(url).json()
                self.assertIsInstance(cuerpo, list)
                self.assertFalse(CLAVES_DEL_SOBRE_DE_PAGINACION & set(cuerpo[0]))

    def test_el_alta_sin_version_capturada_sigue_entrando(self):
        """G1-16: la clave es **opcional**. La app instalada
        (`Chaco-mobile@a66c2d3`) no la manda y no puede empezar a recibir 400."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez"},
            },
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertIsNone(resp.json()["version_capturada"])

    def test_el_adjunto_repetido_responde_201_y_no_duplica(self):
        """G1-07: la idempotencia **no** cambia el código de respuesta. La app
        clasifica la subida por el status; un 200 que hoy no espera sería un
        cambio de contrato que pide release de `Chaco-mobile`."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        pregunta = PreguntaGlobal.objects.create(texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, orden=900)
        formulario = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")
        url = reverse("becas_api:formulario-adjuntos", args=[formulario.pk])

        primera = self.client.post(
            url, {"pregunta_global": pregunta.pk, "archivo": SimpleUploadedFile("dni.jpg", b"una")}, format="multipart"
        )
        segunda = self.client.post(
            url, {"pregunta_global": pregunta.pk, "archivo": SimpleUploadedFile("dni.jpg", b"otra")}, format="multipart"
        )

        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(segunda.status_code, 201, segunda.data)
        self.assertEqual(sorted(segunda.json()), sorted(CLAVES_ADJUNTO))
        self.assertEqual(segunda.json()["id"], primera.json()["id"])
        self.assertEqual(len(self.client.get(url).json()), 1)

    def test_la_raiz_de_la_api_no_se_abre_a_quien_no_es_de_campo(self):
        self.client.credentials()
        self.assertIn(self.client.get("/api/becas/").status_code, (401, 403))

        coordinador = User.objects.create_user("coord-raiz", password="secret123")
        coordinador.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        token, _ = Token.objects.get_or_create(user=coordinador)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.assertEqual(self.client.get("/api/becas/").status_code, 403)
