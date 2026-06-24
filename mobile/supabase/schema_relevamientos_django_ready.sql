-- Prototipo Supabase para Relevamiento Chaco.
-- Objetivo: probar el flujo mobile antes de migrar auth/datos a Django.
-- Ejecutar en Supabase SQL Editor.

create extension if not exists pgcrypto;

-- =========================================
-- 1) Usuarios de prueba para login mobile
-- =========================================
create table if not exists public.grupos (
  id uuid primary key default gen_random_uuid(),
  nombre text not null unique,
  descripcion text,
  created_at timestamptz not null default now()
);

create table if not exists public.usuarios (
  id uuid primary key default gen_random_uuid(),
  username text not null unique,
  password text not null,
  nombre text not null,
  foto text,
  es_admin boolean not null default false,
  activo boolean not null default true,
  django_user_id bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.usuario_grupos (
  usuario_id uuid not null references public.usuarios(id) on delete cascade,
  grupo_id uuid not null references public.grupos(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (usuario_id, grupo_id)
);

-- =========================================
-- 2) Plantillas y campos dinamicos
-- =========================================
create table if not exists public.relevamiento_plantillas (
  id uuid primary key default gen_random_uuid(),
  nombre text not null,
  descripcion text,
  version integer not null default 1,
  activa boolean not null default true,
  django_template_id bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.relevamiento_campos (
  id uuid primary key default gen_random_uuid(),
  plantilla_id uuid not null references public.relevamiento_plantillas(id) on delete cascade,
  clave text not null,
  etiqueta text not null,
  tipo text not null check (tipo in ('texto', 'textarea', 'numero', 'fecha', 'booleano', 'select', 'choice', 'archivo')),
  orden integer not null default 1,
  requerido boolean not null default false,
  opciones jsonb not null default '[]'::jsonb,
  validaciones jsonb not null default '{}'::jsonb,
  ayuda text,
  activo boolean not null default true,
  django_field_id bigint,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (plantilla_id, clave)
);

create index if not exists idx_relevamiento_campos_plantilla
on public.relevamiento_campos(plantilla_id, orden);

-- =========================================
-- 3) Relevamientos asignados al relevador
-- =========================================
create table if not exists public.relevamientos_asignados (
  id uuid primary key default gen_random_uuid(),
  client_uid uuid not null unique default gen_random_uuid(),
  plantilla_id uuid references public.relevamiento_plantillas(id),
  assigned_user_id uuid references public.usuarios(id),
  django_relevamiento_id bigint,

  titulo text not null default 'Relevamiento',
  descripcion text,
  estado text not null default 'ASIGNADO'
    check (estado in ('ASIGNADO', 'DESCARGADO', 'EN_PROGRESO', 'COMPLETADO_LOCAL', 'SINCRONIZANDO', 'SINCRONIZADO', 'ERROR')),
  prioridad text not null default 'MEDIA'
    check (prioridad in ('BAJA', 'MEDIA', 'ALTA')),

  -- Direccion que recibe el relevador para ir al domicilio.
  direccion_objetivo text not null,
  localidad text,
  provincia text not null default 'Chaco',
  latitud_objetivo numeric(10, 7),
  longitud_objetivo numeric(10, 7),
  radio_permitido_metros integer not null default 250,

  -- Geolocalizacion capturada al completar. No se muestra en UI mobile.
  latitud_capturada numeric(10, 7),
  longitud_capturada numeric(10, 7),
  precision_metros numeric(10, 2),

  observaciones text,
  asignado_at timestamptz not null default now(),
  descargado_at timestamptz,
  iniciado_at timestamptz,
  completado_at timestamptz,
  last_synced_at timestamptz,
  sync_error text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create index if not exists idx_relevamientos_assigned_user
on public.relevamientos_asignados(assigned_user_id, estado);

create index if not exists idx_relevamientos_estado
on public.relevamientos_asignados(estado);

-- =========================================
-- 4) Datos DNI + validacion RENAPER
-- =========================================
create table if not exists public.relevamiento_personas (
  id uuid primary key default gen_random_uuid(),
  relevamiento_id uuid not null unique references public.relevamientos_asignados(id) on delete cascade,

  dni_numero text not null,
  dni_sexo text check (dni_sexo in ('M', 'F', 'X')),
  dni_tramite text,
  apellido text,
  nombres text,
  cuil text,
  fecha_nacimiento date,
  nacionalidad text,
  ejemplar text,
  vencimiento_dni date,

  domicilio_calle text,
  domicilio_numero text,
  domicilio_piso text,
  domicilio_departamento text,
  domicilio_barrio text,
  domicilio_ciudad text,
  domicilio_municipio text,
  domicilio_provincia text,
  codigo_postal text,

  renaper_estado text not null default 'PENDIENTE'
    check (renaper_estado in ('PENDIENTE', 'VALIDADO', 'NO_VALIDADO', 'ERROR')),
  renaper_validado_at timestamptz,
  renaper_respuesta jsonb not null default '{}'::jsonb,
  renaper_error text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_relevamiento_personas_dni
on public.relevamiento_personas(dni_numero);

-- =========================================
-- 5) Respuestas dinamicas
-- =========================================
create table if not exists public.relevamiento_respuestas (
  id uuid primary key default gen_random_uuid(),
  relevamiento_id uuid not null references public.relevamientos_asignados(id) on delete cascade,
  campo_id uuid not null references public.relevamiento_campos(id),
  valor_texto text,
  valor_numero numeric,
  valor_booleano boolean,
  valor_fecha date,
  valor_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (relevamiento_id, campo_id)
);

create index if not exists idx_relevamiento_respuestas_relevamiento
on public.relevamiento_respuestas(relevamiento_id);

-- =========================================
-- 6) Adjuntos: DNI frente/dorso, archivos dinamicos y evidencia
-- =========================================
create table if not exists public.relevamiento_archivos (
  id uuid primary key default gen_random_uuid(),
  relevamiento_id uuid not null references public.relevamientos_asignados(id) on delete cascade,
  campo_id uuid references public.relevamiento_campos(id),
  categoria text not null check (categoria in ('DNI_FRENTE', 'DNI_DORSO', 'CAMPO_ARCHIVO', 'EVIDENCIA')),
  storage_bucket text not null default 'relevamientos',
  storage_path text not null,
  nombre_original text,
  mime_type text,
  size_bytes bigint,
  checksum text,
  subido_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists ux_relevamiento_dni_frente
on public.relevamiento_archivos(relevamiento_id)
where categoria = 'DNI_FRENTE';

create unique index if not exists ux_relevamiento_dni_dorso
on public.relevamiento_archivos(relevamiento_id)
where categoria = 'DNI_DORSO';

create index if not exists idx_relevamiento_adjuntos_relevamiento
on public.relevamiento_archivos(relevamiento_id);

-- =========================================
-- 7) Outbox/sync server-side para auditoria de pruebas
-- =========================================
create table if not exists public.relevamiento_sync_eventos (
  id uuid primary key default gen_random_uuid(),
  relevamiento_id uuid references public.relevamientos_asignados(id) on delete cascade,
  usuario_id uuid references public.usuarios(id),
  client_uid uuid,
  evento text not null check (evento in ('DESCARGADO', 'GUARDADO_LOCAL', 'SYNC_INTENTO', 'SYNC_OK', 'SYNC_ERROR')),
  detalle jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_relevamiento_sync_eventos_relevamiento
on public.relevamiento_sync_eventos(relevamiento_id, created_at desc);

-- =========================================
-- 8) updated_at
-- =========================================
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists usuarios_set_updated_at on public.usuarios;
create trigger usuarios_set_updated_at
before update on public.usuarios
for each row execute function public.set_updated_at();

