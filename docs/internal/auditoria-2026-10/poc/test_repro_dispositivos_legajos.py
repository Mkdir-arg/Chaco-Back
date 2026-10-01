r"""Reproducciones de Dispositivos, Merenderos y Legajos (verificación V3, pasada 2).

Auditoría integral DATAÑACH, oct-2026 (ver el README.md de la carpeta de la auditoría).

CÓMO LEERLO (importante para TDD)
  Cada test AFIRMA EL COMPORTAMIENTO DEFECTUOSO ACTUAL: hoy PASA (verde = el bug existe en
  origin/development @ 917e583). Después del fix, el test correspondiente tiene que FALLAR.
  Para el ciclo TDD del ítem: copiá el test, INVERTÍ la aserción (o escribí el test de la
  sección «Tests a agregar» de la ficha), confirmá que el test invertido FALLA antes del fix
  y PASA después. Este archivo NO se commitea tal cual: se commitea el test invertido, con
  el nombre que pide la ficha.

CÓMO CORRERLO (PowerShell, raíz del repo, en el worktree de la ola)
  $env:PY = "C:\Users\mkdir\Proyectos\Chaco\.venv312\Scripts\python.exe"   # el venv vive en el checkout principal
  $env:DJANGO_SECRET_KEY = "test-key"; $env:PYTEST_RUNNING = "1"; $env:DJANGO_SYNCDB_PROJECT_APPS = "True"
  Copy-Item <este archivo> programas/tests/test_repro_dispositivos_legajos.py
  & $env:PY manage.py test programas.tests.test_repro_dispositivos_legajos -v 2
  (.venv312 = Python 3.12 + Django 5.2.17, igual al CI. No usar el Python global.)

  Para simular MariaDB en DIS-02 el test borra el índice parcial en SQLite
  (DROP INDEX admision_una_estadia_activa_por_dispositivo): es lo que Django omite en MySQL/MariaDB.

QUÉ ID CANÓNICO REPRODUCE CADA CLASE
  A305SQL                                        -> DIS-01 (compila el SQL con el backend mysql sin conectarse: CONVERT_TZ)
  A306DobleAlojamiento                           -> DIS-02 (test_admitir_usa_full_clean_* muestra que la vía admitir SÍ está protegida)
  A307EsperaHuerfana                             -> DIS-03
  A309CierreConAlojados                          -> DIS-04
  A310CamaTomada                                 -> DIS-05
  A311EgresoFuturo                               -> DIS-06
  A312Alertas                                    -> LEG-01 (+ PERF-20 / V4-NEW-05)
  A315Reinscripcion                              -> LEG-02
  A316Vinculos                                   -> LEG-03
  A317A318Adjuntos                               -> LEG-04 / LEG-05
  A319A320A321                                   -> DIS-07 / DIS-08 / DIS-09
  A322                                           -> MER-01 (crea su propio merendero ACTIVO; SUSPENDIDO -> ACTIVO da ValidationError)
  A313A314                                       -> SEC-18 / SEC-19
"""

from datetime import date, datetime, timedelta
from datetime import timezone as dt_tz
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.backends.mysql.base import DatabaseWrapper as MySQLWrapper
from django.db.models.functions import TruncMonth
from django.test import TestCase, override_settings
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from legajos.models import Adjunto, AlertaCiudadano, Ciudadano, LegajoAtencion
from programas.models import (
    Admision,
    Cama,
    DerivacionPrograma,
    Dispositivo,
    EsperaAdmision,
    InscripcionPrograma,
    Merendero,
    Programa,
    RegistroDiario,
    TipoDispositivo,
)
from programas.services.admisiones import (
    admitir_ciudadano,
    egresar_admision,
    poner_en_espera,
    promover_espera,
    trasladar_admision,
)
from programas.services.camas import resumen_ocupacion
from programas.services.dispositivos import cerrar_dispositivo, inactivar_dispositivo
from programas.services.registro_diario import calcular_cantidades
from programas.services.reportes import filtrar_dispositivos


def _mysql():
    from django.db import connections

    conf = dict(connections["default"].settings_dict)
    conf.update(ENGINE="django.db.backends.mysql", NAME="x", USER="x", PASSWORD="", HOST="127.0.0.1", PORT="1")
    conf["OPTIONS"] = {}
    return MySQLWrapper(conf, "mysqlfake")


