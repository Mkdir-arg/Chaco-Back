"""Serializers de «Plazas y estadías» en la app de campo (Cambio 596): solo lectura.

Las respuestas las arma ``programas.services.plazas_app`` (fechas ya en ISO 8601 con zona); acá se fijan las claves
que lee la app (`Chaco-mobile`). Agregar una clave es seguro; renombrarla o sacarla es un release coordinado de la
app y de ``programas/tests/test_api_emergencia_plazas.py``. Documentado en ``docs/internal/contrato-app-emergencia.md``.
"""

from rest_framework import serializers


class ResumenPlazasSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    libres = serializers.IntegerField()
    ocupadas = serializers.IntegerField()
    reservadas = serializers.IntegerField()
    prestadas = serializers.IntegerField()
    fuera_servicio = serializers.IntegerField()


class DispositivoBreveSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class DispositivoDelMapaSerializer(DispositivoBreveSerializer):
    estado = serializers.CharField(help_text="Estado de la institución (`ACTIVO`, `CERRADO`…).")


class EdificioBreveSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class EdificioConDireccionSerializer(EdificioBreveSerializer):
    direccion = serializers.CharField(allow_blank=True, help_text="Calle, número, localidad y provincia.")


class EdificioDeLaAppSerializer(serializers.Serializer):
    """Un par institución-edificio en el alcance del usuario, con las cifras de sus camas."""

    dispositivo = DispositivoBreveSerializer()
    edificio = EdificioConDireccionSerializer()
    resumen = ResumenPlazasSerializer()


class PersonaEnPlazaSerializer(serializers.Serializer):
    nombre = serializers.CharField(help_text="«Apellido, Nombre».")
    dni = serializers.CharField(allow_null=True)


class PlazaDelEdificioSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()
    tipo = serializers.CharField()
    estado = serializers.ChoiceField(choices=["disponible", "ocupada", "reservada", "prestada", "fuera_servicio"])
    persona = PersonaEnPlazaSerializer(allow_null=True, help_text="Solo con `ciudadano.ver`; si no, `null`.")
    estadia_id = serializers.IntegerField(allow_null=True)
    reserva_id = serializers.IntegerField(
        allow_null=True, help_text="La reserva o el préstamo sin liberar, aunque haya vencido."
    )
    desde = serializers.CharField(allow_null=True, help_text="Ingreso de la estadía o inicio de la reserva (ISO 8601).")
    hasta = serializers.CharField(allow_null=True, help_text="Fin de la reserva o del préstamo, si tiene.")
    acciones = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["egresar", "reubicar", "liberar", "reservar", "prestar", "fuera_servicio", "volver"]
        ),
        help_text="Lo que este usuario puede hacer con la cama ahora, en el orden del modal de la web.",
    )
    bloqueo = serializers.CharField(
        allow_blank=True, help_text="Por qué la acción `fuera_servicio` no va a proceder; vacío si procede."
    )


class SectorDelEdificioSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    tipo = serializers.CharField()
    resumen = ResumenPlazasSerializer()
    plazas = PlazaDelEdificioSerializer(many=True)


class PuedeEnElMapaSerializer(serializers.Serializer):
    egresar = serializers.BooleanField()
    admitir = serializers.BooleanField()
    editar = serializers.BooleanField()
    ver_personas = serializers.BooleanField()


class MapaDelEdificioSerializer(serializers.Serializer):
    """El mapa de camas de un edificio. Lo devuelven también las acciones de cama (Cambios 597 y 598)."""

    dispositivo = DispositivoDelMapaSerializer()
    edificio = EdificioBreveSerializer()
    resumen = ResumenPlazasSerializer()
    puede = PuedeEnElMapaSerializer()
    sectores = SectorDelEdificioSerializer(many=True)


class SectorBreveSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class PlazaBreveSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField()


class EmergenciaDeLaEstadiaSerializer(serializers.Serializer):
    caso_numero = serializers.CharField()


class EstadiaDelEdificioSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    persona = PersonaEnPlazaSerializer(allow_null=True, help_text="Solo con `ciudadano.ver`; si no, `null`.")
    sector = SectorBreveSerializer(allow_null=True)
    plaza = PlazaBreveSerializer(allow_null=True)
    fecha_ingreso = serializers.CharField()
    fecha_egreso = serializers.CharField(allow_null=True)
    estado = serializers.ChoiceField(choices=["activa", "egresada"])
    origen = serializers.ChoiceField(choices=["emergencia", "dispositivo"])
    emergencia = EmergenciaDeLaEstadiaSerializer(allow_null=True)
    acciones = serializers.ListField(child=serializers.ChoiceField(choices=["egresar", "reubicar"]))


class PaginaDeEstadiasSerializer(serializers.Serializer):
    """La página al estilo DRF: `count`, `next`, `previous` y `results`."""

    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = EstadiaDelEdificioSerializer(many=True)
