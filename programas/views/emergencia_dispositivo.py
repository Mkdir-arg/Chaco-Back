"""E6 · «Emergencia · Llegadas»: la guardia del dispositivo recibe a la familia desde el backoffice.

Es el mismo guion que la app (03 §3 y §8): buscar por DNI → aceptar o rechazar la derivación
→ confirmar a cada persona con su ficha y su cama → «Familia alojada» o cerrar con
diferencia; y, sin derivación, ingresar igual o avisar a la mesa.

Las vistas **no tienen reglas de la etapa**. Cada acción llama a la función de
``programas/services/emergencia_alojar.py`` —la misma que usa la API (RU-1, RU-2)— y traduce
lo que contesta:

* :class:`EstadoCambio` → la pantalla quedó vieja (otra guardia, la mesa o el cron se
  adelantaron). Es el 409 de la API; acá se vuelve a la pantalla que corresponde al estado
  nuevo con el mensaje del servicio (RU-20).
* ``ValidationError`` → el mensaje del servicio, en su campo si la pantalla es un formulario.
* ``PermissionDenied`` → no se atrapa (403). No debería llegar: el alcance ya se exigió acá.

Quién entra (plan C2, Cambio 432)
---------------------------------

* Sin ``dispositivo.admitir`` en **ningún** lado del programa Dispositivos → **403**.
* Con la capacidad pero sin alcance sobre **este** dispositivo, o con un id que no existe →
  **404**, el mismo. Y lo mismo para una derivación o un caso de **otro** dispositivo
  pedidos por id dentro de uno propio: se buscan **siempre** filtrados por
  ``self.dispositivo``, así que no existen (RU-9).

El estado del recorrido es el del caso, no la sesión: no hay nada que una segunda pestaña
pueda pisar, y cada paso se abre por su URL.
"""

from collections import Counter
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from core.rbac import puede
from programas.forms_emergencia_dispositivo import (
    BuscarFamiliaForm,
    CancelarIngresoForm,
    DiferenciaForm,
    FamiliaAlojadaForm,
    FichaIntegranteForm,
    Formulario1DispositivoForm,
    RechazarDerivacionForm,
)
from programas.mixins_dispositivos import dispositivo_operable_o_404
from programas.models import CasoEmergencia, Derivacion, Dispositivo, IntegranteGrupo
from programas.selectors import emergencia_alojar as selectores
from programas.selectors import emergencia_llegadas as pantalla
from programas.selectors.emergencia_mesa import nombre_de
from programas.services import emergencia_alojar as servicio
from programas.services.dispositivos import puede_en_programa_dispositivos
from programas.services.emergencia import EstadoCambio

CAP_ADMITIR = "dispositivo.admitir"
CAP_VER_CIUDADANO = "ciudadano.ver"

Estado = CasoEmergencia.Estado

TEMPLATES = "programas/emergencia/dispositivo/"


def _errores_de(form):
    return " ".join(dict.fromkeys(error for errores in form.errors.values() for error in errores))


def _mensajes(error):
    return " ".join(error.messages)


