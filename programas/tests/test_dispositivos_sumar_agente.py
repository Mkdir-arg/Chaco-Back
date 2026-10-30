"""«Sumar como agente» desde «Buscar agente» (Dispositivos · 30-oct-2026, Cambio 404).

Lo que se fija acá, y por qué:

1. **La búsqueda suma a los usuarios activos del backoffice sin el rol**, marcados `sumable` y con DNI y correo
   enmascarados. No aparecen superusuarios, ciudadanos del portal ni inactivos sin el rol.
2. **Sumar da EXACTAMENTE el grupo sembrado de agente** y ningún permiso más; no toca contraseña ni datos.
3. **El endpoint no confía en el template**: 403 sin la capacidad (también la de otro programa) o con un edificio
   fuera de alcance, 405 con GET, 429 por operador, y rechazo de inactivos, superusuarios y ciudadanos.
4. **Idempotente**: quien ya es agente responde 200 con `sumado: false` y no escribe.
5. El personal de una institución del edificio recibe el rol pero la respuesta dice `asignable: false`.
"""

import logging

from django.contrib.auth.models import Group, User
from django.urls import reverse

from core import rbac
from programas.models import AsignacionDispositivo
from programas.services.buscador_agentes import MOTIVO_SUMABLE, MOTIVO_SUMABLE_PERSONAL
from programas.services.inspecciones import agentes_asignables
from programas.tests.test_dispositivos_buscar_agente import BaseBuscarAgente
from programas.tests.test_dispositivos_inspecciones import _permiso
from users.models import RolMeta

URL_SUMAR = "users:usuario_sumar_agente"


class BaseSumarAgente(BaseBuscarAgente):
    def setUp(self):
        super().setUp()
        self.url_sumar = reverse(URL_SUMAR)
        self.ana = self._persona("ana", "Ana", "Sumable", "30999888", "ana@example.com")

    def _sumar(self, usuario_id, edificio=None, operador=None, **extra):
        datos = {"user_id": usuario_id}
        if edificio is not False:
            datos["edificio_id"] = (edificio or self.predio).pk
        datos.update(extra)
        return self._cliente(operador or self.creador).post(self.url_sumar, datos)

    def _foto(self):
        return (
            {(g.pk, g.name, frozenset(g.permissions.values_list("pk", flat=True))) for g in Group.objects.all()},
            {(u.pk, frozenset(u.groups.values_list("pk", flat=True)), u.password, u.email) for u in User.objects.all()},
        )


class BusquedaSumableTests(BaseSumarAgente):
    def _filas(self, q):
        return {f["id"]: f for f in self._buscar(q).json()["resultados"]}

    def test_quien_no_tiene_el_rol_viene_sumable_y_enmascarado(self):
        fila = self._filas("Sumable")[self.ana.pk]
        self.assertTrue(fila["sumable"])
        self.assertFalse(fila["asignable"])
        self.assertEqual(fila["motivo"], MOTIVO_SUMABLE)
        self.assertEqual(fila["dni"], "30.***.888")
        self.assertEqual(fila["email"], "a***@example.com")

    def test_el_agente_con_el_rol_no_es_sumable(self):
        fila = self._filas("Quiroga")[self.carla.pk]
        self.assertFalse(fila["sumable"])
        self.assertTrue(fila["asignable"])

    def test_no_aparecen_superusuarios_ciudadanos_ni_inactivos_sin_rol(self):
        superu = self._persona("superu", "Sara", "Excluida", "30111001", "superu@example.com")
        superu.is_superuser = True
        superu.save()
        ciudadano = self._persona("ciud", "Cira", "Excluida", "30111002", "ciud@example.com")
        ciudadano.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        inactivo = self._persona("inact", "Ines", "Excluida", "30111003", "inact@example.com")
        inactivo.is_active = False
        inactivo.save()
        self.assertEqual(set(self._filas("Excluida")), set())

    def test_dni_y_correo_exactos_tambien_para_los_sumables(self):
        self.assertEqual(set(self._filas("30.999.888")), {self.ana.pk})
        self.assertEqual(set(self._filas("ANA@example.com")), {self.ana.pk})
        self.assertEqual(set(self._filas("3099")), set())
        self.assertEqual(set(self._filas("ana@exam")), set())

    def test_el_tope_de_diez_se_mantiene_con_sumables(self):
        for n in range(12):
            self._persona(f"mas{n}", "Mara", f"Lopez{n:02d}", f"3022{n:04d}", f"mas{n}@example.com")
        cuerpo = self._buscar("Lopez").json()
        self.assertEqual(len(cuerpo["resultados"]), 10)
        self.assertTrue(cuerpo["hay_mas"])

    def test_el_personal_del_edificio_viene_sumable_con_su_motivo(self):
        propio = self._persona("propio", "Pablo", "Personal", "30111555", "propio@example.com")
        rol_institucion = Group.objects.create(name="Rol institucion personal")
        RolMeta.objects.create(
            grupo=rol_institucion, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True
        )
        propio.groups.add(rol_institucion)
        AsignacionDispositivo.objects.create(dispositivo=self.parador, rol=rol_institucion, activo=True)
        fila = self._filas("Personal")[propio.pk]
        self.assertTrue(fila["sumable"])
        self.assertEqual(fila["motivo"], MOTIVO_SUMABLE_PERSONAL)

    def test_buscar_sigue_sin_dar_nada(self):
        antes = self._foto()
        self._buscar("Sumable")
        self.assertEqual(antes, self._foto())


