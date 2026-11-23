"""Inactivar y reactivar un edificio (Cambio 583, task #1228).

1. Servicio: el administrador del programa inactiva y reactiva; la traza queda en cada institución vinculada; el
   resto recibe ``PermissionDenied`` y no cambia nada.
2. Bloqueos, cada uno por su cuenta y los tres juntos en un solo mensaje: sectores activos (de cualquier institución),
   relevamiento en curso y entregas de kits por recibir. El Equipo asignado no bloquea y vuelve tal cual.
3. Un edificio inactivo no se ofrece para vincular, ubicar sectores ni crear relevamientos, y no se edita ni se
   desvincula.
4. Vistas: POST con 403 sin la capacidad, vuelta segura, mensaje de bloqueo por toast.
5. Pantallas: la página del edificio, la ficha de Edificios, el listado y la tarjeta de Infraestructura.
"""

import re
from unittest import mock

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from programas.forms_dispositivos import SectorForm
from programas.models import (
    Dispositivo,
    Edificio,
    EntregaKit,
    InspeccionEdificio,
    MiembroEquipoDispositivo,
    Sector,
    TrazaDispositivo,
)
from programas.selectors.capacidad_dispositivo import edificios_vinculables
from programas.services.edificios import (
    desvincular_edificio,
    editar_edificio,
    inactivar_edificio,
    reactivar_edificio,
    vincular_edificio,
)
from programas.services.inspecciones import edificios_para_asignar, edificios_sin_relevar
from programas.services.plazas import crear_sector, editar_sector, reactivar_sector
from programas.tests.test_dispositivos_edificio_operativo import BaseOperativo
from programas.tests.test_equipo_alcance_edificio import Alcance

CAPS_ADMIN = ("dispositivo.ver", "dispositivo.editar", "programa.configurar", "inspeccion.asignar")
CAPS_NO_ADMIN = ("dispositivo.ver", "dispositivo.editar", "dispositivo.admitir", "inspeccion.asignar")
Estado = EntregaKit.Estado


class BaseInactivar(BaseOperativo):
    def setUp(self):
        super().setUp()
        self.admin_prog = self._con("Admin del programa", *CAPS_ADMIN)
        self.no_admin = self._con("Sin administrar", *CAPS_NO_ADMIN)
        # Sin sectores ni relevamientos: se puede inactivar de entrada.
        self.edif_c = self._edificio("ED-C")
        self._numero = 0

    def _fresco(self, usuario):
        return User.objects.get(pk=usuario.pk)

    def _cliente(self, usuario):
        """Un cliente por usuario: la sesión única del backoffice cierra la segunda sesión que se abre."""

        clientes = self.__dict__.setdefault("_clientes", {})
        if usuario.pk not in clientes:
            cliente = Client()
            cliente.force_login(self._fresco(usuario))
            clientes[usuario.pk] = cliente
        return clientes[usuario.pk]

    def _inactivar(self, edificio=None, usuario=None):
        return inactivar_edificio(edificio=edificio or self.edif_c, usuario=self._fresco(usuario or self.admin_prog))

    def _reactivar(self, edificio=None, usuario=None):
        return reactivar_edificio(edificio=edificio or self.edif_c, usuario=self._fresco(usuario or self.admin_prog))

    def _activo(self, edificio=None):
        return Edificio.objects.get(pk=(edificio or self.edif_c).pk).activo

    def _inactivo(self, edificio=None):
        edificio = edificio or self.edif_c
        Edificio.objects.filter(pk=edificio.pk).update(activo=False)
        return Edificio.objects.get(pk=edificio.pk)

    def _relevamiento(self, edificio, estado=InspeccionEdificio.Estado.ASIGNADA):
        Estado_ = InspeccionEdificio.Estado
        datos = {}
        if estado == Estado_.REALIZADA:
            datos = {
                "criticidad": InspeccionEdificio.Criticidad.BAJA,
                "realizada_en": timezone.now(),
                "realizada_por": self.de_a,
            }
        elif estado == Estado_.CANCELADA:
            datos = {"motivo_cancelacion": "Ya no hace falta"}
        return InspeccionEdificio.objects.create(
            edificio=edificio,
            estado=estado,
            asignado_a=self.de_a,
            creado_por=self.admin_prog,
            fecha_vencimiento="2099-01-01",
            **datos,
        )

    def _relevamiento_en_curso(self, edificio):
        return self._relevamiento(edificio)

    def _entrega(self, edificio, estado=Estado.EN_CAMINO):
        self._numero += 1
        return EntregaKit.objects.create(
            numero=f"2026-K-{self._numero:06d}",
            dispositivo=self.cis,
            edificio=edificio,
            estado=estado,
            armada_por=self.admin_prog,
        )

    def _sector(self, edificio, nombre="Sector extra", dispositivo=None):
        return Sector.objects.create(dispositivo=dispositivo or self.cis, nombre=nombre, capacidad=2, edificio=edificio)

    def _mensaje(self, edificio=None):
        with self.assertRaises(ValidationError) as error:
            self._inactivar(edificio)
        self.assertTrue(self._activo(edificio))
        return error.exception.message_dict["__all__"][0]


