import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';
import * as FileSystem from 'expo-file-system/legacy';
import * as SQLite from 'expo-sqlite';
import * as SecureStore from 'expo-secure-store';
import { decode as decodeBase64 } from 'base64-arraybuffer';
import { Platform } from 'react-native';
import { supabase } from '../config/supabaseConfig';
import { SUPABASE_CONFIG } from '../config/supabaseConfig';

const LOCAL_RELEVAMIENTOS_KEY = 'field_relevamientos_records';
const SYNC_QUEUE_KEY = 'field_relevamientos_sync_queue';
const TABLE_RELEVAMIENTOS = 'relevamientos';
const TABLE_RELEVAMIENTOS_ASIGNADOS = 'relevamientos_asignados';
const TABLE_RELEVAMIENTO_PERSONAS = 'relevamiento_personas';
const TABLE_RELEVAMIENTO_RESPUESTAS = 'relevamiento_respuestas';
const TABLE_RELEVAMIENTO_ARCHIVOS = 'relevamiento_archivos';
const TABLE_CAMPOS_EXTRA = 'relevamiento_campos_extra';
const TABLE_ADJUNTOS = 'relevamiento_adjuntos';
const USER_ID_STORAGE_KEY = 'user_id';
const SQLITE_DB_NAME = 'relevamientos_offline.db';
const SQLITE_LOCAL_TABLE = 'local_relevamientos';
const SQLITE_OUTBOX_TABLE = 'outbox_relevamientos';
const SQLITE_META_TABLE = 'sync_metadata';
const SQLITE_MIGRATION_FLAG_KEY = 'field_relevamientos_sqlite_migrated_v1';
const ATTACHMENTS_DIR = `${FileSystem.documentDirectory}attachments`;
const MAX_RETRY_COUNT = 8;
const OUTBOX_IN_FLIGHT_TIMEOUT_MS = 10 * 60 * 1000;
const ERROR_MISSING_LOCAL_FILE = 'ERROR_MISSING_LOCAL_FILE';
const ERROR_OFFLINE = 'ERROR_OFFLINE';
const ERROR_ATTACHMENTS_UPLOAD = 'ERROR_ATTACHMENTS_UPLOAD';
const ERROR_REMOTE_SCHEMA = 'ERROR_REMOTE_SCHEMA';

let syncInFlightPromise = null;
let sqliteDbPromise = null;
let sqliteInitPromise = null;

const nowIso = () => new Date().toISOString();
const createLocalId = () => `local_rel_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
const createClientUuid = () => 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
  const r = Math.random() * 16 | 0;
  const v = c === 'x' ? r : ((r & 0x3) | 0x8);
  return v.toString(16);
});
const createClientUid = createClientUuid;
const deriveClientUuidFromSeed = (seed = '') => {
  const base = String(seed || createLocalId());
  let hex = '';
  for (let i = 0; i < base.length; i += 1) {
    hex += (base.charCodeAt(i) % 16).toString(16);
  }
  const padded = (hex + '0123456789abcdef0123456789abcdef').slice(0, 32);
  return `${padded.slice(0, 8)}-${padded.slice(8, 12)}-4${padded.slice(13, 16)}-a${padded.slice(17, 20)}-${padded.slice(20, 32)}`;
};
const deriveClientUidFromSeed = deriveClientUuidFromSeed;
const toNullableText = (value) => {
  if (value === undefined || value === null) return null;
  const text = String(value).trim();
  return text === '' ? null : text;
};
const toNullableInt = (value) => {
  if (value === undefined || value === null || value === '') return null;
  const parsed = Number.parseInt(String(value), 10);
  return Number.isNaN(parsed) ? null : parsed;
};
const toNullableFloat = (value) => {
  if (value === undefined || value === null || value === '') return null;
  const parsed = Number.parseFloat(String(value));
  return Number.isNaN(parsed) ? null : parsed;
};

const safeParse = (value, fallback = []) => {
  try {
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
};
const uniqueBy = (items = [], keySelector) => {
  const seen = new Set();
  const out = [];
  for (const item of items || []) {
    const key = keySelector(item);
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
};
const toSqliteBool = (value) => (value ? 1 : 0);
const normalizeUuid = (value) => String(value || '').trim().toLowerCase();
const isMissingRemoteColumnError = (error, columnName) => {
  const text = String(error?.message || '').toLowerCase();
  return text.includes(`column '${String(columnName).toLowerCase()}' does not exist`) ||
    text.includes(`column \"${String(columnName).toLowerCase()}\" does not exist`) ||
    text.includes(`could not find the '${String(columnName).toLowerCase()}' column`);
};
const isRemoteConflictTargetError = (error, target = 'client_uuid') => {
  const text = String(error?.message || '').toLowerCase();
  return text.includes('on conflict') && text.includes(String(target).toLowerCase());
};

const getStoredUserId = async () => {
  if (Platform.OS === 'web') {
    return AsyncStorage.getItem(USER_ID_STORAGE_KEY);
  }

  try {
    return await SecureStore.getItemAsync(USER_ID_STORAGE_KEY);
  } catch {
    return AsyncStorage.getItem(USER_ID_STORAGE_KEY);
  }
};

const mapAssignedStatusToSyncEstado = (estado) => {
  if (estado === 'SINCRONIZADO') return 'SINCRONIZADO';
  if (estado === 'SINCRONIZANDO') return 'SINCRONIZANDO';
  if (estado === 'ERROR') return 'ERROR';
  return 'PENDIENTE';
};

const mapAssignedRelevamiento = (row = {}) => ({
  id: row.id,
  source: 'asignado',
  titulo: row.titulo,
  descripcion: row.descripcion,
  direccion_objetivo: row.direccion_objetivo,
  localidad: row.localidad,
  provincia: row.provincia,
  prioridad: row.prioridad,
  estado: row.estado,
  id_institucion: null,
  created_at: row.asignado_at || row.created_at,
  relevado_at: row.completado_at || null,
  last_synced_at: row.last_synced_at,
  sync_estado: mapAssignedStatusToSyncEstado(row.estado),
  observaciones: row.observaciones || row.descripcion || '',
  latitud: row.latitud_capturada,
  longitud: row.longitud_capturada,
  latitud_objetivo: row.latitud_objetivo,
  longitud_objetivo: row.longitud_objetivo,
});

const formatDynamicValue = (row = {}) => {
  if (row.valor_texto !== null && row.valor_texto !== undefined) return String(row.valor_texto);
  if (row.valor_numero !== null && row.valor_numero !== undefined) return String(row.valor_numero);
  if (row.valor_booleano !== null && row.valor_booleano !== undefined) return row.valor_booleano ? 'Si' : 'No';
  if (row.valor_fecha) return String(row.valor_fecha);
  if (row.valor_json && Object.keys(row.valor_json || {}).length) return JSON.stringify(row.valor_json);
  return '-';
};

const getSqliteDb = async () => {
  if (!sqliteDbPromise) {
    sqliteDbPromise = SQLite.openDatabaseAsync(SQLITE_DB_NAME);
  }
  return sqliteDbPromise;
};

const runSqliteTx = async (db, task) => {
  if (typeof db.withExclusiveTransactionAsync === 'function') {
    try {
      await db.withExclusiveTransactionAsync(task);
      return;
    } catch (error) {
      if (!String(error?.message || '').includes('not supported on web')) {
        throw error;
      }
    }
  }
  await db.withTransactionAsync(async () => {
    await task(db);
  });
};