class SumarTests(BaseSumarAgente):
    def test_suma_exactamente_el_grupo_de_agente_y_nada_mas(self):
        antes = self._foto()
        respuesta = self._sumar(self.ana.pk)

        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["ok"])
        self.assertTrue(cuerpo["sumado"])
        self.assertTrue(cuerpo["asignable"])
        self.assertEqual(cuerpo["user"], {"id": self.ana.pk, "label": "Ana Sumable"})
        ana = User.objects.get(pk=self.ana.pk)
        self.assertEqual(set(ana.groups.values_list("pk", flat=True)), {self.rol_agente.pk})
        # Ningún permiso directo, ni cambio de contraseña, correo o flags; los grupos no cambian de contenido.
        self.assertFalse(ana.user_permissions.exists())
        self.assertFalse(ana.is_staff or ana.is_superuser)
        despues = self._foto()
        self.assertEqual(antes[0], despues[0])
        cambiados = {u for u in despues[1] if u not in antes[1]}
        self.assertEqual({u[0] for u in cambiados}, {self.ana.pk})
        original = next(u for u in antes[1] if u[0] == self.ana.pk)
        nuevo = next(u for u in despues[1] if u[0] == self.ana.pk)
        self.assertEqual((original[2], original[3]), (nuevo[2], nuevo[3]))
        self.assertIn(ana, set(agentes_asignables(self.predio)))

    def test_conserva_los_otros_roles_que_ya_tenia(self):
        otro = Group.objects.create(name="Rol previo")
        self.ana.groups.add(otro)
        self._sumar(self.ana.pk)
        self.assertEqual(
            set(User.objects.get(pk=self.ana.pk).groups.values_list("pk", flat=True)), {otro.pk, self.rol_agente.pk}
        )

    def test_es_idempotente_si_ya_es_agente(self):
        respuesta = self._sumar(self.carla.pk)
        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(respuesta.json()["sumado"])
        self.assertTrue(respuesta.json()["asignable"])
        self.assertEqual(self.carla.groups.filter(pk=self.rol_agente.pk).count(), 1)
        self._sumar(self.ana.pk)
        self._sumar(self.ana.pk)
        self.assertEqual(self.ana.groups.filter(pk=self.rol_agente.pk).count(), 1)

    def test_el_personal_del_edificio_recibe_el_rol_pero_no_es_asignable(self):
        propio = self._persona("propio", "Pablo", "Personal", "30111555", "propio@example.com")
        rol_institucion = Group.objects.create(name="Rol institucion personal")
        RolMeta.objects.create(
            grupo=rol_institucion, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True
        )
        propio.groups.add(rol_institucion)
        AsignacionDispositivo.objects.create(dispositivo=self.parador, rol=rol_institucion, activo=True)

        respuesta = self._sumar(propio.pk)

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["sumado"])
        self.assertFalse(respuesta.json()["asignable"])
        self.assertIn("no se le puede asignar", respuesta.json()["message"])
        self.assertTrue(propio.groups.filter(pk=self.rol_agente.pk).exists())
        self.assertNotIn(propio, set(agentes_asignables(self.predio)))

    def test_deja_traza_sin_datos_personales(self):
        with self.assertLogs("programas.services.sumar_agente", level=logging.INFO) as registro:
            self._sumar(self.ana.pk)
        texto = "\n".join(registro.output)
        self.assertIn(f"operador_id={self.creador.pk}", texto)
        self.assertIn(f"usuario_id={self.ana.pk}", texto)
        for dato in ("Ana", "Sumable", "30999888", "ana@example.com"):
            self.assertNotIn(dato, texto)