def _sql(qs):
    sql, params = qs.query.get_compiler(connection=_mysql()).as_sql()
    return sql % tuple(repr(p) for p in params)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.u = User.objects.create_superuser("v3", "v3@x.com", "x")
        cls.programa, _ = Programa.objects.get_or_create(
            codigo="DISPOSITIVOS", defaults={"nombre": "Dispositivos", "tipo": Programa.TipoPrograma.DISPOSITIVOS}
        )
        cls.tipo = TipoDispositivo.objects.create(codigo="T", nombre="T", maneja_camas=True)

    def disp(self, codigo, camas=1):
        d = Dispositivo.objects.create(codigo=codigo, nombre=codigo, tipo=self.tipo, estado=Dispositivo.Estado.ACTIVO)
        cs = [Cama.objects.create(dispositivo=d, codigo=f"C{i}") for i in range(camas)]
        return d, cs

    def persona(self, dni):
        return Ciudadano.objects.create(dni=f"3{dni:0>7}", nombre="N" + dni, apellido="A")


class A305SQL(Base):
    def test_parte_diario_y_filtro_periodo_generan_convert_tz(self):
        qs_ing = Admision.objects.filter(cama__isnull=False, fecha_ingreso__date=date(2026, 9, 1))
        qs_egr = Admision.objects.filter(fecha_egreso__date=date(2026, 9, 1))
        qs_per = filtrar_dispositivos(Dispositivo.objects.all(), desde=date(2026, 9, 1), hasta=date(2026, 9, 30))
        for qs in (qs_ing, qs_egr, qs_per):
            s = _sql(qs)
            print("\nA3-05 SQL:", s[s.find("WHERE") :][:260])
            self.assertIn("CONVERT_TZ", s)

    def test_fix_por_rango_no_usa_convert_tz(self):
        inicio = timezone.make_aware(datetime(2026, 9, 1))
        s = _sql(Admision.objects.filter(fecha_ingreso__gte=inicio, fecha_ingreso__lt=inicio + timedelta(days=1)))
        self.assertNotIn("CONVERT_TZ", s)

    def test_variante_truncmonth_sobre_datefield_no_usa_convert_tz(self):
        s = _sql(LegajoAtencion.objects.annotate(mes=TruncMonth("fecha_admision")).values("mes"))
        print("\nTruncMonth DateField:", s[:200])
        self.assertNotIn("CONVERT_TZ", s)

    def test_parte_diario_en_sqlite_cuenta_bien_el_borde(self):
        # En SQLite (tests) el __date sí convierte a hora local: los tests no ven el bug de MariaDB.
        d, (c,) = self.disp("D05")
        p = self.persona("5")
        a = admitir_ciudadano(ciudadano=p, dispositivo=d, cama=c, usuario=self.u)
        # 23:30 ART del 1/9 = 02:30 UTC del 2/9
        Admision.objects.filter(pk=a.pk).update(fecha_ingreso=datetime(2026, 9, 2, 2, 30, tzinfo=dt_tz.utc))
        self.assertEqual(calcular_cantidades(dispositivo=d, fecha=date(2026, 9, 1))["ingresos"], 1)


