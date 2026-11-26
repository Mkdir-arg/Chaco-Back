"""Pantallas de operar el stock de un edificio (análisis 010, PR 5: «Entregar a persona»).

La vista **no decide permisos ni saldos**: orquesta. Cada acción llama a ``programas/services/stock.py`` —el mismo que
usará la API de la app— y traduce lo que contesta, como ``emergencia_kits``:

* ``PermissionDenied`` del servicio → 403. No se atrapa.
* :class:`SaldoInsuficiente` → vuelve a la pantalla con el saldo **de ahora** en cada fila (RN-010-03).
* ``ValidationError`` → el mensaje del servicio, en su campo si la pantalla lo tiene.

**Dos capas de autorización**, las dos con test: la vista (``_lugar``) y el servicio, que vuelve a exigir todo.

* Sin ``stock.entregar`` sobre **ninguna** institución, 403: no abre esta parte del módulo.
* Con la capacidad en otra institución o en otro edificio, o con una institución que no lleva stock, **404**: igual
  que un id inexistente, sin confirmar que existe.
* Con alcance sobre el edificio pero sin lo que entregar exige además (``stock.ver`` y ``ciudadano.ver``), 403.

**«Entregar a persona» es una sola pantalla y no usa la sesión**: el GET ``?dni=&sexo=`` resuelve a la persona sin
escribir nada; el POST lleva a la persona en ocultos, el servicio la vuelve a resolver y la entrega entera es una
operación idempotente por ``uuid_cliente``.
"""

from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from core import rbac
from programas.forms_cantidades import ids_con_cantidad
from programas.forms_stock import (
    DestinoForm,
    EntregaPersonaForm,
    IngresoForm,
    PersonaForm,
    TraspasoForm,
    valor_de_destino,
)
from programas.selectors import stock as selectores
from programas.services import stock as servicio
from programas.services.dispositivos import (
    CAP_STOCK_ENTREGAR,
    CAP_STOCK_INGRESAR,
    dispositivos_en_alcance,
    puede_operar_edificio,
)
from programas.services.edificio_operativo import edificio_de_la_institucion
from programas.services.estadias import CAP_VER_CIUDADANO
from programas.services.stock_personas import PersonaSinDatos, filas_de_historial, texto_de_la_persona

TEMPLATE_ENTREGAR = "programas/dispositivos/stock/entregar.html"
TEMPLATE_INGRESAR = "programas/dispositivos/stock/ingresar.html"
TEMPLATE_TRASPASAR = "programas/dispositivos/stock/traspasar.html"
AUTO_ID_ENTREGA = "entrega_%s"
AUTO_ID_INGRESO = "ingreso_%s"
AUTO_ID_TRASPASO = "traspaso_%s"
COLUMNAS_EN_STOCK = ["En stock"]


class _OperarStockView(LoginRequiredMixin, View):
    """Lo común de las pantallas que operan el stock de **un edificio**: el lugar, sus dos 4xx y las URL de vuelta.

    ``CAPACIDAD`` es la que abre la pantalla (``stock.entregar``, ``stock.ingresar``); cada subclase suma lo suyo a
    ``_puede_abrir``. La acción vuelve a exigir todo en el servicio.
    """

    CAPACIDAD = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.dispositivo, self.edificio = self._lugar(request.user, kwargs["pk"], kwargs["edificio_pk"])
        return super().dispatch(request, *args, **kwargs)

    def _puede_abrir(self, usuario, dispositivo, edificio):
        """Lo que la pantalla exige **además** de operar el edificio: ``stock.ver`` ahí. Sin esto, 403."""

        return servicio.puede_ver_stock(usuario, dispositivo, edificio.pk)

    def _lugar(self, usuario, dispositivo_pk, edificio_pk):
        """``(institución, edificio)`` sobre los que ``usuario`` opera, o 403 / 404 (ver el docstring del módulo)."""

        en_alcance = dispositivos_en_alcance(usuario, self.CAPACIDAD)
        dispositivo = en_alcance.select_related("tipo").filter(pk=dispositivo_pk).first()
        if dispositivo is None:
            if not en_alcance.exists():
                raise PermissionDenied
            raise Http404("Institución inexistente.")
        edificio = edificio_de_la_institucion(usuario, dispositivo, edificio_pk)
        if (
            edificio is None
            or not servicio.lleva_stock(dispositivo)
            or not puede_operar_edificio(usuario, dispositivo, edificio.pk, self.CAPACIDAD)
        ):
            raise Http404("Ese edificio no es de esta institución o no está en tu alcance.")
        if not self._puede_abrir(usuario, dispositivo, edificio):
            raise PermissionDenied
        return dispositivo, edificio

    def _url_stock(self):
        return reverse("dispositivos:edificio_operativo", args=[self.dispositivo.pk, self.edificio.pk]) + "?tab=stock"

    def _saldos(self, cargados=()):
        """Los insumos con fila: los que **hoy** tienen saldo en este edificio **más** los que llegan cargados (una consulta).

        Un insumo que llegó a 0 entre el GET y el POST conserva su fila: el servicio contesta ``SaldoInsuficiente`` y
        la pantalla dice «Hay 0 y pediste 3» en vez de operar el resto sin avisar.
        """

        cargados = set(cargados)
        return [
            (saldo.item, saldo.cantidad)
            for saldo in selectores.saldos_de(self.dispositivo, self.edificio)
            if saldo.cantidad > 0 or saldo.item_id in cargados
        ]

    def _terminada(self, request, operacion, hecho, ya_estaba):
        """Éxito, o reenvío del mismo ``uuid_cliente`` (``ya_existia``): en los dos casos vuelve a la solapa Stock."""

        if getattr(operacion, "ya_existia", False):
            messages.info(request, ya_estaba)
        else:
            messages.success(request, hecho)
        return redirect(self._url_stock())

    @staticmethod
    def _con_otro_identificador(datos):
        """Una copia de ``datos`` con un ``uuid_cliente`` nuevo: el reintento tras ``UuidEnUso`` es una operación nueva."""

        datos = datos.copy()
        datos["uuid_cliente"] = str(uuid4())
        return datos


