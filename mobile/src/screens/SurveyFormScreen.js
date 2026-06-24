import React, { useState, useRef } from 'react';
import { View, Text, StyleSheet, ScrollView, TextInput, Pressable, Platform, TouchableOpacity, Modal } from 'react-native';
import SignaturePad from '../components/SignaturePad';
import { useTheme } from '../context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import MaskedView from '@react-native-masked-view/masked-view';
import StaggeredItem from '../components/StaggeredItem';
import CustomButton from '../components/CustomButton';
import { fontSizes, radii } from '../theme';

const GradientIcon = ({ name, size = 24, style, colors }) => {
    return (
        <View style={[{ width: size, height: size }, style]}>
            <MaskedView
                style={{ flex: 1 }}
                maskElement={
                    <View style={{ backgroundColor: 'transparent', justifyContent: 'center', alignItems: 'center', flex: 1 }}>
                        <Ionicons name={name} size={size} color="black" />
                    </View>
                }
            >
                <LinearGradient
                    colors={colors}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 0, y: 1 }}
                    style={{ flex: 1 }}
                />
            </MaskedView>
        </View>
    );
};

export default function SurveyFormScreen({ onCancel, onSave }) {
    const { theme, typography } = useTheme();
    const [signature, setSignature] = useState([]);
    const [showSigModal, setShowSigModal] = useState(false);
    const signaturePadRef = useRef(null);

    const [formData, setFormData] = useState({
        nombre: '',
        dni: '',
        observaciones: '',
        ubicacion: 'Geolocalización activa: -34.6037, -58.3816',
    });

    const renderInput = (label, placeholder, key, icon, multiline = false) => (
        <View style={styles.inputGroup}>
            <Text style={[styles.label, { color: theme.colors.text, fontFamily: typography.semibold }]}>{label}</Text>
            <View style={[styles.inputWrapper, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                <Ionicons name={icon} size={20} color={theme.colors.icon} style={styles.inputIcon} />
                <TextInput
                    style={[styles.input, { color: theme.colors.text, fontFamily: typography.regular, height: multiline ? 100 : 50 }]}
                    placeholder={placeholder}
                    placeholderTextColor={theme.colors.textMuted}
                    value={formData[key]}
                    onChangeText={(text) => setFormData({ ...formData, [key]: text })}
                    multiline={multiline}
                />
            </View>
        </View>
    );

    return (
        <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
            <View style={[styles.header, { borderBottomColor: theme.colors.border }]}>
                <TouchableOpacity onPress={onCancel} style={styles.backBtn}>
                    <Ionicons name="close" size={28} color={theme.colors.text} />
                </TouchableOpacity>
                <Text style={[styles.headerTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                    NUEVO RELEVAMIENTO
                </Text>
            </View>

            <ScrollView contentContainerStyle={styles.scrollContent}>
                <StaggeredItem index={0}>
                    <View style={[styles.locationBadge, { backgroundColor: `${theme.colors.success}15` }]}>
                        <Ionicons name="location" size={16} color={theme.colors.success} />
                        <Text style={[styles.locationText, { color: theme.colors.success, fontFamily: typography.medium }]}>
                            {formData.ubicacion}
                        </Text>
                    </View>
                </StaggeredItem>

                <StaggeredItem index={1}>
                    {renderInput('Nombre del Titular', 'Ej: Juan Pérez', 'nombre', 'person')}
                </StaggeredItem>

                <StaggeredItem index={2}>
                    {renderInput('DNI / Documento', 'Número de identificación', 'dni', 'card')}
                </StaggeredItem>

                <StaggeredItem index={3}>
                    <Text style={[styles.label, { color: theme.colors.text, fontFamily: typography.semibold }]}>Evidencias (Fotos)</Text>
                    <View style={styles.evidenceGrid}>
                        <TouchableOpacity style={[styles.addEvidenceBtn, { backgroundColor: theme.colors.surface, borderColor: theme.colors.primary, borderStyle: 'dashed' }]}>
                            <Ionicons name="camera" size={32} color={theme.colors.icon} />
                            <Text style={[styles.addEvidenceText, { color: theme.colors.primary, fontFamily: typography.bold }]}>TOMAR FOTO</Text>
                        </TouchableOpacity>
                        <View style={[styles.photoPlaceholder, { backgroundColor: theme.colors.surfaceAlt }]} />
                        <View style={[styles.photoPlaceholder, { backgroundColor: theme.colors.surfaceAlt }]} />
                    </View>
                </StaggeredItem>

                <StaggeredItem index={4}>
                    {renderInput('Observaciones de Campo', 'Detalles del entorno, necesidades urgentes...', 'observaciones', 'create', true)}
                </StaggeredItem>

                <StaggeredItem index={5}>
                    <Text style={[styles.label, { color: theme.colors.text, fontFamily: typography.semibold }]}>Firma Digital del Titular</Text>
                    <TouchableOpacity
                        onPress={() => setShowSigModal(true)}
                        style={[styles.signatureBox, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}
                    >
                        {signature.length > 0 ? (
                            <View style={styles.signaturePreview}>
                                <Ionicons name="checkmark-circle" size={32} color={theme.colors.success} />
                                <Text style={[styles.signatureHint, { color: theme.colors.success, fontFamily: typography.bold }]}>Firma capturada</Text>
                            </View>
                        ) : (
                            <>
                                <Ionicons name="pencil" size={32} color={theme.colors.icon} style={{ opacity: 0.3 }} />
                                <Text style={[styles.signatureHint, { color: theme.colors.textMuted, fontFamily: typography.regular }]}>Toca aquí para firmar</Text>
                            </>
                        )}
                    </TouchableOpacity>

                    {/* Modal para la Firma */}
                    <Modal visible={showSigModal} animationType="slide" transparent={true}>
                        <View style={styles.modalOverlay}>
                            <View style={styles.modalContent}>
                                <View style={styles.sigModalHeader}>
                                    <Text style={{ fontFamily: typography.bold, fontSize: fontSizes.lg, color: theme.colors.black }}>FIRMA DIGITAL</Text>
                                    <TouchableOpacity
                                        onPress={() => setShowSigModal(false)}
                                        style={styles.closeButton}
                                    >
                                        <Ionicons name="close" size={40} color={theme.colors.icon} />
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
                                            if (signaturePadRef.current) {
                                                signaturePadRef.current.clear();
                                            }
                                        }}
                                        iconLeft="trash-outline"
                                        size="Base"
                                        variant="secondary"
                                        style={{ flex: 1 }}
                                    />

                                    <CustomButton
                                        title="Confirmar"
                                        onPress={() => setShowSigModal(false)}
                                        iconRight="checkmark"
                                        size="Base"
                                        style={{ flex: 1 }}
                                    />
                                </View>
                            </View>
                        </View>
                    </Modal>
                </StaggeredItem>

                <StaggeredItem index={6}>
                    <View style={styles.footerBtns}>
                        <CustomButton
                            title="GUARDAR Y SINCRONIZAR"
                            onPress={onSave}
                            iconLeft="cloud-upload"
                            size="L"
                        />
                    </View>
                </StaggeredItem>
            </ScrollView>
        </View>
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
        borderBottomWidth: 1,
    },
    backBtn: {
        marginRight: 16,
    },
    headerTitle: {
        fontSize: fontSizes.lg,
        letterSpacing: 1,
    },
    scrollContent: {
        padding: 20,
    },
    locationBadge: {
        flexDirection: 'row',
        alignItems: 'center',
        padding: 12,
        borderRadius: radii.xl,
        marginBottom: 24,
    },
    locationText: {
        fontSize: fontSizes.xs,
        marginLeft: 8,
    },
    inputGroup: {
        marginBottom: 20,
    },
    label: {
        fontSize: fontSizes.sm,
        marginBottom: 8,
        marginLeft: 4,
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
        fontSize: fontSizes.base,
    },
    evidenceGrid: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        marginBottom: 24,
    },
    addEvidenceBtn: {
        width: '31%',
        aspectRatio: 1,
        borderRadius: radii['2xl'],
        borderWidth: 2,
        justifyContent: 'center',
        alignItems: 'center',
    },
    addEvidenceText: {
        fontSize: fontSizes.xxs,
        marginTop: 4,
    },
    photoPlaceholder: {
        width: '31%',
        aspectRatio: 1,
        borderRadius: radii['2xl'],
    },
    signatureBox: {
        height: 120,
        borderRadius: radii['2xl'],
        borderWidth: 1,
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 24,
    },
    signatureHint: {
        fontSize: fontSizes.xs,
        marginTop: 10,
    },
    signaturePreview: {
        justifyContent: 'center',
        alignItems: 'center',
    },
    sigModalHeader: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: 20,
        borderBottomWidth: 1,
        borderBottomColor: '#EEE',
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
    footerBtns: {
        marginTop: 10,
        marginBottom: 40,
    }
});
