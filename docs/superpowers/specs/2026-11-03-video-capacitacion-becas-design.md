# Video de capacitación de Becas — diseño

Fecha: 2026-11-03. Estado: aprobado en conversación, pendiente de plan.

## Objetivo

Un único video largo (estimado 70–90 min) que explique el módulo Becas completo:
los cinco roles, todas las pantallas y configuraciones del backoffice, la
inscripción pública por link, la app de campo, y una sección de errores
frecuentes con su solución. Las pantallas son las de la aplicación real,
grabadas en local con datos ficticios. Narración con voz neural en castellano
rioplatense.

Condición de aceptación: **no queda ninguna configuración, campo, acción,
mensaje ni estado del módulo sin mostrar.** Se verifica con un inventario
generado desde el código (ver §4), no con memoria.

## 1. Decisiones tomadas

| Tema | Decisión |
|---|---|
| Formato | Un solo video, con capítulos navegables en el MP4 y subtítulos `.srt`. |
| Audiencia | Todos los roles; cada cambio de rol se muestra cerrando sesión y entrando con el otro usuario. |
| Ambiente | Local (`docker compose up -d`, backoffice en `localhost:8000`), base de desarrollo sembrada con `seed_video_becas`. Nunca testing ni PRD: sin datos reales, errores provocables, regrabable. |
| App de campo | `Chaco-mobile` con `npm run web`, apuntando a la API local. Se graba en ventana 390×844 centrada sobre el lienzo 1920×1080. |
| Voz | `edge-tts`, voz `es-AR-ElenaNeural` (parámetro; alternativa `es-AR-TomasNeural`). El guion no contiene datos de personas. |
| Integraciones | RENAPER / Personas / SIIS en modo de prueba (`RENAPER_TEST_MODE` y equivalentes): se ven las pantallas funcionando sin tocar servicios reales. |
| Tiempos del sistema | Cron de las 03:10 y vencimientos se simulan corriendo el comando a mano; la narración lo dice. |
| Barra de direcciones | No aparece: se graba el contenido de la página. |
| Salida | El MP4 y los intermedios no se versionan; sí todo lo que permite regenerarlos. |

## 2. Estructura del video

| # | Capítulo | Rol que opera | Min (est.) |
|---|---|---|---|
| 0 | Qué es Becas y glosario (programa, segmento, subsegmento, convocatoria, relevamiento, caso, padrón, cupo) | — | 3 |
| 1 | Los 5 roles, qué ve cada uno, alcance por programa / por subsegmento; alta de usuario y asignación del rol | Administrador | 6 |
| 2 | Configuración del programa: segmentos, subsegmentos con cupo, requisitos, preguntas, coordinadores, identificadores SIIS, pausas | Administrador | 10 |
| 3 | Convocatorias: alta, fechas, constructor del formulario, padrón, cierre automático, reactivación | Coordinador | 8 |
| 4 | Relevamientos: territorial y público, zona, cupo propio, link público, finalizar, volver a campo, reprogramar, reasignar | Coordinador | 8 |
| 5 | Inscripción por link: paso 1, paso 2, comprobante, vista del ciudadano | Ciudadano | 5 |
| 6 | App de campo: ingreso, relevamientos asignados, iniciar, cargar persona, fotos, sin conexión, finalizar | Territorial | 10 |
| 7 | Revisión de casos: bandeja, identidad (RENAPER / padrón), aprobar, rechazar, terminar revisión, envío a SIIS | Coordinador | 10 |
| 8 | Cupo, lista de espera y beneficiarios: baja y promoción | Coordinador | 5 |
| 9 | Reportes y dashboard; qué cambia para Coordinador Regional y Referente | varios | 4 |
| 10 | Errores frecuentes y soluciones (cada uno provocado en pantalla) | varios | 8 |

Los minutos son estimaciones; la duración real la fija la cobertura (§4).
Lista inicial del capítulo 10, a completar con los mensajes reales del código:

- «Este formulario ya no admite inscripciones» (relevamiento vencido → volver a
  campo con fecha nueva; no apretar «Finalizar»).
- «Solo se puede relevar dentro del período asignado».
- DNI ya inscripto / fuera del padrón / cupo lleno.
- Relevamiento pausado por herencia (segmento o programa).
- Relevamiento que vuelve solo a «En revisión» por el cierre de las 03:10.
- Usuario que no ve un menú por falta de capacidad.
- Sesión cerrada por abrir en otra computadora; cambio de contraseña obligatorio.