class A306DobleAlojamiento(Base):
    def test_a_espera_de_un_alojado_y_promocion(self):
        d, (c1, c2) = self.disp("D06", 2)
        p = self.persona("6")
        admitir_ciudadano(ciudadano=p, dispositivo=d, cama=c1, usuario=self.u)
        esp = poner_en_espera(ciudadano=p, dispositivo=d, usuario=self.u)  # no rechaza
        self.assertEqual(esp.estado, Admision.Estado.LISTA_ESPERA)
        with self.assertRaises(IntegrityError), transaction.atomic():  # SQLite: índice parcial existe
            promover_espera(espera=esp.espera, cama=c2, usuario=self.u)
        # Simula MariaDB (Django no crea el índice condicional)
        with connection.cursor() as cur:
            cur.execute("DROP INDEX admision_una_estadia_activa_por_dispositivo")
        promover_espera(espera=EsperaAdmision.objects.get(admision=esp), cama=c2, usuario=self.u)
        self.assertEqual(Admision.objects.filter(ciudadano=p, dispositivo=d, estado="ALOJADO").count(), 2)
        self.assertEqual(Cama.objects.filter(dispositivo=d, estado="OCUPADA").count(), 2)

    def test_b_espera_previa_y_admision_directa(self):
        d, (c1, c2) = self.disp("D06B", 2)
        p = self.persona("66")
        esp = poner_en_espera(ciudadano=p, dispositivo=d, usuario=self.u)
        admitir_ciudadano(ciudadano=p, dispositivo=d, cama=c1, usuario=self.u)  # no consume la espera
        self.assertTrue(EsperaAdmision.objects.filter(admision=esp, promovida=False).exists())

    def test_admitir_usa_full_clean_y_valida_la_condicional_en_python(self):
        # Contraprueba: por full_clean() la vía admitir SÍ está protegida aun sin índice.
        d, (c1, c2) = self.disp("D06C", 2)
        p = self.persona("666")
        admitir_ciudadano(ciudadano=p, dispositivo=d, cama=c1, usuario=self.u)
        with connection.cursor() as cur:
            cur.execute("DROP INDEX admision_una_estadia_activa_por_dispositivo")
        with self.assertRaises(ValidationError):
            admitir_ciudadano(ciudadano=p, dispositivo=d, cama=c2, usuario=self.u)

    def test_vista_promover_da_500_en_sqlite(self):
        d, (c1, c2) = self.disp("D06D", 2)
        p = self.persona("6666")
        admitir_ciudadano(ciudadano=p, dispositivo=d, cama=c1, usuario=self.u)
        esp = poner_en_espera(ciudadano=p, dispositivo=d, usuario=self.u)
        self.client.force_login(self.u)
        with self.assertRaises(IntegrityError):
            self.client.post(reverse("dispositivos:espera_promover", args=[d.pk, esp.espera.pk]), {"cama": c2.pk})


class A307EsperaHuerfana(Base):
    def test_traslado_con_cama_deja_espera_previa_trabada(self):
        d1, (c1,) = self.disp("D71")
        d2, _ = self.disp("D72", 0)
        d3, (c3,) = self.disp("D73")
        p = self.persona("7")
        a = admitir_ciudadano(ciudadano=p, dispositivo=d1, cama=c1, usuario=self.u)
        e2 = trasladar_admision(admision=a, destino=d2, cama=None, usuario=self.u)
        trasladar_admision(admision=a, destino=d3, cama=c3, usuario=self.u)  # no revisa la espera pendiente
        c21 = Cama.objects.create(dispositivo=d2, codigo="X")
        with self.assertRaisesMessage(ValidationError, "origen ya no está alojada"):
            promover_espera(espera=EsperaAdmision.objects.get(admision=e2), cama=c21, usuario=self.u)
        self.assertTrue(EsperaAdmision.objects.filter(admision=e2, promovida=False).exists())
        with self.assertRaisesMessage(ValidationError, "ya está en lista de espera"):
            poner_en_espera(ciudadano=p, dispositivo=d2, usuario=self.u)

    def test_traslado_pendiente_bloquea_egreso(self):
        d1, (c1,) = self.disp("D74")
        d2, _ = self.disp("D75", 0)
        p = self.persona("77")
        a = admitir_ciudadano(ciudadano=p, dispositivo=d1, cama=c1, usuario=self.u)
        trasladar_admision(admision=a, destino=d2, cama=None, usuario=self.u)
        with self.assertRaisesMessage(ValidationError, "traslado pendiente"):
            egresar_admision(admision=a, usuario=self.u, fecha_egreso=timezone.now(), motivo="x", destino="y")


class A309CierreConAlojados(Base):
    def test_cerrar_con_alojados_y_promover_en_inactivo(self):
        d, (c1, c2) = self.disp("D09", 2)
        p, q = self.persona("9"), self.persona("99")
        admitir_ciudadano(ciudadano=p, dispositivo=d, cama=c1, usuario=self.u)
        esp = poner_en_espera(ciudadano=q, dispositivo=d, usuario=self.u)
        inactivar_dispositivo(d, self.u)
        promover_espera(espera=esp.espera, cama=c2, usuario=self.u)  # promueve en INACTIVO
        d.refresh_from_db()
        cerrar_dispositivo(d, self.u)
        d.refresh_from_db()
        self.assertEqual(d.estado, Dispositivo.Estado.CERRADO)
        self.assertEqual(Admision.objects.filter(dispositivo=d, estado="ALOJADO").count(), 2)


