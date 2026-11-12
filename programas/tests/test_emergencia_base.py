"""Módulo Emergencia, PR 1: programa, capacidades y configuración (E7).

Qué fija este archivo, regla por regla:

* **RU-6 / RU-7** — las capacidades ``emergencia.*`` se evalúan con alcance sobre el
  programa EMERGENCIA, y el catálogo solo las deja tildar en el programa que corresponde.
  ``emergencia.recibir_kit`` es la excepción a propósito: va en un rol de DISPOSITIVOS
  (hallazgo H3 del plan), porque se evalúa con ``puede_operar_dispositivo``.
* **RU §6 n.° 3, mitad backoffice** — un rol de Becas no abre ninguna URL ``emergencia:*``.
  Es un barrido del URLconf y no una lista escrita a mano: la pantalla que se sume en un
  PR siguiente entra sola. ``UnRolDeOtroProgramaNoAbreEmergenciaTests`` se vio en rojo
  contra la regla invertida antes de quedar verde (el detalle, en su docstring).
* **RU-11** — el ciudadano del portal no llega a ninguna URL del módulo.
* **RN-5.5** — guardar E7 deja ``TrazaConfiguracion`` solo de los campos que cambiaron.
* **RN-4.7** — un ``TipoKit`` se agrega y se desactiva; no se borra.
* **Cambio 104** — el seed crea el programa y la fila del SLA y no pisa lo configurado.
"""

import importlib
from io import StringIO

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core import rbac
from core.tests.historico import estado_historico
from core.tests.test_superficie_publica import rutas_concretas
from programas.forms_emergencia import PREFIJO_KITS
from programas.management.commands.seed_emergencia import (
    PROGRAMA_EMERGENCIA_DEFAULTS,
    asegurar_programa_emergencia,
)
from programas.models import Programa, SLAEmergencia, TipoKit, TrazaConfiguracion
from programas.services import configuracion_emergencia as servicio
from programas.services.emergencia_programa import (
    PROGRAMA_EMERGENCIA_CODIGO,
    programa_emergencia,
    puede_en_programa_emergencia,
)
from users.models import Capacidad, RolMeta

RELEVAR = "emergencia.relevar"
OPERAR = "emergencia.operar"
SUPERVISAR = "emergencia.supervisar"
RECIBIR_KIT = "emergencia.recibir_kit"
LAS_DE_LA_MESA = {RELEVAR, OPERAR, SUPERVISAR}

URL_CONFIGURACION = "/emergencia/config/"


def _permiso(codigo):
    tipo = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo)


def _programa(codigo, nombre):
    return Programa.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre, "tipo": codigo})[0]


def urls_de_emergencia():
    """Toda URL del namespace ``emergencia`` que existe hoy, sacada del URLconf."""
    return [url for nombre, url in rutas_concretas() if nombre.startswith("emergencia:")]


class BaseEmergencia(TestCase):
    """El programa EMERGENCIA sembrado, la caché de proceso limpia y roles por programa."""

    def setUp(self):
        super().setUp()
        # `programas:emergencia` es una clave de proceso: sobrevive al rollback entre tests.
        cache.clear()
        self.addCleanup(cache.clear)
        self.programa, _creado, _sla = asegurar_programa_emergencia()
        self.becas = _programa("BECAS", "Becas")
        self.dispositivos = _programa("DISPOSITIVOS", "Dispositivos")

    def _usuario(self, nombre, capacidades=(), programa=None, categoria=rbac.CATEGORIA_PROGRAMA):
        """Un usuario con un rol de ``programa`` (por defecto EMERGENCIA) que tiene ``capacidades``."""
        rol = Group.objects.create(name=f"Rol {nombre}")
        if categoria == rbac.CATEGORIA_PROGRAMA:
            programa = programa or self.programa
        RolMeta.objects.create(grupo=rol, categoria=categoria, programa=programa, activo=True)
        rol.permissions.add(*[_permiso(codigo) for codigo in capacidades])
        usuario = User.objects.create_user(username=nombre, password="x")
        usuario.groups.add(rol)
        # `rbac` memoiza las capacidades en el objeto: se devuelve uno recién leído.
        return User.objects.get(pk=usuario.pk)


# ---------------------------------------------------------------------------
# Catálogo y alcance
# ---------------------------------------------------------------------------


class CatalogoEmergenciaTests(SimpleTestCase):
    def test_el_catalogo_expone_las_cuatro_capacidades(self):
        self.assertTrue(LAS_DE_LA_MESA | {RECIBIR_KIT} <= set(rbac.codigos_de_capacidad()))

    def test_las_cuatro_son_de_programa(self):
        self.assertTrue(LAS_DE_LA_MESA | {RECIBIR_KIT} <= rbac.codigos_de_programa())

    def test_las_de_la_mesa_se_otorgan_solo_en_un_rol_de_emergencia(self):
        self.assertTrue(LAS_DE_LA_MESA <= rbac.capacidades_de_programa_asignables("EMERGENCIA"))
        for otro in ("DISPOSITIVOS", "BECAS"):
            with self.subTest(programa=otro):
                self.assertEqual(LAS_DE_LA_MESA & rbac.capacidades_de_programa_asignables(otro), set())
                self.assertTrue(LAS_DE_LA_MESA <= rbac.capacidades_fuera_del_programa(otro))

    def test_recibir_kit_se_otorga_en_un_rol_de_dispositivos_y_no_en_uno_de_emergencia(self):
        """Hallazgo H3: se evalúa con ``puede_operar_dispositivo``, que mira roles de DISPOSITIVOS."""
        self.assertIn(RECIBIR_KIT, rbac.capacidades_de_programa_asignables("DISPOSITIVOS"))
        self.assertIn(RECIBIR_KIT, rbac.capacidades_delegables("DISPOSITIVOS"))
        self.assertNotIn(RECIBIR_KIT, rbac.capacidades_de_programa_asignables("EMERGENCIA"))
        self.assertNotIn(RECIBIR_KIT, rbac.capacidades_de_programa_asignables("BECAS"))
        self.assertIn(RECIBIR_KIT, rbac.capacidades_fuera_del_programa("EMERGENCIA"))

    def test_un_rol_de_emergencia_no_recibe_capacidades_de_otros_programas(self):
        asignables = rbac.capacidades_de_programa_asignables("EMERGENCIA")
        self.assertEqual({c for c in asignables if c.startswith(("becas.", "dispositivo.", "inspeccion."))}, set())

    def test_el_arbol_del_abm_de_un_rol_de_emergencia_tiene_la_solapa_emergencia(self):
        tabs = {
            tab["id"]: {m["modulo"] for m in tab["modulos"]}
            for tab in rbac.arbol_por_tabs(solo_programa=True, programa="EMERGENCIA")
        }
        self.assertEqual(tabs["emergencia"], {"emergencia"})
        self.assertNotIn("dispositivos", tabs)
        self.assertNotIn("becas", tabs)

    def test_recibir_kit_va_en_la_solapa_de_dispositivos(self):
        tabs = {
            tab["id"]: {m["modulo"] for m in tab["modulos"]}
            for tab in rbac.arbol_por_tabs(solo_programa=True, programa="DISPOSITIVOS")
        }
        self.assertIn("dispositivos_emergencia", tabs["dispositivos"])
        self.assertNotIn("emergencia", tabs)

    def test_el_codigo_del_programa_es_uno_solo(self):
        self.assertEqual(rbac.CODIGO_PROGRAMA_EMERGENCIA, "EMERGENCIA")
        self.assertEqual(PROGRAMA_EMERGENCIA_CODIGO, rbac.CODIGO_PROGRAMA_EMERGENCIA)


