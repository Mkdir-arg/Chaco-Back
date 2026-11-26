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
from programas.forms_stock import EntregaPersonaForm, PersonaForm
from programas.selectors import stock as selectores
from programas.services import stock as servicio
from programas.services.dispositivos import CAP_STOCK_ENTREGAR, dispositivos_en_alcance, puede_operar_edificio
from programas.services.edificio_operativo import edificio_de_la_institucion
from programas.services.edificio_stock import filas_de_historial, texto_de_la_persona
from programas.services.estadias import CAP_VER_CIUDADANO
from programas.services.stock_personas import PersonaSinDatos

TEMPLATE_ENTREGAR = "programas/dispositivos/stock/entregar.html"


class EntregarAPersonaView(LoginRequiredMixin, View):
    """«Entregar a persona»: descuenta insumos del stock de un edificio y los asienta a nombre de una persona."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.dispositivo, self.edificio = self._lugar(request.user, kwargs["pk"], kwargs["edificio_pk"])
        return super().dispatch(request, *args, **kwargs)

    def _lugar(self, usuario, dispositivo_pk, edificio_pk):
        """``(institución, edificio)`` sobre los que ``usuario`` entrega, o 403 / 404 (ver el docstring del módulo)."""

        en_alcance = dispositivos_en_alcance(usuario, CAP_STOCK_ENTREGAR)
        dispositivo = en_alcance.select_related("tipo").filter(pk=dispositivo_pk).first()
        if dispositivo is None:
            if not en_alcance.exists():
                raise PermissionDenied
            raise Http404("Institución inexistente.")
        edificio = edificio_de_la_institucion(usuario, dispositivo, edificio_pk)
        if (
            edificio is None
            or not servicio.lleva_stock(dispositivo)
            or not puede_operar_edificio(usuario, dispositivo, edificio.pk, CAP_STOCK_ENTREGAR)
        ):
            raise Http404("Ese edificio no es de esta institución o no está en tu alcance.")
        if not (servicio.puede_ver_stock(usuario, dispositivo, edificio.pk) and rbac.puede(usuario, CAP_VER_CIUDADANO)):
            raise PermissionDenied
        return dispositivo, edificio

    def _url_stock(self):
        return reverse("dispositivos:edificio_operativo", args=[self.dispositivo.pk, self.edificio.pk]) + "?tab=stock"

    def _url_entregar(self):
        return reverse("dispositivos:stock_entregar", args=[self.dispositivo.pk, self.edificio.pk])

    def _saldos(self):
        """Los insumos que se pueden entregar: los que **hoy** tienen saldo en este edificio (una consulta)."""

        return [saldo for saldo in selectores.saldos_de(self.dispositivo, self.edificio) if saldo.cantidad > 0]

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
                filas=form.filas() if form.saldos else [],
                columnas_info=["En stock"],
                sin_insumos=not form.saldos,
            )
        return render(request, TEMPLATE_ENTREGAR, contexto, status=status)

    def _mostrar_persona(self, request, persona_form, form_de_entrega):
        """Resuelve a la persona **sin escribir** y dibuja la pantalla; si no se puede, la pantalla pide lo que falta.

        ``form_de_entrega`` es la función que arma el formulario de la entrega con los saldos de ahora.
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
            return EntregaPersonaForm(initial={**iniciales, "uuid_cliente": uuid4()}, saldos=self._saldos())

        return self._mostrar_persona(request, persona_form, sin_cargar)

    def post(self, request, **_url):
        persona_form = PersonaForm(request.POST)
        if not persona_form.is_valid():
            return self._pantalla(request, persona_form)
        form = EntregaPersonaForm(request.POST, saldos=self._saldos())
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
                form = EntregaPersonaForm(request.POST, saldos=self._saldos())
                form.full_clean()
                form.agregar_errores_del_servicio(error)
                form.marcar_faltantes(error.faltantes)
            except servicio.UuidEnUso as error:
                # Ese identificador ya fue de otra operación: se regenera para que el reintento sea una entrega nueva.
                datos = request.POST.copy()
                datos["uuid_cliente"] = str(uuid4())
                form = EntregaPersonaForm(datos, saldos=self._saldos())
                form.full_clean()
                form.agregar_errores_del_servicio(error)
            except PersonaSinDatos as error:
                persona_form.pedir_nombre = True
                persona_form.add_error(None, error)
                return self._pantalla(request, persona_form)
            except ValidationError as error:
                form.agregar_errores_del_servicio(error)
            else:
                return self._entregada(request, operacion)
        return self._mostrar_persona(request, persona_form, lambda: form)

    def _entregada(self, request, operacion):
        """Éxito, o reenvío del mismo ``uuid_cliente`` (``ya_existia``): en los dos casos vuelve a la solapa Stock."""

        if getattr(operacion, "ya_existia", False):
            messages.info(request, "Esa entrega ya estaba registrada: no se descontó dos veces.")
        else:
            messages.success(request, "Entrega registrada: el stock del edificio ya está descontado.")
        return redirect(self._url_stock())
