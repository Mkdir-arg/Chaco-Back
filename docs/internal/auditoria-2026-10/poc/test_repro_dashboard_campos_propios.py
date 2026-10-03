r"""Reproducción: el Excel de respuestas y el dashboard no ven los campos propios del constructor (G2, pasada 3).

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
  Copy-Item <este archivo> programas/tests/test_repro_dashboard_campos_propios.py
  & $env:PY manage.py test programas.tests.test_repro_dashboard_campos_propios -v 2
  (.venv312 = Python 3.12 + Django 5.2.17, igual al CI. No usar el Python global.)

  Depende de programas.tests.test_dashboard_becas (DashboardBecasBase, HOY).

QUÉ ID CANÓNICO REPRODUCE CADA CLASE
  CampoPropioFueraDeReportesTests                -> G2-01
"""

from datetime import timedelta

from programas.models import Formulario
from programas.services import dashboard_becas as svc
from programas.tests.test_dashboard_becas import HOY, DashboardBecasBase

DEFINICION = {
    "version": 1,
    "canal": "PUBLICO",
    "items": [
        {
            "clave": "g-1",
            "tipo": "grupo",
            "texto": "Hogar",
            "items": [
                {
                    "clave": "cp-hijos",
                    "tipo": "SELECTOR",
                    "tipo_item": "campo",
                    "texto": "¿Tenés hijos a cargo?",
                    "opciones": ["Sí", "No"],
                }
            ],
        }
    ],
}


class CampoPropioFueraDeReportesTests(DashboardBecasBase):
    def test_campo_propio_no_llega_al_excel_ni_al_dashboard(self):
        f = self._formulario(
            self.rel_publico,
            creado=HOY - timedelta(days=1),
            definicion=DEFINICION,
            respuestas={"cp-hijos": "Sí"},
            data={"globales": {}, "requisitos": {}},
        )
        self.assertEqual(Formulario.objects.get(pk=f.pk).respuestas, {"cp-hijos": "Sí"})
        reporte, _ = svc.respuestas_por_persona(self.conv_propia)
        self.assertNotIn("¿Tenés hijos a cargo?", " ".join(map(str, reporte.encabezados)))
        fila = reporte.filas[0]
        self.assertNotIn("Sí", fila[len(svc.COLUMNAS_FIJAS) :])
        claves = [p.clave for p in svc.preguntas_graficables(self.admin, self.programa)]
        self.assertFalse(any("hijos" in c or c.startswith("cp") for c in claves))
