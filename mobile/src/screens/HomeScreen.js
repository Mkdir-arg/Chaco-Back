import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import StaggeredItem from '../components/StaggeredItem';
import { fontSizes, radii } from '../theme';

const ACTIONS = [
    { id: 'sync', title: 'Sincronizacion', icon: 'cloud-upload-outline', subtitle: 'Enviar relevamientos pendientes' },
];

export default function HomeScreen({ onOpenRelevamientos, onSyncPress, syncPendingCount = 0 }) {
    const { theme, typography } = useTheme();
    const { user } = useAuth();
    const displayName = user?.username || user?.nombre || 'Usuario';

    const handleActionPress = (actionId) => {
        if (actionId === 'relevamientos') return onOpenRelevamientos?.();
        if (actionId === 'sync') return onSyncPress?.();
    };

    return (
        <ScrollView style={[styles.container, { backgroundColor: theme.colors.background }]} contentContainerStyle={styles.content}>
            <StaggeredItem index={0}>
                <View style={styles.hero}>
                    <View style={styles.heroText}>
                        <Text style={[styles.eyebrow, { color: theme.colors.primary, fontFamily: typography.bold }]}>
                            Relevamiento Chaco
                        </Text>
                        <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.extrabold }]}>
                            Hola, {displayName}
                        </Text>
                        <Text style={[styles.sectionSubtitle, { color: theme.colors.textMuted, fontFamily: typography.medium }]}>
                            Recibi tus relevamientos asignados, entra a cada caso y completa los pasos en territorio.
                        </Text>
                    </View>
                    <View style={[styles.statusPill, { backgroundColor: theme.colors.successSoft, borderColor: theme.colors.success }]}>
                        <View style={[styles.statusDot, { backgroundColor: theme.colors.success }]} />
                        <Text style={[styles.statusText, { color: theme.colors.text, fontFamily: typography.bold }]}>
                            {syncPendingCount > 0 ? `${syncPendingCount} pendientes` : 'Al dia'}
                        </Text>
                    </View>
                </View>
            </StaggeredItem>

            <StaggeredItem index={1}>
                <Pressable
                    onPress={() => handleActionPress('relevamientos')}
                    style={({ pressed }) => [styles.primaryActionWrap, { opacity: pressed ? 0.92 : 1 }]}
                >
                    <LinearGradient
                        colors={theme.colors.gradients?.brand}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 1 }}
                        style={styles.primaryAction}
                    >
                        <View style={styles.primaryIconBadge}>
                            <Ionicons name="clipboard-outline" size={fontSizes['2xl']} color={theme.colors.white} />
                        </View>
                        <View style={styles.primaryActionText}>
                            <Text style={[styles.primaryActionTitle, { color: theme.colors.white, fontFamily: typography.extrabold }]}>
                                Mis relevamientos
                            </Text>
                            <Text style={[styles.primaryActionSubtitle, { color: theme.colors.white, fontFamily: typography.medium }]}>
                                Ver asignados, abrir el relevamiento y completar la carga paso a paso.
                            </Text>
                        </View>
                        <Ionicons name="arrow-forward" size={fontSizes.xl} color={theme.colors.white} />
                    </LinearGradient>
                </Pressable>
            </StaggeredItem>

            <View style={styles.sectionHeader}>
                <Text style={[styles.blockTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                    Operacion
                </Text>
            </View>

            <View style={styles.actionsWrap}>
                {ACTIONS.map((action, index) => (
                    <StaggeredItem key={action.id} index={index + 2}>
                        <Pressable
                            onPress={() => handleActionPress(action.id)}
                            style={({ pressed }) => [
                                styles.actionRow,
                                {
                                    backgroundColor: theme.colors.surface,
                                    borderColor: theme.colors.border,
                                    shadowColor: theme.colors.shadow,
                                    opacity: pressed ? 0.86 : 1,
                                },
                            ]}
                        >
                            <View style={[styles.iconBadge, { backgroundColor: theme.colors.brandSoft }]}>
                                <Ionicons name={action.icon} size={22} color={theme.colors.icon} />
                            </View>
                            <View style={styles.cardTextWrap}>
                                <Text style={[styles.cardTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                                    {action.title}
                                </Text>
                                <Text style={[styles.cardSubtitle, { color: theme.colors.textMuted, fontFamily: typography.medium }]}>
                                    {action.subtitle}
                                </Text>
                            </View>
                            <Ionicons name="chevron-forward" size={20} color={theme.colors.textSoft} />
                        </Pressable>
                    </StaggeredItem>
                ))}
            </View>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    content: {
        padding: 20,
        paddingBottom: 120,
    },
    hero: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 16,
        marginBottom: 18,
    },
    heroText: {
        flex: 1,
    },
    eyebrow: {
        fontSize: fontSizes.xs,
        marginBottom: 6,
    },
    sectionTitle: {
        fontSize: fontSizes['2xl'],
        lineHeight: 32,
    },
    sectionSubtitle: {
        fontSize: 14,
        lineHeight: 20,
        marginTop: 6,
        maxWidth: 280,
    },
    statusPill: {
        minHeight: 30,
        borderRadius: radii.full,
        borderWidth: 1,
        paddingHorizontal: 10,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
    },
    statusDot: {
        width: 7,
        height: 7,
        borderRadius: radii.base,
    },
    statusText: {
        fontSize: fontSizes.xs,
    },
    primaryActionWrap: {
        borderRadius: radii['2xl'],
        marginBottom: 20,
        overflow: 'hidden',
    },
    primaryAction: {
        minHeight: 132,
        padding: 18,
        borderRadius: radii['2xl'],
        flexDirection: 'row',
        alignItems: 'center',
        gap: 14,
    },
    primaryIconBadge: {
        width: 48,
        height: 48,
        borderRadius: radii['3xl'],
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(255,255,255,0.22)',
    },
    primaryActionText: {
        flex: 1,
    },
    primaryActionTitle: {
        fontSize: fontSizes.xl,
        lineHeight: 27,
        marginBottom: 4,
    },
    primaryActionSubtitle: {
        fontSize: fontSizes.xs,
        lineHeight: 19,
    },
    sectionHeader: {
        marginBottom: 10,
    },
    blockTitle: {
        fontSize: fontSizes.base,
    },
    actionsWrap: {
        width: '100%',
        gap: 12,
    },
    actionRow: {
        minHeight: 78,
        borderRadius: radii.xl,
        borderWidth: 1,
        padding: 14,
        flexDirection: 'row',
        alignItems: 'center',
        shadowOffset: { width: 0, height: 6 },
        shadowOpacity: 0.05,
        shadowRadius: 12,
        elevation: 2,
    },
    iconBadge: {
        width: 42,
        height: 42,
        borderRadius: radii.full,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 12,
    },
    cardTextWrap: {
        flex: 1,
    },
    cardTitle: {
        fontSize: fontSizes.sm,
        lineHeight: 20,
    },
    cardSubtitle: {
        fontSize: fontSizes.xs,
        lineHeight: 18,
        marginTop: 2,
    },
});
