"""Lo que comparten la ficha del dispositivo y la pantalla «Sectores y plazas»: el mapa de plazas y sus acciones.

Vive **fuera de `programas/views/`** a propósito, como `mixins_dispositivos`: lo usan `dispositivos_legajo`
(la solapa de la ficha) y `views/dispositivos_sectores` (la pantalla de siempre), y una vista que le pide algo a
otra vista es lo que mide el ratchet de `programas/tests/test_arquitectura.py`. `dispositivos_legajo` re-exporta
los helpers que ya importaba de acá.
"""

from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from core.rbac import puede
from programas.forms_dispositivos import (
    AUTO_ID_PLAZA_LIBERAR,
    AUTO_ID_PLAZA_PRESTAR,
    AUTO_ID_PLAZA_RESERVAR,
    AUTO_ID_PLAZA_SACAR,
    AgregarPlazasForm,
    CambioPlazaForm,
    LiberarPlazaForm,
    PlazaForm,
    PrestarPlazaForm,
    ReservarPlazaForm,
    SacarPlazaDeServicioForm,
    SectorForm,
)
from programas.mixins_dispositivos import _entero
from programas.models import (
    Estadia,
    Plaza,
    Sector,
)
from programas.selectors.capacidad_dispositivo import plazas_dadas_de_baja, sectores_inactivos
from programas.services.dispositivos import q_edificios_en_alcance
from programas.services.estadias import (
    CAP_ADMITIR,
    CAP_EGRESAR,
    CAP_VER_CIUDADANO,
    puede_ingresar_persona,
)
from programas.services.ingreso import plazas_para_ingresar
from programas.services.plazas import motivo_sin_ampliar_capacidad, puede_configurar_plazas
from programas.services.sectores_plazas import (
    ACCION_BAJA,
    ACCION_FUERA_SERVICIO,
    ACCION_LIBERAR,
    ACCION_PRESTAR,
    ACCION_RESERVAR,
    ACCION_REUBICAR,
    ACCION_VOLVER,
    MOTIVO_PLAZA_OCUPADA,
    PARAM_EDIFICIO_SECTORES,
    bloqueo_de_plaza,
    datos_para_el_modal,
    filtro_de_edificio,
    plaza_para_accion,
    sectores_con_plazas,
)
from programas.views.ajax_utils import is_ajax


def _q_sectores_visibles(usuario):
    """Los sectores de los edificios que ``usuario`` alcanza leyendo (``Q`` sobre ``Sector``; RN4)."""

    return q_edificios_en_alcance(usuario, "dispositivo.ver", "dispositivo_id", "edificio_id")


def _q_plazas_visibles(usuario):
    return q_edificios_en_alcance(usuario, "dispositivo.ver", "sector__dispositivo_id", "sector__edificio_id")


#: Valor de `?opcion=` con el que se pide abrir directo el formulario de reubicar de una plaza con menú.
OPCION_REUBICAR = "reubicar"
#: Valor de `?fragmento=` con el que el mapa pide, por AJAX, solo el cuerpo del modal de reubicar.
FRAGMENTO_REUBICAR = "reubicar"


#: Adónde manda el modal de cada acción. La vista lo resuelve con `reverse`: el template
#: no arma URLs y el parámetro `?plaza=` nunca se usa como destino.
URL_DE_ACCION = {
    ACCION_RESERVAR: "dispositivos:plaza_reservar",
    ACCION_PRESTAR: "dispositivos:plaza_prestar",
    ACCION_LIBERAR: "dispositivos:plaza_liberar",
    ACCION_FUERA_SERVICIO: "dispositivos:plaza_fuera_servicio",
    ACCION_VOLVER: "dispositivos:plaza_volver_servicio",
    ACCION_BAJA: "dispositivos:plaza_baja",
}


#: Los dos formularios de P7 tienen un campo `motivo`: con el `id_%s` de Django los dos
#: controles saldrían con `id="id_motivo"` y el label del segundo apuntaría al primero.
AUTO_ID_CAMBIO = "cambio_%s"


def _sectores_para_cambio(dispositivo, usuario):
    """Las plazas del dispositivo con su estado, de `ocupacion.estado_de_plazas` (vía el asistente de ingreso).

    Es la misma fuente que el mapa y que el ingreso: acá no se decide qué es una plaza libre.
    """

    sectores, _elegibles = plazas_para_ingresar(dispositivo, usuario=usuario)
    return sectores


