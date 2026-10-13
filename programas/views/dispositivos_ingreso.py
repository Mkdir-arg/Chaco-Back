"""Asistente de ingreso de una persona a un dispositivo (MVP v2, etapa 2 · #690 · P6).

Una URL por paso, con el estado en sesión (arquetipo Wizard):

1. **Persona** — búsqueda por DNI en el Legajo Ciudadano; si no está, se consulta el
   Registro de Personas (RENAPER). Acá se avisa si ya está alojada en la red.
2. **Plaza** — solo si el tipo del dispositivo maneja plazas.
3. **Confirmar** — resumen y escritura.

Solo el paso final escribe. Y como entre el paso 2 y el 3 otro operador puede tomar la
plaza, el paso final **no confía en lo que se eligió antes**: delega en
:func:`programas.services.ingreso.confirmar_ingreso`, que revalida y toma la plaza
bloqueando su fila, y si falla vuelve al paso de la plaza con el error.
"""

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from core.rbac import puede
from legajos.models import Ciudadano
from programas.forms_ingreso import IngresoConfirmarForm, IngresoPersonaForm
from programas.models import Dispositivo, Plaza
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

CLAVE_SESION = "ingreso_asistente"
#: Quien busca a la persona en el legajo necesita verla: es lo que muestra el asistente.
CAP_VER_CIUDADANO = "ciudadano.ver"
CAP_CREAR_CIUDADANO = "ciudadano.crear"


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

    def estado(self):
        guardado = self.request.session.get(CLAVE_SESION)
        if not guardado or guardado.get("dispositivo") != self.dispositivo.pk:
            guardado = {"dispositivo": self.dispositivo.pk}
        return guardado

    def guardar(self, estado):
        self.request.session[CLAVE_SESION] = estado

    def limpiar(self):
        self.request.session.pop(CLAVE_SESION, None)

    # ----- Contexto común ---------------------------------------------------------------

    def urls(self):
        pk = self.dispositivo.pk
        return {
            "persona": reverse("dispositivos:ingreso_persona", args=[pk]),
            "plaza": reverse("dispositivos:ingreso_plaza", args=[pk]),
            "confirmar": reverse("dispositivos:ingreso_confirmar", args=[pk]),
            "dispositivo": reverse("dispositivos:detalle", args=[pk]),
        }

    def contexto(self, paso_actual, bajada):
        urls = self.urls()
        pasos = [{"etiqueta": "Persona", "url": urls["persona"]}]
        if self.usa_plazas:
            pasos.append({"etiqueta": "Plaza", "url": urls["plaza"]})
        pasos.append({"etiqueta": "Confirmar", "url": urls["confirmar"]})
        return {
            "dispositivo": self.dispositivo,
            "urls": urls,
            "pasos": pasos,
            "paso_actual": paso_actual,
            "total_pasos": len(pasos),
            "bajada": bajada,
        }

    def resumen_persona(self, estado):
        """Lo que se muestra de la persona, venga del legajo o del Registro de Personas."""

        if estado.get("ciudadano_id"):
            ciudadano = Ciudadano.objects.filter(pk=estado["ciudadano_id"]).first()
            if ciudadano is not None:
                return {
                    "nombre": ciudadano.nombre_completo,
                    "dni": ciudadano.dni,
                    "fecha_nacimiento": ciudadano.fecha_nacimiento,
                    "genero": ciudadano.get_genero_display(),
                    "domicilio": ciudadano.domicilio,
                    "origen": "Legajo Ciudadano",
                    "legajo_url": reverse("legajos:ciudadano_detalle", args=[ciudadano.pk]),
                }
        datos = estado.get("renaper")
        if datos:
            return {
                "nombre": f"{datos.get('apellido') or ''}, {datos.get('nombre') or ''}".strip(", "),
                "dni": datos["dni"],
                "fecha_nacimiento": datos.get("fecha_nacimiento"),
                "genero": dict(IngresoPersonaForm.GENERO_CHOICES).get(datos.get("genero") or "", ""),
                "domicilio": datos.get("domicilio") or "",
                "origen": "Registro de Personas",
                "legajo_url": "",
            }
        return None


class IngresoPersonaView(IngresoBaseView):
    """Paso 1: búsqueda por documento, alta desde el Registro de Personas y aviso de la red."""

    template_name = "programas/dispositivos/ingreso/paso_persona.html"
    paso = 1

    def render_paso(self, request, form, verificacion=None):
        contexto = self.contexto(1, "quién ingresa. Se busca por documento en el Legajo Ciudadano.")
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
            nuevo = {"dispositivo": self.dispositivo.pk, "ciudadano_id": ciudadano.pk}
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
            nuevo = {"dispositivo": self.dispositivo.pk, "ciudadano_id": None, "renaper": datos}

        # El paso se guarda recién ahora, con el form válido; lo que dependía de la persona
        # anterior (la plaza) se descarta.
        self.guardar(nuevo)
        return redirect(self.urls()["plaza"] if self.usa_plazas else self.urls()["confirmar"])