class AlcanceDePrograma(BaseEmergencia):
    def test_programa_emergencia_devuelve_la_fila_sembrada(self):
        self.assertEqual(programa_emergencia().pk, self.programa.pk)

    def test_con_la_capacidad_en_un_rol_de_emergencia_puede(self):
        supervisor = self._usuario("supervisor", [SUPERVISAR])
        self.assertTrue(puede_en_programa_emergencia(supervisor, SUPERVISAR))
        # En un bucle a propósito: `test_rbac_contrato` cuenta como «uso» de una capacidad
        # cualquier literal que llegue a esta función, y estas dos todavía no tienen pantalla.
        for otra in (OPERAR, RELEVAR):
            self.assertFalse(puede_en_programa_emergencia(supervisor, otra))

    def test_la_misma_capacidad_en_un_rol_de_otro_programa_no_alcanza(self):
        """El caso que ya cobró en Dispositivos: «un rol de Becas habilita»."""
        colado = self._usuario("colado", [SUPERVISAR], programa=self.becas)
        self.assertTrue(rbac.puede(colado, SUPERVISAR), "sin alcance la tiene: por eso no se pregunta así")
        self.assertFalse(puede_en_programa_emergencia(colado, SUPERVISAR))

    def test_un_rol_global_con_la_capacidad_si_alcanza(self):
        global_ = self._usuario("global", [SUPERVISAR], categoria=rbac.CATEGORIA_BACKOFFICE)
        self.assertTrue(puede_en_programa_emergencia(global_, SUPERVISAR))

    def test_sin_el_programa_sembrado_nadie_puede_ni_el_superusuario(self):
        root = User.objects.create_superuser("root", "root@example.com", "x")
        SLAEmergencia.objects.all().delete()
        Programa.objects.filter(codigo="EMERGENCIA").delete()
        cache.clear()
        self.assertIsNone(programa_emergencia())
        self.assertFalse(puede_en_programa_emergencia(root, SUPERVISAR))

    def test_anonimo_y_none_no_pueden(self):
        from django.contrib.auth.models import AnonymousUser

        self.assertFalse(puede_en_programa_emergencia(AnonymousUser(), SUPERVISAR))
        self.assertFalse(puede_en_programa_emergencia(None, SUPERVISAR))


class SoloCampoTests(BaseEmergencia):
    """``emergencia.relevar`` es capacidad de la app de campo (``CAPACIDADES_DE_CAMPO``)."""

    def test_relevar_esta_entre_las_capacidades_de_campo(self):
        self.assertIn(RELEVAR, rbac.CAPACIDADES_DE_CAMPO)
        self.assertEqual(rbac.CAPACIDADES_DE_CAMPO, {"becas.campo", "inspeccion.relevar", RELEVAR})

    def test_un_usuario_con_solo_relevar_es_solo_campo(self):
        agente = self._usuario("agente", [RELEVAR])
        self.assertTrue(rbac.es_solo_campo(agente))
        self.assertTrue(rbac.roles_solo_campo(list(agente.groups.all())))

    def test_con_relevar_y_operar_no_es_solo_campo(self):
        mixto = self._usuario("mixto", [RELEVAR, OPERAR])
        self.assertFalse(rbac.es_solo_campo(mixto))
        self.assertFalse(rbac.roles_solo_campo(list(mixto.groups.all())))

    def test_con_solo_operar_no_es_solo_campo(self):
        operador = self._usuario("operador", [OPERAR])
        self.assertFalse(rbac.es_solo_campo(operador))

    def test_el_login_web_rechaza_al_que_solo_releva(self):
        """La misma pregunta que responde el login: quien solo releva no pisa el backoffice."""
        from users.forms.auth import UsuariosAuthenticationForm

        agente = self._usuario("agente", [RELEVAR])
        form = UsuariosAuthenticationForm(None, data={"username": agente.username, "password": "x"})
        self.assertFalse(form.is_valid())
        self.assertEqual([e.code for e in form.non_field_errors().as_data()], ["territorial_mobile_only"])
        operador = self._usuario("operador", [OPERAR])
        self.assertTrue(
            UsuariosAuthenticationForm(None, data={"username": operador.username, "password": "x"}).is_valid()
        )


# ---------------------------------------------------------------------------
# RU §6 n.° 3 (mitad backoffice) y RU-11: quién no abre el módulo
# ---------------------------------------------------------------------------


