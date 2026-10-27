from django.urls import path

from programas.views import dispositivos_bitacora as bitacora
from programas.views import dispositivos_capacidad as capacidad
from programas.views import dispositivos_config as cfg
from programas.views import dispositivos_formularios as frm
from programas.views import dispositivos_ingreso as ingreso
from programas.views import dispositivos_legajo as legajo
from programas.views import dispositivos_relevamientos as relevamientos
from programas.views import reportes

app_name = "dispositivos"

# Las rutas del circuito operativo —admisión, egreso, traslado, lista de espera,
# parte diario y camas— se fueron con los modelos de la versión 1.
# Las repone el MVP v2 con `Sector`/`Plaza`,
# `Estadia` y `Turno`; mientras tanto el legajo institucional del dispositivo y la
# configuración de tipos siguen en pie.
urlpatterns = [
    path("", legajo.DispositivoListView.as_view(), name="lista"),
    path("export/<str:reporte>/<str:formato>/", reportes.DispositivoExportView.as_view(), name="exportar"),
    path("nuevo/", legajo.DispositivoCreateView.as_view(), name="crear"),
    path("buscar-duplicados/", legajo.DispositivoDuplicateSearchView.as_view(), name="buscar_duplicados"),
    # La sección «Crear dispositivo» del tipo elegido en el alta y la edición (P3 · P17).
    path("formulario-tipo/", legajo.DispositivoFormularioTipoView.as_view(), name="formulario_tipo_seccion"),
    path("<int:pk>/enviar-validacion/", legajo.DispositivoEnviarValidacionView.as_view(), name="enviar_validacion"),
    path("<int:pk>/validar/", legajo.DispositivoValidarView.as_view(), name="validar"),
    path("<int:pk>/observar/", legajo.DispositivoObservarView.as_view(), name="observar"),
    path("<int:pk>/rechazar/", legajo.DispositivoRechazarView.as_view(), name="rechazar"),
    path("<int:pk>/inactivar/", legajo.DispositivoInactivarView.as_view(), name="inactivar"),
    path("<int:pk>/cerrar/", legajo.DispositivoCerrarView.as_view(), name="cerrar"),
    path("<int:pk>/", legajo.DispositivoDetailView.as_view(), name="detalle"),
    path("<int:pk>/editar/", legajo.DispositivoUpdateView.as_view(), name="editar"),
    path("<int:pk>/sectores/", legajo.DispositivoSectoresView.as_view(), name="sectores"),
    # Capacidad instalada (carril C5). Mutan: solo POST. Los modales de las dos altas llegan
    # con `sectores` y los abre el botón; el de la edición, `?sector=<id>` sobre esa pantalla.
    path("<int:pk>/sectores/nuevo/", capacidad.SectorCrearView.as_view(), name="sector_crear"),
    path(
        "<int:pk>/sectores/<int:sector_pk>/editar/",
        capacidad.SectorEditarView.as_view(),
        name="sector_editar",
    ),
    path("<int:pk>/plazas/agregar/", capacidad.PlazasAgregarView.as_view(), name="plazas_agregar"),
    path("<int:pk>/plazas/<int:plaza_pk>/editar/", capacidad.PlazaEditarView.as_view(), name="plaza_editar"),
    # Edificio de la solapa Infraestructura (P19). El alta lo vincula; «vincular» declara el
    # predio compartido con un edificio que ya existe.
    path("<int:pk>/edificio/nuevo/", capacidad.EdificioCrearView.as_view(), name="edificio_crear"),
    path(
        "<int:pk>/edificio/<int:edificio_pk>/editar/",
        capacidad.EdificioEditarView.as_view(),
        name="edificio_editar",
    ),
    path("<int:pk>/edificio/vincular/", capacidad.EdificioVincularView.as_view(), name="edificio_vincular"),
    path(
        "<int:pk>/edificio/<int:edificio_pk>/desvincular/",
        capacidad.EdificioDesvincularView.as_view(),
        name="edificio_desvincular",
    ),
    # Acciones del mapa de plazas (P5). El modal las abre con `?plaza=<id>` sobre `sectores`.
    path(
        "<int:pk>/plazas/<int:plaza_pk>/reservar/",
        legajo.PlazaReservarView.as_view(),
        name="plaza_reservar",
    ),
    path(
        "<int:pk>/plazas/<int:plaza_pk>/prestar/",
        legajo.PlazaPrestarView.as_view(),
        name="plaza_prestar",
    ),
    path(
        "<int:pk>/plazas/<int:plaza_pk>/liberar/",
        legajo.PlazaLiberarView.as_view(),
        name="plaza_liberar",
    ),
    path(
        "<int:pk>/plazas/<int:plaza_pk>/fuera-servicio/",
        legajo.PlazaFueraDeServicioView.as_view(),
        name="plaza_fuera_servicio",
    ),
    path(
        "<int:pk>/plazas/<int:plaza_pk>/volver-servicio/",
        legajo.PlazaVolverAServicioView.as_view(),
        name="plaza_volver_servicio",
    ),
    path("<int:pk>/estadias/", legajo.DispositivoEstadiasView.as_view(), name="estadias"),
    path("<int:pk>/estadias/<int:estadia_pk>/", legajo.EstadiaDetalleView.as_view(), name="estadia_detalle"),
    path("<int:pk>/estadias/<int:estadia_pk>/egresar/", legajo.EstadiaEgresarView.as_view(), name="egresar"),
    path(
        "<int:pk>/estadias/<int:estadia_pk>/cambiar-plaza/",
        legajo.EstadiaCambiarPlazaView.as_view(),
        name="cambiar_plaza",
    ),
    path("<int:pk>/bitacora/", bitacora.BitacoraTurnoView.as_view(), name="bitacora"),
    path("<int:pk>/bitacora/novedad/", bitacora.NovedadCrearView.as_view(), name="bitacora_novedad"),
    path("<int:pk>/bitacora/corregir/", bitacora.NovedadCorregirView.as_view(), name="bitacora_corregir"),
    path("<int:pk>/bitacora/turnos/", bitacora.TurnoGuardarView.as_view(), name="bitacora_turnos"),
    path("<int:pk>/ingresar/", ingreso.IngresoPersonaView.as_view(), name="ingreso_persona"),
    path("<int:pk>/ingresar/plaza/", ingreso.IngresoPlazaView.as_view(), name="ingreso_plaza"),
    path("<int:pk>/ingresar/confirmar/", ingreso.IngresoConfirmarView.as_view(), name="ingreso_confirmar"),
    # Relevamientos edilicios del coordinador (P21 · #701): en el código, `InspeccionEdificio`.
    path("relevamientos/", relevamientos.RelevamientoListView.as_view(), name="relevamientos"),
    path(
        "relevamientos/<int:pk>/informe/",
        relevamientos.RelevamientoInformeView.as_view(),
        name="relevamiento_informe",
    ),
    path(
        "relevamientos/edificio/<int:edificio_pk>/asignar/",
        relevamientos.RelevamientoAsignarView.as_view(),
        name="relevamiento_asignar",
    ),
    path(
        "<int:pk>/relevamiento/asignar/",
        relevamientos.DispositivoRelevamientoAsignarView.as_view(),
        name="relevamiento_asignar_dispositivo",
    ),
    path(
        "relevamientos/<int:pk>/reasignar/",
        relevamientos.RelevamientoReasignarView.as_view(),
        name="relevamiento_reasignar",
    ),
    path(
        "relevamientos/<int:pk>/cancelar/",
        relevamientos.RelevamientoCancelarView.as_view(),
        name="relevamiento_cancelar",
    ),
    path(
        "relevamientos/<int:pk>/revisar/",
        relevamientos.RelevamientoRevisarView.as_view(),
        name="relevamiento_revisar",
    ),
    path("config/", cfg.TipoDispositivoListView.as_view(), name="tipos"),
    path("config/nuevo/", cfg.TipoDispositivoCreateView.as_view(), name="tipo_crear"),
    path("config/<int:pk>/", cfg.TipoDispositivoDetailView.as_view(), name="tipo_detalle"),
    path("config/<int:pk>/editar/", cfg.TipoDispositivoUpdateView.as_view(), name="tipo_editar"),
    path("config/<int:pk>/toggle/", cfg.TipoDispositivoToggleView.as_view(), name="tipo_toggle"),
    # Formularios del tipo, uno por momento (P17): el constructor de Becas con otro dueño.
    path("config/<int:pk>/formularios/nuevo/", frm.FormularioTipoCrearView.as_view(), name="formulario_crear"),
    path(
        "config/<int:pk>/formularios/<slug:momento>/",
        frm.FormularioTipoEditorView.as_view(),
        name="formulario_editor",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/eliminar/",
        frm.FormularioTipoEliminarView.as_view(),
        name="formulario_eliminar",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/reactivar/",
        frm.FormularioTipoReactivarView.as_view(),
        name="formulario_reactivar",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/mover/",
        frm.FormularioTipoMoverView.as_view(),
        name="formulario_mover",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/grupo/",
        frm.FormularioTipoGrupoView.as_view(),
        name="formulario_grupo_crear",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/texto/",
        frm.FormularioTipoTextoView.as_view(),
        name="formulario_texto_crear",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/campo-propio/",
        frm.FormularioTipoPropioView.as_view(),
        name="formulario_propio_crear",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/item/<str:clave>/editar/",
        frm.FormularioTipoItemEditarView.as_view(),
        name="formulario_item_editar",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/item/<str:clave>/condicion/",
        frm.FormularioTipoCondicionView.as_view(),
        name="formulario_condicion",
    ),
    path(
        "config/<int:pk>/formularios/<slug:momento>/item/<str:clave>/eliminar/",
        frm.FormularioTipoItemEliminarView.as_view(),
        name="formulario_item_eliminar",
    ),
]