class InactivarYReactivarTests(BaseInactivar):
    def test_el_admin_inactiva_y_reactiva(self):
        self._inactivar()
        self.assertFalse(self._activo())

        self._reactivar()
        self.assertTrue(self._activo())

    def test_la_traza_queda_en_cada_institucion_vinculada(self):
        otra = Dispositivo.objects.create(tipo=self.tipo, codigo="OTRA", nombre="Otra", estado="ACTIVO")
        self.edif_c.dispositivos.add(otra)

        self._inactivar()
        self._reactivar()

        for dispositivo in (self.cis, otra):
            acciones = list(
                TrazaDispositivo.objects.filter(dispositivo=dispositivo, edificio=self.edif_c).values_list(
                    "accion", flat=True
                )
            )
            self.assertEqual(acciones, ["EDIFICIO_INACTIVADO", "EDIFICIO_REACTIVADO"], dispositivo.nombre)

    def test_inactivar_no_borra_vinculos_ni_relevamientos(self):
        realizada = self._relevamiento(self.edif_c, InspeccionEdificio.Estado.REALIZADA)

        self._inactivar()
        self._reactivar()

        self.assertTrue(self.edif_c.dispositivos.filter(pk=self.cis.pk).exists())
        self.assertTrue(InspeccionEdificio.objects.filter(pk=realizada.pk).exists())

    def test_inactivar_uno_ya_inactivo_o_reactivar_uno_activo_se_rechaza(self):
        with self.assertRaises(ValidationError):
            self._reactivar()
        self._inactivar()
        with self.assertRaises(ValidationError):
            self._inactivar()
        self.assertEqual(TrazaDispositivo.objects.filter(accion="EDIFICIO_INACTIVADO").count(), 1)

    def test_quien_no_es_admin_recibe_permission_denied_y_no_cambia_nada(self):
        trazas = TrazaDispositivo.objects.count()
        for usuario in (self.no_admin, self.de_inst, self.de_a):
            with self.subTest(usuario=usuario.username), self.assertRaises(PermissionDenied):
                self._inactivar(usuario=usuario)
        self.assertTrue(self._activo())

        self._inactivo()
        for usuario in (self.no_admin, self.de_inst):
            with self.subTest(reactivar=usuario.username), self.assertRaises(PermissionDenied):
                self._reactivar(usuario=usuario)
        self.assertFalse(self._activo())
        self.assertEqual(TrazaDispositivo.objects.count(), trazas)

    def test_el_superusuario_puede(self):
        root = User.objects.create_superuser(username="root_edificios", password="x")

        self._inactivar(usuario=root)

        self.assertFalse(self._activo())