class UnRolDeOtroProgramaNoAbreEmergenciaTests(BaseEmergencia):
    """Mutación RU §6 n.° 3: un rol de Becas no ve ninguna URL ``emergencia:*``.

    Vistos en rojo contra la regla invertida, de dos maneras: con
    ``EmergenciaPermissionMixin`` evaluando ``rbac.puede`` **sin alcance** falla el del rol
    de Becas con la capacidad tildada (200 en el GET), que es el caso que ya cobró en
    Dispositivos; con el mixin **sin chequeo** fallan los cuatro barridos y los de E7.
    """

    def _no_abre(self, usuario):
        self.client.force_login(usuario)
        urls = urls_de_emergencia()
        self.assertIn(URL_CONFIGURACION, urls, "el barrido no encontró las URLs del módulo")
        for url in urls:
            with self.subTest(url=url, metodo="GET"):
                self.assertIn(self.client.get(url).status_code, (302, 403))
            with self.subTest(url=url, metodo="POST"):
                self.assertIn(self.client.post(url, {}).status_code, (302, 403))

    def test_el_territorial_de_becas_no_abre_ninguna_url(self):
        self._no_abre(self._usuario("territorial", ["becas.campo"], programa=self.becas))

    def test_el_coordinador_de_becas_no_abre_ninguna_url(self):
        becas_de_gestion = [c for c in rbac.capacidades_de_programa_asignables("BECAS") if c.startswith("becas.")]
        self._no_abre(self._usuario("coordinador", becas_de_gestion, programa=self.becas))

    def test_un_rol_de_becas_con_la_capacidad_de_emergencia_tildada_tampoco(self):
        """El catálogo no deja tildarla (SEC-06), pero si la fila está igual, el alcance la frena."""
        self._no_abre(self._usuario("colado", [SUPERVISAR, OPERAR], programa=self.becas))

    def test_un_rol_de_dispositivos_con_recibir_kit_tampoco(self):
        self._no_abre(self._usuario("guardia", [RECIBIR_KIT, "dispositivo.admitir"], programa=self.dispositivos))

    def test_la_configuracion_no_se_guarda_para_quien_no_abre(self):
        colado = self._usuario("colado", [SUPERVISAR], programa=self.becas)
        self.client.force_login(colado)
        self.client.post(URL_CONFIGURACION, {"objetivo_tomar_min": 99})
        self.assertEqual(servicio.sla_vigente().objetivo_tomar_min, 15)
        self.assertFalse(TrazaConfiguracion.objects.exists())


class CiudadanoDelPortalTests(BaseEmergencia):
    """RU-11: lo frena ``PortalCiudadanoMiddleware`` antes de la vista, tenga el rol que tenga."""

    def test_un_ciudadano_no_llega_a_ninguna_url_del_modulo(self):
        ciudadano = self._usuario("ciudadano", [SUPERVISAR])
        ciudadano.groups.add(Group.objects.get_or_create(name=rbac.GRUPO_CIUDADANO_PORTAL)[0])
        self.client.force_login(User.objects.get(pk=ciudadano.pk))
        urls = urls_de_emergencia()
        self.assertTrue(urls)
        for url in urls:
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertRedirects(respuesta, reverse("portal:home"), fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# E7 · Configuración
# ---------------------------------------------------------------------------


class BaseE7(BaseEmergencia):
    def setUp(self):
        super().setUp()
        self.supervisor = self._usuario("supervisor", [SUPERVISAR])
        self.url = reverse("emergencia:configuracion")

    def _datos(self, kits_nuevos=(), **cambios):
        """El POST que mandaría el navegador: lo que la pantalla muestra, más ``cambios``.

        Las claves de ``cambios`` son nombres de campo del SLA o ``kits-<n>-<campo>``.
        """
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        form, kits = respuesta.context["form"], respuesta.context["kits"]
        datos = {nombre: form[nombre].value() for nombre in form.fields}
        for campo in kits.management_form:
            datos[campo.html_name] = campo.value()
        for fila in kits.forms:
            for nombre in fila.fields:
                valor = fila[nombre].value()
                if valor is True:
                    datos[fila[nombre].html_name] = "on"
                elif valor is not False and valor is not None:
                    datos[fila[nombre].html_name] = valor
        datos.update(cambios)
        return {clave: valor for clave, valor in datos.items() if valor is not None}

    def _fila_nueva(self, **campos):
        """Las claves de la fila vacía del formset (la de «Agregar ítem»)."""
        indice = TipoKit.objects.count()
        return {f"{PREFIJO_KITS}-{indice}-{campo}": valor for campo, valor in campos.items()}


class AccesoE7Tests(BaseE7):
    def test_sin_login_redirige_al_login(self):
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, f"{reverse('users:login')}?next={self.url}")
        self.assertEqual(self.client.post(self.url, {}).status_code, 302)

    def test_la_url_es_la_del_namespace_emergencia(self):
        self.assertEqual(self.url, URL_CONFIGURACION)

    def test_sin_supervisar_rechaza(self):
        self.client.force_login(self._usuario("sin_rol"))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {}).status_code, 403)

    def test_con_operar_solo_tambien_rechaza(self):
        self.client.force_login(self._usuario("operador", [OPERAR]))
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, {"objetivo_tomar_min": 99}).status_code, 403)
        self.assertEqual(servicio.sla_vigente().objetivo_tomar_min, 15)

    def test_con_supervisar_abre_con_los_valores_de_fabrica(self):
        self.client.force_login(self.supervisor)
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.status_code, 200)
        self.assertTemplateUsed(respuesta, "programas/emergencia/configuracion.html")
        form = respuesta.context["form"]
        self.assertEqual(
            [form[campo].value() for campo in servicio.CAMPOS_SLA],
            ["Emergencia", 15, 30, 120, 60, 720, 60, 80],
        )
        self.assertContains(respuesta, "Catálogo de kits")
        self.assertContains(respuesta, "csrfmiddlewaretoken")

    def test_el_superusuario_abre(self):
        self.client.force_login(User.objects.create_superuser("root", "root@example.com", "x"))
        self.assertEqual(self.client.get(self.url).status_code, 200)


