import React from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable } from 'react-native';
import { useTheme } from '../context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';
import StaggeredItem from '../components/StaggeredItem';
import { fontSizes, radii } from '../theme';

const ACTION_COLOR = '#4338CA';
const ACTION_BORDER = '#3730A3';
const ACTION_SOFT = 'rgba(255,255,255,0.16)';
const NOTIFICATION_COLOR = '#EF4444';

export default function HomeScreen({
    onOpenRelevamientos,
    onSyncPress,
    newRelevamientosCount = 0,
    syncPendingCount = 0,
}) {
    const { theme, typography } = useTheme();
    const newLabel = newRelevamientosCount > 9 ? '9+' : String(newRelevamientosCount);
    const syncLabel = syncPendingCount > 9 ? '9+' : String(syncPendingCount);

    return (
        <ScrollView style={[styles.container, { backgroundColor: theme.colors.background }]} contentContainerStyle={styles.content}>
            <StaggeredItem index={0}>
                <View style={styles.metricsRow}>
                    <Pressable
                        onPress={onOpenRelevamientos}
                        style={({ pressed }) => [
                            styles.metricCard,
                            {
                                backgroundColor: theme.colors.surface,
                                borderColor: theme.colors.border,
                                shadowColor: theme.colors.shadow,
                                opacity: pressed ? 0.88 : 1,
                            },
                        ]}
                    >
                        <View style={[styles.metricIcon, { backgroundColor: theme.colors.brandSoft }]}>
                            <Ionicons name="sparkles-outline" size={18} color={theme.colors.icon} />
                        </View>
                        <Text style={[styles.metricValue, { color: theme.colors.text, fontFamily: typography.extrabold }]}>
                            {newLabel}
                        </Text>
                        <Text style={[styles.metricLabel, { color: theme.colors.textSoft, fontFamily: typography.bold }]}>
                            Nuevos
                        </Text>
                    </Pressable>

                    <Pressable
                        onPress={onSyncPress}
                        style={({ pressed }) => [
                            styles.metricCard,
                            {
                                backgroundColor: theme.colors.surface,
                                borderColor: theme.colors.border,
                                shadowColor: theme.colors.shadow,
                                opacity: pressed ? 0.88 : 1,
                            },
                        ]}
                    >
                        <View style={[styles.metricIcon, { backgroundColor: syncPendingCount > 0 ? theme.colors.warningSoft : theme.colors.successSoft }]}>
                            <Ionicons
                                name={syncPendingCount > 0 ? 'cloud-upload-outline' : 'cloud-done-outline'}
                                size={18}
                                color={syncPendingCount > 0 ? theme.colors.warning : theme.colors.success}
                            />
                        </View>
                        <Text style={[styles.metricValue, { color: theme.colors.text, fontFamily: typography.extrabold }]}>
                            {syncLabel}
                        </Text>
                        <Text style={[styles.metricLabel, { color: theme.colors.textSoft, fontFamily: typography.bold }]}>
                            Sync
                        </Text>
                    </Pressable>
                </View>
            </StaggeredItem>

            <StaggeredItem index={1}>
                <Pressable
                    onPress={onOpenRelevamientos}
                    style={({ pressed }) => [
                        styles.primaryAction,
                        {
                            backgroundColor: ACTION_COLOR,
                            borderColor: ACTION_BORDER,
                            shadowColor: theme.colors.shadow,
                            opacity: pressed ? 0.9 : 1,
                        },
                    ]}
                >
                    <View style={styles.primaryTopRow}>
                        <View style={styles.primaryIconBadge}>
                            <Ionicons name="clipboard-outline" size={fontSizes['2xl']} color="#FFFFFF" />
                        </View>
                        {newRelevamientosCount > 0 ? (
                            <View style={styles.newBadge}>
                                <View style={styles.newBadgeDot} />
                                <Text style={[styles.newBadgeText, { fontFamily: typography.bold }]}>
                                    {newRelevamientosCount > 9 ? '9+ nuevos' : `${newRelevamientosCount} nuevo${newRelevamientosCount === 1 ? '' : 's'}`}
                                </Text>
                            </View>
                        ) : null}
                    </View>

                    <View style={styles.primaryBottomRow}>
                        <View style={styles.primaryActionText}>
                            <Text style={[styles.primaryActionTitle, { color: '#FFFFFF', fontFamily: typography.extrabold }]}>
                                Mis relevamientos
                            </Text>
                            <Text style={[styles.primaryActionMeta, { color: 'rgba(255,255,255,0.78)', fontFamily: typography.bold }]}>
                                ASIGNADOS
                            </Text>
                        </View>
                        <View style={styles.primaryArrow}>
                            <Ionicons name="arrow-forward" size={fontSizes.lg} color="#FFFFFF" />
                        </View>
                    </View>
                </Pressable>
            </StaggeredItem>

            <StaggeredItem index={2}>
                <Pressable
                    onPress={onSyncPress}
                    style={({ pressed }) => [
                        styles.syncRow,
                        {
                            backgroundColor: theme.colors.surface,
                            borderColor: theme.colors.border,
                            shadowColor: theme.colors.shadow,
                            opacity: pressed ? 0.88 : 1,
                        },
                    ]}
                >
                    <View style={[styles.syncIcon, { backgroundColor: syncPendingCount > 0 ? theme.colors.warningSoft : theme.colors.successSoft }]}>
                        <Ionicons
                            name="sync-outline"
                            size={20}
                            color={syncPendingCount > 0 ? theme.colors.warning : theme.colors.success}
                        />
                    </View>
                    <Text style={[styles.syncTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                        Sincronizar
                    </Text>
                    <Ionicons name="chevron-forward" size={20} color={theme.colors.textSoft} />
                </Pressable>
            </StaggeredItem>
        </ScrollView>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    content: {
        padding: 18,
        paddingBottom: 120,
        gap: 14,
    },
    metricsRow: {
        flexDirection: 'row',
        gap: 12,
    },
    metricCard: {
        flex: 1,
        minHeight: 106,
        borderRadius: radii.xl,
        borderWidth: 1,
        padding: 14,
        shadowOffset: { width: 0, height: 6 },
        shadowOpacity: 0.05,
        shadowRadius: 12,
        elevation: 2,
    },
    metricIcon: {
        width: 34,
        height: 34,
        borderRadius: radii.full,
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 10,
    },
    metricValue: {
        fontSize: fontSizes['2xl'],
        lineHeight: 31,
    },
    metricLabel: {
        marginTop: 1,
        fontSize: fontSizes.xxs,
        lineHeight: 13,
        textTransform: 'uppercase',
    },
    primaryAction: {
        position: 'relative',
        minHeight: 168,
        padding: 18,
        borderRadius: radii['2xl'],
        borderWidth: 1,
        justifyContent: 'space-between',
        overflow: 'hidden',
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.06,
        shadowRadius: 14,
        elevation: 2,
    },
    primaryTopRow: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
    },
    primaryIconBadge: {
        width: 50,
        height: 50,
        borderRadius: radii['3xl'],
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: ACTION_SOFT,
    },
    newBadge: {
        minHeight: 24,
        borderRadius: radii.full,
        paddingHorizontal: 10,
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: '#FFFBEB',
    },
    newBadgeDot: {
        width: 7,
        height: 7,
        borderRadius: radii.full,
        marginRight: 6,
        backgroundColor: NOTIFICATION_COLOR,
    },
    newBadgeText: {
        color: '#7F1D1D',
        fontSize: fontSizes.xxs,
        lineHeight: 13,
        textTransform: 'uppercase',
    },
    primaryBottomRow: {
        flexDirection: 'row',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
    },
    primaryActionText: {
        flex: 1,
        paddingRight: 14,
    },
    primaryActionTitle: {
        fontSize: fontSizes['2xl'],
        lineHeight: 32,
        marginBottom: 4,
    },
    primaryActionMeta: {
        fontSize: fontSizes.xxs,
        lineHeight: 13,
        letterSpacing: 0,
    },
    primaryArrow: {
        width: 36,
        height: 36,
        borderRadius: radii.full,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: ACTION_SOFT,
    },
    syncRow: {
        minHeight: 66,
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
    syncIcon: {
        width: 38,
        height: 38,
        borderRadius: radii.full,
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 12,
    },
    syncTitle: {
        flex: 1,
        fontSize: fontSizes.sm,
        lineHeight: 20,
    },
});