const ensureSqliteColumn = async (db, tableName, columnName, columnDef) => {
  const rows = await db.getAllAsync(`PRAGMA table_info(${tableName})`);
  const exists = rows.some((row) => row?.name === columnName);
  if (!exists) {
    await db.execAsync(`ALTER TABLE ${tableName} ADD COLUMN ${columnName} ${columnDef};`);
  }
};

const getMetaValue = async (db, key) => {
  const row = await db.getFirstAsync(
    `SELECT value FROM ${SQLITE_META_TABLE} WHERE key = ?`,
    key
  );
  return row?.value ?? null;
};

const setMetaValue = async (db, key, value) => {
  await db.runAsync(
    `INSERT INTO ${SQLITE_META_TABLE} (key, value, updated_at)
     VALUES (?, ?, ?)
     ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at`,
    key,
    String(value),
    nowIso()
  );
};

const recoverStaleInFlightOperations = async (db) => {
  const threshold = new Date(Date.now() - OUTBOX_IN_FLIGHT_TIMEOUT_MS).toISOString();
  await db.runAsync(
    `UPDATE ${SQLITE_OUTBOX_TABLE}
     SET status = 'PENDING',
         started_at = NULL,
         updated_at = ?,
         last_error = COALESCE(last_error, 'Recovered IN_FLIGHT after app restart')
     WHERE status = 'IN_FLIGHT'
       AND (started_at IS NULL OR started_at <= ?)`,
    nowIso(),
    threshold
  );
};

const mapLocalRow = (row = {}) => {
  const payload = safeParse(row.payload_json, {});
  const clientUuid = normalizeUuid(row.client_uuid || payload?.client_uuid || payload?.client_uid || '');
  if (clientUuid) {
    payload.client_uuid = clientUuid;
    payload.client_uid = clientUuid;
  }
  return {
    local_id: row.local_id,
    remote_id: row.remote_id || null,
    client_uuid: clientUuid || null,
    observaciones: row.observaciones || '',
    latitud: row.latitud ?? '',
    longitud: row.longitud ?? '',
    sync_estado: row.sync_estado || 'PENDIENTE',
    synced: !!row.synced,
    created_at: row.created_at || nowIso(),
    sync_error: row.sync_error || null,
    sync_error_code: row.sync_error_code || null,
    payload,
  };
};

const mapOutboxRow = (row = {}) => ({
  op_id: row.op_id,
  local_id: row.local_id,
  status: row.status || 'PENDING',
  type: row.type || 'insert_relevamiento',
  payload: safeParse(row.payload_json, {}),
  created_at: row.created_at || nowIso(),
  started_at: row.started_at || null,
  ack_at: row.ack_at || null,
  server_id: row.server_id || null,
  retry_count: Number(row.retry_count || 0),
  next_retry_at: row.next_retry_at || null,
  last_error: row.last_error || null,
  last_error_code: row.last_error_code || null,
});

const migrateAsyncStorageToSqliteIfNeeded = async (db) => {
  const [legacyFlag, sqliteMetaFlag] = await Promise.all([
    AsyncStorage.getItem(SQLITE_MIGRATION_FLAG_KEY),
    getMetaValue(db, 'migrated_to_sqlite_v1'),
  ]);
  if (legacyFlag === '1' && sqliteMetaFlag === '1') return;

  const localCountRow = await db.getFirstAsync(`SELECT COUNT(*) as count FROM ${SQLITE_LOCAL_TABLE}`);
  const localCount = Number(localCountRow?.count || 0);
  if (legacyFlag === '1' && localCount > 0) {
    await setMetaValue(db, 'migrated_to_sqlite_v1', '1');
    return;
  }

  const [legacyLocalRaw, legacyQueueRaw] = await Promise.all([
    AsyncStorage.getItem(LOCAL_RELEVAMIENTOS_KEY),
    AsyncStorage.getItem(SYNC_QUEUE_KEY),
  ]);
  const legacyLocal = safeParse(legacyLocalRaw, []);
  const legacyQueue = safeParse(legacyQueueRaw, []);
  if (!legacyLocal.length && !legacyQueue.length) {
    await Promise.all([
      AsyncStorage.setItem(SQLITE_MIGRATION_FLAG_KEY, '1'),
      setMetaValue(db, 'migrated_to_sqlite_v1', '1'),
    ]);
    return;
  }

  await runSqliteTx(db, async (tx) => {
    for (const item of legacyLocal) {
      const payload = item?.payload || {};
      const clientUuid = normalizeUuid(payload?.client_uuid || payload?.client_uid || deriveClientUuidFromSeed(item?.local_id));
      await tx.runAsync(
        `INSERT INTO ${SQLITE_LOCAL_TABLE}
        (local_id, remote_id, client_uuid, created_at, synced, sync_estado, sync_error, sync_error_code, observaciones, latitud, longitud, payload_json, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(local_id) DO UPDATE SET
          remote_id = excluded.remote_id,
          client_uuid = excluded.client_uuid,
          created_at = excluded.created_at,
          synced = excluded.synced,
          sync_estado = excluded.sync_estado,
          sync_error = excluded.sync_error,
          sync_error_code = excluded.sync_error_code,
          observaciones = excluded.observaciones,
          latitud = excluded.latitud,
          longitud = excluded.longitud,
          payload_json = excluded.payload_json,
          updated_at = excluded.updated_at`,
        item?.local_id || createLocalId(),
        item?.remote_id || null,
        clientUuid || null,
        item?.created_at || nowIso(),
        toSqliteBool(!!item?.synced),
        item?.sync_estado || (item?.synced ? 'SINCRONIZADO' : 'PENDIENTE'),
        item?.sync_error || null,
        item?.sync_error_code || null,
        item?.observaciones || '',
        item?.latitud ?? '',
        item?.longitud ?? '',
        JSON.stringify(payload),
        nowIso()
      );
    }

    for (const op of legacyQueue) {
      const opClientUuid = normalizeUuid(op?.payload?.client_uuid || op?.payload?.client_uid || deriveClientUuidFromSeed(op?.local_id));
      await tx.runAsync(
        `INSERT INTO ${SQLITE_OUTBOX_TABLE}
        (local_id, op_id, type, payload_json, created_at, started_at, ack_at, server_id, retry_count, next_retry_at, last_error, last_error_code, status, updated_at)
        VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, 'PENDING', ?)
        ON CONFLICT(local_id) DO UPDATE SET
          op_id = excluded.op_id,
          type = excluded.type,
          payload_json = excluded.payload_json,
          created_at = excluded.created_at,
          retry_count = excluded.retry_count,
          next_retry_at = excluded.next_retry_at,
          last_error = excluded.last_error,
          last_error_code = excluded.last_error_code,
          status = 'PENDING',
          started_at = NULL,
          ack_at = NULL,
          updated_at = excluded.updated_at`,
        op?.local_id || createLocalId(),
        op?.op_id || createLocalId(),
        op?.type || 'insert_relevamiento',
        JSON.stringify({
          ...(op?.payload || {}),
          client_uuid: opClientUuid || null,
          client_uid: opClientUuid || null,
        }),
        op?.created_at || nowIso(),
        Number(op?.retry_count || 0),
        op?.next_retry_at || null,
        op?.last_error || null,
        op?.last_error_code || null,
        nowIso()
      );
    }

  });

  await Promise.all([
    AsyncStorage.setItem(SQLITE_MIGRATION_FLAG_KEY, '1'),
    setMetaValue(db, 'migrated_to_sqlite_v1', '1'),
  ]);
};

