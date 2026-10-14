"""Asistente de ingreso de una persona a un dispositivo (MVP v2, etapa 2 · #690 · P6).

Una URL por paso, con el estado en sesión (arquetipo Wizard):

1. **Persona** — búsqueda por DNI en el Legajo Ciudadano; si no está, se consulta el
   Registro de Personas (RENAPER). Acá se avisa si ya está alojada en la red.
2. **Plaza** — solo si el tipo del dispositivo maneja plazas. Tocar una plaza en el mapa
   la marca; recién «Continuar» la guarda.
3. **Confirmar** — resumen y escritura.

Solo el paso final escribe. Y como entre el paso 2 y el 3 otro operador puede tomar la
plaza, el paso final **no confía en lo que se eligió antes**: delega en
:func:`programas.services.ingreso.confirmar_ingreso`, que revalida y toma la plaza
bloqueando su fila, y si falla vuelve al paso de la plaza con el error.

**Lo que se escribe es lo que la pantalla mostró.** Las pestañas de un mismo navegador
comparten la sesión: si en otra pestaña se elige otra persona u otra plaza, la sesión
cambia y la primera pestaña sigue mostrando lo de antes. Por eso los formularios de los
pasos 2 y 3 devuelven, en campos ocultos, qué persona y qué plaza mostraban
(:meth:`IngresoBaseView.mostrado`), y la vista los compara con la sesión antes de
guardar o de escribir: si no coinciden, no se toca nada y se vuelve a mostrar el paso con
lo que hay ahora y un aviso. El progreso se guarda **por dispositivo**, así que abrir el
asistente de otro dispositivo no pisa el de este.
"""

import hashlib
import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from core.edad import edad_en_anios, fecha_o_none
from core.rbac import puede
from legajos.models import Ciudadano
from programas.forms_ingreso import IngresoConfirmarForm, IngresoPersonaForm
from programas.models import Dispositivo, Plaza
from programas.services.bitacora import turno_vigente
from programas.services.dispositivos import puede_operar_dispositivo
from programas.services.estadias import CAP_ADMITIR, AlojamientoEnLaRed, verificar_alojamiento_en_red
from programas.services.ingreso import (
    buscar_ciudadano_por_dni,
    confirmar_ingreso,
    consultar_registro_de_personas,
    maneja_plazas,
    plazas_para_ingresar,
)
from programas.services.ocupacion import LEYENDA_PLAZAS

#: Una sola clave de sesión con un estado por dispositivo: `{"<pk>": {...}}`.
CLAVE_SESION = "ingreso_asistente"
#: Quien busca a la persona en el legajo necesita verla: es lo que muestra el asistente.
CAP_VER_CIUDADANO = "ciudadano.ver"
CAP_CREAR_CIUDADANO = "ciudadano.crear"

AVISO_OTRA_PESTANA = (
    "Mientras esta pantalla estaba abierta, el ingreso cambió en otra pestaña. "
    "Revisá lo que se muestra ahora antes de seguir."
)