class SidebarTests(BaseE7):
    ENLACE = 'href="/emergencia/config/"'

    def test_el_supervisor_ve_la_entrada_emergencia(self):
        self.client.force_login(self.supervisor)
        self.assertContains(self.client.get(self.url), self.ENLACE)

    def test_sin_capacidad_de_emergencia_no_se_ve(self):
        self.client.force_login(self._usuario("becario", ["becas.segmento.ver"], programa=self.becas))
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self.ENLACE)

    def test_la_entrada_no_suma_consultas_a_la_pagina(self):
        """El sidebar se dibuja en todas las pantallas: la entrada sale del cache de capacidades."""
        from django.template import Context, Template

        usuario = self._usuario("becario", ["becas.segmento.ver"], programa=self.becas)
        rbac.puede(usuario, SUPERVISAR)  # calienta el cache por request, como cualquier otro ítem
        plantilla = Template('{% load rbac %}{% if u|puede:"emergencia.supervisar" %}x{% endif %}')
        with self.assertNumQueries(0):
            self.assertEqual(plantilla.render(Context({"u": usuario})), "")

    def test_con_operar_solo_no_se_ve_la_configuracion(self):
        """E7 es de quien supervisa: al operador se le ofrece la bandeja, no un link a un 403."""
        self.client.force_login(self._usuario("operador", [OPERAR]))
        respuesta = self.client.get(reverse("core:inicio"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, self.ENLACE)
        self.assertContains(respuesta, 'href="/emergencia/casos/"')


class GuardarSLATests(BaseE7):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.supervisor)

    def test_guardar_cambia_la_fila_y_traza_solo_lo_que_cambio(self):
        respuesta = self.client.post(self.url, self._datos(vigencia_derivacion_min=480, objetivo_derivar_min=45))

        self.assertRedirects(respuesta, self.url)
        sla = SLAEmergencia.objects.get()
        self.assertEqual((sla.vigencia_derivacion_min, sla.objetivo_derivar_min), (480, 45))
        self.assertEqual((sla.objetivo_tomar_min, sla.objetivo_aceptar_min, sla.objetivo_alojar_min), (15, 120, 60))
        trazas = {
            t.campo: (t.valor_anterior, t.valor_nuevo, t.usuario_id, t.objeto, t.objeto_id, t.programa_id)
            for t in TrazaConfiguracion.objects.all()
        }
        esperado = (self.supervisor.pk, TrazaConfiguracion.Objeto.SLA, sla.pk, self.programa.pk)
        self.assertEqual(
            trazas,
            {
                "vigencia_derivacion_min": ("720", "480", *esperado),
                "objetivo_derivar_min": ("30", "45", *esperado),
            },
        )

    def test_guardar_sin_cambios_no_deja_traza(self):
        respuesta = self.client.post(self.url, self._datos())
        self.assertRedirects(respuesta, self.url)
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_cambiar_el_nombre_del_evento_deja_su_traza(self):
        self.client.post(self.url, self._datos(nombre_evento="Inundación del Río Negro"))
        self.assertEqual(SLAEmergencia.objects.get().nombre_evento, "Inundación del Río Negro")
        traza = TrazaConfiguracion.objects.get()
        self.assertEqual((traza.campo, traza.valor_anterior), ("nombre_evento", "Emergencia"))

    def test_los_valores_fuera_de_rango_se_rechazan_y_no_se_guarda_nada(self):
        casos = {
            "vigencia_derivacion_min": [29, 0],
            "umbral_por_vencer_pct": [49, 96],
            "objetivo_tomar_min": [0],
            "objetivo_derivar_min": [0],
            "objetivo_aceptar_min": [0],
            "objetivo_alojar_min": [0],
            "sin_avance_min": [-1],
        }
        for campo, valores in casos.items():
            for valor in valores:
                with self.subTest(campo=campo, valor=valor):
                    # Otro campo válido viaja en el mismo POST: tampoco se tiene que guardar.
                    datos = self._datos(nombre_evento="No se guarda", **{campo: valor})
                    respuesta = self.client.post(self.url, datos)
                    self.assertEqual(respuesta.status_code, 400)
                    self.assertTrue(respuesta.context["form"].errors.get(campo))
                    sla = SLAEmergencia.objects.get()
                    self.assertEqual(sla.nombre_evento, "Emergencia")
                    self.assertEqual(getattr(sla, campo), SLAEmergencia._meta.get_field(campo).default)
                    self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_los_bordes_validos_se_aceptan(self):
        datos = self._datos(
            vigencia_derivacion_min=30, umbral_por_vencer_pct=50, sin_avance_min=0, objetivo_tomar_min=1
        )
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        datos = self._datos(umbral_por_vencer_pct=95)
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        sla = SLAEmergencia.objects.get()
        self.assertEqual(
            (sla.vigencia_derivacion_min, sla.umbral_por_vencer_pct, sla.sin_avance_min, sla.objetivo_tomar_min),
            (30, 95, 0, 1),
        )


