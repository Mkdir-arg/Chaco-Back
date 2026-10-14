"""Regresiones de la revisión C5: ocupación, admin de consulta y alcance."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Permission, User
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models.query import QuerySet
from django.test import RequestFactory
from django.urls import reverse

from programas.models import Dispositivo, Edificio, Plaza, ReservaPlaza, Sector, TrazaDispositivo
from programas.services.estadias import ingresar_persona, reservar_plaza
from programas.services.plazas import agregar_plazas, editar_plaza
from programas.tests.test_dispositivos_capacidad import BaseCapacidad


class PlazaTomadaNoSeEditaTests(BaseCapacidad):
    def _rechaza_edicion(self, ocupacion):
        original = (self.plaza.codigo, self.plaza.tipo)
        with self.assertRaisesMessage(ValidationError, ocupacion):
            editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo="NUEVA", tipo=Plaza.Tipo.CUPO)
        self.client.force_login(self.operador_cis)
        respuesta = self.client.post(
            reverse("dispositivos:plaza_editar", args=[self.cis.pk, self.plaza.pk]),
            {"codigo": "NUEVA", "tipo": Plaza.Tipo.CUPO},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn(ocupacion, str(respuesta.json()))
        self.plaza.refresh_from_db()
        self.assertEqual((self.plaza.codigo, self.plaza.tipo), original)
        self.assertFalse(TrazaDispositivo.objects.filter(accion="PLAZA_EDITADA").exists())

    def test_estadia_activa_impide_editar_codigo_y_tipo(self):
        ingresar_persona(ciudadano=self.persona, dispositivo=self.cis, usuario=self.operador_cis, plaza=self.plaza)
        self._rechaza_edicion("una estadía activa")

    def test_reserva_vigente_impide_editar_codigo_y_tipo(self):
        reservar_plaza(
            plaza=self.plaza,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            desde=self.ahora,
            hasta=self.ahora + timedelta(hours=12),
        )
        self._rechaza_edicion("una reserva vigente")

    def test_prestamo_vigente_impide_editar_codigo_y_tipo(self):
        reservar_plaza(
            plaza=self.plaza,
            ciudadano=self.persona,
            usuario=self.operador_cis,
            desde=self.ahora,
            hasta=self.ahora + timedelta(hours=12),
            tipo=ReservaPlaza.Tipo.PRESTAMO,
        )
        self._rechaza_edicion("un préstamo vigente")


class AdminCapacidadSoloLecturaTests(BaseCapacidad):
    def test_el_admin_no_permite_agregar_cambiar_ni_borrar_incluso_al_superusuario(self):
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(username="consulta", password="x")
        for modelo in (Edificio, Sector, Plaza):
            registro = admin.site._registry[modelo]
            with self.subTest(modelo=modelo):
                self.assertTrue(registro.has_view_permission(request))
                self.assertFalse(registro.has_add_permission(request))
                self.assertFalse(registro.has_change_permission(request))
                self.assertFalse(registro.has_delete_permission(request))
                campos = {campo.name for campo in modelo._meta.fields + modelo._meta.many_to_many}
                self.assertSetEqual(set(registro.get_readonly_fields(request)), campos)

    def test_los_post_del_admin_no_escriben(self):
        edificio = Edificio.objects.create(codigo="E1", nombre="Predio")
        staff_ajeno = self.operador_parador
        staff_ajeno.is_staff = True
        staff_ajeno.save()
        staff_ajeno.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="programas",
                codename__in=[
                    f"{accion}_{modelo}"
                    for accion in ("add", "change", "delete", "view")
                    for modelo in ("edificio", "sector", "plaza")
                ],
            )
        )
        soporte = User.objects.create_superuser(username="soporte_revision", password="x")
        for usuario in (staff_ajeno, soporte):
            self.client.force_login(usuario)
            for obj in (edificio, self.sector, self.plaza):
                modelo = obj._meta.model_name
                with self.subTest(usuario=usuario.username, modelo=modelo):
                    self.assertEqual(
                        self.client.get(reverse(f"admin:programas_{modelo}_change", args=[obj.pk])).status_code, 200
                    )
                    for accion in ("add", "change", "delete"):
                        args = [] if accion == "add" else [obj.pk]
                        respuesta = self.client.post(
                            reverse(f"admin:programas_{modelo}_{accion}", args=args),
                            {
                                "codigo": "AJENA",
                                "nombre": "Cambio",
                                "tipo": Plaza.Tipo.CUPO,
                                "sector": self.sector.pk,
                                "dispositivo": self.cis.pk,
                                "post": "yes",
                            },
                        )
                        self.assertEqual(respuesta.status_code, 403)
        self.plaza.refresh_from_db()
        self.assertEqual(self.plaza.codigo, "P1")
        self.assertEqual(Edificio.objects.count(), 1)


class DispositivoFueraDeAlcanceTests(BaseCapacidad):
    def test_dispositivo_ajeno_e_inexistente_dan_el_mismo_404_antes_del_formulario(self):
        self.client.force_login(self.operador_cis)
        for accion in ("sector_crear", "plazas_agregar", "edificio_crear", "edificio_vincular"):
            for ajax in (False, True):
                extras = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"} if ajax else {}
                with self.subTest(accion=accion, ajax=ajax):
                    respuestas = [
                        self.client.post(reverse(f"dispositivos:{accion}", args=[pk]), {}, **extras)
                        for pk in (self.parador.pk, 999999)
                    ]
                    self.assertEqual([r.status_code for r in respuestas], [404, 404])


class UnicidadBajoCandadoTests(BaseCapacidad):
    """En SQLite el FOR UPDATE no actúa: fijamos su evaluación y la lectura posterior."""

    def _tras_bloquear_dispositivo(self, operacion, comprobar):
        obtener = QuerySet.get
        candados = []

        def get(queryset, *args, **kwargs):
            resultado = obtener(queryset, *args, **kwargs)
            if queryset.query.select_for_update:
                self.assertTrue(connection.in_atomic_block)
                self.assertFalse(queryset.query.select_related, "El FOR UPDATE debe bloquear una sola tabla")
                candados.append(queryset.model)
                if queryset.model is Dispositivo:
                    # Otro POST terminó mientras esperábamos: el form ya vio el código libre.
                    Plaza.objects.create(sector=self.rival, codigo="B-01")
            return resultado

        self.rival = Sector.objects.create(dispositivo=self.cis, nombre="Otro pabellón")
        with patch.object(QuerySet, "get", get):
            comprobar(operacion)
        self.assertEqual(candados[0], Dispositivo)
        self.assertEqual(candados[-1], Plaza if operacion == "editar" else Sector)

    def test_el_lote_relee_codigos_despues_de_bloquear_el_dispositivo(self):
        def comprobar(_):
            plazas = agregar_plazas(sector=self.sector, usuario=self.operador_cis, cantidad=1, prefijo="B-")
            self.assertEqual([p.codigo for p in plazas], ["B-02"])

        self._tras_bloquear_dispositivo("lote", comprobar)

    def test_la_edicion_revalida_unicidad_despues_de_bloquear_el_dispositivo(self):
        def comprobar(_):
            with self.assertRaisesMessage(ValidationError, "Ya hay una plaza con ese código"):
                editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo="b-01", tipo=Plaza.Tipo.CAMA)

        self._tras_bloquear_dispositivo("editar", comprobar)

    def test_la_guarda_de_ocupacion_se_consulta_con_la_plaza_bloqueada(self):
        obtener = QuerySet.get
        candados = []

        def get(queryset, *args, **kwargs):
            resultado = obtener(queryset, *args, **kwargs)
            if queryset.query.select_for_update:
                candados.append(queryset.model)
                self.assertFalse(queryset.query.select_related)
            return resultado

        def tomada(plaza):
            self.assertEqual(candados, [Dispositivo, Plaza])
            self.assertTrue(connection.in_atomic_block)
            return "una estadía activa"

        with patch.object(QuerySet, "get", get), patch("programas.services.plazas._plaza_tomada_por", tomada):
            with self.assertRaises(ValidationError):
                editar_plaza(plaza=self.plaza, usuario=self.operador_cis, codigo="NUEVA", tipo=Plaza.Tipo.CAMA)
