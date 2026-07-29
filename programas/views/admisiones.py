"""Vistas del circuito operativo de admisiones de Dispositivos."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from core import rbac
from legajos.models import Ciudadano
from legajos.services import CiudadanosService
from programas.forms import (
    BusquedaCiudadanoDNIForm,
    CiudadanoAdmisionForm,
    EgresoAdmisionForm,
    F00DinamicoForm,
    PromoverEsperaForm,
    RegistroDiarioForm,
    TrasladoAdmisionForm,
)
from programas.models import Admision, Cama, Dispositivo, EsperaAdmision, RegistroDiario
from programas.services.admisiones import (
    admitir_ciudadano,
    egresar_admision,
    poner_en_espera,
    promover_espera,
    trasladar_admision,
)
from programas.services.dispositivos import dispositivos_visibles, puede_operar_dispositivo
from programas.services.registro_diario import calcular_cantidades, registrar_parte_diario
from programas.views.dispositivos_legajo import DispositivoProgramaPermissionMixin


class DispositivoOperacionMixin(DispositivoProgramaPermissionMixin):
    def get_dispositivo(self):
        if not hasattr(self, "_dispositivo"):
            dispositivo = get_object_or_404(Dispositivo.objects.select_related("tipo"), pk=self.kwargs["pk"])
            if not puede_operar_dispositivo(self.request.user, dispositivo, self.capacidad_requerida):
                raise PermissionDenied
            self._dispositivo = dispositivo
        return self._dispositivo


class AdmisionCreateView(DispositivoOperacionMixin, View):
    capacidad_requerida = "dispositivo.admitir"
    template_name = "programas/admisiones/admitir.html"

    def _contexto(self, *, busqueda=None, ciudadano=None, ciudadano_form=None, f00_form=None, cama=None):
        dispositivo = self.get_dispositivo()
        return {
            "dispositivo": dispositivo,
            "busqueda_form": busqueda or BusquedaCiudadanoDNIForm(),
            "ciudadano": ciudadano,
            "ciudadano_form": ciudadano_form,
            "f00_form": f00_form,
            "camas": dispositivo.camas.filter(estado=Cama.Estado.DISPONIBLE),
            "cama_seleccionada": cama,
        }

    def get(self, request, pk):
        dni = request.GET.get("dni", "")
        busqueda = BusquedaCiudadanoDNIForm(request.GET if dni else None)
        if not dni or not busqueda.is_valid():
            return render(request, self.template_name, self._contexto(busqueda=busqueda))
        ciudadano = Ciudadano.objects.filter(dni=busqueda.cleaned_data["dni"]).first()
        ciudadano_form = None
        if ciudadano is None:
            inicial = {"dni": busqueda.cleaned_data["dni"]}
            if busqueda.cleaned_data["sexo"]:
                resultado = CiudadanosService.consultar_renaper(
                    busqueda.cleaned_data["dni"], busqueda.cleaned_data["sexo"]
                )
                if resultado.get("success"):
                    inicial.update(
                        {
                            clave: resultado.get("data", {}).get(clave)
                            for clave in ("nombre", "apellido", "fecha_nacimiento", "genero", "domicilio")
                            if resultado.get("data", {}).get(clave) is not None
                        }
                    )
            ciudadano_form = CiudadanoAdmisionForm(initial=inicial)
        f00_form = F00DinamicoForm(tipo_dispositivo=self.get_dispositivo().tipo, ciudadano=ciudadano)
        return render(
            request,
            self.template_name,
            self._contexto(busqueda=busqueda, ciudadano=ciudadano, ciudadano_form=ciudadano_form, f00_form=f00_form),
        )

    def post(self, request, pk):
        dispositivo = self.get_dispositivo()
        dni = request.POST.get("dni", "")
        busqueda = BusquedaCiudadanoDNIForm({"dni": dni})
        if not busqueda.is_valid():
            return render(request, self.template_name, self._contexto(busqueda=busqueda))
        ciudadano = Ciudadano.objects.filter(dni=busqueda.cleaned_data["dni"]).first()
        ciudadano_form = None if ciudadano else CiudadanoAdmisionForm(request.POST)
        f00_form = F00DinamicoForm(request.POST, request.FILES, tipo_dispositivo=dispositivo.tipo, ciudadano=ciudadano)
        cama_id = request.POST.get("cama")
        cama = (
            Cama.objects.filter(pk=cama_id, dispositivo=dispositivo, estado=Cama.Estado.DISPONIBLE).first()
            if cama_id
            else None
        )
        valido = f00_form.is_valid() and (ciudadano is not None or ciudadano_form.is_valid())
        if ciudadano is None and not rbac.puede(request.user, "ciudadano.crear"):
            ciudadano_form.add_error(None, "No tenés permiso para crear un nuevo ciudadano.")
            valido = False
        accion = request.POST.get("accion")
        if accion == "alojar" and cama is None:
            accion = "espera"
        if accion not in {"alojar", "espera"}:
            messages.error(request, "Seleccioná una acción de admisión válida.")
            valido = False
        if not valido:
            return render(
                request,
                self.template_name,
                self._contexto(
                    busqueda=busqueda, ciudadano=ciudadano, ciudadano_form=ciudadano_form, f00_form=f00_form, cama=cama
                ),
            )
        try:
            with transaction.atomic():
                if ciudadano is None:
                    ciudadano = Ciudadano.objects.create(**ciudadano_form.cleaned_data)
                respuestas, archivos = f00_form.respuestas_y_archivos()
                if accion == "espera":
                    admision = poner_en_espera(
                        ciudadano=ciudadano,
                        dispositivo=dispositivo,
                        usuario=request.user,
                        respuestas_f00=respuestas,
                        archivos_f00=archivos,
                    )
                    messages.success(request, f"{ciudadano.nombre_completo} quedó en lista de espera.")
                else:
                    admision = admitir_ciudadano(
                        ciudadano=ciudadano,
                        dispositivo=dispositivo,
                        cama=cama,
                        usuario=request.user,
                        respuestas_f00=respuestas,
                        archivos_f00=archivos,
                    )
                    messages.success(request, f"Admisión registrada para {ciudadano.nombre_completo}.")
        except (ValidationError, IntegrityError) as error:
            f00_form.add_error(None, getattr(error, "messages", ["No se pudo registrar la admisión."])[0])
            return render(
                request,
                self.template_name,
                self._contexto(
                    busqueda=busqueda, ciudadano=ciudadano, ciudadano_form=ciudadano_form, f00_form=f00_form, cama=cama
                ),
            )
        return redirect("dispositivos:detalle", pk=admision.dispositivo_id)


class ParteDiarioView(DispositivoOperacionMixin, View):
    capacidad_requerida = "dispositivo.admitir"
    template_name = "programas/dispositivos/legajo/parte_diario.html"

    def _contexto(self, form, parte=None):
        dispositivo = self.get_dispositivo()
        fecha = timezone.localdate()
        cantidades = parte.cantidades_legibles if parte else calcular_cantidades(dispositivo=dispositivo, fecha=fecha).items()
        return {
            "dispositivo": dispositivo,
            "form": form,
            "parte": parte,
            "fecha": fecha,
            "cantidades": cantidades,
        }

    def get(self, request, pk):
        turno = request.GET.get("turno")
        dispositivo = self.get_dispositivo()
        parte = RegistroDiario.objects.filter(
            dispositivo=dispositivo, fecha=timezone.localdate(), turno=turno
        ).first()
        form = RegistroDiarioForm(instance=parte, initial={"turno": turno} if turno else None)
        return render(request, self.template_name, self._contexto(form, parte))

    def post(self, request, pk):
        form = RegistroDiarioForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, self._contexto(form))
        try:
            parte = registrar_parte_diario(
                dispositivo=self.get_dispositivo(),
                fecha=timezone.localdate(),
                turno=form.cleaned_data["turno"],
                usuario=request.user,
                observaciones=form.observaciones_por_concepto(),
                observaciones_generales=form.cleaned_data["observaciones_generales"],
            )
        except ValueError as error:
            form.add_error(None, error)
            return render(request, self.template_name, self._contexto(form))
        messages.success(request, f"Parte {parte.get_turno_display().lower()} guardado con valores calculados.")
        return redirect(f"{reverse('dispositivos:parte_diario', args=[parte.dispositivo_id])}?turno={parte.turno}")


class EgresoAdmisionView(DispositivoOperacionMixin, View):
    capacidad_requerida = "dispositivo.egresar"
    template_name = "programas/admisiones/egreso.html"

    def get_admision(self):
        admision = get_object_or_404(
            Admision.objects.select_related("ciudadano", "dispositivo"), pk=self.kwargs["admision_pk"]
        )
        if admision.dispositivo_id != self.get_dispositivo().pk:
            raise PermissionDenied
        return admision

    def get(self, request, pk, admision_pk):
        admision = self.get_admision()
        return render(
            request,
            self.template_name,
            {
                "dispositivo": self.get_dispositivo(),
                "admision": admision,
                "form": EgresoAdmisionForm(initial={"fecha_egreso": timezone.localtime().strftime("%Y-%m-%dT%H:%M")}),
            },
        )

    def post(self, request, pk, admision_pk):
        admision = self.get_admision()
        form = EgresoAdmisionForm(request.POST)
        if form.is_valid():
            try:
                egresar_admision(admision=admision, usuario=request.user, **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "Egreso registrado; la cama quedó disponible.")
                return redirect("dispositivos:detalle", pk=self.get_dispositivo().pk)
        return render(
            request, self.template_name, {"dispositivo": self.get_dispositivo(), "admision": admision, "form": form}
        )


class EsperaAdmisionListView(DispositivoOperacionMixin, View):
    capacidad_requerida = "dispositivo.ver"
    template_name = "programas/admisiones/espera.html"

    def get(self, request, pk):
        dispositivo = self.get_dispositivo()
        esperas = EsperaAdmision.objects.filter(admision__dispositivo=dispositivo, promovida=False).select_related(
            "admision__ciudadano"
        )
        return render(request, self.template_name, {"dispositivo": dispositivo, "esperas": esperas})


class PromoverEsperaView(DispositivoOperacionMixin, View):
    capacidad_requerida = "dispositivo.admitir"
    template_name = "programas/admisiones/promover.html"

    def get_espera(self):
        espera = get_object_or_404(
            EsperaAdmision.objects.select_related("admision__ciudadano"), pk=self.kwargs["espera_pk"], promovida=False
        )
        if espera.admision.dispositivo_id != self.get_dispositivo().pk:
            raise PermissionDenied
        return espera

    def get(self, request, pk, espera_pk):
        espera = self.get_espera()
        return render(
            request,
            self.template_name,
            {
                "dispositivo": self.get_dispositivo(),
                "espera": espera,
                "form": PromoverEsperaForm(dispositivo=self.get_dispositivo()),
            },
        )

    def post(self, request, pk, espera_pk):
        espera = self.get_espera()
        form = PromoverEsperaForm(request.POST, dispositivo=self.get_dispositivo())
        if form.is_valid():
            try:
                promover_espera(espera=espera, cama=form.cleaned_data["cama"], usuario=request.user)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, "La persona fue promovida a una cama disponible.")
                return redirect("dispositivos:espera", pk=self.get_dispositivo().pk)
        return render(
            request, self.template_name, {"dispositivo": self.get_dispositivo(), "espera": espera, "form": form}
        )


class TrasladoAdmisionView(DispositivoOperacionMixin, View):
    capacidad_requerida = "dispositivo.egresar"
    template_name = "programas/admisiones/traslado.html"

    def get_admision(self):
        admision = get_object_or_404(
            Admision.objects.select_related("ciudadano", "dispositivo"), pk=self.kwargs["admision_pk"]
        )
        if admision.dispositivo_id != self.get_dispositivo().pk:
            raise PermissionDenied
        return admision

    def _form(self, *args, **kwargs):
        return TrasladoAdmisionForm(
            *args, dispositivos=dispositivos_visibles(self.request.user).exclude(pk=self.get_dispositivo().pk), **kwargs
        )

    def get(self, request, pk, admision_pk):
        admision = self.get_admision()
        destino_id = request.GET.get("destino")
        form = self._form(initial={"destino": destino_id} if destino_id else None)
        destino = form.fields["destino"].queryset.filter(pk=destino_id).first()
        f00_form = F00DinamicoForm(tipo_dispositivo=destino.tipo, ciudadano=admision.ciudadano) if destino else None
        return render(
            request,
            self.template_name,
            {
                "dispositivo": self.get_dispositivo(),
                "admision": admision,
                "form": form,
                "destino": destino,
                "f00_form": f00_form,
            },
        )

    def post(self, request, pk, admision_pk):
        admision = self.get_admision()
        form = self._form(request.POST)
        destino = form.fields["destino"].queryset.filter(pk=request.POST.get("destino")).first()
        f00_form = (
            F00DinamicoForm(request.POST, request.FILES, tipo_dispositivo=destino.tipo, ciudadano=admision.ciudadano)
            if destino
            else None
        )
        if form.is_valid() and f00_form is not None and f00_form.is_valid():
            if not puede_operar_dispositivo(request.user, form.cleaned_data["destino"], "dispositivo.admitir"):
                raise PermissionDenied
            try:
                respuestas, archivos = f00_form.respuestas_y_archivos()
                nueva = trasladar_admision(
                    admision=admision,
                    destino=form.cleaned_data["destino"],
                    cama=form.cleaned_data["cama"],
                    usuario=request.user,
                    respuestas_f00=respuestas,
                    archivos_f00=archivos,
                )
            except ValidationError as error:
                form.add_error(None, error)
            else:
                if nueva.estado == Admision.Estado.LISTA_ESPERA:
                    messages.warning(request, "Destino sin cama: la persona quedó en espera y el origen sigue alojado.")
                else:
                    messages.success(request, "Traslado confirmado; se liberó la cama de origen.")
                return redirect("dispositivos:detalle", pk=self.get_dispositivo().pk)
        return render(
            request,
            self.template_name,
            {
                "dispositivo": self.get_dispositivo(),
                "admision": admision,
                "form": form,
                "destino": destino,
                "f00_form": f00_form,
            },
        )
