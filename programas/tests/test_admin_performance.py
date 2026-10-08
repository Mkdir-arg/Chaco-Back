"""G1c-09 y G1c-11 · Ninguna pantalla del `/admin/` crece con la tabla.

La PoC de la auditoría (`poc/test_repro_admin_cron_renaper.py::G1c09AdminNmas1Tests`)
medía la ficha de un `Formulario` pasando de **19 a 46** consultas cuando la tabla
pasaba de 5 a 35 casos, y el alta de una `DerivacionPrograma` de **21 a 80** con 5 → 35
inscripciones. La causa es el `<select>` que Django arma para cada FK: trae todas las
filas del modelo apuntado y llama a su `__str__` por opción, y `Formulario.__str__` abre
el ciudadano mientras `InscripcionPrograma.__str__` abre ciudadano y programa.

Estos tests son el invertido: la **misma** cantidad de consultas con 5 y con 35 filas.
Están escritos contra el número medido y no contra un techo, así que vuelven a ponerse
rojos si alguien agrega una FK a una ficha sin ponerla en `raw_id_fields`.

La segunda mitad es G1c-11, los listados: las FK de `list_display` resueltas fila por
fila. Mismo criterio —constante respecto de la cantidad de filas de la página—.

Y la tercera, el contrato que no se puede romper al arreglar esto: **nadie gana ni
pierde acceso al admin**.
"""

from datetime import date

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from zeal import zeal_ignore

from legajos.models import Ciudadano
from programas.models import (
    Convocatoria,
    DerivacionPrograma,
    Formulario,
    InscripcionPrograma,
    ListaEspera,
    Programa,
    ProgramaSiis,
    Relevamiento,
    Segmento,
    TracaFormulario,
)

#: Cuántas filas tiene la tabla en la primera y en la segunda medición. Con 5 y con 35
#: la PoC ya mostraba el crecimiento; más filas solo haría el test más lento.
CHICO, GRANDE = 5, 30


class _BaseAdmin(TestCase):
    """Un superusuario logueado y el árbol mínimo de Becas."""

    def setUp(self):
        self.root = User.objects.create_superuser("root_g1c09", "root@g1c09.test", "x")
        self.client.force_login(self.root)
        siis = ProgramaSiis.objects.create(nombre="P G1c-09", siis_programa_id=79)
        self.segmento = Segmento.objects.create(nombre="Seg G1c-09", cupo_maximo=100, programa=siis)
        convocatoria = Convocatoria.objects.create(
            nombre="Conv G1c-09",
            segmento=self.segmento,
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 12, 31),
        )
        self.relevamiento = Relevamiento.objects.create(
            convocatoria=convocatoria,
            territorial=self.root,
            fecha_asignada=date(2026, 6, 1),
            zona="A",
        )
        self.programa = Programa.objects.create(codigo="G1C09", nombre="Programa G1c-09")
        self.creados = 0

    def sumar_filas(self, cuantas):
        """Agrega `cuantas` ciudadanos, cada uno con su caso y su inscripción."""
        for _ in range(cuantas):
            self.creados += 1
            ciudadano = Ciudadano.objects.create(
                dni=f"4{self.creados:07d}", nombre="Nombre", apellido=f"Apellido{self.creados}"
            )
            formulario = Formulario.objects.create(relevamiento=self.relevamiento, ciudadano=ciudadano)
            InscripcionPrograma.objects.create(ciudadano=ciudadano, programa=self.programa)
            TracaFormulario.objects.create(
                formulario=formulario, editado_por=self.root, campo="estado", valor_anterior="", valor_nuevo="ENVIADO"
            )
            ListaEspera.objects.create(segmento=self.segmento, formulario=formulario, posicion=self.creados)

    def consultas_de(self, url):
        # zeal corta con `NPlusOneError` antes de que el test pueda contar: lo que acá
        # se mide es cuántas consultas salen, no si zeal las reconoce.
        with zeal_ignore(), CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, url)
        return len(capturadas.captured_queries)

    def primera_visita(self, url):
        """El primer request de la sesión paga cosas que no se repiten —el `Profile` de
        la sesión única de backoffice, el alta de la fila de sesión—. Se descartan: lo
        que se compara es request de régimen contra request de régimen."""
        with zeal_ignore():
            self.client.get(url)

    def assert_no_crece(self, url):
        """La misma URL cuesta lo mismo con `CHICO` filas que con `CHICO + GRANDE`."""
        self.sumar_filas(CHICO)
        self.primera_visita(url)
        con_pocas = self.consultas_de(url)
        self.sumar_filas(GRANDE)
        con_muchas = self.consultas_de(url)
        self.assertEqual(
            con_muchas,
            con_pocas,
            f"{url}: {con_pocas} consultas con {CHICO} filas y {con_muchas} con {CHICO + GRANDE}",
        )
        return con_pocas