class CatalogoDeKitsE7Tests(BaseE7):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.supervisor)

    def test_se_agrega_un_item(self):
        datos = self._datos(**self._fila_nueva(nombre="Agua 6 l", unidad="bidón", orden=2))
        self.assertRedirects(self.client.post(self.url, datos), self.url)

        tipo = TipoKit.objects.get()
        self.assertEqual((tipo.nombre, tipo.unidad, tipo.orden, tipo.activo), ("Agua 6 l", "bidón", 2, True))
        traza = TrazaConfiguracion.objects.get()
        self.assertEqual(
            (traza.objeto, traza.objeto_id, traza.campo, traza.valor_nuevo, traza.usuario_id),
            (TrazaConfiguracion.Objeto.TIPO_KIT, tipo.pk, servicio.CAMPO_ALTA, "Agua 6 l (bidón)", self.supervisor.pk),
        )

    def test_la_fila_vacia_no_agrega_nada(self):
        self.assertRedirects(self.client.post(self.url, self._datos()), self.url)
        self.assertFalse(TipoKit.objects.exists())

    def test_un_item_sin_unidad_se_rechaza(self):
        respuesta = self.client.post(self.url, self._datos(**self._fila_nueva(nombre="Colchón")))
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(TipoKit.objects.exists())

    def test_se_desactiva_y_no_se_borra(self):
        tipo = TipoKit.objects.create(nombre="Kit de higiene", unidad="kit")
        datos = self._datos()
        self.assertEqual(datos.pop(f"{PREFIJO_KITS}-0-activo"), "on")
        # Un POST armado a mano que además pide borrar la fila: el formset no tiene borrado.
        datos[f"{PREFIJO_KITS}-0-DELETE"] = "on"

        self.assertRedirects(self.client.post(self.url, datos), self.url)

        tipo.refresh_from_db()
        self.assertFalse(tipo.activo)
        self.assertEqual(TipoKit.objects.count(), 1)
        traza = TrazaConfiguracion.objects.get()
        self.assertEqual((traza.campo, traza.valor_anterior, traza.valor_nuevo), ("activo", "Sí", "No"))
        self.assertEqual(list(servicio.catalogo_kits(solo_activos=True)), [])
        self.assertEqual(list(servicio.catalogo_kits()), [tipo])

    def test_la_pantalla_no_ofrece_borrar(self):
        TipoKit.objects.create(nombre="Kit de higiene", unidad="kit")
        respuesta = self.client.get(self.url)
        self.assertFalse(respuesta.context["kits"].can_delete)
        self.assertNotContains(respuesta, "-DELETE")

    def test_se_vuelve_a_activar(self):
        tipo = TipoKit.objects.create(nombre="Frazada", unidad="unidad", activo=False)
        datos = self._datos(**{f"{PREFIJO_KITS}-0-activo": "on"})
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        tipo.refresh_from_db()
        self.assertTrue(tipo.activo)

    def test_se_edita_nombre_y_unidad_con_una_traza_por_campo(self):
        tipo = TipoKit.objects.create(nombre="Agua", unidad="unidad")
        datos = self._datos(**{f"{PREFIJO_KITS}-0-nombre": "Agua 6 l", f"{PREFIJO_KITS}-0-unidad": "bidón"})
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        tipo.refresh_from_db()
        self.assertEqual((tipo.nombre, tipo.unidad), ("Agua 6 l", "bidón"))
        self.assertEqual(
            {t.campo: (t.valor_anterior, t.valor_nuevo) for t in TrazaConfiguracion.objects.all()},
            {"nombre": ("Agua", "Agua 6 l"), "unidad": ("unidad", "bidón")},
        )

    def test_un_nombre_duplicado_se_rechaza(self):
        TipoKit.objects.create(nombre="Agua 6 l", unidad="bidón")
        for nombre in ("Agua 6 l", "agua 6 L", "  Agua   6 l "):
            with self.subTest(nombre=nombre):
                datos = self._datos(**self._fila_nueva(nombre=nombre, unidad="botella"))
                respuesta = self.client.post(self.url, datos)
                self.assertEqual(respuesta.status_code, 400)
                self.assertContains(respuesta, servicio.MENSAJE_NOMBRE_DUPLICADO, status_code=400)
                self.assertEqual(TipoKit.objects.count(), 1)
                self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_renombrar_un_item_al_nombre_de_otro_se_rechaza(self):
        TipoKit.objects.create(nombre="Agua", unidad="bidón", orden=1)
        colchon = TipoKit.objects.create(nombre="Colchón", unidad="unidad", orden=2)
        respuesta = self.client.post(self.url, self._datos(**{f"{PREFIJO_KITS}-1-nombre": "agua"}))
        self.assertEqual(respuesta.status_code, 400)
        colchon.refresh_from_db()
        self.assertEqual(colchon.nombre, "Colchón")

    def test_varios_items_se_editan_en_un_solo_guardado(self):
        """Con `zeal` prendido en la suite, un ``get`` por fila acá es un ``NPlusOneError``."""
        for orden, nombre in enumerate(("Agua", "Colchón", "Frazada"), start=1):
            TipoKit.objects.create(nombre=nombre, unidad="unidad", orden=orden)
        datos = self._datos(**{f"{PREFIJO_KITS}-{i}-unidad": "pieza" for i in range(3)})
        self.assertRedirects(self.client.post(self.url, datos), self.url)
        self.assertEqual(set(TipoKit.objects.values_list("unidad", flat=True)), {"pieza"})
        self.assertEqual(TrazaConfiguracion.objects.filter(campo="unidad").count(), 3)

    def test_un_id_que_no_es_del_catalogo_se_rechaza(self):
        TipoKit.objects.create(nombre="Agua", unidad="bidón")
        for valor in ("999999", "abc"):
            with self.subTest(id=valor):
                datos = self._datos(**{f"{PREFIJO_KITS}-0-id": valor, f"{PREFIJO_KITS}-0-nombre": "Otro"})
                self.assertEqual(self.client.post(self.url, datos).status_code, 400)
                self.assertEqual(TipoKit.objects.get().nombre, "Agua")

    def test_un_error_en_el_catalogo_no_deja_guardado_el_sla(self):
        """E7 es una sola transacción: o entra todo, o no entra nada."""
        datos = self._datos(objetivo_tomar_min=20, **self._fila_nueva(nombre="Sin unidad"))
        self.assertEqual(self.client.post(self.url, datos).status_code, 400)
        self.assertEqual(SLAEmergencia.objects.get().objetivo_tomar_min, 15)
        self.assertFalse(TrazaConfiguracion.objects.exists())


