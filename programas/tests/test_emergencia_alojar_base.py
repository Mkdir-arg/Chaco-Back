"""Base común de los tests de la etapa 3 de Emergencia (alojar): ``BaseAlojar`` y ``ficha_minima``.

Sin tests: lo importan ``test_emergencia_alojar`` y los de cada módulo del servicio
(``test_emergencia_recepcion``, ``…_confirmacion``, ``…_cierre``, ``…_sin_derivacion``), las
vistas y las carreras.
"""

from datetime import time

from django.contrib.auth.models import User

from programas.models import (
    CasoEmergencia,
    Derivacion,
    MiembroEquipoDispositivo,
    MotivoEgreso,
    ReservaPlaza,
    TrazaCaso,
    Turno,
)
from programas.selectors import emergencia_alojar as selectores
from programas.services import emergencia as mesa
from programas.services import emergencia_alojar as servicio
from programas.tests.test_emergencia_casos import BaseCasos

Estado = CasoEmergencia.Estado
Accion = TrazaCaso.Accion

GUARDIA = ("dispositivo.ver", "dispositivo.admitir", "dispositivo.egresar")


def ficha_minima(dni, **cambios):
    """Una ficha con el mínimo: hija de 20 años, las cinco preguntas en «no»."""

    ficha = {
        "parentesco": {"parentesco": "HIJO"},
        "datos_personales": {
            "dni": dni,
            "nombre": "Juan",
            "apellido": "Pérez",
            "sexo": "M",
            "fecha_nacimiento": "2006-03-10",
        },
        "avisos_salud": {
            "embarazo": False,
            "discapacidad": False,
            "electrodependiente": False,
            "medicacion_critica": False,
            "alergias_graves": False,
        },
    }
    for seccion, datos in cambios.items():
        ficha.setdefault(seccion, {}).update(datos)
    return ficha


class BaseAlojar(BaseCasos):
    """La mesa de ``BaseCasos`` más dos dispositivos con guardia propia y una familia de 7."""

    def setUp(self):
        super().setUp()
        self.club = self._dispositivo("Club Sarmiento", camas=9, localidad="Resistencia")
        self.escuela = self._dispositivo("Escuela 12", camas=5)
        self.guardia = self._guardia("guardia_club", self.club)
        self.guardia_escuela = self._guardia("guardia_escuela", self.escuela)
        self.motivo_alta, _ = MotivoEgreso.objects.get_or_create(codigo="alta", defaults={"nombre": "Alta", "orden": 1})

    def _guardia(self, nombre, *dispositivos, capacidades=GUARDIA):
        usuario = self._usuario(nombre, capacidades, programa=self.dispositivos)
        rol = usuario.groups.get()
        for dispositivo in dispositivos:
            MiembroEquipoDispositivo.objects.create(dispositivo=dispositivo, usuario=usuario, rol=rol)
        return User.objects.get(pk=usuario.pk)

    def _turno(self, dispositivo):
        """Un turno que cubre las 10 de la mañana de ``T0``: con él la bitácora se escribe."""

        return Turno.objects.create(dispositivo=dispositivo, nombre="Mañana", hora_desde=time(6), hora_hasta=time(14))

    def _derivado(self, dispositivo=None, plazas=None, **datos):
        """Un caso de 7 personas tomado y derivado. Devuelve ``(caso, derivacion)``."""

        datos = {"menores_f": 2, "menores_m": 3, "dni": "30111222", "nombre": "Rosa", "apellido": "Benítez", **datos}
        caso = self._caso_tomado(**datos)
        derivacion = mesa.derivar_caso(
            caso, self.operador, dispositivo or self.club, plazas or caso.grupo.total_declarado, True
        )
        return CasoEmergencia.objects.get(pk=caso.pk), derivacion

    def _aceptado(self, **kwargs):
        caso, derivacion = self._derivado(**kwargs)
        resultado = servicio.aceptar_derivacion(derivacion=derivacion, usuario=self.guardia)
        return resultado.caso, resultado.derivacion

    def _reservas(self, derivacion, estado=ReservaPlaza.Estado.VIGENTE):
        return list(ReservaPlaza.objects.filter(derivacion=derivacion, estado=estado).order_by("plaza_id"))

    def _confirmar(self, caso, orden, dni, plaza=None, usuario=None, **cambios):
        if plaza is None:
            plaza = self._reservas(Derivacion.objects.get(clave_vigente=caso.pk))[0].plaza
        return servicio.confirmar_integrante(
            caso=caso, orden=orden, usuario=usuario or self.guardia, ficha=ficha_minima(dni, **cambios), plaza=plaza
        )

    def _cama_libre(self, dispositivo=None):
        return selectores.camas_libres(dispositivo or self.club)[0]

    def _estado(self, caso):
        return CasoEmergencia.objects.values_list("estado", flat=True).get(pk=caso.pk)
