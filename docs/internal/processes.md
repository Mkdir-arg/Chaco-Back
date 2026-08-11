# Procesos internos

## Deploy a producción

```bash
# 1. Asegurarse de estar en main actualizado
git checkout main
git pull origin main

# 2. Ejecutar script de deploy
./scripts/deploy_prod.sh
```

El script `deploy_prod.sh` realiza:
1. Build de la imagen Docker
2. Push al registry
3. Restart del servicio en el servidor

### Checklist pre-deploy

- [ ] Tests pasando en CI
- [ ] Migraciones revisadas (sin operaciones destructivas sin respaldo)
- [ ] Variables de entorno de producción actualizadas si hubo cambios
- [ ] Notificar al equipo en el canal correspondiente

## Cron del host (icore-srv)

Hay trabajo periódico que **no** corre dentro de la app: lo dispara el cron del
usuario `icore` en el host, siempre con el mismo patrón —
`docker exec chaco-web-1 python manage.py <comando>` y log en `~/cron-chaco.log`.

Los snippets están versionados en [`docker/cron/`](../../docker/cron/), con la
explicación de cada uno en su cabecera. Se instalan **una sola vez** por servidor:
no viajan con el deploy, así que un servidor nuevo (o un `crontab` que se pierda)
los necesita de nuevo a mano.

| Comando | Horario | Qué pasa si no corre |
|---|---|---|
| `generar_alertas` | horario | No se generan las alertas de legajos |
| `procesar_vencimientos` | 03:10 | Convocatorias vencidas quedan abiertas y sus relevamientos no pasan a revisión |
| `limpiar_alertas_conversaciones` | 03:30 | Se acumulan alertas de conversaciones ya resueltas |
| `sincronizar_programas_siis` | 04:00 | **Una baja de programa en SIIS no se detecta**: el segmento sigue operando como si el programa estuviera vigente |

Instalación:

```bash
# En el host, como usuario icore (NUNCA con sudo su: la sesión de docker/git es de icore)
crontab -e
# pegar las líneas de los .cron de docker/cron/, y verificar:
crontab -l
```

### Al agregar un comando periódico nuevo

1. Versionar el snippet en `docker/cron/<comando>.cron` con su cabecera explicativa.
2. Sumarlo a la tabla de arriba.
3. Instalarlo en el host (paso manual, no lo hace el deploy).

**No** lo agregues a `LOCAL_OPTIONAL_BOOTSTRAP_COMMANDS` de `docker-compose.prod.yml`
salvo que el comando no pueda fallar. El `docker-entrypoint.sh` corre con `set -eu`
y sin tolerancia a fallos, así que un comando de bootstrap que termine con error
**deja el contenedor sin arrancar**. Ese es el motivo por el que
`procesar_vencimientos` (puro trabajo local sobre la base) sí está en el bootstrap
y `sincronizar_programas_siis` (depende de un servicio externo) no: una caída de
ECOM tiraría abajo el arranque de `web`.

## Rollback

Si el deploy falla o hay un error crítico en producción:

```bash
# Volver a la imagen anterior
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d --no-build
# (ajustar tag de imagen según el caso)
```

Para rollback de migraciones:
```bash
docker compose exec django python manage.py migrate <app> <migration_anterior>
```

## Gestión de incidentes

### Severidades

| Nivel | Descripción | Tiempo de respuesta |
|---|---|---|
| P1 | Sistema caído o datos comprometidos | Inmediato |
| P2 | Funcionalidad crítica degradada | < 2 horas |
| P3 | Bug con workaround disponible | Próximo sprint |

### Pasos ante un incidente P1/P2

1. Notificar en el canal del equipo con descripción del problema
2. Revisar logs: `docker compose logs -f django`
3. Evaluar rollback si el problema es post-deploy
4. Abrir issue en GitHub con label `incident` documentando causa y resolución

## Gestión de migraciones en producción

- Siempre hacer backup de la base antes de migraciones que alteran tablas grandes
- Migraciones con `ALTER TABLE` en tablas > 100k filas deben planificarse en horario de bajo tráfico
- Usar `--fake` solo si se está seguro de que el esquema ya está aplicado manualmente
