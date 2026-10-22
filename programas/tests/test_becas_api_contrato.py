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
from unittest.mock import patch

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
    Segmento,
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
    "acepta_respuestas",
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
    "respuestas",
    "creado",
    "modificado",
]

# G1-03: el **listado** de casos de un relevamiento sirve lo mismo menos `data`,
# que es el JSON de respuestas del contrato anterior (~7 KB por caso) y de esta
# lista la app no lo lee. `datos_identificacion` se queda: es de donde salen el
# nombre y el DNI mientras el caso todavía no tiene legajo, que es el estado
# normal de una carga offline recién sincronizada (`RelevamientoDetailScreen.js`,
# la lista de personas, y `dniYaRelevado` en `relevamientoService.js`).
CLAVES_FORMULARIO_LISTADO = [clave for clave in CLAVES_FORMULARIO if clave not in {"data", "respuestas"}]

CLAVES_ADJUNTO = ["id", "formulario", "pregunta_global", "requisito_nativo", "clave", "archivo", "creado"]

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

    def test_el_adjunto_se_sube_con_el_id_de_la_lista_plana(self):
        """G1-07 contra lo que la app manda de verdad (`Chaco-mobile@a66c2d3`).

        `mapDjangoRelevamientoDetail` arma `campos_definicion` con las listas
        **planas** `globales`/`requisitos` —no con `items`— y
        `syncRemoteBecasFormulario` sube un archivo por campo `ARCHIVO`, en
        multipart, con `pregunta_global` o `requisito_nativo` = el `id` de esa
        lista según el `scope`. Si el control de pertenencia rechazara una de
        esas referencias, la cola de la app marca el envío `PARCIAL` y **corta**:
        los adjuntos que venían después tampoco se suben."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        pregunta = PreguntaGlobal.objects.create(texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, activo=True, orden=900)
        requisito = RequisitoNativo.objects.create(
            texto="Constancia", tipo=TipoCampo.ARCHIVO, segmento=self.seg, orden=901
        )
        alta = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            {
                "celular": "3624111222",
                "email_contacto": "x@y.com",
                "datos_identificacion": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez"},
            },
            format="json",
        )
        self.assertEqual(alta.status_code, 201, alta.data)
        definicion = self.client.get(reverse("becas_api:relevamiento-detail", args=[self.rel.pk])).json()[
            "definicion_formulario"
        ]
        url = reverse("becas_api:formulario-adjuntos", args=[alta.json()["id"]])
        subidas = [
            ("pregunta_global" if scope == "globales" else "requisito_nativo", campo["id"])
            for scope in ("globales", "requisitos")
            for campo in definicion[scope]
            if campo["tipo"] == "ARCHIVO"
        ]
        self.assertIn(("pregunta_global", pregunta.pk), subidas)
        self.assertIn(("requisito_nativo", requisito.pk), subidas)

        for relacion, ident in subidas:
            with self.subTest(relacion=relacion):
                # La app manda los campos del FormData como texto.
                resp = self.client.post(
                    url, {relacion: str(ident), "archivo": SimpleUploadedFile("foto.jpg", b"x")}, format="multipart"
                )
                self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(len(self.client.get(url).json()), len(subidas))

    def test_el_400_del_adjunto_trae_el_motivo_en_non_field_errors(self):
        """`buildResponseError` (`becasApi.js`) arma el mensaje con
        `detail || error || non_field_errors[0]`: el motivo tiene que estar en
        una de esas tres, como texto."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        pregunta = PreguntaGlobal.objects.create(texto="Foto del DNI", tipo=TipoCampo.ARCHIVO, orden=900)
        # La única referencia que todavía rebota: la de otro padrón. Un campo que
        # quedó viejo entre la captura y la sincronización entra y se observa, que
        # es lo que evita que la cola de subidas de la app corte ahí.
        ajeno = RequisitoNativo.objects.create(
            texto="Certificado de otro programa",
            tipo=TipoCampo.ARCHIVO,
            segmento=Segmento.objects.create(nombre="Otro seg", cupo_maximo=10),
            orden=901,
        )
        formulario = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")
        url = reverse("becas_api:formulario-adjuntos", args=[formulario.pk])

        for motivo, datos in (
            ("formato", {"pregunta_global": pregunta.pk, "archivo": SimpleUploadedFile("dni.exe", b"x")}),
            ("fuera del formulario", {"requisito_nativo": ajeno.pk, "archivo": SimpleUploadedFile("dni.jpg", b"x")}),
        ):
            with self.subTest(motivo=motivo):
                resp = self.client.post(url, datos, format="multipart")
                self.assertEqual(resp.status_code, 400)
                self.assertIsInstance(resp.json()["non_field_errors"][0], str)

    def test_el_400_del_alta_trae_el_motivo_en_non_field_errors(self):
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            {"celular": "1", "email_contacto": "x@y.com", "datos_identificacion": {"dni": "12"}},
            format="json",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertIsInstance(resp.json()["non_field_errors"][0], str)

    def test_la_persona_no_encontrada_es_un_404_con_error(self):
        """La app (`RelevamientoDetailScreen.js`, consulta de identidad) decide
        **solo por el status**: `e.status === 404` → «DNI no encontrado» y
        carga manual; cualquier otro error → aviso de validación fallida. El
        texto que deja a la vista sale de `error`. Da igual por qué no se la
        encontró (código 12 de Personas o un 404 del servicio): las dos tienen
        que llegar como este 404."""
        no_encontrada = {
            "validado": False,
            "fallecido": False,
            "no_encontrado": True,
            "error": "Base de Personas no encontró a la persona.",
            "datos": None,
            "origen": "manual",
            "diferencias": {},
        }
        with patch("programas.api.views.identificar", return_value=no_encontrada):
            resp = self.client.post(
                reverse("becas_api:personas-consultar"), {"dni": "40400400", "sexo": "F"}, format="json"
            )

        self.assertEqual(resp.status_code, 404)
        self.assertIs(resp.json()["success"], False)
        self.assertIsInstance(resp.json()["error"], str)
        self.assertTrue(resp.json()["error"])

    def test_la_raiz_de_la_api_no_se_abre_a_quien_no_es_de_campo(self):
        self.client.credentials()
        self.assertIn(self.client.get("/api/becas/").status_code, (401, 403))

        coordinador = User.objects.create_user("coord-raiz", password="secret123")
        coordinador.groups.add(Group.objects.get(name=ROL_COORDINADOR))
        token, _ = Token.objects.get_or_create(user=coordinador)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.assertEqual(self.client.get("/api/becas/").status_code, 403)

    # ── SEC-23 / SEC-24 (Cambio 184) ────────────────────────────────────────
    # Lo que el teléfono instalado manda de verdad en el alta, fijado como
    # contrato: `syncRemoteBecasFormulario` arma el cuerpo con `validado_renaper`
    # y `client_uuid` adentro (`relevamientoService.js:941`). `validado_renaper`
    # pasó a ser de **solo lectura**; `client_uuid` sigue siendo escribible
    # porque es la idempotencia de la cola offline. Un campo de solo lectura que
    # llegara a dar 400 deja la operación `FAILED_PERMANENT` y pierde la carga.

    def _cuerpo_de_la_app(self, **extra):
        cuerpo = {
            "celular": "3624111222",
            "email_contacto": "x@y.com",
            "apoderado_nombre": "",
            "apoderado_apellido": "",
            "apoderado_dni": "",
            "apoderado_genero": "",
            "apoderado_fecha_nacimiento": None,
            "gps_lat": None,
            "gps_lng": None,
            "validado_renaper": True,
            "client_uuid": "4f1c0b4e-9b2a-4c0d-8b4e-1a2b3c4d5e6f",
            "capturado_en": timezone.now().isoformat(),
            "datos_identificacion": {
                "dni": "40400400",
                "nombre": "Juan",
                "apellido": "Perez",
                "fecha_nacimiento": date(1990, 1, 2).isoformat(),
                "sexo": "M",
                "origen": "manual",
            },
            "data": {"globales": {}, "requisitos": {}},
        }
        cuerpo.update(extra)
        return cuerpo

    def test_el_alta_con_el_cuerpo_exacto_de_la_app_sigue_entrando(self):
        """El payload literal de `syncRemoteBecasFormulario`, clave por clave."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            self._cuerpo_de_la_app(),
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        cuerpo = resp.json()
        self.assertEqual(sorted(cuerpo), sorted(CLAVES_FORMULARIO))
        # El `client_uuid` que la app mandó vuelve: es con lo que deduplica.
        self.assertEqual(cuerpo["client_uuid"], "4f1c0b4e-9b2a-4c0d-8b4e-1a2b3c4d5e6f")

    def test_el_validado_renaper_del_telefono_se_ignora_sin_dar_400(self):
        """SEC-23: el cliente no acredita identidad, pero mandarla **no** es un
        error. El valor que vuelve es el que calculó el servidor."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

        resp = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[self.rel.pk]),
            self._cuerpo_de_la_app(),
            format="json",
        )

        self.assertEqual(resp.status_code, 201, resp.data)
        # Origen `manual` ⇒ sin validar, pese al `"validado_renaper": True` del
        # cuerpo.
        self.assertFalse(resp.json()["validado_renaper"])
        self.assertFalse(Formulario.objects.get(pk=resp.json()["id"]).validado_renaper)

    def test_el_alta_repetida_sigue_siendo_idempotente_por_client_uuid(self):
        """`client_uuid` **no** pasó a solo lectura: la cola offline reintenta y
        el segundo POST tiene que devolver el mismo caso, no uno nuevo."""
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])
        url = reverse("becas_api:relevamiento-formularios", args=[self.rel.pk])

        primera = self.client.post(url, self._cuerpo_de_la_app(), format="json")
        segunda = self.client.post(url, self._cuerpo_de_la_app(), format="json")

        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.assertEqual(segunda.json()["id"], primera.json()["id"])
        self.assertEqual(Formulario.objects.filter(relevamiento=self.rel).count(), 1)


