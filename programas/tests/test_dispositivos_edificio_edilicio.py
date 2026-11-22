"""Solapa «Estado edilicio» de la página operativa del edificio (Cambio 567, PR 5 del lote «el edificio como unidad operativa»).

1. Lista: los relevamientos realizados del edificio, del más nuevo al más viejo, con su marca y su botón.
2. Detalle: el de otro edificio, uno no realizado, uno que el usuario no ve o un id raro dan 404.
3. Alcance del informe (Cambio 428): sin él no hay observaciones, quién relevó ni fotos, ni en la lista ni en el detalle.
4. Las fotos del detalle son las de **ese** relevamiento.
5. El costo no crece con los relevamientos ni con las fotos (``dispositivos_edificio_operativo_edilicio``).
"""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.db import connection
from django.test import tag
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from programas.models import FotoInspeccion, InspeccionEdificio, MiembroEquipoDispositivo
from programas.tests.test_dispositivos_edificio_operativo import PRESUPUESTOS, BaseOperativo

CLAVE_PRESUPUESTO = "dispositivos_edificio_operativo_edilicio"

Estado = InspeccionEdificio.Estado
Criticidad = InspeccionEdificio.Criticidad


class BaseEdilicio(BaseOperativo):
    def _relevar(self, edificio, criticidad=Criticidad.BAJA, *, dias_atras=1, observaciones="", fotos=(), **extra):
        momento = timezone.now() - timedelta(days=dias_atras)
        inspeccion = InspeccionEdificio.objects.create(
            edificio=edificio,
            estado=extra.pop("estado", Estado.REALIZADA),
            criticidad=criticidad,
            observaciones=observaciones,
            asignado_a=self.de_inst,
            creado_por=self.de_inst,
            fecha_vencimiento=momento.date(),
            realizada_en=momento,
            realizada_por=self.de_inst,
            **extra,
        )
        for rotulo in fotos:
            FotoInspeccion.objects.create(
                inspeccion=inspeccion,
                archivo=ContentFile(b"x", name=f"{rotulo}.jpg"),
                descripcion=rotulo,
                cargada_por=self.de_inst,
            )
        return inspeccion

    def _edilicio(self, usuario, edificio=None, **params):
        return self._get(usuario, edificio or self.edif_a, tab="edilicio", **params)

    def _detalle(self, usuario, inspeccion, edificio=None):
        return self._edilicio(usuario, edificio, relevamiento=inspeccion.pk)

    def _sin_informe(self):
        """Entra a la página por ``dispositivo.ver_todos`` pero sin ser del Equipo ni coordinar: no abre informes."""

        usuario = self._con("Solo mira", "dispositivo.ver", "dispositivo.ver_todos")
        MiembroEquipoDispositivo.objects.filter(usuario=usuario).delete()
        return User.objects.get(pk=usuario.pk)


