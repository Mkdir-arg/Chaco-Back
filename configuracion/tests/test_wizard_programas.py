"""El wizard de alta de programas, que crea `Programa` sin un solo test (TST-02).

Medido el 04-oct-2026: `configuracion/views/programas.py` al **22 %**, 3 tests para
las 30 rutas de la app y el único que tocaba rutas `configuracion:` miraba el menú
(`users/tests/test_menu_rbac.py`). El wizard **crea un Programa** —la fila de la que
cuelga todo el RBAC de alcance por programa— y `programa_cambiar_estado` lo activa.

Es además el piso que SEC-07 necesita para moverse sin romper nada.

**Dos desvíos de la ficha, los dos code-first.** (1) La ficha pedía
`test_sin_config_administrar_los_ocho_pasos_dan_403`: la capacidad que gobierna el
wizard es `programa.configurar`, no `config.administrar` (`config.administrar` es la
de Geografía y Secretarías). (2) Y el contrato del backoffice sin capacidad es
**redirect** al listado, no 403 —`@requiere(..., redirect_to="configuracion:programas")`,
el 403 queda para AJAX—, igual que ya se registró al cerrar RED-73. Los tests van
contra lo que el código hace.
"""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from configuracion.tests.test_configuracion_ola5 import usuario_con
from core.models import Secretaria, Subsecretaria
from programas.models import Programa

#: Los cuatro pasos del alta más los cuatro de la edición.
PASOS_ALTA = (
    "configuracion:programa_wizard_paso1",
    "configuracion:programa_wizard_paso2",
    "configuracion:programa_wizard_paso3",
    "configuracion:programa_wizard_paso4",
)
PASOS_EDICION = (
    "configuracion:programa_editar_paso1",
    "configuracion:programa_editar_paso2",
    "configuracion:programa_editar_paso3",
    "configuracion:programa_editar_paso4",
)


class WizardDeProgramaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.secretaria = Secretaria.objects.create(nombre="Secretaría de Desarrollo")
        cls.subsecretaria = Subsecretaria.objects.create(nombre="Subsecretaría de Niñez", secretaria=cls.secretaria)

    def setUp(self):
        self.operador = usuario_con("programa.configurar", username="cfg-wizard")
        self.client.force_login(self.operador)

    # ---------------------------------------------------------------- andamios

    def _paso1(self, **extra):
        return {
            "nombre": "Programa nuevo",
            "codigo": "PROG-NUEVO",
            "descripcion": "Descripción breve",
            "secretaria": self.secretaria.pk,
            "subsecretaria": self.subsecretaria.pk,
            **extra,
        }

    def _completar_los_cuatro_pasos(self):
        self.client.post(reverse("configuracion:programa_wizard_paso1"), self._paso1())
        self.client.post(
            reverse("configuracion:programa_wizard_paso2"),
            {"naturaleza": Programa.Naturaleza.PERSISTENTE},
        )
        self.client.post(
            reverse("configuracion:programa_wizard_paso3"),
            {"cupo_maximo": "50", "tiene_lista_espera": "on"},
        )
        return self.client.post(
            reverse("configuracion:programa_wizard_paso4"),
            {"icono": "folder", "color": "#6366f1", "orden": "3"},
        )

    # ------------------------------------------------------------------ casos

    def test_los_cuatro_pasos_crean_el_programa_con_todo(self):
        """El estado vive en la sesión y recién el paso 4 escribe: lo que llega a la
        base tiene que traer los datos de los cuatro pasos, no solo del último."""
        respuesta = self._completar_los_cuatro_pasos()

        self.assertRedirects(respuesta, reverse("configuracion:programas"))
        programa = Programa.objects.get(codigo="PROG-NUEVO")
        self.assertEqual(programa.nombre, "Programa nuevo")
        self.assertEqual(programa.subsecretaria_id, self.subsecretaria.pk)
        self.assertEqual(programa.naturaleza, Programa.Naturaleza.PERSISTENTE)
        self.assertEqual(programa.cupo_maximo, 50)
        self.assertTrue(programa.tiene_lista_espera)
        self.assertEqual(programa.orden, 3)
        self.assertEqual(programa.estado, Programa.Estado.BORRADOR)

    def test_el_programa_nace_en_borrador_y_la_sesion_queda_limpia(self):
        """Nace apagado (hay que activarlo a mano) y el wizard no deja residuos: si
        no se limpiara, el alta siguiente arrancaría con los datos de la anterior."""
        self._completar_los_cuatro_pasos()

        self.assertNotIn("wizard_programa_nuevo", self.client.session)
        self.assertEqual(Programa.objects.get(codigo="PROG-NUEVO").estado, Programa.Estado.BORRADOR)

    def test_entrar_al_paso_3_sin_haber_hecho_el_1_redirige(self):
        """Cada paso exige el anterior: entrar directo por URL vuelve atrás, no
        revienta ni crea un programa a medias."""
        respuesta = self.client.get(reverse("configuracion:programa_wizard_paso3"))

        self.assertRedirects(
            respuesta,
            reverse("configuracion:programa_wizard_paso2"),
            target_status_code=302,  # el paso 2, también vacío, rebota al 1
        )

        respuesta = self.client.get(reverse("configuracion:programa_wizard_paso2"))

        self.assertRedirects(respuesta, reverse("configuracion:programa_wizard_paso1"))

    def test_sin_programa_configurar_los_ocho_pasos_vuelven_al_listado(self):
        """Los cuatro del alta y los cuatro de la edición, con un usuario sin rol."""
        programa = Programa.objects.create(
            codigo="PROG-RBAC", nombre="Programa RBAC", naturaleza=Programa.Naturaleza.PERSISTENTE
        )
        self.client.force_login(usuario_con(username="cfg-sin-rol"))
        listado = reverse("configuracion:programas")

        for nombre in PASOS_ALTA:
            with self.subTest(paso=nombre):
                self.assertRedirects(self.client.get(reverse(nombre)), listado)

        for nombre in PASOS_EDICION:
            with self.subTest(paso=nombre):
                self.assertRedirects(self.client.get(reverse(nombre, args=[programa.pk])), listado)

    def test_un_anonimo_va_al_login_en_los_ocho_pasos(self):
        """El login del backoffice vive en la **raíz** (`users:login` → `/`, RED-78),
        no en `/login/`: lo que se afirma es la URL resuelta más el `?next=`."""
        programa = Programa.objects.create(
            codigo="PROG-ANON", nombre="Programa anónimo", naturaleza=Programa.Naturaleza.PERSISTENTE
        )
        login = reverse(settings.LOGIN_URL)
        self.client.logout()

        for nombre in PASOS_ALTA:
            with self.subTest(paso=nombre):
                destino = self.client.get(reverse(nombre))["Location"]
                self.assertEqual(destino, f"{login}?next={reverse(nombre)}")

        for nombre in PASOS_EDICION:
            with self.subTest(paso=nombre):
                url = reverse(nombre, args=[programa.pk])
                self.assertEqual(self.client.get(url)["Location"], f"{login}?next={url}")

    def test_el_codigo_repetido_no_crea_un_segundo_programa(self):
        Programa.objects.create(codigo="PROG-NUEVO", nombre="Ya existía")

        respuesta = self.client.post(reverse("configuracion:programa_wizard_paso1"), self._paso1())

        self.assertEqual(respuesta.status_code, 200)
        self.assertFormError(respuesta.context["form"], "codigo", "Ya existe un programa con ese código.")
        self.assertEqual(Programa.objects.filter(codigo="PROG-NUEVO").count(), 1)

    def test_la_lista_de_espera_sin_cupo_no_pasa_del_paso_3(self):
        """Regla del paso 3: una lista de espera sin cupo no tiene de qué desbordar."""
        self.client.post(reverse("configuracion:programa_wizard_paso1"), self._paso1())
        self.client.post(
            reverse("configuracion:programa_wizard_paso2"),
            {"naturaleza": Programa.Naturaleza.PERSISTENTE},
        )

        respuesta = self.client.post(reverse("configuracion:programa_wizard_paso3"), {"tiene_lista_espera": "on"})

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(
            "La lista de espera requiere que se configure un cupo máximo.",
            respuesta.context["form"].non_field_errors(),
        )