# ── Robustez de la API de campo (K1–K8, 22-oct-2026) ─────────────────────────
#
# Las claves y los `code` de abajo son lo que la app **nueva** lee primero. Los
# `detail` siguen siendo los de siempre —la app instalada los reconoce por
# regex—, y por eso cada test los fija también.

CLAVES_LOGIN = ["token", "user_id", "username", "modulos", "app"]
CLAVES_ITEM_GRUPO = {"tipo", "clave", "titulo", "subtitulo", "condicion", "canal", "items"}
CLAVES_ITEM_TEXTO = {"tipo", "clave", "texto", "condicion"}
CLAVES_ITEM_CAMPO = {
    "tipo_item",
    "condicion",
    "id",
    "texto",
    "tipo",
    "opciones",
    "presentacion",
    "obligatorio",
    "orden",
    "alcance",
    "subsegmento_id",
    "canal",
    "origen",
    "vinculo",
    "grupo",
    "clave",
}
#: Opcional: solo viaja cuando el campo tiene destino en SIIS.
CLAVES_ITEM_CAMPO_OPCIONALES = {"destino_siis"}


class ContratoDeErroresYLoginTests(_BaseApiTest):
    def setUp(self):
        super().setUp()
        self.autenticar(self.terri)
        self.url_alta = reverse("becas_api:relevamiento-formularios", args=[self.rel.pk])

    def _cuerpo(self, **extra):
        cuerpo = {
            "client_uuid": "7d1c0b4e-9b2a-4c0d-8b4e-1a2b3c4d5e6f",
            "capturado_en": timezone.now().isoformat(),
            "celular": "3624111222",
            "datos_identificacion": {"dni": "40400400", "nombre": "Juan", "apellido": "Perez", "origen": "manual"},
            "data": {"globales": {}, "requisitos": {}},
        }
        cuerpo.update(extra)
        return cuerpo

    def _en_curso(self):
        self.rel.estado = Relevamiento.Estado.EN_CURSO
        self.rel.save(update_fields=["estado", "modificado"])

    def _pausar(self):
        self.conv.pausado = True
        self.conv.pausa_motivo = "Revisión de padrón"
        self.conv.save(update_fields=["pausado", "pausa_motivo"])

    def _login(self):
        return self.client.post(
            reverse("becas_api:token"), {"username": "terri", "password": "secret123"}, format="json"
        )

    # K7

    def test_el_login_trae_modulos_y_version_minima_sin_tocar_lo_de_siempre(self):
        resp = self._login()

        self.assertEqual(resp.status_code, 200)
        cuerpo = resp.json()
        self.assertEqual(sorted(cuerpo), sorted(CLAVES_LOGIN))
        self.assertEqual(cuerpo["username"], "terri")
        self.assertIsInstance(cuerpo["user_id"], int)
        self.assertEqual(cuerpo["modulos"], ["becas"])
        self.assertEqual(cuerpo["app"], {"version_minima": None})

    def test_la_version_minima_sale_de_la_configuracion(self):
        with self.settings(APP_CAMPO_VERSION_MINIMA="1.4.0"):
            resp = self._login()

        self.assertEqual(resp.json()["app"], {"version_minima": "1.4.0"})

    def test_modulos_sin_becas_campo_es_solo_dispositivos(self):
        with (
            patch("programas.api.views.puede", side_effect=lambda user, codigo, *a, **k: codigo != "becas.campo"),
            patch("programas.api.views.puede_en_programa_dispositivos", return_value=True),
        ):
            resp = self._login()

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["modulos"], ["dispositivos"])

    def test_modulos_con_las_dos_capacidades_van_ordenados(self):
        with patch("programas.api.views.puede_en_programa_dispositivos", return_value=True):
            resp = self._login()

        self.assertEqual(resp.json()["modulos"], ["becas", "dispositivos"])

    # K1

    def test_el_alta_pausada_es_409_pausado_con_o_sin_capturado_en(self):
        self._en_curso()
        self._pausar()
        sin_captura = {k: v for k, v in self._cuerpo().items() if k != "capturado_en"}

        for nombre, cuerpo in (("con capturado_en", self._cuerpo()), ("sin capturado_en", sin_captura)):
            with self.subTest(nombre):
                resp = self.client.post(self.url_alta, cuerpo, format="json")
                self.assertEqual(resp.status_code, 409, resp.content)
                self.assertEqual(
                    resp.json(),
                    {
                        "detail": "El relevamiento está pausado: Revisión de padrón",
                        "pausado": True,
                        "code": "PAUSADO",
                    },
                )
        self.assertEqual(Formulario.objects.count(), 0)

    def test_toda_respuesta_de_pausa_lleva_el_mismo_cuerpo(self):
        """iniciar, finalizar y reabrir: el mismo 409 con `pausado` y `code`."""
        self._pausar()
        esperado = {"detail": "El relevamiento está pausado: Revisión de padrón", "pausado": True, "code": "PAUSADO"}

        for accion in ("iniciar", "finalizar", "reabrir"):
            with self.subTest(accion):
                resp = self.client.post(reverse(f"becas_api:relevamiento-{accion}", args=[self.rel.pk]), {})
                self.assertEqual(resp.status_code, 409)
                self.assertEqual(resp.json(), esperado)

    def test_el_adjunto_pausado_lleva_code(self):
        self._en_curso()
        formulario = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")
        self._pausar()

        resp = self.client.post(
            reverse("becas_api:formulario-adjuntos", args=[formulario.pk]),
            {"clave": "pg-1", "archivo": SimpleUploadedFile("a.jpg", b"x")},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json()["code"], "PAUSADO")
        self.assertIs(resp.json()["pausado"], True)

    # K3

    def test_el_alta_en_un_relevamiento_que_no_esta_en_curso_lleva_code(self):
        resp = self.client.post(self.url_alta, self._cuerpo(), format="json")

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            resp.json(),
            {
                "detail": "Solo se pueden cargar personas en un relevamiento en curso.",
                "code": "RELEVAMIENTO_NO_EN_CURSO",
            },
        )

    def test_fuera_de_periodo_y_gracia_vencida_llevan_code(self):
        fin = timezone.now() - timedelta(hours=2)
        Relevamiento.objects.filter(pk=self.rel.pk).update(
            fecha_asignada=fin - timedelta(days=1), fecha_hasta=fin, estado=Relevamiento.Estado.EN_CURSO
        )

        # Captura posterior al período: fuera de período (400).
        posterior = self.client.post(
            self.url_alta, self._cuerpo(capturado_en=(fin + timedelta(minutes=30)).isoformat()), format="json"
        )
        self.assertEqual(posterior.status_code, 400)
        self.assertEqual(
            posterior.json(),
            {"detail": "La captura se realizó fuera del período asignado.", "code": "FUERA_DE_PERIODO"},
        )

        # Cerrado hace más de 24 h: gracia vencida (409).
        lejos = timezone.now() - timedelta(hours=30)
        Relevamiento.objects.filter(pk=self.rel.pk).update(
            fecha_asignada=lejos - timedelta(days=1), fecha_hasta=lejos, estado=Relevamiento.Estado.EN_REVISION
        )
        vencida = self.client.post(
            self.url_alta, self._cuerpo(capturado_en=(lejos - timedelta(hours=1)).isoformat()), format="json"
        )
        self.assertEqual(vencida.status_code, 409)
        cuerpo = vencida.json()
        self.assertEqual(cuerpo["code"], "GRACIA_VENCIDA")
        self.assertTrue(cuerpo["detail"].startswith("El relevamiento cerró hace más de 24 horas"))
        self.assertNotIn("pausado", cuerpo)

    def test_el_cupo_completo_conserva_su_cuerpo(self):
        self._en_curso()
        Relevamiento.objects.filter(pk=self.rel.pk).update(cupo_maximo=0)

        resp = self.client.post(self.url_alta, self._cuerpo(), format="json")

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(
            resp.json(),
            {
                "detail": "Se alcanzó el cupo del relevamiento. No se pueden cargar nuevas personas.",
                "code": "CUPO_RELEVAMIENTO_COMPLETO",
                "cupo_maximo": 0,
            },
        )

    def test_iniciar_finalizar_y_reabrir_llevan_code(self):
        fecha_invalida = (
            {"capturado_en": "no-es-una-fecha"},
            {"capturado_en": "La fecha de captura no es válida.", "code": "CAPTURADO_EN_INVALIDO"},
        )
        casos = [
            ("iniciar", *fecha_invalida),
            ("finalizar", *fecha_invalida),
            (
                "finalizar",
                {},
                {"detail": "El relevamiento no está en curso.", "code": "RELEVAMIENTO_NO_EN_CURSO"},
            ),
            (
                "reabrir",
                {},
                {"detail": "Solo se puede reabrir un relevamiento finalizado.", "code": "RELEVAMIENTO_NO_FINALIZADO"},
            ),
        ]
        for accion, cuerpo, esperado in casos:
            with self.subTest(accion=accion, cuerpo=cuerpo):
                resp = self.client.post(reverse(f"becas_api:relevamiento-{accion}", args=[self.rel.pk]), cuerpo)
                self.assertEqual(resp.status_code, 400, resp.content)
                self.assertEqual(resp.json(), esperado)

    def test_iniciar_un_relevamiento_ya_cerrado_dice_que_no_esta_asignado(self):
        Relevamiento.objects.filter(pk=self.rel.pk).update(estado=Relevamiento.Estado.FINALIZADO)

        resp = self.client.post(reverse("becas_api:relevamiento-iniciar", args=[self.rel.pk]), {})

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json(),
            {"detail": "Solo se puede iniciar un relevamiento asignado.", "code": "RELEVAMIENTO_NO_ASIGNADO"},
        )

    def test_fuera_de_periodo_en_iniciar_lleva_code(self):
        Relevamiento.objects.filter(pk=self.rel.pk).update(
            fecha_asignada=timezone.now() + timedelta(days=2), fecha_hasta=timezone.now() + timedelta(days=5)
        )

        resp = self.client.post(reverse("becas_api:relevamiento-iniciar", args=[self.rel.pk]), {})

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json(),
            {"detail": "Solo se puede relevar dentro del período asignado.", "code": "FUERA_DE_PERIODO"},
        )

    def test_la_validacion_del_alta_mantiene_su_forma_y_suma_code(self):
        self._en_curso()

        resp = self.client.post(self.url_alta, {"celular": "1", "datos_identificacion": {"dni": "12"}}, format="json")

        self.assertEqual(resp.status_code, 400)
        cuerpo = resp.json()
        self.assertEqual(cuerpo["code"], "VALIDACION")
        self.assertIn("datos_identificacion", cuerpo)
        self.assertIsInstance(cuerpo["non_field_errors"][0], str)

    def test_la_validacion_del_adjunto_suma_code(self):
        self._en_curso()
        formulario = Formulario.objects.create(relevamiento=self.rel, celular="111", email_contacto="a@b.com")

        resp = self.client.post(
            reverse("becas_api:formulario-adjuntos", args=[formulario.pk]),
            {"archivo": SimpleUploadedFile("a.jpg", b"x")},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["code"], "VALIDACION")
        self.assertIn("non_field_errors", resp.json())

    def test_el_dni_existe_sin_dni_suma_code(self):
        resp = self.client.get(reverse("becas_api:relevamiento-dni-existe", args=[self.rel.pk]))

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {"dni": "El DNI es requerido.", "code": "VALIDACION"})

    # K4

    def test_el_client_uuid_de_otro_relevamiento_es_409_client_uuid_en_uso(self):
        self._en_curso()
        otro = Relevamiento.objects.create(
            convocatoria=self.conv, territorial=self.terri, fecha_asignada=timezone.localdate(), zona="Otra zona"
        )
        otro.estado = Relevamiento.Estado.EN_CURSO
        otro.save(update_fields=["estado", "modificado"])
        primero = self.client.post(
            reverse("becas_api:relevamiento-formularios", args=[otro.pk]), self._cuerpo(), format="json"
        )
        self.assertEqual(primero.status_code, 201, primero.content)

        resp = self.client.post(self.url_alta, self._cuerpo(), format="json")

        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(
            resp.json(),
            {
                "detail": "El identificador de la carga ya está en uso. La app tiene que generar uno nuevo.",
                "code": "CLIENT_UUID_EN_USO",
            },
        )
        self.assertEqual(Formulario.objects.count(), 1)

    def test_el_mismo_client_uuid_con_otro_dni_en_el_mismo_relevamiento_es_409(self):
        self._en_curso()
        primero = self.client.post(self.url_alta, self._cuerpo(), format="json")
        self.assertEqual(primero.status_code, 201, primero.content)
        otra_persona = self._cuerpo(
            datos_identificacion={"dni": "30300300", "nombre": "Ana", "apellido": "Gomez", "origen": "manual"}
        )

        resp = self.client.post(self.url_alta, otra_persona, format="json")

        self.assertEqual(resp.status_code, 409, resp.content)
        self.assertEqual(resp.json()["code"], "CLIENT_UUID_EN_USO")
        self.assertEqual(Formulario.objects.count(), 1)

    def test_el_reintento_del_mismo_alta_sigue_siendo_200(self):
        self._en_curso()
        primero = self.client.post(self.url_alta, self._cuerpo(), format="json")

        reintento = self.client.post(self.url_alta, self._cuerpo(), format="json")

        self.assertEqual(primero.status_code, 201)
        self.assertEqual(reintento.status_code, 200)
        self.assertEqual(reintento.json()["id"], primero.json()["id"])

    # K8 · la forma de los ítems y los enums

    def _definicion_con_texto_y_campo_propio(self):
        from programas.models import CanalFormulario, ItemDiseno
        from programas.services.diseno import obtener_o_crear_diseno

        diseno, _ = obtener_o_crear_diseno(self.conv)
        grupo = diseno.items.filter(tipo=ItemDiseno.Tipo.GRUPO).order_by("orden").first()
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.TEXTO,
            clave="t-contrato",
            padre=grupo,
            orden=998,
            texto="Adjuntá el certificado.",
            canal=CanalFormulario.AMBOS,
        )
        ItemDiseno.objects.create(
            diseno=diseno,
            tipo=ItemDiseno.Tipo.CAMPO,
            clave="cp-contrato",
            padre=grupo,
            orden=999,
            canal=CanalFormulario.APP,
            propio={"texto": "Propio", "tipo": "STRING"},
        )
        resp = self.client.get(reverse("becas_api:relevamiento-detail", args=[self.rel.pk]))
        self.assertEqual(resp.status_code, 200)
        return resp.json()["definicion_formulario"]

    def test_las_claves_de_cada_tipo_de_item(self):
        definicion = self._definicion_con_texto_y_campo_propio()
        grupos = definicion["items"]
        self.assertTrue(grupos)
        textos, campos = [], []
        for grupo in grupos:
            self.assertEqual(set(grupo), CLAVES_ITEM_GRUPO, grupo["clave"])
            self.assertEqual(grupo["tipo"], "grupo")
            for hijo in grupo["items"]:
                (campos if hijo.get("tipo_item") == "campo" else textos).append(hijo)
        self.assertTrue(textos, "el diseño de prueba tiene un texto")
        self.assertTrue(campos, "el diseño de prueba tiene campos")
        for texto in textos:
            self.assertEqual(set(texto), CLAVES_ITEM_TEXTO, texto["clave"])
            self.assertEqual(texto["tipo"], "texto")
        for campo in campos:
            claves = set(campo)
            self.assertTrue(CLAVES_ITEM_CAMPO <= claves, (campo["clave"], CLAVES_ITEM_CAMPO - claves))
            self.assertTrue(claves <= CLAVES_ITEM_CAMPO | CLAVES_ITEM_CAMPO_OPCIONALES, (campo["clave"], claves))

    def test_los_enums_van_en_minuscula(self):
        definicion = self._definicion_con_texto_y_campo_propio()

        self.assertIn(definicion["canal"], {"app", "link"})
        campos = [hijo for g in definicion["items"] for hijo in g["items"] if hijo.get("tipo_item") == "campo"]
        for campo in campos:
            with self.subTest(clave=campo["clave"]):
                self.assertIn(campo["canal"], {"app", "link", "ambos"})
                self.assertIn(campo["origen"], {"pregunta", "legajo", "persona_vinculada"})
                self.assertIn(campo["alcance"], {"global", "programa", "segmento", "subsegmento", "propio"})
                self.assertIn(campo["tipo"], {"STRING", "INT", "SELECTOR", "SELECTOR_MULTIPLE", "DATE", "ARCHIVO"})
        for grupo in definicion["items"]:
            self.assertIn(grupo["canal"], {"app", "link", "ambos"})
        self.assertIn("legajo", {campo["origen"] for campo in campos})
