"""P3: la localidad sale del catálogo y los días y horarios son franjas estructuradas.

Lo que se fija acá, y por qué:

1. **Localidad del catálogo de Chaco**, guardada por nombre en el mismo `CharField`. Un POST
   con otra cosa se rechaza; un valor heredado del padrón se ofrece como «(cargado antes)»
   solo en su propio legajo, para que editar otro campo no lo borre.
2. **Las reglas de las franjas viven en el servicio** (`horarios_dispositivo`): inicio
   anterior al fin, sin superposición en el mismo día (contiguas sí), tope por día. El form
   las usa para pintar el error en la fila, y `reemplazar_franjas` las vuelve a exigir.
3. **`Dispositivo.horarios` es derivado**: con franjas, su resumen; sin franjas y con texto
   viejo, el texto se conserva; si tenía franjas y se quitan todas, queda vacío.
"""

from datetime import time
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase, TestCase, tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import Localidad, Municipio, Provincia
from programas.forms import DispositivoForm
from programas.models import Dispositivo, HorarioDispositivo, TipoDispositivo, TrazaDispositivo
from programas.services.horarios_dispositivo import (
    MAX_FRANJAS_POR_DIA,
    Franja,
    errores_de_franjas,
    reemplazar_franjas,
    resumen_de_franjas,
)
from programas.tests.test_dispositivos_fidelidad_fd import AHORA
from programas.tests.test_dispositivos_infraestructura import BaseInfraestructura

LUNES, MARTES = HorarioDispositivo.Dia.LUNES, HorarioDispositivo.Dia.MARTES


def catalogo_chaco(*localidades):
    """Provincia de Chaco con un municipio y sus localidades (por defecto, Resistencia)."""
    provincia, _ = Provincia.objects.get_or_create(nombre="Chaco")
    municipio, _ = Municipio.objects.get_or_create(nombre="Resistencia", provincia=provincia)
    for nombre in localidades or ("Resistencia",):
        Localidad.objects.get_or_create(nombre=nombre, municipio=municipio)
    return municipio


def _f(dia, desde, hasta):
    return Franja(dia, time(*desde), time(*hasta))


def _post_franjas(*franjas, borrar=(), extra_vacias=1):
    """El POST del formset como lo arma el navegador: filas con datos y vacías al final."""
    datos = {}
    filas = [*franjas, *([None] * extra_vacias)]
    for indice, franja in enumerate(filas):
        dia, desde, hasta = franja or ("", "", "")
        datos[f"franjas-{indice}-dia"] = dia
        datos[f"franjas-{indice}-hora_desde"] = desde
        datos[f"franjas-{indice}-hora_hasta"] = hasta
        if indice in borrar:
            datos[f"franjas-{indice}-DELETE"] = "on"
    datos["franjas-TOTAL_FORMS"] = str(len(filas))
    datos["franjas-INITIAL_FORMS"] = "0"
    return datos


class ReglasDeFranjasTests(SimpleTestCase):
    def test_desde_igual_o_posterior_a_hasta_es_error_en_hasta(self):
        for franja in (_f(LUNES, (12, 0), (9, 0)), _f(LUNES, (9, 0), (9, 0))):
            with self.subTest(franja=franja):
                self.assertEqual(
                    errores_de_franjas([franja]),
                    [(0, "hora_hasta", "La hora «Hasta» tiene que ser posterior a «Desde».")],
                )

    def test_dos_franjas_del_mismo_dia_superpuestas_se_rechazan(self):
        errores = errores_de_franjas([_f(LUNES, (9, 0), (12, 0)), _f(LUNES, (11, 0), (14, 0))])

        self.assertEqual(errores, [(1, "hora_desde", "Se superpone con la franja del lunes de 09:00 a 12:00.")])

    def test_superposicion_contra_una_franja_anterior_que_no_es_la_previa(self):
        # 09–18 contiene a las dos siguientes: la tercera no pisa a la segunda, pero sí a la primera.
        errores = errores_de_franjas(
            [_f(LUNES, (9, 0), (18, 0)), _f(LUNES, (10, 0), (11, 0)), _f(LUNES, (12, 0), (13, 0))]
        )

        self.assertEqual([posicion for posicion, _campo, _mensaje in errores], [1, 2])

    def test_franjas_contiguas_son_validas(self):
        self.assertEqual(errores_de_franjas([_f(LUNES, (9, 0), (12, 0)), _f(LUNES, (12, 0), (18, 0))]), [])

    def test_mismo_horario_en_dias_distintos_es_valido(self):
        self.assertEqual(errores_de_franjas([_f(LUNES, (9, 0), (12, 0)), _f(MARTES, (9, 0), (12, 0))]), [])

    def test_tope_de_franjas_por_dia(self):
        franjas = [_f(LUNES, (hora, 0), (hora, 30)) for hora in range(8, 8 + MAX_FRANJAS_POR_DIA + 1)]

        self.assertEqual(errores_de_franjas(franjas), [(MAX_FRANJAS_POR_DIA, "dia", "Un día admite hasta 4 franjas.")])
        self.assertEqual(errores_de_franjas(franjas[:MAX_FRANJAS_POR_DIA]), [])

    def test_resumen_por_dia_en_orden(self):
        franjas = [_f(MARTES, (15, 0), (16, 0)), _f(LUNES, (13, 0), (18, 0)), _f(LUNES, (9, 0), (12, 0))]

        self.assertEqual(resumen_de_franjas(franjas), "Lunes 09:00–12:00 y 13:00–18:00 · Martes 15:00–16:00")
        self.assertEqual(
            resumen_de_franjas([*franjas, _f(LUNES, (19, 0), (20, 0))]),
            "Lunes 09:00–12:00, 13:00–18:00 y 19:00–20:00 · Martes 15:00–16:00",
        )


