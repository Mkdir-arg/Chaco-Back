"""Equipo por persona y alcance de Dispositivos (Cambio 410).

Lo que se fija acá, y cada guarda se verificó con mutación (romperla deja rojo el test):

1. ``dispositivo.ver_todos`` da **ver** todos los dispositivos y nada más.
2. Operar exige ser del Equipo con un rol que tenga la capacidad; un rol sin ella, de otro
   programa o inactivo no habilita; la baja (o perder el rol) quita el acceso.
3. La migración de datos arma el Equipo desde las asignaciones y **no suma agentes**.
4. Solo el admin del programa o un responsable de ese dispositivo arma el Equipo, y no se
   deja sin responsables a quien ya tenía.
"""

from importlib import import_module

from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from core import rbac
from programas.models import (
    AsignacionDispositivo,
    Dispositivo,
    MiembroEquipoDispositivo,
    Programa,
    TipoDispositivo,
)
from programas.services import equipo_dispositivo as equipo
from programas.services.dispositivos import (
    dispositivos_en_alcance,
    dispositivos_visibles,
    puede_operar_dispositivo,
)
from programas.services.inspecciones import CLAVE_ROL_AGENTE
from users.models import Capacidad, RolMeta


def _permiso(codigo):
    tipo = ContentType.objects.get_for_model(Capacidad)
    return Permission.objects.get(codename=rbac.codename_de(codigo), content_type=tipo)


class BaseEquipo(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS",
            defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS},
        )
        self.becas, _ = Programa.objects.get_or_create(
            codigo="BECAS-X", defaults={"nombre": "Becas X", "tipo": Programa.TipoPrograma.BECAS}
        )
        self.tipo = TipoDispositivo.objects.create(codigo="ALBERGUE", nombre="Albergue")
        self.disp_a = self._dispositivo("A-1")
        self.disp_b = self._dispositivo("B-1")

    def _dispositivo(self, codigo):
        return Dispositivo.objects.create(
            tipo=self.tipo, codigo=codigo, nombre=f"Disp {codigo}", estado=Dispositivo.Estado.ACTIVO
        )

    def _rol(self, nombre, capacidades, programa="default", activo=True, clave=None):
        rol = Group.objects.create(name=nombre)
        RolMeta.objects.create(
            grupo=rol,
            categoria=rbac.CATEGORIA_PROGRAMA,
            programa=self.programa if programa == "default" else programa,
            activo=activo,
            clave=clave,
        )
        rol.permissions.add(*[_permiso(c) for c in capacidades])
        return rol

    def _usuario(self, nombre, *roles):
        usuario = User.objects.create_user(username=nombre, password="x")
        usuario.groups.add(*roles)
        return usuario

    def _fresco(self, usuario):
        # `rbac` memoiza las capacidades en el objeto.
        cache.clear()
        return User.objects.get(pk=usuario.pk)

    def _miembro(self, dispositivo, usuario, rol, responsable=False):
        return MiembroEquipoDispositivo.objects.create(
            dispositivo=dispositivo, usuario=usuario, rol=rol, es_responsable=responsable
        )