class BloqueosTests(BaseInactivar):
    def test_un_sector_activo_bloquea_y_dice_cuantos(self):
        self._sector(self.edif_c)

        self.assertEqual(
            self._mensaje(),
            "No se puede inactivar Edificio ED-C: tiene 1 sector activo. Dalo de baja antes.",
        )

    def test_el_sector_de_cualquier_institucion_bloquea(self):
        otra = Dispositivo.objects.create(tipo=self.tipo, codigo="OTRA", nombre="Otra", estado="ACTIVO")
        self.edif_c.dispositivos.add(otra)
        self._sector(self.edif_c, dispositivo=otra)

        self.assertIn("1 sector activo", self._mensaje())

    def test_un_sector_dado_de_baja_no_bloquea(self):
        sector = self._sector(self.edif_c)
        Sector.objects.filter(pk=sector.pk).update(activo=False)

        self._inactivar()

        self.assertFalse(self._activo())

    def test_un_relevamiento_en_curso_bloquea(self):
        self._relevamiento_en_curso(self.edif_c)

        self.assertEqual(
            self._mensaje(),
            "No se puede inactivar Edificio ED-C: tiene un relevamiento en curso. Cerrá o cancelá el relevamiento antes.",
        )

    def test_un_relevamiento_realizado_o_cancelado_no_bloquea(self):
        for estado in (InspeccionEdificio.Estado.REALIZADA, InspeccionEdificio.Estado.CANCELADA):
            self._relevamiento(self.edif_c, estado)

        self._inactivar()

        self.assertFalse(self._activo())

    def test_una_entrega_de_kits_por_recibir_bloquea(self):
        for estado in (Estado.EN_CAMINO, Estado.PREPARADA):
            with self.subTest(estado=estado):
                entrega = self._entrega(self.edif_c, estado)
                self.assertEqual(
                    self._mensaje(),
                    "No se puede inactivar Edificio ED-C: tiene 1 entrega de kits por recibir. Recibí la entrega antes.",
                )
                EntregaKit.objects.filter(pk=entrega.pk).delete()

    def test_las_entregas_cerradas_o_de_otro_edificio_no_bloquean(self):
        for estado in (Estado.RECIBIDA, Estado.RECIBIDA_CON_DIFERENCIAS, Estado.CANCELADA):
            self._entrega(self.edif_c, estado)
        self._entrega(self.edif_a)

        self._inactivar()

        self.assertFalse(self._activo())

    def test_los_tres_motivos_juntos_van_en_un_solo_mensaje(self):
        self._sector(self.edif_c, "Uno")
        self._sector(self.edif_c, "Dos")
        self._entrega(self.edif_c)

        self.assertEqual(
            self._mensaje(),
            "No se puede inactivar Edificio ED-C: tiene 2 sectores activos y 1 entrega de kits por recibir. "
            "Dalos de baja o recibí la entrega antes.",
        )
        self._relevamiento_en_curso(self.edif_c)
        self._entrega(self.edif_c)
        self.assertEqual(
            self._mensaje(),
            "No se puede inactivar Edificio ED-C: tiene 2 sectores activos, un relevamiento en curso y "
            "2 entregas de kits por recibir. Dalos de baja, cerrá o cancelá el relevamiento o recibí las entregas antes.",
        )
        self.assertEqual(TrazaDispositivo.objects.filter(accion="EDIFICIO_INACTIVADO").count(), 0)

    def test_el_equipo_asignado_no_bloquea_y_vuelve_tal_cual(self):
        miembro = self._con("Del edificio C", "dispositivo.ver", alcance=Alcance.EDIFICIOS, edificios=[self.edif_c])
        fila = MiembroEquipoDispositivo.objects.get(usuario=miembro, dispositivo=self.cis)

        self._inactivar()
        self.assertEqual(set(fila.edificios.values_list("pk", flat=True)), {self.edif_c.pk})

        self._reactivar()
        fila.refresh_from_db()
        self.assertEqual(fila.alcance, Alcance.EDIFICIOS)
        self.assertEqual(set(fila.edificios.values_list("pk", flat=True)), {self.edif_c.pk})


