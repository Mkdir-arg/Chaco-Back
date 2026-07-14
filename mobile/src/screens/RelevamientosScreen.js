import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
    View,
    Text,
    StyleSheet,
    ScrollView,
    Pressable,
    ActivityIndicator,
    RefreshControl,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import StaggeredItem from '../components/StaggeredItem';
import relevamientoService from '../services/relevamientoService';
import { designColors, fontSizes, radii } from '../theme';
import { formatDate as formatAppDate } from '../utils/dates';

const DONE_STATES = ['SINCRONIZADO', 'COMPLETADO_LOCAL', 'REALIZADO', 'FINALIZADO', 'TERMINADO'];
const IN_PROGRESS_STATES = ['EN_PROGRESO', 'EN_CURSO', 'FINALIZANDO'];

const UI = {
    canvas: designColors.bgSecondary,
    surface: designColors.white,
    heading: '#252F40',
    body: designColors.textBody,
    subtle: designColors.textBodySubtle,
    border: designColors.borderBase,
    borderSoft: designColors.bgTertiary,
    brand: designColors.brand,
};

const BADGE = {
    gray: { bg: '#F9FAFB', bd: '#E5E7EB', tx: '#374151' },
    white: { bg: '#FFFFFF', bd: '#E5E7EB', tx: '#374151' },
    brand: { bg: '#FFEAF6', bd: '#FFB9DC', tx: '#A11F60' },
    danger: { bg: '#FEF0F2', bd: '#FFCCD3', tx: '#8B0836' },
    warning: { bg: '#FFF8F1', bd: '#FCD9BD', tx: '#771D1D' },
    success: { bg: '#ECFDF5', bd: '#A4F4CF', tx: '#006045' },
};

const FILTER_OPTIONS = [
    { key: 'TODOS', label: 'Todos' },
    { key: 'ASIGNADOS', label: 'Asignados' },
    { key: 'EN_CURSO', label: 'En curso' },
    { key: 'FINALIZADOS', label: 'Finalizados' },
    { key: 'SIN_SYNC', label: 'Sin sync' },
];

const normalizeEstado = (estado) => String(estado || '').toUpperCase();

const progressLabel = (item) => {
    const estado = normalizeEstado(item.estado);
    if (DONE_STATES.includes(estado)) return 'Finalizado';
    if (IN_PROGRESS_STATES.includes(estado)) return 'En curso';
    if (estado === 'ASIGNADO') return 'Asignado';
    if (estado === 'ERROR') return 'Con error';
    return 'Pendiente';
};

const progressBadge = (item) => {
    const estado = normalizeEstado(item.estado);
    if (DONE_STATES.includes(estado)) return BADGE.success;
    if (IN_PROGRESS_STATES.includes(estado)) return BADGE.warning;
    if (estado === 'ERROR' || estado === 'VENCIDO') return BADGE.danger;
    if (estado === 'ASIGNADO') return BADGE.gray;
    return BADGE.brand;
};

const syncLabel = (syncEstado) => {
    const estado = normalizeEstado(syncEstado);
    if (estado === 'SINCRONIZADO') return 'Sincronizado';
    if (estado === 'SINCRONIZANDO') return 'Sincronizando';
    if (estado === 'ERROR') return 'Error de sync';
    return 'Sin sincronizar';
};

const syncBadge = (syncEstado) => {
    const estado = normalizeEstado(syncEstado);
    if (estado === 'SINCRONIZADO') return BADGE.success;
    if (estado === 'ERROR') return BADGE.danger;
    if (estado === 'SINCRONIZANDO') return BADGE.warning;
    return BADGE.white;
};

const statusIcon = (syncEstado) => {
    const estado = normalizeEstado(syncEstado);
    if (estado === 'SINCRONIZADO') return 'cloud-done-outline';
    if (estado === 'SINCRONIZANDO') return 'sync-outline';
    if (estado === 'ERROR') return 'alert-circle-outline';
    return 'cloud-upload-outline';
};