class RechazosTests(BaseSumarAgente):
    def _rechaza(self, usuario, estado):
        antes = self._foto()
        respuesta = self._sumar(usuario.pk)
        self.assertEqual(respuesta.status_code, estado, respuesta.content)
        self.assertFalse(respuesta.json()["ok"])
        self.assertEqual(antes, self._foto())

    def test_inactivo_es_409(self):
        self.ana.is_active = False
        self.ana.save()
        self._rechaza(self.ana, 409)

    def test_superusuario_es_403(self):
        self.ana.is_superuser = True
        self.ana.save()
        self._rechaza(self.ana, 403)

    def test_ciudadano_del_portal_es_403(self):
        self.ana.groups.add(Group.objects.create(name=rbac.GRUPO_CIUDADANO_PORTAL))
        self._rechaza(self.ana, 403)

    def test_usuario_inexistente_o_id_invalido_es_403(self):
        self.assertEqual(self._sumar(99999).status_code, 403)
        self.assertEqual(self._sumar("abc").status_code, 403)

    def test_si_el_rol_de_agente_no_esta_disponible_es_409(self):
        meta = self.rol_agente.meta
        meta.activo = False
        meta.save()
        self._rechaza(self.ana, 409)

    def test_si_el_rol_de_agente_tiene_programa_configurar_no_se_reparte(self):
        self.rol_agente.permissions.add(_permiso("programa.configurar"))
        self._rechaza(self.ana, 409)


class EndpointTests(BaseSumarAgente):
    def test_sin_la_capacidad_es_403_y_no_suma(self):
        usuario = self._usuario("sin_cap", ("inspeccion.asignar", "dispositivo.ver"), [self.parador])
        self.assertEqual(self._sumar(self.ana.pk, operador=usuario).status_code, 403)
        self.assertFalse(self.ana.groups.exists())

    def test_la_capacidad_en_otro_programa_es_403(self):
        usuario = self._usuario("cap_ajena", ("inspeccion.asignar", "dispositivo.ver"), [self.parador])
        usuario.groups.add(self._con_capacidad_en_otro_programa("sumar"))
        usuario = User.objects.get(pk=usuario.pk)
        self.assertEqual(self._sumar(self.ana.pk, operador=usuario).status_code, 403)
        self.assertFalse(self.ana.groups.exists())

    def test_un_edificio_fuera_de_alcance_o_inexistente_es_403(self):
        self.assertEqual(self._sumar(self.ana.pk, edificio=self.edificio_cis).status_code, 403)
        self.assertEqual(self._sumar(self.ana.pk, edificio=False, edificio_id="99999").status_code, 403)
        self.assertFalse(self.ana.groups.exists())

    def test_sin_edificio_es_400(self):
        self.assertEqual(self._sumar(self.ana.pk, edificio=False).status_code, 400)

    def test_solo_post(self):
        self.assertEqual(self._cliente(self.creador).get(self.url_sumar).status_code, 405)

    def test_anonimo_no_entra(self):
        from django.test import Client

        self.assertIn(Client().post(self.url_sumar, {"user_id": self.ana.pk}).status_code, (302, 401, 403))
        self.assertFalse(self.ana.groups.exists())

    def test_exige_csrf(self):
        from django.test import Client

        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.creador)
        respuesta = cliente.post(self.url_sumar, {"user_id": self.ana.pk, "edificio_id": self.predio.pk})
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(self.ana.groups.exists())

    def test_limite_por_operador(self):
        estados = [self._sumar(self.carla.pk).status_code for _ in range(21)]
        self.assertEqual(estados[:20], [200] * 20)
        self.assertEqual(estados[20], 429)
        otro = self._usuario(
            "creador2", ("inspeccion.asignar", "inspeccion.agente.crear", "dispositivo.ver"), [self.parador]
        )
        self.assertEqual(self._sumar(self.carla.pk, operador=otro).status_code, 200)


class ModalTests(BaseSumarAgente):
    def test_el_modal_trae_la_url_de_sumar_y_el_texto_de_confirmacion(self):
        usuario = self._usuario(
            "creador_total",
            ("inspeccion.asignar", "inspeccion.agente.crear", "dispositivo.ver"),
            [self.parador, self.cis],
        )
        respuesta = self._cliente(usuario).get(reverse("dispositivos:relevamientos"), {"asignar": self.edificio_cis.pk})
        self.assertContains(respuesta, f'data-action-agente-sumar="{self.url_sumar}"')
        self.assertContains(respuesta, "Sumar como agente")
        self.assertContains(respuesta, "Va a poder ver los relevamientos que le asignen.")