class IngresoBaseView(LoginRequiredMixin, View):
    """Gate común: capacidad `dispositivo.admitir` **con alcance** y dispositivo activo.

    La verificación de la red (`verificar_alojamiento_en_red`) no exige capacidad por sí
    misma: el gate vive acá y corre antes de cualquier paso, así nada de lo que devuelve
    llega a quien no puede admitir en este dispositivo.
    """

    paso = 0

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.dispositivo = get_object_or_404(Dispositivo.objects.select_related("tipo"), pk=kwargs["pk"])
        if not puede_operar_dispositivo(request.user, self.dispositivo, CAP_ADMITIR) or not puede(
            request.user, CAP_VER_CIUDADANO
        ):
            raise PermissionDenied
        if self.dispositivo.estado != Dispositivo.Estado.ACTIVO:
            messages.error(request, "Solo se puede alojar en un dispositivo activo.")
            return redirect("dispositivos:detalle", pk=self.dispositivo.pk)
        self.usa_plazas = maneja_plazas(self.dispositivo)
        return super().dispatch(request, *args, **kwargs)

    # ----- Sesión -----------------------------------------------------------------------

    def _todos(self):
        """Los asistentes en curso de esta sesión, uno por dispositivo."""

        todos = self.request.session.get(CLAVE_SESION)
        # Una sesión con la forma anterior (un solo asistente, con `dispositivo` adentro)
        # se descarta: era de un único dispositivo y se vuelve a empezar.
        if not isinstance(todos, dict) or "dispositivo" in todos:
            return {}
        return todos

    def estado(self):
        return dict(self._todos().get(str(self.dispositivo.pk)) or {})

    def guardar(self, estado):
        todos = self._todos()
        todos[str(self.dispositivo.pk)] = estado
        self.request.session[CLAVE_SESION] = todos

    def limpiar(self):
        todos = self._todos()
        todos.pop(str(self.dispositivo.pk), None)
        self.request.session[CLAVE_SESION] = todos

    # ----- Lo que la pantalla mostró ----------------------------------------------------

    @staticmethod
    def huella_persona(estado):
        """Quién es la persona del asistente, en un texto que viaja en un campo oculto.

        Con legajo, su id. Sin legajo, la persona es lo que respondió el Registro de
        Personas, que se consulta por DNI **y** sexo: el mismo DNI con otro sexo puede ser
        otra persona. Por eso la huella lleva el sexo consultado y un resumen de los datos
        que se van a dar de alta, no solo el DNI.
        """

        if estado.get("ciudadano_id"):
            return f"legajo:{estado['ciudadano_id']}"
        datos = estado.get("renaper")
        if datos:
            resumen = hashlib.sha256(json.dumps(datos, sort_keys=True, default=str).encode()).hexdigest()[:16]
            return f"registro:{datos.get('dni') or ''}:{estado.get('sexo') or ''}:{resumen}"
        return ""

    def mostrado(self, estado, plaza_id=None):
        """Los ocultos de un form: la persona y la plaza que la pantalla está mostrando."""

        return {"persona": self.huella_persona(estado), "plaza": "" if plaza_id is None else str(plaza_id)}

    def misma_persona(self, estado):
        """¿El POST viene de una pantalla que mostraba a la persona que hoy está en la sesión?"""

        huella = self.huella_persona(estado)
        return bool(huella) and self.request.POST.get("persona") == huella

    # ----- Contexto común ---------------------------------------------------------------

    def urls(self):
        pk = self.dispositivo.pk
        return {
            "persona": reverse("dispositivos:ingreso_persona", args=[pk]),
            "plaza": reverse("dispositivos:ingreso_plaza", args=[pk]),
            "confirmar": reverse("dispositivos:ingreso_confirmar", args=[pk]),
            "dispositivo": reverse("dispositivos:detalle", args=[pk]),
        }

    def eyebrow(self):
        """«CIS N.º 3 · turno Tarde · 08/09/2026 16:48», como el eyebrow de P6.

        El turno sale de `turno_vigente` —la única cuenta del turno del sistema— y de la
        lista de turnos del dispositivo, en una consulta. Si el momento cae en un hueco
        sin turno, o el dispositivo todavía no tiene turnos configurados, el eyebrow va
        sin turno: no se inventa uno.
        """

        ahora = timezone.now()
        situado = turno_vigente(self.dispositivo, ahora)
        turno = f" · turno {situado.turno.nombre}" if situado is not None else ""
        return f"{self.dispositivo.nombre}{turno} · {timezone.localtime(ahora):%d/%m/%Y %H:%M}"

    def contexto(self, paso_actual):
        urls = self.urls()
        pasos = [{"etiqueta": "Persona", "url": urls["persona"]}]
        if self.usa_plazas:
            pasos.append({"etiqueta": "Plaza", "url": urls["plaza"]})
        pasos.append({"etiqueta": "Confirmar", "url": urls["confirmar"]})
        return {
            "dispositivo": self.dispositivo,
            "eyebrow": self.eyebrow(),
            "urls": urls,
            "pasos": pasos,
            "paso_actual": paso_actual,
            "total_pasos": len(pasos),
            "bajada": pasos[paso_actual - 1]["etiqueta"],
        }

    def resumen_persona(self, estado):
        """Lo que se muestra de la persona, venga del legajo o del Registro de Personas.

        `None` si no hay persona, o si el legajo que se eligió ya no existe.
        """

        if estado.get("ciudadano_id"):
            ciudadano = Ciudadano.objects.filter(pk=estado["ciudadano_id"]).first()
            if ciudadano is None:
                return None
            return {
                "nombre": ciudadano.nombre_completo,
                "dni": ciudadano.dni,
                "nacimiento": _nacimiento(ciudadano.fecha_nacimiento),
                "genero": ciudadano.get_genero_display(),
                "obra_social": ciudadano.obra_social,
                "domicilio": ciudadano.domicilio,
                "origen": "Legajo Ciudadano",
                "en_legajo": True,
                "legajo_url": reverse("legajos:ciudadano_detalle", args=[ciudadano.pk]),
                "ciudadano": ciudadano,
                "nota": "Estos datos vienen del Legajo Ciudadano y no se vuelven a preguntar. Si están mal, se corrigen allí.",
            }
        datos = estado.get("renaper")
        if datos:
            return {
                "nombre": f"{datos.get('nombre') or ''} {datos.get('apellido') or ''}".strip(),
                "dni": datos["dni"],
                "nacimiento": _nacimiento(datos.get("fecha_nacimiento")),
                "genero": dict(IngresoPersonaForm.GENERO_CHOICES).get(datos.get("genero") or "", ""),
                "obra_social": "",
                "domicilio": datos.get("domicilio") or "",
                "origen": "Registro de Personas",
                "en_legajo": False,
                "legajo_url": "",
                "nota": "Estos datos vienen del Registro de Personas. Al confirmar, la persona se da de alta en el Legajo Ciudadano.",
            }
        return None

    def volver_al_inicio(self, mensaje):
        """El legajo elegido ya no existe: se descarta el progreso y se vuelve a buscar."""

        self.limpiar()
        messages.error(self.request, mensaje)
        return redirect(self.urls()["persona"])