class ReemplazarFranjasTests(TestCase):
    def setUp(self):
        tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")
        self.dispositivo = Dispositivo.objects.create(codigo="H-1", nombre="Hogar", tipo=tipo)

    def test_guarda_las_franjas_y_deriva_el_resumen(self):
        cambio = reemplazar_franjas(self.dispositivo, [_f(MARTES, (15, 0), (16, 0)), _f(LUNES, (9, 0), (18, 0))])

        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.horarios, "Lunes 09:00–18:00 · Martes 15:00–16:00")
        self.assertEqual(cambio, {"anterior": "", "nuevo": "Lunes 09:00–18:00 · Martes 15:00–16:00"})
        self.assertEqual(
            list(self.dispositivo.franjas_horarias.values_list("dia", "hora_desde", "hora_hasta")),
            [(LUNES, time(9), time(18)), (MARTES, time(15), time(16))],
        )

    def test_el_servicio_rechaza_superpuestas_aunque_no_pasen_por_el_form(self):
        with self.assertRaises(ValidationError):
            reemplazar_franjas(self.dispositivo, [_f(LUNES, (9, 0), (12, 0)), _f(LUNES, (11, 0), (13, 0))])

        self.assertFalse(self.dispositivo.franjas_horarias.exists())
        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.horarios, "")

    def test_texto_viejo_se_conserva_sin_franjas(self):
        self.dispositivo.horarios = "Lunes a viernes de 8 a 16"
        self.dispositivo.save()

        self.assertIsNone(reemplazar_franjas(self.dispositivo, []))

        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.horarios, "Lunes a viernes de 8 a 16")

    def test_texto_viejo_se_reemplaza_al_cargar_franjas(self):
        self.dispositivo.horarios = "Lunes a viernes de 8 a 16"
        self.dispositivo.save()

        reemplazar_franjas(self.dispositivo, [_f(LUNES, (8, 0), (16, 0))])

        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.horarios, "Lunes 08:00–16:00")

    def test_quitar_todas_las_franjas_vacia_el_resumen(self):
        reemplazar_franjas(self.dispositivo, [_f(LUNES, (8, 0), (16, 0))])

        cambio = reemplazar_franjas(self.dispositivo, [])

        self.dispositivo.refresh_from_db()
        self.assertEqual(self.dispositivo.horarios, "")
        self.assertEqual(cambio, {"anterior": "Lunes 08:00–16:00", "nuevo": ""})
        self.assertFalse(self.dispositivo.franjas_horarias.exists())

    def test_sin_el_bloque_de_franjas_no_toca_nada(self):
        reemplazar_franjas(self.dispositivo, [_f(LUNES, (8, 0), (16, 0))])

        self.assertIsNone(reemplazar_franjas(self.dispositivo, None))

        self.assertEqual(self.dispositivo.franjas_horarias.count(), 1)

    def test_el_mismo_conjunto_no_reescribe(self):
        reemplazar_franjas(self.dispositivo, [_f(LUNES, (8, 0), (16, 0))])
        franja = self.dispositivo.franjas_horarias.get()

        self.assertIsNone(reemplazar_franjas(self.dispositivo, [_f(LUNES, (8, 0), (16, 0))]))

        self.assertEqual(self.dispositivo.franjas_horarias.get().pk, franja.pk)