class ServicioConfiguracionTests(BaseEmergencia):
    """El servicio exige la capacidad y valida por su cuenta: la vista no es la única puerta."""

    def setUp(self):
        super().setUp()
        self.supervisor = self._usuario("supervisor", [SUPERVISAR])
        self.operador = self._usuario("operador", [OPERAR])

    def test_sla_vigente_crea_la_fila_con_los_valores_de_fabrica(self):
        SLAEmergencia.objects.all().delete()
        sla = servicio.sla_vigente()
        self.assertEqual(
            [getattr(sla, campo) for campo in servicio.CAMPOS_SLA], ["Emergencia", 15, 30, 120, 60, 720, 60, 80]
        )
        self.assertEqual(servicio.sla_vigente().pk, sla.pk)
        self.assertEqual(SLAEmergencia.objects.count(), 1)

    def test_sla_vigente_sin_programa_lo_dice(self):
        SLAEmergencia.objects.all().delete()
        RolMeta.objects.filter(programa=self.programa).delete()
        Programa.objects.filter(codigo="EMERGENCIA").delete()
        cache.clear()
        with self.assertRaises(servicio.ProgramaEmergenciaInexistente):
            servicio.sla_vigente()

    def test_guardar_sla_sin_supervisar_no_guarda(self):
        colado = self._usuario("colado", [SUPERVISAR], programa=self.becas)
        for usuario in (self.operador, colado, None):
            with self.subTest(usuario=usuario):
                with self.assertRaises(PermissionDenied):
                    servicio.guardar_sla(usuario, objetivo_tomar_min=5)
        self.assertEqual(servicio.sla_vigente().objetivo_tomar_min, 15)
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_guardar_sla_valida_los_rangos(self):
        invalidos = (
            {"vigencia_derivacion_min": 29},
            {"umbral_por_vencer_pct": 49},
            {"umbral_por_vencer_pct": 96},
            {"objetivo_alojar_min": 0},
        )
        for campos in invalidos:
            with self.subTest(campos=campos):
                with self.assertRaises(ValidationError):
                    servicio.guardar_sla(self.supervisor, **campos)
        sla = servicio.sla_vigente()
        self.assertEqual(
            (sla.vigencia_derivacion_min, sla.umbral_por_vencer_pct, sla.objetivo_alojar_min), (720, 80, 60)
        )
        self.assertFalse(TrazaConfiguracion.objects.exists())

    def test_guardar_sla_no_acepta_campos_que_no_son_del_sla(self):
        with self.assertRaises(TypeError):
            servicio.guardar_sla(self.supervisor, programa_id=999)

    def test_dos_guardados_seguidos_dejan_las_dos_trazas(self):
        servicio.guardar_sla(self.supervisor, objetivo_derivar_min=40)
        otro = self._usuario("otra_supervisora", [SUPERVISAR])
        servicio.guardar_sla(otro, objetivo_derivar_min=50)
        self.assertEqual(
            [(t.usuario_id, t.valor_anterior, t.valor_nuevo) for t in TrazaConfiguracion.objects.all()],
            [(self.supervisor.pk, "30", "40"), (otro.pk, "40", "50")],
        )

    def test_el_catalogo_exige_supervisar(self):
        tipo = TipoKit.objects.create(nombre="Kit", unidad="kit")
        with self.assertRaises(PermissionDenied):
            servicio.crear_tipo_kit(self.operador, nombre="Agua", unidad="bidón")
        with self.assertRaises(PermissionDenied):
            servicio.editar_tipo_kit(self.operador, tipo, nombre="Otro")
        with self.assertRaises(PermissionDenied):
            servicio.cambiar_estado_tipo_kit(self.operador, tipo, False)
        tipo.refresh_from_db()
        self.assertEqual((TipoKit.objects.count(), tipo.nombre, tipo.activo), (1, "Kit", True))

    def test_crear_y_cambiar_estado_dejan_traza(self):
        tipo = servicio.crear_tipo_kit(self.supervisor, nombre="  Agua   6 l ", unidad=" bidón ")
        self.assertEqual((tipo.nombre, tipo.unidad), ("Agua 6 l", "bidón"))
        servicio.cambiar_estado_tipo_kit(self.supervisor, tipo, False)
        servicio.cambiar_estado_tipo_kit(self.supervisor, tipo, False)  # ya estaba: sin traza
        self.assertEqual(
            [(t.campo, t.valor_anterior, t.valor_nuevo) for t in TrazaConfiguracion.objects.all()],
            [(servicio.CAMPO_ALTA, "", "Agua 6 l (bidón)"), ("activo", "Sí", "No")],
        )

    def test_el_servicio_rechaza_el_nombre_duplicado(self):
        servicio.crear_tipo_kit(self.supervisor, nombre="Agua", unidad="bidón")
        with self.assertRaises(ValidationError):
            servicio.crear_tipo_kit(self.supervisor, nombre="AGUA", unidad="botella")
        self.assertEqual(TipoKit.objects.count(), 1)

    def test_guardar_configuracion_es_todo_o_nada(self):
        servicio.crear_tipo_kit(self.supervisor, nombre="Agua", unidad="bidón")
        TrazaConfiguracion.objects.all()._raw_delete(TrazaConfiguracion.objects.db)
        with self.assertRaises(ValidationError):
            servicio.guardar_configuracion(
                self.supervisor,
                sla={"objetivo_tomar_min": 20},
                kits=[(None, {"nombre": "agua", "unidad": "botella", "orden": 0, "activo": True})],
            )
        self.assertEqual(servicio.sla_vigente().objetivo_tomar_min, 15)
        self.assertFalse(TrazaConfiguracion.objects.exists())


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------