const ensureSqliteReady = async () => {
  if (sqliteInitPromise) {
    await sqliteInitPromise;
    return;
  }

  sqliteInitPromise = (async () => {
    const db = await getSqliteDb();
    await db.execAsync(`
      PRAGMA journal_mode = WAL;
      PRAGMA synchronous = FULL;
      CREATE TABLE IF NOT EXISTS ${SQLITE_META_TABLE} (
        key TEXT PRIMARY KEY NOT NULL,
        value TEXT,
        updated_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS ${SQLITE_LOCAL_TABLE} (
        local_id TEXT PRIMARY KEY NOT NULL,
        remote_id TEXT,
        client_uuid TEXT,
        created_at TEXT NOT NULL,
        synced INTEGER NOT NULL DEFAULT 0,
        sync_estado TEXT NOT NULL DEFAULT 'PENDIENTE',
        sync_error TEXT,
        sync_error_code TEXT,
        observaciones TEXT,
        latitud TEXT,
        longitud TEXT,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS ${SQLITE_OUTBOX_TABLE} (
        local_id TEXT PRIMARY KEY NOT NULL,
        op_id TEXT NOT NULL,
        type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        started_at TEXT,
        ack_at TEXT,
        server_id TEXT,
        retry_count INTEGER NOT NULL DEFAULT 0,
        next_retry_at TEXT,
        last_error TEXT,
        last_error_code TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING',
        updated_at TEXT NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_${SQLITE_LOCAL_TABLE}_client_uuid
      ON ${SQLITE_LOCAL_TABLE} (client_uuid);
      CREATE INDEX IF NOT EXISTS idx_${SQLITE_OUTBOX_TABLE}_status_next_retry
      ON ${SQLITE_OUTBOX_TABLE} (status, next_retry_at, created_at);
      CREATE INDEX IF NOT EXISTS idx_${SQLITE_OUTBOX_TABLE}_status_started
      ON ${SQLITE_OUTBOX_TABLE} (status, started_at);
      CREATE INDEX IF NOT EXISTS idx_${SQLITE_LOCAL_TABLE}_created_at
      ON ${SQLITE_LOCAL_TABLE} (created_at DESC);
    `);

    await ensureSqliteColumn(db, SQLITE_LOCAL_TABLE, 'client_uuid', 'TEXT');
    await ensureSqliteColumn(db, SQLITE_OUTBOX_TABLE, 'started_at', 'TEXT');
    await ensureSqliteColumn(db, SQLITE_OUTBOX_TABLE, 'ack_at', 'TEXT');
    await ensureSqliteColumn(db, SQLITE_OUTBOX_TABLE, 'server_id', 'TEXT');
    await migrateAsyncStorageToSqliteIfNeeded(db);
    await recoverStaleInFlightOperations(db);
  })();

  await sqliteInitPromise;
};

const sanitizeFileName = (value = 'archivo') =>
  String(value)
    .replace(/[^\w.-]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '') || 'archivo';

const inferMimeType = (uri = '', fallback = 'application/octet-stream') => {
  const lower = String(uri).toLowerCase();
  if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) return 'image/jpeg';
  if (lower.endsWith('.png')) return 'image/png';
  if (lower.endsWith('.webp')) return 'image/webp';
  if (lower.endsWith('.gif')) return 'image/gif';
  if (lower.endsWith('.heic')) return 'image/heic';
  if (lower.endsWith('.pdf')) return 'application/pdf';
  if (lower.endsWith('.doc')) return 'application/msword';
  if (lower.endsWith('.docx')) return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  return fallback;
};

const createSyncError = (code, message, details = {}) => {
  const error = new Error(message);
  error.code = code;
  Object.assign(error, details);
  return error;
};

const isNetworkError = (error) => {
  const message = String(error?.message || '').toLowerCase();
  return (
    message.includes('network request failed') ||
    message.includes('failed to fetch') ||
    message.includes('unable to resolve host') ||
    message.includes('timed out') ||
    message.includes('network')
  );
};

const getConnectivitySnapshot = async () => {
  try {
    const state = await NetInfo.fetch();
    const isConnected = !!state?.isConnected;
    const isInternetReachable = state?.isInternetReachable;
    const hasInternet = isConnected && isInternetReachable !== false;
    return {
      hasInternet,
      isConnected,
      isInternetReachable,
      type: state?.type || 'unknown',
    };
  } catch (error) {
    return {
      hasInternet: false,
      isConnected: false,
      isInternetReachable: false,
      type: 'error',
      error: error?.message || 'NetInfo unavailable',
    };
  }
};

const ensureAttachmentsDir = async () => {
  const info = await FileSystem.getInfoAsync(ATTACHMENTS_DIR);
  if (!info.exists) {
    await FileSystem.makeDirectoryAsync(ATTACHMENTS_DIR, { intermediates: true });
  }
};

const buildPersistentName = ({ uri, fileName, fallbackPrefix = 'file' }) => {
  const sourceName = sanitizeFileName(fileName || String(uri || '').split('/').pop() || fallbackPrefix);
  const ts = Date.now();
  const rand = Math.random().toString(36).slice(2, 8);
  return `${ts}_${rand}_${sourceName}`;
};

const isRemoteUri = (uri = '') => String(uri).startsWith('http://') || String(uri).startsWith('https://');
const isPersistentUri = (uri = '') => String(uri).startsWith(ATTACHMENTS_DIR);
const isTemporaryPickerUri = (uri = '') => {
  const value = String(uri || '');
  return value.includes('/cache/ImagePicker/') || value.includes('/cache/');
};

const persistLocalFileIfNeeded = async ({ uri, fileName, mimeType, size }) => {
  if (!uri || isRemoteUri(uri) || isPersistentUri(uri)) {
    return { uri, mimeType, size };
  }

  await ensureAttachmentsDir();
  const sourceInfo = await FileSystem.getInfoAsync(uri, { size: true });
  const isContentUri = String(uri).startsWith('content://');
  if (!isContentUri && !sourceInfo.exists) {
    throw createSyncError(
      ERROR_MISSING_LOCAL_FILE,
      'Adjunto no disponible, volve a adjuntarlo',
      { uri }
    );
  }

  console.log('[SYNC][FILE][PERSIST_START]', {
    sourceUri: uri,
    fileName: fileName || null,
    sizeBytes: sourceInfo?.size || size || null,
    fromCache: isTemporaryPickerUri(uri),
  });

  const stableName = buildPersistentName({ uri, fileName });
  const stableUri = `${ATTACHMENTS_DIR}/${stableName}`;
  await FileSystem.copyAsync({ from: uri, to: stableUri });

  const stableInfo = await FileSystem.getInfoAsync(stableUri, { size: true });
  console.log('[SYNC][FILE][PERSIST_OK]', {
    sourceUri: uri,
    stableUri,
    sizeBytes: stableInfo?.size || null,
  });
  return {
    uri: stableUri,
    mimeType: mimeType || inferMimeType(fileName || stableUri),
    size: stableInfo?.size || size || null,
  };
};