class FichasQueNoCrecenConLaTablaTests(_BaseAdmin):
    """G1c-09: las dos fichas que la PoC midió, más las que comparten la causa."""

    def test_la_ficha_de_un_caso_no_crece_con_la_cantidad_de_casos(self):
        self.sumar_filas(CHICO)
        caso = Formulario.objects.order_by("pk").first()
        url = reverse("admin:programas_formulario_change", args=[caso.pk])
        self.primera_visita(url)
        con_pocas = self.consultas_de(url)
        self.sumar_filas(GRANDE)
        con_muchas = self.consultas_de(url)
        self.assertEqual(con_muchas, con_pocas, f"{con_pocas} consultas con {CHICO} casos y {con_muchas} con 35")

    def test_el_alta_de_una_derivacion_no_crece_con_las_inscripciones(self):
        self.assert_no_crece(reverse("admin:programas_derivacionprograma_add"))

    def test_el_alta_de_un_caso_no_crece_con_la_tabla(self):
        self.assert_no_crece(reverse("admin:programas_formulario_add"))

    def test_el_alta_de_una_inscripcion_no_crece_con_el_padron(self):
        self.assert_no_crece(reverse("admin:programas_inscripcionprograma_add"))

    def test_el_alta_en_lista_de_espera_no_crece_con_los_casos(self):
        self.assert_no_crece(reverse("admin:programas_listaespera_add"))

    def test_las_fk_grandes_de_cada_ficha_estan_en_raw_id_fields(self):
        """El contrato, escrito como tal: qué FK no puede volver a ser un `<select>`.

        Es la red del test de consultas: si mañana alguien suma una FK a
        `programas_formulario`, este test nombra el lugar donde ponerla.
        """
        esperado = {
            Formulario: {"relevamiento", "ciudadano", "duplicado_de", "apoderado_ciudadano", "created_by"},
            InscripcionPrograma: {"ciudadano", "responsable"},
            DerivacionPrograma: {"ciudadano", "inscripcion_creada", "derivado_por", "respondido_por"},
            ListaEspera: {"formulario"},
        }
        for modelo, campos in esperado.items():
            registrado = admin.site._registry[modelo]
            self.assertTrue(
                campos <= set(registrado.raw_id_fields),
                f"{modelo.__name__}: faltan en raw_id_fields {campos - set(registrado.raw_id_fields)}",
            )


