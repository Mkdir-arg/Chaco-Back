import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, TextInput, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import CustomButton from '../components/CustomButton';
import FrostedBackButton from '../components/FrostedBackButton';
import citizenLegajoService from '../services/citizenLegajoService';
import { fontSizes, radii } from '../theme';

const VIA_INGRESO_OPTIONS = ['ESPONTANEA', 'DERIVACION', 'JUDICIAL', 'HOSPITAL'];
const RIESGO_OPTIONS = ['BAJO', 'MEDIO', 'ALTO'];

const createEmptyForm = () => ({
  local_id: null,
  citizen_id: null,
  legajo_id: null,
  nombre: '',
  apellido: '',
  dni: '',
  telefono: '',
  domicilio: '',
  via_ingreso: 'ESPONTANEA',
  nivel_riesgo: 'BAJO',
  estado: 'EN_SEGUIMIENTO',
  notas: '',
});

export default function CitizenLegajoScreen({ onClose, onSaved }) {
  const { theme, typography, isDark } = useTheme();
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState(createEmptyForm());

  const selectedRecord = useMemo(
    () => records.find((item) => item.local_id === selectedId) || null,
    [records, selectedId]
  );

  const loadRecords = async (refreshFromRemote = true) => {
    setLoading(true);
    const result = await citizenLegajoService.getCitizenLegajoRecords({ refreshFromRemote });
    setRecords(result.records || []);
    if (result.error) {
      setInfoMessage('Mostrando datos locales. Pendiente de sincronizacion.');
    } else {
      setInfoMessage('');
    }
    setLoading(false);
  };

  useEffect(() => {
    loadRecords(true);
  }, []);

  const applyRecordToForm = (record) => {
    setSelectedId(record.local_id);
    setForm({
      local_id: record.local_id,
      citizen_id: record.citizen_id,
      legajo_id: record.legajo_id,
      nombre: record.citizen?.nombre || '',
      apellido: record.citizen?.apellido || '',
      dni: record.citizen?.dni || '',
      telefono: record.citizen?.telefono || '',
      domicilio: record.citizen?.domicilio || '',
      via_ingreso: record.legajo?.via_ingreso || 'ESPONTANEA',
      nivel_riesgo: record.legajo?.nivel_riesgo || 'BAJO',
      estado: record.legajo?.estado || 'EN_SEGUIMIENTO',
      notas: record.legajo?.notas || '',
    });
    setErrorMessage('');
    setInfoMessage(record.synced ? 'Registro sincronizado' : 'Registro local pendiente de sincronizacion');
  };

  const resetForm = () => {
    setSelectedId(null);
    setForm(createEmptyForm());
    setErrorMessage('');
    setInfoMessage('');
  };

  const handleSave = async () => {
    if (!form.nombre.trim() || !form.apellido.trim() || !form.dni.trim()) {
      setErrorMessage('Nombre, apellido y DNI son obligatorios.');
      return;
    }

    setSaving(true);
    setErrorMessage('');

    try {
      const result = await citizenLegajoService.saveCitizenLegajo({
        local_id: form.local_id,
        citizen_id: form.citizen_id,
        legajo_id: form.legajo_id,
        citizen: {
          nombre: form.nombre.trim(),
          apellido: form.apellido.trim(),
          dni: form.dni.trim(),
          telefono: form.telefono.trim(),
          domicilio: form.domicilio.trim(),
        },
        legajo: {
          via_ingreso: form.via_ingreso,
          nivel_riesgo: form.nivel_riesgo,
          estado: form.estado,
          notas: form.notas.trim(),
        },
      });

      const pending = await citizenLegajoService.getPendingCount();
      if (pending > 0 || result.syncResult?.failed > 0) {
        setInfoMessage('Guardado local. Se sincronizara cuando haya conexion.');
      } else {
        setInfoMessage('Guardado y sincronizado en Supabase.');
      }

      await loadRecords(true);
      onSaved?.();
    } catch (error) {
      setErrorMessage(error?.message || 'No se pudo guardar el registro.');
    } finally {
      setSaving(false);
    }
  };

  const handleManualSync = async () => {
    setSyncing(true);
    const result = await citizenLegajoService.syncPendingOperations();
    await loadRecords(true);
    setSyncing(false);
    onSaved?.();

    if (result.failed > 0) {
      setInfoMessage(`Sincronizadas ${result.synced}. Fallidas ${result.failed}.`);
    } else {
      setInfoMessage(`Sincronizadas ${result.synced}.`);
    }
  };

  const setField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const renderInput = (label, key, placeholder, options = {}) => (
    <View style={styles.fieldBlock}>
      <Text style={[styles.label, { color: theme.colors.text, fontFamily: typography.medium }]}>{label}</Text>
      <TextInput
        value={form[key]}
        onChangeText={(text) => setField(key, text)}
        placeholder={placeholder}
        placeholderTextColor={theme.colors.textMuted}
        style={[
          styles.input,
          {
            color: theme.colors.text,
            borderColor: theme.colors.border,
            backgroundColor: theme.colors.surface,
            minHeight: options.multiline ? 90 : 50,
            textAlignVertical: options.multiline ? 'top' : 'center',
            fontFamily: typography.regular,
          },
        ]}
        multiline={!!options.multiline}
      />
    </View>
  );

  const renderSelector = (label, key, choices) => (
    <View style={styles.fieldBlock}>
      <Text style={[styles.label, { color: theme.colors.text, fontFamily: typography.medium }]}>{label}</Text>
      <View style={styles.selectorRow}>
        {choices.map((choice) => (
          <Pressable
            key={choice}
            onPress={() => setField(key, choice)}
            style={[
              styles.selectorChip,
              {
                borderColor: theme.colors.border,
                backgroundColor: theme.colors.surface,
              },
              form[key] === choice && {
                borderColor: theme.colors.primary,
                backgroundColor: `${theme.colors.primary}20`,
              },
            ]}
          >
            <Text
              style={[
                styles.selectorText,
                {
                  color: form[key] === choice ? theme.colors.primary : theme.colors.text,
                  fontFamily: typography.medium,
                },
              ]}
            >
              {choice}
            </Text>
          </Pressable>
        ))}
      </View>
    </View>
  );

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <View style={[styles.header, { borderBottomColor: theme.colors.border }]}>
        <FrostedBackButton
          onPress={onClose}
          iconColor={theme.colors.icon}
          tint={isDark ? 'dark' : 'light'}
          style={styles.headerIcon}
        />
        <Text style={[styles.headerTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
          CIUDADANOS Y LEGAJOS
        </Text>
        <Pressable onPress={resetForm} style={styles.headerIcon}>
          <Ionicons name="add-circle-outline" size={26} color={theme.colors.icon} />
        </Pressable>
      </View>

      <ScrollView style={styles.body} contentContainerStyle={styles.content}>
        <View style={styles.section}>
          <View style={styles.sectionTitleRow}>
            <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
              Ciudadanos
            </Text>
            <CustomButton
              title={syncing ? 'Sincronizando...' : 'Sincronizar'}
              onPress={handleManualSync}
              size="SM"
              iconLeft="cloud-upload-outline"
              disabled={syncing}
              style={{ width: 160 }}
            />
          </View>

          {loading ? (
            <Text style={[styles.message, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
              Cargando registros...
            </Text>
          ) : records.length === 0 ? (
            <Text style={[styles.message, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
              Todavia no hay registros.
            </Text>
          ) : (
            records.map((record) => (
              <Pressable
                key={record.local_id}
                onPress={() => applyRecordToForm(record)}
                style={[
                  styles.recordCard,
                  {
                    borderColor: theme.colors.border,
                    backgroundColor: theme.colors.surface,
                  },
                  selectedRecord?.local_id === record.local_id && {
                    borderColor: theme.colors.primary,
                  },
                ]}
              >
                <View style={styles.recordTop}>
                  <Text style={[styles.recordName, { color: theme.colors.text, fontFamily: typography.semibold }]}>
                    {record.citizen?.apellido} {record.citizen?.nombre}
                  </Text>
                  <View
                    style={[
                      styles.syncBadge,
                      { backgroundColor: record.synced ? theme.colors.successSoft : theme.colors.warningSoft },
                    ]}
                  >
                    <Text
                      style={[
                        styles.syncBadgeText,
                        { color: record.synced ? theme.colors.success : theme.colors.warning, fontFamily: typography.bold },
                      ]}
                    >
                      {record.synced ? 'SYNC' : 'LOCAL'}
                    </Text>
                  </View>
                </View>
                <Text style={[styles.recordMeta, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                  DNI: {record.citizen?.dni || '-'} | Riesgo: {record.legajo?.nivel_riesgo || '-'}
                </Text>
              </Pressable>
            ))
          )}
        </View>

        <View style={styles.section}>
          <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
            {selectedRecord ? 'Editar registro' : 'Nuevo registro'}
          </Text>

          {renderInput('Nombre', 'nombre', 'Nombre')}
          {renderInput('Apellido', 'apellido', 'Apellido')}
          {renderInput('DNI', 'dni', 'Documento')}
          {renderInput('Telefono', 'telefono', 'Telefono')}
          {renderInput('Domicilio', 'domicilio', 'Domicilio')}

          {renderSelector('Via de ingreso', 'via_ingreso', VIA_INGRESO_OPTIONS)}
          {renderSelector('Nivel de riesgo', 'nivel_riesgo', RIESGO_OPTIONS)}
          {renderInput('Notas de legajo', 'notas', 'Notas del caso', { multiline: true })}

          {!!errorMessage && (
            <Text style={[styles.errorText, { color: theme.colors.danger, fontFamily: typography.medium }]}>
              {errorMessage}
            </Text>
          )}
          {!!infoMessage && (
            <Text style={[styles.infoText, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
              {infoMessage}
            </Text>
          )}

          <View style={styles.formButtons}>
            <CustomButton
              title="Guardar ciudadano y legajo"
              onPress={handleSave}
              size="L"
              iconLeft="save-outline"
              loading={saving}
            />
          </View>
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    paddingTop: Platform.OS === 'ios' ? 58 : 36,
    paddingBottom: 16,
    paddingHorizontal: 18,
    borderBottomWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerIcon: {
    width: 36,
    height: 36,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerTitle: {
    fontSize: fontSizes.sm,
    letterSpacing: 1.5,
  },
  body: {
    flex: 1,
  },
  content: {
    padding: 18,
    paddingBottom: 50,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: fontSizes.lg,
    marginBottom: 12,
  },
  message: {
    fontSize: fontSizes.sm,
  },
  recordCard: {
    borderWidth: 1,
    borderRadius: radii.xl,
    padding: 12,
    marginBottom: 10,
  },
  recordTop: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  recordName: {
    fontSize: fontSizes.sm,
  },
  recordMeta: {
    fontSize: fontSizes.xs,
  },
  syncBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.lg,
  },
  syncBadgeText: {
    fontSize: fontSizes.xs,
  },
  fieldBlock: {
    marginBottom: 14,
  },
  label: {
    fontSize: fontSizes.xs,
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderRadius: radii.xl,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: fontSizes.sm,
  },
  selectorRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  selectorChip: {
    borderWidth: 1,
    borderRadius: radii.lg,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  selectorText: {
    fontSize: fontSizes.xs,
  },
  errorText: {
    marginTop: 4,
    fontSize: fontSizes.xs,
  },
  infoText: {
    marginTop: 8,
    fontSize: fontSizes.xs,
  },
  formButtons: {
    marginTop: 14,
  },
});