def _nacimiento(valor):
    """«01/01/2000 · 26 años», o vacío si no hay fecha (o no se entiende)."""

    fecha = fecha_o_none(valor)
    if fecha is None:
        return ""
    edad = edad_en_anios(fecha)
    return f"{fecha:%d/%m/%Y}" + (f" · {edad} años" if edad is not None else "")


class IngresoPersonaView(IngresoBaseView):
    """Paso 1: búsqueda por documento, alta desde el Registro de Personas y aviso de la red."""

    template_name = "programas/dispositivos/ingreso/paso_persona.html"
    paso = 1

    def render_paso(self, request, form, verificacion=None):
        contexto = self.contexto(1)
        contexto.update({"form": form, "verificacion": verificacion})
        return render(request, self.template_name, contexto)

    def get(self, request, pk):
        estado = self.estado()
        persona = self.resumen_persona(estado)
        form = IngresoPersonaForm(initial={"dni": persona["dni"]} if persona else None)
        return self.render_paso(request, form)

    def post(self, request, pk):
        form = IngresoPersonaForm(request.POST)
        if not form.is_valid():
            return self.render_paso(request, form)
        dni = form.cleaned_data["dni"]
        sexo = form.cleaned_data["sexo"]

        ciudadano = buscar_ciudadano_por_dni(dni)
        if ciudadano is not None:
            verificacion = verificar_alojamiento_en_red(ciudadano, request.user)
            if verificacion.alojada:
                # El aviso llega antes de confirmar: la persona no avanza hasta que se
                # resuelva el egreso o el traslado. Fuera de alcance, solo se sabe que existe.
                return self.render_paso(request, form, verificacion)
            nuevo = {"ciudadano_id": ciudadano.pk}
        else:
            if not puede(request.user, CAP_CREAR_CIUDADANO):
                form.add_error(
                    "dni", "La persona no está en el Legajo Ciudadano y no tenés permiso para darla de alta."
                )
                return self.render_paso(request, form)
            if not sexo:
                form.add_error("sexo", "Indicá el sexo para consultar el Registro de Personas.")
                return self.render_paso(request, form)
            datos, error = consultar_registro_de_personas(dni, sexo)
            if error:
                form.add_error("dni", error)
                return self.render_paso(request, form)
            nuevo = {"ciudadano_id": None, "renaper": datos, "sexo": sexo}

        # El paso se guarda recién ahora, con el form válido; lo que dependía de la persona
        # anterior (la plaza) se descarta.
        self.guardar(nuevo)
        return redirect(self.urls()["plaza"] if self.usa_plazas else self.urls()["confirmar"])


