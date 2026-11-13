"""Etapa 3 de Emergencia: el dispositivo recibe a la familia y la aloja (03-alojar).

``DERIVADO → INGRESO_EN_CURSO → ALOJADO``: la guardia busca a la familia por DNI, acepta o
rechaza la derivación, confirma a cada persona con su ficha mínima y su cama, y cierra el
ingreso (N de N, o con diferencia). También el ingreso directo —la familia que llegó sola— y
el cierre del caso cuando egresa el último.

**Toda regla de la etapa se importa desde acá.** La pantalla E6 del backoffice
(``programas.views.emergencia_dispositivo``) y la API de la app (PR 8) llaman a estas mismas
funciones (RU-1, RU-2): por eso ninguna recibe un ``request`` ni lee la sesión, todas toman
argumentos por nombre y devuelven la fila recién leída con lo que hace falta para armar la
respuesta. Lo que se lee —mapa de camas, filas de la familia, llegadas— está en
``programas.selectors.emergencia_alojar``.

Este módulo es la **fachada**: el código vive en seis módulos, con las dependencias en un
solo sentido (``ficha`` e ``ingreso_comun`` abajo, ninguno importa a un hermano de su nivel)::

    emergencia_ficha            el Formulario 2: esquema, validador y aplanado (puro)
    emergencia_ingreso_comun    alcance, candados del caso y la derivación, filas, bitácora,
                                reserva de camas y acciones_del_ingreso (la regla de los cierres)
    emergencia_recepcion        buscar por DNI, aceptar y rechazar (M2-1, M2-2)
    emergencia_confirmacion     confirmar, completar la ficha y agregar (M2-3, M2-4)
    emergencia_cierre           alojar, cerrar con diferencia, cancelar y el egreso (M2-5, RN-3.12)
    emergencia_sin_derivacion   ingreso directo y aviso a la mesa (M2-6)

Se importa y se parcha **donde vive** cada cosa; desde acá se reexporta lo público.

Cómo está hecha cada función
----------------------------

1. **Alcance, antes de tocar nada** (RU-8, RU-9): ``puede_operar_dispositivo(usuario,
   dispositivo, "dispositivo.admitir")`` sobre el dispositivo **de la derivación**. Sin
   alcance, ``PermissionDenied`` y no se toma ni un candado: quien opera A no bloquea filas
   de una familia de B. La vista web lo traduce a 404 (plan C2) porque ya filtró antes; la
   API, igual.
2. Abre una transacción, **bloquea el caso y después la derivación** y decide con lo que lee
   de esas dos filas. Si ya no están como la acción necesita, :class:`EstadoCambio` (409):
   otra guardia, la mesa o el cron se adelantaron.
3. Deja ``TrazaCaso`` (RU-15) y, en aceptar, alojar y cerrar con diferencia, la novedad
   ``GENERAL`` automática de la bitácora del turno (RN-3.14). Sin turno vigente no se
   escribe y no es un error (plan R8): la traza del caso queda igual.

El orden de los candados
------------------------

El global del módulo (plan §8, R1)::

    caso → derivación → plazas (por pk) → reservas → persona

* El caso y la derivación los bloquea **este módulo**; ``estadias.py`` y
  ``reservas_derivacion.py`` no los bloquean ni los releen (contrato del PR 6). Sin JOIN, como
  en ``services.emergencia``.
* Las plazas, las reservas y la persona que ingresa los bloquean las funciones de
  ``estadias.py`` y ``reservas_derivacion.py``. Cuando una confirmación toca **varias** plazas
  —la cama libre que eligió la guardia, la de la reserva sobrante que devuelve y las de las
  reservas comunes de la persona que se cierran—, se piden todas de una vez ordenadas por
  pk, se liberan las reservas, se bloquea a la persona y recién entonces se ingresa: plaza →
  reserva → persona, nunca al revés.
* El alta mínima de la persona va **antes** de las plazas: un ``INSERT`` no espera a nadie
  que tenga algo nuestro, y si choca con el mismo DNI dado de alta a la vez, espera con solo
  el caso y la derivación tomados.
* Lo último son las altas que cuelgan de la persona ya bloqueada: el ``VinculoFamiliar`` y la
  fila del integrante. El vínculo toma, por la FK, un lock **compartido** sobre la fila del
  responsable; no se le pide el exclusivo a propósito (un egreso del responsable en curso
  no tiene que esperar a esta transacción, ni al revés).
* ``aceptar_derivacion`` **no reintenta** si una cama elegida se ocupó entre la foto y el
  candado: ``ROLLBACK TO SAVEPOINT`` no suelta los locks de fila en InnoDB, y pedir un
  segundo juego de plazas con el primero todavía tomado rompería «todas de una vez, por
  pk». Falla con un mensaje claro y la guardia vuelve a tocar «Aceptar».

El egreso (RN-3.12) y por qué no forma un ciclo
-----------------------------------------------

``al_egresar_estadia`` recibe ``estadia_egresada`` **dentro** de la transacción de
``estadias.egresar_persona``, que llega con la fila de la estadía bloqueada y con locks
compartidos sobre la plaza que deja (el ``INSERT`` del movimiento la referencia). Su orden
es, entonces, *estadía → caso → integrante*: el revés del módulo, que va del caso hacia las
plazas. No forma un ciclo porque **ninguna función de este módulo espera, con el caso
tomado, algo que un egreso tenga**:

* ninguna bloquea una ``Estadia`` que ya existe (``ingresar_persona`` solo inserta);
* las plazas que piden ``aceptar``, ``cerrar_con_diferencia``, ``cancelar_ingreso`` y
  ``alojar_familia`` son las de reservas **vigentes** o camas libres, y una plaza con una
  estadía activa no tiene ni una cosa ni la otra;
* ``confirmar_integrante`` es la única que recibe una plaza de afuera, y por eso **mira sin
  candado si está ocupada antes de pedirla**: mientras el egreso no commitea, la cama se lee
  ocupada y la confirmación se rechaza sin esperar; cuando commiteó, ya no tiene locks.
* el receptor bloquea el caso **antes** de escribir al integrante, igual que
  ``completar_ficha``: los dos piden caso → integrante.
* **La excepción conocida:** al confirmar en una cama libre, ``confirmar_integrante`` también
  bloquea las plazas de las reservas comunes de la persona, que salen de ``abiertas()`` y no de
  ``vigentes()``: una común con el ``hasta`` vencido y sin liberar puede estar sobre la cama de
  un familiar ya confirmado. Si ese familiar egresa en el mismo instante, el egreso (estadía →
  plaza compartida → caso) y la confirmación (caso → plaza) se esperan: ``ERROR 1213`` y una
  de las dos se deshace entera, sin dato a medias. Evitarlo pediría tocar ``liberar_reserva``
  de Dispositivos; hacen falta la misma familia, una reserva vencida sin liberar y un egreso
  simultáneo.

Para una estadía que no es de Emergencia el receptor hace **una** consulta y vuelve: está en
el camino de todos los egresos de Dispositivos.

La ficha individual (Formulario 2)
----------------------------------

Esquema fijo y versionado (decisión 6 del PM): ver ``programas.services.emergencia_ficha``.
"""