const persistPayloadFiles = async (payload = {}) => {
  const nextPayload = { ...payload };
  const evidencias = Array.isArray(payload?.evidencias) ? payload.evidencias : [];
  const adjuntos = Array.isArray(payload?.adjuntos) ? payload.adjuntos : [];

  const persistedEvidencias = [];
  for (const item of evidencias) {
    const rawUri = item?.uri || '';
    if (!rawUri) continue;
    const persisted = await persistLocalFileIfNeeded({
      uri: rawUri,
      fileName: item?.nombre || rawUri.split('/').pop(),
      mimeType: item?.mimeType || 'image/jpeg',
      size: item?.size || null,
    });
    persistedEvidencias.push({
      ...item,
      uri: persisted.uri,
      mimeType: persisted.mimeType,
      size: persisted.size,
    });
  }

  const persistedAdjuntos = [];
  for (const item of adjuntos) {
    const rawUri = item?.uri || '';
    if (!rawUri) continue;
    const persisted = await persistLocalFileIfNeeded({
      uri: rawUri,
      fileName: item?.nombre || rawUri.split('/').pop(),
      mimeType: item?.mimeType || inferMimeType(item?.nombre || rawUri),
      size: item?.size || null,
    });
    persistedAdjuntos.push({
      ...item,
      uri: persisted.uri,
      mimeType: persisted.mimeType,
      size: persisted.size,
    });
  }

  nextPayload.evidencias = persistedEvidencias;
  nextPayload.adjuntos = persistedAdjuntos;
  return nextPayload;
};

const calculateBackoffMs = (retryCount = 0) => {
  const base = 2500;
  const max = 5 * 60 * 1000;
  return Math.min(max, base * (2 ** Math.max(0, retryCount)));
};

const uploadToStorage = async ({ relevamientoId, category, uri, mimeType, fileName }) => {
  if (!uri) return null;
  if (isRemoteUri(uri)) {
    return { storage_path: uri, mime_type: mimeType || inferMimeType(uri), size_bytes: null };
  }

  const persisted = await persistLocalFileIfNeeded({
    uri,
    fileName: fileName || String(uri).split('/').pop(),
    mimeType,
    size: null,
  });
  const uploadUri = persisted?.uri || uri;
  const uploadMimeType = persisted?.mimeType || mimeType;

  const connectivity = await getConnectivitySnapshot();
  if (!connectivity.hasInternet) {
    throw createSyncError(ERROR_OFFLINE, 'Sin conectividad: upload diferido', { connectivity });
  }

  const localInfo = await FileSystem.getInfoAsync(uploadUri, { size: true });
  if (!localInfo.exists) {
    throw createSyncError(
      ERROR_MISSING_LOCAL_FILE,
      'Adjunto no disponible, volve a adjuntarlo',
      { uri: uploadUri }
    );
  }

  const safeName = sanitizeFileName(fileName || uploadUri.split('/').pop() || createLocalId());
  const ts = Date.now();
  const storagePath = `${relevamientoId}/${category.toLowerCase()}_${ts}_${safeName}`;
  const contentType = uploadMimeType || inferMimeType(safeName);
  const endpoint = `${SUPABASE_CONFIG.url}/storage/v1/object/relevamientos/${storagePath}`;

  console.log('[SYNC][UPLOAD][START]', {
    endpoint,
    category,
    uri: uploadUri,
    fileName: safeName,
    contentType,
    sizeBytes: localInfo?.size || null,
    connectivity,
  });

  const base64 = await FileSystem.readAsStringAsync(uploadUri, {
    encoding: FileSystem.EncodingType.Base64,
  });
  const arrayBuffer = decodeBase64(base64 || '');
  if (!arrayBuffer || !arrayBuffer.byteLength) {
    throw new Error('El archivo local no tiene contenido o no se pudo leer');
  }
  const sizeBytes = arrayBuffer?.byteLength || null;

  const { error: uploadError } = await supabase.storage
    .from('relevamientos')
    .upload(storagePath, arrayBuffer, {
      contentType,
      upsert: false,
    });

  if (uploadError) {
    console.warn('[SYNC][UPLOAD][ERROR]', {
      endpoint,
      storagePath,
      category,
      uri: uploadUri,
      message: uploadError?.message || 'Error desconocido al subir',
      statusCode: uploadError?.statusCode || uploadError?.status || null,
    });
    throw uploadError;
  }

  console.log('[SYNC][UPLOAD][OK]', {
    endpoint,
    storagePath,
    category,
    sizeBytes,
  });
  return { storage_path: storagePath, mime_type: contentType, size_bytes: sizeBytes };
};

const readLocalRecords = async () => {
  await ensureSqliteReady();
  const db = await getSqliteDb();
  const rows = await db.getAllAsync(
    `SELECT local_id, remote_id, client_uuid, created_at, synced, sync_estado, sync_error, sync_error_code, observaciones, latitud, longitud, payload_json
     FROM ${SQLITE_LOCAL_TABLE}
     ORDER BY created_at DESC`
  );
  return rows.map(mapLocalRow);
};

const readQueue = async () => {
  await ensureSqliteReady();
  const db = await getSqliteDb();
  const rows = await db.getAllAsync(
    `SELECT local_id, op_id, status, type, payload_json, created_at, started_at, ack_at, server_id, retry_count, next_retry_at, last_error, last_error_code
     FROM ${SQLITE_OUTBOX_TABLE}
     WHERE status = 'PENDING'
     ORDER BY created_at ASC`
  );
  return rows.map(mapOutboxRow);
};