const titleFor = (item) => {
    if (item.titulo?.trim()) return item.titulo.trim();
    if (item.observaciones?.trim()) return `Relevamiento: ${item.observaciones.trim().slice(0, 42)}`;
    return `Relevamiento Institucion #${item.id_institucion || '-'}`;
};

const valueOrDash = (value) => {
    if (value === 0) return '0';
    if (!value) return '-';
    const text = String(value).trim();
    return text || '-';
};

export default function RelevamientosScreen({ onOpenRelevamiento }) {
    const { typography } = useTheme();
    const [relevamientos, setRelevamientos] = useState([]);
    const [statusFilter, setStatusFilter] = useState('TODOS');
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');

    const formatDate = useCallback((isoDate) => {
        return formatAppDate(isoDate);
    }, []);

    const loadRelevamientos = useCallback(async (silent = false) => {
        if (silent) setRefreshing(true);
        else setLoading(true);
        setError('');

        const result = await relevamientoService.getRelevamientos({ refreshFromRemote: true });
        if (!result.success && result.error) setError(result.error);
        setRelevamientos(result.records || []);

        setLoading(false);
        setRefreshing(false);
    }, []);

    useEffect(() => {
        loadRelevamientos();
    }, [loadRelevamientos]);

    const filteredRelevamientos = useMemo(() => {
        if (statusFilter === 'TODOS') return relevamientos;
        if (statusFilter === 'ASIGNADOS') {
            return relevamientos.filter((item) => normalizeEstado(item.estado) === 'ASIGNADO');
        }
        if (statusFilter === 'EN_CURSO') {
            return relevamientos.filter((item) => IN_PROGRESS_STATES.includes(normalizeEstado(item.estado)));
        }
        if (statusFilter === 'FINALIZADOS') {
            return relevamientos.filter((item) => DONE_STATES.includes(normalizeEstado(item.estado)));
        }
        if (statusFilter === 'SIN_SYNC') {
            return relevamientos.filter((item) => normalizeEstado(item.sync_estado) !== 'SINCRONIZADO');
        }
        return relevamientos;
    }, [relevamientos, statusFilter]);

    const stats = useMemo(() => {
        const total = relevamientos.length;
        const inProgress = relevamientos.filter((item) => IN_PROGRESS_STATES.includes(normalizeEstado(item.estado))).length;
        const done = relevamientos.filter((item) => DONE_STATES.includes(normalizeEstado(item.estado))).length;
        const pendingSync = relevamientos.filter((item) => normalizeEstado(item.sync_estado) !== 'SINCRONIZADO').length;
        return [
            { key: 'total', label: 'Total', value: total, icon: 'folder-open-outline', tone: 'brand' },
            { key: 'progress', label: 'En curso', value: inProgress, icon: 'time-outline', tone: 'warning' },
            { key: 'done', label: 'Finalizados', value: done, icon: 'checkmark-done-outline', tone: 'success' },
            { key: 'sync', label: 'Sin sync', value: pendingSync, icon: 'cloud-upload-outline', tone: 'danger' },
        ];
    }, [relevamientos]);

    return (
        <View style={styles.container}>
            <ScrollView
                contentContainerStyle={styles.content}
                refreshControl={
                    <RefreshControl
                        refreshing={refreshing}
                        onRefresh={() => loadRelevamientos(true)}
                        colors={[UI.brand]}
                        tintColor={UI.brand}
                    />
                }
            >
                <StaggeredItem index={0}>
                    <View style={styles.header}>
                        <View style={styles.breadcrumbRow}>
                            <Text style={[styles.breadcrumbText, { fontFamily: typography.semibold }]}>Programa Becas</Text>
                            <Ionicons name="chevron-forward" size={14} color={UI.subtle} />
                            <Text style={[styles.breadcrumbText, { fontFamily: typography.semibold }]}>Relevamientos</Text>
                        </View>

                        <View style={styles.headerTitleRow}>
                            <View style={styles.headerCopy}>
                                <Text style={[styles.title, { fontFamily: typography.bold }]}>Relevamientos</Text>
                                <Text style={[styles.subtitle, { fontFamily: typography.regular }]}>
                                    Operativos de relevamiento en territorio. Entra a un operativo para ver las personas relevadas dentro.
                                </Text>
                            </View>
                        </View>
                    </View>
                </StaggeredItem>

                <StaggeredItem index={1}>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.statsRow}>
                        {stats.map((stat) => (
                            <StatCard key={stat.key} stat={stat} typography={typography} />
                        ))}
                    </ScrollView>
                </StaggeredItem>

                <StaggeredItem index={2}>
                    <View style={styles.filterBar}>
                        <View style={styles.filterHeader}>
                            <View>
                                <Text style={[styles.filterLabel, { fontFamily: typography.bold }]}>Estado</Text>
                                <Text style={[styles.filterHint, { fontFamily: typography.regular }]}>
                                    {`${filteredRelevamientos.length} de ${relevamientos.length} relevamientos`}
                                </Text>
                            </View>
                            <Pressable
                                accessibilityRole="button"
                                accessibilityLabel="Actualizar relevamientos"
                                onPress={() => loadRelevamientos(true)}
                                style={({ pressed }) => [styles.tertiaryButton, pressed && styles.pressed]}
                            >
                                {refreshing ? (
                                    <ActivityIndicator size="small" color={UI.brand} />
                                ) : (
                                    <Ionicons name="refresh-outline" size={17} color={UI.brand} />
                                )}
                                <Text style={[styles.tertiaryButtonText, { fontFamily: typography.bold }]}>Actualizar</Text>
                            </Pressable>
                        </View>

                        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filtersRow}>
                            {FILTER_OPTIONS.map((option) => {
                                const selected = statusFilter === option.key;
                                return (
                                    <Pressable
                                        key={option.key}
                                        onPress={() => setStatusFilter(option.key)}
                                        style={[
                                            styles.filterChip,
                                            selected ? styles.filterChipSelected : styles.filterChipIdle,
                                        ]}
                                    >
                                        <Text
                                            style={[
                                                styles.filterChipText,
                                                { fontFamily: selected ? typography.bold : typography.semibold },
                                                selected ? styles.filterChipTextSelected : styles.filterChipTextIdle,
                                            ]}
                                        >
                                            {option.label}
                                        </Text>
                                    </Pressable>
                                );
                            })}
                        </ScrollView>
                    </View>
                </StaggeredItem>

                {loading ? (
                    <View style={styles.centerBox}>
                        <ActivityIndicator size="large" color={UI.brand} />
                        <Text style={[styles.infoText, { fontFamily: typography.medium }]}>Cargando relevamientos...</Text>
                    </View>
                ) : null}

                {!loading && !!error ? (
                    <View style={[styles.messageCard, styles.errorCard]}>
                        <Ionicons name="alert-circle-outline" size={18} color={BADGE.danger.tx} />
                        <Text style={[styles.messageText, styles.errorText, { fontFamily: typography.semibold }]}>
                            {`Sin conexion con el servidor. Mostrando datos locales. (${error})`}
                        </Text>
                    </View>
                ) : null}

                {!loading && (
                    <View style={styles.tableCard}>
                        <View style={styles.tableHeader}>
                            <Text style={[styles.tableTitle, { fontFamily: typography.bold }]}>Operativos asignados</Text>
                            <Badge label="Mobile" tone={BADGE.brand} typography={typography} />
                        </View>

                        {filteredRelevamientos.length === 0 ? (
                            <View style={styles.emptyState}>
                                <Ionicons name="file-tray-outline" size={30} color={UI.subtle} />
                                <Text style={[styles.emptyTitle, { fontFamily: typography.bold }]}>Sin relevamientos</Text>
                                <Text style={[styles.emptyText, { fontFamily: typography.regular }]}>
                                    {error
                                        ? 'No hay relevamientos locales para el filtro seleccionado.'
                                        : 'No hay relevamientos para el filtro seleccionado.'}
                                </Text>
                            </View>
                        ) : null}

                        {filteredRelevamientos.map((item, index) => (
                            <StaggeredItem key={item.id} index={index + 3}>
                                <RelevamientoRow
                                    item={item}
                                    index={index}
                                    total={filteredRelevamientos.length}
                                    formatDate={formatDate}
                                    onOpenRelevamiento={onOpenRelevamiento}
                                    typography={typography}
                                />
                            </StaggeredItem>
                        ))}

                        <View style={styles.tableFooter}>
                            <Text style={[styles.footerText, { fontFamily: typography.medium }]}>
                                {`Mostrando ${filteredRelevamientos.length} de ${relevamientos.length}`}
                            </Text>
                            <View style={styles.pagePill}>
                                <Text style={[styles.pagePillText, { fontFamily: typography.bold }]}>1</Text>
                            </View>
                        </View>
                    </View>
                )}
            </ScrollView>
        </View>
    );
}

