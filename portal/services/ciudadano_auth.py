from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.db import transaction

from legajos.models import Ciudadano
from legajos.services.consulta_renaper import consultar_datos_renaper

LOGIN_MAX_INTENTOS = 5
LOGIN_BLOQUEO_SEGUNDOS = 300


class RegistroCiudadanoError(Exception):
    pass


class RegistroCiudadanoCuentaExistenteError(RegistroCiudadanoError):
    pass


class RegistroCiudadanoSesionInvalidaError(RegistroCiudadanoError):
    pass


class RegistroCiudadanoIdentidadNoVerificadaError(RegistroCiudadanoError):
    pass


class RegistroCiudadanoServicioNoDisponibleError(RegistroCiudadanoError):
    pass


class RegistroCiudadanoLegajoYaVinculadoError(RegistroCiudadanoError):
    pass


def get_login_cache_key(ip):
    return f"login_intentos_{ip}"


def get_login_intentos(ip):
    return cache.get(get_login_cache_key(ip), 0)


def login_bloqueado(ip):
    return get_login_intentos(ip) >= LOGIN_MAX_INTENTOS


def registrar_login_fallido(ip):
    cache.set(get_login_cache_key(ip), get_login_intentos(ip) + 1, LOGIN_BLOQUEO_SEGUNDOS)


def limpiar_login_fallido(ip):
    cache.delete(get_login_cache_key(ip))


def preparar_registro_ciudadano(*, dni, genero):
    ciudadano = Ciudadano.objects.filter(dni=dni).first()
    if ciudadano:
        if ciudadano.usuario_id:
            raise RegistroCiudadanoCuentaExistenteError()
        return {
            "flujo": "legajo_existente",
            "ciudadano_id": ciudadano.pk,
            "dni": dni,
        }

    try:
        resultado = consultar_datos_renaper(dni, genero)
    except Exception as exc:
        raise RegistroCiudadanoServicioNoDisponibleError() from exc

    if not resultado.get("success"):
        raise RegistroCiudadanoIdentidadNoVerificadaError()

    datos_renaper = resultado["data"]
    return {
        "flujo": "nuevo",
        "dni": dni,
        "genero": genero,
        "nombre": datos_renaper.get("nombre", ""),
        "apellido": datos_renaper.get("apellido", ""),
    }


@transaction.atomic
def completar_registro_ciudadano(*, datos_registro, email, telefono, password):
    if not datos_registro or "dni" not in datos_registro:
        raise RegistroCiudadanoSesionInvalidaError()

    dni = datos_registro["dni"]
    if User.objects.filter(username=dni).exists():
        raise RegistroCiudadanoCuentaExistenteError()

    grupo, _ = Group.objects.get_or_create(name="Ciudadanos")
    flujo = datos_registro.get("flujo")

    if flujo == "legajo_existente":
        ciudadano = Ciudadano.objects.select_for_update().get(pk=datos_registro["ciudadano_id"])
        if ciudadano.usuario_id:
            raise RegistroCiudadanoLegajoYaVinculadoError()
        nombre = ciudadano.nombre
        apellido = ciudadano.apellido
    else:
        ciudadano = None
        nombre = datos_registro.get("nombre", "")
        apellido = datos_registro.get("apellido", "")

    user = User.objects.create_user(username=dni, email=email, password=password)
    user.groups.add(grupo)

    if flujo == "legajo_existente":
        ciudadano.usuario = user
        if email:
            ciudadano.email = email
        if telefono:
            ciudadano.telefono = telefono
        ciudadano.save()
    else:
        ciudadano = Ciudadano.objects.create(
            dni=dni,
            nombre=nombre,
            apellido=apellido,
            email=email,
            telefono=telefono or "",
            genero=datos_registro.get("genero", "X"),
            usuario=user,
        )

    user.first_name = ciudadano.nombre
    user.last_name = ciudadano.apellido
    user.save()
    return user, ciudadano