const buildRelevamientoRow = (payload = {}) => {
  const directKeys = [
    'tiene_colaboradores',
    'cantidad_colaboradores',
    'tipo_espacio_fisico',
    'espacio_fisico_otro',
    'tiene_cocina',
    'espacio_elaboracion_alimentos',
    'almacenamiento_alimentos_secos',
    'heladera',
    'freezer',
    'recipiente_residuos_organicos',
    'recipiente_residuos_reciclables',
    'otros_residuos',
    'recipiente_otros_residuos',
    'abastecimiento_combustible',
    'abastecimiento_agua',
    'abastecimiento_agua_otro',
    'instalacion_electrica',
    'espacio_equipado',
    'tiene_ventilacion',
    'tiene_salida_emergencia',
    'salida_emergencia_senializada',
    'tiene_equipacion_incendio',
    'tiene_botiquin',
    'tiene_buena_iluminacion',
    'tiene_sanitarios',
    'desague_hinodoro',
    'gestion_quejas',
    'gestion_quejas_otro',
    'informacion_quejas',
    'frecuencia_limpieza',
    'tipo_insumo',
    'frecuencia_insumo',
    'tecnologia',
    'acceso_institucion',
    'distancia_transporte',
    'servicio_internet',
    'zona_inundable',
    'actividades_jardin_maternal',
    'actividades_jardin_infantes',
    'apoyo_escolar',
    'alfabetizacion_terminalidad',
    'capacitaciones_talleres',
    'tipo_talleres',
    'promocion_salud',
    'actividades_discapacidad',
    'actividades_recreativas',
    'cuales_actividades_recreativas',
    'actividades_culturales',
    'cuales_actividades_culturales',
    'emprendimientos_productivos',
    'cuales_emprendimientos_productivos',
    'actividades_religiosas',
    'actividades_huerta',
    'otras_actividades',
    'cuales_otras_actividades',
    'latitud',
    'longitud',
    'observaciones',
    'firma_paths',
  ];

  const row = {
    client_uuid: toNullableText(payload?.client_uuid || payload?.client_uid) || createClientUuid(),
    id_institucion: 1,
    responsable_nombre: toNullableText(payload?.nombre),
    responsable_apellido: toNullableText(payload?.apellido),
    responsable_dni: toNullableText(payload?.dni),
    responsable_telefono: toNullableText(payload?.telefono),
    responsable_email: toNullableText(payload?.email),
    responsable_funcion: toNullableText(payload?.funcion),
    usuario_username: toNullableText(payload?.usuario_username || payload?.operador_username),
    relevado_at: toNullableText(payload?.relevado_at || payload?.created_at) || nowIso(),
    sync_estado: 'SINCRONIZADO',
    sync_error: null,
    last_synced_at: nowIso(),
  };

  directKeys.forEach((key) => {
    if (Object.prototype.hasOwnProperty.call(payload, key)) {
      row[key] = payload[key];
    }
  });

  row.cantidad_colaboradores = toNullableInt(row.cantidad_colaboradores);
  row.latitud = toNullableFloat(row.latitud);
  row.longitud = toNullableFloat(row.longitud);
  row.espacio_fisico_otro = toNullableText(row.espacio_fisico_otro);
  row.abastecimiento_agua_otro = toNullableText(row.abastecimiento_agua_otro);
  row.gestion_quejas_otro = toNullableText(row.gestion_quejas_otro);
  row.tipo_talleres = toNullableText(row.tipo_talleres);
  row.cuales_actividades_recreativas = toNullableText(row.cuales_actividades_recreativas);
  row.cuales_actividades_culturales = toNullableText(row.cuales_actividades_culturales);
  row.cuales_emprendimientos_productivos = toNullableText(row.cuales_emprendimientos_productivos);
  row.cuales_otras_actividades = toNullableText(row.cuales_otras_actividades);
  row.observaciones = toNullableText(row.observaciones);
  row.firma_paths = Array.isArray(row.firma_paths) ? row.firma_paths : [];

  return row;
};

const insertRelatedData = async (relevamientoId, payload = {}) => {
  // Reintentos idempotentes: limpiamos detalle previo y lo volvemos a insertar.
  const { error: clearExtraError } = await supabase.from(TABLE_CAMPOS_EXTRA).delete().eq('relevamiento_id', relevamientoId);
  if (clearExtraError) throw clearExtraError;
  const { error: clearAdjError } = await supabase.from(TABLE_ADJUNTOS).delete().eq('relevamiento_id', relevamientoId);
  if (clearAdjError) throw clearAdjError;

  const extraRows = (payload?.campos_extra || []).map((item, idx) => ({
    relevamiento_id: relevamientoId,
    orden: idx + 1,
    nombre: item.nombre,
    valor: item.valor,
  }));

  if (extraRows.length > 0) {
    const { error } = await supabase.from(TABLE_CAMPOS_EXTRA).insert(extraRows);
    if (error) throw error;
  }

  const attachmentRows = [];
  const uploadErrors = [];

  const evidenciasUnicas = uniqueBy(payload?.evidencias || [], (item) => `${item?.uri || ''}|${item?.nombre || ''}`);
  const adjuntosUnicos = uniqueBy(payload?.adjuntos || [], (item) => `${item?.uri || ''}|${item?.nombre || ''}|${item?.tipo || ''}`);

  for (const item of evidenciasUnicas) {
    try {
      const uploaded = await uploadToStorage({
        relevamientoId,
        category: 'EVIDENCIA',
        uri: item?.uri,
        mimeType: item?.mimeType || 'image/jpeg',
        fileName: item?.nombre || item?.uri?.split('/').pop() || 'evidencia.jpg',
      });
      if (!uploaded?.storage_path) continue;
      attachmentRows.push({
        relevamiento_id: relevamientoId,
        categoria: 'EVIDENCIA',
        tipo_archivo: 'IMAGEN',
        storage_bucket: 'relevamientos',
        storage_path: uploaded.storage_path,
        nombre_original: item?.nombre || item?.uri?.split('/').pop() || 'evidencia.jpg',
        mime_type: uploaded.mime_type || null,
        size_bytes: uploaded.size_bytes || null,
      });
    } catch (error) {
      uploadErrors.push({
        code: error?.code || null,
        message: `EVIDENCIA ${item?.nombre || item?.uri || ''}: ${error?.message || 'Error al subir archivo'}`,
      });
    }
  }

  for (const item of adjuntosUnicos) {
    try {
      const uploaded = await uploadToStorage({
        relevamientoId,
        category: 'DOCUMENTO',
        uri: item?.uri,
        mimeType: item?.mimeType || null,
        fileName: item?.nombre || item?.uri?.split('/').pop() || 'adjunto',
      });
      if (!uploaded?.storage_path) continue;
      attachmentRows.push({
        relevamiento_id: relevamientoId,
        categoria: 'DOCUMENTO',
        tipo_archivo: item?.tipo === 'imagen' ? 'IMAGEN' : 'ARCHIVO',
        storage_bucket: 'relevamientos',
        storage_path: uploaded.storage_path,
        nombre_original: item?.nombre || 'adjunto',
        mime_type: uploaded.mime_type || null,
        size_bytes: uploaded.size_bytes || item?.size || null,
      });
    } catch (error) {
      uploadErrors.push({
        code: error?.code || null,
        message: `DOCUMENTO ${item?.nombre || item?.uri || ''}: ${error?.message || 'Error al subir archivo'}`,
      });
    }
  }

  if (uploadErrors.length > 0) {
    const missingFile = uploadErrors.find((item) => item?.code === ERROR_MISSING_LOCAL_FILE);
    if (missingFile) {
      throw createSyncError(
        ERROR_MISSING_LOCAL_FILE,
        'Adjunto no disponible, volve a adjuntarlo',
        { detail: missingFile.message }
      );
    }
    throw createSyncError(
      ERROR_ATTACHMENTS_UPLOAD,
      `No se pudieron subir algunos adjuntos. ${uploadErrors[0]?.message || 'Error al subir adjuntos'}`,
      { errors: uploadErrors }
    );
  }

  const attachmentRowsUnicos = uniqueBy(
    attachmentRows,
    (row) => `${row?.categoria || ''}|${row?.tipo_archivo || ''}|${row?.storage_path || ''}|${row?.nombre_original || ''}`
  );

  if (attachmentRowsUnicos.length > 0) {
    const { error } = await supabase.from(TABLE_ADJUNTOS).insert(attachmentRowsUnicos);
    if (error) throw error;
  }
};

