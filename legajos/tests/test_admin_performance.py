"""G1c-09 y G1c-11 en `legajos` · El admin de contactos y vínculos no crece con el padrón.

`VinculoFamiliarAdmin` tenía **dos** combos con el padrón entero, uno al lado del otro, y
`HistorialContactoAdmin` listaba todos los legajos de atención y todos los usuarios.
`CiudadanoAdmin` prefetcheaba `inscripciones_programas__programa`, que ninguna de sus dos
pantallas lee.

**Lo que la ficha daba por cierto y no lo era:** los *listados* de estos tres modelos no
eran N+1. Django le aplica `select_related()` sin argumentos a toda `ChangeList` con un
campo relacionado en `list_display`, y las cuatro FK en juego (`legajo`, `profesional`,
los dos ciudadanos del vínculo) son **no nulas**, que es justo lo que ese
`select_related()` cubre. Los tests de listado de acá quedan como guarda: pasan hoy y se
ponen rojos si alguien vuelve nulable una de esas FK, porque ahí sí Django la deja afuera.

El gemelo en Becas es `programas/tests/test_admin_performance.py`, donde las FK nulables
(`Formulario.ciudadano`, `Relevamiento.territorial`, `TracaFormulario.editado_por`) y los
saltos de segundo nivel sí hacían crecer la página.
"""

from django.contrib import admin
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from zeal import zeal_ignore

from legajos.models import Ciudadano, LegajoAtencion
from legajos.models.contactos import HistorialContacto, VinculoFamiliar
from programas.models import InscripcionPrograma, Programa

CHICO, GRANDE = 5, 30


class _BaseAdminLegajos(TestCase):
    def setUp(self):
        self.root = User.objects.create_superuser("root_g1c11", "root@g1c11.test", "x")
        self.client.force_login(self.root)
        self.programa = Programa.objects.create(codigo="G1C11", nombre="Programa G1c-11")
        self.creados = 0

    def sumar_filas(self, cuantas):
        for _ in range(cuantas):
            self.creados += 1
            n = self.creados
            titular = Ciudadano.objects.create(dni=f"5{n:07d}", nombre="Titular", apellido=f"Ap{n}")
            pariente = Ciudadano.objects.create(dni=f"6{n:07d}", nombre="Pariente", apellido=f"Ap{n}")
            # El legajo no tiene FK al ciudadano: se enlaza por el `legajo_id` de la
            # inscripción, que es un `UUIDField` suelto (ver `services/linking.py`).
            legajo = LegajoAtencion.objects.create()
            InscripcionPrograma.objects.create(ciudadano=titular, programa=self.programa, legajo_id=legajo.id)
            HistorialContacto.objects.create(
                legajo=legajo,
                profesional=self.root,
                tipo_contacto="TELEFONICO",
                fecha_contacto=timezone.now(),
                motivo="m",
                resumen="r",
            )
            VinculoFamiliar.objects.create(
                ciudadano_principal=titular, ciudadano_vinculado=pariente, tipo_vinculo="HERMANO"
            )

    def consultas_de(self, url):
        with zeal_ignore(), CaptureQueriesContext(connection) as capturadas:
            respuesta = self.client.get(url)
        self.assertEqual(respuesta.status_code, 200, url)
        return len(capturadas.captured_queries)

    def primera_visita(self, url):
        """El primer request de la sesión paga el `Profile` de la sesión única y el alta
        de la fila de sesión: no se repiten y no se cuentan."""
        with zeal_ignore():
            self.client.get(url)

    def assert_no_crece(self, url):
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


class ListadosDeLegajosTests(_BaseAdminLegajos):
    def test_el_listado_de_contactos_trae_el_legajo_y_el_profesional_en_la_misma_consulta(self):
        """Guarda: la página une las dos FK en su propia consulta.

        Hoy lo consigue sin `list_select_related`, porque las dos son no nulas y las toma
        el `select_related()` que Django aplica solo. Volver nulable cualquiera de las dos
        —o sumar una tercera FK a `list_display`— deja este test en rojo, que es el aviso
        de que ahí hace falta declarar `list_select_related`.
        """
        self.sumar_filas(CHICO)
        url = reverse("admin:legajos_historialcontacto_changelist")
        self.primera_visita(url)
        with zeal_ignore(), CaptureQueriesContext(connection) as capturadas:
            self.assertEqual(self.client.get(url).status_code, 200)

        pagina = [q["sql"] for q in capturadas.captured_queries if "legajos_historialcontacto" in q["sql"]]
        con_las_dos = [sql for sql in pagina if "legajos_legajoatencion" in sql and "auth_user" in sql]
        self.assertTrue(con_las_dos, "la página trae los contactos sin unir el legajo ni el profesional")

    def test_el_listado_de_contactos_crece_de_a_una_consulta_por_fila_y_solo_por_el_vinculo_blando(self):
        """Lo que queda pendiente, fijado para que no crezca.

        La única consulta por fila que sobrevive es `LegajoAtencion.__str__` abriendo su
        property `ciudadano`: `InscripcionPrograma.legajo_id` es un `UUIDField` suelto, no
        una FK, así que no hay relación que el ORM pueda seguir. Si el número sube de 1,
        alguien agregó otro N+1.
        """
        self.sumar_filas(CHICO)
        url = reverse("admin:legajos_historialcontacto_changelist")
        self.primera_visita(url)
        con_pocas = self.consultas_de(url)
        self.sumar_filas(GRANDE)
        con_muchas = self.consultas_de(url)

        self.assertEqual(con_muchas - con_pocas, GRANDE)

    def test_el_listado_de_vinculos_no_crece_con_la_pagina(self):
        self.assert_no_crece(reverse("admin:legajos_vinculofamiliar_changelist"))

    def test_el_listado_de_ciudadanos_no_crece_con_la_pagina(self):
        self.assert_no_crece(reverse("admin:legajos_ciudadano_changelist"))

    def test_el_listado_de_ciudadanos_no_lee_las_inscripciones_que_no_muestra(self):
        """El prefetch que se sacó: ninguna consulta de la página toca inscripciones."""
        self.sumar_filas(CHICO)
        with zeal_ignore(), CaptureQueriesContext(connection) as capturadas:
            self.client.get(reverse("admin:legajos_ciudadano_changelist"))
        sql = " ".join(q["sql"] for q in capturadas.captured_queries)
        self.assertNotIn("programas_inscripcionprograma", sql)


class FichasDeLegajosTests(_BaseAdminLegajos):
    def test_el_alta_de_un_contacto_no_crece_con_los_legajos(self):
        self.assert_no_crece(reverse("admin:legajos_historialcontacto_add"))

    def test_el_alta_de_un_vinculo_no_crece_con_el_padron(self):
        self.assert_no_crece(reverse("admin:legajos_vinculofamiliar_add"))

    def test_las_fk_grandes_estan_en_raw_id_fields(self):
        esperado = {
            HistorialContacto: {"legajo", "profesional"},
            VinculoFamiliar: {"ciudadano_principal", "ciudadano_vinculado"},
        }
        for modelo, campos in esperado.items():
            registrado = admin.site._registry[modelo]
            self.assertTrue(
                campos <= set(registrado.raw_id_fields),
                f"{modelo.__name__}: faltan en raw_id_fields {campos - set(registrado.raw_id_fields)}",
            )
