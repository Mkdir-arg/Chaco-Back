"""La migración de datos siembra el catálogo protegido en bases que ya existían
(Cambio 58, fase 4). Sin ella, un despliegue que no corre ``seed_becas`` deja el
formulario del portal sin identidad, contacto ni apoderado.

Se ejercita la función de la migración con los modelos reales: en la última
migración los históricos y los reales coinciden.
"""

from importlib import import_module

from django.apps import apps
from django.test import TestCase

from programas.models import GrupoRequisito, OrigenRequisito, PreguntaGlobal, TipoCampo

MIGRACION = import_module("programas.migrations.0060_sembrar_catalogo_protegido")


class SembrarCatalogoProtegidoTests(TestCase):
    def _sembrar(self):
        MIGRACION.sembrar(apps, None)

    def test_siembra_los_grupos_y_los_campos_vinculados(self):
        self.assertFalse(GrupoRequisito.objects.exists())
        self._sembrar()
        claves = list(GrupoRequisito.objects.order_by("orden").values_list("clave", flat=True))
        self.assertEqual(claves, ["datos_personales", "contacto", "apoderado", "cuestionario"])
        self.assertEqual(GrupoRequisito.objects.filter(protegido=True).count(), 3)
        genero = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="genero")
        self.assertEqual(genero.opciones, ["F", "M"])
        self.assertTrue(genero.protegido)
        self.assertEqual(PreguntaGlobal.objects.filter(origen=OrigenRequisito.PERSONA_VINCULADA).count(), 5)
        apoderado = GrupoRequisito.objects.get(clave="apoderado")
        self.assertEqual(apoderado.condicion_defecto["reglas"][0]["valor"], 18)
        email = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="email")
        self.assertFalse(email.obligatorio)  # D9: el contacto puede ser opcional

    def test_es_idempotente_y_no_pisa_lo_editado(self):
        self._sembrar()
        contacto = GrupoRequisito.objects.get(clave="contacto")
        contacto.nombre = "Cómo te contactamos"
        contacto.save(update_fields=["nombre"])
        telefono = PreguntaGlobal.objects.get(origen=OrigenRequisito.LEGAJO, vinculo="telefono")
        telefono.texto = "Tu celular"
        telefono.obligatorio = False
        telefono.save(update_fields=["texto", "obligatorio"])
        total = PreguntaGlobal.objects.count()

        self._sembrar()

        self.assertEqual(PreguntaGlobal.objects.count(), total)
        contacto.refresh_from_db()
        telefono.refresh_from_db()
        self.assertEqual(contacto.nombre, "Cómo te contactamos")
        self.assertEqual(telefono.texto, "Tu celular")
        self.assertFalse(telefono.obligatorio)

    def test_las_preguntas_sueltas_van_al_cuestionario(self):
        suelta = PreguntaGlobal.objects.create(texto="Vieja", tipo=TipoCampo.STRING, orden=5)
        PreguntaGlobal.objects.filter(pk=suelta.pk).update(grupo=None)
        self._sembrar()
        suelta.refresh_from_db()
        self.assertEqual(suelta.grupo, GrupoRequisito.objects.get(clave="cuestionario"))

    def test_no_choca_con_el_orden_de_las_preguntas_del_operador(self):
        PreguntaGlobal.objects.create(texto="Una", tipo=TipoCampo.STRING, orden=1)
        PreguntaGlobal.objects.create(texto="Otra", tipo=TipoCampo.STRING, orden=2)
        self._sembrar()
        ordenes = list(PreguntaGlobal.objects.values_list("orden", flat=True))
        self.assertEqual(len(ordenes), len(set(ordenes)))

    def test_coincide_con_lo_que_siembra_el_comando(self):
        """El snapshot de la migración y el catálogo vivo no deben divergir en
        qué campos existen (el comando manda si algún día cambian)."""
        from programas.management.commands.seed_becas import CATALOGO_PROTEGIDO

        del_comando = {
            (origen, vinculo)
            for _c, _n, _s, _o, _cond, campos in CATALOGO_PROTEGIDO
            for origen, vinculo, _e, _ob in campos
        }
        de_la_migracion = {
            (origen, vinculo)
            for _c, _n, _s, _o, _cond, campos in MIGRACION.CATALOGO_PROTEGIDO
            for origen, vinculo, _e, _ob in campos
        }
        self.assertEqual(del_comando, de_la_migracion)
