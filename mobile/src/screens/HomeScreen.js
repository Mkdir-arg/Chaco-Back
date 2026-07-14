import React, { useCallback, useMemo, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, RefreshControl } from 'react-native';
import { useTheme } from '../context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';
import StaggeredItem from '../components/StaggeredItem';
import { designColors, fontSizes, radii } from '../theme';
import { dateKey } from '../utils/dates';

const UI = {
    canvas: designColors.bgSecondary,
    surface: designColors.white,
    heading: designColors.textHeading,
    body: designColors.textBody,
    subtle: designColors.textBodySubtle,
    border: designColors.borderBase,
    brandSoft: designColors.bgBrandSoft,
    brandBorder: designColors.bgBrandMedium,
    brandText: '#A11F60',
};

export default function HomeScreen({
    onOpenRelevamientos,
    onOpenRelevamiento,
    onRefresh,
    assignedRelevamientos = [],
}) {
    const { typography } = useTheme();
    const [selectedDateKey, setSelectedDateKey] = useState(() => dateKey(new Date()));
    const [refreshing, setRefreshing] = useState(false);
    const todayDateKey = dateKey(new Date());

    const calendarDays = useMemo(() => {
        const today = new Date();
        const base = Array.from({ length: 7 }, (_, index) => {
            const next = new Date(today);
            next.setDate(today.getDate() + index);
            return dateKey(next);
        });
        const assigned = assignedRelevamientos
            .map((item) => assignmentDateKey(item))
            .filter(Boolean);
        return Array.from(new Set([...base, ...assigned])).sort();
    }, [assignedRelevamientos]);

    const selectedRelevamientos = useMemo(
        () => assignedRelevamientos.filter((item) => assignmentDateKey(item) === selectedDateKey),
        [assignedRelevamientos, selectedDateKey]
    );
    const hasSelectedRelevamientos = selectedRelevamientos.length > 0;

    const handleRefresh = useCallback(async () => {
        if (!onRefresh || refreshing) return;
        setRefreshing(true);
        try {
            await onRefresh();
        } finally {
            setRefreshing(false);
        }
    }, [onRefresh, refreshing]);

    return (
        <ScrollView
            style={styles.container}
            contentContainerStyle={styles.content}
            refreshControl={(
                <RefreshControl
                    refreshing={refreshing}
                    onRefresh={handleRefresh}
                    tintColor={designColors.brand}
                    colors={[designColors.brand]}
                />
            )}
        >
            <StaggeredItem index={0}>
                <View style={styles.calendarSection}>
                    <View style={styles.calendarHeader}>
                        <Text style={[styles.tableTitle, { fontFamily: typography.bold }]}>Calendario</Text>
                        <View style={styles.badge}>
                            <Text style={[styles.badgeText, { fontFamily: typography.bold }]}>
                                {`${assignedRelevamientos.length} asignado${assignedRelevamientos.length === 1 ? '' : 's'}`}
                            </Text>
                        </View>
                    </View>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.daysRow}>
                        {calendarDays.map((key) => {
                            const selected = selectedDateKey === key;
                            const isToday = key === todayDateKey;
                            const dayRelevamientos = assignedRelevamientos.filter((item) => assignmentDateKey(item) === key);
                            const count = dayRelevamientos.length;
                            const hasOverdue = key < todayDateKey && dayRelevamientos.some((item) => isOverdueRelevamiento(item, todayDateKey));
                            const label = formatCalendarLabel(key);
                            return (
                                <Pressable
                                    key={key}
                                    onPress={() => setSelectedDateKey(key)}
                                    style={[
                                        styles.dayChip,
                                        selected ? styles.dayChipSelected : styles.dayChipIdle,
                                        isToday && styles.dayChipToday,
                                        hasOverdue && styles.dayChipOverdue,
                                    ]}
                                >
                                    <Text style={[styles.dayName, { fontFamily: typography.bold }, selected && styles.dayTextSelected, isToday && styles.dayTextToday]}>{label.day}</Text>
                                    <Text style={[styles.dayNumber, { fontFamily: typography.bold }, selected && styles.dayTextSelected, isToday && styles.dayTextToday]}>{label.number}</Text>
                                    <Text style={[styles.dayMonth, { fontFamily: typography.semibold }, selected && styles.dayTextSelected, isToday && styles.dayTextToday]}>{label.month}</Text>
                                    {count > 0 ? <View style={[styles.dayDot, isToday && styles.dayDotToday, hasOverdue && styles.dayDotOverdue]} /> : null}
                                </Pressable>
                            );
                        })}
                    </ScrollView>

                    <View style={[styles.assignmentList, !hasSelectedRelevamientos && styles.assignmentListEmpty]}>
                        {!hasSelectedRelevamientos ? (
                            <View style={styles.emptyDay}>
                                <Ionicons name="calendar-clear-outline" size={30} color={UI.subtle} />
                                <Text style={[styles.emptyDayText, { fontFamily: typography.medium }]}>Sin relevamientos asignados para esta fecha.</Text>
                            </View>
                        ) : (
                            selectedRelevamientos.map((item) => (
                                <RelevamientoCard
                                    key={item.id}
                                    item={item}
                                    typography={typography}
                                    overdue={isOverdueRelevamiento(item, todayDateKey)}
                                    onPress={() => (onOpenRelevamiento ? onOpenRelevamiento(item.id) : onOpenRelevamientos())}
                                />
                            ))
                        )}
                    </View>
                </View>
            </StaggeredItem>

        </ScrollView>
    );
}

