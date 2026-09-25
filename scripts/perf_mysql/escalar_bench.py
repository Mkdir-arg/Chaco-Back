"""Escala el banco a la forma de producción: UN relevamiento público con N casos
completos (foto de la definición, respuestas, data legacy, legajo, adjuntos,
validaciones SIIS y trazas de aprobación), sobre lo que ya sembró seed_perf.

Uso (desde la raíz del repo, con DATABASE_* apuntando al banco; ver README.md):
    python scripts/perf_mysql/escalar_bench.py --casos 20000
"""

import argparse
import random
import uuid
from datetime import timedelta

from _bootstrap import cargar_django  # noqa: E402

cargar_django()

from django.contrib.auth.models import User  # noqa: E402
from django.utils import timezone  # noqa: E402

from legajos.models import Ciudadano  # noqa: E402
from programas.models import (  # noqa: E402
    AdjuntoFormulario,
    Convocatoria,
    Formulario,
    Relevamiento,
    RequisitoNativo,
    Segmento,
    TracaFormulario,
    ValidacionSIS,
)
from programas.services.becas import definicion_formulario  # noqa: E402
from programas.services.respuestas import campos_de, foto_definicion, legacy_desde_respuestas  # noqa: E402

LOTE = 1000
random.seed(42)


def _respuestas_para(foto, i):
    """Una respuesta plausible por ítem visible de la foto."""
    respuestas = {}
    for item in campos_de(foto):
        clave = item.get("clave")
        tipo = (item.get("tipo_campo") or item.get("tipo") or "").upper()
        if not clave:
            continue
        vinculo = item.get("vinculo") or ""
        if vinculo == "dni":
            respuestas[clave] = f"{30000000 + i}"
        elif vinculo == "nombre":
            respuestas[clave] = f"Nombre{i}"
        elif vinculo == "apellido":
            respuestas[clave] = f"Apellido{i}"
        elif vinculo == "fecha_nacimiento":
            respuestas[clave] = f"19{80 + i % 20:02d}-0{1 + i % 9}-1{i % 9}"
        elif vinculo == "telefono":
            respuestas[clave] = f"3624{i:06d}"
        elif vinculo == "email":
            respuestas[clave] = f"caso{i}@bench.invalid"
        elif vinculo == "genero":
            respuestas[clave] = "F" if i % 2 else "M"
        elif tipo == "SELECTOR":
            opciones = item.get("opciones") or ["Sí", "No"]
            respuestas[clave] = opciones[i % len(opciones)]
        elif tipo == "SELECTOR_MULTIPLE":
            opciones = item.get("opciones") or ["A", "B"]
            respuestas[clave] = opciones[: 1 + i % len(opciones)]
        elif tipo == "ARCHIVO":
            respuestas[clave] = f"adjunto_{i}.jpg"
        elif tipo == "INT":
            respuestas[clave] = str(i % 1000)
        elif tipo == "DATE":
            respuestas[clave] = "2026-03-15"
        else:
            respuestas[clave] = f"Respuesta de texto del caso {i}: " + "x" * 60
    return respuestas