drop trigger if exists plantillas_set_updated_at on public.relevamiento_plantillas;
create trigger plantillas_set_updated_at
before update on public.relevamiento_plantillas
for each row execute function public.set_updated_at();

drop trigger if exists campos_set_updated_at on public.relevamiento_campos;
create trigger campos_set_updated_at
before update on public.relevamiento_campos
for each row execute function public.set_updated_at();

drop trigger if exists relevamientos_asignados_set_updated_at on public.relevamientos_asignados;
create trigger relevamientos_asignados_set_updated_at
before update on public.relevamientos_asignados
for each row execute function public.set_updated_at();

drop trigger if exists personas_set_updated_at on public.relevamiento_personas;
create trigger personas_set_updated_at
before update on public.relevamiento_personas
for each row execute function public.set_updated_at();

drop trigger if exists respuestas_set_updated_at on public.relevamiento_respuestas;
create trigger respuestas_set_updated_at
before update on public.relevamiento_respuestas
for each row execute function public.set_updated_at();

drop trigger if exists archivos_set_updated_at on public.relevamiento_archivos;
create trigger archivos_set_updated_at
before update on public.relevamiento_archivos
for each row execute function public.set_updated_at();

-- =========================================
-- 9) RLS abierta para desarrollo mobile con anon key.
-- Ajustar antes de produccion o al pasar a API Django.
-- =========================================
alter table public.grupos enable row level security;
alter table public.usuarios enable row level security;
alter table public.usuario_grupos enable row level security;
alter table public.relevamiento_plantillas enable row level security;
alter table public.relevamiento_campos enable row level security;
alter table public.relevamientos_asignados enable row level security;
alter table public.relevamiento_personas enable row level security;
alter table public.relevamiento_respuestas enable row level security;
alter table public.relevamiento_archivos enable row level security;
alter table public.relevamiento_sync_eventos enable row level security;

drop policy if exists grupos_all_dev on public.grupos;
create policy grupos_all_dev on public.grupos for all to anon, authenticated using (true) with check (true);

drop policy if exists usuarios_all_dev on public.usuarios;
create policy usuarios_all_dev on public.usuarios for all to anon, authenticated using (true) with check (true);

drop policy if exists usuario_grupos_all_dev on public.usuario_grupos;
create policy usuario_grupos_all_dev on public.usuario_grupos for all to anon, authenticated using (true) with check (true);