class A310CamaTomada(Base):
    def test_alojar_con_cama_ocupada_pasa_a_espera_en_silencio(self):
        d, (c1, c2) = self.disp("D10", 2)
        otro = self.persona("100")
        admitir_ciudadano(ciudadano=otro, dispositivo=d, cama=c1, usuario=self.u)
        p = self.persona("10")
        self.client.force_login(self.u)
        r = self.client.post(
            reverse("dispositivos:admitir", args=[d.pk]), {"dni": p.dni, "cama": c1.pk, "accion": "alojar"}
        )
        if r.status_code != 302:
            print("A3-10 ctx:", r.context["f00_form"].errors, r.context["busqueda_form"].errors)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Admision.objects.get(ciudadano=p).estado, Admision.Estado.LISTA_ESPERA)


class A311EgresoFuturo(Base):
    def test_egreso_futuro_y_ocupacion_por_encima_de_camas(self):
        d, (c,) = self.disp("D11")
        p, q = self.persona("11"), self.persona("111")
        a = admitir_ciudadano(ciudadano=p, dispositivo=d, cama=c, usuario=self.u)
        egresar_admision(
            admision=a, usuario=self.u, fecha_egreso=timezone.now() + timedelta(days=3), motivo="x", destino="y"
        )
        c.refresh_from_db()
        admitir_ciudadano(ciudadano=q, dispositivo=d, cama=c, usuario=self.u)
        cant = calcular_cantidades(dispositivo=d, fecha=timezone.localdate())
        self.assertEqual(cant["ocupacion_nocturna"], 2)
        self.assertEqual(cant["camas_totales"], 1)


class A312Alertas(Base):
    def test_dos_corridas_duplican_y_renotifican(self):
        from legajos.services.alertas import AlertasService

        p = self.persona("12")
        leg = LegajoAtencion.objects.create(responsable=self.u)
        InscripcionPrograma.objects.create(ciudadano=p, programa=self.programa, legajo_id=leg.id)
        with patch.object(AlertasService, "_enviar_notificacion_alerta") as notif:
            AlertasService.generar_alertas_ciudadano(p.id)
            AlertasService.generar_alertas_ciudadano(p.id)
        self.assertEqual(AlertaCiudadano.objects.filter(ciudadano=p, tipo="SIN_PLAN").count(), 2)
        self.assertEqual(notif.call_count, 2)
        vieja = AlertaCiudadano.objects.filter(ciudadano=p, tipo="SIN_PLAN", activa=False).get()
        self.assertIsNone(vieja.fecha_cierre)


class A315Reinscripcion(Base):
    def test_aceptar_derivacion_con_inscripcion_cerrada(self):
        p = self.persona("15")
        InscripcionPrograma.objects.create(ciudadano=p, programa=self.programa, estado="CERRADO")
        der = DerivacionPrograma.objects.create(ciudadano=p, programa_destino=self.programa, motivo="m")
        with self.assertRaises(IntegrityError):
            der.aceptar(usuario=self.u)

    def test_inscripcion_directa_con_cerrada_da_500(self):
        p = self.persona("155")
        Programa.objects.filter(pk=self.programa.pk).update(estado="ACTIVO")
        InscripcionPrograma.objects.create(ciudadano=p, programa=self.programa, estado="CERRADO")
        self.client.force_login(self.u)  # superuser -> is_staff
        try:
            r = self.client.post(
                reverse("legajos:derivar_programa", args=[p.pk]),
                {
                    "institucion_programa": self.programa.pk,
                    "tipo_inicio": "inscripcion_directa",
                    "motivo": "motivo largo",
                    "urgencia": "MEDIA",
                },
            )
        except IntegrityError:
            return
        print(
            "A3-15 form:",
            r.status_code,
            r.context and r.context["form"].errors,
            Programa.objects.values_list("codigo", "estado"),
        )
        self.fail("no IntegrityError")


class A316Vinculos(Base):
    def test_api_vinculos_no_montada_y_search_ignorado(self):
        with self.assertRaises(Resolver404):
            resolve("/api/legajos/contactos/vinculos-familiares/")
        self.persona("16")
        self.client.force_login(self.u)
        r = self.client.get("/api/legajos/ciudadanos/?search=zzzzzz")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.json()["count"], 0)


