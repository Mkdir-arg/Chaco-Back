from django.test import SimpleTestCase


class LegajosPackageExportsTests(SimpleTestCase):
    def test_services_and_selectors_packages_export_public_symbols(self):
        from legajos.api_views import CiudadanoViewSet
        from legajos.api_views.contactos import HistorialContactoViewSet
        from legajos.forms import CiudadanoForm, DerivarProgramaForm
        from legajos.selectors import build_ciudadano_detail_context
        from legajos.services import (
            AlertasService,
            CiudadanosService,
            ContactosFilesError,
            DerivacionProgramaService,
            FiltrosUsuarioService,
            ServicioDeteccionDuplicados,
            ServicioOperacionNachec,
            ServicioSLA,
            ServicioTransicionNachec,
            SolapasService,
        )

        for simbolo in (
            AlertasService,
            CiudadanoViewSet,
            CiudadanoForm,
            CiudadanosService,
            DerivarProgramaForm,
            DerivacionProgramaService,
            FiltrosUsuarioService,
            HistorialContactoViewSet,
            ServicioOperacionNachec,
            ServicioDeteccionDuplicados,
            ServicioSLA,
            ServicioTransicionNachec,
            SolapasService,
            ContactosFilesError,
        ):
            self.assertIsNotNone(simbolo)
        self.assertTrue(callable(build_ciudadano_detail_context))

    def test_derivacion_programa_service_exportado(self):
        from legajos.services import DerivacionProgramaService

        self.assertIsNotNone(DerivacionProgramaService)
