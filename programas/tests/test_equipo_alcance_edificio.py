"""Alcance por edificio del Equipo de un dispositivo: un solo dueño y cada punto de aplicación (Cambio 523).

El dueño es `programas.services.dispositivos` (`alcance_de_edificios` para un objeto,
`q_edificios_en_alcance` para listas). Con alcance Edificios se ve y se opera lo de esos edificios;
lo ajeno responde 404, y la institución (legajo, kits, edificios) queda en solo lectura.

1. Función central: fila Institución, fila Edificios, varias filas, edificio desvinculado.
2. Puntos de aplicación: sectores, plazas, ingreso, derivación por edificio, legajo, kits.
3. Servicio del Equipo: RN2 (Edificios exige edificio vinculado) y RN6 (responsable acotado).
4. Un solo dueño: ninguna vista, selector o servicio arma el filtro de edificio por fuera.
"""

import re
from datetime import time
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse

from core import rbac
from core.views.media import _autorizar
from legajos.models import Ciudadano
from programas.models import (
    AdjuntoRespuestaIngreso,
    DisenoFormulario,
    Edificio,
    EntradaBitacora,
    EntregaKit,
    MiembroEquipoDispositivo,
    MomentoFormulario,
    Plaza,
    RespuestasIngresoEstadia,
    Sector,
)
from programas.selectors import kits as selectores_kits
from programas.services import equipo_dispositivo as equipo
from programas.services import kits as servicio_kits
from programas.services.bitacora import corregir_entrada, crear_turno, editar_turno, registrar_entrada
from programas.services.detalle_dispositivo import eventos_de_historial
from programas.services.dispositivos import (
    alcance_de_edificios,
    puede_editar_legajo,
    puede_operar_edificio,
    puede_operar_institucion,
    puede_operar_plaza,
    q_edificios_en_alcance,
)
from programas.services.estadias import ingresar_persona, verificar_alojamiento_en_red
from programas.tests.test_dispositivos_bitacora_pantalla import MARTES, MIERCOLES, TODO, BasePantalla, _local, _reloj
from users.models import RolMeta

Alcance = MiembroEquipoDispositivo.Alcance
RAIZ = Path(__file__).resolve().parents[1]


class BaseAlcance(BasePantalla):
    """El CIS con dos edificios (A y B), un sector con una plaza en cada uno, y gente con distinto alcance."""

    def setUp(self):
        super().setUp()
        self.edif_a = self._edificio("ED-A")
        self.edif_b = self._edificio("ED-B")
        Sector.objects.filter(pk=self.sector.pk).update(edificio=self.edif_a)
        self.sector_a = Sector.objects.get(pk=self.sector.pk)
        self.sector_b = Sector.objects.create(dispositivo=self.cis, nombre="Mujeres", capacidad=2, edificio=self.edif_b)
        self.plaza_a = Plaza.objects.select_related("sector").get(pk=self.p1.pk)
        self.plaza_b = Plaza.objects.create(sector=self.sector_b, codigo="B-01")
        self.de_a = self._miembro("De A", Alcance.EDIFICIOS, [self.edif_a])
        self.de_inst = self._miembro("De institucion", Alcance.INSTITUCION)

    def _edificio(self, codigo):
        edificio = Edificio.objects.create(codigo=codigo, nombre=f"Edificio {codigo}")
        edificio.dispositivos.add(self.cis)
        return edificio

    def _miembro(self, nombre, alcance, edificios=(), capacidades=TODO):
        usuario = self._usuario(nombre, self.cis, capacidades)
        fila = MiembroEquipoDispositivo.objects.get(usuario=usuario)
        fila.alcance = alcance
        fila.save(update_fields=["alcance"])
        fila.edificios.set(edificios)
        return usuario

    def _segunda_fila(self, usuario, nombre, alcance, edificios=()):
        """Otra fila del Equipo del mismo usuario, con otro rol que tiene las mismas capacidades."""

        primera = MiembroEquipoDispositivo.objects.get(usuario=usuario)
        rol = Group.objects.create(name=nombre)
        rol.permissions.add(*primera.rol.permissions.all())
        RolMeta.objects.create(grupo=rol, categoria=rbac.CATEGORIA_PROGRAMA, programa=self.programa, activo=True)
        usuario.groups.add(rol)
        fila = MiembroEquipoDispositivo.objects.create(dispositivo=self.cis, usuario=usuario, rol=rol, alcance=alcance)
        fila.edificios.set(edificios)
        return User.objects.get(pk=usuario.pk)


