---
name: auditoria-pre-release
description: Auditoría de preparación para producción de Chaco con evidencia local — qué puede romper en ECOM (MariaDB, WAF, sin tablas de timezone), migraciones y reversa, autorización, datos personales, operación — con un puntaje y una recomendación de salir o frenar. Usala antes de /pushGitLabecomTEST o /pushGitLabecomPRD, después de un merge grande, o cuando pregunten "¿está listo para producción?" o "¿qué rompe en prod?".
---

# Auditoría pre-release

Adaptada de la skill `production-audit` de [ECC](https://github.com/affaan-m/ECC)
(MIT, © 2026 Affaan Mustafa), con los riesgos reales de llevar Chaco a ECOM.

No reemplaza al `release-gate` ni a los pasos de `docs/internal/espejo-ecom.md`: los
complementa con la pregunta que el CI no contesta, **qué rompe en producción aunque todo
esté verde**. Es triage de ingeniería, no una certificación.

## Reglas

- Solo evidencia local o autorizada: checkout, PRs, corridas del CI, el ambiente que diga
  el usuario. No se sube código ni datos a servicios externos, ni se corre un escáner
  remoto sin aprobación explícita.
- Contra un ambiente real (DEV/QA/PRD) solo lecturas, y preguntando antes de escribir
  nada. PRD no se toca para auditar.
- Ningún dato personal del padrón en la respuesta ni en un archivo del repo.

## Orden

1. **Superficie del release.** Qué SHA de `main` se va a espejar y desde qué release viene.
   ```text
   git log --oneline --decorate -20 origin/main
   git diff --stat <ecom/test>..origin/main
   ```
   Mirar también `publish-main.yml`: un check rojo "no bloqueante" congela `main` en silencio.
2. **Migraciones.** Listar las nuevas respecto del ambiente destino. Para cada una:
   ¿cumple `scripts/check_migraciones.py`? ¿Entra en las del paso D.4 de
   `docs/internal/processes.md` (sin vuelta salvo restore)? ¿Hay backup previsto?
3. **Bordes del sistema** que el diff toca de verdad: autorización, `/api/` de la app
   móvil, inscripción pública por token, integraciones, cron, `media/`.
4. **CI y release-gate** del SHA exacto, no de un SHA vecino.
5. **Recomendación** con puntaje, bloqueantes y una próxima acción.

## Lentes de riesgo

### Motor y ambiente (lo que más rompe solo en ECOM)

- ¿Algún `Trunc*` nuevo sobre un `DateTimeField`? En ECOM da `NULL` (sin tablas de timezone).
- ¿`UUIDField` nuevo sin su migración a `char(36)`, o un lookup por UUID sin `q_uuid_en_texto`?
- ¿`UniqueConstraint(condition=…)` usada como regla de negocio? En MariaDB no existe.
- ¿Consultas nuevas que puedan pasar los 10 s de `read_timeout` con el volumen de PRD?
- ¿Ruta nueva expuesta a internet? El WAF de ECOM bloquea rutas nuevas desde afuera.
- ¿Variable de entorno, cron o servicio nuevo? Tiene que estar en `processes.md` y avisado.

### Autorización y separación de superficies

- ¿Cada vista nueva autoriza por capacidad (`@requiere`, `puede`) y del lado del servidor?
- ¿Respeta el alcance por programa y el territorial? ¿Un rol de otro programa no habilita?
- ¿El ciudadano sigue sin poder salir de `/portal/` (`PortalCiudadanoMiddleware`)?
- ¿Los archivos nuevos se sirven por `media_protegida` y no por una URL abierta?

### Integridad de datos

- ¿Las migraciones de datos tienen reversa declarada o `# REVERSA-NOOP:` con el motivo?
- ¿Los rellenos van por lotes? ¿El DDL partido puede dejar la base a mitad?
- ¿Las escrituras que se reintentan (envíos, sincronización con SIIS, altas) son idempotentes?
- ¿Las cargas y drenajes masivos van por páginas, no todo en una transacción?

### Operación

- ¿Arranca desde cero con el entrypoint (migraciones, `collectstatic` con manifest, seed)?
- ¿`/health/` sigue probando lo que importa?
- ¿El CSS de Tailwind compilado está commiteado?
- ¿Los logs nuevos no imprimen DNI, CUIL, correos ni tokens?
- ¿Está escrito cómo se vuelve atrás (entrada del registro, sección *Reversión*)?

### Usuarios

- ¿Los caminos críticos del cambio se probaron en testing (`datanach.ecomdev.ar`) con
  sus casos de QA?
- ¿Los estados vacío, error y sin permiso le dicen a la persona qué pasó?

## Puntaje

El número fuerza a priorizar; no es una medición.

| Banda | Puntaje | Significa |
|---|---|---|
| Frenar | 0-49 | No sale hasta arreglar los riesgos principales |
| Riesgoso | 50-69 | Solo a testing, no a PRD |
| Sale con reservas | 70-84 | Sale si el PM acepta los riesgos listados |
| Firme | 85-100 | Sin bloqueantes visibles con la evidencia disponible |

**Tope 69** si: falta autorización del lado del servidor sobre datos sensibles; hay una
migración sin vuelta sin backup previsto; hay datos personales en logs o en el repo; no
hay camino de reversa para un cambio de alto impacto; o aparece una de las trampas de
motor de arriba.

**Tope 84** si el CI o el release-gate del SHA no están en verde, o el camino crítico no
se probó en testing.

## Salida

Una oración primero:

```text
Pre-release: 72/100, sale con reservas: programas.00NN es barrera de reversa (requiere backup) y la exportación nueva no se probó en testing.
```

Después:

- **Bloqueantes:** lo que se arregla antes de espejar.
- **Arreglos que suben el puntaje:** los siguientes, en orden.
- **Evidencia revisada:** archivos, comandos, corridas del CI, PRs.
- **Evidencia faltante:** qué cambiaría la confianza.
- **Próxima acción:** una sola, concreta.

## Antipatrones

- Tratar el CI verde como "listo para producción".
- Dar un puntaje sin nombrar la evidencia.
- Correr `npx paquete@latest` o un escáner remoto como camino por defecto.
- Cerrar con un "decime qué querés hacer" genérico.