class ModelosTests(BaseEmergencia):
    def test_str_del_sla(self):
        sla = servicio.sla_vigente()
        self.assertEqual(str(sla), "SLA de Emergencia")
        sla.nombre_evento = "Inundación"
        self.assertEqual(str(sla), "SLA de Inundación")

    def test_una_sola_fila_de_sla_por_programa(self):
        from django.db import IntegrityError, transaction

        servicio.sla_vigente()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SLAEmergencia.objects.create(programa=self.programa)

    def test_str_del_tipo_de_kit(self):
        self.assertEqual(str(TipoKit(nombre="Agua 6 l", unidad="bidón")), "Agua 6 l (bidón)")

    def test_el_tipo_de_kit_no_se_borra(self):
        tipo = TipoKit.objects.create(nombre="Frazada", unidad="unidad")
        with self.assertRaises(ValidationError):
            tipo.delete()
        self.assertTrue(TipoKit.objects.filter(pk=tipo.pk).exists())

    def test_el_catalogo_se_ordena_por_orden_y_nombre(self):
        TipoKit.objects.create(nombre="Zapatillas", unidad="par", orden=1)
        TipoKit.objects.create(nombre="Agua", unidad="bidón", orden=2)
        TipoKit.objects.create(nombre="Abrigo", unidad="unidad", orden=2)
        self.assertEqual([t.nombre for t in TipoKit.objects.all()], ["Zapatillas", "Abrigo", "Agua"])

    def _traza(self):
        return TrazaConfiguracion.objects.create(
            programa=self.programa,
            objeto=TrazaConfiguracion.Objeto.SLA,
            campo="objetivo_tomar_min",
            valor_anterior="15",
            valor_nuevo="20",
        )

    def test_str_de_la_traza(self):
        self.assertEqual(str(self._traza()), "SLA · objetivo_tomar_min: 15 → 20")
        alta = TrazaConfiguracion(objeto=TrazaConfiguracion.Objeto.TIPO_KIT, campo="alta", valor_nuevo="Agua (bidón)")
        self.assertEqual(str(alta), "Tipo de kit · alta: — → Agua (bidón)")

    def test_la_traza_es_inmutable(self):
        traza = self._traza()
        traza.valor_nuevo = "99"
        with self.assertRaises(ValidationError):
            traza.save()
        with self.assertRaises(ValidationError):
            traza.delete()
        with self.assertRaises(ValidationError):
            TrazaConfiguracion.objects.filter(pk=traza.pk).update(valor_nuevo="99")
        with self.assertRaises(ValidationError):
            TrazaConfiguracion.objects.all().delete()
        with self.assertRaises(ValidationError):
            TrazaConfiguracion.objects.bulk_update([traza], ["valor_nuevo"])
        self.assertEqual(TrazaConfiguracion.objects.get(pk=traza.pk).valor_nuevo, "20")


# ---------------------------------------------------------------------------
# Seed y migraciones
# ---------------------------------------------------------------------------


def _sin_programa_emergencia():
    """Deja la base sin el programa: con las migraciones reales, ``programas.0117`` ya lo creó."""
    SLAEmergencia.objects.all().delete()
    Programa.objects.filter(codigo="EMERGENCIA").delete()
    cache.clear()


def _correr(comando):
    salida = StringIO()
    call_command(comando, stdout=salida)
    return salida.getvalue()


class SeedEmergenciaTests(TestCase):
    def setUp(self):
        _sin_programa_emergencia()
        self.addCleanup(cache.clear)

    def test_crea_el_programa_y_la_fila_del_sla(self):
        salida = _correr("seed_emergencia")

        programa = Programa.objects.get(codigo="EMERGENCIA")
        for campo, valor in PROGRAMA_EMERGENCIA_DEFAULTS.items():
            self.assertEqual(getattr(programa, campo), valor, campo)
        sla = SLAEmergencia.objects.get(programa=programa)
        self.assertEqual(
            [getattr(sla, campo) for campo in servicio.CAMPOS_SLA], ["Emergencia", 15, 30, 120, 60, 720, 60, 80]
        )
        self.assertIn("✓", salida)

    def test_dos_corridas_dejan_una_sola_fila(self):
        _correr("seed_emergencia")
        salida = _correr("seed_emergencia")

        self.assertEqual(Programa.objects.filter(codigo="EMERGENCIA").count(), 1)
        self.assertEqual(SLAEmergencia.objects.count(), 1)
        self.assertNotIn("✓", salida)

    def test_no_pisa_lo_configurado(self):
        _correr("seed_emergencia")
        Programa.objects.filter(codigo="EMERGENCIA").update(
            nombre="Emergencia hídrica", estado=Programa.Estado.SUSPENDIDO, color="#000000", orden=7
        )
        SLAEmergencia.objects.update(nombre_evento="Inundación", objetivo_tomar_min=5, vigencia_derivacion_min=480)

        _correr("seed_emergencia")
        _correr("crear_programas")

        programa = Programa.objects.get(codigo="EMERGENCIA")
        self.assertEqual(
            (programa.nombre, programa.estado, programa.color, programa.orden),
            ("Emergencia hídrica", Programa.Estado.SUSPENDIDO, "#000000", 7),
        )
        sla = SLAEmergencia.objects.get()
        self.assertEqual(
            (sla.nombre_evento, sla.objetivo_tomar_min, sla.vigencia_derivacion_min), ("Inundación", 5, 480)
        )

    def test_crear_programas_tambien_lo_crea(self):
        _correr("crear_programas")
        _correr("crear_programas")
        self.assertEqual(Programa.objects.filter(codigo="EMERGENCIA").count(), 1)
        self.assertEqual(SLAEmergencia.objects.count(), 1)

    def test_si_el_nombre_ya_es_de_otro_programa_frena(self):
        Programa.objects.create(codigo="OTRO", nombre="Emergencia")
        with self.assertRaises(CommandError):
            _correr("seed_emergencia")
        self.assertFalse(Programa.objects.filter(codigo="EMERGENCIA").exists())

    def test_no_siembra_roles(self):
        antes = Group.objects.count()
        _correr("seed_emergencia")
        self.assertEqual(Group.objects.count(), antes)
        self.assertFalse(RolMeta.objects.filter(programa__codigo="EMERGENCIA").exists())