class LocalidadDelCatalogoTests(TestCase):
    def setUp(self):
        self.tipo = TipoDispositivo.objects.create(codigo="AM", nombre="Adulto Mayor")
        catalogo_chaco("Resistencia", "Barranqueras")
        self.datos = {"tipo": self.tipo.pk, "codigo": "LOC-1", "nombre": "Hogar"}

    def test_localidad_fuera_del_catalogo_se_rechaza(self):
        # Una localidad de otra provincia tampoco vale: el catálogo es el de Chaco.
        corrientes = Municipio.objects.create(nombre="Goya", provincia=Provincia.objects.create(nombre="Corrientes"))
        Localidad.objects.create(nombre="Goya", municipio=corrientes)
        for valor in ("Inventada", "Goya"):
            with self.subTest(valor=valor):
                form = DispositivoForm({**self.datos, "localidad": valor})

                self.assertFalse(form.is_valid())
                self.assertEqual(form.errors["localidad"], ["Elegí una localidad del listado."])

    def test_localidad_del_catalogo_se_guarda_por_nombre(self):
        form = DispositivoForm({**self.datos, "localidad": "Barranqueras"})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().localidad, "Barranqueras")

    def test_el_selector_tiene_opcion_vacia_y_las_localidades(self):
        opciones = DispositivoForm().fields["localidad"].choices

        self.assertEqual(
            opciones, [("", "Elegí una localidad"), ("Barranqueras", "Barranqueras"), ("Resistencia", "Resistencia")]
        )

    def test_nombre_repetido_entre_municipios_va_una_vez_con_los_municipios(self):
        otro = Municipio.objects.create(nombre="Puerto Tirol", provincia=Provincia.objects.get(nombre="Chaco"))
        Localidad.objects.create(nombre="Barranqueras", municipio=otro)

        opciones = DispositivoForm().fields["localidad"].choices

        self.assertIn(("Barranqueras", "Barranqueras (Puerto Tirol / Resistencia)"), opciones)
        self.assertEqual([valor for valor, _ in opciones].count("Barranqueras"), 1)

    def test_valor_heredado_se_ofrece_marcado_y_se_conserva_al_editar(self):
        dispositivo = Dispositivo.objects.create(
            codigo="LOC-1", nombre="Hogar", tipo=self.tipo, localidad="Pampa del Infierno (padrón)"
        )

        form = DispositivoForm(instance=dispositivo)
        self.assertEqual(
            form.fields["localidad"].choices[1],
            ("Pampa del Infierno (padrón)", "Pampa del Infierno (padrón) (cargado antes)"),
        )
        self.assertIn('value="Pampa del Infierno (padrón)" selected', str(form["localidad"]))

        form = DispositivoForm(
            {**self.datos, "nombre": "Hogar renombrado", "localidad": "Pampa del Infierno (padrón)"},
            instance=dispositivo,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn("localidad", form.changed_data)

    def test_valor_heredado_no_vale_para_otro_legajo(self):
        Dispositivo.objects.create(
            codigo="LOC-1", nombre="Hogar", tipo=self.tipo, localidad="Pampa del Infierno (padrón)"
        )

        form = DispositivoForm({**self.datos, "codigo": "LOC-2", "localidad": "Pampa del Infierno (padrón)"})

        self.assertFalse(form.is_valid())
        self.assertIn("localidad", form.errors)

    def test_valor_heredado_reemplazado_ya_no_se_ofrece(self):
        dispositivo = Dispositivo.objects.create(
            codigo="LOC-1", nombre="Hogar", tipo=self.tipo, localidad="Pampa del Infierno (padrón)"
        )
        form = DispositivoForm({**self.datos, "localidad": "Resistencia"}, instance=dispositivo)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()

        self.assertNotIn(
            "Pampa del Infierno (padrón)",
            [valor for valor, _ in DispositivoForm(instance=dispositivo).fields["localidad"].choices],
        )


class PantallaDeHorariosTests(BaseInfraestructura):
    def setUp(self):
        reloj = patch("django.utils.timezone.now", return_value=AHORA)
        reloj.start()
        self.addCleanup(reloj.stop)
        super().setUp()
        catalogo_chaco()
        self.client.force_login(self.admin)
        self.cis.estado = Dispositivo.Estado.BORRADOR
        self.cis.localidad = "Resistencia"
        self.cis.save()
        self.editar = reverse("dispositivos:editar", args=[self.cis.pk])
        self.datos = {
            "tipo": self.cis.tipo_id,
            "codigo": self.cis.codigo,
            "nombre": self.cis.nombre,
            "localidad": "Resistencia",
        }

    def test_alta_guarda_franjas_y_resumen_en_la_misma_transaccion(self):
        respuesta = self.client.post(
            reverse("dispositivos:crear"),
            {
                "tipo": self.cis.tipo_id,
                "codigo": "HOR-1",
                "nombre": "Institución con horario",
                "localidad": "Resistencia",
                **_post_franjas((LUNES, "09:00", "12:00"), (LUNES, "13:00", "18:00"), (MARTES, "15:00", "16:00")),
            },
        )

        self.assertEqual(respuesta.status_code, 302)
        nuevo = Dispositivo.objects.get(codigo="HOR-1")
        self.assertEqual(nuevo.horarios, "Lunes 09:00–12:00 y 13:00–18:00 · Martes 15:00–16:00")
        self.assertEqual(nuevo.franjas_horarias.count(), 3)

    def test_edicion_superpuesta_vuelve_con_el_error_en_la_fila_y_no_guarda(self):
        respuesta = self.client.post(
            self.editar, {**self.datos, **_post_franjas((LUNES, "09:00", "12:00"), (LUNES, "11:00", "14:00"))}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Se superpone con la franja del lunes de 09:00 a 12:00.")
        self.assertFalse(self.cis.franjas_horarias.exists())

    def test_fila_a_medias_pide_lo_que_falta(self):
        respuesta = self.client.post(self.editar, {**self.datos, **_post_franjas((LUNES, "09:00", ""))})

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Indicá hasta qué hora.")

    def test_edicion_reemplaza_el_conjunto_y_deja_traza_del_resumen(self):
        reemplazar_franjas(self.cis, [_f(LUNES, (8, 0), (16, 0)), _f(MARTES, (8, 0), (16, 0))])

        respuesta = self.client.post(
            self.editar,
            {**self.datos, **_post_franjas((LUNES, "08:00", "16:00"), (MARTES, "08:00", "16:00"), borrar={1})},
        )

        self.assertEqual(respuesta.status_code, 302)
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.horarios, "Lunes 08:00–16:00")
        self.assertEqual(self.cis.franjas_horarias.count(), 1)
        traza = TrazaDispositivo.objects.filter(dispositivo=self.cis, accion="EDITADO").latest("pk")
        self.assertIn('"horarios"', traza.detalle)
        self.assertIn('"nuevo": "Lunes 08:00–16:00"', traza.detalle)

    def test_la_tabla_muestra_las_franjas_y_su_quitar(self):
        reemplazar_franjas(self.cis, [_f(LUNES, (9, 0), (12, 0))])

        respuesta = self.client.get(self.editar)

        self.assertContains(respuesta, "Días y horarios")
        self.assertContains(respuesta, 'data-dia="1" data-desde="09:00" data-hasta="12:00"')
        self.assertContains(respuesta, 'name="franjas-0-DELETE"')
        self.assertContains(respuesta, 'name="franjas-TOTAL_FORMS" value="4"')
        self.assertContains(respuesta, '<tr data-franjas-vacio class="hidden">')
        self.assertNotContains(respuesta, 'name="horarios"')

    def test_horario_viejo_se_muestra_hasta_que_haya_franjas(self):
        self.cis.horarios = "Lunes a viernes de 8 a 16"
        self.cis.save()

        respuesta = self.client.get(self.editar)
        self.assertContains(respuesta, "Horario cargado antes:")
        self.assertContains(respuesta, "Lunes a viernes de 8 a 16")

        # Guardar otro dato sin franjas no lo pierde.
        respuesta = self.client.post(self.editar, {**self.datos, "nombre": "Renombrado", **_post_franjas()})
        self.assertEqual(respuesta.status_code, 302)
        self.cis.refresh_from_db()
        self.assertEqual(self.cis.horarios, "Lunes a viernes de 8 a 16")

        reemplazar_franjas(self.cis, [_f(LUNES, (8, 0), (16, 0))])
        self.assertNotContains(self.client.get(self.editar), "Horario cargado antes:")

    def test_localidad_heredada_sobrevive_a_una_edicion_por_pantalla(self):
        self.cis.localidad = "Colonia vieja"
        self.cis.save()

        respuesta = self.client.get(self.editar)
        self.assertContains(respuesta, "Colonia vieja (cargado antes)")

        respuesta = self.client.post(
            self.editar, {**self.datos, "localidad": "Colonia vieja", "nombre": "Renombrado", **_post_franjas()}
        )
        self.assertEqual(respuesta.status_code, 302)
        self.cis.refresh_from_db()
        self.assertEqual((self.cis.nombre, self.cis.localidad), ("Renombrado", "Colonia vieja"))

    @tag("performance")
    def test_editar_no_hace_una_consulta_por_franja(self):
        def consultas():
            with CaptureQueriesContext(connection) as capturadas:
                self.assertEqual(self.client.get(self.editar).status_code, 200)
            return len(capturadas)

        reemplazar_franjas(self.cis, [_f(LUNES, (9, 0), (10, 0))])
        consultas()  # la primera paga la sesión y la caché del programa
        una = consultas()
        reemplazar_franjas(
            self.cis, [_f(dia, (hora, 0), (hora, 30)) for dia in (LUNES, MARTES) for hora in (9, 11, 13, 15)]
        )

        self.assertEqual(consultas(), una)