class ListadosQueNoCrecenConLaPaginaTests(_BaseAdmin):
    """G1c-11: una FK de `list_display` no se puede resolver fila por fila."""

    def test_el_listado_de_casos_no_crece_con_la_pagina(self):
        self.assert_no_crece(reverse("admin:programas_formulario_changelist"))

    def test_el_listado_de_trazas_no_crece_con_la_pagina(self):
        self.assert_no_crece(reverse("admin:programas_tracaformulario_changelist"))

    def test_el_listado_de_lista_de_espera_no_crece_con_la_pagina(self):
        self.assert_no_crece(reverse("admin:programas_listaespera_changelist"))

    def test_el_listado_de_inscripciones_no_crece_con_la_pagina(self):
        self.assert_no_crece(reverse("admin:programas_inscripcionprograma_changelist"))

    def test_el_listado_de_relevamientos_no_crece_con_la_pagina(self):
        """`RelevamientoAdmin` muestra convocatoria y territorial sin `get_queryset`."""
        self.primera_visita(reverse("admin:programas_relevamiento_changelist"))
        for n in range(CHICO + GRANDE):
            convocatoria = Convocatoria.objects.create(
                nombre=f"Conv extra {n}",
                segmento=self.segmento,
                fecha_inicio=date(2026, 1, 1),
                fecha_fin=date(2026, 12, 31),
            )
            Relevamiento.objects.create(
                convocatoria=convocatoria,
                territorial=self.root,
                fecha_asignada=date(2026, 6, 1),
                zona=f"Z{n}",
            )
            if n == CHICO - 1:
                con_pocos = self.consultas_de(reverse("admin:programas_relevamiento_changelist"))
        con_muchos = self.consultas_de(reverse("admin:programas_relevamiento_changelist"))
        self.assertEqual(con_muchos, con_pocos)

    def test_la_traza_se_busca_por_id_exacto_y_no_con_like(self):
        """`=formulario__id`: sin el `=`, Django arma `LIKE %texto%` sobre el id."""
        registrado = admin.site._registry[TracaFormulario]
        self.assertIn("=formulario__id", registrado.search_fields)
        self.assertNotIn("formulario__id", registrado.search_fields)


class NadieGanaNiPierdeAccesoAlAdminTests(_BaseAdmin):
    """El contrato que G1c-09 y G1c-11 no pueden romper mientras optimizan.

    `raw_id_fields` y `list_select_related` son cambios de presentación y de consulta:
    quién entra a cada pantalla lo siguen decidiendo `is_staff` y los permisos de
    Django, y DAT-02 sigue sin dejar borrar.
    """

    #: Los modelos que este PR tocó, con el prefijo de sus URLs de admin.
    TOCADOS = (
        ("programas", "formulario"),
        ("programas", "inscripcionprograma"),
        ("programas", "derivacionprograma"),
        ("programas", "listaespera"),
        ("programas", "tracaformulario"),
        ("programas", "relevamiento"),
        ("legajos", "ciudadano"),
        ("legajos", "historialcontacto"),
        ("legajos", "vinculofamiliar"),
    )

    def test_sin_is_staff_ninguna_de_las_pantallas_tocadas_se_abre(self):
        sin_staff = User.objects.create_user("sin_staff_g1c09", password="x")
        self.client.force_login(sin_staff)
        for app, modelo in self.TOCADOS:
            respuesta = self.client.get(reverse(f"admin:{app}_{modelo}_changelist"))
            self.assertEqual(respuesta.status_code, 302, f"{app}.{modelo}")
            self.assertIn("/admin/login/", respuesta["Location"])

    def test_con_is_staff_y_sin_permiso_del_modelo_tampoco(self):
        staff = User.objects.create_user("staff_g1c09", password="x", is_staff=True)
        self.client.force_login(staff)
        for app, modelo in self.TOCADOS:
            respuesta = self.client.get(reverse(f"admin:{app}_{modelo}_changelist"))
            self.assertEqual(respuesta.status_code, 403, f"{app}.{modelo}")

    def test_con_el_permiso_de_ver_del_modelo_se_abre_su_listado(self):
        staff = User.objects.create_user("staff_ver_g1c09", password="x", is_staff=True)
        for app, modelo in self.TOCADOS:
            staff.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=f"view_{modelo}"))
        self.client.force_login(staff)
        self.sumar_filas(CHICO)
        for app, modelo in self.TOCADOS:
            with zeal_ignore():
                respuesta = self.client.get(reverse(f"admin:{app}_{modelo}_changelist"))
            self.assertEqual(respuesta.status_code, 200, f"{app}.{modelo}")

    def test_los_cuatro_modelos_de_dat02_siguen_sin_poder_borrarse(self):
        for modelo in (Relevamiento, Formulario, TracaFormulario, ListaEspera):
            registrado = admin.site._registry[modelo]
            self.assertFalse(registrado.has_delete_permission(self._pedido()), modelo.__name__)

    def _pedido(self):
        from django.test import RequestFactory

        pedido = RequestFactory().get("/admin/")
        pedido.user = self.root
        return pedido
