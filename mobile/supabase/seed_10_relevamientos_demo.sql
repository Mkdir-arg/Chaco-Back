-- Seed de 10 relevamientos demo para el usuario relevador.demo.
-- Ejecutar despues de schema_relevamientos_django_ready.sql.

insert into public.relevamientos_asignados
  (
    id,
    client_uid,
    plantilla_id,
    assigned_user_id,
    titulo,
    descripcion,
    direccion_objetivo,
    localidad,
    latitud_objetivo,
    longitud_objetivo,
    prioridad,
    estado
  )
select
  seed.id::uuid,
  seed.client_uid::uuid,
  p.id,
  u.id,
  seed.titulo,
  seed.descripcion,
  seed.direccion_objetivo,
  seed.localidad,
  seed.latitud_objetivo,
  seed.longitud_objetivo,
  seed.prioridad,
  'ASIGNADO'
from (
  values
    ('10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 'Relevamiento Barrio Centro', 'DNI obligatorio, campos dinamicos y geolocalizacion en domicilio.', 'Av. Alberdi 150, Resistencia', 'Resistencia', -27.4521000, -58.9869000, 'MEDIA'),
    ('10000000-0000-4000-8000-000000000002', '20000000-0000-4000-8000-000000000002', 'Relevamiento Villa Rio Negro', 'Validar datos de DNI y completar situacion habitacional.', 'Calle 7 y Pasaje 3, Resistencia', 'Resistencia', -27.4308000, -58.9972000, 'ALTA'),
    ('10000000-0000-4000-8000-000000000003', '20000000-0000-4000-8000-000000000003', 'Relevamiento Fontana Norte', 'Caso asignado para prueba offline con adjuntos obligatorios.', 'Av. 25 de Mayo 3200, Fontana', 'Fontana', -27.4189000, -59.0331000, 'MEDIA'),
    ('10000000-0000-4000-8000-000000000004', '20000000-0000-4000-8000-000000000004', 'Relevamiento Barranqueras', 'Completar datos RENAPER y documentacion del DNI.', 'Av. San Martin 890, Barranqueras', 'Barranqueras', -27.4825000, -58.9394000, 'BAJA'),
    ('10000000-0000-4000-8000-000000000005', '20000000-0000-4000-8000-000000000005', 'Relevamiento Puerto Vilelas', 'Prueba de formulario dinamico con archivos adicionales.', 'Calle Formosa 245, Puerto Vilelas', 'Puerto Vilelas', -27.5112000, -58.9479000, 'MEDIA'),
    ('10000000-0000-4000-8000-000000000006', '20000000-0000-4000-8000-000000000006', 'Relevamiento Villa Prosperidad', 'Caso para validar carga sin internet y sync posterior.', 'Av. Hernandarias 1850, Resistencia', 'Resistencia', -27.4637000, -58.9711000, 'ALTA'),
    ('10000000-0000-4000-8000-000000000007', '20000000-0000-4000-8000-000000000007', 'Relevamiento Villa Libertad', 'Completar DNI frente/dorso, campos choice y select.', 'Av. Edison 1200, Resistencia', 'Resistencia', -27.4754000, -58.9956000, 'MEDIA'),
    ('10000000-0000-4000-8000-000000000008', '20000000-0000-4000-8000-000000000008', 'Relevamiento Don Bosco', 'Asignacion demo para listado mobile del relevador.', 'Calle Don Bosco 540, Resistencia', 'Resistencia', -27.4463000, -58.9778000, 'BAJA'),
    ('10000000-0000-4000-8000-000000000009', '20000000-0000-4000-8000-000000000009', 'Relevamiento Villa Chica', 'Caso con prioridad alta para validar filtros.', 'Calle Obligado 2100, Resistencia', 'Resistencia', -27.4568000, -58.9635000, 'ALTA'),
    ('10000000-0000-4000-8000-000000000010', '20000000-0000-4000-8000-000000000010', 'Relevamiento Sameep', 'Prueba integral de direccion objetivo y sync.', 'Av. Sarmiento 1750, Resistencia', 'Resistencia', -27.4386000, -58.9832000, 'MEDIA')
) as seed(id, client_uid, titulo, descripcion, direccion_objetivo, localidad, latitud_objetivo, longitud_objetivo, prioridad)
join public.usuarios u on u.username = 'relevador.demo'
join public.relevamiento_plantillas p on p.nombre = 'Relevamiento DNI + campos dinamicos' and p.activa = true
on conflict (id) do update set
  assigned_user_id = excluded.assigned_user_id,
  plantilla_id = excluded.plantilla_id,
  titulo = excluded.titulo,
  descripcion = excluded.descripcion,
  direccion_objetivo = excluded.direccion_objetivo,
  localidad = excluded.localidad,
  latitud_objetivo = excluded.latitud_objetivo,
  longitud_objetivo = excluded.longitud_objetivo,
  prioridad = excluded.prioridad,
  estado = excluded.estado,
  updated_at = now();