const upsertRemoteRelevamiento = async (payload = {}) => {
  const rowByClientUuid = buildRelevamientoRow(payload);
  const { data, error } = await supabase
    .from(TABLE_RELEVAMIENTOS)
    .upsert(rowByClientUuid, { onConflict: 'client_uuid' })
    .select('id, id_institucion, created_at, relevado_at, last_synced_at, sync_estado, observaciones, latitud, longitud')
    .single();

  if (!error) return data;
  if (!isMissingRemoteColumnError(error, 'client_uuid') && !isRemoteConflictTargetError(error, 'client_uuid')) {
    throw error;
  }

  const legacyPayload = { ...payload, client_uid: payload?.client_uuid || payload?.client_uid || createClientUuid() };
  const legacyRow = {
    ...buildRelevamientoRow(legacyPayload),
    client_uid: legacyPayload.client_uid,
  };
  delete legacyRow.client_uuid;

  const { data: legacyData, error: legacyError } = await supabase
    .from(TABLE_RELEVAMIENTOS)
    .upsert(legacyRow, { onConflict: 'client_uid' })
    .select('id, id_institucion, created_at, relevado_at, last_synced_at, sync_estado, observaciones, latitud, longitud')
    .single();

  if (legacyError) {
    throw createSyncError(
      ERROR_REMOTE_SCHEMA,
      legacyError?.message || 'No se pudo sincronizar por schema remoto incompatible',
      { cause: legacyError }
    );
  }
  return legacyData;
};

const syncSingleOperation = async (operation) => {
  const clientUuid = normalizeUuid(
    operation?.payload?.client_uuid ||
    operation?.payload?.client_uid ||
    deriveClientUuidFromSeed(operation?.local_id || operation?.op_id)
  );
  const payloadWithClientUuid = {
    ...(operation.payload || {}),
    client_uuid: clientUuid,
    client_uid: clientUuid,
  };

  const created = await upsertRemoteRelevamiento(payloadWithClientUuid);
  await insertRelatedData(created.id, payloadWithClientUuid);
  return created;
};

const upsertLocalRecordAndEnqueue = async (payload) => {
  await ensureSqliteReady();
  const db = await getSqliteDb();
  const local_id = payload.local_id || createLocalId();
  const clientUuid = normalizeUuid(payload.client_uuid || payload.client_uid || createClientUuid());
  const createdAt = payload.created_at || nowIso();
  const normalizedPayload = {
    ...payload,
    client_uuid: clientUuid,
    client_uid: clientUuid,
  };
  const record = {
    local_id,
    remote_id: payload.remote_id || null,
    client_uuid: clientUuid,
    observaciones: payload.observaciones || '',
    latitud: payload.latitud || '',
    longitud: payload.longitud || '',
    sync_estado: payload.sync_estado || 'PENDIENTE',
    synced: !!payload.synced,
    created_at: createdAt,
    payload: normalizedPayload,
  };

  await runSqliteTx(db, async (tx) => {
    const updatedAt = nowIso();
    await tx.runAsync(
      `INSERT INTO ${SQLITE_LOCAL_TABLE}
      (local_id, remote_id, client_uuid, created_at, synced, sync_estado, sync_error, sync_error_code, observaciones, latitud, longitud, payload_json, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?)
      ON CONFLICT(local_id) DO UPDATE SET
        remote_id = excluded.remote_id,
        client_uuid = excluded.client_uuid,
        created_at = excluded.created_at,
        synced = excluded.synced,
        sync_estado = excluded.sync_estado,
        sync_error = NULL,
        sync_error_code = NULL,
        observaciones = excluded.observaciones,
        latitud = excluded.latitud,
        longitud = excluded.longitud,
        payload_json = excluded.payload_json,
        updated_at = excluded.updated_at`,
      record.local_id,
      record.remote_id,
      record.client_uuid || null,
      record.created_at,
      toSqliteBool(record.synced),
      record.sync_estado,
      record.observaciones || '',
      record.latitud ?? '',
      record.longitud ?? '',
      JSON.stringify(record.payload || {}),
      updatedAt
    );

    await tx.runAsync(
      `INSERT INTO ${SQLITE_OUTBOX_TABLE}
      (local_id, op_id, type, payload_json, created_at, started_at, ack_at, server_id, retry_count, next_retry_at, last_error, last_error_code, status, updated_at)
      VALUES (?, ?, 'insert_relevamiento', ?, ?, NULL, NULL, NULL, 0, NULL, NULL, NULL, 'PENDING', ?)
      ON CONFLICT(local_id) DO UPDATE SET
        op_id = excluded.op_id,
        type = excluded.type,
        payload_json = excluded.payload_json,
        created_at = excluded.created_at,
        started_at = NULL,
        ack_at = NULL,
        server_id = NULL,
        retry_count = 0,
        next_retry_at = NULL,
        last_error = NULL,
        last_error_code = NULL,
        status = 'PENDING',
        updated_at = excluded.updated_at`,
      record.local_id,
      createLocalId(),
      JSON.stringify(record.payload || {}),
      record.created_at,
      updatedAt
    );
  });

  return record;
};

const markOutboxOperationInFlight = async (localId) => {
  await ensureSqliteReady();
  const db = await getSqliteDb();
  const startedAt = nowIso();
  const result = await db.runAsync(
    `UPDATE ${SQLITE_OUTBOX_TABLE}
     SET status = 'IN_FLIGHT',
         started_at = ?,
         updated_at = ?
     WHERE local_id = ?
       AND status = 'PENDING'`,
    startedAt,
    startedAt,
    localId
  );
  return Number(result?.changes || 0) > 0;
};

const markOperationSyncedAtomic = async (localId, remoteRow) => {
  await ensureSqliteReady();
  const db = await getSqliteDb();
  await runSqliteTx(db, async (tx) => {
    const stamp = nowIso();
    await tx.runAsync(
      `UPDATE ${SQLITE_LOCAL_TABLE}
       SET remote_id = ?,
           synced = 1,
           sync_estado = 'SINCRONIZADO',
           sync_error = NULL,
           sync_error_code = NULL,
           observaciones = ?,
           latitud = ?,
           longitud = ?,
           updated_at = ?
       WHERE local_id = ?`,
      remoteRow?.id || null,
      remoteRow?.observaciones || '',
      remoteRow?.latitud ?? '',
      remoteRow?.longitud ?? '',
      stamp,
      localId
    );

    await tx.runAsync(
      `UPDATE ${SQLITE_OUTBOX_TABLE}
       SET status = 'SYNCED',
           ack_at = ?,
           server_id = ?,
           last_error = NULL,
           last_error_code = NULL,
           next_retry_at = NULL,
           started_at = NULL,
           updated_at = ?
       WHERE local_id = ?`,
      stamp,
      remoteRow?.id || null,
      stamp,
      localId
    );
  });
};

const markOperationRetryAtomic = async (localId, {
  retryCount,
  nextRetryAt,
  message,
  errorCode,
  localSyncEstado = 'PENDIENTE',
}) => {
  await ensureSqliteReady();
  const db = await getSqliteDb();
  await runSqliteTx(db, async (tx) => {
    const stamp = nowIso();
    await tx.runAsync(
      `UPDATE ${SQLITE_LOCAL_TABLE}
       SET sync_estado = ?,
           synced = 0,
           sync_error = ?,
           sync_error_code = ?,
           updated_at = ?
       WHERE local_id = ?`,
      localSyncEstado,
      message || null,
      'RETRY',
      stamp,
      localId
    );

    await tx.runAsync(
      `UPDATE ${SQLITE_OUTBOX_TABLE}
       SET retry_count = ?,
           next_retry_at = ?,
           last_error = ?,
           last_error_code = ?,
           status = 'PENDING',
           started_at = NULL,
           updated_at = ?
       WHERE local_id = ?`,
      Number(retryCount || 0),
      nextRetryAt || null,
      message || null,
      errorCode || null,
      stamp,
      localId
    );
  });
};