class ListaTests(BaseEdilicio):
    def test_lista_los_relevamientos_del_mas_nuevo_al_mas_viejo_con_sus_marcas(self):
        viejo = self._relevar(self.edif_a, Criticidad.ALTA, dias_atras=30, observaciones="Sin disyuntor")
        medio = self._relevar(self.edif_a, Criticidad.MEDIA, dias_atras=10)
        nuevo = self._relevar(self.edif_a, Criticidad.BAJA, dias_atras=1, fotos=("fachada", "techo"))

        respuesta = self._edilicio(self.de_inst)
        filas = respuesta.context["edilicio_lista"]["filas"]

        self.assertEqual([fila["numero"] for fila in filas], [f"REL-{pk:04d}" for pk in (nuevo.pk, medio.pk, viejo.pk)])
        self.assertEqual([fila["marca"] for fila in filas], ["Último", "", "Primer relevamiento"])
        self.assertEqual([fila["criticidad"] for fila in filas], ["Baja", "Media", "Alta"])
        self.assertEqual(filas[0]["fotos"], "2 fotos")
        self.assertEqual(filas[1]["observaciones"], "Sin observaciones")
        self.assertContains(respuesta, "Relevamientos del edificio")
        self.assertContains(respuesta, "Ver detalle", count=3)

    def test_no_lista_los_de_otro_edificio_ni_los_que_no_se_realizaron(self):
        propio = self._relevar(self.edif_a)
        self._relevar(self.edif_b)
        self._relevar(self.edif_a, estado=Estado.ASIGNADA, criticidad="")
        self._relevar(self.edif_a, estado=Estado.CANCELADA, criticidad="", motivo_cancelacion="Duplicado")

        filas = self._edilicio(self.de_inst).context["edilicio_lista"]["filas"]

        self.assertEqual([fila["numero"] for fila in filas], [f"REL-{propio.pk:04d}"])

    def test_crear_relevamiento_solo_con_la_capacidad(self):
        con = self._con("Asigna", "dispositivo.ver", "inspeccion.asignar")
        sin = self._con("No asigna", "dispositivo.ver")

        self.assertContains(self._edilicio(con), "Crear relevamiento")
        self.assertNotContains(self._edilicio(sin), "Crear relevamiento")

    def test_sin_relevamientos_muestra_el_vacio(self):
        self.assertContains(self._edilicio(self.de_inst), "Todavía no hay relevamientos")

    def test_pagina_de_a_diez(self):
        for dias in range(1, 13):
            self._relevar(self.edif_a, dias_atras=dias)

        respuesta = self._edilicio(self.de_inst, relevamientos_page=2)

        self.assertEqual(len(respuesta.context["edilicio_lista"]["filas"]), 2)
        self.assertEqual(respuesta.context["edilicio_lista"]["filas"][-1]["marca"], "Primer relevamiento")


class DetalleTests(BaseEdilicio):
    def test_abre_el_detalle_con_sus_datos_y_solo_sus_fotos(self):
        self._relevar(self.edif_a, dias_atras=20, fotos=("ajena",))
        inspeccion = self._relevar(
            self.edif_a, Criticidad.MEDIA, observaciones="Pérdida en el baño", fotos=("baño", "cocina")
        )

        respuesta = self._detalle(self.de_inst, inspeccion)
        detalle = respuesta.context["edilicio_detalle"]

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(detalle["numero"], f"REL-{inspeccion.pk:04d}")
        self.assertEqual([foto["rotulo"] for foto in detalle["fotos"]], ["baño", "cocina"])
        self.assertIn("el más nuevo de 2", detalle["subtitulo"])
        self.assertEqual(
            detalle["url_informe"],
            reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk]) + f"?dispositivo={self.cis.pk}",
        )
        self.assertContains(respuesta, "Volver a los relevamientos")
        self.assertContains(respuesta, "Descargar informe")
        self.assertContains(respuesta, "Pérdida en el baño")
        self.assertNotContains(respuesta, "ajena")

    def test_volver_conserva_la_pagina_de_la_lista(self):
        for dias in range(1, 13):
            self._relevar(self.edif_a, dias_atras=dias)

        lista = self._edilicio(self.de_inst, relevamientos_page=2).context["edilicio_lista"]["filas"]
        url = lista[0]["url_detalle"]
        self.assertIn("relevamientos_page=2", url)
        pagina_uno = self._edilicio(self.de_inst).context["edilicio_lista"]["filas"][0]["url_detalle"]
        self.assertNotIn("relevamientos_page", pagina_uno)

        self.client.force_login(self.de_inst)
        detalle = self.client.get(url).context["edilicio_detalle"]
        self.assertTrue(detalle["url_volver"].endswith("?tab=edilicio&relevamientos_page=2"))
        sin_pagina = self.client.get(pagina_uno).context["edilicio_detalle"]
        self.assertTrue(sin_pagina["url_volver"].endswith("?tab=edilicio"))

    def test_de_otro_edificio_da_404(self):
        ajeno = self._relevar(self.edif_b, fotos=("fachada",))

        # Ni siquiera un usuario con alcance a los dos edificios lo abre desde el equivocado.
        self.assertEqual(self._detalle(self.de_inst, ajeno, self.edif_a).status_code, 404)

    def test_uno_no_realizado_o_inexistente_o_raro_da_404(self):
        en_curso = self._relevar(self.edif_a, estado=Estado.ASIGNADA, criticidad="")

        self.assertEqual(self._detalle(self.de_inst, en_curso).status_code, 404)
        for valor in ("99999", "abc", "²", "-1"):
            with self.subTest(valor=valor):
                self.assertEqual(self._edilicio(self.de_inst, relevamiento=valor).status_code, 404)

    def test_el_parametro_se_ignora_en_otra_solapa(self):
        self.assertEqual(self._get(self.de_inst, self.edif_a, tab="equipo", relevamiento="abc").status_code, 200)


