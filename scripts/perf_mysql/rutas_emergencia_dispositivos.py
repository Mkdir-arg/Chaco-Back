"""Rutas de **Emergencia** y **Dispositivos** para ``bench_mysql.py``.

Las fichas E-PERF-* y D-PERF-* de la auditoría de noviembre de 2026 (§8.a) piden medir
pantallas, endpoints de la API de campo y descargas con el volumen que dejan
``escalar_emergencia.py`` y ``escalar_dispositivos.py``. Los actores son los usuarios
``bench_*`` que esos scripts crean con roles acotados (no el ``perf_admin`` de Becas, que
no tiene alcance sobre un dispositivo):

* web: ``bench_mesa_01`` (mesa), ``bench_sup_01`` (supervisor), ``bench_admin_disp_01``
  (administrador del programa Dispositivos), ``bench_coord_01`` (coordinador, en el
  Equipo de 41 dispositivos) y ``bench_guardia_01``;
* API de campo: ``Authorization: Token`` de la guardia y del agente.

Si el banco no tiene la siembra (no hay ``BENCH-E-GRANDE``/``BENCH-D-GRANDE``), no
agrega nada.
"""

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from rest_framework.authtoken.models import Token

ACTORES_WEB = {
    "mesa": "bench_mesa_01",
    "supervisor": "bench_sup_01",
    "admin_disp": "bench_admin_disp_01",
    "coordinador": "bench_coord_01",
    "guardia_web": "bench_guardia_01",
}
ACTORES_API = {"guardia_api": "bench_guardia_01", "agente_api": "bench_agente_01"}


def clientes():
    """Un cliente por actor; vacío para el que no existe en la base."""
    usuarios = {u.username: u for u in get_user_model().objects.filter(username__startswith="bench_")}
    resultado = {}
    for clave, username in ACTORES_WEB.items():
        if username in usuarios:
            c = Client()
            c.force_login(usuarios[username])
            resultado[clave] = c
    for clave, username in ACTORES_API.items():
        if username in usuarios:
            token = Token.objects.get(user=usuarios[username])
            resultado[clave] = Client(headers={"Authorization": f"Token {token.key}"})
    return resultado


def _t(clave, actor, url):
    return {"key": clave, "actor": actor, "url": url}


def emergencia():
    from programas.models import CasoEmergencia, Derivacion, Dispositivo, EntregaKit, Estadia

    grande = Dispositivo.objects.filter(codigo="BENCH-E-GRANDE").first()
    if grande is None:
        return []
    Estado = CasoEmergencia.Estado
    casos = CasoEmergencia.objects.filter(numero__startswith="BENCH-C-")
    rutas = [
        _t("E-bandeja_abiertos", "mesa", reverse("emergencia:bandeja")),
        _t("E-bandeja_cerrados", "mesa", reverse("emergencia:bandeja") + "?solapa=cerrados"),
        _t("E-bandeja_cerrados_pag_90", "mesa", reverse("emergencia:bandeja") + "?solapa=cerrados&page=90"),
        _t("E-bandeja_texto", "mesa", reverse("emergencia:bandeja") + "?texto=BENCH0001"),
        _t("E-bandeja_fuera_sla", "mesa", reverse("emergencia:bandeja") + "?solapa=fuera_sla"),
        _t("E-caso_nuevo_form", "mesa", reverse("emergencia:caso_nuevo")),
        _t("E-tablero", "supervisor", reverse("emergencia:tablero")),
        _t("E-entregas_recibidas", "mesa", reverse("emergencia:entregas") + "?solapa=recibidas"),
        _t("E-entregas_recibidas_ultima", "mesa", reverse("emergencia:entregas") + "?solapa=recibidas&page=99999"),
        _t("E-entregas_abiertas", "mesa", reverse("emergencia:entregas")),
        _t("E-entrega_nueva", "mesa", reverse("emergencia:entrega_nueva")),
        _t("E-llegadas_grande", "guardia_web", reverse("dispositivos:emergencia_llegadas", args=[grande.pk])),
        _t("E-api_mis_dispositivos", "guardia_api", reverse("emergencia_api:mis-dispositivos")),
        _t("E-api_caso_mios", "agente_api", reverse("emergencia_api:caso-mios")),
        _t(
            "E-api_dispositivo_buscar_inexistente",
            "guardia_api",
            reverse("emergencia_api:dispositivo-buscar", args=[grande.pk]) + "?dni=99999999",
        ),
        _t(
            "E-api_dispositivo_entregas",
            "guardia_api",
            reverse("emergencia_api:dispositivo-entregas", args=[grande.pk]),
        ),
        _t(
            "E-api_dispositivo_entregas_pendientes",
            "guardia_api",
            reverse("emergencia_api:dispositivo-entregas", args=[grande.pk]) + "?pendientes=1",
        ),
    ]
    abierto = casos.filter(estado__in=[Estado.NUEVO, Estado.EN_GESTION]).order_by("pk").first()
    if abierto:
        rutas.append(_t("E-ficha_caso_abierto", "mesa", reverse("emergencia:caso_detalle", args=[abierto.pk])))
    from django.db.models import Count

    largo = casos.filter(estado=Estado.ALOJADO).annotate(n=Count("trazas")).order_by("-n", "pk").first()
    if largo:
        rutas.append(_t("E-ficha_caso_100_trazas", "mesa", reverse("emergencia:caso_detalle", args=[largo.pk])))
    ingreso = Derivacion.objects.filter(dispositivo=grande, caso__estado=Estado.INGRESO_EN_CURSO).first()
    if ingreso:
        rutas.append(
            _t(
                "E-api_dispositivo_plazas_caso",
                "guardia_api",
                reverse("emergencia_api:dispositivo-plazas", args=[grande.pk]) + f"?caso={ingreso.caso_id}",
            )
        )
    # Un alojado de verdad: el responsable de un caso ALOJADO que tiene la estadía abierta en el grande.
    responsables = casos.filter(estado=Estado.ALOJADO, derivaciones__dispositivo=grande).values("grupo__responsable_id")
    estadia = (
        Estadia.objects.filter(dispositivo=grande, estado="ACTIVA", ciudadano_id__in=responsables)
        .select_related("ciudadano")
        .first()
    )
    if estadia:
        rutas.append(
            _t(
                "E-api_dispositivo_buscar_alojado",
                "guardia_api",
                reverse("emergencia_api:dispositivo-buscar", args=[grande.pk]) + f"?dni={estadia.ciudadano.dni}",
            )
        )
    # Una persona del padrón que no está en ningún caso: la búsqueda recorre el camino de «una familia, un caso
    # abierto» (Cambio 579) hasta el final y no encuentra nada. Es el costo que paga cada DNI que llega a la puerta.
    from legajos.models import Ciudadano
    from programas.models import GrupoFamiliar, IntegranteGrupo

    for sin_caso in Ciudadano.objects.order_by("pk")[:300]:
        if (
            not GrupoFamiliar.objects.filter(responsable_id=sin_caso.pk).exists()
            and not IntegranteGrupo.objects.filter(ciudadano_id=sin_caso.pk).exists()
        ):
            rutas.append(
                _t(
                    "E-api_dispositivo_buscar_padron_sin_caso",
                    "guardia_api",
                    reverse("emergencia_api:dispositivo-buscar", args=[grande.pk]) + f"?dni={sin_caso.dni}",
                )
            )
            break
    entrega = EntregaKit.objects.filter(dispositivo=grande, estado="EN_CAMINO").order_by("pk").first()
    if entrega:
        rutas.append(
            _t("E-api_entrega_detalle", "guardia_api", reverse("emergencia_api:entrega-detail", args=[entrega.pk]))
        )
        rutas.append(_t("E-entrega_detalle_web", "mesa", reverse("emergencia:entrega_detalle", args=[entrega.pk])))
    return rutas