const markOperationPermanentErrorAtomic = async (localId, {
  retryCount,
  message,
  errorCode,
  localSyncEstado = 'ERROR',
}) => {
  await ensureSqliteReady();
  const db = await getSqliteDb();
  await runSqliteTx(db, async (tx) => {
    const stamp = nowIso();
    await tx.runAsync(
      `UPDATE ${SQLITE_LOCAL_TABLE}
       SET sync_estado = ?,
           synced = 0,
           sync_error = ?,
           sync_error_code = ?,
           updated_at = ?
       WHERE local_id = ?`,
      localSyncEstado,
      message || null,
      'PERMANENT',
      stamp,
      localId
    );

    await tx.runAsync(
      `UPDATE ${SQLITE_OUTBOX_TABLE}
       SET retry_count = ?,
           next_retry_at = NULL,
           last_error = ?,
           last_error_code = ?,
           status = 'FAILED_PERMANENT',
           started_at = NULL,
           updated_at = ?
       WHERE local_id = ?`,
      Number(retryCount || 0),
      message || null,
      errorCode || null,
      stamp,
      localId
    );
  });
};

const fetchRemoteRecords = async () => {
  try {
    const currentUserId = await getStoredUserId();
    let query = supabase
      .from(TABLE_RELEVAMIENTOS_ASIGNADOS)
      .select('id, client_uid, titulo, descripcion, estado, prioridad, direccion_objetivo, localidad, provincia, latitud_objetivo, longitud_objetivo, latitud_capturada, longitud_capturada, observaciones, asignado_at, completado_at, last_synced_at, created_at')
      .is('deleted_at', null)
      .order('asignado_at', { ascending: false });

    if (currentUserId) {
      query = query.eq('assigned_user_id', currentUserId);
    }

    const { data, error } = await query;
    if (error) throw error;
    return (data || []).map(mapAssignedRelevamiento);
  } catch (assignedError) {
    const message = String(assignedError?.message || '').toLowerCase();
    const canFallbackToLegacy =
      message.includes(TABLE_RELEVAMIENTOS_ASIGNADOS) ||
      message.includes('does not exist') ||
      message.includes('could not find');

    if (!canFallbackToLegacy) throw assignedError;
  }

  const { data, error } = await supabase
    .from(TABLE_RELEVAMIENTOS)
    .select('id, id_institucion, created_at, relevado_at, last_synced_at, sync_estado, observaciones, latitud, longitud')
    .eq('id_institucion', 1)
    .is('deleted_at', null)
    .order('created_at', { ascending: false });

  if (error) throw error;
  return data || [];
};

const isLocalId = (id) => String(id || '').startsWith('local_rel_');