class IngresoPlazaView(IngresoBaseView):
    """Paso 2: el mapa de plazas. Elegir una plaza **no la reserva**: se toma al confirmar.

    Tocar una plaza del mapa (`?elegir=`) solo la marca en la pantalla y **no escribe la
    sesión**; la guarda «Continuar», que es un POST con la plaza y la persona que la
    pantalla mostraba.
    """

    template_name = "programas/dispositivos/ingreso/paso_plaza.html"
    paso = 2

    def _previo(self, estado):
        """Redirige al paso anterior si falta la persona, o al final si no hay plazas."""

        if not (estado.get("ciudadano_id") or estado.get("renaper")):
            return redirect(self.urls()["persona"])
        if not self.usa_plazas:
            return redirect(self.urls()["confirmar"])
        return None

    def mapa(self):
        """`(sectores, elegibles)` del dispositivo, calculado una sola vez por petición."""

        if not hasattr(self, "_mapa"):
            self._mapa = plazas_para_ingresar(
                self.dispositivo, puede_ver_personas=puede(self.request.user, CAP_VER_CIUDADANO)
            )
        return self._mapa

    def render_paso(self, request, estado, persona, elegida=None, error="", aviso=""):
        sectores, elegibles = self.mapa()
        url_plaza = self.urls()["plaza"]
        for item in sectores:
            for plaza in item["plazas"]:
                plaza["seleccionada"] = plaza["pk"] == elegida
                if plaza["pk"] in elegibles:
                    plaza["url"] = f"{url_plaza}?elegir={plaza['pk']}"
        contexto = self.contexto(2)
        contexto.update(
            {
                "sectores": sectores,
                "leyenda": LEYENDA_PLAZAS,
                "hay_disponibles": bool(elegibles),
                "plaza_obligatoria": self.dispositivo.tipo.plaza_obligatoria_al_ingresar,
                "persona": persona,
                "mostrado": self.mostrado(estado, elegida),
                "error": error,
                "aviso": aviso,
            }
        )
        return render(request, self.template_name, contexto)

    def get(self, request, pk):
        estado = self.estado()
        previo = self._previo(estado)
        if previo:
            return previo
        persona = self.resumen_persona(estado)
        if persona is None:
            return self.volver_al_inicio("La persona elegida ya no está en el Legajo Ciudadano. Buscala de nuevo.")
        error = estado.pop("error_plaza", "")
        if error:
            self.guardar(estado)

        _sectores, elegibles = self.mapa()
        pedida = request.GET.get("elegir")
        if pedida:
            if pedida.isdigit() and int(pedida) in elegibles:
                return self.render_paso(request, estado, persona, int(pedida), error)
            return self.render_paso(request, estado, persona, None, "Esa plaza ya no está disponible. Elegí otra.")
        # Al volver desde «Confirmar», la plaza guardada sigue marcada si todavía se puede elegir.
        guardada = estado.get("plaza_id")
        return self.render_paso(request, estado, persona, guardada if guardada in elegibles else None, error)

    def post(self, request, pk):
        """«Continuar» con la plaza marcada, o «Continuar sin plaza» si el tipo no la exige."""

        estado = self.estado()
        previo = self._previo(estado)
        if previo:
            return previo
        persona = self.resumen_persona(estado)
        if persona is None:
            return self.volver_al_inicio("La persona elegida ya no está en el Legajo Ciudadano. Buscala de nuevo.")
        if not self.misma_persona(estado):
            return self.render_paso(request, estado, persona, aviso=AVISO_OTRA_PESTANA)

        if request.POST.get("sin_plaza"):
            if self.dispositivo.tipo.plaza_obligatoria_al_ingresar:
                return self.render_paso(
                    request, estado, persona, error="Este tipo de dispositivo exige asignar una plaza al ingresar."
                )
            estado.update({"plaza_id": None, "plaza_decidida": True})
            self.guardar(estado)
            return redirect(self.urls()["confirmar"])

        pedida = request.POST.get("plaza") or ""
        if not pedida:
            return self.render_paso(request, estado, persona, error="Elegí una plaza disponible en el mapa.")
        _sectores, elegibles = self.mapa()
        if not (pedida.isdigit() and int(pedida) in elegibles):
            return self.render_paso(request, estado, persona, error="Esa plaza ya no está disponible. Elegí otra.")
        estado.update({"plaza_id": int(pedida), "plaza_decidida": True})
        self.guardar(estado)
        return redirect(self.urls()["confirmar"])