class MigracionProgramaEmergenciaTests(TestCase):
    """``programas.0117``: crea el programa y, al revertir, lo borra solo si está vacío."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migracion = importlib.import_module("programas.migrations.0117_programa_emergencia")
        # RED-17: los modelos de entonces, no los de hoy.
        cls.apps_de_entonces = estado_historico("programas", "0117_programa_emergencia")

    def setUp(self):
        _sin_programa_emergencia()
        self.addCleanup(cache.clear)

    def test_los_literales_son_los_del_seed(self):
        self.assertEqual(self.migracion.CODIGO, PROGRAMA_EMERGENCIA_CODIGO)
        # `str()` de un TextChoices es su valor: la migración escribe los mismos literales.
        self.assertEqual(self.migracion.DATOS, {campo: valor for campo, valor in PROGRAMA_EMERGENCIA_DEFAULTS.items()})

    def test_crea_el_programa_y_es_idempotente(self):
        self.migracion.crear_programa(self.apps_de_entonces, None)
        self.migracion.crear_programa(self.apps_de_entonces, None)

        programa = Programa.objects.get(codigo="EMERGENCIA")
        self.assertEqual((programa.nombre, programa.estado, programa.tipo), ("Emergencia", "ACTIVO", "EMERGENCIA"))

    def test_no_toca_un_programa_que_ya_existe(self):
        Programa.objects.create(codigo="EMERGENCIA", nombre="Mesa de crisis", estado=Programa.Estado.BORRADOR)
        self.migracion.crear_programa(self.apps_de_entonces, None)
        programa = Programa.objects.get(codigo="EMERGENCIA")
        self.assertEqual((programa.nombre, programa.estado), ("Mesa de crisis", Programa.Estado.BORRADOR))

    def test_frena_si_el_nombre_es_de_otro_programa(self):
        Programa.objects.create(codigo="OTRO", nombre="Emergencia")
        with self.assertRaises(RuntimeError):
            self.migracion.crear_programa(self.apps_de_entonces, None)

    def test_la_reversa_borra_el_programa_vacio_con_su_sla(self):
        self.migracion.crear_programa(self.apps_de_entonces, None)
        SLAEmergencia.objects.create(programa=Programa.objects.get(codigo="EMERGENCIA"))

        self.migracion.borrar_programa_si_esta_vacio(self.apps_de_entonces, None)

        self.assertFalse(Programa.objects.filter(codigo="EMERGENCIA").exists())
        self.assertFalse(SLAEmergencia.objects.exists())

    def test_la_reversa_no_borra_un_programa_con_roles(self):
        self.migracion.crear_programa(self.apps_de_entonces, None)
        programa = Programa.objects.get(codigo="EMERGENCIA")
        rol = Group.objects.create(name="Emergencia — Operador de mesa")
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=programa, activo=True)

        with self.assertLogs("programas.migrations.0117_programa_emergencia", level="WARNING"):
            self.migracion.borrar_programa_si_esta_vacio(self.apps_de_entonces, None)

        self.assertTrue(Programa.objects.filter(codigo="EMERGENCIA").exists())

    def test_la_reversa_no_borra_un_programa_con_trazas(self):
        self.migracion.crear_programa(self.apps_de_entonces, None)
        programa = Programa.objects.get(codigo="EMERGENCIA")
        SLAEmergencia.objects.create(programa=programa)
        TrazaConfiguracion.objects.create(programa=programa, objeto="SLA", campo="objetivo_tomar_min")

        with self.assertLogs("programas.migrations.0117_programa_emergencia", level="WARNING"):
            self.migracion.borrar_programa_si_esta_vacio(self.apps_de_entonces, None)

        self.assertTrue(Programa.objects.filter(codigo="EMERGENCIA").exists())
        self.assertTrue(SLAEmergencia.objects.exists())

    def test_la_reversa_sin_programa_no_hace_nada(self):
        self.migracion.borrar_programa_si_esta_vacio(self.apps_de_entonces, None)
        self.assertFalse(Programa.objects.filter(codigo="EMERGENCIA").exists())


class MigracionCapacidadesEmergenciaTests(TestCase):
    """``users.0047``: declara las cuatro capacidades y le da tres al Administrador."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migracion = importlib.import_module("users.migrations.0047_capacidades_emergencia")
        cls.apps_de_entonces = estado_historico("users", "0047_capacidades_emergencia", al_final=True)

    def _administrador(self, *codenames):
        grupo = Group.objects.create(name=rbac.ROL_ADMINISTRADOR)
        RolMeta.objects.create(
            grupo=grupo,
            categoria=rbac.CATEGORIA_BACKOFFICE,
            protegido=True,
            activo=True,
            clave=self.migracion.CLAVE_ADMINISTRADOR,
        )
        tipo = ContentType.objects.get_for_model(Capacidad)
        grupo.permissions.add(*Permission.objects.filter(content_type=tipo, codename__in=codenames))
        return grupo

    def _codenames(self, grupo):
        return set(grupo.permissions.values_list("codename", flat=True))

    def test_los_codenames_y_etiquetas_son_los_del_catalogo(self):
        """Si alguien renombra una, la siembra quedaría sin efecto en silencio."""
        catalogo = dict(rbac.todas_las_capacidades())
        for codename, nombre in self.migracion.CAPACIDADES:
            self.assertEqual(catalogo.get(codename), nombre)
        self.assertEqual(
            {codename for codename, _ in self.migracion.CAPACIDADES},
            {rbac.codename_de(c) for c in (OPERAR, SUPERVISAR, RECIBIR_KIT)},
        )

    def test_el_estado_declara_las_cuatro(self):
        declaradas = {c for c, _ in self.apps_de_entonces.get_model("users", "Capacidad")._meta.permissions}
        self.assertTrue({rbac.codename_de(c) for c in LAS_DE_LA_MESA | {RECIBIR_KIT}} <= declaradas)

    def test_el_administrador_recibe_tres_y_no_relevar(self):
        admin = self._administrador("dispositivo_ver")

        self.migracion.sembrar(self.apps_de_entonces, None)
        self.migracion.sembrar(self.apps_de_entonces, None)

        self.assertEqual(
            self._codenames(admin),
            {"dispositivo_ver", "emergencia_operar", "emergencia_supervisar", "emergencia_recibir_kit"},
        )

    def test_no_toca_a_otros_roles(self):
        self._administrador()
        otro = Group.objects.create(name="Operador de backoffice")
        self.migracion.sembrar(self.apps_de_entonces, None)
        self.assertEqual(self._codenames(otro), set())

    def test_sin_administrador_no_hace_nada(self):
        self.migracion.sembrar(self.apps_de_entonces, None)
        self.migracion.quitar(self.apps_de_entonces, None)
        self.assertFalse(Group.objects.filter(name=rbac.ROL_ADMINISTRADOR).exists())

    def test_la_reversa_se_las_saca_y_conserva_lo_demas(self):
        admin = self._administrador("dispositivo_ver")
        self.migracion.sembrar(self.apps_de_entonces, None)

        self.migracion.quitar(self.apps_de_entonces, None)

        self.assertEqual(self._codenames(admin), {"dispositivo_ver"})