class IngresoPlazaView(IngresoBaseView):
    """Paso 2: el mapa de plazas. Elegir una plaza **no la reserva**: se toma al confirmar."""

    template_name = "programas/dispositivos/ingreso/paso_plaza.html"
    paso = 2

    def _previo(self):
        """Redirige al paso anterior si falta la persona, o al final si no hay plazas."""

        estado = self.estado()
        if not (estado.get("ciudadano_id") or estado.get("renaper")):
            return redirect(self.urls()["persona"])
        if not self.usa_plazas:
            return redirect(self.urls()["confirmar"])
        return None

    def render_paso(self, request, estado, error=""):
        sectores, elegibles = plazas_para_ingresar(self.dispositivo)
        elegida = estado.get("plaza_id")
        url_plaza = self.urls()["plaza"]
        for item in sectores:
            for plaza in item["plazas"]:
                plaza["seleccionada"] = plaza["pk"] == elegida
                if plaza["pk"] in elegibles:
                    plaza["url"] = f"{url_plaza}?elegir={plaza['pk']}"
        contexto = self.contexto(2, "dónde se aloja. Elegí una plaza disponible.")
        contexto.update(
            {
                "sectores": sectores,
                "leyenda": LEYENDA_PLAZAS,
                "hay_disponibles": bool(elegibles),
                "plaza_obligatoria": self.dispositivo.tipo.plaza_obligatoria_al_ingresar,
                "persona": self.resumen_persona(estado),
                "error": error,
            }
        )
        return render(request, self.template_name, contexto)

    def get(self, request, pk):
        previo = self._previo()
        if previo:
            return previo
        estado = self.estado()
        error = estado.pop("error_plaza", "")
        if error:
            self.guardar(estado)

        elegida = request.GET.get("elegir")
        if elegida:
            _sectores, elegibles = plazas_para_ingresar(self.dispositivo)
            if elegida.isdigit() and int(elegida) in elegibles:
                estado.update({"plaza_id": int(elegida), "plaza_decidida": True})
                self.guardar(estado)
                return redirect(self.urls()["confirmar"])
            estado.pop("plaza_id", None)
            self.guardar(estado)
            error = "Esa plaza ya no está disponible. Elegí otra."
        return self.render_paso(request, estado, error)

    def post(self, request, pk):
        """«Continuar sin plaza»: solo cuando el tipo no la exige."""

        previo = self._previo()
        if previo:
            return previo
        estado = self.estado()
        if self.dispositivo.tipo.plaza_obligatoria_al_ingresar:
            return self.render_paso(request, estado, "Este tipo de dispositivo exige asignar una plaza al ingresar.")
        estado.update({"plaza_id": None, "plaza_decidida": True})
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

    def render_paso(self, request, estado, form):
        persona = self.resumen_persona(estado)
        ciudadano_id = estado.get("ciudadano_id")
        verificacion = None
        if ciudadano_id:
            ciudadano = Ciudadano.objects.filter(pk=ciudadano_id).first()
            if ciudadano is not None:
                verificacion = verificar_alojamiento_en_red(ciudadano, request.user)
        plaza = None
        if estado.get("plaza_id"):
            plaza = Plaza.objects.select_related("sector").filter(pk=estado["plaza_id"]).first()
        contexto = self.contexto(3 if self.usa_plazas else 2, "revisá lo cargado y confirmá el ingreso.")
        contexto.update(
            {
                "form": form,
                "resumen": {"persona": persona, "plaza": plaza},
                "verificacion": verificacion,
                "url_anterior": self.urls()["plaza" if self.usa_plazas else "persona"],
            }
        )
        return render(request, self.template_name, contexto)

    def get(self, request, pk):
        estado = self.estado()
        previo = self._previo(estado)
        return previo or self.render_paso(request, estado, IngresoConfirmarForm())

    def post(self, request, pk):
        estado = self.estado()
        previo = self._previo(estado)
        if previo:
            return previo
        form = IngresoConfirmarForm(request.POST)
        if not form.is_valid():
            return self.render_paso(request, estado, form)

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
            return self.render_paso(request, estado, form)
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
            return self.render_paso(request, estado, form)

        self.limpiar()
        messages.success(request, f"{estadia.ciudadano.nombre_completo} ingresó a {self.dispositivo.nombre}.")
        return redirect(self.urls()["dispositivo"])

    def _volver_a_la_plaza(self, estado, mensaje):
        estado.pop("plaza_id", None)
        estado.pop("plaza_decidida", None)
        estado["error_plaza"] = mensaje
        self.guardar(estado)
        return redirect(self.urls()["plaza"])
