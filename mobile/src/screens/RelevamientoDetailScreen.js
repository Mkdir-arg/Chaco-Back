import React, { useEffect, useMemo, useRef, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, ActivityIndicator, Image, Pressable, Alert, Modal, TextInput, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';
import * as FileSystemLegacy from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';
import * as WebBrowser from 'expo-web-browser';
import { useTheme } from '../context/ThemeContext';
import Banner from '../components/Banner';
import relevamientoService from '../services/relevamientoService';
import { supabase } from '../config/supabaseConfig';
import { API_CONFIG } from '../config/apiConfig';
import { designColors, fontSizes, radii } from '../theme';

const formatDate = (isoDate) => {
  if (!isoDate) return '-';
  try {
    return new Date(isoDate).toLocaleString('es-AR', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoDate;
  }
};

const emptyDniForm = {
  dni_numero: '',
  dni_sexo: '',
  dni_tramite: '',
  apellido: '',
  nombres: '',
  fecha_nacimiento: '',
  ejemplar: '',
  fecha_emision: '',
};

const RENAPER_RESET_FIELDS = ['dni_numero', 'dni_sexo', 'apellido', 'nombres', 'fecha_nacimiento'];

export default function RelevamientoDetailScreen({ relevamientoId, onClose, syncStatus = 'synced', syncPendingCount = 0, onSyncPress }) {
  const { theme, typography } = useTheme();
  const insets = useSafeAreaInsets();
  const [activeTab, setActiveTab] = useState('RESUMEN');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [detail, setDetail] = useState(null);
  const [imageUrls, setImageUrls] = useState({});
  const [mapProviderIndex, setMapProviderIndex] = useState(0);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewUri, setPreviewUri] = useState('');
  const [previewName, setPreviewName] = useState('');
  const [sharingId, setSharingId] = useState('');
  const [cameraPermission, requestCameraPermission] = useCameraPermissions();
  const [scannerVisible, setScannerVisible] = useState(false);
  const [scannerLocked, setScannerLocked] = useState(false);
  const [scannerCameraKey, setScannerCameraKey] = useState(0);
  const [currentStep, setCurrentStep] = useState(1);
  const [maxVisitedStep, setMaxVisitedStep] = useState(1);
  const [renaperStatus, setRenaperStatus] = useState('PENDIENTE');
  const [renaperLoading, setRenaperLoading] = useState(false);
  const [renaperResult, setRenaperResult] = useState(null);
  const [renaperError, setRenaperError] = useState('');
  const [dniForm, setDniForm] = useState(emptyDniForm);
  const [dniPhotos, setDniPhotos] = useState({ frente: null, dorso: null });
  const [dynamicValues, setDynamicValues] = useState({});
  const modernScannerSubscriptionRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      const result = await relevamientoService.getRelevamientoDetail(relevamientoId);
      if (!mounted) return;
      if (!result.success) {
        setError(result.error || 'No se pudo cargar el detalle.');
      } else {
        setDetail(result.detail);
        const persona = result.detail?.persona || {};
        setDniForm({
          ...emptyDniForm,
          dni_numero: persona.dni_numero || '',
          dni_sexo: persona.dni_sexo || '',
          dni_tramite: persona.dni_tramite || '',
          apellido: persona.apellido || '',
          nombres: persona.nombres || '',
          fecha_nacimiento: persona.fecha_nacimiento || '',
          ejemplar: persona.ejemplar || '',
          fecha_emision: persona.fecha_emision || '',
        });
        setRenaperStatus(persona.renaper_estado || 'PENDIENTE');
        const responseValues = {};
        (result.detail?.campos_extra || []).forEach((item) => {
          responseValues[item.id] = item.valor || '';
        });
        setDynamicValues(responseValues);
      }
      setLoading(false);
    })();
    return () => { mounted = false; };
  }, [relevamientoId]);

  useEffect(() => () => {
    modernScannerSubscriptionRef.current?.remove?.();
    modernScannerSubscriptionRef.current = null;
  }, []);

  const readValue = (...keys) => {
    for (const key of keys) {
      const value = detail?.[key] ?? detail?.payload?.[key];
      if (value !== undefined && value !== null && String(value).trim() !== '') {
        return String(value);
      }
    }
    return '-';
  };

  const assignedSteps = [
    { id: 1, title: 'DNI', icon: 'card-outline' },
    { id: 2, title: 'Fotos', icon: 'camera-outline' },
    { id: 3, title: 'RENAPER', icon: 'shield-checkmark-outline' },
    { id: 4, title: 'Campos', icon: 'list-outline' },
    { id: 5, title: 'Confirmar', icon: 'checkmark-circle-outline' },
  ];

  const isAssignedFlow = detail?.source === 'asignado';

  const updateDniField = (key, value) => {
    setDniForm((prev) => ({ ...prev, [key]: value }));
    if (RENAPER_RESET_FIELDS.includes(key)) {
      setRenaperStatus('PENDIENTE');
      setRenaperResult(null);
      setRenaperError('');
    }
  };

  const cleanDigits = (value = '') => String(value || '').replace(/\D/g, '');

  const normalizeToken = (value = '') =>
    String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '');

  const normalizeSex = (value = '') => {
    const normalized = String(value || '').trim().toUpperCase();
    if (['M', 'F', 'X'].includes(normalized)) return normalized;
    if (normalized === '1') return 'M';
    if (normalized === '2') return 'F';
    if (normalized === '0' || normalized === '3') return 'X';
    if (normalized.startsWith('MASC')) return 'M';
    if (normalized.startsWith('FEM')) return 'F';
    return '';
  };

  const normalizeDateText = (value = '') => {
    const text = String(value || '').trim();
    if (!text) return '';
    const iso = text.match(/^(\d{4})[-/](\d{2})[-/](\d{2})/);
    if (iso) return `${iso[3]}/${iso[2]}/${iso[1]}`;
    const local = text.match(/^(\d{2})[-/](\d{2})[-/](\d{4})$/);
    if (local) return `${local[1]}/${local[2]}/${local[3]}`;
    const shortLocal = text.match(/^(\d{2})[-/](\d{2})[-/](\d{2})$/);
    if (shortLocal) {
      const currentYear = new Date().getFullYear();
      const currentShortYear = currentYear % 100;
      const shortYear = Number(shortLocal[3]);
      const fullYear = shortYear <= currentShortYear ? 2000 + shortYear : 1900 + shortYear;
      return `${shortLocal[1]}/${shortLocal[2]}/${fullYear}`;
    }
    const compact = text.match(/^(\d{8})$/);
    if (compact) {
      const valueDigits = compact[1];
      const yearFirst = Number(valueDigits.slice(0, 4));
      const dayFirst = Number(valueDigits.slice(0, 2));
      const monthFirst = Number(valueDigits.slice(2, 4));
      const yearLast = Number(valueDigits.slice(4, 8));
      if (yearFirst >= 1900 && yearFirst <= 2099) {
        return `${valueDigits.slice(6, 8)}/${valueDigits.slice(4, 6)}/${valueDigits.slice(0, 4)}`;
      }
      if (dayFirst >= 1 && dayFirst <= 31 && monthFirst >= 1 && monthFirst <= 12 && yearLast >= 1900 && yearLast <= 2099) {
        return `${valueDigits.slice(0, 2)}/${valueDigits.slice(2, 4)}/${valueDigits.slice(4, 8)}`;
      }
    }
    return text;
  };

  const decodeDniPart = (value = '') => {
    const text = String(value || '').trim();
    try {
      return decodeURIComponent(text.replace(/\+/g, ' ')).trim();
    } catch {
      return text;
    }
  };

  const normalizeDniDateField = (value = '') => {
    const text = decodeDniPart(value);
    if (/^\d{2}[-/]\d{2}[-/]\d{2,4}$/.test(text) || /^\d{4}[-/]\d{2}[-/]\d{2}/.test(text) || /^\d{8}$/.test(text)) {
      return normalizeDateText(text);
    }
    return '';
  };

  const normalizeCompareText = (value = '') =>
    String(value || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toUpperCase()
      .replace(/[^A-Z0-9]/g, '');

  const normalizeCompareDate = (value = '') => normalizeCompareText(normalizeDateText(value));

  const buildRenaperComparisons = (renaperData = {}) => ([
    {
      key: 'dni',
      label: 'Numero de DNI',
      documentValue: cleanDigits(dniForm.dni_numero),
      renaperValue: cleanDigits(renaperData.dni),
      matches: cleanDigits(dniForm.dni_numero) === cleanDigits(renaperData.dni),
    },
    {
      key: 'apellido',
      label: 'Apellido',
      documentValue: dniForm.apellido,
      renaperValue: renaperData.apellido,
      matches: normalizeCompareText(dniForm.apellido) === normalizeCompareText(renaperData.apellido),
    },
    {
      key: 'nombre',
      label: 'Nombre',
      documentValue: dniForm.nombres,
      renaperValue: renaperData.nombre,
      matches: normalizeCompareText(dniForm.nombres) === normalizeCompareText(renaperData.nombre),
    },
    {
      key: 'fecha_nacimiento',
      label: 'Fecha de nacimiento',
      documentValue: dniForm.fecha_nacimiento,
      renaperValue: normalizeDateText(renaperData.fecha_nacimiento),
      matches: normalizeCompareDate(dniForm.fecha_nacimiento) === normalizeCompareDate(renaperData.fecha_nacimiento),
    },
    {
      key: 'sexo',
      label: 'Sexo',
      documentValue: normalizeSex(dniForm.dni_sexo),
      renaperValue: normalizeSex(renaperData.sexo),
      matches: normalizeSex(dniForm.dni_sexo) === normalizeSex(renaperData.sexo),
    },
  ]);

  const escapeRegExp = (value = '') => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

  const getParamValue = (text, keys) => {
    for (const key of keys) {
      const safeKey = escapeRegExp(key);
      const match = text.match(new RegExp(`(?:^|[?&;#\\s])${safeKey}=([^&#;\\s]+)`, 'i'));
      if (match?.[1]) return decodeURIComponent(match[1].replace(/\+/g, ' '));
      const looseMatch = text.match(new RegExp(`${safeKey}\\s*[:=]\\s*([^|@;\\n\\r]+)`, 'i'));
      if (looseMatch?.[1]) return decodeURIComponent(looseMatch[1].trim().replace(/\+/g, ' '));
    }
    return '';
  };

  const flattenObject = (source, target = {}) => {
    Object.entries(source || {}).forEach(([key, value]) => {
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        flattenObject(value, target);
        return;
      }
      target[normalizeToken(key)] = value;
    });
    return target;
  };

  const getObjectValue = (source, keys) => {
    const flat = flattenObject(source);
    for (const key of keys) {
      const value = flat[normalizeToken(key)];
      if (value !== undefined && value !== null && String(value).trim() !== '') return String(value).trim();
    }
    return '';
  };

  const mapDniFields = (source) => ({
    dni_numero: cleanDigits(getObjectValue(source, ['dni', 'documento', 'numeroDocumento', 'numero_documento', 'nroDocumento', 'nro_doc', 'documentNumber'])),
    dni_sexo: normalizeSex(getObjectValue(source, ['sexo', 'gender', 'sex'])),
    dni_tramite: cleanDigits(getObjectValue(source, ['tramite', 'id_tramite', 'numeroTramite', 'numero_tramite', 'nroTramite', 'numTramite', 'transactionNumber'])),
    apellido: getObjectValue(source, ['apellido', 'apellidos', 'lastName', 'surname']),
    nombres: getObjectValue(source, ['nombres', 'nombre', 'firstName', 'givenName']),
    fecha_nacimiento: normalizeDniDateField(getObjectValue(source, ['fechaNacimiento', 'fecha_nacimiento', 'nacimiento', 'birthDate'])),
    ejemplar: getObjectValue(source, ['ejemplar', 'copy', 'version']).toUpperCase(),
    fecha_emision: normalizeDniDateField(getObjectValue(source, ['fechaEmision', 'fecha_emision', 'emision', 'issueDate'])),
  });

  const stripEmptyValues = (source = {}) => {
    const result = {};
    Object.entries(source).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value).trim() !== '') {
        result[key] = String(value).trim();
      }
    });
    return result;
  };

  const parseDniCode = (rawValue = '', barcodeType = '') => {
    const raw = String(rawValue || '').trim();
    if (!raw) return {};

    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object') {
        return stripEmptyValues(mapDniFields(parsed));
      }
    } catch {
      // El QR puede venir como URL o texto plano, seguimos con parsers tolerantes.
    }

    const paramResult = stripEmptyValues({
      dni_numero: cleanDigits(getParamValue(raw, ['dni', 'documento', 'numeroDocumento', 'numero_documento', 'nroDocumento', 'nro_doc'])),
      dni_sexo: normalizeSex(getParamValue(raw, ['sexo', 'gender', 'sex'])),
      dni_tramite: cleanDigits(getParamValue(raw, ['tramite', 'id_tramite', 'numeroTramite', 'numero_tramite', 'nroTramite', 'numTramite', 'transactionNumber'])),
      apellido: getParamValue(raw, ['apellido', 'apellidos', 'lastName', 'surname']).trim(),
      nombres: getParamValue(raw, ['nombres', 'nombre', 'firstName', 'givenName']).trim(),
      fecha_nacimiento: normalizeDniDateField(getParamValue(raw, ['fechaNacimiento', 'fecha_nacimiento', 'nacimiento', 'birthDate'])),
      ejemplar: getParamValue(raw, ['ejemplar', 'copy', 'version']).trim().toUpperCase(),
      fecha_emision: normalizeDniDateField(getParamValue(raw, ['fechaEmision', 'fecha_emision', 'emision', 'issueDate'])),
    });
    if (Object.values(paramResult).some(Boolean)) return paramResult;

    const separator = raw.includes('@') ? '@' : (raw.includes('|') ? '|' : null);
    if (separator) {
      const parts = raw.split(separator).map(decodeDniPart);
      const compactParts = parts.filter(Boolean);
      const codeType = String(barcodeType || '').toUpperCase();
      const looksLikePdf417 = codeType.includes('PDF417') || (parts.length >= 8 && /^\d{1,2}$/.test(parts[3]) && /^\d{7,8}$/.test(cleanDigits(parts[4])));
      const looksLikeQr = codeType.includes('QR') || (parts.length >= 8 && /^\d{7,8}$/.test(cleanDigits(parts[3])));

      if (separator === '@' && looksLikePdf417) {
        return stripEmptyValues({
          dni_tramite: cleanDigits(parts[0]),
          apellido: parts[1] || '',
          nombres: parts[2] || '',
          dni_sexo: normalizeSex(parts[3]),
          dni_numero: cleanDigits(parts[4]),
          ejemplar: (parts[5] || '').toUpperCase(),
          fecha_nacimiento: normalizeDniDateField(parts[6]),
          fecha_emision: normalizeDniDateField(parts[7]),
        });
      }

      if (separator === '@' && looksLikeQr) {
        return stripEmptyValues({
          dni_tramite: cleanDigits(parts[0]),
          apellido: parts[1] || '',
          nombres: parts[2] || '',
          dni_numero: cleanDigits(parts[3]),
          ejemplar: (parts[4] || '').toUpperCase(),
          fecha_nacimiento: normalizeDniDateField(parts[5]),
          fecha_emision: normalizeDniDateField(parts[6]),
        });
      }

      const dniIndex = compactParts.findIndex((part) => /^\d{7,8}$/.test(cleanDigits(part)));
      const sexoIndex = compactParts.findIndex((part) => ['M', 'F', 'X', '1', '2', '3'].includes(part.toUpperCase()));
      const dates = compactParts.filter((part) => /^\d{2}\/\d{2}\/\d{4}$/.test(part) || /^\d{4}-\d{2}-\d{2}$/.test(part) || /^\d{8}$/.test(part));
      return stripEmptyValues({
        apellido: compactParts[1] || '',
        nombres: compactParts[2] || '',
        dni_sexo: sexoIndex >= 0 ? normalizeSex(compactParts[sexoIndex]) : '',
        dni_numero: dniIndex >= 0 ? cleanDigits(compactParts[dniIndex]) : '',
        dni_tramite: cleanDigits(compactParts.find((part) => /^\d{10,12}$/.test(cleanDigits(part))) || ''),
        fecha_nacimiento: normalizeDniDateField(dates[0]),
        fecha_emision: normalizeDniDateField(dates[1]),
      });
    }

    const dniMatch = raw.match(/\b\d{7,8}\b/);
    return { dni_numero: dniMatch?.[0] || '' };
  };

  const applyDniScanResult = (scanData = {}) => {
    const nextForm = {};
    Object.entries(scanData).forEach(([key, value]) => {
      if (value !== undefined && value !== null && String(value).trim() !== '') {
        nextForm[key] = String(value).trim();
      }
    });
    if (!Object.keys(nextForm).length) {
      Alert.alert('DNI', 'No pude leer datos utiles del codigo. Probemos manualmente.');
      setScannerLocked(false);
      return;
    }
    setDniForm((prev) => ({ ...prev, ...nextForm }));
    setRenaperStatus('PENDIENTE');
    setRenaperResult(null);
    setRenaperError('');
    closeDniScanner();
  };

  const getBarcodeTypeLabel = (type = '') => {
    const normalized = String(type || '').toLowerCase();
    if (normalized.includes('pdf417')) return 'PDF417';
    if (normalized.includes('qr')) return 'QR';
    return type ? String(type).toUpperCase() : 'DESCONOCIDO';
  };

  const openDniScanner = async () => {
    if (!cameraPermission?.granted) {
      const response = await requestCameraPermission();
      if (!response?.granted) {
        Alert.alert('Camara', 'Necesitamos permiso de camara para escanear el DNI.');
        return;
      }
    }
    setScannerLocked(false);
    if (Platform.OS === 'ios' && CameraView.isModernBarcodeScannerAvailable) {
      try {
        modernScannerSubscriptionRef.current?.remove?.();
        modernScannerSubscriptionRef.current = CameraView.onModernBarcodeScanned((event) => {
          modernScannerSubscriptionRef.current?.remove?.();
          modernScannerSubscriptionRef.current = null;
          CameraView.dismissScanner?.().catch?.(() => {});
          handleDniBarcodeScanned(event);
        });
        await CameraView.launchScanner({
          barcodeTypes: ['qr', 'pdf417'],
          isGuidanceEnabled: false,
          isHighlightingEnabled: true,
          isPinchToZoomEnabled: true,
        });
        return;
      } catch {
        modernScannerSubscriptionRef.current?.remove?.();
        modernScannerSubscriptionRef.current = null;
      }
    }
    setScannerCameraKey((prev) => prev + 1);
    setScannerVisible(true);
  };

  const closeDniScanner = () => {
    modernScannerSubscriptionRef.current?.remove?.();
    modernScannerSubscriptionRef.current = null;
    if (Platform.OS === 'ios') {
      CameraView.dismissScanner?.().catch?.(() => {});
    }
    setScannerVisible(false);
    setScannerLocked(false);
  };

  const handleDniBarcodeScanned = ({ data, type }) => {
    if (scannerLocked) return;
    setScannerLocked(true);
    applyDniScanResult(parseDniCode(data, getBarcodeTypeLabel(type)));
  };

  const openDniPhotoCamera = async (target) => {
    try {
      const permission = await ImagePicker.getCameraPermissionsAsync();
      const granted = permission?.granted || (await ImagePicker.requestCameraPermissionsAsync())?.granted;
      if (!granted) {
        Alert.alert('Camara', 'Necesitamos permiso de camara para tomar fotos del DNI.');
        return;
      }
      const result = await ImagePicker.launchCameraAsync({
        mediaTypes: 'images',
        allowsEditing: false,
        quality: 0.86,
      });
      if (result?.canceled) return;
      const asset = result?.assets?.[0];
      if (!asset?.uri) throw new Error('No se pudo guardar la foto.');
      setDniPhotos((prev) => ({
        ...prev,
        [target]: {
          uri: asset.uri,
          width: asset.width,
          height: asset.height,
          capturedAt: new Date().toISOString(),
        },
      }));
    } catch (e) {
      Alert.alert('Foto DNI', e?.message || 'No se pudo tomar la foto.');
    }
  };

  const openDniPhotoPreview = (target, label) => {
    const photo = dniPhotos[target];
    if (!photo?.uri) {
      openDniPhotoCamera(target);
      return;
    }
    setPreviewUri(photo.uri);
    setPreviewName(label);
    setPreviewVisible(true);
  };

  const getMissingDniFields = () => {
    const required = [
      ['dni_numero', 'Numero de DNI'],
      ['apellido', 'Apellido'],
      ['nombres', 'Nombre'],
      ['fecha_nacimiento', 'Fecha de nacimiento'],
      ['dni_sexo', 'Sexo'],
    ];
    return required
      .filter(([key]) => !String(dniForm[key] || '').trim())
      .map(([, label]) => label);
  };

  const nextAssignedStep = () => {
    if (currentStep === 1) {
      const missing = getMissingDniFields();
      if (missing.length) {
        Alert.alert('Datos del DNI', `Completa antes de continuar: ${missing.join(', ')}.`);
        return;
      }
    }
    if (currentStep === 2 && (!dniPhotos.frente?.uri || !dniPhotos.dorso?.uri)) {
      Alert.alert('Fotos DNI', 'Carga la foto del frente y del dorso del DNI para continuar.');
      return;
    }
    if (currentStep === 3 && !['VALIDADO', 'NO_COINCIDE'].includes(renaperStatus)) {
      Alert.alert('RENAPER', 'Realiza la validacion RENAPER antes de continuar.');
      return;
    }
    if (currentStep < assignedSteps.length) {
      const next = currentStep + 1;
      setCurrentStep(next);
      setMaxVisitedStep((prev) => Math.max(prev, next));
    }
  };

  const prevAssignedStep = () => {
    if (currentStep > 1) setCurrentStep((prev) => prev - 1);
  };

  const validateRenaper = async () => {
    if (!dniForm.dni_numero.trim() || !dniForm.dni_sexo.trim()) {
      Alert.alert('RENAPER', 'Completa DNI y sexo para validar.');
      return;
    }

    setRenaperLoading(true);
    setRenaperError('');
    setRenaperStatus('VALIDANDO');

    try {
      const response = await fetch(`${API_CONFIG.djangoBaseUrl}/api/legajos/renaper/consultar/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dni: cleanDigits(dniForm.dni_numero),
          sexo: normalizeSex(dniForm.dni_sexo),
        }),
      });
      const responseText = await response.text();
      let payload = {};
      try {
        payload = responseText ? JSON.parse(responseText) : {};
      } catch {
        payload = {};
      }
      if (!response.ok || !payload?.success) {
        throw new Error(payload?.error || `No se pudo consultar RENAPER (${response.status}).`);
      }

      const renaperData = payload.data || {};
      const comparisons = buildRenaperComparisons(renaperData);
      const allMatch = comparisons.every((item) => item.matches);
      setRenaperResult({
        data: renaperData,
        comparisons,
        checkedAt: new Date().toISOString(),
      });
      setRenaperStatus(allMatch ? 'VALIDADO' : 'NO_COINCIDE');
    } catch (e) {
      setRenaperStatus('ERROR');
      setRenaperResult(null);
      setRenaperError(e?.message || 'No se pudo consultar RENAPER.');
    } finally {
      setRenaperLoading(false);
    }
  };

  const parseOptions = (options) => {
    if (Array.isArray(options)) return options;
    try {
      const parsed = JSON.parse(options || '[]');
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  };

  const renderDynamicField = (field) => {
    const value = dynamicValues[field.id] || '';
    const options = parseOptions(field.opciones);
    const setValue = (nextValue) => setDynamicValues((prev) => ({ ...prev, [field.id]: nextValue }));

    if (field.tipo === 'select' || field.tipo === 'choice') {
      return (
        <View key={field.id} style={styles.formGroup}>
          <Text style={[styles.inputLabel, { color: theme.colors.text, fontFamily: typography.semibold }]}>
            {field.etiqueta}{field.requerido ? ' *' : ''}
          </Text>
          <View style={styles.optionWrap}>
            {options.map((option) => {
              const selected = value === option;
              return (
                <Pressable
                  key={option}
                  onPress={() => setValue(option)}
                  style={[
                    styles.optionChip,
                    { borderColor: theme.colors.border, backgroundColor: theme.colors.surface },
                    selected && { borderColor: theme.colors.primary, backgroundColor: `${theme.colors.primary}18` },
                  ]}
                >
                  <Text style={[styles.optionText, { color: selected ? theme.colors.primary : theme.colors.text, fontFamily: selected ? typography.bold : typography.medium }]}>
                    {option}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      );
    }

    if (field.tipo === 'archivo') {
      return (
        <View key={field.id} style={styles.formGroup}>
          <Text style={[styles.inputLabel, { color: theme.colors.text, fontFamily: typography.semibold }]}>
            {field.etiqueta}{field.requerido ? ' *' : ''}
          </Text>
          <View style={[styles.filePlaceholder, { borderColor: theme.colors.border, backgroundColor: theme.colors.surfaceAlt }]}>
            <Ionicons name="cloud-upload-outline" size={22} color={theme.colors.icon} />
            <Text style={[styles.filePlaceholderText, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
              Adjuntos disponibles en el siguiente paso de implementacion
            </Text>
          </View>
        </View>
      );
    }

    return (
      <View key={field.id} style={styles.formGroup}>
        <Text style={[styles.inputLabel, { color: theme.colors.text, fontFamily: typography.semibold }]}>
          {field.etiqueta}{field.requerido ? ' *' : ''}
        </Text>
        <TextInput
          value={value}
          onChangeText={setValue}
          multiline={field.tipo === 'textarea'}
          keyboardType={field.tipo === 'numero' ? 'numeric' : 'default'}
          style={[
            styles.textInput,
            field.tipo === 'textarea' && styles.textArea,
            { color: theme.colors.text, borderColor: theme.colors.border, backgroundColor: theme.colors.surface },
          ]}
          placeholderTextColor={theme.colors.textSoft}
          placeholder="Completar"
        />
      </View>
    );
  };

  const signaturePaths = useMemo(
    () => detail?.firma_paths || detail?.payload?.firma_paths || [],
    [detail]
  );

  const attachments = detail?.adjuntos || [];
  const imageAttachments = attachments.filter((item) => item.tipo_archivo === 'IMAGEN');
  const docAttachments = attachments.filter((item) => item.tipo_archivo !== 'IMAGEN');
  const lat = readValue('latitud');
  const lng = readValue('longitud');
  const hasGeo = lat !== '-' && lng !== '-';
  const mapPreviewUrls = hasGeo
    ? [
      `https://staticmap.openstreetmap.de/staticmap.php?center=${lat},${lng}&zoom=16&size=800x420&markers=${lat},${lng},red-pushpin`,
      `https://static-maps.yandex.ru/1.x/?ll=${lng},${lat}&size=650,300&z=16&l=map&pt=${lng},${lat},pm2rdm&lang=es_ES`,
    ]
    : [];
  const mapPreviewUrl = mapPreviewUrls[mapProviderIndex] || null;

  const getSignatureBounds = (paths) => {
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    paths.forEach((path) => {
      const nums = path.match(/-?\d+(\.\d+)?/g);
      if (!nums) return;
      for (let i = 0; i < nums.length; i += 2) {
        const x = parseFloat(nums[i]);
        const y = parseFloat(nums[i + 1]);
        if (Number.isNaN(x) || Number.isNaN(y)) continue;
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    });
    if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) return null;
    return { minX, minY, width: Math.max(1, maxX - minX), height: Math.max(1, maxY - minY) };
  };

  const getCenteredSignaturePaths = (paths, targetWidth = 320, targetHeight = 190, padding = 14) => {
    const bounds = getSignatureBounds(paths);
    if (!bounds) return paths;
    const scaleX = (targetWidth - padding * 2) / bounds.width;
    const scaleY = (targetHeight - padding * 2) / bounds.height;
    const scale = Math.min(scaleX, scaleY);
    const offsetX = (targetWidth - bounds.width * scale) / 2 - bounds.minX * scale;
    const offsetY = (targetHeight - bounds.height * scale) / 2 - bounds.minY * scale;
    return paths.map((path) =>
      path.replace(/(-?\d+(\.\d+)?),(-?\d+(\.\d+)?)/g, (_, x, __, y) => {
        const nx = parseFloat(x) * scale + offsetX;
        const ny = parseFloat(y) * scale + offsetY;
        return `${nx.toFixed(2)},${ny.toFixed(2)}`;
      })
    );
  };

  useEffect(() => {
    let mounted = true;
    const resolveImageUris = async () => {
      const nextMap = {};
      for (const item of imageAttachments) {
        const raw = item.storage_path || '';
        if (!raw) continue;
        if (raw.startsWith('http://') || raw.startsWith('https://') || raw.startsWith('file://') || raw.startsWith('content://')) {
          nextMap[item.id || raw] = raw;
          continue;
        }
        try {
          const { data } = await supabase.storage.from(item.storage_bucket || 'relevamientos').createSignedUrl(raw, 3600);
          if (data?.signedUrl) nextMap[item.id || raw] = data.signedUrl;
        } catch {
          // ignore
        }
      }
      if (mounted) setImageUrls(nextMap);
    };
    resolveImageUris();
    return () => { mounted = false; };
  }, [detail]);

  const resolveAttachmentUrl = async (item) => {
    const raw = item?.storage_path || '';
    if (!raw) return '';
    if (
      raw.startsWith('http://') ||
      raw.startsWith('https://') ||
      raw.startsWith('file://') ||
      raw.startsWith('content://')
    ) {
      return encodeURI(raw);
    }
    const { data } = await supabase.storage
      .from(item.storage_bucket || 'relevamientos')
      .createSignedUrl(raw, 3600);
    return data?.signedUrl || '';
  };

  const sanitizeFileName = (name = 'archivo') =>
    String(name).replace(/[\\/:*?"<>|]/g, '_').trim() || `archivo_${Date.now()}`;

  const openImagePreview = async (item) => {
    try {
      const url = imageUrls[item.id || item.storage_path] || await resolveAttachmentUrl(item);
      if (!url) throw new Error('No se pudo abrir la imagen');
      setPreviewUri(url);
      setPreviewName(item?.nombre_original || 'Imagen');
      setPreviewVisible(true);
    } catch (e) {
      Alert.alert('Imagen', e?.message || 'No se pudo abrir la imagen');
    }
  };

  const previewDocumentInApp = async (item) => {
    try {
      const url = await resolveAttachmentUrl(item);
      if (!url) throw new Error('No se pudo abrir el documento');
      await WebBrowser.openBrowserAsync(url, { showTitle: true, enableDefaultShareMenuItem: false });
    } catch (e) {
      Alert.alert('Documento', e?.message || 'No se pudo abrir el documento');
    }
  };

  const shareAttachment = async (item) => {
    const id = String(item?.id || item?.storage_path || Math.random());
    try {
      setSharingId(id);
      const canShare = await Sharing.isAvailableAsync();
      if (!canShare) throw new Error('Compartir no disponible en este dispositivo');
      const url = await resolveAttachmentUrl(item);
      if (!url) throw new Error('Adjunto sin URL');
      const fileName = sanitizeFileName(item?.nombre_original || 'adjunto');
      const localUri = `${FileSystemLegacy.cacheDirectory}${Date.now()}_${fileName}`;
      const result = await FileSystemLegacy.downloadAsync(url, localUri);
      if (!result?.uri) throw new Error('No se pudo preparar el archivo');
      await Sharing.shareAsync(result.uri);
    } catch (e) {
      Alert.alert('Compartir', e?.message || 'No se pudo compartir el adjunto');
    } finally {
      setSharingId('');
    }
  };

  const tabs = ['RESUMEN', 'ADJUNTOS', 'FIRMA'];
  const createdDateLabel = formatDate(detail?.created_at || detail?.relevado_at);
  const syncedDateLabel = detail?.last_synced_at
    ? formatDate(detail?.last_synced_at)
    : (readValue('sync_estado') === 'SINCRONIZADO' ? formatDate(detail?.created_at) : 'Pendiente');

  const renderDniInput = (label, key, placeholder = '', keyboardType = 'default') => (
    <View style={styles.formGroup}>
      <Text style={[styles.inputLabel, { color: theme.colors.text, fontFamily: typography.semibold }]}>{label}</Text>
      <TextInput
        value={dniForm[key] || ''}
        onChangeText={(value) => updateDniField(key, value)}
        keyboardType={keyboardType}
        style={[styles.textInput, { color: theme.colors.text, borderColor: theme.colors.border, backgroundColor: theme.colors.surface }]}
        placeholder={placeholder}
        placeholderTextColor={theme.colors.textSoft}
        autoCapitalize={['apellido', 'nombres'].includes(key) ? 'words' : 'none'}
      />
    </View>
  );

  const renderAssignedStepContent = () => {
    if (currentStep === 1) {
      return (
        <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
          <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Datos del DNI</Text>
          <Text style={[styles.stepHelp, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
            Carga los datos visibles del documento. Las fotos de frente y dorso quedan como obligatorias para el flujo final.
          </Text>
          <TouchableOpacity onPress={openDniScanner} style={[styles.scanAction, { backgroundColor: theme.colors.primary }]}>
            <Ionicons name="scan-outline" size={18} color="#FFFFFF" />
            <Text style={[styles.scanActionText, { fontFamily: typography.bold }]}>ESCANEAR DNI</Text>
          </TouchableOpacity>
          <Text style={[styles.scanHint, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
            Lee QR de DNI nuevo y PDF417 de DNI anterior.
          </Text>
          <Text style={[styles.formSectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Identidad</Text>
          {renderDniInput('Apellido', 'apellido', 'Ej: Perez')}
          {renderDniInput('Nombres', 'nombres', 'Ej: Juan Carlos')}
          <View style={styles.formGroup}>
            <Text style={[styles.inputLabel, { color: theme.colors.text, fontFamily: typography.semibold }]}>Numero de DNI *</Text>
            <TextInput
              value={dniForm.dni_numero}
              onChangeText={(value) => updateDniField('dni_numero', value)}
              keyboardType="number-pad"
              style={[styles.textInput, { color: theme.colors.text, borderColor: theme.colors.border, backgroundColor: theme.colors.surface }]}
              placeholder="Ej: 30111222"
              placeholderTextColor={theme.colors.textSoft}
            />
          </View>
          {renderDniInput('Fecha de nacimiento', 'fecha_nacimiento', 'DD/MM/AAAA')}
          <Text style={[styles.formSectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Documento</Text>
          <View style={styles.formGroup}>
            <Text style={[styles.inputLabel, { color: theme.colors.text, fontFamily: typography.semibold }]}>Sexo DNI *</Text>
            <View style={styles.optionWrap}>
              {['M', 'F', 'X'].map((option) => {
                const selected = dniForm.dni_sexo === option;
                return (
                  <Pressable
                    key={option}
                    onPress={() => updateDniField('dni_sexo', option)}
                    style={[
                      styles.optionChip,
                      { borderColor: theme.colors.border, backgroundColor: theme.colors.surface },
                      selected && { borderColor: theme.colors.primary, backgroundColor: `${theme.colors.primary}18` },
                    ]}
                  >
                    <Text style={[styles.optionText, { color: selected ? theme.colors.primary : theme.colors.text, fontFamily: selected ? typography.bold : typography.medium }]}>
                      {option}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
          </View>
          <View style={styles.formGroup}>
            <Text style={[styles.inputLabel, { color: theme.colors.text, fontFamily: typography.semibold }]}>Numero de tramite</Text>
            <TextInput
              value={dniForm.dni_tramite}
              onChangeText={(value) => updateDniField('dni_tramite', value)}
              keyboardType="number-pad"
              style={[styles.textInput, { color: theme.colors.text, borderColor: theme.colors.border, backgroundColor: theme.colors.surface }]}
              placeholder="Opcional"
              placeholderTextColor={theme.colors.textSoft}
            />
          </View>
          {renderDniInput('Ejemplar', 'ejemplar', 'Ej: A')}
          {renderDniInput('Fecha de emision', 'fecha_emision', 'DD/MM/AAAA')}
        </View>
      );
    }

    if (currentStep === 2) {
      const renderPhotoCard = (target, label) => {
        const photo = dniPhotos[target];
        return (
          <View style={[styles.dniCaptureCard, { borderColor: theme.colors.border, backgroundColor: theme.colors.surfaceAlt }]}>
            <TouchableOpacity
              activeOpacity={0.84}
              onPress={() => openDniPhotoPreview(target, label)}
              style={styles.dniCapturePreview}
            >
              {photo?.uri ? (
                <Image source={{ uri: photo.uri }} style={styles.dniCaptureImage} resizeMode="cover" />
              ) : (
                <View style={styles.dniCaptureEmpty}>
                  <Ionicons name="camera-outline" size={28} color={theme.colors.icon} />
                  <Text style={[styles.dniPhotoText, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{label}</Text>
                </View>
              )}
            </TouchableOpacity>
            <TouchableOpacity onPress={() => openDniPhotoCamera(target)} style={[styles.dniCaptureButton, { backgroundColor: theme.colors.primary }]}>
              <Ionicons name={photo?.uri ? 'refresh-outline' : 'camera-outline'} size={17} color="#FFFFFF" />
              <Text style={[styles.dniCaptureButtonText, { fontFamily: typography.bold }]}>
                {photo?.uri ? 'REPETIR FOTO' : 'SACAR FOTO'}
              </Text>
            </TouchableOpacity>
          </View>
        );
      };

      return (
        <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
          <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Fotos del DNI</Text>
          <Text style={[styles.stepHelp, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
            Carga una foto del frente y una del dorso. Quedan guardadas localmente para sincronizarlas al finalizar.
          </Text>
          <View style={styles.dniPhotoRow}>
            {renderPhotoCard('frente', 'DNI frente')}
            {renderPhotoCard('dorso', 'DNI dorso')}
          </View>
        </View>
      );
    }

    if (currentStep === 3) {
      const statusColor = renaperStatus === 'VALIDADO'
        ? theme.colors.success
        : (renaperStatus === 'NO_COINCIDE' || renaperStatus === 'ERROR' ? theme.colors.danger : theme.colors.warning);
      const statusLabel = {
        PENDIENTE: 'Pendiente de validacion',
        VALIDANDO: 'Consultando RENAPER',
        VALIDADO: 'Los datos coinciden',
        NO_COINCIDE: 'Los datos no coinciden',
        ERROR: 'No se pudo validar',
      }[renaperStatus] || 'Pendiente de validacion';
      const statusIcon = renaperStatus === 'VALIDADO'
        ? 'checkmark-circle'
        : (renaperStatus === 'NO_COINCIDE' || renaperStatus === 'ERROR' ? 'alert-circle' : 'time-outline');
      const documentRows = [
        ['Numero de DNI', dniForm.dni_numero],
        ['Apellido', dniForm.apellido],
        ['Nombre', dniForm.nombres],
        ['Fecha de nacimiento', dniForm.fecha_nacimiento],
        ['Sexo', normalizeSex(dniForm.dni_sexo) || dniForm.dni_sexo],
      ];
      const renaperRows = renaperResult?.data ? [
        ['Numero de DNI', renaperResult.data.dni],
        ['Apellido', renaperResult.data.apellido],
        ['Nombre', renaperResult.data.nombre],
        ['Fecha de nacimiento', normalizeDateText(renaperResult.data.fecha_nacimiento)],
        ['Sexo', normalizeSex(renaperResult.data.sexo)],
      ] : [];

      return (
        <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
          <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Validacion RENAPER</Text>
          <Text style={[styles.stepHelp, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
            Revisa los datos obtenidos del documento y comparalos contra RENAPER.
          </Text>
          <View style={[styles.renaperStatus, { backgroundColor: `${statusColor}18` }]}>
            {renaperLoading ? (
              <ActivityIndicator color={statusColor} />
            ) : (
              <Ionicons name={statusIcon} size={20} color={statusColor} />
            )}
            <Text style={[styles.renaperStatusText, { color: statusColor, fontFamily: typography.bold }]}>
              {statusLabel}
            </Text>
          </View>

          <Text style={[styles.renaperSectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Datos del documento</Text>
          <View style={[styles.renaperDataBox, { borderColor: theme.colors.border, backgroundColor: theme.colors.surfaceAlt }]}>
            {documentRows.map(([label, value]) => (
              <View key={label} style={styles.kvRow}>
                <Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>{label}</Text>
                <Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{value || '-'}</Text>
              </View>
            ))}
          </View>

          <TouchableOpacity
            onPress={validateRenaper}
            disabled={renaperLoading}
            style={[styles.primaryAction, { backgroundColor: theme.colors.primary }, renaperLoading && { opacity: 0.72 }]}
          >
            <Ionicons name="shield-checkmark-outline" size={18} color="#FFFFFF" />
            <Text style={[styles.primaryActionText, { fontFamily: typography.bold }]}>
              {renaperLoading ? 'VALIDANDO...' : 'VALIDAR RENAPER'}
            </Text>
          </TouchableOpacity>

          {!!renaperError && (
            <Text style={[styles.renaperError, { color: theme.colors.danger, fontFamily: typography.medium }]}>
              {renaperError}
            </Text>
          )}

          {!!renaperResult?.data && (
            <>
              <Text style={[styles.renaperSectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Datos RENAPER</Text>
              <View style={[styles.renaperDataBox, { borderColor: theme.colors.border, backgroundColor: theme.colors.surfaceAlt }]}>
                {renaperRows.map(([label, value]) => (
                  <View key={label} style={styles.kvRow}>
                    <Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>{label}</Text>
                    <Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{value || '-'}</Text>
                  </View>
                ))}
              </View>

              <Text style={[styles.renaperSectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Comparacion</Text>
              {renaperResult.comparisons.map((item) => {
                const color = item.matches ? theme.colors.success : theme.colors.danger;
                return (
                  <View key={item.key} style={[styles.renaperCompareRow, { borderColor: theme.colors.border }]}>
                    <View style={styles.renaperCompareValues}>
                      <Text style={[styles.renaperCompareLabel, { color: theme.colors.text, fontFamily: typography.bold }]}>{item.label}</Text>
                      <Text style={[styles.renaperCompareValue, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>Doc: {item.documentValue || '-'}</Text>
                      <Text style={[styles.renaperCompareValue, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>RENAPER: {item.renaperValue || '-'}</Text>
                    </View>
                    <View style={[styles.renaperCompareBadge, { backgroundColor: `${color}18` }]}>
                      <Ionicons name={item.matches ? 'checkmark' : 'close'} size={16} color={color} />
                    </View>
                  </View>
                );
              })}
            </>
          )}
        </View>
      );
    }

    if (currentStep === 4) {
      const fields = detail?.campos_definicion || [];
      return (
        <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
          <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Campos del relevamiento</Text>
          {fields.length === 0 ? (
            <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>No hay campos dinamicos configurados.</Text>
          ) : (
            fields.map(renderDynamicField)
          )}
        </View>
      );
    }

    return (
      <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
        <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Confirmacion</Text>
        <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>DNI</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{dniForm.dni_numero || '-'}</Text></View>
        <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Persona</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{`${dniForm.apellido || ''} ${dniForm.nombres || ''}`.trim() || '-'}</Text></View>
        <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Nacimiento</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{dniForm.fecha_nacimiento || '-'}</Text></View>
        <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Fotos DNI</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{dniPhotos.frente?.uri && dniPhotos.dorso?.uri ? 'Frente y dorso cargados' : 'Pendientes'}</Text></View>
        <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>RENAPER</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{renaperStatus}</Text></View>
        <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Direccion</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{readValue('direccion_objetivo')}</Text></View>
        <Text style={[styles.stepHelp, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
          La confirmacion final va a guardar localmente el relevamiento y sincronizarlo cuando vuelva internet.
        </Text>
        <TouchableOpacity style={[styles.primaryAction, { backgroundColor: theme.colors.success }]}>
          <Ionicons name="checkmark-circle-outline" size={18} color="#FFFFFF" />
          <Text style={[styles.primaryActionText, { fontFamily: typography.bold }]}>CONFIRMAR RELEVAMIENTO</Text>
        </TouchableOpacity>
      </View>
    );
  };

  if (isAssignedFlow) {
    return (
      <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
        <View style={styles.bannerWrap}>
          <Banner
            title={readValue('titulo') !== '-' ? readValue('titulo') : 'Relevamiento'}
            syncStatus={syncStatus}
            syncPendingCount={syncPendingCount}
            onSyncPress={onSyncPress}
            showBackButton
            onBackPress={onClose}
          />
        </View>

        <View style={styles.stepperScroll}>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.stepper}>
            {assignedSteps.map((step, idx) => (
              <React.Fragment key={step.id}>
                <TouchableOpacity
                  activeOpacity={step.id <= maxVisitedStep ? 0.8 : 1}
                  disabled={step.id > maxVisitedStep}
                  onPress={() => {
                    if (step.id <= maxVisitedStep) setCurrentStep(step.id);
                  }}
                  style={styles.stepNode}
                >
                  <View style={[
                    styles.stepIconCircle,
                    { backgroundColor: theme.colors.surface, borderColor: theme.colors.border },
                    currentStep >= step.id && { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
                  ]}>
                    <Ionicons name={step.icon} size={fontSizes.sm} color={currentStep >= step.id ? theme.colors.white : theme.colors.textSoft} />
                  </View>
                  <Text style={[
                    styles.stepNodeLabel,
                    { color: theme.colors.textSoft, fontFamily: typography.medium },
                    currentStep === step.id && { color: theme.colors.primary, fontFamily: typography.bold },
                    step.id > maxVisitedStep && { opacity: 0.5 },
                  ]}>
                    {step.title}
                  </Text>
                </TouchableOpacity>
                {idx < assignedSteps.length - 1 && (
                  <View
                    style={[
                      styles.stepConnect,
                      { backgroundColor: theme.colors.border },
                      currentStep > step.id && { backgroundColor: theme.colors.primary },
                    ]}
                  />
                )}
              </React.Fragment>
            ))}
          </ScrollView>
        </View>

        <ScrollView contentContainerStyle={styles.assignedContent} keyboardShouldPersistTaps="handled">
          {loading ? (
            <ActivityIndicator size="large" color={theme.colors.primary} />
          ) : error ? (
            <Text style={{ color: theme.colors.danger, fontFamily: typography.semibold }}>{error}</Text>
          ) : (
            renderAssignedStepContent()
          )}
        </ScrollView>

        {!loading && !error ? (
          <View
            style={[
              styles.assignedFooter,
              {
                borderTopColor: theme.colors.border,
                backgroundColor: theme.colors.background,
                paddingBottom: Math.max(insets.bottom, 16) + 6,
              },
            ]}
          >
            {currentStep > 1 ? (
              <TouchableOpacity onPress={prevAssignedStep} style={[styles.secondaryFooterButton, { borderColor: theme.colors.border, backgroundColor: theme.colors.surface }]}>
                <Ionicons name="chevron-back" size={18} color={theme.colors.text} />
                <Text style={[styles.secondaryFooterText, { color: theme.colors.text, fontFamily: typography.bold }]}>ANTERIOR</Text>
              </TouchableOpacity>
            ) : null}
            <TouchableOpacity onPress={nextAssignedStep} style={[styles.primaryFooterButton, { backgroundColor: theme.colors.primary }]}>
              <Text style={[styles.primaryFooterText, { fontFamily: typography.bold }]}>
                {currentStep === assignedSteps.length ? 'FINALIZAR' : 'SIGUIENTE'}
              </Text>
              <Ionicons name={currentStep === assignedSteps.length ? 'checkmark' : 'chevron-forward'} size={18} color="#FFFFFF" />
            </TouchableOpacity>
          </View>
        ) : null}

        <Modal visible={scannerVisible} transparent animationType="fade" onRequestClose={closeDniScanner}>
          <View style={styles.barcodeModalOverlay}>
            <View style={[styles.barcodePanel, { backgroundColor: theme.colors.surface }]}>
              <View style={styles.barcodeHeader}>
                <Text style={[styles.barcodeTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Escanear DNI</Text>
                <TouchableOpacity onPress={closeDniScanner} style={[styles.barcodeCloseButton, { backgroundColor: theme.colors.surfaceAlt }]}>
                  <Ionicons name="close" size={22} color={theme.colors.text} />
                </TouchableOpacity>
              </View>
              <View style={styles.barcodeCameraFrame}>
                <CameraView
                  key={scannerCameraKey}
                  style={styles.barcodeCamera}
                  facing="back"
                  autofocus="off"
                  barcodeScannerSettings={{ barcodeTypes: ['qr', 'pdf417'] }}
                  onBarcodeScanned={scannerLocked ? undefined : handleDniBarcodeScanned}
                />
                <View pointerEvents="none" style={styles.barcodeFrameBorder} />
              </View>
              {scannerLocked ? (
                <View style={styles.barcodeReading}>
                  <ActivityIndicator color={theme.colors.primary} />
                </View>
              ) : null}
            </View>
          </View>
        </Modal>

      </View>
    );
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <View style={styles.bannerWrap}>
        <Banner
          title="Detalle"
          syncStatus={syncStatus}
          syncPendingCount={syncPendingCount}
          onSyncPress={onSyncPress}
          showBackButton
          onBackPress={onClose}
        />
      </View>

      <View style={styles.tabsRow}>
        {tabs.map((tab) => {
          const selected = activeTab === tab;
          return (
            <Pressable
              key={tab}
              onPress={() => setActiveTab(tab)}
              style={[
                styles.tabChip,
                { backgroundColor: theme.colors.surface, borderColor: theme.colors.border },
                selected && { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
              ]}
            >
              <Text
                style={[
                  styles.tabChipText,
                  { color: theme.colors.text, fontFamily: typography.medium },
                  selected && { color: '#FFFFFF', fontFamily: typography.bold },
                ]}
              >
                {tab}
              </Text>
            </Pressable>
          );
        })}
      </View>

      <ScrollView contentContainerStyle={styles.content}>
        {loading ? (
          <ActivityIndicator size="large" color={theme.colors.primary} />
        ) : error ? (
          <Text style={{ color: theme.colors.danger, fontFamily: typography.semibold }}>{error}</Text>
        ) : (
          <>
            {activeTab === 'RESUMEN' && (
              <>
                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>General</Text>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>ID</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{readValue('id', 'local_id')}</Text></View>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Titulo</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{readValue('titulo')}</Text></View>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Estado</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{readValue('sync_estado')}</Text></View>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Prioridad</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{readValue('prioridad')}</Text></View>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Fecha creado</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{createdDateLabel}</Text></View>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Fecha sincronizado</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{syncedDateLabel}</Text></View>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Institucion</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>#{readValue('id_institucion')}</Text></View>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Direccion</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{readValue('direccion_objetivo')}</Text></View>
                  <View style={styles.kvRow}><Text style={[styles.k, { color: theme.colors.text, fontFamily: typography.semibold }]}>Geo</Text><Text style={[styles.v, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{hasGeo ? `${lat}, ${lng}` : 'Sin geolocalizacion'}</Text></View>
                  {mapPreviewUrl ? (
                    <Image
                      source={{ uri: mapPreviewUrl }}
                      style={styles.mapPreview}
                      resizeMode="cover"
                      onError={() => {
                        if (mapProviderIndex < mapPreviewUrls.length - 1) {
                          setMapProviderIndex((prev) => prev + 1);
                        }
                      }}
                    />
                  ) : null}
                </View>

                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Responsable</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Nombre: {readValue('responsable_nombre', 'nombre')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Apellido: {readValue('responsable_apellido', 'apellido')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>DNI: {readValue('responsable_dni', 'dni')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Telefono: {readValue('responsable_telefono', 'telefono')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Email: {readValue('responsable_email', 'email')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Funcion: {readValue('responsable_funcion', 'funcion')}</Text>
                </View>

                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Institucion</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tipo espacio fisico: {readValue('tipo_espacio_fisico')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Espacio fisico otro: {readValue('espacio_fisico_otro')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tiene colaboradores: {readValue('tiene_colaboradores')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Cantidad colaboradores: {readValue('cantidad_colaboradores')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tiene cocina: {readValue('tiene_cocina')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Espacio equipado: {readValue('espacio_equipado')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tiene ventilacion: {readValue('tiene_ventilacion')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tiene salida emergencia: {readValue('tiene_salida_emergencia')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Salida emergencia senializada: {readValue('salida_emergencia_senializada')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tiene equipacion incendio: {readValue('tiene_equipacion_incendio')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tiene botiquin: {readValue('tiene_botiquin')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tiene buena iluminacion: {readValue('tiene_buena_iluminacion')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tiene sanitarios: {readValue('tiene_sanitarios')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Desague hinodoro: {readValue('desague_hinodoro')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Gestion quejas: {readValue('gestion_quejas')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Gestion quejas otro: {readValue('gestion_quejas_otro')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Informacion quejas: {readValue('informacion_quejas')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Frecuencia limpieza: {readValue('frecuencia_limpieza')}</Text>
                </View>

                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Cocina</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Espacio elaboracion alimentos: {readValue('espacio_elaboracion_alimentos')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Almacenamiento alimentos secos: {readValue('almacenamiento_alimentos_secos')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Heladera: {readValue('heladera')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Freezer: {readValue('freezer')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Recipiente residuos organicos: {readValue('recipiente_residuos_organicos')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Recipiente residuos reciclables: {readValue('recipiente_residuos_reciclables')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Otros residuos: {readValue('otros_residuos')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Recipiente otros residuos: {readValue('recipiente_otros_residuos')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Abastecimiento combustible: {readValue('abastecimiento_combustible')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Abastecimiento agua: {readValue('abastecimiento_agua')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Abastecimiento agua otro: {readValue('abastecimiento_agua_otro')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Instalacion electrica: {readValue('instalacion_electrica')}</Text>
                </View>

                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Anexo y actividades</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tipo insumo: {readValue('tipo_insumo')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Frecuencia insumo: {readValue('frecuencia_insumo')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tecnologia: {readValue('tecnologia')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Acceso institucion: {readValue('acceso_institucion')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Distancia transporte: {readValue('distancia_transporte')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Servicio internet: {readValue('servicio_internet')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Zona inundable: {readValue('zona_inundable')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Jardin maternal: {readValue('actividades_jardin_maternal')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Jardin infantes: {readValue('actividades_jardin_infantes')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Apoyo escolar: {readValue('apoyo_escolar')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Alfabetizacion: {readValue('alfabetizacion_terminalidad')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Capacitaciones talleres: {readValue('capacitaciones_talleres')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Tipo talleres: {readValue('tipo_talleres')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Promocion salud: {readValue('promocion_salud')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Actividades discapacidad: {readValue('actividades_discapacidad')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Actividades recreativas: {readValue('actividades_recreativas')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Cuales recreativas: {readValue('cuales_actividades_recreativas')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Actividades culturales: {readValue('actividades_culturales')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Cuales culturales: {readValue('cuales_actividades_culturales')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Emprendimientos productivos: {readValue('emprendimientos_productivos')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Cuales emprendimientos: {readValue('cuales_emprendimientos_productivos')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Actividades religiosas: {readValue('actividades_religiosas')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Actividades huerta: {readValue('actividades_huerta')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Otras actividades: {readValue('otras_actividades')}</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Cuales otras actividades: {readValue('cuales_otras_actividades')}</Text>
                </View>

                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Observaciones</Text>
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                    {readValue('observaciones')}
                  </Text>
                </View>

                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                    Campos extras ({detail?.campos_extra?.length || 0})
                  </Text>
                  {(detail?.campos_extra || []).length === 0 ? (
                    <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Sin campos extra</Text>
                  ) : (
                    (detail?.campos_extra || []).map((item, idx) => (
                      <View key={item.id || `${item.nombre}-${idx}`} style={styles.extraRow}>
                        <Text style={[styles.extraName, { color: theme.colors.text, fontFamily: typography.semibold }]}>{item.nombre}</Text>
                        <Text style={[styles.extraValue, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>{item.valor}</Text>
                      </View>
                    ))
                  )}
                </View>
              </>
            )}

            {activeTab === 'ADJUNTOS' && (
              <>
                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                    Imagenes ({imageAttachments.length})
                  </Text>
                  {imageAttachments.length === 0 ? (
                    <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Sin imagenes</Text>
                  ) : (
                    <View style={styles.imageGrid}>
                      {imageAttachments.map((item, idx) => (
                        <View key={item.id || `${item.nombre_original}-${idx}`} style={styles.imageBox}>
                          <TouchableOpacity onPress={() => openImagePreview(item)}>
                            {imageUrls[item.id || item.storage_path] ? (
                              <Image source={{ uri: imageUrls[item.id || item.storage_path] }} style={styles.imageThumb} resizeMode="cover" />
                            ) : (
                              <View style={[styles.imageThumb, styles.imagePlaceholder]}>
                                <Ionicons name="image-outline" size={22} color={theme.colors.textSoft} />
                                <Text style={[styles.imagePlaceholderText, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>No disponible</Text>
                              </View>
                            )}
                          </TouchableOpacity>
                          <Text numberOfLines={1} style={[styles.imageName, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                            {item.nombre_original || 'Imagen'}
                          </Text>
                        </View>
                      ))}
                    </View>
                  )}
                </View>

                <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                  <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                    Documentos ({docAttachments.length})
                  </Text>
                  {docAttachments.length === 0 ? (
                    <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Sin documentos</Text>
                  ) : (
                    docAttachments.map((item, idx) => {
                      const actionId = String(item.id || item.storage_path || idx);
                      return (
                        <View key={actionId} style={styles.docRow}>
                          <View style={styles.docInfo}>
                            <Ionicons name="document-text-outline" size={18} color={theme.colors.icon} />
                            <Text style={[styles.docName, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                              {item.nombre_original || item.storage_path || 'Documento'}
                            </Text>
                          </View>
                          <View style={styles.docActions}>
                            <TouchableOpacity style={styles.docActionBtn} onPress={() => previewDocumentInApp(item)}>
                              <Ionicons name="eye-outline" size={16} color={theme.colors.icon} />
                            </TouchableOpacity>
                            <TouchableOpacity
                              style={styles.docActionBtn}
                              onPress={() => shareAttachment(item)}
                              disabled={sharingId === actionId}
                            >
                              {sharingId === actionId ? (
                                <ActivityIndicator size="small" color={theme.colors.primary} />
                              ) : (
                                <Ionicons name="share-social-outline" size={16} color={theme.colors.icon} />
                              )}
                            </TouchableOpacity>
                          </View>
                        </View>
                      );
                    })
                  )}
                </View>
              </>
            )}

            {activeTab === 'FIRMA' && (
              <View style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Firma final</Text>
                {signaturePaths.length === 0 ? (
                  <Text style={[styles.row, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>Sin firma registrada</Text>
                ) : (
                  <View style={[styles.signatureBox, { borderColor: theme.colors.border }]}>
                    <Svg height="100%" width="100%" viewBox="0 0 320 180">
                      {getCenteredSignaturePaths(signaturePaths).map((path, index) => (
                        <Path
                          key={index}
                          d={path}
                          stroke={theme.colors.black}
                          strokeWidth={2}
                          fill="none"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        />
                      ))}
                    </Svg>
                  </View>
                )}
              </View>
            )}
          </>
        )}
      </ScrollView>

      <Modal visible={previewVisible} transparent animationType="fade" onRequestClose={() => setPreviewVisible(false)}>
        <View style={styles.previewOverlay}>
          <View style={styles.previewTopBar}>
            <Text numberOfLines={1} style={[styles.previewTitle, { fontFamily: typography.semibold }]}>
              {previewName}
            </Text>
            <TouchableOpacity onPress={() => setPreviewVisible(false)} style={styles.previewCloseBtn}>
              <Ionicons name="close" size={fontSizes['2xl']} color={theme.colors.white} />
            </TouchableOpacity>
          </View>
          <View style={styles.previewBody}>
            {previewUri ? <Image source={{ uri: previewUri }} style={styles.previewImage} resizeMode="contain" /> : null}
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  bannerWrap: {
    position: 'relative',
  },
  tabsRow: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 6,
  },
  tabChip: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginRight: 8,
  },
  tabChipText: {
    fontSize: fontSizes.xs,
  },
  content: { padding: 16, paddingTop: 8 },
  assignedContent: {
    padding: 16,
    paddingTop: 8,
    paddingBottom: 104,
  },
  card: {
    borderRadius: radii.xl,
    borderWidth: 1,
    padding: 14,
    marginBottom: 12,
  },
  cardTitle: { fontSize: fontSizes.base, marginBottom: 8 },
  row: { fontSize: 14, marginBottom: 5 },
  kvRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  k: {
    width: 92,
    fontSize: 14,
  },
  v: {
    flex: 1,
    fontSize: 14,
  },
  extraRow: {
    paddingVertical: 7,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: designColors.borderBase,
  },
  extraName: {
    fontSize: 14,
  },
  extraValue: {
    fontSize: fontSizes.xs,
    marginTop: 2,
  },
  imageGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
  },
  imageBox: {
    width: '48%',
    marginBottom: 12,
  },
  imageThumb: {
    width: '100%',
    height: 120,
    borderRadius: radii.lg,
    backgroundColor: '#EEE',
  },
  imagePlaceholder: {
    alignItems: 'center',
    justifyContent: 'center',
  },
  imagePlaceholderText: {
    fontSize: fontSizes.xs,
    marginTop: 4,
  },
  imageName: {
    fontSize: 12,
    marginTop: 5,
  },
  docRow: {
    borderWidth: 1,
    borderColor: designColors.borderBase,
    borderRadius: radii.lg,
    padding: 10,
    marginBottom: 10,
  },
  docInfo: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  docName: {
    fontSize: 14,
    marginLeft: 8,
    flex: 1,
  },
  docActions: {
    marginTop: 8,
    flexDirection: 'row',
    justifyContent: 'flex-end',
  },
  docActionBtn: {
    width: 34,
    height: 34,
    borderRadius: radii.full,
    marginLeft: 8,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: designColors.bgBrandSofter,
  },
  signatureBox: {
    height: 190,
    borderWidth: 1,
    borderRadius: radii.lg,
    backgroundColor: designColors.bgSecondary,
    overflow: 'hidden',
  },
  previewOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.92)',
  },
  previewTopBar: {
    paddingTop: 46,
    paddingHorizontal: 14,
    paddingBottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  previewTitle: {
    color: '#FFFFFF',
    fontSize: 14,
    flex: 1,
    marginRight: 8,
  },
  previewCloseBtn: {
    width: 34,
    height: 34,
    borderRadius: radii.full,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
  previewBody: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 10,
  },
  previewImage: {
    width: '100%',
    height: '100%',
  },
  mapPreview: {
    width: '100%',
    height: 180,
    borderRadius: radii.lg,
    marginTop: 8,
  },
  stepperScroll: {
    backgroundColor: 'rgba(0,0,0,0.02)',
  },
  stepper: {
    paddingHorizontal: 20,
    paddingVertical: 14,
    alignItems: 'center',
  },
  stepNode: {
    alignItems: 'center',
    width: 76,
  },
  stepIconCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 2,
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 4,
  },
  stepNodeLabel: {
    fontSize: fontSizes.xxs,
    textTransform: 'uppercase',
    textAlign: 'center',
  },
  stepConnect: {
    width: 20,
    height: 2,
    marginTop: -15,
    marginHorizontal: 5,
  },
  stepHelp: {
    fontSize: fontSizes.sm,
    lineHeight: 20,
    marginBottom: 14,
  },
  formGroup: {
    marginBottom: 14,
  },
  formSectionTitle: {
    fontSize: fontSizes.xs,
    textTransform: 'uppercase',
    marginTop: 6,
    marginBottom: 10,
  },
  inputLabel: {
    fontSize: fontSizes.sm,
    marginBottom: 7,
  },
  textInput: {
    minHeight: 46,
    borderWidth: 1,
    borderRadius: radii.lg,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: fontSizes.sm,
  },
  textArea: {
    minHeight: 96,
    textAlignVertical: 'top',
  },
  optionWrap: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  optionChip: {
    borderWidth: 1,
    borderRadius: radii.full,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  optionText: {
    fontSize: fontSizes.xs,
  },
  dniPhotoRow: {
    flexDirection: 'row',
    gap: 12,
  },
  dniCaptureCard: {
    flex: 1,
    borderWidth: 1,
    borderRadius: radii.lg,
    padding: 9,
  },
  dniCapturePreview: {
    width: '100%',
    aspectRatio: 1.58,
    borderRadius: radii.md,
    overflow: 'hidden',
    minHeight: 108,
  },
  dniCaptureEmpty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: designColors.borderBase,
    borderRadius: radii.md,
  },
  dniCaptureImage: {
    width: '100%',
    height: '100%',
  },
  dniPhotoText: {
    fontSize: fontSizes.xs,
    marginTop: 5,
    textAlign: 'center',
  },
  dniCaptureButton: {
    minHeight: 40,
    borderRadius: radii.md,
    marginTop: 8,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    paddingHorizontal: 8,
  },
  dniCaptureButtonText: {
    color: '#FFFFFF',
    fontSize: fontSizes.xxs,
    marginLeft: 6,
  },
  renaperStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: radii.lg,
    padding: 12,
    marginBottom: 14,
  },
  renaperStatusText: {
    fontSize: fontSizes.sm,
    marginLeft: 8,
  },
  renaperSectionTitle: {
    fontSize: fontSizes.sm,
    marginBottom: 8,
    marginTop: 2,
  },
  renaperDataBox: {
    borderWidth: 1,
    borderRadius: radii.lg,
    padding: 12,
    marginBottom: 14,
  },
  renaperError: {
    fontSize: fontSizes.sm,
    lineHeight: 19,
    marginBottom: 14,
  },
  renaperCompareRow: {
    minHeight: 64,
    borderWidth: 1,
    borderRadius: radii.lg,
    padding: 10,
    marginBottom: 8,
    flexDirection: 'row',
    alignItems: 'center',
  },
  renaperCompareValues: {
    flex: 1,
  },
  renaperCompareLabel: {
    fontSize: fontSizes.sm,
    marginBottom: 4,
  },
  renaperCompareValue: {
    fontSize: fontSizes.xs,
    lineHeight: 17,
  },
  renaperCompareBadge: {
    width: 32,
    height: 32,
    borderRadius: radii.full,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 10,
  },
  primaryAction: {
    minHeight: 46,
    borderRadius: radii.lg,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    marginBottom: 14,
  },
  primaryActionText: {
    color: '#FFFFFF',
    fontSize: fontSizes.xs,
    marginLeft: 8,
  },
  scanAction: {
    minHeight: 46,
    borderRadius: radii.lg,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    marginBottom: 8,
  },
  scanActionText: {
    color: '#FFFFFF',
    fontSize: fontSizes.xs,
    marginLeft: 8,
  },
  scanHint: {
    fontSize: fontSizes.xs,
    marginBottom: 14,
    textAlign: 'center',
  },
  filePlaceholder: {
    minHeight: 74,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderRadius: radii.lg,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 12,
  },
  filePlaceholderText: {
    fontSize: fontSizes.xs,
    marginTop: 6,
    textAlign: 'center',
  },
  assignedFooter: {
    borderTopWidth: 1,
    paddingTop: 12,
    paddingHorizontal: 14,
    flexDirection: 'row',
    gap: 10,
  },
  secondaryFooterButton: {
    flex: 1,
    minHeight: 46,
    borderRadius: radii.lg,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  secondaryFooterText: {
    fontSize: fontSizes.xs,
    marginLeft: 6,
  },
  primaryFooterButton: {
    flex: 1.35,
    minHeight: 46,
    borderRadius: radii.lg,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  primaryFooterText: {
    color: '#FFFFFF',
    fontSize: fontSizes.xs,
    marginRight: 6,
  },
  barcodeModalOverlay: {
    flex: 1,
    justifyContent: 'center',
    padding: 18,
    backgroundColor: 'rgba(0,0,0,0.58)',
  },
  barcodePanel: {
    borderRadius: radii.xl,
    padding: 14,
  },
  barcodeHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  barcodeTitle: {
    fontSize: fontSizes.lg,
  },
  barcodeCloseButton: {
    width: 38,
    height: 38,
    borderRadius: radii.full,
    alignItems: 'center',
    justifyContent: 'center',
  },
  barcodeCameraFrame: {
    width: '100%',
    aspectRatio: 1.58,
    borderRadius: radii.lg,
    overflow: 'hidden',
    backgroundColor: '#000000',
  },
  barcodeCamera: {
    ...StyleSheet.absoluteFillObject,
  },
  barcodeFrameBorder: {
    ...StyleSheet.absoluteFillObject,
    borderWidth: 2,
    borderColor: '#FFFFFF',
    borderRadius: radii.lg,
  },
  barcodeReading: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 18,
    alignItems: 'center',
  },
});