class FuncionCentralTests(BaseAlcance):
    def _ids(self, usuario, capacidad="dispositivo.ver"):
        alcance = alcance_de_edificios(User.objects.get(pk=usuario.pk), self.cis, capacidad)
        return "todo" if alcance.todo else set(alcance.edificios)

    def test_edificios_ve_solo_los_suyos_e_institucion_ve_todo(self):
        self.assertEqual(self._ids(self.de_a), {self.edif_a.pk})
        self.assertEqual(self._ids(self.de_inst), "todo")

    def test_fila_sin_alcance_cargado_es_toda_la_institucion(self):
        MiembroEquipoDispositivo.objects.filter(usuario=self.de_a).update(alcance=None)
        self.assertEqual(self._ids(self.de_a), "todo")

    def test_desvincular_su_unico_edificio_lo_deja_sin_nada_y_no_cae_a_la_institucion(self):
        self.edif_a.dispositivos.remove(self.cis)
        self.assertEqual(self._ids(self.de_a), set())
        self.assertFalse(puede_operar_edificio(self.de_a, self.cis, self.edif_a.pk, "dispositivo.ver"))

    def test_dos_filas_una_institucion_y_otra_edificios_ve_todo(self):
        usuario = self._segunda_fila(self.de_a, "Rol inst", Alcance.INSTITUCION)
        self.assertEqual(self._ids(usuario), "todo")

    def test_dos_filas_edificios_es_la_union(self):
        edif_c = self._edificio("ED-C")
        usuario = self._segunda_fila(self.de_a, "Rol C", Alcance.EDIFICIOS, [edif_c])
        self.assertEqual(self._ids(usuario), {self.edif_a.pk, edif_c.pk})

    def test_sin_la_capacidad_no_alcanza_nada(self):
        sin_ver = self._miembro("Sin ver", Alcance.INSTITUCION, capacidades=("dispositivo.admitir",))
        self.assertEqual(self._ids(sin_ver), set())

    def test_edificio_sin_dato_no_entra_con_alcance_edificios(self):
        self.assertFalse(puede_operar_edificio(self.de_a, self.cis, None, "dispositivo.ver"))
        self.assertTrue(puede_operar_edificio(self.de_inst, self.cis, None, "dispositivo.ver"))

    def test_la_q_de_listas_coincide_con_la_funcion_por_objeto(self):
        for usuario in (self.de_a, self.de_inst):
            fresco = User.objects.get(pk=usuario.pk)
            filtro = q_edificios_en_alcance(fresco, "dispositivo.ver", "dispositivo_id", "edificio_id")
            con_q = set(Sector.objects.filter(filtro).values_list("pk", flat=True))
            esperado = {
                s.pk
                for s in Sector.objects.all()
                if puede_operar_edificio(fresco, s.dispositivo, s.edificio_id, "dispositivo.ver")
            }
            self.assertEqual(con_q, esperado, usuario.username)


