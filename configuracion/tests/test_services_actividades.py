"""`configuracion.services` quedó vacío al retirar el flujo institucional viejo.

TST-02. Este módulo tenía un solo test, `self.assertTrue(True)`: pasaba en verde
dijera lo que dijera el código y no habría avisado si el flujo volvía. Lo que de
verdad hay que sostener es que el paquete **no exporta nada**: si alguien vuelve a
colgar un servicio ahí, tiene que ser una decisión visible y no un reingreso del
camino que se retiró.

El ABM real de Configuración vive en `views/` y se prueba en
`test_wizard_programas.py` y `test_secretarias.py`.
"""

from django.test import SimpleTestCase

import configuracion.services


class ConfiguracionServicesVacioTests(SimpleTestCase):
    def test_el_paquete_de_servicios_no_exporta_nada_publico(self):
        publicos = [nombre for nombre in vars(configuracion.services) if not nombre.startswith("_")]

        self.assertEqual(
            publicos,
            [],
            "`configuracion/services/` está vacío a propósito desde que se retiró el flujo "
            "institucional. Si hace falta un servicio acá, actualizá este test y decí por qué.",
        )