class A317A318Adjuntos(Base):
    def test_subida_no_atomica(self):
        from legajos.services.contactos import ContactosFilesError, subir_archivos_para_objeto

        p = self.persona("18")
        with TemporaryDirectory() as m, override_settings(MEDIA_ROOT=m):
            with self.assertRaises(ContactosFilesError):
                subir_archivos_para_objeto(
                    p, [SimpleUploadedFile("dni.pdf", b"x"), SimpleUploadedFile("foto.heic", b"y")]
                )
        self.assertEqual(Adjunto.objects.count(), 1)

    def test_blob_faltante_vacia_la_lista(self):
        from legajos.services.contactos import subir_archivos_para_objeto

        p = self.persona("17")
        self.client.force_login(self.u)
        with TemporaryDirectory() as m, override_settings(MEDIA_ROOT=m):
            subir_archivos_para_objeto(p, [SimpleUploadedFile("a.pdf", b"x"), SimpleUploadedFile("b.pdf", b"y")])
            Adjunto.objects.order_by("id").first().archivo.delete(save=False)
            from zeal import zeal_ignore

            with zeal_ignore():
                r = self.client.get(reverse("legajos:archivos_ciudadano", args=[p.pk]))
        print("\nA3-17:", r.status_code, str(r.json())[:200])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 0)
        self.assertIn("error", r.json())


class A319A320A321(Base):
    def test_reservadas_cuentan_como_libres(self):
        d, cs = self.disp("D19", 3)
        Cama.objects.filter(pk__in=[cs[0].pk, cs[1].pk]).update(estado=Cama.Estado.RESERVADA)
        self.assertEqual(resumen_ocupacion(d)["libres"], 3)

    def test_ultima_actualizacion_usa_fecha_utc(self):
        from programas.services.indicadores import indicadores_dispositivo

        d, _ = self.disp("D20")
        r = RegistroDiario.objects.create(dispositivo=d, fecha=date(2026, 9, 9), turno="NOCHE", firmado_por=self.u)
        # 22:30 ART del 9/9 = 01:30 UTC del 10/9
        RegistroDiario.objects.filter(pk=r.pk).update(modificado=datetime(2026, 9, 10, 1, 30, tzinfo=dt_tz.utc))
        ind = indicadores_dispositivo(d, hoy=date(2026, 9, 10))
        self.assertEqual(ind["actualizacion"]["dias"], 0)  # debería ser 1

    def test_egreso_cierra_membresia_con_espera_pendiente(self):
        d1, (c1,) = self.disp("D211")
        d2, _ = self.disp("D212", 0)
        p = self.persona("21")
        a = admitir_ciudadano(ciudadano=p, dispositivo=d1, cama=c1, usuario=self.u)
        poner_en_espera(ciudadano=p, dispositivo=d2, usuario=self.u)
        egresar_admision(admision=a, usuario=self.u, fecha_egreso=timezone.now(), motivo="x", destino="y")
        self.assertEqual(InscripcionPrograma.objects.get(ciudadano=p, programa=self.programa).estado, "CERRADO")


class A322(Base):
    def test_suspendido_no_vuelve_a_activo(self):
        from programas.services.merenderos import cambiar_estado_merendero

        # Fixture mínima (antes el test se salteaba si la base de test no traía un merendero).
        m = Merendero.objects.create(
            codigo="MER-R2", nombre="Merendero R2", domicilio="Calle 1", responsable_nombre="Resp"
        )
        self.assertEqual(m.estado, Merendero.Estado.ACTIVO)
        cambiar_estado_merendero(m, nuevo_estado=Merendero.Estado.SUSPENDIDO, usuario=self.u)
        with self.assertRaises(ValidationError):
            cambiar_estado_merendero(m, nuevo_estado=Merendero.Estado.ACTIVO, usuario=self.u)


class A313A314(Base):
    def test_criticas_visibles_y_debug_sin_escapar(self):
        p = Ciudadano.objects.create(dni="31234567", nombre="<img src=x onerror=alert(1)>", apellido="A")
        AlertaCiudadano.objects.create(ciudadano=p, tipo="VIOLENCIA", prioridad="CRITICA", mensaje="m")
        cualquiera = User.objects.create_user("merenderos-op", password="x")
        self.client.force_login(cualquiera)
        r = self.client.get("/legajos/alertas/debug/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<img src=x onerror=alert(1)>", r.content)