class PuntosDeAplicacionTests(BaseAlcance):
    def _get(self, usuario, nombre, *args, **params):
        self.client.force_login(usuario)
        return self.client.get(reverse(f"dispositivos:{nombre}", args=args), params)

    def _post(self, usuario, nombre, *args, **datos):
        self.client.force_login(usuario)
        return self.client.post(reverse(f"dispositivos:{nombre}", args=args), datos)

    def test_sectores_muestra_los_del_edificio_alcanzado_y_no_los_ajenos(self):
        respuesta = self._get(self.de_a, "sectores", self.cis.pk)
        self.assertContains(respuesta, "Varones")
        self.assertNotContains(respuesta, "Mujeres")
        total = self._get(self.de_inst, "sectores", self.cis.pk)
        self.assertContains(total, "Varones")
        self.assertContains(total, "Mujeres")

    def test_plaza_de_otro_edificio_por_url_directa_es_404_igual_que_inexistente(self):
        ajena = self._post(self.de_a, "plaza_editar", self.cis.pk, self.plaza_b.pk)
        inexistente = self._post(self.de_a, "plaza_editar", self.cis.pk, 999999)
        propia = self._post(self.de_a, "plaza_editar", self.cis.pk, self.plaza_a.pk)
        self.assertEqual((ajena.status_code, inexistente.status_code), (404, 404))
        self.assertNotEqual(propia.status_code, 404)

    def test_ingresar_a_una_plaza_de_otro_edificio_se_rechaza(self):
        persona = Ciudadano.objects.create(dni="30555666", nombre="Eva", apellido="Soto")
        momento = _local(MARTES, 10)
        with self.assertRaises(PermissionDenied):
            ingresar_persona(
                ciudadano=persona,
                dispositivo=self.cis,
                plaza=self.plaza_b,
                usuario=self.de_a,
                fecha_ingreso=momento,
            )
        libre_a = Plaza.objects.select_related("sector").create(sector=self.sector_a, codigo="A-09")
        estadia = ingresar_persona(
            ciudadano=persona,
            dispositivo=self.cis,
            plaza=libre_a,
            usuario=self.de_a,
            fecha_ingreso=momento,
        )
        self.assertEqual(estadia.plaza_id, libre_a.pk)

    def test_puede_operar_plaza_sigue_el_edificio_del_sector(self):
        self.assertTrue(puede_operar_plaza(self.de_a, self.cis, self.plaza_a, "dispositivo.ver"))
        self.assertFalse(puede_operar_plaza(self.de_a, self.cis, self.plaza_b, "dispositivo.ver"))
        self.assertTrue(puede_operar_plaza(self.de_inst, self.cis, self.plaza_b, "dispositivo.ver"))

    def test_derivacion_se_opera_por_su_edificio(self):
        self.assertTrue(puede_operar_edificio(self.de_a, self.cis, self.edif_a.pk, "dispositivo.admitir"))
        self.assertFalse(puede_operar_edificio(self.de_a, self.cis, self.edif_b.pk, "dispositivo.admitir"))

    def test_el_legajo_y_los_kits_son_de_la_institucion_completa(self):
        self.assertFalse(puede_editar_legajo(self.de_a, self.cis))
        self.assertFalse(puede_operar_institucion(self.de_a, self.cis, "dispositivo.ver"))
        self.assertTrue(puede_editar_legajo(self.de_inst, self.cis))
        self.assertTrue(puede_operar_institucion(self.de_inst, self.cis, "dispositivo.ver"))

    def test_la_institucion_sigue_en_el_detalle(self):
        self.assertEqual(self._get(self.de_a, "detalle", self.cis.pk).status_code, 200)