def main(casos):
    admin = User.objects.filter(is_superuser=True).first() or User.objects.first()
    segmento = Segmento.objects.order_by("pk").first()
    conv, _ = Convocatoria.objects.get_or_create(
        nombre="BENCH Convocatoria pública",
        segmento=segmento,
        defaults={
            "fecha_inicio": timezone.localdate() - timedelta(days=60),
            "fecha_fin": timezone.localdate() + timedelta(days=60),
        },
    )
    rel, creado = Relevamiento.objects.get_or_create(
        convocatoria=conv,
        tipo=Relevamiento.Tipo.PUBLICO,
        defaults={
            "fecha_asignada": timezone.now() - timedelta(days=30),
            "fecha_hasta": timezone.now() + timedelta(days=30),
            "cupo_maximo": casos * 2,
            "estado": Relevamiento.Estado.EN_CURSO,
        },
    )
    if not creado and rel.cupo_maximo < casos * 2:
        rel.cupo_maximo = casos * 2
        rel.save(update_fields=["cupo_maximo"])
    ya = Formulario.objects.filter(relevamiento=rel).count()
    if ya >= casos:
        print(f"El relevamiento público {rel.pk} ya tiene {ya} casos; nada que hacer.")
        return rel

    foto = foto_definicion(rel, definicion_formulario(rel))
    print(f"foto de la definición: {len(foto.get('items', []))} ítems, ~{len(str(foto))} bytes")
    requisito_archivo = RequisitoNativo.objects.filter(tipo="ARCHIVO").order_by("pk").first()

    inicio = ya
    numero_base = (
        Formulario.objects.filter(relevamiento=rel).order_by("-numero").values_list("numero", flat=True).first() or 0
    )
    ahora = timezone.now()
    for lote_ini in range(inicio, casos, LOTE):
        lote_fin = min(lote_ini + LOTE, casos)
        ciudadanos = [
            Ciudadano(
                dni=f"{30000000 + i}",
                nombre=f"Nombre{i}",
                apellido=f"Apellido{i}",
                genero="F" if i % 2 else "M",
            )
            for i in range(lote_ini, lote_fin)
        ]
        Ciudadano.objects.bulk_create(ciudadanos, ignore_conflicts=True)
        dnis = [c.dni for c in ciudadanos]
        por_dni = dict(Ciudadano.objects.filter(dni__in=dnis).values_list("dni", "pk"))

        formularios = []
        for i in range(lote_ini, lote_fin):
            respuestas = _respuestas_para(foto, i)
            data, fijos = legacy_desde_respuestas(respuestas, foto)
            r = random.random()
            estado = (
                Formulario.Estado.APROBADO
                if r < 0.45
                else Formulario.Estado.RECHAZADO
                if r < 0.55
                else Formulario.Estado.ENVIADO
            )
            formularios.append(
                Formulario(
                    relevamiento=rel,
                    numero=numero_base + i - inicio + 1,
                    estado=estado,
                    ciudadano_id=por_dni[f"{30000000 + i}"],
                    dni_titular=f"{30000000 + i}",
                    celular=fijos.get("celular", ""),
                    email_contacto=fijos.get("email_contacto", ""),
                    data=data,
                    respuestas=respuestas,
                    definicion=foto,
                    datos_identificacion=None,
                    client_uuid=uuid.uuid4(),
                    validado_renaper=i % 3 != 0,
                    capturado_en=ahora - timedelta(minutes=casos - i),
                    created_by=None,
                )
            )
        Formulario.objects.bulk_create(formularios, batch_size=LOTE)
        # bulk_create no devuelve pks en MySQL: se releen por numero.
        pks = dict(
            Formulario.objects.filter(
                relevamiento=rel, numero__gte=formularios[0].numero, numero__lte=formularios[-1].numero
            ).values_list("numero", "pk")
        )
        trazas, validaciones, adjuntos = [], [], []
        for f in formularios:
            pk = pks[f.numero]
            if f.estado == Formulario.Estado.APROBADO:
                trazas.append(
                    TracaFormulario(
                        formulario_id=pk,
                        editado_por=admin,
                        campo="estado",
                        valor_anterior="ENVIADO",
                        valor_nuevo="APROBADO",
                    )
                )
                validaciones.append(
                    ValidacionSIS(
                        formulario_id=pk,
                        estado=ValidacionSIS.Estado.OK,
                        documento=f.dni_titular,
                        sexo="F",
                        respuesta={"ok": True},
                    )
                )
            elif f.estado == Formulario.Estado.RECHAZADO:
                validaciones.append(
                    ValidacionSIS(
                        formulario_id=pk,
                        estado=ValidacionSIS.Estado.RECHAZADO,
                        documento=f.dni_titular,
                        sexo="M",
                        codigo_motivo="E01",
                        motivo="No cumple",
                        respuesta={"ok": False},
                    )
                )
            if requisito_archivo is not None:
                adjuntos.append(
                    AdjuntoFormulario(
                        formulario_id=pk,
                        requisito_nativo=requisito_archivo,
                        archivo=f"becas/adjuntos/bench/{uuid.uuid4().hex}.jpg",
                    )
                )
        TracaFormulario.objects.bulk_create(trazas, batch_size=LOTE)
        ValidacionSIS.objects.bulk_create(validaciones, batch_size=LOTE)
        AdjuntoFormulario.objects.bulk_create(adjuntos, batch_size=LOTE)
        print(f"  casos {lote_ini}..{lote_fin - 1} listos")
    # Fechas de creación repartidas en 60 días (auto_now_add no deja fijarlas en el insert).
    Formulario.objects.filter(relevamiento=rel).update(creado=ahora - timedelta(days=30))
    print(
        f"Relevamiento público {rel.pk} (convocatoria {conv.pk}): {Formulario.objects.filter(relevamiento=rel).count()} casos"
    )
    return rel


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--casos", type=int, default=20000)
    main(parser.parse_args().casos)