class VerTodosTests(BaseEquipo):
    def test_ver_todos_ve_todo_pero_no_opera(self):
        rol = self._rol("Lector", ["dispositivo.ver", "dispositivo.ver_todos", "dispositivo.admitir"])
        usuario = self._fresco(self._usuario("lector", rol))

        self.assertEqual(set(dispositivos_visibles(usuario)), {self.disp_a, self.disp_b})
        self.assertTrue(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.ver"))
        # tiene la capacidad de admitir en el programa, pero ver_todos no es operar
        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.admitir"))
        self.assertFalse(dispositivos_en_alcance(usuario, "dispositivo.admitir").exists())

    def test_ver_todos_sin_ver_no_da_nada(self):
        rol = self._rol("SoloTodos", ["dispositivo.ver_todos"])
        usuario = self._fresco(self._usuario("solo_todos", rol))
        self.assertFalse(dispositivos_visibles(usuario).exists())
        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.ver"))

    def test_ver_todos_de_un_rol_de_otro_programa_no_cuenta(self):
        rol = self._rol("Lector Becas", ["dispositivo.ver", "dispositivo.ver_todos"], programa=self.becas)
        usuario = self._fresco(self._usuario("lector_becas", rol))
        self.assertFalse(dispositivos_visibles(usuario).exists())

    def test_sin_ver_todos_ni_equipo_no_ve_nada(self):
        rol = self._rol("Opera", ["dispositivo.ver", "dispositivo.admitir", "ciudadano.ver"])
        usuario = self._fresco(self._usuario("opera", rol))
        self.assertFalse(dispositivos_visibles(usuario).exists())


class AlcanceDelEquipoTests(BaseEquipo):
    def test_el_miembro_opera_solo_donde_esta(self):
        rol = self._rol("Operador", ["dispositivo.ver", "dispositivo.admitir"])
        usuario = self._usuario("op", rol)
        self._miembro(self.disp_a, usuario, rol)
        usuario = self._fresco(usuario)

        self.assertTrue(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.admitir"))
        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_b, "dispositivo.admitir"))
        self.assertEqual(set(dispositivos_en_alcance(usuario, "dispositivo.admitir")), {self.disp_a})

    def test_la_misma_persona_con_roles_distintos_en_dispositivos_distintos(self):
        rol_lee = self._rol("Lee", ["dispositivo.ver"])
        rol_admite = self._rol("Admite", ["dispositivo.ver", "dispositivo.admitir"])
        usuario = self._usuario("doble", rol_lee, rol_admite)
        self._miembro(self.disp_a, usuario, rol_lee)
        self._miembro(self.disp_b, usuario, rol_admite)
        usuario = self._fresco(usuario)

        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.admitir"))
        self.assertTrue(puede_operar_dispositivo(usuario, self.disp_b, "dispositivo.admitir"))

    def test_miembro_con_rol_sin_la_capacidad_no_opera(self):
        con = self._rol("Con", ["dispositivo.ver", "dispositivo.admitir"])
        sin = self._rol("Sin", ["dispositivo.ver"])
        usuario = self._usuario("mixto", con)  # la capacidad la da `con`, el Equipo lo une a `sin`
        usuario.groups.add(sin)
        self._miembro(self.disp_a, usuario, sin)
        usuario = self._fresco(usuario)

        self.assertTrue(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.ver"))
        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.admitir"))

    def test_la_baja_quita_el_acceso(self):
        rol = self._rol("Operador", ["dispositivo.ver"])
        usuario = self._usuario("op", rol)
        miembro = self._miembro(self.disp_a, usuario, rol)
        self.assertTrue(puede_operar_dispositivo(self._fresco(usuario), self.disp_a, "dispositivo.ver"))

        miembro.activo = False
        miembro.save()
        usuario = self._fresco(usuario)
        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.ver"))
        self.assertFalse(dispositivos_visibles(usuario).exists())

    def test_rol_de_otro_programa_no_habilita(self):
        rol = self._rol("Rol Becas", ["dispositivo.ver"], programa=self.becas)
        base = self._rol("Base", ["dispositivo.ver"])  # la capacidad global la da este rol
        usuario = self._usuario("ajeno", rol, base)
        self._miembro(self.disp_a, usuario, rol)
        usuario = self._fresco(usuario)
        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.ver"))
        self.assertFalse(dispositivos_visibles(usuario).exists())

    def test_rol_inactivo_no_habilita(self):
        rol = self._rol("Apagado", ["dispositivo.ver"], activo=False)
        base = self._rol("Base", ["dispositivo.ver"])
        usuario = self._usuario("apagado", rol, base)
        self._miembro(self.disp_a, usuario, rol)
        usuario = self._fresco(usuario)
        self.assertFalse(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.ver"))

    def test_si_la_persona_perdio_el_rol_la_fila_no_habilita(self):
        rol = self._rol("Operador", ["dispositivo.ver"])
        base = self._rol("Base", ["dispositivo.ver"])
        usuario = self._usuario("op", rol, base)
        self._miembro(self.disp_a, usuario, rol)
        usuario.groups.remove(rol)
        self.assertFalse(puede_operar_dispositivo(self._fresco(usuario), self.disp_a, "dispositivo.ver"))

    def test_la_asignacion_de_rol_vieja_sigue_valiendo_en_la_transicion(self):
        rol = self._rol("Viejo", ["dispositivo.ver"])
        usuario = self._usuario("viejo", rol)
        AsignacionDispositivo.objects.create(dispositivo=self.disp_a, rol=rol, activo=True)
        usuario = self._fresco(usuario)
        self.assertTrue(puede_operar_dispositivo(usuario, self.disp_a, "dispositivo.ver"))
        self.assertEqual(set(dispositivos_visibles(usuario)), {self.disp_a})


class ModeloTests(BaseEquipo):
    def test_unico_por_dispositivo_usuario_y_rol_sin_condicion(self):
        unico = next(c for c in MiembroEquipoDispositivo._meta.constraints)
        self.assertIsNone(unico.condition)
        rol = self._rol("R", ["dispositivo.ver"])
        usuario = self._usuario("u", rol)
        self._miembro(self.disp_a, usuario, rol)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._miembro(self.disp_a, usuario, rol)


class MigracionDeDatosTests(BaseEquipo):
    def _correr(self):
        modulo = import_module("programas.migrations.0111_equipo_desde_asignaciones")
        modulo.crear_equipo(django_apps, schema_editor=None)

    def test_arma_el_equipo_desde_las_asignaciones_y_no_suma_agentes(self):
        rol = self._rol("Operador", ["dispositivo.ver"])
        rol_agente = self._rol("Agente", ["inspeccion.relevar"], clave=CLAVE_ROL_AGENTE)
        ana = self._usuario("ana", rol)
        beto = self._usuario("beto", rol)
        agente = self._usuario("agente", rol_agente)
        AsignacionDispositivo.objects.create(dispositivo=self.disp_a, rol=rol, activo=True)
        AsignacionDispositivo.objects.create(dispositivo=self.disp_a, rol=rol_agente, activo=True)
        AsignacionDispositivo.objects.create(dispositivo=self.disp_b, rol=rol, activo=False)

        self._correr()

        self.assertEqual(
            set(MiembroEquipoDispositivo.objects.values_list("dispositivo__codigo", "usuario__username")),
            {("A-1", ana.username), ("A-1", beto.username)},
        )
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=agente).exists())

    def test_es_idempotente(self):
        rol = self._rol("Operador", ["dispositivo.ver"])
        self._usuario("ana", rol)
        AsignacionDispositivo.objects.create(dispositivo=self.disp_a, rol=rol, activo=True)
        self._correr()
        self._correr()
        self.assertEqual(MiembroEquipoDispositivo.objects.count(), 1)