## 3. Escenario de datos: `seed_video_becas`

Comando en `programas/management/commands/seed_video_becas.py`, con la misma
guarda que los seeds demo existentes (`exigir_entorno_demo`). Reutiliza
`seed_becas` para el programa y los roles. Deja:

- Un usuario por rol, con nombre ficticio y clave conocida: `admin.becas`,
  `coordinador`, `coord.regional`, `referente`, `territorial`.
- Programa BECAS con dos segmentos: uno con subsegmentos y cupo repartido, otro
  sin subsegmentos.
- Convocatorias: vigente con padrón; vigente sin padrón (link abierto); cerrada
  automáticamente por fecha; pausada por herencia del segmento.
- Relevamientos en cada estado: asignado, en curso, finalizado, en revisión,
  terminado; uno vencido; uno con cupo lleno; público y territorial.
- Casos en cada estado: enviado, aprobado, rechazado, baja, lista de espera;
  uno con identidad sin validar; uno marcado fallecido en el padrón.
- Padrón de ~30 personas ficticias con DNIs de un rango que no existe.

Es idempotente: se puede volver a correr antes de regrabar.

## 4. Inventario de cobertura

`scripts/video_becas/inventario.py` genera desde el código la lista de ítems que
el video tiene que mostrar y reporta los que no tienen escena asignada:

- Pantallas: todas las URLs del namespace `becas`, las del portal público de
  inscripción y las pantallas de la app.
- Campos: cada campo de cada form de `programas/forms/` (y del portal), con sus
  opciones y texto de ayuda.
- Acciones: cada botón / `data-confirm-*` / form de acción de cada template, con
  su confirmación.
- Mensajes: cada `messages.*`, `ValidationError`, `_error(...)` y texto de
  template de estado vacío / no disponible.
- Estados y transiciones de convocatoria, relevamiento y caso, incluidas las del
  cron (`procesar_vencimientos`).
- Decisiones de `requerimientos.md` que explican comportamientos no obvios
  (consultadas por etiqueta con `scripts/requerimientos.py`).

Cada escena declara los ítems que cubre; el chequeo tiene que dar **0 sin cubrir**
para dar el video por terminado.

## 5. Pipeline

```
scripts/video_becas/            ← export-ignore (.gitattributes)
  inventario.py                 ← §4
  guion/NN-capitulo.md          ← narración por escena, legible por una persona
  escenas/NN-capitulo.js        ← Playwright (Node): pasos {narración, acciones, cubre:[ítems]}
  lib/                          ← cursor visible, resaltado, tipeo humano, carteles, voz, sincronía
  armar.ps1                     ← seed → grabar → voz → unir → MP4 + .srt
  package.json                  ← Playwright propio; no toca el package.json de la raíz
  salida/                       ← gitignored: .webm, .mp3, .mp4
```

Flujo por escena: para cada paso se genera el audio (edge-tts → mp3 + duración),
se ejecutan las acciones con un cursor visible y resaltado del elemento nombrado,
y el paso dura `max(audio, acciones)`: la voz nunca habla de algo que no se ve.
Playwright graba cada escena a 1920×1080 (`recordVideo`). `ffmpeg` concatena,
inserta el cartel de capítulo (HTML renderizado por Playwright), escribe los
capítulos como metadata del MP4 y genera el `.srt` desde el guion.

Herramientas a instalar (avisar antes de cada una): `ffmpeg` (winget),
`edge-tts` (venv aparte, no entra a `requirements.txt`), Playwright para Node en
`scripts/video_becas/`.

## 6. Orden de trabajo

1. Inventario (§4) y seed (§3). El inventario se corre primero: su tamaño fija el
   guion.
2. Guion completo, capítulo por capítulo, revisado por el PM antes de grabar.
3. Infraestructura de grabación (`lib/`, `armar.ps1`) probada con una escena corta.
4. Grabación capítulo por capítulo; cada capítulo se revisa aislado.
5. Cierre: inventario en 0, video completo revisado contra el guion, entrada en
   `docs/internal/requerimientos.md`.

## 7. Riesgos

- El video se vuelve viejo cuando cambia una pantalla: por eso todo es
  regenerable por escena.
- La app de campo en web puede diferir levemente de la nativa (cámara, GPS): se
  narra la diferencia donde aplique.
- `edge-tts` depende de un servicio externo gratuito sin garantía; si deja de
  andar, la alternativa es grabar la narración con el guion ya escrito.