const relevamientoService = {
  async saveRelevamiento(payload) {
    await ensureSqliteReady();
    const persistedPayload = await persistPayloadFiles(payload || {});
    const clientUuid = normalizeUuid(payload?.client_uuid || payload?.client_uid || createClientUuid());
    const normalizedPayload = {
      ...persistedPayload,
      client_uuid: clientUuid,
      client_uid: clientUuid,
      relevado_at: payload?.relevado_at || payload?.created_at || nowIso(),
    };

    const localRecord = await upsertLocalRecordAndEnqueue({
      ...normalizedPayload,
      sync_estado: 'PENDIENTE',
      synced: false,
      created_at: nowIso(),
    });

    const syncResult = await this.syncPendingOperations();
    return { success: true, record: localRecord, syncResult };
  },

  async syncPendingOperations() {
    await ensureSqliteReady();
    if (syncInFlightPromise) {
      return syncInFlightPromise;
    }

    syncInFlightPromise = (async () => {
    const db = await getSqliteDb();
    await recoverStaleInFlightOperations(db);
    const queue = await readQueue();
    if (!queue.length) return { synced: 0, failed: 0, errors: [] };

    const connectivity = await getConnectivitySnapshot();
    if (!connectivity.hasInternet) {
      console.log('[SYNC][SKIP_OFFLINE]', {
        pending: queue.length,
        connectivity,
      });
      return {
        synced: 0,
        failed: 0,
        skipped: queue.length,
        offline: true,
        errors: [{ message: 'Sin conexion: adjuntos pendientes' }],
      };
    }

    let synced = 0;
    let failed = 0;
    const errors = [];
    const nowTs = Date.now();

    for (const operation of queue) {
      const nextRetryAtTs = operation?.next_retry_at ? Date.parse(operation.next_retry_at) : null;
      if (nextRetryAtTs && Number.isFinite(nextRetryAtTs) && nextRetryAtTs > nowTs) {
        continue;
      }

      const acquired = await markOutboxOperationInFlight(operation.local_id);
      if (!acquired) {
        continue;
      }

      try {
        console.log('[SYNC][OP][START]', {
          op_id: operation?.op_id,
          local_id: operation?.local_id,
          retry_count: operation?.retry_count || 0,
          next_retry_at: operation?.next_retry_at || null,
          attachments: {
            evidencias: operation?.payload?.evidencias?.length || 0,
            adjuntos: operation?.payload?.adjuntos?.length || 0,
          },
        });
        const remoteRow = await syncSingleOperation(operation);
        await markOperationSyncedAtomic(operation.local_id, remoteRow);
        synced += 1;
      } catch (error) {
        failed += 1;
        const status = Number(error?.statusCode || error?.status || 0);
        const retriable = isNetworkError(error) || (status >= 500 && status <= 599);
        const retryCount = (operation?.retry_count || 0) + 1;
        const canRetry = retriable && retryCount <= MAX_RETRY_COUNT;
        const nextRetry = canRetry ? new Date(Date.now() + calculateBackoffMs(retryCount)).toISOString() : null;
        const errorCode = error?.code || null;
        const message = errorCode === ERROR_MISSING_LOCAL_FILE
          ? 'Adjunto no disponible, volve a adjuntarlo'
          : (error?.message || 'Error desconocido');
        const localSyncEstado = errorCode === ERROR_ATTACHMENTS_UPLOAD ? 'PARCIAL' : 'PENDIENTE';

        console.warn('[SYNC][OP][ERROR]', {
          op_id: operation?.op_id,
          local_id: operation?.local_id,
          status,
          retriable,
          canRetry,
          error_code: errorCode,
          retry_count: retryCount,
          next_retry_at: nextRetry,
          message,
          stack: error?.stack || null,
        });

        if (canRetry) {
          await markOperationRetryAtomic(operation.local_id, {
            retryCount,
            nextRetryAt: nextRetry,
            message,
            errorCode,
            localSyncEstado,
          });
        } else {
          await markOperationPermanentErrorAtomic(operation.local_id, {
            retryCount,
            message,
            errorCode,
            localSyncEstado: errorCode === ERROR_ATTACHMENTS_UPLOAD ? 'PARCIAL' : 'ERROR',
          });
        }

        errors.push({
          local_id: operation.local_id,
          message,
          code: errorCode,
        });
      }
    }

    return { synced, failed, errors };
    })();

    try {
      return await syncInFlightPromise;
    } finally {
      syncInFlightPromise = null;
    }
  },

  async getPendingCount() {
    await ensureSqliteReady();
    const db = await getSqliteDb();
    const row = await db.getFirstAsync(
      `SELECT COUNT(*) as count FROM ${SQLITE_OUTBOX_TABLE} WHERE status IN ('PENDING', 'IN_FLIGHT')`
    );
    return Number(row?.count || 0);
  },

  async getRelevamientos({ refreshFromRemote = true } = {}) {
    if (refreshFromRemote) {
      try {
        await this.syncPendingOperations();
        const localRecords = await readLocalRecords();
        const remote = await fetchRemoteRecords();
        const pendingLocal = localRecords
          .filter((item) => !item.synced)
          .map((item) => ({
            id: item.local_id,
            id_institucion: 1,
            created_at: item.created_at,
            sync_estado: item.sync_estado || 'PENDIENTE',
            observaciones: item.observaciones,
            latitud: item.latitud,
            longitud: item.longitud,
        }));
        return { success: true, records: [...pendingLocal, ...remote] };
      } catch (error) {
        const localRecords = await readLocalRecords();
        const fallback = localRecords.map((item) => ({
          id: item.local_id,
          id_institucion: 1,
          created_at: item.created_at,
          sync_estado: item.sync_estado || (item.synced ? 'SINCRONIZADO' : 'PENDIENTE'),
          observaciones: item.observaciones,
          latitud: item.latitud,
          longitud: item.longitud,
        }));
        return { success: false, records: fallback, error: error?.message || 'Modo offline' };
      }
    }

    const localRecords = await readLocalRecords();
    const mapped = localRecords.map((item) => ({
      id: item.local_id,
      id_institucion: 1,
      created_at: item.created_at,
      sync_estado: item.sync_estado || (item.synced ? 'SINCRONIZADO' : 'PENDIENTE'),
      observaciones: item.observaciones,
      latitud: item.latitud,
      longitud: item.longitud,
    }));
    return { success: true, records: mapped };
  },

  async getRelevamientoDetail(id) {
    if (!id) return { success: false, error: 'ID invalido' };

    if (isLocalId(id)) {
      const localRecords = await readLocalRecords();
      const local = localRecords.find((item) => item.local_id === id);
      if (!local) return { success: false, error: 'No se encontro el relevamiento local' };
      return {
        success: true,
        detail: {
          id: local.local_id,
          id_institucion: 1,
          created_at: local.created_at,
          sync_estado: local.sync_estado || (local.synced ? 'SINCRONIZADO' : 'PENDIENTE'),
          observaciones: local.observaciones,
          latitud: local.latitud,
          longitud: local.longitud,
          payload: local.payload || {},
          campos_extra: local.payload?.campos_extra || [],
          adjuntos: [
            ...(local.payload?.evidencias || []).map((x) => ({
              categoria: 'EVIDENCIA',
              tipo_archivo: 'IMAGEN',
              nombre_original: x?.uri?.split('/').pop() || 'evidencia.jpg',
              storage_path: x?.uri || '',
            })),
            ...(local.payload?.adjuntos || []).map((x) => ({
              categoria: 'DOCUMENTO',
              tipo_archivo: x.tipo === 'imagen' ? 'IMAGEN' : 'ARCHIVO',
              nombre_original: x.nombre || 'adjunto',
              storage_path: x.uri || '',
            })),
          ],
        },
      };
    }

    try {
      const { data: assigned, error: assignedError } = await supabase
        .from(TABLE_RELEVAMIENTOS_ASIGNADOS)
        .select('*, relevamiento_plantillas(nombre, version)')
        .eq('id', id)
        .single();

      if (assignedError) throw assignedError;

      const [{ data: persona }, { data: respuestas }, { data: archivos }, { data: camposDefinicion }] = await Promise.all([
        supabase
          .from(TABLE_RELEVAMIENTO_PERSONAS)
          .select('*')
          .eq('relevamiento_id', id)
          .maybeSingle(),
        supabase
          .from(TABLE_RELEVAMIENTO_RESPUESTAS)
          .select('id, valor_texto, valor_numero, valor_booleano, valor_fecha, valor_json, relevamiento_campos(clave, etiqueta, tipo, orden)')
          .eq('relevamiento_id', id),
        supabase
          .from(TABLE_RELEVAMIENTO_ARCHIVOS)
          .select('id, categoria, storage_bucket, storage_path, nombre_original, mime_type, size_bytes')
          .eq('relevamiento_id', id)
          .order('created_at', { ascending: true }),
        supabase
          .from('relevamiento_campos')
          .select('id, clave, etiqueta, tipo, orden, requerido, opciones, ayuda, validaciones')
          .eq('plantilla_id', assigned.plantilla_id)
          .eq('activo', true)
          .order('orden', { ascending: true }),
      ]);

      const camposExtra = (respuestas || [])
        .sort((a, b) => (a.relevamiento_campos?.orden || 0) - (b.relevamiento_campos?.orden || 0))
        .map((row) => ({
          id: row.id,
          nombre: row.relevamiento_campos?.etiqueta || row.relevamiento_campos?.clave || 'Campo',
          valor: formatDynamicValue(row),
        }));

      const adjuntos = (archivos || []).map((item) => ({
        id: item.id,
        categoria: item.categoria,
        tipo_archivo: String(item.mime_type || '').startsWith('image/') ? 'IMAGEN' : 'ARCHIVO',
        storage_bucket: item.storage_bucket || 'relevamientos',
        storage_path: item.storage_path,
        nombre_original: item.nombre_original,
        mime_type: item.mime_type,
        size_bytes: item.size_bytes,
      }));

      return {
        success: true,
        detail: {
          ...assigned,
          source: 'asignado',
          id_institucion: '-',
          sync_estado: mapAssignedStatusToSyncEstado(assigned.estado),
          observaciones: assigned.observaciones || assigned.descripcion || '',
          latitud: assigned.latitud_capturada,
          longitud: assigned.longitud_capturada,
          persona: persona || null,
          campos_definicion: camposDefinicion || [],
          campos_extra: camposExtra,
          adjuntos,
        },
      };
    } catch (assignedError) {
      const message = String(assignedError?.message || '').toLowerCase();
      const canFallbackToLegacy =
        message.includes(TABLE_RELEVAMIENTOS_ASIGNADOS) ||
        message.includes('does not exist') ||
        message.includes('could not find') ||
        message.includes('no rows');

      if (!canFallbackToLegacy) {
        return { success: false, error: assignedError.message || 'No se pudo cargar el relevamiento asignado' };
      }
    }

    const { data: main, error: mainError } = await supabase
      .from(TABLE_RELEVAMIENTOS)
      .select('*')
      .eq('id', id)
      .single();
    if (mainError) return { success: false, error: mainError.message || 'No se pudo cargar el relevamiento' };

    const { data: camposExtra } = await supabase
      .from(TABLE_CAMPOS_EXTRA)
      .select('id, orden, nombre, valor')
      .eq('relevamiento_id', id)
      .order('orden', { ascending: true });

    const { data: adjuntos } = await supabase
      .from(TABLE_ADJUNTOS)
      .select('id, categoria, tipo_archivo, nombre_original, storage_path')
      .eq('relevamiento_id', id)
      .order('created_at', { ascending: true });

    return {
      success: true,
      detail: {
        ...main,
        campos_extra: camposExtra || [],
        adjuntos: adjuntos || [],
      },
    };
  },
};

export default relevamientoService;