function RelevamientoCard({ item, typography, overdue, onPress }) {
    return (
        <Pressable
            onPress={onPress}
            style={({ pressed }) => [
                styles.assignmentRow,
                overdue && styles.assignmentRowOverdue,
                pressed && styles.actionPressed,
            ]}
        >
            <View style={[styles.actionIcon, overdue && styles.actionIconOverdue]}>
                <Ionicons name="clipboard-outline" size={22} color={overdue ? designColors.danger : designColors.brand} />
            </View>
            <View style={styles.actionCopy}>
                <Text style={[styles.actionTitle, { fontFamily: typography.bold }]} numberOfLines={1}>
                    {item.titulo || item.nombre || 'Relevamiento'}
                </Text>
                <View style={styles.actionMetaRow}>
                    <Text style={[styles.actionDescription, { fontFamily: typography.regular }]} numberOfLines={1}>
                        {item.zona || item.localidad || item.direccion_objetivo || 'Sin zona'}
                    </Text>
                    <View style={[styles.statusPill, overdue && styles.statusPillOverdue]}>
                        <Text style={[styles.statusPillText, overdue && styles.statusPillTextOverdue, { fontFamily: typography.bold }]}>
                            {overdue ? 'Vencido' : statusLabel(item.estado)}
                        </Text>
                    </View>
                </View>
            </View>
            <Ionicons name="chevron-forward" size={18} color={UI.subtle} />
        </Pressable>
    );
}

function assignmentDateKey(item = {}) {
    return dateKey(item.fecha_asignada || item.created_at || item.relevado_at);
}

function isOpenRelevamiento(item = {}) {
    const status = String(item.estado || '').toUpperCase();
    return status === 'ASIGNADO' || status === 'EN_CURSO' || status === 'FINALIZANDO';
}

function isOverdueRelevamiento(item = {}, todayKey = '') {
    const assignedKey = assignmentDateKey(item);
    return !!assignedKey && assignedKey < todayKey && isOpenRelevamiento(item);
}

function formatCalendarLabel(key) {
    const date = new Date(`${key}T12:00:00`);
    const day = date.toLocaleDateString('es-AR', { weekday: 'short' }).replace('.', '');
    const month = date.toLocaleDateString('es-AR', { month: 'short' }).replace('.', '');
    return {
        day,
        number: String(date.getDate()).padStart(2, '0'),
        month,
    };
}