def _form_de_cambio_de_plaza(dispositivo, estadia, sectores):
    """El formulario del modal «Cambiar de plaza» (o «Asignar plaza») y adónde envía.

    Lo arman el detalle del dispositivo (P4), el mapa de plazas (P5) y la estadía (P7): cada uno
    decide qué hace si no hay plazas libres (`form.hay_plazas_libres`); el POST es siempre
    `dispositivos:cambiar_plaza`, que es quien aplica la regla.
    """

    form = CambioPlazaForm(estadia=estadia, sectores=sectores, auto_id=AUTO_ID_CAMBIO)
    return form, reverse("dispositivos:cambiar_plaza", args=[dispositivo.pk, estadia.pk])


class SectoresPlazasMixin:
    """«Sectores y plazas» (MVP v2, etapas 1 y 5 · P5): el mapa de plazas y sus acciones.

    Lo comparten la solapa de la ficha (`DispositivoDetailView`) y la pantalla de siempre
    (`DispositivoSectoresView`, que sigue respondiendo): las dos dibujan `sectores/_cuerpo.html` con
    el mismo contexto, así que no hay dos armados que se separen. `en_solapa` y `param_editar_sector`
    son lo único que cambia: en la ficha los enlaces conservan `?tab=sectores` y el sector se edita
    con `?editar_sector=` (`?sector=` ya es el filtro de Estadías).

    El modal de la acción se abre con `?plaza=<id>` y lo arma el servidor, como los de P21:
    el contenido depende del estado de esa plaza y la celda del mapa solo sabe navegar. Si
    la plaza no se puede gestionar —ajena, inexistente, de un sector dado de baja o sin la
    capacidad— el modal no se abre y el aviso es el mismo para los cuatro casos.

    «Editar sector» se abre igual, con `?<param_editar_sector>=<id>` (`sector` en la pantalla suelta,
    `editar_sector` en la ficha). «Nuevo sector» y «+ Agregar plazas» no:
    no dependen de un registro, así que sus formularios llegan con la página y los abre el
    botón, como el modal de la golden. Los tres se arman **solo** si quien mira puede
    configurar las plazas: sin eso, el formulario llegaría armado a quien la acción va a
    rechazar. El mapa sigue en las consultas fijas de su presupuesto, y el selector del lote
    en las del suyo; el alta del sector no consulta.
    """

    en_solapa = False
    param_editar_sector = "sector"

    def get(self, request, *args, **kwargs):
        if request.GET.get("fragmento") == FRAGMENTO_REUBICAR and is_ajax(request):
            return self._fragmento_reubicar(request)
        return super().get(request, *args, **kwargs)

    def _fragmento_reubicar(self, request):
        """Solo el cuerpo del modal «Cambiar de plaza», para abrirlo sin recargar la página.

        Corta **antes** de armar el mapa: resuelve únicamente la plaza pedida, con el mismo
        gate de alcance y de capacidades que `?plaza=<id>`, y el mismo 404 para la ajena, la
        inexistente, la que no se reubica y la que el usuario no puede gestionar. Es lo que
        el mapa no puede traer por plaza sin pasarse de su presupuesto: la estadía y las
        plazas libres. Lo dibuja la misma parcial que el camino `?plaza=<id>` sin JS.
        """

        dispositivo = self.object = self.get_object()
        usuario = request.user
        puede_liberar = self._puede_operar(dispositivo, CAP_ADMITIR)
        configura_plazas = puede_configurar_plazas(usuario, dispositivo)
        # Sin filtro en el pedido (lo normal) no se consulta nada: el fragmento sigue costando lo de antes.
        pedido_edificio = request.GET.get(PARAM_EDIFICIO_SECTORES, "")
        edificio_id = filtro_de_edificio(usuario, dispositivo, pedido_edificio)[0] if pedido_edificio else None
        pk = _entero(request.GET.get("plaza", ""))
        accion = (
            plaza_para_accion(
                dispositivo,
                pk,
                puede_liberar=puede_liberar,
                puede_configurar_plazas=configura_plazas,
                puede_ver_personas=puede(usuario, CAP_VER_CIUDADANO),
                usuario=usuario,
            )
            if pk is not None
            else None
        )
        if accion is None or ACCION_REUBICAR not in accion["acciones"]:
            raise Http404
        context = {
            "dispositivo": dispositivo,
            "plaza_accion": accion,
            "puede_configurar_plazas": configura_plazas,
            "qs_sectores": self._qs_sectores(edificio_id),
            "edificio_filtrado": edificio_id,
        }
        if not self._preparar_reubicar(context, dispositivo, accion):
            raise Http404
        return render(request, "programas/dispositivos/sectores/_modal_reubicar.html", context)

    def _qs_sectores(self, edificio_id):
        """Lo que los enlaces del cuerpo conservan: la solapa y el filtro «Edificio» (el resto abre modales)."""

        qs = "tab=sectores&" if self.en_solapa else ""
        if edificio_id is not None:
            qs += f"{PARAM_EDIFICIO_SECTORES}={edificio_id}&"
        return qs

    def _preparar_sectores_y_plazas(self, context, dispositivo):
        """Arma todo lo que dibuja `sectores/_cuerpo.html` y lo suma a ``context``.

        El mapa va en `sectores_mapa` (y no en `sectores`, que en la ficha ya es el censo por sector).
        El filtro «Edificio» acota el mapa, los totales y los inactivos; su valor se valida contra los
        edificios que quien mira alcanza (`filtro_de_edificio`): uno ajeno, inexistente o fuera de su
        alcance se ignora y queda «Todos». Con uno solo en alcance no hay filtro.
        """

        usuario = self.request.user
        puede_liberar = self._puede_operar(dispositivo, CAP_ADMITIR)
        configura_plazas = puede_configurar_plazas(usuario, dispositivo)

        edificio_id, pildoras = filtro_de_edificio(
            usuario, dispositivo, self.request.GET.get(PARAM_EDIFICIO_SECTORES, "")
        )
        ver_inactivos = self.request.GET.get("inactivos") == "1"
        # Lo que los enlaces del cuerpo conservan: la solapa y el filtro (el resto de los parámetros abre modales).
        qs = self._qs_sectores(edificio_id)
        ocultos = [("tab", "sectores")] if self.en_solapa else []
        if ver_inactivos:
            ocultos.append(("inactivos", "1"))

        datos = sectores_con_plazas(
            dispositivo,
            puede_liberar=puede_liberar,
            puede_configurar_plazas=configura_plazas,
            puede_ver_personas=puede(usuario, CAP_VER_CIUDADANO),
            puede_egresar=self._puede_operar(dispositivo, CAP_EGRESAR),
            usuario=usuario,
            edificio_id=edificio_id,
            qs_url=qs,
        )
        context["sectores_mapa"] = datos.pop("sectores")
        context.update(datos)
        context["qs_sectores"] = qs
        context["en_solapa"] = self.en_solapa
        context["param_editar_sector"] = self.param_editar_sector
        context["pildoras_sectores"] = pildoras
        context["edificio_filtrado"] = edificio_id
        context["ocultos_sectores"] = ocultos
        context["puede_reubicar"] = puede_liberar
        # Los inactivos se piden con `?inactivos=1`: sin el parámetro no cuestan ninguna consulta.
        context["ver_inactivos"] = ver_inactivos
        if ver_inactivos:
            q_sectores = _q_sectores_visibles(usuario)
            q_plazas = _q_plazas_visibles(usuario)
            if edificio_id is not None:
                q_sectores &= Q(edificio_id=edificio_id)
                q_plazas &= Q(sector__edificio_id=edificio_id)
            context["sectores_inactivos"] = sectores_inactivos(dispositivo, q_alcance=q_sectores)
            context["plazas_dadas_de_baja"] = plazas_dadas_de_baja(dispositivo, q_alcance=q_plazas)
        context["puede_configurar_plazas"] = configura_plazas
        # Las altas (sector nuevo, lote de plazas) solo se ofrecen donde el servicio las admite.
        context["puede_ampliar_capacidad"] = configura_plazas and not motivo_sin_ampliar_capacidad(dispositivo)
        self._preparar_modal_de_plaza(context, dispositivo, puede_liberar, configura_plazas)
        self._preparar_modal(context, dispositivo, puede_liberar, configura_plazas)
        self._preparar_modales_de_configuracion(context, dispositivo, configura_plazas)
        return context

    def _preparar_modales_de_configuracion(self, context, dispositivo, puede_configurar_plazas):
        """«Nuevo sector», «Editar sector» y «+ Agregar plazas»: cuál abrir y con qué formulario.

        Un sector ajeno, inexistente o dado de baja no abre nada y avisa lo mismo que una
        plaza no gestionable: tres respuestas distintas serían un oráculo de ids. El sector
        dado de baja entra igual —se edita para reactivarlo—, lo que no abre es el que no
        es de este dispositivo.
        """

        if not puede_configurar_plazas:
            return
        # Las altas no dependen de un registro: llegan con la página y las abre el botón, sin el
        # viaje al servidor que se veía como un F5. El alta del sector lleva su propio auto_id
        # porque convive con «Editar sector», que es el mismo formulario.
        if context["puede_ampliar_capacidad"]:
            context["form_sector_nuevo"] = SectorForm(dispositivo=dispositivo, auto_id="id_nuevo_%s")
            context["url_sector_nuevo"] = reverse("dispositivos:sector_crear", args=[dispositivo.pk])
        pedido = self.request.GET.get(self.param_editar_sector, "")
        # `?sector=nuevo` es el enlace de antes al alta: se ignora en vez de avisar que ese
        # sector no se puede editar.
        if pedido and pedido != "nuevo":
            pk = _entero(pedido)
            sector = (
                Sector.objects.filter(pk=pk, dispositivo=dispositivo)
                .filter(_q_sectores_visibles(self.request.user))
                .first()
                if pk is not None
                else None
            )
            if sector is None:
                messages.warning(self.request, "Ese sector ya no se puede editar desde acá.")
            else:
                context["sector_en_edicion"] = sector
                context["form_sector"] = SectorForm(dispositivo=dispositivo, sector=sector)
                context["url_sector"] = reverse("dispositivos:sector_editar", args=[dispositivo.pk, sector.pk])

        if context["sectores_mapa"] and context["puede_ampliar_capacidad"]:
            context["form_plazas"] = AgregarPlazasForm(
                dispositivo=dispositivo,
                sectores=Sector.objects.filter(dispositivo=dispositivo, activo=True).filter(
                    _q_sectores_visibles(self.request.user)
                ),
            )
            context["url_plazas"] = reverse("dispositivos:plazas_agregar", args=[dispositivo.pk])

        pedido = self.request.GET.get("editar_plaza", "")
        if pedido:
            pk = _entero(pedido)
            plaza = (
                Plaza.objects.filter(pk=pk, sector__dispositivo=dispositivo)
                .filter(_q_plazas_visibles(self.request.user))
                .first()
                if pk is not None
                else None
            )
            if plaza is None:
                messages.warning(self.request, "Esa plaza ya no se puede editar desde acá.")
            else:
                context["plaza_en_edicion"] = plaza
                context["form_editar_plaza"] = PlazaForm(dispositivo=dispositivo, plaza=plaza)
                context["url_editar_plaza"] = reverse("dispositivos:plaza_editar", args=[dispositivo.pk, plaza.pk])

    def _preparar_modal_de_plaza(self, context, dispositivo, puede_liberar, puede_configurar_plazas):
        """El modal de una plaza, armado **una vez** y sin consultas: lo abre `abrirPlaza(<id>)`.

        Los formularios (reservar, prestar, sacar, liberar) llegan con la página y el `action`
        del `<form>` se arma en el navegador con la URL de la plaza elegida: las URLs viajan
        con `__pk__` en el lugar del id, una por acción, y no una por plaza. Los datos de
        cada plaza (`plazas_modal`) ya los calculó el mapa. Sin ninguna capacidad no se arma nada.
        """

        context["urls_plaza"] = {}
        context["motivo_plaza_ocupada"] = MOTIVO_PLAZA_OCUPADA
        if not (puede_liberar or puede_configurar_plazas):
            return
        # Las sugerencias de personas piden lo mismo que reservar y prestar (admitir + ver personas):
        # a quien no las puede usar no se le ofrecen, y el campo queda como siempre.
        url_sugerencias = (
            reverse("dispositivos:personas_buscar", args=[dispositivo.pk])
            if puede_ingresar_persona(
                self.request.user, dispositivo, puede_admitir=self._puede_operar(dispositivo, CAP_ADMITIR)
            )
            else None
        )
        context["form_reservar"] = ReservarPlazaForm(auto_id=AUTO_ID_PLAZA_RESERVAR, url_sugerencias=url_sugerencias)
        context["form_prestar"] = PrestarPlazaForm(auto_id=AUTO_ID_PLAZA_PRESTAR, url_sugerencias=url_sugerencias)
        context["form_sacar"] = SacarPlazaDeServicioForm(auto_id=AUTO_ID_PLAZA_SACAR)
        context["form_liberar"] = LiberarPlazaForm(auto_id=AUTO_ID_PLAZA_LIBERAR)
        context["urls_plaza"] = {
            accion: reverse(nombre, args=[dispositivo.pk, 0]).replace("/plazas/0/", "/plazas/__pk__/")
            for accion, nombre in URL_DE_ACCION.items()
        }

    def _preparar_modal(self, context, dispositivo, puede_liberar, puede_configurar_plazas):
        """`?plaza=<id>`: el enlace directo, y el camino de vuelta a una plaza concreta.

        Resuelve las acciones de la plaza con `plaza_para_accion` y, si no hay ninguna que ofrecer, avisa
        con un mensaje. Las acciones que se arman en el navegador (todas menos reubicar) abren el modal ya
        elegido (`plaza_inicial`, sumando la plaza a `plazas_modal` si quedó más allá del tope de la
        grilla); la reubicación, que depende de la estadía, la arma el servidor en `_preparar_reubicar`. Una
        plaza ocupada abre el formulario de reubicar solo si es lo único que ofrece o si la URL trae
        `&opcion=reubicar` (el regreso de «Cambiar de plaza»); con más opciones llega el menú.
        """

        pedida = self.request.GET.get("plaza", "")
        if not pedida:
            return
        pk = _entero(pedida)
        accion = (
            plaza_para_accion(
                dispositivo,
                pk,
                puede_liberar=puede_liberar,
                puede_configurar_plazas=puede_configurar_plazas,
                puede_ver_personas=puede(self.request.user, CAP_VER_CIUDADANO),
                puede_egresar=self._puede_operar(dispositivo, CAP_EGRESAR),
                usuario=self.request.user,
            )
            if pk is not None
            else None
        )
        if accion is None:
            messages.warning(self.request, "Esa plaza ya no se puede gestionar desde acá.")
            return
        plaza = accion["plaza"]
        abre_reubicar = ACCION_REUBICAR in accion["acciones"] and (
            accion["acciones"] == [ACCION_REUBICAR] or self.request.GET.get("opcion") == OPCION_REUBICAR
        )
        if abre_reubicar or ACCION_REUBICAR not in accion["acciones"]:
            context["plaza_accion"] = accion
        if abre_reubicar:
            # Su destino es el de la estadía (`url_cambiar_plaza`), no una acción de plaza.
            if not self._preparar_reubicar(context, dispositivo, accion):
                context.pop("plaza_accion")
                messages.warning(self.request, "Esa plaza ya no se puede gestionar desde acá.")
            return
        # Una plaza más allá del tope de la grilla no está en `plazas_modal`: se suma acá.
        context["plazas_modal"].setdefault(
            plaza.pk,
            datos_para_el_modal(
                plaza,
                accion["estado"],
                accion["acciones"],
                accion["bloqueo"],
                accion["enlaces"],
                con_reserva_abierta=accion["reserva"] is not None,
            ),
        )
        context["plaza_inicial"] = plaza.pk

    def _preparar_reubicar(self, context, dispositivo, accion):
        """Reubicar a quien ocupa la plaza: el formulario del cambio de plaza de P7, dentro del mapa.

        Se arma **solo** con el modal abierto (el mapa cerrado conserva sus consultas
        fijas). El POST va a `dispositivos:cambiar_plaza`, que es quien aplica la regla.
        Sin plazas libres el modal avisa y no trae formulario. Devuelve `False` si la persona
        ya no está en la plaza (no hay a quién mover); quien llama decide cómo avisarlo.
        """

        estadia = (
            Estadia.objects.activas()
            .filter(plaza=accion["plaza"])
            .select_related("ciudadano", "dispositivo", "plaza__sector")
            .first()
        )
        if estadia is None:
            # La persona se fue entre el dibujo del mapa y el clic: no hay a quién mover.
            return False
        estadia.persona_visible = (
            estadia.ciudadano.apellido_nombre if puede(self.request.user, CAP_VER_CIUDADANO) else "Persona alojada"
        )
        form, url = _form_de_cambio_de_plaza(
            dispositivo, estadia, _sectores_para_cambio(dispositivo, self.request.user)
        )
        # Bajo `reubicar` y no en `form_cambio`/`estadia_cambio`: en la solapa de la ficha esas claves son las
        # del modal «Cambiar plaza» de Estadías, y abrirían los dos.
        reubicar = {"estadia": estadia}
        accion["bloqueo"] = bloqueo_de_plaza(
            accion["estado"], ACCION_REUBICAR, hay_plazas_libres=form.hay_plazas_libres
        )
        if not accion["bloqueo"]:
            reubicar.update(form=form, url=url)
        context["reubicar"] = reubicar
        return True