class GestionDelEquipoTests(BaseEquipo):
    def setUp(self):
        super().setUp()
        self.rol_admin = self._rol("Admin Disp", ["programa.configurar", "dispositivo.ver"])
        self.admin = self._fresco(self._usuario("admin_disp", self.rol_admin))
        self.rol_resp = self._rol("Responsable", ["dispositivo.ver"])
        self.rol_op = self._rol("Operador", ["dispositivo.ver", "dispositivo.admitir"])
        self.resp = self._usuario("resp", self.rol_resp)
        self.resp2 = self._usuario("resp2", self.rol_resp)
        self.op = self._usuario("op", self.rol_op)
        self.m_resp = self._miembro(self.disp_a, self.resp, self.rol_resp, responsable=True)

    def test_puede_gestionar_el_admin_y_el_responsable_de_ese_dispositivo(self):
        self.assertTrue(equipo.puede_gestionar_equipo(self.admin, self.disp_a))
        self.assertTrue(equipo.puede_gestionar_equipo(self._fresco(self.resp), self.disp_a))
        self.assertFalse(equipo.puede_gestionar_equipo(self._fresco(self.resp), self.disp_b))

    def test_un_no_responsable_no_gestiona(self):
        self._miembro(self.disp_a, self.op, self.rol_op, responsable=False)
        op = self._fresco(self.op)
        self.assertFalse(equipo.puede_gestionar_equipo(op, self.disp_a))
        with self.assertRaises(PermissionDenied):
            equipo.sumar_miembro(actor=op, dispositivo=self.disp_a, usuario=self.resp2, rol=self.rol_resp)

    def test_un_responsable_dado_de_baja_no_gestiona(self):
        self.m_resp.activo = False
        self.m_resp.save()
        self.assertFalse(equipo.puede_gestionar_equipo(self._fresco(self.resp), self.disp_a))

    def test_sumar_valida_el_rol(self):
        with self.assertRaises(ValidationError):  # la persona no tiene ese rol
            equipo.sumar_miembro(actor=self.admin, dispositivo=self.disp_a, usuario=self.resp2, rol=self.rol_op)
        rol_otro = self._rol("De Becas", ["dispositivo.ver"], programa=self.becas)
        self.resp2.groups.add(rol_otro)
        with self.assertRaises(ValidationError):  # rol de otro programa
            equipo.sumar_miembro(actor=self.admin, dispositivo=self.disp_a, usuario=self.resp2, rol=rol_otro)
        rol_apagado = self._rol("Apagado", ["dispositivo.ver"], activo=False)
        self.resp2.groups.add(rol_apagado)
        with self.assertRaises(ValidationError):  # rol inactivo
            equipo.sumar_miembro(actor=self.admin, dispositivo=self.disp_a, usuario=self.resp2, rol=rol_apagado)
        self.assertFalse(MiembroEquipoDispositivo.objects.filter(usuario=self.resp2).exists())

    def test_el_responsable_suma_y_volver_a_sumar_reactiva(self):
        actor = self._fresco(self.resp)
        m = equipo.sumar_miembro(actor=actor, dispositivo=self.disp_a, usuario=self.op, rol=self.rol_op)
        self.assertTrue(m.activo)
        equipo.dar_de_baja(actor=actor, miembro=m)
        m.refresh_from_db()
        self.assertFalse(m.activo)
        otra = equipo.sumar_miembro(actor=actor, dispositivo=self.disp_a, usuario=self.op, rol=self.rol_op)
        self.assertEqual(otra.pk, m.pk)
        self.assertTrue(otra.activo)
        self.assertEqual(MiembroEquipoDispositivo.objects.filter(usuario=self.op).count(), 1)

    def test_cambiar_rol(self):
        m = equipo.sumar_miembro(actor=self.admin, dispositivo=self.disp_a, usuario=self.op, rol=self.rol_op)
        rol2 = self._rol("Otro", ["dispositivo.ver"])
        self.op.groups.add(rol2)
        m = equipo.cambiar_rol(actor=self.admin, miembro=m, rol_nuevo=rol2)
        self.assertEqual(m.rol, rol2)
        with self.assertRaises(ValidationError):
            equipo.cambiar_rol(actor=self.admin, miembro=m, rol_nuevo=self.rol_admin)

    def test_no_deja_al_dispositivo_sin_responsables(self):
        with self.assertRaises(ValidationError):
            equipo.dar_de_baja(actor=self.admin, miembro=self.m_resp)
        with self.assertRaises(ValidationError):
            equipo.desmarcar_responsable(actor=self.admin, miembro=self.m_resp)
        self.m_resp.refresh_from_db()
        self.assertTrue(self.m_resp.activo and self.m_resp.es_responsable)

        # con otro responsable, ya se puede
        m2 = equipo.sumar_miembro(
            actor=self.admin, dispositivo=self.disp_a, usuario=self.resp2, rol=self.rol_resp, es_responsable=True
        )
        equipo.dar_de_baja(actor=self.admin, miembro=self.m_resp)
        self.m_resp.refresh_from_db()
        self.assertFalse(self.m_resp.activo)
        with self.assertRaises(ValidationError):  # ahora m2 es el único
            equipo.desmarcar_responsable(actor=self.admin, miembro=m2)

    def test_marcar_responsable_exige_estar_activo(self):
        m = equipo.sumar_miembro(actor=self.admin, dispositivo=self.disp_a, usuario=self.op, rol=self.rol_op)
        equipo.marcar_responsable(actor=self.admin, miembro=m)
        m.refresh_from_db()
        self.assertTrue(m.es_responsable)
        equipo.desmarcar_responsable(actor=self.admin, miembro=m)
        equipo.dar_de_baja(actor=self.admin, miembro=m)
        with self.assertRaises(ValidationError):
            equipo.marcar_responsable(actor=self.admin, miembro=m)

    def test_alta_de_dispositivo_exige_responsable(self):
        with self.assertRaises(ValidationError):
            equipo.validar_responsables_al_crear([])
        self.assertEqual(equipo.validar_responsables_al_crear([self.resp, self.resp]), [self.resp])