def dispositivos():
    from programas.models import (
        AdjuntoBitacora,
        AdjuntoRespuestaRelevamiento,
        Dispositivo,
        Edificio,
        InspeccionEdificio,
    )

    grande = Dispositivo.objects.filter(codigo="BENCH-D-GRANDE").first()
    if grande is None:
        return []
    detalle = reverse("dispositivos:detalle", args=[grande.pk])
    rutas = [
        _t("D-lista", "admin_disp", reverse("dispositivos:lista")),
        _t("D-detalle_grande", "admin_disp", detalle),
        _t("D-historial_pag_1", "admin_disp", detalle + "?tab=historial&historial_page=1"),
        _t("D-historial_pag_profunda", "admin_disp", detalle + "?tab=historial&historial_page=99999"),
        _t("D-bitacora_censo", "admin_disp", reverse("dispositivos:bitacora", args=[grande.pk])),
        _t("D-estadias", "admin_disp", detalle + "?tab=estadias"),
        _t("D-alta_form", "admin_disp", reverse("dispositivos:crear")),
        _t("D-edificios", "admin_disp", reverse("dispositivos:edificios")),
        _t("D-edificios_pag_profunda", "admin_disp", reverse("dispositivos:edificios") + "?page=200"),
        _t("D-edificios_estado_critico", "admin_disp", reverse("dispositivos:edificios") + "?estado=CRITICO"),
        _t("D-edificios_estado_sin_relevar", "admin_disp", reverse("dispositivos:edificios") + "?estado=SIN_RELEVAR"),
        _t("D-relevamientos_p21_admin", "admin_disp", reverse("dispositivos:relevamientos")),
        _t("D-relevamientos_p21_coordinador", "coordinador", reverse("dispositivos:relevamientos")),
        _t("D-padron_csv", "admin_disp", reverse("dispositivos:exportar", args=["padron", "csv"])),
        _t("D-padron_xlsx", "admin_disp", reverse("dispositivos:exportar", args=["padron", "xlsx"])),
    ]
    edificio = Edificio.objects.filter(codigo__startswith="BENCH-ED-").order_by("pk").first()
    if edificio:
        rutas.append(
            _t("D-edificio_detalle", "admin_disp", reverse("dispositivos:edificio_detalle", args=[edificio.pk]))
        )
    inspeccion = (
        InspeccionEdificio.objects.filter(edificio__codigo__startswith="BENCH-ED-", estado="REALIZADA")
        .order_by("pk")
        .first()
    )
    if inspeccion:
        rutas.append(
            _t(
                "D-relevamiento_informe",
                "admin_disp",
                reverse("dispositivos:relevamiento_informe", args=[inspeccion.pk]),
            )
        )
    for clave, modelo, prefijo in (
        ("D-media_adjunto_bitacora", AdjuntoBitacora, "dispositivos/bitacora/bench/"),
        ("D-media_adjunto_relevamiento", AdjuntoRespuestaRelevamiento, "dispositivos/formularios/bench/rel-"),
    ):
        filas = modelo.objects.filter(archivo__startswith=prefijo)
        total = filas.count()
        if total:
            # El de en medio: el archivo existe en disco (lo escribe escalar_dispositivos.py).
            adjunto = filas.order_by("pk")[total // 2]
            rutas.append(_t(clave, "admin_disp", "/media/" + str(adjunto.archivo)))
    return rutas


def construir():
    """(targets, clientes) de las dos familias; ``([], {})`` si el banco no está sembrado."""
    targets = emergencia() + dispositivos()
    return (targets, clientes()) if targets else ([], {})