class EntregarAPersonaView(_OperarStockView):
    """«Entregar a persona»: descuenta insumos del stock de un edificio y los asienta a nombre de una persona."""

    CAPACIDAD = CAP_STOCK_ENTREGAR

    def _puede_abrir(self, usuario, dispositivo, edificio):
        return super()._puede_abrir(usuario, dispositivo, edificio) and rbac.puede(usuario, CAP_VER_CIUDADANO)

    def _url_entregar(self):
        return reverse("dispositivos:stock_entregar", args=[self.dispositivo.pk, self.edificio.pk])

    def _form_entrega(self, datos=None, initial=None):
        """El formulario de la entrega con los saldos de ahora. ``auto_id`` propio: los ocultos repiten los ids del GET."""

        cargados = ids_con_cantidad(datos) if datos is not None else ()
        return EntregaPersonaForm(datos, initial=initial, insumos=self._saldos(cargados), auto_id=AUTO_ID_ENTREGA)

    def _pantalla(self, request, persona_form, form=None, persona=None, historial=(), status=200):
        contexto = {
            "dispositivo": self.dispositivo,
            "edificio": self.edificio,
            "persona_form": persona_form,
            "persona": persona,
            "form": form,
            "url_stock": self._url_stock(),
            "url_entregar": self._url_entregar(),
        }
        if persona is not None:
            contexto.update(
                texto_persona=texto_de_la_persona(persona),
                historial=filas_de_historial(historial),
                tope_historial=selectores.HISTORIAL_DE_PERSONA,
                filas=form.filas() if form.insumos else [],
                columnas_info=COLUMNAS_EN_STOCK,
                sin_insumos=not form.insumos,
            )
        return render(request, TEMPLATE_ENTREGAR, contexto, status=status)

    def _mostrar_persona(self, request, persona_form, form_de_entrega, resuelta=None):
        """Resuelve a la persona **sin escribir** y dibuja la pantalla; si no se puede, la pantalla pide lo que falta.

        ``form_de_entrega`` es la función que arma el formulario de la entrega con los saldos de ahora. ``resuelta`` es
        la persona que el servicio ya resolvió en un POST rechazado: no se consulta de nuevo al Registro.
        """

        datos = persona_form.cleaned_data
        try:
            persona, historial = servicio.consultar_persona(
                self.request.user,
                self.dispositivo,
                self.edificio,
                datos["dni"],
                datos["sexo"],
                datos["nombre"],
                datos["apellido"],
                persona=resuelta,
            )
        except PersonaSinDatos as error:
            persona_form.pedir_nombre = True
            persona_form.add_error(None, error)
            return self._pantalla(request, persona_form)
        except ValidationError as error:
            persona_form.pedir_nombre = bool(datos["nombre"] or datos["apellido"])
            persona_form.agregar_errores_del_servicio(error)
            return self._pantalla(request, persona_form)
        persona_form.pedir_nombre = persona.origen == "manual"
        return self._pantalla(request, persona_form, form_de_entrega(), persona, historial)

    def get(self, request, **_url):
        if "dni" not in request.GET:
            return self._pantalla(request, PersonaForm())
        persona_form = PersonaForm(request.GET)
        if not persona_form.is_valid():
            return self._pantalla(request, persona_form)

        def sin_cargar():
            datos = persona_form.cleaned_data
            iniciales = {clave: datos[clave] for clave in ("dni", "sexo", "nombre", "apellido")}
            return self._form_entrega(initial={**iniciales, "uuid_cliente": uuid4()})

        return self._mostrar_persona(request, persona_form, sin_cargar)

    def post(self, request, **_url):
        persona_form = PersonaForm(request.POST)
        if not persona_form.is_valid():
            return self._pantalla(request, persona_form)
        form = self._form_entrega(request.POST)
        resuelta = None
        if form.is_valid():
            try:
                operacion = servicio.entregar_a_persona(
                    request.user,
                    self.dispositivo,
                    self.edificio,
                    form.cleaned_data["dni"],
                    form.lineas(),
                    sexo=form.cleaned_data["sexo"],
                    nombre=form.cleaned_data["nombre"],
                    apellido=form.cleaned_data["apellido"],
                    observacion=form.cleaned_data["observacion"],
                    uuid_cliente=form.cleaned_data["uuid_cliente"],
                )
            except servicio.SaldoInsuficiente as error:
                # El saldo de ahora (otra entrega pudo haber pasado): se vuelve a leer y se marca cada fila.
                resuelta = getattr(error, "persona", None)
                form = self._form_entrega(request.POST)
                form.full_clean()
                form.agregar_errores_del_servicio(error)
                form.marcar_faltantes(error.faltantes)
            except servicio.UuidEnUso as error:
                # Ese identificador ya fue de otra operación: se regenera para que el reintento sea una entrega nueva.
                resuelta = getattr(error, "persona", None)
                form = self._form_entrega(self._con_otro_identificador(request.POST))
                form.full_clean()
                form.agregar_errores_del_servicio(error)
            except PersonaSinDatos as error:
                persona_form.pedir_nombre = True
                persona_form.add_error(None, error)
                return self._pantalla(request, persona_form)
            except ValidationError as error:
                resuelta = getattr(error, "persona", None)
                form.agregar_errores_del_servicio(error)
            else:
                return self._entregada(request, operacion)
        return self._mostrar_persona(request, persona_form, lambda: form, resuelta)

    def _entregada(self, request, operacion):
        return self._terminada(
            request,
            operacion,
            "Entrega registrada: el stock del edificio ya está descontado.",
            "Esa entrega ya estaba registrada: no se descontó dos veces.",
        )