class IngresoConfirmarView(IngresoBaseView):
    """Paso final: resumen, aviso de la red y escritura con la plaza revalidada y bloqueada."""

    template_name = "programas/dispositivos/ingreso/paso_confirmar.html"

    def _previo(self, estado):
        if not (estado.get("ciudadano_id") or estado.get("renaper")):
            return redirect(self.urls()["persona"])
        if self.usa_plazas and not estado.get("plaza_decidida"):
            return redirect(self.urls()["plaza"])
        return None

    def render_paso(self, request, estado, persona, form, aviso=""):
        ciudadano = persona.get("ciudadano")
        verificacion = verificar_alojamiento_en_red(ciudadano, request.user) if ciudadano else None
        plaza = None
        if estado.get("plaza_id"):
            plaza = Plaza.objects.select_related("sector").filter(pk=estado["plaza_id"]).first()
        contexto = self.contexto(3 if self.usa_plazas else 2)
        contexto.update(
            {
                "form": form,
                "resumen": {"persona": persona, "plaza": plaza},
                "mostrado": self.mostrado(estado, estado.get("plaza_id")),
                "verificacion": verificacion,
                "aviso": aviso,
                "url_anterior": self.urls()["plaza" if self.usa_plazas else "persona"],
            }
        )
        return render(request, self.template_name, contexto)

    def get(self, request, pk):
        estado = self.estado()
        previo = self._previo(estado)
        if previo:
            return previo
        persona = self.resumen_persona(estado)
        if persona is None:
            return self.volver_al_inicio("La persona elegida ya no está en el Legajo Ciudadano. Buscala de nuevo.")
        return self.render_paso(request, estado, persona, IngresoConfirmarForm())

    def _es_lo_mostrado(self, estado):
        """¿Persona y plaza del POST son las de la sesión? Si falta alguna, no."""

        plaza = self.request.POST.get("plaza")
        if plaza is None:
            return False
        esperada = "" if estado.get("plaza_id") is None else str(estado["plaza_id"])
        return self.misma_persona(estado) and plaza == esperada

    def post(self, request, pk):
        estado = self.estado()
        previo = self._previo(estado)
        if previo:
            return previo
        persona = self.resumen_persona(estado)
        if persona is None:
            return self.volver_al_inicio("La persona elegida ya no está en el Legajo Ciudadano. Buscala de nuevo.")
        form = IngresoConfirmarForm(request.POST)
        if not self._es_lo_mostrado(estado):
            # Otra pestaña cambió la persona o la plaza: no se escribe nada y se vuelve a
            # mostrar el resumen con lo que hay ahora, que es lo único que se puede confirmar.
            return self.render_paso(request, estado, persona, IngresoConfirmarForm(), AVISO_OTRA_PESTANA)
        if not form.is_valid():
            return self.render_paso(request, estado, persona, form)

        try:
            estadia = confirmar_ingreso(
                dispositivo=self.dispositivo,
                usuario=request.user,
                ciudadano_id=estado.get("ciudadano_id"),
                datos_renaper=estado.get("renaper"),
                plaza_id=estado.get("plaza_id"),
                fecha_ingreso=form.cleaned_data["fecha_ingreso"],
            )
        except AlojamientoEnLaRed as error:
            form.add_error(None, error.verificacion.mensaje)
            return self.render_paso(request, estado, persona, form)
        except Ciudadano.DoesNotExist:
            return self.volver_al_inicio("La persona elegida ya no está en el Legajo Ciudadano. Buscala de nuevo.")
        except Plaza.DoesNotExist:
            return self._volver_a_la_plaza(estado, "La plaza elegida ya no existe. Elegí otra.")
        except ValidationError as error:
            errores = getattr(error, "message_dict", None) or {"__all__": error.messages}
            if "plaza" in errores or "reserva" in errores:
                # Otro operador la tomó (o la sacaron de servicio, o la reserva dejó de
                # valer) desde que se eligió: se vuelve al paso que la eligió, con el
                # motivo, y no se reintenta solo.
                return self._volver_a_la_plaza(estado, " ".join(errores.get("plaza", []) + errores.get("reserva", [])))
            for campo, mensajes in errores.items():
                for mensaje in mensajes:
                    form.add_error(campo if campo in form.fields else None, mensaje)
            return self.render_paso(request, estado, persona, form)

        self.limpiar()
        messages.success(request, f"{estadia.ciudadano.nombre_completo} ingresó a {self.dispositivo.nombre}.")
        return redirect(self.urls()["dispositivo"])

    def _volver_a_la_plaza(self, estado, mensaje):
        estado.pop("plaza_id", None)
        estado.pop("plaza_decidida", None)
        estado["error_plaza"] = mensaje
        self.guardar(estado)
        return redirect(self.urls()["plaza"])