class InactivoNoSeOfreceTests(BaseInactivar):
    def setUp(self):
        super().setUp()
        self.otra = Dispositivo.objects.create(tipo=self.tipo, codigo="OTRA", nombre="Otra", estado="ACTIVO")
        self.libre = Edificio.objects.create(codigo="ED-LIBRE", nombre="Libre")
        self.admin = User.objects.create_superuser(username="root_inactivo", password="x")

    def test_no_se_ofrece_para_vincular_ni_se_vincula(self):
        self.assertIn(self.libre, edificios_vinculables(self.admin, self.otra))
        self._inactivo(self.libre)

        self.assertNotIn(self.libre, edificios_vinculables(self._fresco(self.admin), self.otra))
        with self.assertRaises(PermissionDenied):
            vincular_edificio(edificio=self.libre, dispositivo=self.otra, usuario=self._fresco(self.admin))
        self.assertFalse(self.libre.dispositivos.filter(pk=self.otra.pk).exists())

    def test_vincular_vuelve_a_mirar_que_este_activo_bajo_candado(self):
        """Aun si el alcance lo dejara pasar, un edificio inactivo (o que se está inactivando) no se vincula."""

        self._inactivo(self.libre)

        with mock.patch(
            "programas.services.edificios.edificios_vinculables", return_value=Edificio.objects.filter(pk=self.libre.pk)
        ):
            with self.assertRaises(ValidationError):
                vincular_edificio(edificio=self.libre, dispositivo=self.otra, usuario=self._fresco(self.admin))
        self.assertFalse(self.libre.dispositivos.filter(pk=self.otra.pk).exists())

    def test_no_se_ofrece_para_relevamientos(self):
        self.assertIn(self.edif_c, edificios_para_asignar(self.admin))
        self._inactivo()

        self.assertNotIn(self.edif_c, edificios_para_asignar(self._fresco(self.admin)))
        self.assertNotIn(self.edif_c, edificios_sin_relevar(self._fresco(self.admin)))

    def test_no_se_ofrece_para_ubicar_un_sector_ni_se_ubica(self):
        self._inactivo()

        form = SectorForm(dispositivo=self.cis)
        self.assertNotIn(self.edif_c, form.fields["edificio"].queryset)
        self.assertIn(self.edif_a, form.fields["edificio"].queryset)
        with self.assertRaises(ValidationError) as error:
            crear_sector(
                dispositivo=self.cis,
                usuario=self._fresco(self.admin),
                nombre="Nuevo",
                tipo=Sector.Tipo.HABITACION,
                edificio=Edificio.objects.get(pk=self.edif_c.pk),
            )
        self.assertIn("edificio", error.exception.message_dict)
        self.assertFalse(Sector.objects.filter(nombre="Nuevo").exists())

    def test_un_sector_en_edicion_conserva_su_edificio_inactivo_en_el_form_y_no_se_activa_alli(self):
        sector = self._sector(self.edif_c)
        Sector.objects.filter(pk=sector.pk).update(activo=False)
        sector.refresh_from_db()
        self._inactivo()

        form = SectorForm(dispositivo=self.cis, sector=sector)
        self.assertIn(self.edif_c, form.fields["edificio"].queryset)

        with self.assertRaises(ValidationError):
            reactivar_sector(sector=sector, usuario=self._fresco(self.admin))
        with self.assertRaises(ValidationError):
            editar_sector(
                sector=sector,
                usuario=self._fresco(self.admin),
                nombre=sector.nombre,
                tipo=sector.tipo,
                edificio=Edificio.objects.get(pk=self.edif_c.pk),
                activo=True,
            )
        self.assertFalse(Sector.objects.get(pk=sector.pk).activo)

    def test_no_se_edita_ni_se_desvincula_hasta_reactivarlo(self):
        self._inactivo()
        edificio = Edificio.objects.get(pk=self.edif_c.pk)

        with self.assertRaises(ValidationError):
            editar_edificio(
                edificio=edificio, dispositivo=self.cis, usuario=self._fresco(self.admin), codigo="ED-X", nombre="X"
            )
        with self.assertRaises(ValidationError):
            desvincular_edificio(edificio=edificio, dispositivo=self.cis, usuario=self._fresco(self.admin))
        self.assertEqual(Edificio.objects.get(pk=edificio.pk).codigo, "ED-C")
        self.assertTrue(edificio.dispositivos.filter(pk=self.cis.pk).exists())

        self._reactivar()
        desvincular_edificio(edificio=edificio, dispositivo=self.cis, usuario=self._fresco(self.admin))
        self.assertFalse(edificio.dispositivos.filter(pk=self.cis.pk).exists())