class IngresarStockView(_OperarStockView):
    """«Ingresar stock»: suma insumos al stock de un edificio con su origen (donación, compra…) y un comprobante de texto."""

    CAPACIDAD = CAP_STOCK_INGRESAR

    def _url_ingresar(self):
        return reverse("dispositivos:stock_ingresar", args=[self.dispositivo.pk, self.edificio.pk])

    def _form(self, datos=None):
        """Con los insumos activos de ahora. ``auto_id`` propio, como en Entregar."""

        insumos = selectores.insumos_para_ingresar(self.dispositivo, self.edificio)
        return IngresoForm(datos, insumos=insumos, auto_id=AUTO_ID_INGRESO)

    def _pantalla(self, request, form, status=200):
        contexto = {
            "dispositivo": self.dispositivo,
            "edificio": self.edificio,
            "form": form,
            "filas": form.filas(),
            "columnas_info": COLUMNAS_EN_STOCK,
            "sin_insumos": not form.insumos,
            "url_stock": self._url_stock(),
            "url_ingresar": self._url_ingresar(),
        }
        return render(request, TEMPLATE_INGRESAR, contexto, status=status)

    def get(self, request, **_url):
        return self._pantalla(request, self._form())

    def post(self, request, **_url):
        form = self._form(request.POST)
        if form.is_valid():
            datos = form.cleaned_data
            try:
                operacion = servicio.ingresar_manual(
                    request.user,
                    self.dispositivo,
                    self.edificio,
                    form.lineas(),
                    datos["origen"],
                    origen_detalle=datos["origen_detalle"],
                    comprobante=datos["comprobante"],
                    uuid_cliente=datos["uuid_cliente"],
                )
            except servicio.UuidEnUso as error:
                form = self._form(self._con_otro_identificador(request.POST))
                form.full_clean()
                form.agregar_errores_del_servicio(error)
            except ValidationError as error:
                form.agregar_errores_del_servicio(error)
            else:
                return self._terminada(
                    request,
                    operacion,
                    "Ingreso registrado: el stock del edificio ya está sumado.",
                    "Ese ingreso ya estaba registrado: no se sumó dos veces.",
                )
        return self._pantalla(request, form)


