import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, TextInput, TouchableOpacity, Platform, Image, Alert, Animated, Easing, KeyboardAvoidingView, Modal, ActivityIndicator, AppState, InteractionManager } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import * as DocumentPicker from 'expo-document-picker';
import * as Location from 'expo-location';
import Svg, { Path } from 'react-native-svg';
import { useTheme } from '../context/ThemeContext';
import StaggeredItem from '../components/StaggeredItem';
import CustomButton from '../components/CustomButton';
import SignaturePad from '../components/SignaturePad';
import FrostedBackButton from '../components/FrostedBackButton';
import { designColors, fontSizes, radii } from '../theme';

export default function NewRelevamientoScreen({ onCancel, onSave }) {
    const MAX_IMAGES = 8;
    const { theme, typography, isDark } = useTheme();
    const [currentStep, setCurrentStep] = useState(1);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const submitLockRef = useRef(false);
    const [maxVisitedStep, setMaxVisitedStep] = useState(1);
    const [images, setImages] = useState([]);
    const [locationLoading, setLocationLoading] = useState(false);
    const [locationError, setLocationError] = useState('');
    const [mapProviderIndex, setMapProviderIndex] = useState(0);
    const stepperRef = useRef(null);
    const formScrollRef = useRef(null);
    const spinValue = useRef(new Animated.Value(0)).current;
    const signaturePadRef = useRef(null);
    const [attachments, setAttachments] = useState([]);
    const [signature, setSignature] = useState([]);
    const [showSigModal, setShowSigModal] = useState(false);
    const [extraFields, setExtraFields] = useState([]);
    const [newExtraFieldId, setNewExtraFieldId] = useState(null);
    const [isPickerLaunching, setIsPickerLaunching] = useState(false);
    const pickerLaunchInProgressRef = useRef(false);
    const isMountedRef = useRef(false);
    const isAppActiveRef = useRef(true);
    const isViewReadyRef = useRef(false);
    const [formData, setFormData] = useState({
        nombre: '',
        apellido: '',
        dni: '',
        telefono: '',
        email: '',
        funcion: '',
        tiene_colaboradores: 'No',
        cantidad_colaboradores: '',
        tipo_espacio_fisico: 'Espacio Propio',
        espacio_fisico_otro: '',
        tiene_cocina: 'No',
        espacio_elaboracion_alimentos: 'No',
        almacenamiento_alimentos_secos: 'No',
        heladera: 'No',
        freezer: 'No',
        recipiente_residuos_organicos: 'No',
        recipiente_residuos_reciclables: 'No',
        otros_residuos: 'No',
        recipiente_otros_residuos: 'No',
        abastecimiento_combustible: 'Gas natural',
        abastecimiento_agua: 'Agua de red',
        abastecimiento_agua_otro: '',
        instalacion_electrica: 'No',
        espacio_equipado: 'No',
        tiene_ventilacion: 'No',
        tiene_salida_emergencia: 'No',
        salida_emergencia_senializada: 'No',
        tiene_equipacion_incendio: 'No',
        tiene_botiquin: 'No',
        tiene_buena_iluminacion: 'No',
        tiene_sanitarios: 'No',
        desague_hinodoro: 'Cloaca',
        gestion_quejas: 'Buzon',
        gestion_quejas_otro: '',
        informacion_quejas: 'No',
        frecuencia_limpieza: '1 vez por dia',
        tipo_insumo: 'Dinero',
        frecuencia_insumo: '1 vez por semana',
        tecnologia: 'Computadora',
        acceso_institucion: 'Calle de tierra',
        distancia_transporte: 'De 0 a 5 cuadras',
        servicio_internet: 'No',
        zona_inundable: 'No',
        actividades_jardin_maternal: 'No',
        actividades_jardin_infantes: 'No',
        apoyo_escolar: 'No',
        alfabetizacion_terminalidad: 'No',
        capacitaciones_talleres: 'No',
        tipo_talleres: '',
        promocion_salud: 'No',
        actividades_discapacidad: 'No',
        actividades_recreativas: 'No',
        cuales_actividades_recreativas: '',
        actividades_culturales: 'No',
        cuales_actividades_culturales: '',
        emprendimientos_productivos: 'No',
        cuales_emprendimientos_productivos: '',
        actividades_religiosas: 'No',
        actividades_huerta: 'No',
        espacio_huerta: '',
        otras_actividades: 'No',
        cuales_otras_actividades: '',
        latitud: '',
        longitud: '',
        observaciones: '',
    });

    const steps = [
        { id: 1, title: 'Responsable', icon: 'person' },
        { id: 2, title: 'Institucion', icon: 'business' },
        { id: 3, title: 'Fotos', icon: 'camera' },
        { id: 4, title: 'Localizacion', icon: 'location' },
        { id: 5, title: 'Documentos', icon: 'document-attach' },
        { id: 6, title: 'Observaciones', icon: 'clipboard' },
        { id: 7, title: 'Final', icon: 'create' },
    ];

    const nextStep = async () => {
        if (submitLockRef.current || isSubmitting) return;

        if (currentStep < steps.length) {
            const next = currentStep + 1;
            setCurrentStep(next);
            setMaxVisitedStep((prev) => Math.max(prev, next));
            return;
        }

        const missingFields = getMissingRequiredFields();
        if (missingFields.length > 0) {
            Alert.alert(
                'Faltan campos obligatorios',
                `Completa los siguientes campos:\n- ${missingFields.join('\n- ')}`
            );
            return;
        }

        if (onSave) {
            submitLockRef.current = true;
            setIsSubmitting(true);
            try {
                await onSave({
                    ...formData,
                    evidencias: images,
                    adjuntos: attachments,
                    campos_extra: extraFields
                        .filter((field) => String(field.nombre || '').trim() && String(field.valor || '').trim())
                        .map((field) => ({
                            nombre: String(field.nombre || '').trim(),
                            valor: String(field.valor || '').trim(),
                        })),
                    firma_paths: signature,
                });
            } finally {
                setIsSubmitting(false);
                submitLockRef.current = false;
            }
        }
    };

    const getMissingRequiredFields = () => {
        const missing = [];
        const isEmpty = (value) => !String(value || '').trim();

        // Paso 2 - Condicionales
        if (formData.tipo_espacio_fisico === 'Otro' && isEmpty(formData.espacio_fisico_otro)) {
            missing.push('Especificar tipo de espacio (Otro)');
        }
        if (formData.tiene_colaboradores === 'Si' && isEmpty(formData.cantidad_colaboradores)) {
            missing.push('Cantidad de colaboradores');
        }
        if (formData.gestion_quejas === 'Otro' && isEmpty(formData.gestion_quejas_otro)) {
            missing.push('Gestion quejas (otro)');
        }
        if (formData.tiene_cocina === 'Si' && formData.abastecimiento_agua === 'Otro' && isEmpty(formData.abastecimiento_agua_otro)) {
            missing.push('Abastecimiento agua (otro)');
        }
        if (formData.capacitaciones_talleres === 'Si' && isEmpty(formData.tipo_talleres)) {
            missing.push('Tipo de talleres');
        }
        if (formData.actividades_recreativas === 'Si' && isEmpty(formData.cuales_actividades_recreativas)) {
            missing.push('Cuales actividades recreativas');
        }
        if (formData.actividades_culturales === 'Si' && isEmpty(formData.cuales_actividades_culturales)) {
            missing.push('Cuales actividades culturales');
        }
        if (formData.emprendimientos_productivos === 'Si' && isEmpty(formData.cuales_emprendimientos_productivos)) {
            missing.push('Cuales emprendimientos productivos');
        }
        if (formData.otras_actividades === 'Si' && isEmpty(formData.cuales_otras_actividades)) {
            missing.push('Cuales otras actividades');
        }
        extraFields.forEach((field, index) => {
            if (isEmpty(field.nombre) || isEmpty(field.valor)) {
                missing.push(`Campo extra ${index + 1} (nombre y valor)`);
            }
        });

        // Paso 7 - Firma
        if (!signature.length) {
            missing.push('Firma');
        }

        return missing;
    };

    const prevStep = () => {
        if (currentStep > 1) setCurrentStep(currentStep - 1);
    };

    useEffect(() => {
        isMountedRef.current = true;
        isAppActiveRef.current = AppState.currentState === 'active';

        const appStateSub = AppState.addEventListener('change', (nextState) => {
            isAppActiveRef.current = nextState === 'active';
        });

        const interactionTask = InteractionManager.runAfterInteractions(() => {
            requestAnimationFrame(() => {
                setTimeout(() => {
                    if (isMountedRef.current) {
                        isViewReadyRef.current = true;
                    }
                }, 0);
            });
        });

        return () => {
            isMountedRef.current = false;
            isViewReadyRef.current = false;
            pickerLaunchInProgressRef.current = false;
            appStateSub?.remove?.();
            interactionTask?.cancel?.();
        };
    }, []);

    useEffect(() => {
        if (!locationLoading) {
            spinValue.stopAnimation();
            spinValue.setValue(0);
            return;
        }

        const loop = Animated.loop(
            Animated.timing(spinValue, {
                toValue: 1,
                duration: 900,
                easing: Easing.linear,
                useNativeDriver: true,
            })
        );
        loop.start();

        return () => loop.stop();
    }, [locationLoading, spinValue]);

    useEffect(() => {
        if (!stepperRef.current) return;
        const estimatedStepWidth = 92;
        const x = Math.max(0, (currentStep - 1) * estimatedStepWidth - 40);
        stepperRef.current.scrollTo({ x, animated: true });
    }, [currentStep]);

    useEffect(() => {
        setTimeout(() => {
            formScrollRef.current?.scrollTo({ y: 0, animated: true });
        }, 30);
    }, [currentStep]);

    const ensureInputVisible = (event) => {
        const target = event?.target || event?.nativeEvent?.target;
        if (!target || !formScrollRef.current?.scrollResponderScrollNativeHandleToKeyboard) return;
        requestAnimationFrame(() => {
            formScrollRef.current.scrollResponderScrollNativeHandleToKeyboard(
                target,
                Platform.OS === 'ios' ? 24 : 36,
                true
            );
        });
    };

    const buildImageKey = (asset) => {
        if (!asset) return '';
        return String(asset.uri || '').trim().toLowerCase();
    };

    const buildAttachmentKey = (asset) => {
        if (!asset) return '';
        const uri = String(asset.uri || '').trim().toLowerCase();
        const name = String(asset.nombre || asset.fileName || asset.name || '').trim().toLowerCase();
        const size = String(asset.size || '');
        const mime = String(asset.mimeType || '').trim().toLowerCase();
        return `${uri}|${name}|${size}|${mime}`;
    };

    const addPickedImages = (assets) => {
        if (!assets?.length) return;
        setImages((prev) => {
            const existingKeys = new Set(prev.map((item) => buildImageKey(item)).filter(Boolean));
            const uniqueIncoming = assets.filter((asset) => {
                const key = buildImageKey(asset);
                if (!key || existingKeys.has(key)) return false;
                existingKeys.add(key);
                return true;
            });

            const remaining = MAX_IMAGES - prev.length;
            if (remaining <= 0) {
                Alert.alert('Limite alcanzado', `Solo podes cargar hasta ${MAX_IMAGES} imagenes.`);
                return prev;
            }

            const mapped = uniqueIncoming.slice(0, remaining).map((asset, idx) => ({
                id: Date.now() + idx,
                uri: asset.uri,
            }));

            if (mapped.length === 0) return prev;
            return [...prev, ...mapped];
        });
    };

    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

    const isUnregisteredLauncherError = (error) => {
        const message = String(error?.message || '').toLowerCase();
        return message.includes('unregistered activityresultlauncher') || message.includes('illegalstateexception');
    };

    const waitForPickerReady = async () => {
        await new Promise((resolve) => InteractionManager.runAfterInteractions(resolve));
        await new Promise((resolve) => requestAnimationFrame(() => setTimeout(resolve, 0)));
        return isMountedRef.current && isAppActiveRef.current;
    };

    const runPickerSafely = async (launcher) => {
        if (pickerLaunchInProgressRef.current) return null;

        pickerLaunchInProgressRef.current = true;
        if (isMountedRef.current) setIsPickerLaunching(true);

        try {
            let lastError = null;

            for (let attempt = 0; attempt < 2; attempt += 1) {
                if (!isViewReadyRef.current) {
                    await sleep(120);
                }

                const ready = await waitForPickerReady();
                if (!ready) return null;

                try {
                    return await launcher();
                } catch (e) {
                    lastError = e;
                    if (!isUnregisteredLauncherError(e) || attempt === 1) {
                        throw e;
                    }
                    await sleep(450);
                }
            }

            throw lastError || new Error('No se pudo abrir el selector');
        } finally {
            await sleep(120);
            pickerLaunchInProgressRef.current = false;
            if (isMountedRef.current) setIsPickerLaunching(false);
        }
    };

    const ensureCameraPermission = async () => {
        const current = await ImagePicker.getCameraPermissionsAsync();
        if (current?.granted) return true;
        const requested = await ImagePicker.requestCameraPermissionsAsync();
        const granted = requested?.granted || requested?.status === 'granted';
        if (granted && Platform.OS === 'android') {
            await sleep(350);
        }
        return granted;
    };

    const ensureGalleryPermission = async () => {
        const current = await ImagePicker.getMediaLibraryPermissionsAsync();
        if (current?.granted) return true;
        const requested = await ImagePicker.requestMediaLibraryPermissionsAsync();
        const granted = requested?.granted || requested?.status === 'granted';
        if (granted && Platform.OS === 'android') {
            await sleep(350);
        }
        return granted;
    };

    const openCamera = async () => {
        try {
            const granted = await ensureCameraPermission();
            if (!granted) {
                Alert.alert('Permiso requerido', 'Necesitas habilitar el acceso a la camara.');
                return;
            }
            const result = await runPickerSafely(() => ImagePicker.launchCameraAsync({
                mediaTypes: 'images',
                allowsEditing: false,
                quality: 0.8,
            }));
            if (result && !result.canceled) addPickedImages(result.assets);
        } catch (e) {
            Alert.alert('Camara', e?.message || 'No se pudo abrir la camara.');
        }
    };

    const openGallery = async () => {
        try {
            const granted = await ensureGalleryPermission();
            if (!granted) {
                Alert.alert('Permiso requerido', 'Necesitas habilitar el acceso a la galeria.');
                return;
            }
            const result = await runPickerSafely(() => ImagePicker.launchImageLibraryAsync({
                mediaTypes: 'images',
                allowsMultipleSelection: true,
                selectionLimit: MAX_IMAGES,
                quality: 0.8,
            }));
            if (result && !result.canceled) addPickedImages(result.assets);
        } catch (e) {
            Alert.alert('Galeria', e?.message || 'No se pudo abrir la galeria.');
        }
    };

    const removeImage = (id) => {
        setImages((prev) => prev.filter((img) => img.id !== id));
    };

    const pickDocumentationImage = async () => {
        try {
            const granted = await ensureGalleryPermission();
            if (!granted) {
                Alert.alert('Permiso requerido', 'Necesitas habilitar el acceso a la galeria.');
                return;
            }
            const result = await runPickerSafely(() => ImagePicker.launchImageLibraryAsync({
                mediaTypes: 'images',
                allowsMultipleSelection: true,
                quality: 0.8,
            }));

            if (!result || result.canceled) return;

            const mapped = result.assets.map((asset, idx) => ({
                id: `${Date.now()}-img-${idx}`,
                tipo: 'imagen',
                nombre: asset.fileName || `imagen_${idx + 1}.jpg`,
                uri: asset.uri,
            }));

            setAttachments((prev) => {
                const keys = new Set(prev.map((item) => buildAttachmentKey(item)).filter(Boolean));
                const unique = mapped.filter((item) => {
                    const key = buildAttachmentKey(item);
                    if (!key || keys.has(key)) return false;
                    keys.add(key);
                    return true;
                });
                return unique.length > 0 ? [...prev, ...unique] : prev;
            });
        } catch (e) {
            Alert.alert('Galeria', e?.message || 'No se pudo abrir la galeria.');
        }
    };

    const pickDocumentationCamera = async () => {
        try {
            const granted = await ensureCameraPermission();
            if (!granted) {
                Alert.alert('Permiso requerido', 'Necesitas habilitar el acceso a la camara.');
                return;
            }
            const result = await runPickerSafely(() => ImagePicker.launchCameraAsync({
                mediaTypes: 'images',
                allowsEditing: false,
                quality: 0.8,
            }));

            if (!result || result.canceled) return;

            const mapped = result.assets.map((asset, idx) => ({
                id: `${Date.now()}-cam-${idx}`,
                tipo: 'imagen',
                nombre: asset.fileName || `foto_${idx + 1}.jpg`,
                uri: asset.uri,
            }));

            setAttachments((prev) => {
                const keys = new Set(prev.map((item) => buildAttachmentKey(item)).filter(Boolean));
                const unique = mapped.filter((item) => {
                    const key = buildAttachmentKey(item);
                    if (!key || keys.has(key)) return false;
                    keys.add(key);
                    return true;
                });
                return unique.length > 0 ? [...prev, ...unique] : prev;
            });
        } catch (e) {
            Alert.alert('Camara', e?.message || 'No se pudo abrir la camara.');
        }
    };

    const pickDocumentationFile = async () => {
        if (pickerLaunchInProgressRef.current) return;
        pickerLaunchInProgressRef.current = true;
        if (isMountedRef.current) setIsPickerLaunching(true);

        try {
        const result = await DocumentPicker.getDocumentAsync({
            multiple: false,
            copyToCacheDirectory: true,
            type: '*/*',
        });

        if (result.canceled) return;

        const mapped = result.assets.map((asset, idx) => ({
            id: `${Date.now()}-file-${idx}`,
            tipo: 'archivo',
            nombre: asset.name || `archivo_${idx + 1}`,
            uri: asset.uri,
            mimeType: asset.mimeType || '',
            size: asset.size || 0,
        }));

        setAttachments((prev) => {
            const keys = new Set(prev.map((item) => buildAttachmentKey(item)).filter(Boolean));
            const unique = mapped.filter((item) => {
                const key = buildAttachmentKey(item);
                if (!key || keys.has(key)) return false;
                keys.add(key);
                return true;
            });
            return unique.length > 0 ? [...prev, ...unique] : prev;
        });
        } finally {
            await sleep(120);
            pickerLaunchInProgressRef.current = false;
            if (isMountedRef.current) setIsPickerLaunching(false);
        }
    };

    const removeAttachment = (id) => {
        setAttachments((prev) => prev.filter((item) => item.id !== id));
    };

    const addExtraField = () => {
        const id = `${Date.now()}-${extraFields.length}`;
        setExtraFields((prev) => [...prev, { id, nombre: '', valor: '' }]);
        setNewExtraFieldId(id);
        setTimeout(() => {
            formScrollRef.current?.scrollToEnd({ animated: true });
        }, 150);
    };

    const updateExtraField = (id, key, value) => {
        setExtraFields((prev) => prev.map((field) => (field.id === id ? { ...field, [key]: value } : field)));
    };

    const removeExtraField = (id) => {
        setExtraFields((prev) => prev.filter((field) => field.id !== id));
    };

    const scrollToBottom = () => {
        setTimeout(() => {
            formScrollRef.current?.scrollToEnd({ animated: true });
        }, 120);
    };

    const fetchCurrentLocation = async () => {
        try {
            setLocationLoading(true);
            setLocationError('');
            setMapProviderIndex(0);

            const permission = await Location.requestForegroundPermissionsAsync();
            if (permission.status !== 'granted') {
                setLocationError('Permiso de ubicacion denegado.');
                return;
            }

            const current = await Location.getCurrentPositionAsync({
                accuracy: Location.Accuracy.High,
            });

            setFormData({
                ...formData,
                latitud: String(current.coords.latitude.toFixed(6)),
                longitud: String(current.coords.longitude.toFixed(6)),
            });
        } catch (error) {
            setLocationError('No se pudo obtener la ubicacion.');
        } finally {
            setLocationLoading(false);
        }
    };

    const getAutoCapitalizeByKey = (key) => {
        if (key === 'email') return 'none';
        if (['nombre', 'apellido', 'funcion'].includes(key)) return 'words';
        return 'none';
    };

    const renderInput = (label, placeholder, key, icon, keyboardType = 'default') => (
        <View style={styles.inputGroup}>
            <Text style={[styles.label, { color: theme.colors.text, fontFamily: typography.semibold }]}>{label}</Text>
            <View style={[styles.inputWrapper, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                <Ionicons name={icon} size={20} color={theme.colors.icon} style={styles.inputIcon} />
                <TextInput
                    style={[styles.input, { color: theme.colors.text, fontFamily: typography.regular }]}
                    placeholder={placeholder}
                    placeholderTextColor={theme.colors.textSoft}
                    value={formData[key]}
                    onChangeText={(text) => setFormData({ ...formData, [key]: text })}
                    keyboardType={keyboardType}
                    autoCapitalize={getAutoCapitalizeByKey(key)}
                />
            </View>
        </View>
    );

    const renderSelector = (label, key, options) => (
        <View style={styles.inputGroup}>
            <Text style={[styles.label, { color: theme.colors.text, fontFamily: typography.semibold }]}>{label}</Text>
            <View style={styles.optionsRow}>
                {options.map((option) => {
                    const selected = formData[key] === option;
                    return (
                        <TouchableOpacity
                            key={option}
                            onPress={() => setFormData({ ...formData, [key]: option })}
                            style={[
                                styles.optionChip,
                                { backgroundColor: theme.colors.surface, borderColor: theme.colors.border },
                                selected && { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
                            ]}
                        >
                            <Text
                                style={[
                                    styles.optionText,
                                    { color: theme.colors.text, fontFamily: typography.medium },
                                    selected && { color: '#FFFFFF', fontFamily: typography.bold },
                                ]}
                            >
                                {option}
                            </Text>
                        </TouchableOpacity>
                    );
                })}
            </View>
        </View>
    );

    const renderYesNo = (label, key) => renderSelector(label, key, ['No', 'Si']);
    const mapPreviewUrls = formData.latitud && formData.longitud
        ? [
            `https://staticmap.openstreetmap.de/staticmap.php?center=${formData.latitud},${formData.longitud}&zoom=16&size=800x400&markers=${formData.latitud},${formData.longitud},red-pushpin`,
            `https://static-maps.yandex.ru/1.x/?ll=${formData.longitud},${formData.latitud}&size=650,300&z=16&l=map&pt=${formData.longitud},${formData.latitud},pm2rdm&lang=es_ES`,
        ]
        : [];
    const mapPreviewUrl = mapPreviewUrls[mapProviderIndex] || null;
    const spinInterpolate = spinValue.interpolate({
        inputRange: [0, 1],
        outputRange: ['0deg', '360deg'],
    });

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

        if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) {
            return null;
        }

        const width = Math.max(1, maxX - minX);
        const height = Math.max(1, maxY - minY);
        return { minX, minY, width, height };
    };

    const transformSignaturePath = (path, scale, offsetX, offsetY) => {
        return path.replace(
            /(-?\d+(\.\d+)?),(-?\d+(\.\d+)?)/g,
            (_, x, __, y) => {
                const nx = parseFloat(x) * scale + offsetX;
                const ny = parseFloat(y) * scale + offsetY;
                return `${nx.toFixed(2)},${ny.toFixed(2)}`;
            }
        );
    };

    const getCenteredSignaturePaths = (paths, targetWidth = 320, targetHeight = 180, padding = 14) => {
        const bounds = getSignatureBounds(paths);
        if (!bounds) return paths;

        const scaleX = (targetWidth - padding * 2) / bounds.width;
        const scaleY = (targetHeight - padding * 2) / bounds.height;
        const scale = Math.min(scaleX, scaleY);

        const offsetX = (targetWidth - bounds.width * scale) / 2 - bounds.minX * scale;
        const offsetY = (targetHeight - bounds.height * scale) / 2 - bounds.minY * scale;

        return paths.map((path) => transformSignaturePath(path, scale, offsetX, offsetY));
    };

    const renderStepContent = () => {
        if (currentStep === 1) {
            return (
                <View style={styles.stepContainer}>
                    <StaggeredItem index={0}>
                        <Text style={[styles.stepTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Responsable de la institucion</Text>
                        <Text style={[styles.stepDesc, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                            Completa los datos de la persona responsable de la institucion.
                        </Text>
                    </StaggeredItem>

                    <StaggeredItem index={1}>{renderInput('Nombre del responsable', 'Ej: Juan', 'nombre', 'person-outline')}</StaggeredItem>
                    <StaggeredItem index={2}>{renderInput('Apellido del responsable', 'Ej: Perez', 'apellido', 'person-outline')}</StaggeredItem>
                    <StaggeredItem index={3}>{renderInput('DNI', 'Numero de documento', 'dni', 'card-outline', 'number-pad')}</StaggeredItem>
                    <StaggeredItem index={4}>{renderInput('Telefono del responsable', 'Ej: 11 5555 5555', 'telefono', 'call-outline', 'phone-pad')}</StaggeredItem>
                    <StaggeredItem index={5}>{renderInput('Email del responsable', 'Ej: nombre@dominio.com', 'email', 'mail-outline', 'email-address')}</StaggeredItem>
                    <StaggeredItem index={6}>{renderInput('Funcion en la institucion', 'Ej: Coordinador institucional', 'funcion', 'briefcase-outline')}</StaggeredItem>
                </View>
            );
        }

        if (currentStep === 2) {
            return (
                <View style={styles.stepContainer}>
                    <StaggeredItem index={0}>
                        <Text style={[styles.stepTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Detalle de la institucion</Text>
                        <Text style={[styles.stepDesc, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                            Completa los datos de la institucion y del anexo.
                        </Text>
                    </StaggeredItem>

                    <StaggeredItem index={1}>
                        {renderSelector('Tipo de espacio fisico', 'tipo_espacio_fisico', ['Espacio Propio', 'Espacio Compartido', 'Otro'])}
                    </StaggeredItem>
                    {formData.tipo_espacio_fisico === 'Otro' && (
                        <StaggeredItem index={2}>
                            {renderInput('Especificar otro', 'Detalle del tipo de espacio', 'espacio_fisico_otro', 'document-text-outline')}
                        </StaggeredItem>
                    )}

                    <StaggeredItem index={3}>
                        <View style={[styles.sectionCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                            <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Datos de la institucion</Text>
                            {renderYesNo('Espacio equipado', 'espacio_equipado')}
                            {renderYesNo('Tiene ventilacion', 'tiene_ventilacion')}
                            {renderYesNo('Tiene salida emergencia', 'tiene_salida_emergencia')}
                            {renderYesNo('Salida emergencia senializada', 'salida_emergencia_senializada')}
                            {renderYesNo('Tiene equipacion incendio', 'tiene_equipacion_incendio')}
                            {renderYesNo('Tiene botiquin', 'tiene_botiquin')}
                            {renderYesNo('Tiene buena iluminacion', 'tiene_buena_iluminacion')}
                            {renderYesNo('Tiene sanitarios', 'tiene_sanitarios')}
                            {renderSelector('Desague hinodoro', 'desague_hinodoro', ['Cloaca', 'Pozo ciego', 'Otro'])}
                            {renderSelector('Gestion quejas', 'gestion_quejas', ['Buzon', 'Libro', 'Digital', 'Otro'])}
                            {formData.gestion_quejas === 'Otro' && (
                                renderInput('Gestion quejas (otro)', 'Especificar', 'gestion_quejas_otro', 'chatbox-ellipses-outline')
                            )}
                            {renderYesNo('Informacion quejas', 'informacion_quejas')}
                            {renderSelector('Frecuencia limpieza', 'frecuencia_limpieza', ['1 vez por dia', '2 veces por dia', 'Semanal', 'Otro'])}
                        </View>
                    </StaggeredItem>

                    <StaggeredItem index={4}>
                        {renderYesNo('Tiene colaboradores', 'tiene_colaboradores')}
                    </StaggeredItem>
                    {formData.tiene_colaboradores === 'Si' && (
                        <StaggeredItem index={5}>
                            {renderInput('Cuantos colaboradores', 'Ej: 4', 'cantidad_colaboradores', 'people-outline', 'number-pad')}
                        </StaggeredItem>
                    )}

                    <StaggeredItem index={6}>
                        {renderYesNo('Tiene cocina', 'tiene_cocina')}
                    </StaggeredItem>

                    {formData.tiene_cocina === 'Si' && (
                    <StaggeredItem index={7}>
                        <View style={[styles.sectionCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                            <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Cocina</Text>
                            {renderYesNo('Espacio elaboracion alimentos', 'espacio_elaboracion_alimentos')}
                            {renderYesNo('Almacenamiento alimentos secos', 'almacenamiento_alimentos_secos')}
                            {renderYesNo('Heladera', 'heladera')}
                            {renderYesNo('Freezer', 'freezer')}
                            {renderYesNo('Recipiente residuos organicos', 'recipiente_residuos_organicos')}
                            {renderYesNo('Recipiente residuos reciclables', 'recipiente_residuos_reciclables')}
                            {renderYesNo('Otros residuos', 'otros_residuos')}
                            {renderYesNo('Recipiente otros residuos', 'recipiente_otros_residuos')}
                            {renderSelector('Abastecimiento combustible', 'abastecimiento_combustible', ['Gas natural', 'Garrafa', 'Lenia', 'Otro'])}
                            {renderSelector('Abastecimiento agua', 'abastecimiento_agua', ['Agua de red', 'Pozo', 'Camion cisterna', 'Otro'])}
                            {formData.abastecimiento_agua === 'Otro' && (
                                renderInput('Abastecimiento agua (otro)', 'Especificar', 'abastecimiento_agua_otro', 'water-outline')
                            )}
                            {renderYesNo('Instalacion electrica', 'instalacion_electrica')}
                        </View>
                    </StaggeredItem>
                    )}

                    <StaggeredItem index={8}>
                        <View style={[styles.sectionCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                            <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Anexo</Text>
                            {renderSelector('Tipo insumo', 'tipo_insumo', ['Dinero', 'Alimentos', 'Ropa', 'Otro'])}
                            {renderSelector('Frecuencia insumo', 'frecuencia_insumo', ['1 vez por semana', '2 veces por semana', 'Quincenal', 'Mensual'])}
                            {renderSelector('Tecnologia', 'tecnologia', ['Computadora', 'Tablet', 'Celular', 'Ninguna'])}
                            {renderSelector('Acceso a la institucion', 'acceso_institucion', ['Calle de tierra', 'Calle asfaltada', 'Pasillo', 'Otro'])}
                            {renderSelector('Distancia transporte', 'distancia_transporte', ['De 0 a 5 cuadras', 'De 6 a 10 cuadras', 'Mas de 10 cuadras'])}
                            {renderYesNo('Servicio internet', 'servicio_internet')}
                            {renderYesNo('Zona inundable', 'zona_inundable')}
                        </View>
                    </StaggeredItem>

                    <StaggeredItem index={9}>
                        <View style={[styles.sectionCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                            <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Actividades</Text>
                            {renderYesNo('Jardin maternal', 'actividades_jardin_maternal')}
                            {renderYesNo('Jardin infantes', 'actividades_jardin_infantes')}
                            {renderYesNo('Apoyo escolar', 'apoyo_escolar')}
                            {renderYesNo('Alfabetizacion', 'alfabetizacion_terminalidad')}
                            {renderYesNo('Capacitacion talleres', 'capacitaciones_talleres')}
                            {formData.capacitaciones_talleres === 'Si' && (
                                renderInput('Tipo de talleres', 'Describir tipos de talleres', 'tipo_talleres', 'construct-outline')
                            )}
                            {renderYesNo('Promocion salud', 'promocion_salud')}
                            {renderYesNo('Actividades discapacidad', 'actividades_discapacidad')}
                            {renderYesNo('Actividades recreativas', 'actividades_recreativas')}
                            {formData.actividades_recreativas === 'Si' && (
                                renderInput('Cuales actividades recreativas', 'Describir', 'cuales_actividades_recreativas', 'game-controller-outline')
                            )}
                            {renderYesNo('Actividades culturales', 'actividades_culturales')}
                            {formData.actividades_culturales === 'Si' && (
                                renderInput('Cuales actividades culturales', 'Describir', 'cuales_actividades_culturales', 'musical-notes-outline')
                            )}
                            {renderYesNo('Emprendimientos productivos', 'emprendimientos_productivos')}
                            {formData.emprendimientos_productivos === 'Si' && (
                                renderInput('Cuales emprendimientos productivos', 'Describir', 'cuales_emprendimientos_productivos', 'briefcase-outline')
                            )}
                            {renderYesNo('Actividades religiosas', 'actividades_religiosas')}
                            {renderYesNo('Actividades huerta', 'actividades_huerta')}
                            {renderYesNo('Otras actividades', 'otras_actividades')}
                            {formData.otras_actividades === 'Si' && (
                                renderInput('Cuales otras actividades', 'Describir', 'cuales_otras_actividades', 'list-outline')
                            )}
                        </View>
                    </StaggeredItem>

                </View>
            );
        }

        if (currentStep === 3) {
            return (
                <View style={styles.stepContainer}>
                    <StaggeredItem index={0}>
                        <Text style={[styles.stepTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Evidencia fotografica</Text>
                        <Text style={[styles.stepDesc, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                            Agrega fotos desde camara o galeria para documentar el relevamiento.
                        </Text>
                    </StaggeredItem>

                    <StaggeredItem index={1}>
                        <View style={styles.imageGrid}>
                            <TouchableOpacity
                                onPress={openCamera}
                                disabled={isPickerLaunching}
                                activeOpacity={isPickerLaunching ? 1 : 0.8}
                                style={[styles.imageActionBtn, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}
                            >
                                <Ionicons name="camera" size={30} color={theme.colors.icon} />
                                <Text style={[styles.imageActionText, { color: theme.colors.primary, fontFamily: typography.bold }]}>TOMAR FOTO</Text>
                            </TouchableOpacity>

                            <TouchableOpacity
                                onPress={openGallery}
                                disabled={isPickerLaunching}
                                activeOpacity={isPickerLaunching ? 1 : 0.8}
                                style={[styles.imageActionBtn, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}
                            >
                                <Ionicons name="images" size={30} color={theme.colors.icon} />
                                <Text style={[styles.imageActionText, { color: theme.colors.primary, fontFamily: typography.bold }]}>GALERIA</Text>
                            </TouchableOpacity>
                        </View>

                        <Text style={[styles.imageCount, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                            {images.length}/{MAX_IMAGES} imagenes
                        </Text>
                    </StaggeredItem>

                    {images.length > 0 && (
                        <StaggeredItem index={2}>
                            <View style={styles.imageGrid}>
                                {images.map((img) => (
                                    <View key={img.id} style={styles.imageItem}>
                                        <Image source={{ uri: img.uri }} style={styles.imageThumb} />
                                        <TouchableOpacity
                                            onPress={() => removeImage(img.id)}
                                            style={styles.imageRemoveBtn}
                                        >
                                            <Ionicons name="close-circle" size={24} color={theme.colors.danger} />
                                        </TouchableOpacity>
                                    </View>
                                ))}
                            </View>
                        </StaggeredItem>
                    )}
                </View>
            );
        }

        if (currentStep === 4) {
            return (
                <View style={styles.stepContainer}>
                    <StaggeredItem index={0}>
                        <Text style={[styles.stepTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Geolocalizacion</Text>
                        <Text style={[styles.stepDesc, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                            Captura la ubicacion del relevamiento para registrar coordenadas precisas (opcional).
                        </Text>
                    </StaggeredItem>

                    <StaggeredItem index={1}>
                        <View style={[styles.sectionCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                            <TouchableOpacity
                                onPress={fetchCurrentLocation}
                                style={[styles.geoButton, { backgroundColor: theme.colors.primary }]}
                            >
                                {locationLoading ? (
                                    <Animated.View style={{ transform: [{ rotate: spinInterpolate }] }}>
                                        <Ionicons name="reload" size={18} color="#FFFFFF" />
                                    </Animated.View>
                                ) : (
                                    <Ionicons name="locate" size={18} color="#FFFFFF" />
                                )}
                                <Text style={[styles.geoButtonText, { fontFamily: typography.bold }]}>
                                    {locationLoading ? 'Obteniendo ubicacion...' : 'Obtener ubicacion actual'}
                                </Text>
                            </TouchableOpacity>

                            {locationError ? (
                                <Text style={[styles.geoError, { color: theme.colors.danger, fontFamily: typography.medium }]}>{locationError}</Text>
                            ) : null}

                            <View style={styles.geoRow}>
                                <View style={[styles.geoBadge, { backgroundColor: theme.colors.surfaceAlt }]}>
                                    <Text style={[styles.geoLabel, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>LAT</Text>
                                    <Text style={[styles.geoValue, { color: theme.colors.text, fontFamily: typography.bold }]}>
                                        {formData.latitud || '--'}
                                    </Text>
                                </View>
                                <View style={[styles.geoBadge, { backgroundColor: theme.colors.surfaceAlt }]}>
                                    <Text style={[styles.geoLabel, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>LNG</Text>
                                    <Text style={[styles.geoValue, { color: theme.colors.text, fontFamily: typography.bold }]}>
                                        {formData.longitud || '--'}
                                    </Text>
                                </View>
                            </View>

                            {mapPreviewUrl ? (
                                <Image
                                    source={{ uri: mapPreviewUrl }}
                                    style={styles.mapPreview}
                                    resizeMode="cover"
                                    onError={() => {
                                        if (mapProviderIndex < mapPreviewUrls.length - 1) {
                                            setMapProviderIndex(mapProviderIndex + 1);
                                        } else {
                                            setMapProviderIndex(mapPreviewUrls.length);
                                        }
                                    }}
                                />
                            ) : (
                                <View style={[styles.mapPlaceholder, { backgroundColor: theme.colors.surfaceAlt, borderColor: theme.colors.border }]}>
                                    <Ionicons name="map-outline" size={28} color={theme.colors.textSoft} />
                                    <Text style={[styles.mapPlaceholderText, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                                        Obtene la ubicacion para ver el mapa
                                    </Text>
                                </View>
                            )}
                        </View>
                    </StaggeredItem>
                </View>
            );
        }

        if (currentStep === 5) {
            return (
                <View style={styles.stepContainer}>
                    <StaggeredItem index={0}>
                        <Text style={[styles.stepTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Documentacion</Text>
                        <Text style={[styles.stepDesc, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                            Subi fotos o archivos para respaldar el relevamiento.
                        </Text>
                    </StaggeredItem>

                    <StaggeredItem index={1}>
                        <View style={styles.docsActionsRow}>
                            <TouchableOpacity
                                onPress={pickDocumentationCamera}
                                disabled={isPickerLaunching}
                                activeOpacity={isPickerLaunching ? 1 : 0.8}
                                style={[styles.docsActionBtn, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}
                            >
                                <Ionicons name="camera-outline" size={30} color={theme.colors.icon} />
                                <Text style={[styles.docsActionText, { color: theme.colors.primary, fontFamily: typography.bold }]}>TOMAR FOTO</Text>
                            </TouchableOpacity>

                            <TouchableOpacity
                                onPress={pickDocumentationImage}
                                disabled={isPickerLaunching}
                                activeOpacity={isPickerLaunching ? 1 : 0.8}
                                style={[styles.docsActionBtn, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}
                            >
                                <Ionicons name="images-outline" size={30} color={theme.colors.icon} />
                                <Text style={[styles.docsActionText, { color: theme.colors.primary, fontFamily: typography.bold }]}>GALERIA</Text>
                            </TouchableOpacity>

                            <TouchableOpacity
                                onPress={pickDocumentationFile}
                                disabled={isPickerLaunching}
                                activeOpacity={isPickerLaunching ? 1 : 0.8}
                                style={[styles.docsActionBtn, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}
                            >
                                <Ionicons name="document-attach-outline" size={30} color={theme.colors.icon} />
                                <Text style={[styles.docsActionText, { color: theme.colors.primary, fontFamily: typography.bold }]}>ARCHIVO</Text>
                            </TouchableOpacity>
                        </View>
                        <View style={styles.docsAttachmentsWrap}>
                            <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Adjuntos</Text>
                        </View>
                    </StaggeredItem>

                    {attachments.map((item, idx) => (
                        <StaggeredItem key={item.id} index={idx + 2}>
                            <View style={[styles.extraFieldCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                                <View style={styles.attachmentRow}>
                                    <Ionicons
                                        name={item.tipo === 'imagen' ? 'image-outline' : 'document-outline'}
                                        size={20}
                                        color={theme.colors.icon}
                                        style={{ marginRight: 10 }}
                                    />
                                    <View style={{ flex: 1 }}>
                                        <Text style={[styles.attachmentName, { color: theme.colors.text, fontFamily: typography.semibold }]}>
                                            {item.nombre}
                                        </Text>
                                        <Text style={[styles.attachmentType, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                                            {item.tipo === 'imagen' ? 'Foto/Imagen' : 'Archivo'}
                                        </Text>
                                    </View>
                                    <TouchableOpacity onPress={() => removeAttachment(item.id)} style={styles.removeFieldBtn}>
                                        <Ionicons name="trash-outline" size={16} color={theme.colors.danger} />
                                    </TouchableOpacity>
                                </View>
                            </View>
                        </StaggeredItem>
                    ))}
                </View>
            );
        }

        if (currentStep === 6) {
            return (
                <View style={styles.stepContainer}>
                    <StaggeredItem index={0}>
                        <Text style={[styles.stepTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Observaciones</Text>
                        <Text style={[styles.stepDesc, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                            Agrega observaciones generales y campos extra (nombre y valor).
                        </Text>
                    </StaggeredItem>

                    <StaggeredItem index={1}>
                        <Text style={[styles.label, { color: theme.colors.text, fontFamily: typography.semibold }]}>Observaciones</Text>
                        <View style={[styles.textAreaWrapper, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                            <TextInput
                                style={[styles.textAreaInput, { color: theme.colors.text, fontFamily: typography.regular }]}
                                placeholder="Escribe observaciones"
                                placeholderTextColor={theme.colors.textSoft}
                                multiline
                                autoCapitalize="sentences"
                                value={formData.observaciones}
                                onChangeText={(text) => setFormData({ ...formData, observaciones: text })}
                            />
                        </View>
                    </StaggeredItem>

                    <StaggeredItem index={2}>
                        <View style={styles.extraHeaderRow}>
                            <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Campos extras</Text>
                        </View>
                    </StaggeredItem>

                    {extraFields.map((field, idx) => (
                        <StaggeredItem key={field.id} index={idx + 3}>
                            <View style={[styles.extraFieldCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                                <View style={styles.extraFieldTopRow}>
                                    <Text style={[styles.extraFieldTitle, { color: theme.colors.text, fontFamily: typography.semibold }]}>Campo extra {idx + 1}</Text>
                                    <TouchableOpacity onPress={() => removeExtraField(field.id)} style={styles.removeFieldBtn}>
                                        <Ionicons name="trash-outline" size={16} color={theme.colors.danger} />
                                    </TouchableOpacity>
                                </View>
                                <TextInput
                                    style={[styles.extraTextInput, { color: theme.colors.text, borderColor: theme.colors.border, backgroundColor: theme.colors.background, fontFamily: typography.regular }]}
                                    placeholder="Nombre"
                                    placeholderTextColor={theme.colors.textSoft}
                                    value={field.nombre}
                                    autoFocus={field.id === newExtraFieldId}
                                    onFocus={(event) => {
                                        ensureInputVisible(event);
                                        scrollToBottom();
                                    }}
                                    onChangeText={(text) => updateExtraField(field.id, 'nombre', text)}
                                />
                                <TextInput
                                    style={[styles.extraTextInput, { color: theme.colors.text, borderColor: theme.colors.border, backgroundColor: theme.colors.background, fontFamily: typography.regular }]}
                                    placeholder="Valor"
                                    placeholderTextColor={theme.colors.textSoft}
                                    value={field.valor}
                                    onFocus={(event) => {
                                        ensureInputVisible(event);
                                        scrollToBottom();
                                    }}
                                    onChangeText={(text) => updateExtraField(field.id, 'valor', text)}
                                />
                            </View>
                        </StaggeredItem>
                    ))}

                    <StaggeredItem index={extraFields.length + 3}>
                        <TouchableOpacity onPress={addExtraField} style={[styles.addFieldBtn, { borderColor: theme.colors.primary }]}>
                            <Ionicons name="add-circle-outline" size={18} color={theme.colors.icon} />
                            <Text style={[styles.addFieldText, { color: theme.colors.primary, fontFamily: typography.semibold }]}>Agregar campo extra</Text>
                        </TouchableOpacity>
                    </StaggeredItem>
                </View>
            );
        }

        if (currentStep === 7) {
            return (
                <View style={styles.stepContainer}>
                    <StaggeredItem index={0}>
                        <Text style={[styles.stepTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>Final</Text>
                        <Text style={[styles.stepDesc, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                            Captura la firma para finalizar el relevamiento.
                        </Text>
                    </StaggeredItem>

                    <StaggeredItem index={1}>
                        <TouchableOpacity
                            onPress={() => setShowSigModal(true)}
                            style={[styles.signatureArea, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}
                        >
                            {signature.length > 0 ? (
                                <View style={styles.signaturePreview}>
                                    <View style={[styles.signatureCanvasPreview, { borderColor: theme.colors.border }]}>
                                        <Svg
                                            height="100%"
                                            width="100%"
                                            viewBox="0 0 320 180"
                                            preserveAspectRatio="xMidYMid meet"
                                        >
                                            {getCenteredSignaturePaths(signature).map((path, index) => (
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
                                    <Text style={[styles.signatureHint, { color: theme.colors.success, fontFamily: typography.bold }]}>Firma capturada</Text>
                                </View>
                            ) : (
                                <View style={styles.signaturePreview}>
                                    <Ionicons name="create-outline" size={34} color={theme.colors.icon} />
                                    <Text style={[styles.signatureHint, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>Toca para firmar</Text>
                                </View>
                            )}
                        </TouchableOpacity>
                        {signature.length > 0 && (
                            <TouchableOpacity
                                onPress={() => setShowSigModal(true)}
                                style={[styles.resignButton, { borderColor: theme.colors.primary }]}
                            >
                                <Ionicons name="create-outline" size={15} color={theme.colors.icon} />
                                <Text style={[styles.resignButtonText, { color: theme.colors.primary, fontFamily: typography.semibold }]}>Volver a firmar</Text>
                            </TouchableOpacity>
                        )}
                    </StaggeredItem>

                    <Modal visible={showSigModal} animationType="slide" transparent>
                        <View style={styles.modalOverlay}>
                            <View style={styles.modalContent}>
                                <View style={styles.sigModalHeader}>
                                    <Text style={{ fontFamily: typography.bold, fontSize: fontSizes.lg, color: theme.colors.black }}>FIRMA DIGITAL</Text>
                                    <TouchableOpacity onPress={() => setShowSigModal(false)} style={styles.closeButton}>
                                        <Ionicons name="close" size={36} color={theme.colors.icon} />
                                    </TouchableOpacity>
                                </View>

                                <SignaturePad
                                    ref={signaturePadRef}
                                    onEnd={(paths) => setSignature(paths)}
                                />

                                <View style={styles.sigModalFooter}>
                                    <CustomButton
                                        title="Limpiar"
                                        onPress={() => {
                                            setSignature([]);
                                            if (signaturePadRef.current) signaturePadRef.current.clear();
                                        }}
                                        iconLeft="trash-outline"
                                        size="Base"
                                        variant="secondary"
                                        style={{ flex: 1 }}
                                    />
                                    <CustomButton
                                        title="Confirmar"
                                        onPress={() => {
                                            const paths = signaturePadRef.current?.getPaths?.() || [];
                                            if (paths.length > 0) {
                                                setSignature(paths);
                                            }
                                            setShowSigModal(false);
                                        }}
                                        iconRight="checkmark"
                                        size="Base"
                                        style={{ flex: 1 }}
                                    />
                                </View>
                            </View>
                        </View>
                    </Modal>
                </View>
            );
        }

        return (
            <View style={styles.stepContainer}>
                <View style={[styles.placeholderCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                    <Ionicons name="construct-outline" size={28} color={theme.colors.icon} />
                    <Text style={[styles.placeholderTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                        Paso {currentStep} en preparacion
                    </Text>
                    <Text style={[styles.placeholderText, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                        Ya quedo listo el paso 1. Seguimos con los siguientes en el mismo formato.
                    </Text>
                </View>
            </View>
        );
    };

    return (
        <KeyboardAvoidingView
            style={[styles.container, { backgroundColor: theme.colors.background }]}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            keyboardVerticalOffset={Platform.OS === 'ios' ? 10 : 0}
        >
            <View style={[styles.header, { borderBottomColor: theme.colors.border }]}>
                <FrostedBackButton
                    onPress={onCancel}
                    disabled={isSubmitting}
                    iconColor={theme.colors.icon}
                    tint={isDark ? 'dark' : 'light'}
                    style={styles.closeBtn}
                />
                <Text style={[styles.headerTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                    NUEVO RELEVAMIENTO
                </Text>
                <View style={styles.headerSpacer} />
            </View>

            <View style={styles.stepperScroll}>
                <ScrollView ref={stepperRef} horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.stepper}>
                    {steps.map((step, idx) => (
                        <React.Fragment key={step.id}>
                            <TouchableOpacity
                                activeOpacity={step.id <= maxVisitedStep ? 0.8 : 1}
                                disabled={step.id > maxVisitedStep || isSubmitting}
                                onPress={() => {
                                    if (step.id <= maxVisitedStep && !isSubmitting) {
                                        setCurrentStep(step.id);
                                        formScrollRef.current?.scrollTo({ y: 0, animated: true });
                                    }
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
                            {idx < steps.length - 1 && (
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

            <ScrollView
                ref={formScrollRef}
                contentContainerStyle={styles.scrollBody}
                keyboardShouldPersistTaps="handled"
                keyboardDismissMode="on-drag"
            >
                {renderStepContent()}
            </ScrollView>

            <View style={[styles.footer, { borderTopColor: theme.colors.border }]}>
                {currentStep > 1 && (
                    <CustomButton
                        title="ANTERIOR"
                        onPress={prevStep}
                        iconLeft="chevron-back"
                        size="L"
                        variant="secondary"
                        style={{ flex: 1, marginRight: 12 }}
                        disabled={isSubmitting}
                    />
                )}
                <CustomButton
                    title={currentStep === steps.length ? (isSubmitting ? 'FINALIZANDO...' : 'FINALIZAR') : 'SIGUIENTE'}
                    onPress={nextStep}
                    iconRight={currentStep === steps.length ? 'checkmark' : 'chevron-forward'}
                    size="L"
                    style={{ flex: 1.5 }}
                    disabled={isSubmitting}
                    loading={isSubmitting && currentStep === steps.length}
                />
            </View>

            {isSubmitting ? (
                <View style={styles.submittingOverlay}>
                    <View style={[styles.submittingCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                        <ActivityIndicator size="large" color={theme.colors.primary} />
                        <Text style={[styles.submittingText, { color: theme.colors.text, fontFamily: typography.semibold }]}>
                            Guardando relevamiento...
                        </Text>
                    </View>
                </View>
            ) : null}
        </KeyboardAvoidingView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    header: {
        paddingTop: Platform.OS === 'ios' ? 60 : 40,
        paddingBottom: 20,
        paddingHorizontal: 20,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottomWidth: 1,
    },
    closeBtn: {
        marginRight: 4,
    },
    headerSpacer: {
        width: 40,
    },
    headerTitle: {
        fontSize: fontSizes.xs,
        letterSpacing: 2,
    },
    stepperScroll: {
        backgroundColor: 'rgba(0,0,0,0.02)',
    },
    stepper: {
        paddingHorizontal: 20,
        paddingVertical: 15,
        alignItems: 'center',
    },
    stepNode: {
        alignItems: 'center',
        width: 72,
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
    scrollBody: {
        padding: 24,
    },
    stepContainer: {
        minHeight: 420,
    },
    stepTitle: {
        fontSize: 24,
        marginBottom: 8,
    },
    stepDesc: {
        fontSize: 14,
        lineHeight: 20,
        marginBottom: 24,
    },
    inputGroup: {
        marginBottom: 18,
    },
    label: {
        fontSize: 14,
        marginBottom: 8,
        marginLeft: 2,
    },
    inputWrapper: {
        flexDirection: 'row',
        alignItems: 'center',
        borderRadius: radii['2xl'],
        borderWidth: 1,
        paddingHorizontal: 16,
    },
    inputIcon: {
        marginRight: 12,
    },
    input: {
        flex: 1,
        fontSize: 16,
        height: 50,
    },
    optionsRow: {
        flexDirection: 'row',
        flexWrap: 'wrap',
    },
    optionChip: {
        borderWidth: 1,
        borderRadius: 12,
        paddingHorizontal: 12,
        paddingVertical: 8,
        marginRight: 8,
        marginBottom: 8,
    },
    optionText: {
        fontSize: 12,
    },
    sectionCard: {
        borderWidth: 1,
        borderRadius: 16,
        padding: 14,
        marginBottom: 16,
    },
    sectionTitle: {
        fontSize: 16,
        marginBottom: 8,
    },
    textAreaWrapper: {
        borderWidth: 1,
        borderRadius: radii.xl,
        padding: 12,
        marginBottom: 12,
    },
    textAreaInput: {
        minHeight: 96,
        textAlignVertical: 'top',
        fontSize: fontSizes.sm,
    },
    extraHeaderRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginTop: 10,
        marginBottom: 8,
    },
    extraFieldCard: {
        borderWidth: 1,
        borderRadius: radii.xl,
        padding: 12,
        marginBottom: 10,
    },
    extraFieldTopRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 6,
    },
    extraFieldTitle: {
        fontSize: fontSizes.xs,
    },
    extraTextInput: {
        borderWidth: 1,
        borderRadius: radii.lg,
        paddingHorizontal: 10,
        paddingVertical: 10,
        marginTop: 8,
        fontSize: 14,
    },
    addFieldBtn: {
        borderWidth: 1.5,
        borderRadius: 12,
        paddingVertical: 10,
        paddingHorizontal: 12,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        marginTop: 4,
    },
    addFieldText: {
        marginLeft: 8,
        fontSize: fontSizes.xs,
    },
    attachmentRow: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    attachmentName: {
        fontSize: 14,
    },
    attachmentType: {
        fontSize: 12,
        marginTop: 2,
    },
    removeFieldBtn: {
        padding: 6,
    },
    imageGrid: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        justifyContent: 'space-between',
    },
    imageActionBtn: {
        width: '48%',
        aspectRatio: 1,
        borderRadius: radii['2xl'],
        borderWidth: 2,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 12,
    },
    imageActionText: {
        fontSize: fontSizes.xs,
        marginTop: 8,
    },
    docsActionsRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'stretch',
    },
    docsActionBtn: {
        width: '31.5%',
        height: 92,
        borderRadius: radii.xl,
        borderWidth: 2,
        justifyContent: 'center',
        alignItems: 'center',
    },
    docsActionText: {
        fontSize: fontSizes.xxs,
        marginTop: 6,
        textAlign: 'center',
    },
    docsAttachmentsWrap: {
        marginTop: 10,
    },
    signatureArea: {
        height: 260,
        borderRadius: radii['2xl'],
        borderWidth: 1,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 20,
    },
    signaturePreview: {
        alignItems: 'center',
        justifyContent: 'center',
        width: '100%',
        paddingHorizontal: 14,
    },
    signatureHint: {
        fontSize: fontSizes.xs,
        marginTop: 10,
    },
    signatureCanvasPreview: {
        width: '100%',
        height: 180,
        borderWidth: 1,
        borderRadius: radii.lg,
        backgroundColor: designColors.bgSecondary,
        overflow: 'hidden',
    },
    resignButton: {
        marginTop: 10,
        borderWidth: 1,
        borderRadius: radii.lg,
        alignSelf: 'center',
        paddingHorizontal: 12,
        paddingVertical: 8,
        flexDirection: 'row',
        alignItems: 'center',
    },
    resignButtonText: {
        fontSize: 12,
        marginLeft: 6,
    },
    modalOverlay: {
        flex: 1,
        backgroundColor: 'rgba(0,0,0,0.5)',
        justifyContent: 'flex-end',
    },
    modalContent: {
        height: '75%',
        backgroundColor: '#FFF',
        borderTopLeftRadius: 24,
        borderTopRightRadius: 24,
        overflow: 'hidden',
    },
    sigModalHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: 20,
        borderBottomWidth: 1,
        borderBottomColor: '#EEE',
    },
    sigModalFooter: {
        flexDirection: 'row',
        padding: 20,
        paddingBottom: Platform.OS === 'ios' ? 35 : 20,
        gap: 12,
        borderTopWidth: 1,
        borderTopColor: '#EEE',
    },
    closeButton: {
        padding: 4,
    },
    imageCount: {
        fontSize: 12,
        marginBottom: 8,
    },
    imageItem: {
        width: '48%',
        aspectRatio: 1,
        borderRadius: 16,
        marginBottom: 12,
        overflow: 'hidden',
    },
    imageThumb: {
        width: '100%',
        height: '100%',
    },
    imageRemoveBtn: {
        position: 'absolute',
        top: 6,
        right: 6,
    },
    geoButton: {
        borderRadius: 12,
        paddingHorizontal: 14,
        paddingVertical: 12,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
    },
    geoButtonText: {
        color: '#FFFFFF',
        marginLeft: 8,
        fontSize: fontSizes.xs,
    },
    geoError: {
        marginTop: 10,
        fontSize: 12,
    },
    geoRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginTop: 14,
    },
    geoBadge: {
        width: '48%',
        borderRadius: 12,
        paddingHorizontal: 12,
        paddingVertical: 10,
    },
    geoLabel: {
        fontSize: fontSizes.xs,
        marginBottom: 4,
    },
    geoValue: {
        fontSize: 14,
    },
    mapPreview: {
        width: '100%',
        height: 260,
        borderRadius: 12,
        marginTop: 14,
    },
    mapPlaceholder: {
        width: '100%',
        height: 160,
        borderRadius: 12,
        marginTop: 14,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: 16,
    },
    mapPlaceholderText: {
        fontSize: 12,
        marginTop: 8,
        textAlign: 'center',
    },
    placeholderCard: {
        borderRadius: radii['2xl'],
        borderWidth: 1,
        padding: 20,
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 220,
    },
    placeholderTitle: {
        fontSize: fontSizes.lg,
        marginTop: 10,
        marginBottom: 8,
    },
    placeholderText: {
        fontSize: 14,
        textAlign: 'center',
        lineHeight: 20,
    },
    footer: {
        height: Platform.OS === 'ios' ? 100 : 80,
        paddingHorizontal: 24,
        paddingBottom: Platform.OS === 'ios' ? 30 : 15,
        flexDirection: 'row',
        alignItems: 'center',
        borderTopWidth: 1,
    },
    submittingOverlay: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: 'rgba(0,0,0,0.25)',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 999,
    },
    submittingCard: {
        borderWidth: 1,
        borderRadius: 16,
        paddingVertical: 18,
        paddingHorizontal: 22,
        alignItems: 'center',
        minWidth: 220,
    },
    submittingText: {
        fontSize: 14,
        marginTop: 10,
        textAlign: 'center',
    },
});