function StatCard({ stat, typography }) {
    const tone = toneStyles[stat.tone] || toneStyles.brand;
    return (
        <View style={styles.statCard}>
            <View style={[styles.statIcon, { backgroundColor: tone.bg }]}>
                <Ionicons name={stat.icon} size={21} color={tone.fg} />
            </View>
            <Text style={[styles.statLabel, { fontFamily: typography.semibold }]}>{stat.label}</Text>
            <Text
                style={[styles.statValue, { fontFamily: typography.bold }]}
                numberOfLines={1}
                adjustsFontSizeToFit
                minimumFontScale={0.72}
            >
                {stat.value}
            </Text>
        </View>
    );
}

function RelevamientoRow({ item, index, total, formatDate, onOpenRelevamiento, typography }) {
    const isDone = DONE_STATES.includes(normalizeEstado(item.estado));
    const relevados = item.relevados ?? item.relevados_count ?? item.formularios_count ?? item.personas_count ?? 0;

    return (
        <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Abrir ${titleFor(item)}`}
            onPress={() => onOpenRelevamiento && onOpenRelevamiento(item.id)}
            style={({ pressed }) => [styles.rowCard, index === total - 1 && styles.rowCardLast, pressed && styles.rowPressed]}
        >
            <View style={styles.rowTop}>
                <View style={styles.rowTitleGroup}>
                    <Text style={[styles.rowTitle, { fontFamily: typography.bold }]} numberOfLines={2}>
                        {titleFor(item)}
                    </Text>
                    <Text style={[styles.rowSubtitle, { fontFamily: typography.medium }]} numberOfLines={1}>
                        {valueOrDash(item.convocatoria_nombre || item.descripcion || item.observaciones)}
                    </Text>
                </View>
                <Badge label={progressLabel(item)} tone={progressBadge(item)} typography={typography} />
            </View>

            <View style={styles.rowGrid}>
                <MetaCell
                    label="Segmento"
                    value={valueOrDash(item.segmento || item.subsegmento)}
                    icon="layers-outline"
                    typography={typography}
                />
                <MetaCell
                    label="Zona"
                    value={valueOrDash(item.zona || item.localidad || item.direccion_objetivo)}
                    icon="location-outline"
                    typography={typography}
                />
                <MetaCell
                    label="Fecha"
                    value={formatDate(item.fecha_asignada || item.created_at || item.fecha_finalizado)}
                    icon="calendar-outline"
                    typography={typography}
                />
                <MetaCell
                    label="Relevados"
                    value={valueOrDash(relevados)}
                    icon="people-outline"
                    typography={typography}
                />
            </View>

            <View style={styles.rowFooter}>
                <Badge label={syncLabel(item.sync_estado)} tone={syncBadge(item.sync_estado)} icon={statusIcon(item.sync_estado)} typography={typography} />
                <View style={styles.actionsRow}>
                    {isDone ? (
                        <IconButton icon="checkmark-circle-outline" tone={BADGE.success} />
                    ) : (
                        <IconButton icon="time-outline" tone={BADGE.warning} />
                    )}
                    <IconButton icon="eye-outline" tone={BADGE.white} />
                </View>
            </View>
        </Pressable>
    );
}

function MetaCell({ label, value, icon, typography }) {
    return (
        <View style={styles.metaCell}>
            <View style={styles.metaLabelRow}>
                <Ionicons name={icon} size={13} color={UI.subtle} />
                <Text style={[styles.metaLabel, { fontFamily: typography.semibold }]}>{label}</Text>
            </View>
            <Text style={[styles.metaValue, { fontFamily: typography.semibold }]} numberOfLines={1}>
                {value}
            </Text>
        </View>
    );
}

function Badge({ label, tone, icon, typography }) {
    return (
        <View style={[styles.badge, { backgroundColor: tone.bg, borderColor: tone.bd }]}>
            {icon ? <Ionicons name={icon} size={13} color={tone.tx} /> : null}
            <Text style={[styles.badgeText, { color: tone.tx, fontFamily: typography.bold }]} numberOfLines={1}>
                {label}
            </Text>
        </View>
    );
}

function IconButton({ icon, tone }) {
    return (
        <View style={[styles.iconButton, { backgroundColor: tone.bg, borderColor: tone.bd }]}>
            <Ionicons name={icon} size={17} color={tone.tx} />
        </View>
    );
}

const toneStyles = {
    brand: { bg: '#FFEAF6', fg: UI.brand },
    warning: { bg: '#FFF8F1', fg: designColors.warning },
    success: { bg: '#ECFDF5', fg: designColors.success },
    danger: { bg: '#FEF0F2', fg: designColors.danger },
};

const cardShadow = {
    shadowColor: '#252F40',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.08,
    shadowRadius: 24,
    elevation: 2,
};

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: UI.canvas,
    },
    content: {
        padding: 20,
        paddingBottom: 28,
    },
    header: {
        marginBottom: 18,
    },
    breadcrumbRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        marginBottom: 10,
    },
    breadcrumbText: {
        color: UI.subtle,
        fontSize: fontSizes.xs,
    },
    headerTitleRow: {
        gap: 14,
    },
    headerCopy: {
        gap: 6,
    },
    title: {
        color: UI.heading,
        fontSize: 28,
        lineHeight: 34,
    },
    subtitle: {
        color: UI.subtle,
        fontSize: fontSizes.sm,
        lineHeight: 21,
    },
    pressed: {
        opacity: 0.82,
    },
    statsRow: {
        gap: 12,
        paddingBottom: 16,
        paddingRight: 4,
    },
    statCard: {
        ...cardShadow,
        width: 128,
        minHeight: 126,
        borderRadius: radii.xl,
        borderWidth: 1,
        borderColor: UI.border,
        backgroundColor: UI.surface,
        padding: 14,
    },
    statIcon: {
        width: 44,
        height: 44,
        borderRadius: radii.lg,
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 12,
    },
    statLabel: {
        color: UI.subtle,
        fontSize: fontSizes.xs,
        marginBottom: 2,
    },
    statValue: {
        color: UI.heading,
        fontSize: 30,
        lineHeight: 34,
    },
    filterBar: {
        ...cardShadow,
        backgroundColor: UI.surface,
        borderWidth: 1,
        borderColor: UI.border,
        borderRadius: radii.xl,
        padding: 14,
        marginBottom: 16,
        gap: 12,
    },
    filterHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: 12,
    },
    filterLabel: {
        color: UI.heading,
        fontSize: fontSizes.sm,
    },
    filterHint: {
        color: UI.subtle,
        fontSize: fontSizes.xs,
        marginTop: 2,
    },
    tertiaryButton: {
        minHeight: 40,
        borderRadius: radii.full,
        borderWidth: 1,
        borderColor: UI.brand,
        backgroundColor: UI.surface,
        paddingHorizontal: 12,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
    },
    tertiaryButtonText: {
        color: UI.brand,
        fontSize: fontSizes.xs,
    },
    filtersRow: {
        gap: 8,
        paddingRight: 4,
    },
    filterChip: {
        borderWidth: 1,
        borderRadius: radii.full,
        paddingHorizontal: 12,
        paddingVertical: 8,
    },
    filterChipIdle: {
        backgroundColor: UI.surface,
        borderColor: UI.border,
    },
    filterChipSelected: {
        backgroundColor: '#FFEAF6',
        borderColor: '#FFB9DC',
    },
    filterChipText: {
        fontSize: fontSizes.xs,
    },
    filterChipTextIdle: {
        color: UI.body,
    },
    filterChipTextSelected: {
        color: '#A11F60',
    },
    centerBox: {
        alignItems: 'center',
        justifyContent: 'center',
        paddingVertical: 28,
        gap: 10,
    },
    infoText: {
        color: UI.subtle,
        fontSize: fontSizes.sm,
    },
    messageCard: {
        borderRadius: radii.xl,
        borderWidth: 1,
        padding: 14,
        marginBottom: 14,
        flexDirection: 'row',
        alignItems: 'flex-start',
        gap: 8,
    },
    errorCard: {
        backgroundColor: BADGE.danger.bg,
        borderColor: BADGE.danger.bd,
    },
    messageText: {
        flex: 1,
        fontSize: fontSizes.xs,
        lineHeight: 18,
    },
    errorText: {
        color: BADGE.danger.tx,
    },
    tableCard: {
        ...cardShadow,
        backgroundColor: UI.surface,
        borderWidth: 1,
        borderColor: UI.border,
        borderRadius: radii.xl,
        overflow: 'hidden',
    },
    tableHeader: {
        minHeight: 58,
        paddingHorizontal: 16,
        paddingVertical: 14,
        borderBottomWidth: 1,
        borderBottomColor: UI.borderSoft,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
    },
    tableTitle: {
        color: UI.heading,
        fontSize: fontSizes.base,
    },
    emptyState: {
        alignItems: 'center',
        paddingHorizontal: 24,
        paddingVertical: 34,
        gap: 8,
    },
    emptyTitle: {
        color: UI.heading,
        fontSize: fontSizes.base,
    },
    emptyText: {
        color: UI.subtle,
        fontSize: fontSizes.sm,
        lineHeight: 20,
        textAlign: 'center',
    },
    rowCard: {
        padding: 16,
        borderBottomWidth: 1,
        borderBottomColor: UI.borderSoft,
        backgroundColor: UI.surface,
    },
    rowCardLast: {
        borderBottomWidth: 0,
    },
    rowPressed: {
        backgroundColor: '#FAFAFD',
    },
    rowTop: {
        flexDirection: 'row',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: 12,
        marginBottom: 12,
    },
    rowTitleGroup: {
        flex: 1,
        minWidth: 0,
        gap: 4,
    },
    rowTitle: {
        color: UI.heading,
        fontSize: fontSizes.base,
        lineHeight: 21,
    },
    rowSubtitle: {
        color: UI.subtle,
        fontSize: fontSizes.xs,
    },
    rowGrid: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 10,
        marginBottom: 12,
    },
    metaCell: {
        width: '47%',
        minHeight: 58,
        borderRadius: radii.lg,
        borderWidth: 1,
        borderColor: UI.borderSoft,
        backgroundColor: UI.canvas,
        padding: 10,
        gap: 5,
    },
    metaLabelRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
    },
    metaLabel: {
        color: UI.subtle,
        fontSize: fontSizes.xs,
    },
    metaValue: {
        color: UI.heading,
        fontSize: fontSizes.xs,
    },
    rowFooter: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 10,
    },
    badge: {
        maxWidth: 150,
        minHeight: 28,
        borderWidth: 1,
        borderRadius: radii.full,
        paddingHorizontal: 9,
        paddingVertical: 5,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 4,
    },
    badgeText: {
        fontSize: fontSizes.xs,
    },
    actionsRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
    },
    iconButton: {
        width: 34,
        height: 34,
        borderRadius: radii.full,
        borderWidth: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    tableFooter: {
        minHeight: 56,
        paddingHorizontal: 16,
        paddingVertical: 12,
        backgroundColor: UI.canvas,
        borderTopWidth: 1,
        borderTopColor: UI.borderSoft,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 12,
    },
    footerText: {
        color: UI.subtle,
        fontSize: fontSizes.xs,
    },
    pagePill: {
        width: 32,
        height: 32,
        borderRadius: radii.lg,
        backgroundColor: UI.brand,
        alignItems: 'center',
        justifyContent: 'center',
    },
    pagePillText: {
        color: designColors.white,
        fontSize: fontSizes.xs,
    },
});