class TraspasarStockView(_OperarStockView):
    """«Traspasar stock»: pasa insumos de este edificio a otro lugar del alcance de quien traspasa, de inmediato.

    Un GET ``?destino=`` elige el destino de los que da ``destinos_de_traspaso`` (no escribe nada); el POST lo lleva
    en un oculto y el servicio lo vuelve a validar.
    """

    CAPACIDAD = CAP_STOCK_INGRESAR

    def _url_traspasar(self):
        return reverse("dispositivos:stock_traspasar", args=[self.dispositivo.pk, self.edificio.pk])

    def _destinos(self):
        return servicio.destinos_de_traspaso(self.request.user, self.dispositivo, self.edificio)

    def _form(self, datos=None, initial=None):
        cargados = ids_con_cantidad(datos) if datos is not None else ()
        return TraspasoForm(datos, initial=initial, insumos=self._saldos(cargados), auto_id=AUTO_ID_TRASPASO)

    def _pantalla(self, request, destino_form, destinos, elegido=None, form=None):
        contexto = {
            "dispositivo": self.dispositivo,
            "edificio": self.edificio,
            "destino_form": destino_form,
            "sin_destinos": not destinos,
            "destino": elegido,
            "form": form,
            "url_stock": self._url_stock(),
            "url_traspasar": self._url_traspasar(),
            "columnas_info": COLUMNAS_EN_STOCK,
        }
        if elegido is not None and form is not None:
            contexto.update(filas=form.filas() if form.insumos else [], sin_insumos=not form.insumos)
        return render(request, TEMPLATE_TRASPASAR, contexto)

    def get(self, request, **_url):
        destinos = self._destinos()
        if "destino" not in request.GET:
            return self._pantalla(request, DestinoForm(destinos=destinos), destinos)
        destino_form = DestinoForm(request.GET, destinos=destinos)
        elegido = destino_form.elegido()
        if elegido is None:
            return self._pantalla(request, destino_form, destinos)
        iniciales = {"destino": valor_de_destino(*elegido), "uuid_cliente": uuid4()}
        return self._pantalla(request, destino_form, destinos, elegido, self._form(initial=iniciales))

    def post(self, request, **_url):
        destinos = self._destinos()
        destino_form = DestinoForm({"destino": request.POST.get("destino", "")}, destinos=destinos)
        elegido = destino_form.elegido()
        form = self._form(request.POST)
        if form.is_valid():
            destino_dispositivo, destino_edificio = form.ids_de_destino()
            try:
                operacion = servicio.traspasar(
                    request.user,
                    self.dispositivo,
                    self.edificio,
                    destino_dispositivo,
                    destino_edificio,
                    form.lineas(),
                    observacion=form.cleaned_data["observacion"],
                    uuid_cliente=form.cleaned_data["uuid_cliente"],
                )
            except servicio.SaldoInsuficiente as error:
                form = self._form(request.POST)
                form.full_clean()
                form.agregar_errores_del_servicio(error)
                form.marcar_faltantes(error.faltantes)
            except servicio.UuidEnUso as error:
                form = self._form(self._con_otro_identificador(request.POST))
                form.full_clean()
                form.agregar_errores_del_servicio(error)
            except ValidationError as error:
                if hasattr(error, "error_dict") and "destino" in error.error_dict:
                    # El destino no vale (alcance, estado, o ya no está): se vuelve a elegir, sin tabla.
                    if "destino" not in destino_form.errors:
                        destino_form.add_error("destino", error.error_dict["destino"])
                    return self._pantalla(request, destino_form, destinos)
                form.agregar_errores_del_servicio(error)
            else:
                return self._terminada(
                    request,
                    operacion,
                    "Traspaso registrado: el stock ya pasó al destino.",
                    "Ese traspaso ya estaba registrado: no se movió dos veces.",
                )
        if elegido is None:
            return self._pantalla(request, destino_form, destinos)
        return self._pantalla(request, destino_form, destinos, elegido, form)
