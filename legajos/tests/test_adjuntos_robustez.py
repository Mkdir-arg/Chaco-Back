"""LEG-04 y LEG-05 · Los adjuntos del legajo, cuando algo sale mal.

**LEG-04.** ``_serialize_adjunto`` leía ``archivo.archivo.size`` sin red: un blob que
ya no está en el storage —un restore sin ``media/``, un borrado a mano— tiraba ``OSError``,
la vista lo tragaba y devolvía **200 con la lista vacía** y, en el JSON del error, la
**ruta absoluta del servidor**. Un archivo perdido escondía todos los demás. Además la
consulta no traía el ``content_type``: una query por adjunto (N+1).

**LEG-05.** ``subir_archivos_para_objeto`` validaba y creaba en el mismo bucle: con
``dni.pdf`` válido y ``foto.heic`` inválido, el primero quedaba guardado y el usuario
veía «Formato no permitido». Ahora se valida todo primero y la creación va en una
transacción que, si falla, además borra del storage lo que alcanzó a escribir.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError
from django.db.models.sql.compiler import SQLInsertCompiler
from django.test import TestCase, override_settings
from django.urls import reverse

from legajos.models import Adjunto, Ciudadano
from legajos.selectors.contactos import build_ciudadano_archivos_payload
from legajos.services.contactos import ContactosFilesError, subir_archivos_para_objeto
from legajos.tests.test_adjuntos_rbac import usuario_con


class AdjuntoBlobFaltanteTests(TestCase):
    """LEG-04: un archivo que ya no está en disco no puede vaciar la lista."""

    def setUp(self):
        self.ciudadano = Ciudadano.objects.create(dni="24111222", nombre="Lucía", apellido="Vera")
        self.usuario = usuario_con("ciudadano.ver", username="leg04-ver")
        self.client.force_login(self.usuario)

    def test_archivos_ciudadano_con_blob_faltante_lista_el_resto(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            subir_archivos_para_objeto(
                self.ciudadano,
                [SimpleUploadedFile("a.pdf", b"uno"), SimpleUploadedFile("b.pdf", b"dos")],
            )
            huerfano = Adjunto.objects.order_by("id").first()
            Path(huerfano.archivo.path).unlink()

            respuesta = self.client.get(reverse("legajos:archivos_ciudadano", args=[self.ciudadano.pk]))

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()
        self.assertEqual(datos["count"], 2)
        self.assertNotIn("error", datos)

        por_id = {fila["id"]: fila for fila in datos["results"]}
        self.assertTrue(por_id[huerfano.id]["faltante"])
        self.assertIsNone(por_id[huerfano.id]["tamano"])
        otro = next(fila for fila in datos["results"] if fila["id"] != huerfano.id)
        self.assertFalse(otro["faltante"])
        self.assertEqual(otro["tamano"], 3)

    def test_error_inesperado_no_expone_detalle(self):
        """Un fallo imprevisto da 500 genérico, sin rutas ni mensajes internos."""
        ruta = "legajos.views.contactos_api.build_ciudadano_archivos_payload"
        with self.settings(DEBUG=False):
            with patch(ruta, side_effect=OSError("/srv/datanach/media/secreto.pdf")):
                respuesta = self.client.get(reverse("legajos:archivos_ciudadano", args=[self.ciudadano.pk]))

        self.assertEqual(respuesta.status_code, 500)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["results"], [])
        self.assertNotIn("/srv/datanach", str(cuerpo))
        self.assertNotIn("secreto.pdf", str(cuerpo))

    def test_archivos_ciudadano_sin_n_mas_1(self):
        """El ``content_type`` de cada adjunto viene en la misma consulta.

        Sin ``select_related`` cada fila preguntaba por su ``ContentType``, así que el
        costo crecía con la cantidad de adjuntos (zeal lo levanta en la suite). El
        contrato es que **no crezca**: se mide con uno y con cuatro.
        """
        otro = Ciudadano.objects.create(dni="24111333", nombre="Rosa", apellido="Díaz")
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            subir_archivos_para_objeto(otro, [SimpleUploadedFile("uno.pdf", b"x")])
            subir_archivos_para_objeto(self.ciudadano, [SimpleUploadedFile(f"doc{i}.pdf", b"x") for i in range(4)])
            # Los `ContentType` ya quedaron en la caché del proceso con las subidas.
            with self.assertNumQueries(3):  # ciudadano · legajos · adjuntos
                una = build_ciudadano_archivos_payload(otro.pk)
            with self.assertNumQueries(3):  # las mismas 3 con cuatro adjuntos
                cuatro = build_ciudadano_archivos_payload(self.ciudadano.pk)

        self.assertEqual(una["count"], 1)
        self.assertEqual(cuatro["count"], 4)


class SubidaMultipleAtomicaTests(TestCase):
    """LEG-05: o entran todos los archivos, o no entra ninguno."""

    def setUp(self):
        self.ciudadano = Ciudadano.objects.create(dni="25333444", nombre="Omar", apellido="Luna")

    def test_subida_con_un_archivo_invalido_no_guarda_ninguno(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            with self.assertRaises(ContactosFilesError):
                subir_archivos_para_objeto(
                    self.ciudadano,
                    [SimpleUploadedFile("dni.pdf", b"valido"), SimpleUploadedFile("foto.heic", b"invalido")],
                )

            self.assertEqual(Adjunto.objects.count(), 0)
            self.assertEqual(list(Path(media).rglob("*.pdf")), [])

    def test_subida_valida_guarda_todos(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            subidos = subir_archivos_para_objeto(
                self.ciudadano,
                [SimpleUploadedFile("dni.pdf", b"uno"), SimpleUploadedFile("acta.pdf", b"dos")],
                etiqueta="Documentación",
            )

            self.assertEqual(len(subidos), 2)
            self.assertEqual(Adjunto.objects.count(), 2)
            self.assertEqual({a.etiqueta for a in Adjunto.objects.all()}, {"Documentación"})

    def test_fallo_del_insert_no_deja_la_fila_ni_el_blob_que_ya_se_escribio(self):
        """El INSERT que falla **después** de que el blob se escribió.

        `FileField.pre_save` manda el archivo al storage adentro del `save()`, antes
        del INSERT: con la validación en verde y la base rechazando la fila, el blob
        queda en `media/` sin nada que lo referencie. Se falsea el INSERT —no la
        validación, que corta antes de tocar el disco— del **segundo** adjunto, así
        el test también exige que el blob del primero se limpie.
        """
        inserts = []
        real_as_sql = SQLInsertCompiler.as_sql

        def armar_el_sql_y_reventar(self):
            # `as_sql()` es donde el compilador llama a `pre_save` de cada campo, y es
            # ahí donde el `FileField` manda el blob al storage. Dejarlo correr y
            # fallar **después** es exactamente la ventana del bug: el archivo ya
            # está escrito y la fila todavía no existe. Parchear `_do_insert` entero
            # no sirve: `pre_save` corre adentro, así que el blob nunca se escribiría.
            sql = real_as_sql(self)
            if self.query.model is Adjunto:
                inserts.append(self.query.objs[0].archivo.name)
                if len(inserts) > 1:
                    raise DatabaseError("el INSERT del segundo adjunto falló")
            return sql

        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            with patch.object(SQLInsertCompiler, "as_sql", armar_el_sql_y_reventar):
                with self.assertRaises(DatabaseError):
                    subir_archivos_para_objeto(
                        self.ciudadano,
                        [SimpleUploadedFile("uno.pdf", b"uno"), SimpleUploadedFile("dos.pdf", b"dos")],
                    )

            # Los dos blobs llegaron al storage antes de que el INSERT se ejecutara:
            # el `FieldFile` ya no se llama como el archivo subido, sino `adjuntos/…`.
            self.assertEqual([Path(nombre).parent.name for nombre in inserts], ["adjuntos", "adjuntos"])
            self.assertEqual(Adjunto.objects.count(), 0)
            self.assertEqual(list(Path(media).rglob("*.pdf")), [])