class CambiarEstadoDePrograma(TestCase):
    """`programa_cambiar_estado`: el botón que enciende y apaga un programa."""

    def setUp(self):
        self.operador = usuario_con("programa.configurar", username="cfg-estado")
        self.client.force_login(self.operador)
        self.listado = reverse("configuracion:programas")

    def _programa(self, **extra):
        return Programa.objects.create(
            codigo=extra.pop("codigo", "PROG-EST"),
            nombre=extra.pop("nombre", "Programa estado"),
            estado=Programa.Estado.BORRADOR,
            **extra,
        )

    def test_activar_un_programa_sin_naturaleza_avisa_y_no_activa(self):
        """Sin naturaleza el programa no sabe qué es: activarlo lo dejaría visible y
        roto. El aviso tiene que llegar **y** el estado quedarse donde estaba."""
        programa = self._programa(naturaleza="")

        respuesta = self.client.post(
            reverse("configuracion:programa_cambiar_estado", args=[programa.pk]),
            {"estado": Programa.Estado.ACTIVO},
            follow=True,
        )

        programa.refresh_from_db()
        self.assertEqual(programa.estado, Programa.Estado.BORRADOR)
        self.assertIn(
            "El programa no puede activarse sin tener la naturaleza configurada. Complete el wizard primero.",
            [str(m) for m in respuesta.context["messages"]],
        )

    def test_activar_un_programa_con_naturaleza_si_lo_activa(self):
        """Control: el freno de arriba es por la naturaleza, no porque nunca active."""
        programa = self._programa(codigo="PROG-OK", naturaleza=Programa.Naturaleza.PERSISTENTE)

        self.client.post(
            reverse("configuracion:programa_cambiar_estado", args=[programa.pk]),
            {"estado": Programa.Estado.ACTIVO},
        )

        programa.refresh_from_db()
        self.assertEqual(programa.estado, Programa.Estado.ACTIVO)

    def test_un_estado_que_no_existe_no_se_guarda(self):
        programa = self._programa(codigo="PROG-RARO", naturaleza=Programa.Naturaleza.PERSISTENTE)

        self.client.post(
            reverse("configuracion:programa_cambiar_estado", args=[programa.pk]),
            {"estado": "INVENTADO"},
        )

        programa.refresh_from_db()
        self.assertEqual(programa.estado, Programa.Estado.BORRADOR)

    def test_por_get_no_cambia_nada(self):
        """Cambiar estado es una escritura: un GET no puede ejecutarla (y sin esto un
        `<img src>` apagaría un programa)."""
        programa = self._programa(codigo="PROG-GET", naturaleza=Programa.Naturaleza.PERSISTENTE)

        respuesta = self.client.get(
            reverse("configuracion:programa_cambiar_estado", args=[programa.pk]),
            {"estado": Programa.Estado.ACTIVO},
        )

        programa.refresh_from_db()
        self.assertRedirects(respuesta, self.listado)
        self.assertEqual(programa.estado, Programa.Estado.BORRADOR)

    def test_sin_capacidad_no_cambia_el_estado(self):
        programa = self._programa(codigo="PROG-RBAC2", naturaleza=Programa.Naturaleza.PERSISTENTE)
        self.client.force_login(usuario_con(username="cfg-estado-sin-rol"))

        respuesta = self.client.post(
            reverse("configuracion:programa_cambiar_estado", args=[programa.pk]),
            {"estado": Programa.Estado.ACTIVO},
        )

        programa.refresh_from_db()
        self.assertRedirects(respuesta, self.listado)
        self.assertEqual(programa.estado, Programa.Estado.BORRADOR)