class KitsPorEdificioTests(BaseAlcance):
    """Las entregas de kits llevan edificio: se ven y se reciben solo las de los edificios alcanzados."""

    def setUp(self):
        super().setUp()
        capacidades = (*TODO, "emergencia.recibir_kit")
        self.recibe_a = self._miembro("Recibe A", Alcance.EDIFICIOS, [self.edif_a], capacidades)
        self.recibe_inst = self._miembro("Recibe inst", Alcance.INSTITUCION, capacidades=capacidades)
        self.entrega_a = self._entrega("2026-K-000001", self.edif_a)
        self.entrega_b = self._entrega("2026-K-000002", self.edif_b)
        self.entrega_sin = self._entrega("2026-K-000003", None)

    def _entrega(self, numero, edificio):
        return EntregaKit.objects.create(
            numero=numero,
            dispositivo=self.cis,
            edificio=edificio,
            estado=EntregaKit.Estado.EN_CAMINO,
            armada_por=self.operador,
        )

    def _ids(self, consulta):
        return set(consulta.values_list("numero", flat=True))

    def test_alcance_edificios_ve_solo_las_de_sus_edificios(self):
        fresco = User.objects.get(pk=self.recibe_a.pk)
        self.assertEqual(self._ids(selectores_kits.entregas_al_alcance(fresco)), {"2026-K-000001"})
        self.assertEqual(self._ids(selectores_kits.entregas_pendientes_de(self.cis, fresco)), {"2026-K-000001"})
        self.assertEqual(self._ids(selectores_kits.entregas_de(self.cis, fresco)), {"2026-K-000001"})

    def test_alcance_institucion_ve_todas_incluida_la_sin_edificio(self):
        fresco = User.objects.get(pk=self.recibe_inst.pk)
        self.assertEqual(len(selectores_kits.entregas_al_alcance(fresco)), 3)
        self.assertEqual(len(selectores_kits.entregas_pendientes_de(self.cis, fresco)), 3)

    def test_recepcion_por_edificio_y_la_sin_edificio_solo_con_institucion(self):
        self.assertTrue(servicio_kits.puede_recibir(self.recibe_a, self.entrega_a))
        self.assertFalse(servicio_kits.puede_recibir(self.recibe_a, self.entrega_b))
        self.assertFalse(servicio_kits.puede_recibir(self.recibe_a, self.entrega_sin))
        self.assertTrue(servicio_kits.puede_recibir(self.recibe_inst, self.entrega_sin))

    def test_el_conteo_de_mis_dispositivos_respeta_el_edificio(self):
        fila = [
            f for f in selectores_kits.mis_dispositivos(User.objects.get(pk=self.recibe_a.pk)) if f["id"] == self.cis.pk
        ]
        self.assertEqual(fila[0]["entregas_pendientes"], 1)

    def test_el_edificio_de_una_entrega_nueva_sale_del_pedido_de_la_que_repone_o_del_unico(self):
        destino = self.cis
        self.assertEqual(servicio_kits._edificio_de_la_entrega(destino, self.edif_b, None), self.edif_b.pk)
        self.assertEqual(servicio_kits._edificio_de_la_entrega(destino, None, self.entrega_a), self.edif_a.pk)
        # Con dos edificios y sin origen, queda vacío.
        self.assertIsNone(servicio_kits._edificio_de_la_entrega(destino, None, None))
        # Con uno solo, es ese.
        self.edif_b.dispositivos.remove(self.cis)
        self.assertEqual(servicio_kits._edificio_de_la_entrega(destino, None, None), self.edif_a.pk)
        # Un edificio ajeno al destino se rechaza.
        with self.assertRaises(ValidationError):
            servicio_kits._edificio_de_la_entrega(destino, self.edif_b, None)


class ServicioDelEquipoTests(BaseAlcance):
    def setUp(self):
        super().setUp()
        self.rol = Group.objects.get(name="De institucion")
        # Quien arma el Equipo: un responsable de Edificios {A} y otro de toda la institución.
        self.resp_a = self._miembro("Resp A", Alcance.EDIFICIOS, [self.edif_a])
        self.resp_inst = self._miembro("Resp inst", Alcance.INSTITUCION)
        MiembroEquipoDispositivo.objects.filter(usuario__in=[self.resp_a, self.resp_inst]).update(es_responsable=True)
        self.nuevo = User.objects.create_user(username="nuevo", password="x")

    def _sumar(self, actor, **kw):
        # Los pares (persona, rol) sumables son otra regla (Cambio 414): acá solo se mide el alcance.
        with mock.patch.object(equipo, "_exigir_pares_sumables"):
            return equipo.sumar_miembro(actor=actor, dispositivo=self.cis, usuario=self.nuevo, rol=self.rol, **kw)

    def test_edificios_exige_al_menos_un_edificio(self):
        with self.assertRaises(ValidationError):
            self._sumar(self.resp_inst, alcance=Alcance.EDIFICIOS, edificios=[])

    def test_edificios_exige_que_esten_vinculados_a_la_institucion(self):
        ajeno = Edificio.objects.create(codigo="ED-Z", nombre="Ajeno")
        with self.assertRaises(ValidationError):
            self._sumar(self.resp_inst, alcance=Alcance.EDIFICIOS, edificios=[ajeno])

    def test_el_responsable_de_institucion_suma_con_alcance_edificios(self):
        miembro = self._sumar(self.resp_inst, alcance=Alcance.EDIFICIOS, edificios=[self.edif_b])
        self.assertEqual(miembro.alcance, Alcance.EDIFICIOS)
        self.assertEqual(set(miembro.edificios.values_list("pk", flat=True)), {self.edif_b.pk})

    def test_el_responsable_de_edificios_suma_solo_dentro_de_los_suyos(self):
        with self.assertRaises(PermissionDenied):
            self._sumar(self.resp_a, alcance=Alcance.EDIFICIOS, edificios=[self.edif_b])
        with self.assertRaises(PermissionDenied):
            self._sumar(self.resp_a, alcance=Alcance.INSTITUCION)
        miembro = self._sumar(self.resp_a, alcance=Alcance.EDIFICIOS, edificios=[self.edif_a])
        self.assertEqual(set(miembro.edificios.values_list("pk", flat=True)), {self.edif_a.pk})

    def test_el_responsable_de_edificios_no_edita_a_alguien_de_otro_edificio(self):
        ajeno = self._sumar(self.resp_inst, alcance=Alcance.EDIFICIOS, edificios=[self.edif_b])
        with self.assertRaises(PermissionDenied):
            equipo.dar_de_baja(actor=self.resp_a, miembro=ajeno)
        with self.assertRaises(PermissionDenied):
            equipo.marcar_responsable(actor=self.resp_a, miembro=ajeno)


