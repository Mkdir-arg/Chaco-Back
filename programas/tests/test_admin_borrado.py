"""DAT-02 · El `/admin/` no borra casos ni se come su auditoría.

`RelevamientoAdmin`, `FormularioAdmin`, `TracaFormularioAdmin` y `ListaEsperaAdmin`
borraban en cascada los adjuntos del ciudadano, las trazas de edición —que RN-14/29
declara **inmutables**— y la posición en la lista de espera. La pantalla de
confirmación lista la cascada, pero `delete_selected` se lleva varios de un saque sin
que nadie la lea, y ningún procedimiento pide borrar un caso: lo que hay es
rechazarlo.

La segunda mitad son los campos de `FormularioAdmin` que contaban la historia del caso
y se podían editar sin dejar traza: el estado, la validación de identidad y su origen,
lo que la persona declaró (`data`) y lo que el coordinador corrigió para SIIS.
"""

from datetime import date

from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse

from programas.models import (
    Convocatoria,
    CupoSegmento,
    Formulario,
    ListaEspera,
    Relevamiento,
    Segmento,
    TracaFormulario,
)

#: Los cuatro modelos de la ficha.
SIN_BORRADO = (Relevamiento, Formulario, TracaFormulario, ListaEspera)

#: Lo que `FormularioAdmin` tiene que dejar de solo lectura.
CAMPOS_DE_SOLO_LECTURA = (
    "estado",
    "validado_renaper",
    "identidad_forzada",
    "origen_validacion",
    "datos_siis",
    "data",
)


class AdminSinBorradoTests(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser("root_dat02", "root@dat02.test", "x")
        self.pedido = RequestFactory().get("/admin/")
        self.pedido.user = self.root
        self.client.force_login(self.root)

        segmento = Segmento.objects.create(nombre="Seg DAT-02", cupo_maximo=10)
        convocatoria = Convocatoria.objects.create(
            nombre="Conv DAT-02",
            segmento=segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria, territorial=self.root, fecha_asignada=date(2026, 6, 1), zona="A"
        )
        self.caso = Formulario.objects.create(relevamiento=self.relevamiento, celular="3624000000")

    def test_ni_el_superusuario_puede_borrarlos(self):
        for modelo in SIN_BORRADO:
            with self.subTest(modelo=modelo.__name__):
                self.assertFalse(admin.site._registry[modelo].has_delete_permission(self.pedido))

    def test_la_accion_masiva_no_se_ofrece(self):
        """Con `has_delete_permission` en False, Django saca `delete_selected` solo."""
        for modelo in SIN_BORRADO:
            with self.subTest(modelo=modelo.__name__):
                acciones = admin.site._registry[modelo].get_actions(self.pedido)
                self.assertNotIn("delete_selected", acciones)

    def test_el_post_de_borrado_de_un_caso_no_borra(self):
        url = reverse("admin:programas_formulario_delete", args=[self.caso.pk])

        resp = self.client.post(url, {"post": "yes"})

        self.assertEqual(resp.status_code, 403)
        self.assertTrue(Formulario.objects.filter(pk=self.caso.pk).exists())

    def test_los_campos_que_cuentan_la_historia_del_caso_son_de_lectura(self):
        ficha = admin.site._registry[Formulario]
        de_lectura = ficha.get_readonly_fields(self.pedido, self.caso)

        for campo in CAMPOS_DE_SOLO_LECTURA:
            with self.subTest(campo=campo):
                self.assertIn(campo, de_lectura)

    def test_el_contador_de_cuposegmento_no_se_edita_a_mano(self):
        """`cupo_ocupado` es derivado; a mano desajusta la validación de `Segmento`."""
        ficha = admin.site._registry[CupoSegmento]

        self.assertIn("cupo_ocupado", ficha.get_readonly_fields(self.pedido))

    def test_las_pantallas_de_configuracion_siguen_pudiendo_borrar(self):
        """El candado es de los cuatro modelos de la ficha, no del `/admin/` entero."""
        self.assertTrue(admin.site._registry[Segmento].has_delete_permission(self.pedido))
        self.assertTrue(admin.site._registry[Convocatoria].has_delete_permission(self.pedido))