function statusLabel(status) {
    const value = String(status || '').toUpperCase();
    const labels = {
        ASIGNADO: 'Asignado',
        EN_CURSO: 'En curso',
        FINALIZANDO: 'Finalizando',
        FINALIZADO: 'Finalizado',
        EN_REVISION: 'En revision',
        TERMINADO: 'Terminado',
    };
    return labels[value] || 'Asignado';
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: UI.canvas,
    },
    content: {
        padding: 20,
        paddingBottom: 120,
        gap: 16,
    },
    calendarSection: {
        gap: 12,
    },
    calendarHeader: {
        minHeight: 32,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
    },
    daysRow: {
        gap: 8,
        paddingRight: 4,
    },
    dayChip: {
        width: 62,
        minHeight: 82,
        borderWidth: 1,
        borderRadius: radii.xl,
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
    },
    dayChipIdle: {
        backgroundColor: UI.surface,
        borderColor: UI.border,
    },
    dayChipSelected: {
        backgroundColor: UI.brandSoft,
        borderColor: UI.brandBorder,
    },
    dayChipToday: {
        backgroundColor: designColors.successSoft,
        borderColor: designColors.successMedium,
    },
    dayChipOverdue: {
        backgroundColor: designColors.dangerSoft,
        borderColor: designColors.dangerMedium,
    },
    dayName: {
        color: UI.subtle,
        fontSize: fontSizes.xs,
        textTransform: 'capitalize',
    },
    dayNumber: {
        color: UI.heading,
        fontSize: fontSizes.lg,
        lineHeight: 24,
    },
    dayMonth: {
        color: UI.subtle,
        fontSize: fontSizes.xxs,
        textTransform: 'capitalize',
    },
    dayTextSelected: {
        color: UI.brandText,
    },
    dayTextToday: {
        color: designColors.success,
    },
    dayDot: {
        position: 'absolute',
        bottom: 7,
        width: 5,
        height: 5,
        borderRadius: radii.full,
        backgroundColor: designColors.brand,
    },
    dayDotOverdue: {
        backgroundColor: designColors.danger,
    },
    dayDotToday: {
        backgroundColor: designColors.success,
    },
    assignmentList: {
        gap: 8,
    },
    assignmentListEmpty: {
        minHeight: 360,
        justifyContent: 'center',
    },
    assignmentRow: {
        minHeight: 92,
        paddingHorizontal: 16,
        paddingVertical: 16,
        flexDirection: 'row',
        alignItems: 'center',
        gap: 14,
        borderWidth: 1,
        borderColor: UI.border,
        borderLeftWidth: 4,
        borderLeftColor: designColors.brand,
        borderRadius: radii.xl,
        backgroundColor: UI.surface,
        shadowColor: '#252F40',
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.08,
        shadowRadius: 18,
        elevation: 2,
    },
    assignmentRowOverdue: {
        borderLeftColor: designColors.danger,
        borderColor: designColors.dangerMedium,
        backgroundColor: designColors.dangerSoft,
    },
    emptyDay: {
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: 28,
        gap: 10,
    },
    emptyDayText: {
        color: UI.subtle,
        fontSize: fontSizes.sm,
        lineHeight: 20,
        textAlign: 'center',
    },
    tableTitle: {
        color: UI.heading,
        fontSize: fontSizes.base,
    },
    badge: {
        minHeight: 28,
        borderRadius: radii.full,
        borderWidth: 1,
        borderColor: UI.brandBorder,
        backgroundColor: UI.brandSoft,
        paddingHorizontal: 10,
        justifyContent: 'center',
    },
    badgeText: {
        color: UI.brandText,
        fontSize: fontSizes.xs,
    },
    actionPressed: {
        backgroundColor: '#FAFAFD',
    },
    actionIcon: {
        width: 48,
        height: 48,
        borderRadius: radii.xl,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: UI.brandSoft,
    },
    actionIconOverdue: {
        backgroundColor: designColors.white,
    },
    actionCopy: {
        flex: 1,
        minWidth: 0,
    },
    actionTitle: {
        color: UI.heading,
        fontSize: fontSizes.base,
        marginBottom: 8,
    },
    actionMetaRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
    },
    actionDescription: {
        flex: 1,
        color: UI.subtle,
        fontSize: fontSizes.xs,
        lineHeight: 17,
    },
    statusPill: {
        minHeight: 24,
        borderRadius: radii.full,
        paddingHorizontal: 9,
        justifyContent: 'center',
        backgroundColor: UI.brandSoft,
        borderWidth: 1,
        borderColor: UI.brandBorder,
    },
    statusPillOverdue: {
        backgroundColor: designColors.white,
        borderColor: designColors.dangerMedium,
    },
    statusPillText: {
        color: UI.brandText,
        fontSize: fontSizes.xxs,
        lineHeight: 13,
    },
    statusPillTextOverdue: {
        color: designColors.danger,
    },
});