class VistasTests(BaseInactivar):
    def _url(self, nombre, edificio=None):
        return reverse(f"dispositivos:{nombre}", args=[(edificio or self.edif_c).pk])

    def _post(self, usuario, nombre, edificio=None, **params):
        consulta = "?" + "&".join(f"{k}={v}" for k, v in params.items()) if params else ""
        return self._cliente(usuario).post(self._url(nombre, edificio) + consulta)

    def _textos(self, respuesta):
        return [str(m) for m in respuesta.wsgi_request._messages]

    def test_el_admin_inactiva_y_vuelve_a_la_ficha(self):
        respuesta = self._post(self.admin_prog, "edificio_inactivar")

        self.assertRedirects(respuesta, self._url("edificio_detalle"), fetch_redirect_response=False)
        self.assertFalse(self._activo())
        self.assertEqual(self._textos(respuesta), ["Edificio Edificio ED-C inactivado."])

    def test_el_admin_reactiva(self):
        self._inactivo()

        respuesta = self._post(self.admin_prog, "edificio_reactivar")

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self._activo())

    def test_vuelve_a_la_pagina_del_edificio_con_next(self):
        pagina = reverse("dispositivos:edificio_operativo", args=[self.cis.pk, self.edif_c.pk])

        respuesta = self._post(self.admin_prog, "edificio_inactivar", next=pagina)

        self.assertEqual(respuesta["Location"], pagina)

    def test_un_next_ajeno_o_fuera_de_dispositivos_se_ignora(self):
        for malo in ("https://malo.tld/x", "//malo.tld/x", "/becas/"):
            with self.subTest(next=malo):
                respuesta = self._post(self.admin_prog, "edificio_reactivar", next=malo)
                self.assertEqual(respuesta["Location"], self._url("edificio_detalle"))
                self._inactivo()  # el POST de arriba falla (ya está activo) o vuelve: se deja inactivo para el siguiente

    def test_sin_la_capacidad_es_403_y_no_cambia_nada(self):
        trazas = TrazaDispositivo.objects.count()
        for usuario in (self.no_admin, self.de_inst, self.de_a):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self._post(usuario, "edificio_inactivar").status_code, 403)
        self.assertTrue(self._activo())

        self._inactivo()
        for usuario in (self.no_admin, self.de_inst):
            with self.subTest(reactivar=usuario.username):
                r = self._post(usuario, "edificio_reactivar")
                self.assertEqual(r.status_code, 403, r.get("Location"))
        self.assertFalse(self._activo())
        self.assertEqual(TrazaDispositivo.objects.count(), trazas)

    def test_sin_sesion_va_al_login_y_no_cambia_nada(self):
        respuesta = self.client.post(self._url("edificio_inactivar"))

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("?next=", respuesta["Location"])
        self.assertTrue(self._activo())

    def test_solo_acepta_post(self):
        cliente = self._cliente(self.admin_prog)

        for nombre in ("edificio_inactivar", "edificio_reactivar"):
            self.assertEqual(cliente.get(self._url(nombre)).status_code, 405)
        self.assertTrue(self._activo())

    def test_un_edificio_inexistente_es_404_para_el_admin(self):
        respuesta = self._cliente(self.admin_prog).post(reverse("dispositivos:edificio_inactivar", args=[999999]))

        self.assertEqual(respuesta.status_code, 404)

    def test_el_bloqueo_se_dice_por_mensaje_y_no_cambia_nada(self):
        self._sector(self.edif_c, "Uno")
        self._sector(self.edif_c, "Dos")
        self._entrega(self.edif_c)

        respuesta = self._post(self.admin_prog, "edificio_inactivar")

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            self._textos(respuesta),
            [
                "No se puede inactivar Edificio ED-C: tiene 2 sectores activos y 1 entrega de kits por recibir. "
                "Dalos de baja o recibí la entrega antes."
            ],
        )
        self.assertTrue(self._activo())


