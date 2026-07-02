import AsyncStorage from '@react-native-async-storage/async-storage';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { API_CONFIG } from '../config/apiConfig';

const TOKEN_KEY = 'becas_auth_token';
const USER_DATA_KEY = 'user_data';
const USER_ID_KEY = 'user_id';

const storage = {
  getItem: async (key) => {
    if (Platform.OS === 'web') return AsyncStorage.getItem(key);
    try {
      return await SecureStore.getItemAsync(key);
    } catch {
      return AsyncStorage.getItem(key);
    }
  },
  setItem: async (key, value) => {
    if (Platform.OS === 'web') return AsyncStorage.setItem(key, value);
    try {
      return await SecureStore.setItemAsync(key, value);
    } catch {
      return AsyncStorage.setItem(key, value);
    }
  },
  deleteItem: async (key) => {
    if (Platform.OS === 'web') return AsyncStorage.removeItem(key);
    try {
      return await SecureStore.deleteItemAsync(key);
    } catch {
      return AsyncStorage.removeItem(key);
    }
  },
};

const buildUrl = (path) => {
  const base = API_CONFIG.djangoBaseUrl.replace(/\/+$/, '');
  const cleanPath = String(path || '').replace(/^\/+/, '');
  return `${base}/${cleanPath}`;
};

const parseResponse = async (response) => {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
};

export const getBecasToken = () => storage.getItem(TOKEN_KEY);

export const getStoredBecasUser = async () => {
  const raw = await storage.getItem(USER_DATA_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const clearBecasSession = async () => {
  await Promise.all([
    storage.deleteItem(TOKEN_KEY),
    storage.deleteItem(USER_DATA_KEY),
    storage.deleteItem(USER_ID_KEY),
  ]);
};

export const loginBecas = async ({ username, password }) => {
  const response = await fetch(buildUrl('/api/becas/auth/token/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const payload = await parseResponse(response);
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.non_field_errors?.[0] || 'No se pudo iniciar sesion.');
  }

  const user = {
    id: payload.user_id,
    username: payload.username,
    nombre: payload.username,
    grupos: [],
    es_admin: false,
  };
  await Promise.all([
    storage.setItem(TOKEN_KEY, payload.token),
    storage.setItem(USER_ID_KEY, String(payload.user_id)),
    storage.setItem(USER_DATA_KEY, JSON.stringify(user)),
  ]);
  return user;
};

// Sube un archivo real (multipart) a un endpoint de la API de Becas — a diferencia
// de becasRequest, no serializa el body a JSON: FormData con {uri, name, type}
// es el formato que espera fetch de React Native para adjuntar un archivo local.
export const becasUploadFile = async (path, { fileUri, fileField = 'archivo', fileName, mimeType = 'image/jpeg', fields = {} } = {}) => {
  const token = await getBecasToken();
  const formData = new FormData();
  Object.entries(fields).forEach(([key, value]) => {
    if (value !== null && value !== undefined) formData.append(key, String(value));
  });
  formData.append(fileField, {
    uri: fileUri,
    name: fileName || fileUri.split('/').pop() || 'archivo.jpg',
    type: mimeType,
  });

  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    body: formData,
  });
  const payload = await parseResponse(response);
  if (!response.ok) {
    const error = new Error(payload?.detail || payload?.non_field_errors?.[0] || `Error HTTP ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
};

export const becasRequest = async (path, options = {}) => {
  const token = await getBecasToken();
  const headers = {
    Accept: 'application/json',
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(token ? { Authorization: `Token ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(buildUrl(path), {
    ...options,
    headers,
    body: options.body && typeof options.body !== 'string'
      ? JSON.stringify(options.body)
      : options.body,
  });
  const payload = await parseResponse(response);
  if (!response.ok) {
    const error = new Error(payload?.detail || payload?.error || `Error HTTP ${response.status}`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
};