class AlcanceDelInformeTests(BaseEdilicio):
    def setUp(self):
        super().setUp()
        self.inspeccion = self._relevar(
            self.edif_a, Criticidad.ALTA, observaciones="Cables pelados", fotos=("pizarra reservada",)
        )

    def test_la_lista_no_muestra_observaciones_fotos_ni_quien_relevo(self):
        respuesta = self._edilicio(self._sin_informe())
        fila = respuesta.context["edilicio_lista"]["filas"][0]

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(fila["con_detalle"])
        self.assertEqual(
            (fila["observaciones"], fila["fotos"], fila["relevo"], fila["criticidad"], fila["tono"]),
            ("", "", "", "", ""),
        )
        self.assertNotContains(respuesta, "Cables pelados")
        self.assertNotContains(respuesta, "Ver detalle")
        self.assertNotContains(respuesta, "pizarra reservada")

    def test_el_detalle_da_404(self):
        self.assertEqual(self._detalle(self._sin_informe(), self.inspeccion).status_code, 404)

    def test_con_alcance_si_se_ven(self):
        respuesta = self._detalle(self.de_inst, self.inspeccion)

        self.assertContains(respuesta, "Cables pelados")
        self.assertEqual(len(respuesta.context["edilicio_detalle"]["fotos"]), 1)


@tag("performance")
class PresupuestoEdilicioTests(BaseEdilicio):
    def _medir(self, **params):
        self.client.force_login(self.de_inst)
        url = self._url(self.edif_a)
        self.client.get(url, {"tab": "edilicio", **params})
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(url, {"tab": "edilicio", **params})
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas)

    def test_la_lista_cuesta_lo_mismo_con_uno_que_con_muchos(self):
        self._relevar(self.edif_a, fotos=("a",))
        antes = self._medir()
        for dias in range(2, 9):
            self._relevar(self.edif_a, dias_atras=dias, fotos=("a", "b", "c"))
        despues = self._medir()

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, techo["consultas_fijas"])

    def test_el_detalle_cuesta_lo_mismo_con_una_foto_que_con_muchas(self):
        self._relevar(self.edif_a, dias_atras=9)
        una = self._relevar(self.edif_a, fotos=("a",))
        antes = self._medir(relevamiento=una.pk)
        muchas = self._relevar(self.edif_a, dias_atras=2, fotos=tuple("abcdefgh"))
        despues = self._medir(relevamiento=muchas.pk)

        techo = json.loads(PRESUPUESTOS.read_text(encoding="utf-8"))["servicios"][CLAVE_PRESUPUESTO]
        self.assertEqual(antes, despues)
        self.assertLessEqual(despues, techo["consultas_fijas"])


class SolapaPerezosaTests(BaseEdilicio):
    def test_con_otra_solapa_no_se_arma_y_el_boton_navega(self):
        self._relevar(self.edif_a, fotos=("a",))

        respuesta = self._get(self.de_inst, self.edif_a, tab="equipo")

        self.assertNotIn("edilicio_lista", respuesta.context)
        self.assertNotIn("edilicio_detalle", respuesta.context)
        self.assertContains(respuesta, "data-solapa-navega")
        self.assertTrue(respuesta.context["url_solapa_edilicio"].endswith("?tab=edilicio"))

    def test_con_la_solapa_abierta_el_boton_no_navega(self):
        respuesta = self._edilicio(self.de_inst)

        self.assertNotContains(respuesta, "data-solapa-navega")