class CorreccionesDeAuditoriaTests(BaseAlcance):
    """Los cinco MAJOR de la auditoría del PR: cada uno con su escenario (y su mutación)."""

    def setUp(self):
        super().setUp()
        self.rol = Group.objects.get(name="De institucion")
        self.resp_a = self._miembro("Resp A", Alcance.EDIFICIOS, [self.edif_a])
        MiembroEquipoDispositivo.objects.filter(usuario=self.resp_a).update(es_responsable=True)
        self.resp_inst = self._miembro("Resp inst", Alcance.INSTITUCION)
        MiembroEquipoDispositivo.objects.filter(usuario=self.resp_inst).update(es_responsable=True)

    def _ver(self, usuario, url):
        self.client.force_login(usuario)
        with _reloj():
            return self.client.get(url)

    def _fresco(self, usuario):
        return User.objects.get(pk=usuario.pk)

    def _pdf(self, nombre="c.pdf"):
        return SimpleUploadedFile(nombre, b"%PDF-1.4\n", content_type="application/pdf")

    # 1. sumar_miembro sobre una fila existente
    def _sumar(self, actor, usuario, **kw):
        # El mismo rol que ya tiene: «volver a sumar» es sobre la fila existente.
        rol = MiembroEquipoDispositivo.objects.filter(usuario=usuario).first().rol
        with mock.patch.object(equipo, "_exigir_pares_sumables"):
            return equipo.sumar_miembro(actor=actor, dispositivo=self.cis, usuario=usuario, rol=rol, **kw)

    def test_volver_a_sumar_a_alguien_de_otro_edificio_no_lo_toca(self):
        ajeno = self._miembro("Ajeno B", Alcance.EDIFICIOS, [self.edif_b])
        with self.assertRaises(PermissionDenied):
            self._sumar(self.resp_a, ajeno, alcance=Alcance.EDIFICIOS, edificios=[self.edif_a])
        fila = MiembroEquipoDispositivo.objects.get(usuario=ajeno)
        self.assertEqual(set(fila.edificios.values_list("pk", flat=True)), {self.edif_b.pk})

    def test_volver_a_sumar_a_alguien_de_institucion_no_lo_pasa_a_mis_edificios(self):
        with self.assertRaises(PermissionDenied):
            self._sumar(self.resp_a, self.de_inst, alcance=Alcance.EDIFICIOS, edificios=[self.edif_a])
        self.assertEqual(MiembroEquipoDispositivo.objects.get(usuario=self.de_inst).alcance, Alcance.INSTITUCION)

    def test_volver_a_sumar_sin_alcance_no_deja_a_un_miembro_de_edificios_en_toda_la_institucion(self):
        self._sumar(self.resp_inst, self.de_a)
        fila = MiembroEquipoDispositivo.objects.get(usuario=self.de_a)
        self.assertEqual(fila.alcance, Alcance.EDIFICIOS)
        self.assertEqual(set(fila.edificios.values_list("pk", flat=True)), {self.edif_a.pk})

    def test_reactivar_a_alguien_de_baja_si_toma_el_alcance_nuevo(self):
        MiembroEquipoDispositivo.objects.filter(usuario=self.de_a).update(activo=False)
        self._sumar(self.resp_inst, self.de_a, alcance=Alcance.EDIFICIOS, edificios=[self.edif_b])
        fila = MiembroEquipoDispositivo.objects.get(usuario=self.de_a)
        self.assertTrue(fila.activo)
        self.assertEqual(set(fila.edificios.values_list("pk", flat=True)), {self.edif_b.pk})

    # 2. recepción de kits por URL directa
    def test_recibir_una_entrega_de_otro_edificio_por_url_directa_es_404(self):
        recibe_a = self._miembro("Recibe A", Alcance.EDIFICIOS, [self.edif_a], (*TODO, "emergencia.recibir_kit"))
        entregas = {
            letra: EntregaKit.objects.create(
                numero=f"2026-K-0000{n}",
                dispositivo=self.cis,
                edificio=edificio,
                estado=EntregaKit.Estado.EN_CAMINO,
                armada_por=self.operador,
            )
            for n, (letra, edificio) in enumerate((("a", self.edif_a), ("b", self.edif_b)), 11)
        }

        def url(letra):
            return reverse("emergencia:dispositivo_kit_recibir", args=[self.cis.pk, entregas[letra].pk])

        self.assertEqual(self._ver(recibe_a, url("a")).status_code, 200)
        self.assertEqual(self._ver(recibe_a, url("b")).status_code, 404)

    # 3. archivos del formulario de una estadía
    def test_el_adjunto_del_formulario_de_una_estadia_sigue_el_edificio_de_su_plaza(self):
        diseno = DisenoFormulario.objects.create(tipo_dispositivo=self.tipo, momento=MomentoFormulario.INGRESO)
        persona = Ciudadano.objects.create(dni="30999111", nombre="Bea", apellido="Paz")
        estadia_b = self._ingresar(persona, self.plaza_b, _local(MARTES, 11))
        fila = RespuestasIngresoEstadia.objects.create(estadia=estadia_b, diseno=diseno)
        adjunto = AdjuntoRespuestaIngreso.objects.create(respuestas=fila, clave="c", archivo=self._pdf())
        self.assertIsNone(_autorizar(self._fresco(self.de_a), adjunto.archivo.name))
        self.assertIs(_autorizar(self._fresco(self.de_inst), adjunto.archivo.name), True)

    # 4. Historial: la regla vive en el servicio
    def test_el_historial_se_vacia_en_el_servicio_sin_alcance_total(self):
        self.assertEqual(eventos_de_historial(self.cis, 1, self._fresco(self.de_a))[1], [])
        self.assertNotEqual(eventos_de_historial(self.cis, 1, self._fresco(self.de_inst))[1], [])

    # 5. bitácora de la institución
    def test_la_bitacora_no_muestra_entradas_a_quien_solo_tiene_edificios(self):
        entrada = self._cargar(_local(MIERCOLES, 15), texto="Novedad de toda la casa")
        detalle = reverse("dispositivos:bitacora_entrada", args=[self.cis.pk, entrada.pk])
        self.assertNotContains(self._ver(self.de_a, self.url), "Novedad de toda la casa")
        self.assertEqual(self._ver(self.de_a, detalle).status_code, 404)
        self.assertContains(self._ver(self.de_inst, self.url), "Novedad de toda la casa")
        self.assertEqual(self._ver(self.de_inst, detalle).status_code, 200)

    def test_el_adjunto_de_la_bitacora_es_de_la_institucion_completa(self):
        entrada = self._cargar(_local(MIERCOLES, 15), adjuntos=[self._pdf("acta.pdf")])
        ruta = entrada.adjuntos.get().archivo.name
        self.assertIsNone(_autorizar(self._fresco(self.de_a), ruta))
        self.assertIs(_autorizar(self._fresco(self.de_inst), ruta), True)

    def test_configurar_turnos_pide_toda_la_institucion(self):
        de_a = self._fresco(self.de_a)
        with self.assertRaises(PermissionDenied):
            editar_turno(turno=self.manana, usuario=de_a, nombre="X")
        with self.assertRaises(PermissionDenied):
            crear_turno(dispositivo=self.cis, usuario=de_a, nombre="Nuevo", hora_desde=time(1), hora_hasta=time(2))
        editar_turno(turno=self.manana, usuario=self._fresco(self.de_inst), nombre="Mañana")

    def test_corregir_una_novedad_sin_leer_la_bitacora_da_403_y_no_crea_version(self):
        entrada = self._cargar(_local(MIERCOLES, 15), texto="Novedad de toda la casa")
        self.client.force_login(self._fresco(self.de_a))
        with _reloj():
            respuesta = self.client.post(
                reverse("dispositivos:bitacora_corregir", args=[self.cis.pk]),
                {"entrada": entrada.pk, "texto": "Pisada", "motivo": "x"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(EntradaBitacora.objects.filter(entrada_original=entrada).count(), 0)
        # Un id que no existe responde igual: la compuerta va antes del formulario y no revela ids.
        with _reloj():
            inexistente = self.client.post(
                reverse("dispositivos:bitacora_corregir", args=[self.cis.pk]),
                {"entrada": 999999, "texto": "x"},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(inexistente.status_code, 403)

    def test_el_servicio_no_corrige_ni_vincula_personas_sin_leer_la_bitacora(self):
        entrada = self._cargar(_local(MIERCOLES, 15), texto="Novedad de toda la casa")
        with self.assertRaises(PermissionDenied):
            corregir_entrada(entrada=entrada, usuario=self._fresco(self.de_a), texto="Pisada")
        estadia = self.estadia_ana
        momento = _local(MIERCOLES, 16)
        with _reloj(momento):
            propia = registrar_entrada(
                dispositivo=self.cis,
                usuario=self._fresco(self.de_a),
                tipo=EntradaBitacora.Tipo.INCIDENTE,
                texto="Desde el edificio A",
                momento=momento,
                personas=[estadia],
            )
        self.assertEqual(propia.personas.count(), 0)

    # MINOR: verificar_alojamiento_en_red
    def test_verificar_alojamiento_no_da_la_plaza_de_otro_edificio(self):
        persona = Ciudadano.objects.create(dni="30999222", nombre="Cora", apellido="Luna")
        self._ingresar(persona, self.plaza_b, _local(MARTES, 12))
        admite = self._miembro("Admite A", Alcance.EDIFICIOS, [self.edif_a])
        resultado = verificar_alojamiento_en_red(persona, self._fresco(admite))
        self.assertTrue(resultado.alojada)
        self.assertFalse(resultado.dentro_del_alcance)


# Líneas (sin sangría) fuera de los dueños que nombran la relación del Equipo con los edificios. Congelada:
# sumar una exige decir por qué no es la regla reescrita.
PERMITIDAS = {}

# Los dueños no se recorren a sí mismos: la función central y el servicio que escribe el alcance.
EXCLUIDOS = {"services/dispositivos.py", "services/equipo_dispositivo.py"}


class UnSoloDuenoTests(SimpleTestCase):
    def test_ninguna_vista_ni_servicio_arma_el_filtro_de_edificio_por_fuera(self):
        patron = re.compile(r"miembros_equipo|MiembroEquipoDispositivo\.Alcance|Alcance\.EDIFICIOS|\"EDIFICIOS\"")
        encontrados = {}
        for carpeta in ("views", "selectors", "services", "api", "forms"):
            base = RAIZ / carpeta
            if not base.exists():
                continue
            for archivo in sorted(base.rglob("*.py")):
                clave = f"{carpeta}/{archivo.relative_to(base).as_posix()}"
                if clave in EXCLUIDOS:
                    continue
                for linea in archivo.read_text(encoding="utf-8").splitlines():
                    if patron.search(linea):
                        encontrados.setdefault(clave, set()).add(linea.strip())
        nuevas = {
            archivo: sorted(lineas - PERMITIDAS.get(archivo, set()))
            for archivo, lineas in encontrados.items()
            if lineas - PERMITIDAS.get(archivo, set())
        }
        self.assertEqual(
            nuevas,
            {},
            "«Qué edificios alcanza el Equipo» vive en programas/services/dispositivos.py "
            "(alcance_de_edificios, q_edificios_en_alcance). Usá esa función.",
        )
        # La lista no acumula líneas que ya no existen.
        sobrantes = {a: sorted(ls - encontrados.get(a, set())) for a, ls in PERMITIDAS.items()}
        self.assertEqual({a: ls for a, ls in sobrantes.items() if ls}, {}, "Líneas de la lista que ya no están")