class GuardiaView(LoginRequiredMixin, View):
    """Gate común de E6: ``dispositivo.admitir`` **con alcance** sobre el dispositivo de la URL."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        # Sin la capacidad es 403, con cualquier id; con ella, sin alcance sobre este dispositivo es 404.
        if not puede_en_programa_dispositivos(request.user, CAP_ADMITIR):
            raise PermissionDenied
        self.dispositivo = dispositivo_operable_o_404(
            request, kwargs["pk"], CAP_ADMITIR, Dispositivo.objects.select_related("tipo")
        )
        previo = self.preparar(request, **kwargs)
        if previo is not None:
            return previo
        return super().dispatch(request, *args, **kwargs)

    def preparar(self, request, **kwargs):
        """Lo que la vista necesita además del dispositivo. Devuelve una respuesta para cortar."""

        return None

    def url(self, nombre, *args, **parametros):
        url = reverse(f"dispositivos:emergencia_{nombre}", args=[self.dispositivo.pk, *args])
        consulta = urlencode({clave: valor for clave, valor in parametros.items() if valor not in (None, "")})
        return f"{url}?{consulta}" if consulta else url

    def contexto(self, paso, caso=None, **extra):
        url_integrantes = self.url("integrantes", caso.pk) if caso is not None else None
        return {
            "dispositivo": self.dispositivo,
            "caso": caso,
            "url_dispositivo": reverse("dispositivos:detalle", args=[self.dispositivo.pk]),
            "url_llegadas": self.url("llegadas"),
            "url_integrantes": url_integrantes,
            **pantalla.pasos(paso, self.url("llegadas"), url_integrantes),
            **extra,
        }


# ---------------------------------------------------------------------------
# Paso 1 · Buscar a la familia, y la derivación (M2-1, M2-2, M2-6)
# ---------------------------------------------------------------------------


class LlegadasView(GuardiaView):
    """El buscador por DNI, su resultado y lo que el dispositivo tiene por recibir."""

    def _tarjeta(self, derivacion, ahora):
        tarjeta = pantalla.tarjeta_de_derivacion(derivacion, ahora)
        if tarjeta["pendiente"]:
            tarjeta["url_aceptar"] = self.url("aceptar", derivacion.pk)
            tarjeta["url_rechazar"] = self.url("rechazar", derivacion.pk)
        else:
            tarjeta["url_integrantes"] = self.url("integrantes", derivacion.caso_id)
        return tarjeta

    def _derivacion_pedida(self, pk):
        """La derivación vigente de **este** dispositivo que la lista pidió ver, o ``None``."""

        if not str(pk).isdecimal():
            return None
        return (
            Derivacion.objects.filter(
                pk=pk,
                dispositivo=self.dispositivo,
                estado__in=Derivacion.ESTADOS_VIGENTES,
                caso__estado__in=(Estado.DERIVADO, Estado.INGRESO_EN_CURSO),
            )
            .select_related("caso__grupo__responsable", "derivada_por")
            .first()
        )

    def get(self, request, pk):
        ahora = timezone.now()
        buscado = "dni" in request.GET
        form = BuscarFamiliaForm(request.GET if buscado else None)
        resultado = tarjeta = None
        if buscado and form.is_valid():
            try:
                resultado = servicio.buscar_por_dni(
                    dispositivo=self.dispositivo, dni=form.cleaned_data["dni"], usuario=request.user
                )
            except ValidationError as error:
                form.add_error("dni", error.message_dict.get("dni", error.messages))
        elif request.GET.get("derivacion"):
            derivacion = self._derivacion_pedida(request.GET["derivacion"])
            if derivacion is None:
                messages.warning(request, "Esa derivación ya no está para recibir. Buscá a la familia de nuevo.")
                return redirect(self.url("llegadas"))
            tarjeta = self._tarjeta(derivacion, ahora)
        if resultado is not None and resultado.resultado == servicio.BUSQUEDA_DERIVACION:
            tarjeta = self._tarjeta(resultado.derivacion, ahora)

        llegadas = selectores.llegadas_del_dispositivo(self.dispositivo, request.user)
        sin_derivacion = resultado is not None and resultado.resultado == servicio.BUSQUEDA_SIN_DERIVACION
        contexto = self.contexto(
            1,
            form=form,
            resultado=resultado,
            tarjeta=tarjeta,
            form_rechazo=RechazarDerivacionForm(auto_id="rechazo_%s") if tarjeta and tarjeta["pendiente"] else None,
            sin_derivacion=sin_derivacion,
            alojada=resultado is not None and resultado.resultado == servicio.BUSQUEDA_ALOJADA,
            puede_ingresar_igual=sin_derivacion and resultado.plazas_libres > 0,
            url_ingreso_directo=self.url("ingreso_directo", dni=resultado.dni) if sin_derivacion else "",
            url_avisar=self.url("avisar", dni=resultado.dni) if sin_derivacion else "",
            pendientes=pantalla.filas_de_llegadas(
                llegadas["pendientes"], ahora, lambda derivacion: self.url("llegadas", derivacion=derivacion.pk)
            ),
            en_curso=pantalla.filas_de_llegadas(
                llegadas["en_curso"], ahora, lambda derivacion: self.url("integrantes", derivacion.caso_id)
            ),
        )
        return render(request, f"{TEMPLATES}llegadas.html", contexto)


class _AccionDeDerivacionView(GuardiaView):
    """Un POST sobre una derivación **de este dispositivo**: la de otro, por id, es un 404."""

    http_method_names = ["post"]

    def preparar(self, request, **kwargs):
        # La guarda de C2/RU-9: se busca filtrada por el dispositivo de la URL.
        self.derivacion = get_object_or_404(Derivacion, pk=kwargs["derivacion_pk"], dispositivo=self.dispositivo)

    def despues_de_un_cambio(self, cambio):
        if cambio.estado_actual == Estado.INGRESO_EN_CURSO:
            return redirect(self.url("integrantes", self.derivacion.caso_id))
        return redirect(self.url("llegadas"))


class AceptarDerivacionView(_AccionDeDerivacionView):
    def post(self, request, pk, derivacion_pk):
        try:
            resultado = servicio.aceptar_derivacion(derivacion=self.derivacion, usuario=request.user)
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return self.despues_de_un_cambio(cambio)
        except ValidationError as error:
            messages.error(request, _mensajes(error))
            return redirect(self.url("llegadas", derivacion=self.derivacion.pk))
        if resultado.faltantes:
            messages.warning(request, f"Derivación aceptada. {resultado.mensaje}: podés seguir con las que hay.")
        else:
            messages.success(request, f"Derivación aceptada. {resultado.mensaje}.")
        return redirect(self.url("integrantes", resultado.caso.pk))


class RechazarDerivacionView(_AccionDeDerivacionView):
    def post(self, request, pk, derivacion_pk):
        form = RechazarDerivacionForm(request.POST)
        if not form.is_valid():
            messages.error(request, _errores_de(form))
            return redirect(self.url("llegadas", derivacion=self.derivacion.pk))
        try:
            servicio.rechazar_derivacion(derivacion=self.derivacion, usuario=request.user, **form.cleaned_data)
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return self.despues_de_un_cambio(cambio)
        except ValidationError as error:
            messages.error(request, _mensajes(error))
            return redirect(self.url("llegadas", derivacion=self.derivacion.pk))
        messages.success(request, "Derivación rechazada. El caso volvió a la mesa con el motivo.")
        return redirect(self.url("llegadas"))


# ---------------------------------------------------------------------------
# Paso 2 · Integrantes, ficha y cama (M2-3, M2-4)
# ---------------------------------------------------------------------------


class _IngresoView(GuardiaView):
    """Una pantalla o una acción sobre el ingreso de un caso **en este dispositivo**.

    El caso se busca por su última derivación hacia ``self.dispositivo``: el de otro
    dispositivo no existe (404). Si el ingreso ya no está como la pantalla lo necesita
    —se canceló, la familia ya está alojada— vuelve a «Llegadas» con el aviso.
    """

    estados = (Estado.INGRESO_EN_CURSO,)

    def preparar(self, request, **kwargs):
        derivacion = (
            Derivacion.objects.filter(caso_id=kwargs["caso_pk"], dispositivo=self.dispositivo)
            .select_related("caso__grupo__responsable")
            .order_by("-id")
            .first()
        )
        if derivacion is None:
            raise Http404
        self.derivacion, self.caso = derivacion, derivacion.caso
        if derivacion.estado != Derivacion.Estado.ACEPTADA or self.caso.estado not in self.estados:
            return self.ya_no(request)
        return None

    def ya_no(self, request):
        if self.derivacion.estado == Derivacion.Estado.ACEPTADA and self.caso.estado == Estado.ALOJADO:
            messages.info(request, f"La familia del caso {self.caso.numero} ya figura alojada.")
            return redirect(self.url("integrantes", self.caso.pk))
        if self.derivacion.estado == Derivacion.Estado.PENDIENTE:
            return redirect(self.url("llegadas", derivacion=self.derivacion.pk))
        messages.warning(request, f"El ingreso del caso {self.caso.numero} ya no está en curso en este dispositivo.")
        return redirect(self.url("llegadas"))

    def url_integrantes(self):
        return self.url("integrantes", self.caso.pk)

    def traducir(self, request, accion):
        """Corre ``accion()`` y traduce lo que rechace el servicio. Devuelve ``(resultado, respuesta)``."""

        try:
            return accion(), None
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            destino = self.url_integrantes() if cambio.estado_actual in self.estados else self.url("llegadas")
            if cambio.estado_actual == Estado.ALOJADO:
                destino = self.url_integrantes()
            return None, redirect(destino)
        except ValidationError as error:
            messages.error(request, _mensajes(error))
            return None, redirect(self.url_integrantes())


class IntegrantesView(_IngresoView):
    """M2-3: las N filas de la familia con el contador, y los cierres del ingreso."""

    estados = (Estado.INGRESO_EN_CURSO, Estado.ALOJADO)

    def get(self, request, pk, caso_pk):
        caso = self.caso
        datos = selectores.integrantes_de(caso)
        confirmadas, total = datos["confirmadas"], datos["total_declarado"]
        acciones = servicio.acciones_del_ingreso(
            estado=caso.estado, confirmadas=confirmadas, total=max(total, len(datos["integrantes"]))
        )
        contexto = self.contexto(
            2,
            caso,
            familia=f"Familia {caso.grupo.responsable.apellido}",
            filas=pantalla.filas_de_integrantes(datos, lambda n: self.url("ficha", caso.pk, n)),
            confirmadas=confirmadas,
            total=total,
            declaradas=datos["declaradas_al_relevar"],
            en_curso=caso.estado == Estado.INGRESO_EN_CURSO,
            parcial=caso.ingreso_parcial,
            alojamiento=caso.alojamiento,
            diferencia=caso.diferencia,
            fotos=pantalla.fotos_del_caso(caso),
            puede_alojar=acciones["alojar"],
            puede_diferencia=acciones["diferencia"],
            puede_cancelar=acciones["cancelar"],
            puede_agregar=acciones["agregar"],
            url_agregar=self.url("agregar", caso.pk),
            url_alojar=self.url("alojar", caso.pk),
            url_diferencia=self.url("diferencia", caso.pk),
            url_cancelar=self.url("cancelar", caso.pk),
        )
        if contexto["puede_diferencia"]:
            contexto["form_diferencia"] = DiferenciaForm(auto_id="diferencia_%s")
        if contexto["puede_cancelar"]:
            contexto["form_cancelar"] = CancelarIngresoForm(auto_id="cancelar_%s")
        return render(request, f"{TEMPLATES}integrantes.html", contexto)


class AgregarIntegranteView(_IngresoView):
    """RN-3.8: suma una persona que no estaba declarada y abre su ficha."""

    http_method_names = ["post"]

    def post(self, request, pk, caso_pk):
        integrante, respuesta = self.traducir(
            request, lambda: servicio.agregar_integrante(caso=self.caso, usuario=request.user)
        )
        if respuesta is not None:
            return respuesta
        messages.success(
            request, f"Persona {integrante.orden} agregada. La cama se elige entre las libres al confirmarla."
        )
        return redirect(self.url("ficha", self.caso.pk, integrante.orden))


class _IntegranteView(_IngresoView):
    """Una pantalla sobre **una** fila de la familia."""

    estados = (Estado.INGRESO_EN_CURSO, Estado.ALOJADO)

    def preparar(self, request, **kwargs):
        previo = super().preparar(request, **kwargs)
        if previo is not None:
            return previo
        self.integrante = get_object_or_404(
            IntegranteGrupo.objects.select_related("ciudadano", "estadia__plaza__sector"),
            grupo_id=self.caso.grupo_id,
            orden=kwargs["orden"],
        )
        if not self.integrante.confirmada and self.caso.estado != Estado.INGRESO_EN_CURSO:
            messages.warning(request, "El ingreso ya se cerró: esa persona quedó sin confirmar.")
            return redirect(self.url_integrantes())
        return None

    def mapa(self):
        """Lo que contesta ``plazas_para_caso``, una sola vez por petición."""

        if not hasattr(self, "_mapa"):
            self._mapa = selectores.plazas_para_caso(
                self.dispositivo,
                self.caso,
                self.request.user,
                puede_ver_personas=puede(self.request.user, CAP_VER_CIUDADANO),
            )
        return self._mapa

    def cama_pedida(self, valor):
        """La cama que pidió la URL o el formulario si se puede elegir; si no, la sugerida."""

        if valor not in (None, "") and str(valor).isdecimal():
            cama = pantalla.cama_por_id(self.mapa(), int(valor))
            if cama is not None and cama["elegible"]:
                return cama
        sugerida = pantalla.cama_sugerida(self.mapa())
        return pantalla.cama_por_id(self.mapa(), sugerida) if sugerida is not None else None


class ElegirCamaView(_IntegranteView):
    """El mapa de camas en modo emergencia: tocar una cama vuelve a la ficha con esa cama elegida."""

    def get(self, request, pk, caso_pk, orden):
        if self.integrante.confirmada:
            return redirect(self.url("ficha", caso_pk, orden))
        actual = request.GET.get("cama") or ""
        elegida = int(actual) if actual.isdecimal() else None
        sectores = pantalla.mapa_para_elegir(
            self.mapa(), elegida, lambda plaza_id: self.url("ficha", caso_pk, orden, cama=plaza_id)
        )
        contexto = self.contexto(
            2,
            self.caso,
            orden=orden,
            sectores=sectores,
            leyenda=selectores.LEYENDA_PLAZAS_EMERGENCIA,
            hay_elegibles=any(plaza.get("url") for sector in sectores for plaza in sector["plazas"]),
            url_ficha=self.url("ficha", caso_pk, orden, cama=elegida),
        )
        return render(request, f"{TEMPLATES}cama.html", contexto)


class FichaIntegranteView(_IntegranteView):
    """M2-4: la ficha individual. Sin confirmar, con el mínimo y la cama; confirmada, las secciones que faltan."""

    def _iniciales(self):
        """La persona 1 arranca con los datos del responsable: es quien suele llegar primero."""

        if self.integrante.orden != 1:
            return {}
        responsable = self.caso.grupo.responsable
        return {
            "parentesco": IntegranteGrupo.Parentesco.JEFE,
            "dni": responsable.dni,
            "nombre": responsable.nombre,
            "apellido": responsable.apellido,
            "sexo": responsable.genero,
            "fecha_nacimiento": responsable.fecha_nacimiento,
            "telefono": self.caso.situacion.get("telefono", ""),
        }

    def _render(self, request, form, cama=None, status=200):
        integrante = self.integrante
        contexto = self.contexto(
            2,
            self.caso,
            orden=integrante.orden,
            titulo=(
                f"Ficha de la persona {integrante.orden}"
                if integrante.confirmada
                else f"Confirmar a la persona {integrante.orden}"
            ),
            form=form,
            confirmada=integrante.confirmada,
            cama=cama,
            url_cama=self.url("cama", self.caso.pk, integrante.orden, cama=cama["id"] if cama else None),
        )
        if integrante.confirmada:
            cama_actual = integrante.estadia.plaza if integrante.estadia_id and integrante.estadia.plaza_id else None
            contexto.update(
                persona=integrante.ciudadano.apellido_nombre,
                dni=integrante.ciudadano.dni,
                parentesco=integrante.parentesco_otro or integrante.get_parentesco_display(),
                cama_actual=f"{cama_actual.codigo} ({cama_actual.sector.nombre})" if cama_actual else "",
                egresada=integrante.egresado_en is not None,
                ficha_completa=integrante.ficha_completa,
                faltan=servicio.secciones_incompletas(integrante.ficha),
            )
        return render(request, f"{TEMPLATES}ficha.html", contexto, status=status)

    def get(self, request, pk, caso_pk, orden):
        if self.integrante.confirmada:
            return self._render(request, FichaIntegranteForm(solo_opcionales=True, ficha=self.integrante.ficha))
        cama = self.cama_pedida(request.GET.get("cama"))
        form = FichaIntegranteForm(initial={**self._iniciales(), "plaza": cama["id"] if cama else None})
        return self._render(request, form, cama)

    def post(self, request, pk, caso_pk, orden):
        if self.integrante.confirmada:
            return self._completar(request)
        form = FichaIntegranteForm(request.POST)
        cama = self.cama_pedida(request.POST.get("plaza"))
        if not form.is_valid():
            return self._render(request, form, cama, status=400)
        try:
            integrante = servicio.confirmar_integrante(
                caso=self.caso,
                orden=orden,
                usuario=request.user,
                ficha=form.ficha(),
                # Lo que la pantalla mostró, no lo sugerido: si esa cama ya no se puede, lo dice el servicio.
                plaza=form.cleaned_data.get("plaza"),
            )
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return redirect(self.url_integrantes())
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._render(request, form, cama, status=400)
        plaza = integrante.estadia.plaza
        messages.success(
            request,
            f"{integrante.ciudadano.nombre_completo} quedó en la cama {plaza.codigo} ({plaza.sector.nombre}) · "
            f"{integrante.confirmadas} de {integrante.total_declarado} confirmadas.",
        )
        return redirect(self.url_integrantes())

    def _completar(self, request):
        form = FichaIntegranteForm(request.POST, solo_opcionales=True)
        if not form.is_valid():
            return self._render(request, form, status=400)
        try:
            integrante = servicio.completar_ficha(
                caso=self.caso, orden=self.integrante.orden, usuario=request.user, ficha=form.ficha()
            )
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return redirect(self.url("llegadas"))
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._render(request, form, status=400)
        estado = "quedó completa" if integrante.ficha_completa else "se guardó; todavía faltan secciones"
        messages.success(request, f"La ficha de la persona {integrante.orden} {estado}.")
        return redirect(self.url_integrantes())


# ---------------------------------------------------------------------------
# Paso 3 · Cerrar el ingreso (M2-5, RN-3.9)
# ---------------------------------------------------------------------------


class FamiliaAlojadaView(_IngresoView):
    """M2-5: la sección 4 del Formulario 1, con las N de N confirmadas."""

    def preparar(self, request, **kwargs):
        previo = super().preparar(request, **kwargs)
        if previo is not None:
            return previo
        self.datos = selectores.integrantes_de(self.caso)
        confirmadas = self.datos["confirmadas"]
        total = max(self.datos["total_declarado"], len(self.datos["integrantes"]))
        if not servicio.acciones_del_ingreso(estado=self.caso.estado, confirmadas=confirmadas, total=total)["alojar"]:
            messages.error(request, servicio.mensaje_faltan_confirmar(total - confirmadas))
            return redirect(self.url_integrantes())
        return None

    def _form(self, data=None):
        sectores = selectores.sectores_del_dispositivo(self.dispositivo)
        # El sector se preselecciona con el de las camas de la familia: el que más se repite.
        de_las_camas = Counter(
            integrante["plaza"]["sector_id"] for integrante in self.datos["integrantes"] if integrante["plaza"]
        ).most_common(1)
        iniciales = {"sector": de_las_camas[0][0] if de_las_camas else None, "encargado": nombre_de(self.request.user)}
        return FamiliaAlojadaForm(data, sectores=sectores, initial=iniciales)

    def _render(self, request, form, status=200):
        caso = self.caso
        contexto = self.contexto(
            3,
            caso,
            form=form,
            resumen={
                "familia": f"Familia {caso.grupo.responsable.apellido}",
                "caso": caso.numero,
                "personas": f"{self.datos['confirmadas']} de {self.datos['total_declarado']} confirmadas",
                "camas": ", ".join(
                    integrante["plaza"]["nombre"] for integrante in self.datos["integrantes"] if integrante["plaza"]
                ),
                "incompletas": self.datos["con_ficha_incompleta"],
            },
        )
        return render(request, f"{TEMPLATES}alojar.html", contexto, status=status)

    def get(self, request, pk, caso_pk):
        return self._render(request, self._form())

    def post(self, request, pk, caso_pk):
        form = self._form(request.POST)
        if not form.is_valid():
            return self._render(request, form, status=400)
        try:
            caso = servicio.alojar_familia(caso=self.caso, usuario=request.user, **form.cleaned_data)
        except EstadoCambio as cambio:
            messages.warning(request, cambio.mensaje)
            return redirect(self.url("llegadas"))
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._render(request, form, status=400)
        alojamiento = caso.alojamiento
        donde = " · ".join(parte for parte in (alojamiento["sector"], alojamiento["aula"]) if parte)
        messages.success(
            request,
            f"Familia {self.caso.grupo.responsable.apellido} alojada · {caso.total_alojado} de "
            f"{self.datos['total_declarado']}" + (f" · {donde}" if donde else "") + ". Podés buscar otra familia.",
        )
        return redirect(self.url("llegadas"))


class CerrarConDiferenciaView(_IngresoView):
    """RN-3.9: llegaron menos. Confirmación con motivo (arquetipo Modal)."""

    http_method_names = ["post"]

    def post(self, request, pk, caso_pk):
        form = DiferenciaForm(request.POST)
        if not form.is_valid():
            messages.error(request, _errores_de(form))
            return redirect(self.url_integrantes())
        caso, respuesta = self.traducir(
            request,
            lambda: servicio.cerrar_con_diferencia(caso=self.caso, usuario=request.user, **form.cleaned_data),
        )
        if respuesta is not None:
            return respuesta
        diferencia = caso.diferencia
        messages.success(
            request,
            f"Ingreso cerrado con diferencia: {diferencia['confirmadas']} de {diferencia['declaradas']} personas "
            f"alojadas. Se liberaron {caso.reservas_liberadas} camas reservadas y la mesa ve el motivo.",
        )
        return redirect(self.url("llegadas"))


class CancelarIngresoView(_IngresoView):
    """Sin nadie confirmado: el caso vuelve a la mesa. Confirmación con motivo (arquetipo Modal)."""

    http_method_names = ["post"]

    def post(self, request, pk, caso_pk):
        form = CancelarIngresoForm(request.POST)
        if not form.is_valid():
            messages.error(request, _errores_de(form))
            return redirect(self.url_integrantes())
        _caso, respuesta = self.traducir(
            request, lambda: servicio.cancelar_ingreso(caso=self.caso, usuario=request.user, **form.cleaned_data)
        )
        if respuesta is not None:
            return respuesta
        messages.success(request, "Ingreso cancelado. Las camas quedaron libres y el caso volvió a la mesa.")
        return redirect(self.url("llegadas"))


# ---------------------------------------------------------------------------
# Sin derivación (M2-6). El ingreso directo va al final y en su propia vista a propósito:
# es la decisión 4 del PM, y se tiene que poder sacar sin tocar el resto.
# ---------------------------------------------------------------------------


class _Formulario1View(GuardiaView):
    """El Formulario 1 cargado en la puerta del dispositivo. Las subclases dicen qué se hace con él."""

    titulo = ""
    bajada = ""
    accion = ""
    icono = "fa-check"

    def _render(self, request, form, status=200):
        contexto = self.contexto(1, form=form, titulo=self.titulo, bajada=self.bajada, accion=self.accion)
        contexto["icono"] = self.icono
        return render(request, f"{TEMPLATES}formulario1.html", contexto, status=status)

    def get(self, request, pk):
        return self._render(request, Formulario1DispositivoForm(initial={"dni": request.GET.get("dni", "")}))

    def post(self, request, pk):
        form = Formulario1DispositivoForm(request.POST, request.FILES)
        if not form.is_valid():
            return self._render(request, form, status=400)
        try:
            caso = self.ejecutar(request, form.datos_formulario1())
        except ValidationError as error:
            form.agregar_errores_del_servicio(error)
            return self._render(request, form, status=400)
        return self.despues(request, caso)


class AvisarALaMesaView(_Formulario1View):
    titulo = "Avisar a la mesa"
    bajada = (
        "La familia está en la puerta y no hay una derivación para este dispositivo. El caso llega a la mesa "
        "marcado «En la puerta», y la mesa decide a dónde derivarla."
    )
    accion = "Avisar a la mesa"
    icono = "fa-bullhorn"

    def ejecutar(self, request, datos):
        return servicio.avisar_a_la_mesa(dispositivo=self.dispositivo, usuario=request.user, datos_formulario1=datos)

    def despues(self, request, caso):
        messages.success(
            request, f"Caso {caso.numero} enviado a la mesa. Cuando lo deriven acá, buscá a la familia de nuevo."
        )
        return redirect(self.url("llegadas"))


class IngresoDirectoView(_Formulario1View):
    titulo = "Ingresar igual"
    bajada = (
        "La familia llegó sin derivación y hay camas libres. El caso nace con el ingreso en curso, sin pasar "
        "por la mesa, y queda marcado como ingreso directo."
    )
    accion = "Crear el caso y seguir con las fichas"

    def ejecutar(self, request, datos):
        return servicio.ingreso_directo(dispositivo=self.dispositivo, usuario=request.user, datos_formulario1=datos)

    def despues(self, request, caso):
        if caso.faltantes:
            messages.warning(
                request,
                f"Caso {caso.numero} creado. Reservé {caso.reservadas} camas y faltan {caso.faltantes}: "
                "confirmá a las personas que entren y cerrá con diferencia si no alcanza.",
            )
        else:
            messages.success(request, f"Caso {caso.numero} creado. Reservé {caso.reservadas} camas para la familia.")
        return redirect(self.url("integrantes", caso.pk))