from programas.models import CasoEmergencia
from programas.services.emergencia_cierre import (  # noqa: F401
    MOTIVO_RESERVAS_AL_ALOJAR,
    MotivoDiferencia,
    al_egresar_estadia,
    alojar_familia,
    cancelar_ingreso,
    cerrar_con_diferencia,
    conectar_receptores,
)
from programas.services.emergencia_confirmacion import (  # noqa: F401
    ELEGI_UNA_CAMA,
    MOTIVO_RESERVA_SOBRANTE,
    SIN_CAMA_LIBRE,
    VINCULO_DE_PARENTESCO,
    PersonaYaAlojada,
    agregar_integrante,
    completar_ficha,
    confirmar_integrante,
)
from programas.services.emergencia_ficha import (  # noqa: F401
    BOOLEANO,
    CLAVES_DE_ENVIO,
    EDAD_SIN_ADULTO_RESPONSABLE,
    ESQUEMA_FICHA,
    FECHA,
    FICHA_VERSION,
    OPCION,
    PREGUNTAS_CRITICAS,
    ROTULO_DE_SECCION,
    SECCION_AVISOS,
    SECCION_DATOS,
    SECCION_EDUCACION,
    SECCION_OBSERVACIONES,
    SECCION_PARENTESCO,
    SECCION_SALUD,
    SECCION_TRABAJO,
    SECCION_VACUNACION,
    SECCIONES_MINIMAS,
    SECCIONES_OPCIONALES,
    SIN_DATOS,
    SIN_NUMERO_DE_DOCUMENTO,
    TEXTO,
    NivelEducativo,
    Parentesco,
    ficha_a_plano,
    ficha_desde_plano,
    ficha_esta_completa,
    ficha_minima_valida,
    normalizar_ficha,
    secciones_incompletas,
)
from programas.services.emergencia_ingreso_comun import (  # noqa: F401
    CAMAS_TOMADAS_MIENTRAS_ACEPTABA,
    CAP_ADMITIR,
    SIN_ALCANCE,
    acciones_del_ingreso,
    derivacion_vencida,
    ingreso_sin_candado,
    mensaje_faltan_confirmar,
    mensaje_vencida,
)
from programas.services.emergencia_recepcion import (  # noqa: F401
    BUSQUEDA_ALOJADA,
    BUSQUEDA_DERIVACION,
    BUSQUEDA_SIN_DERIVACION,
    SIN_DERIVACION,
    SIN_PLAZAS_PARA_ACEPTAR,
    MotivoRechazo,
    ResultadoAceptacion,
    ResultadoBusqueda,
    aceptar_derivacion,
    buscar_por_dni,
    rechazar_derivacion,
)
from programas.services.emergencia_sin_derivacion import (  # noqa: F401
    SIN_CAMAS_PARA_INGRESO_DIRECTO,
    avisar_a_la_mesa,
    es_ingreso_directo,
    ingreso_directo,
)

#: Las claves de ``CasoEmergencia.situacion`` que escribe la etapa. Viven en el modelo; se
#: reexportan para quien las leía desde acá.
SITUACION_ALOJAMIENTO = CasoEmergencia.SITUACION_ALOJAMIENTO
SITUACION_DIFERENCIA = CasoEmergencia.SITUACION_DIFERENCIA
SITUACION_EN_LA_PUERTA = CasoEmergencia.SITUACION_EN_LA_PUERTA