class PantallasTests(BaseInactivar):
    def _pagina(self, usuario, edificio=None, **params):
        return self._get(usuario, edificio or self.edif_c, **params)

    def test_activo_el_admin_ve_inactivar_en_mas_acciones_con_su_confirmacion_roja(self):
        respuesta = self._pagina(self.admin_prog)

        self.assertContains(respuesta, "Inactivar edificio")
        self.assertContains(respuesta, f"¿Inactivar {self.edif_c.nombre}?")
        self.assertContains(respuesta, "El edificio deja de ofrecerse para relevamientos, sectores y vínculos.")
        url = reverse("dispositivos:edificio_inactivar", args=[self.edif_c.pk])
        self.assertContains(respuesta, url)
        # La confirmación roja es la del botón de inactivar, no la de otro ítem del menú (p. ej. «Desvincular»).
        boton = re.search(
            r'<button[^>]*data-confirm-url="' + re.escape(url) + r'[^"]*"[^>]*>', respuesta.content.decode()
        )
        self.assertIsNotNone(boton)
        self.assertIn('data-confirm-danger="true"', boton.group(0))
        self.assertNotContains(respuesta, "Activar edificio")

    def test_quien_no_es_admin_no_ve_ningun_boton(self):
        for edificio_inactivo in (False, True):
            if edificio_inactivo:
                self._inactivo()
            respuesta = self._pagina(self.no_admin)
            self.assertNotContains(respuesta, "Inactivar edificio")
            self.assertNotContains(respuesta, "Activar edificio")
            self.assertNotContains(respuesta, reverse("dispositivos:edificio_inactivar", args=[self.edif_c.pk]))

    def test_inactivo_marca_avisa_y_cambia_las_acciones_del_encabezado(self):
        self._inactivo()

        respuesta = self._pagina(self.admin_prog)

        self.assertContains(respuesta, "Inactivo</span>")
        self.assertContains(respuesta, "Este edificio está inactivo.")
        self.assertContains(
            respuesta,
            "No se ofrece para relevamientos, sectores ni vínculos. Sus datos, relevamientos y equipo se conservan.",
        )
        self.assertContains(respuesta, "Activar edificio")
        self.assertContains(respuesta, reverse("dispositivos:edificio_reactivar", args=[self.edif_c.pk]))
        self.assertNotContains(respuesta, reverse("dispositivos:ingreso_persona", args=[self.cis.pk]))
        self.assertNotContains(respuesta, reverse("dispositivos:bitacora", args=[self.cis.pk]))
        self.assertNotContains(respuesta, "Inactivar edificio")
        self.assertNotContains(respuesta, "Editar edificio")
        self.assertNotContains(respuesta, "Desvincular de")

    def test_inactivo_quien_no_es_admin_ve_el_aviso_y_la_marca_sin_acciones(self):
        self._inactivo()

        respuesta = self._pagina(self.no_admin)

        self.assertContains(respuesta, "Este edificio está inactivo.")
        self.assertContains(respuesta, "Inactivo</span>")
        self.assertNotContains(respuesta, reverse("dispositivos:ingreso_persona", args=[self.cis.pk]))

    def test_solapa_de_sectores_de_un_edificio_inactivo_no_ofrece_altas_ni_reactivar(self):
        baja = self._sector(self.edif_c, nombre="Sector de baja")
        Sector.objects.filter(pk=baja.pk).update(activo=False)
        reactivar = reverse("dispositivos:sector_reactivar", args=[self.cis.pk, baja.pk])
        nuevo = reverse("dispositivos:sector_crear", args=[self.cis.pk])

        # Control positivo: con el edificio activo se ofrecen las tres cosas.
        respuesta = self._pagina(self.admin_prog, tab="sectores", inactivos="1")
        self.assertContains(respuesta, nuevo)
        self.assertContains(respuesta, reactivar)

        self._inactivo()
        for params in ({"tab": "sectores"}, {"tab": "sectores", "inactivos": "1"}):
            with self.subTest(params=params):
                respuesta = self._pagina(self.admin_prog, **params)
                self.assertEqual(respuesta.status_code, 200)
                self.assertNotContains(respuesta, nuevo)
                self.assertNotContains(respuesta, reactivar)
                self.assertNotContains(respuesta, "Nuevo sector")

    def _ficha(self, usuario):
        return self._cliente(usuario).get(reverse("dispositivos:edificio_detalle", args=[self.edif_c.pk]))

    def test_ficha_de_edificios_activo_el_admin_ve_inactivar(self):
        admin_ver = self._con("Admin ver", "dispositivo.ver", "edificio.ver", "programa.configurar")

        respuesta = self._ficha(admin_ver)

        self.assertContains(respuesta, "Inactivar edificio")
        self.assertContains(respuesta, reverse("dispositivos:edificio_inactivar", args=[self.edif_c.pk]))

    def test_ficha_de_edificios_inactivo_el_admin_ve_la_marca_y_activar_y_el_resto_404(self):
        self._inactivo()
        admin_ver = self._con("Admin ver", "dispositivo.ver", "edificio.ver", "programa.configurar")
        solo_ver = self._con("Solo ver", "dispositivo.ver", "edificio.ver")

        respuesta = self._ficha(admin_ver)
        self.assertContains(respuesta, 'badge badge-gray">Inactivo')
        self.assertContains(respuesta, "Activar edificio")
        self.assertNotContains(respuesta, "Editar edificio")

        self.assertEqual(self._ficha(solo_ver).status_code, 404)

    def test_ficha_de_edificios_sin_admin_no_hay_botones(self):
        respuesta = self._ficha(self._con("Solo ver", "dispositivo.ver", "edificio.ver"))

        self.assertNotContains(respuesta, "Inactivar edificio")
        self.assertNotContains(respuesta, "Activar edificio")

    def test_el_listado_esconde_el_inactivo_al_no_admin_y_lo_muestra_al_admin_con_situacion(self):
        self._inactivo()
        admin_ver = self._con("Admin ver", "dispositivo.ver", "edificio.ver", "programa.configurar")
        solo_ver = self._con("Solo ver", "dispositivo.ver", "edificio.ver")
        url = reverse("dispositivos:edificios")

        def codigos(usuario, **params):
            return {fila["codigo"] for fila in self._cliente(usuario).get(url, params).context["filas"]}

        for situacion in ("", "inactivos", "todos"):
            with self.subTest(no_admin=situacion):
                self.assertNotIn("ED-C", codigos(solo_ver, situacion=situacion))
        self.assertNotIn("ED-C", codigos(admin_ver))
        for situacion in ("inactivos", "todos"):
            with self.subTest(admin=situacion):
                self.assertIn("ED-C", codigos(admin_ver, situacion=situacion))

    def test_la_tarjeta_de_infraestructura_marca_el_inactivo_y_no_ofrece_editarlo(self):
        self._inactivo()

        respuesta = self._cliente(self.admin_prog).get(
            reverse("dispositivos:detalle", args=[self.cis.pk]), {"tab": "infraestructura"}
        )

        html = respuesta.content.decode()
        tarjeta = html[html.index(f'id="edificio-{self.edif_c.pk}-titulo"') :]
        tarjeta = tarjeta[: tarjeta.index("</article>")]
        self.assertIn("Inactivo", tarjeta)
        self.assertNotIn("Editar edificio", tarjeta)
        self.assertNotIn("Desvincular", tarjeta)
        self.assertIn("Abrir edificio", tarjeta)
