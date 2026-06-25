import Constants from 'expo-constants';
import { Platform } from 'react-native';

const normalizeBaseUrl = (value = '') => String(value || '').trim().replace(/\/+$/, '');

const deriveDevDjangoUrl = () => {
  const configured = normalizeBaseUrl(Constants.expoConfig?.extra?.djangoApiUrl);
  if (configured) return configured;

  if (Platform.OS === 'web') return 'http://localhost:8000';

  const hostUri = Constants.expoConfig?.hostUri || Constants.manifest2?.extra?.expoClient?.hostUri || '';
  const host = String(hostUri).split(':')[0];
  return host ? `http://${host}:8000` : 'http://localhost:8000';
};

export const API_CONFIG = {
  djangoBaseUrl: deriveDevDjangoUrl(),
};