drop policy if exists plantillas_all_dev on public.relevamiento_plantillas;
create policy plantillas_all_dev on public.relevamiento_plantillas for all to anon, authenticated using (true) with check (true);

drop policy if exists campos_all_dev on public.relevamiento_campos;
create policy campos_all_dev on public.relevamiento_campos for all to anon, authenticated using (true) with check (true);

drop policy if exists relevamientos_all_dev on public.relevamientos_asignados;
create policy relevamientos_all_dev on public.relevamientos_asignados for all to anon, authenticated using (true) with check (true);

drop policy if exists personas_all_dev on public.relevamiento_personas;
create policy personas_all_dev on public.relevamiento_personas for all to anon, authenticated using (true) with check (true);

drop policy if exists respuestas_all_dev on public.relevamiento_respuestas;
create policy respuestas_all_dev on public.relevamiento_respuestas for all to anon, authenticated using (true) with check (true);

drop policy if exists archivos_all_dev on public.relevamiento_archivos;
create policy archivos_all_dev on public.relevamiento_archivos for all to anon, authenticated using (true) with check (true);

drop policy if exists sync_eventos_all_dev on public.relevamiento_sync_eventos;
create policy sync_eventos_all_dev on public.relevamiento_sync_eventos for all to anon, authenticated using (true) with check (true);

-- =========================================
-- 10) Storage
-- =========================================
insert into storage.buckets (id, name, public)
values ('relevamientos', 'relevamientos', false)
on conflict (id) do nothing;

drop policy if exists relevamientos_storage_select on storage.objects;
create policy relevamientos_storage_select on storage.objects
for select to anon, authenticated
using (bucket_id = 'relevamientos');

drop policy if exists relevamientos_storage_insert on storage.objects;
create policy relevamientos_storage_insert on storage.objects
for insert to anon, authenticated
with check (bucket_id = 'relevamientos');

drop policy if exists relevamientos_storage_update on storage.objects;
create policy relevamientos_storage_update on storage.objects
for update to anon, authenticated
using (bucket_id = 'relevamientos')
with check (bucket_id = 'relevamientos');

-- =========================================
-- 11) Datos demo
-- Login demo: relevador.demo / 123456
-- =========================================
insert into public.grupos (id, nombre, descripcion)
values
  ('11111111-1111-4111-8111-111111111111', 'Relevador', 'Usuario mobile que completa relevamientos en territorio'),
  ('22222222-2222-4222-8222-222222222222', 'Administrador', 'Usuario administrador de prueba')
on conflict (id) do nothing;

insert into public.usuarios (id, username, password, nombre, es_admin, activo)
values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'relevador.demo', '123456', 'Relevador Demo', false, true),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'admin.demo', '123456', 'Admin Demo', true, true)
on conflict (id) do nothing;

insert into public.usuario_grupos (usuario_id, grupo_id)
values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111'),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '22222222-2222-4222-8222-222222222222')
on conflict do nothing;

insert into public.relevamiento_plantillas (id, nombre, descripcion, version, activa)
values (
  'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  'Relevamiento DNI + campos dinamicos',
  'Plantilla demo con DNI obligatorio, validacion RENAPER y campos configurables.',
  1,
  true
)
on conflict (id) do nothing;

insert into public.relevamiento_campos
  (id, plantilla_id, clave, etiqueta, tipo, orden, requerido, opciones, validaciones, ayuda)
values
  ('d0000001-0000-4000-8000-000000000001', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'observacion_social', 'Observacion social', 'textarea', 1, false, '[]', '{}', null),
  ('d0000001-0000-4000-8000-000000000002', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'situacion_vivienda', 'Situacion de vivienda', 'select', 2, true, '["Propia","Alquilada","Cedida","Situacion de calle","Otra"]', '{}', null),
  ('d0000001-0000-4000-8000-000000000003', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'requiere_asistencia', 'Requiere asistencia inmediata', 'choice', 3, true, '["Si","No"]', '{}', null),
  ('d0000001-0000-4000-8000-000000000004', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'documentacion_extra', 'Documentacion adicional', 'archivo', 4, false, '[]', '{"max_files":3,"mime_types":["image/jpeg","image/png","application/pdf"]}', null)
on conflict (id) do nothing;

insert into public.relevamientos_asignados
  (id, client_uid, plantilla_id, assigned_user_id, titulo, descripcion, direccion_objetivo, localidad, latitud_objetivo, longitud_objetivo, prioridad)
values (
  'eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee',
  'eeeeeeee-0000-4000-8000-eeeeeeeeeeee',
  'cccccccc-cccc-4ccc-8ccc-cccccccccccc',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'Relevamiento demo - DNI obligatorio',
  'Caso demo para probar descarga offline, DNI frente/dorso, RENAPER, geolocalizacion y sincronizacion.',
  'Av. 9 de Julio 145, Resistencia',
  'Resistencia',
  -27.4514000,
  -58.9867000,
  'MEDIA'
)
on conflict (id) do nothing;
