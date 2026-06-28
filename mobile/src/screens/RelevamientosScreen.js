import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, ActivityIndicator, RefreshControl } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import StaggeredItem from '../components/StaggeredItem';
import relevamientoService from '../services/relevamientoService';
import { fontSizes, radii } from '../theme';

const DONE_STATES = ['SINCRONIZADO', 'COMPLETADO_LOCAL', 'REALIZADO', 'FINALIZADO', 'TERMINADO'];

const statusColor = (estado, colors) => {
    if (estado === 'SINCRONIZADO') return colors.success;
    if (estado === 'SINCRONIZANDO') return colors.accent;
    if (estado === 'ERROR') return colors.danger;
    return colors.warning || '#D97706';
};

const progressColor = (estado, colors) => {
    if (DONE_STATES.includes(estado)) return colors.success;
    if (estado === 'EN_PROGRESO') return colors.accent;
    if (estado === 'ERROR') return colors.danger;
    return colors.warning || '#D97706';
};

const progressLabel = (item) => {
    if (DONE_STATES.includes(item.estado)) return 'Realizado';
    if (item.estado === 'EN_PROGRESO' || item.estado === 'EN_CURSO' || item.estado === 'FINALIZANDO') return 'En progreso';
    if (item.estado === 'ASIGNADO') return 'Asignado';
    return 'Pendiente';
};

const syncLabel = (syncEstado) => {
    if (syncEstado === 'SINCRONIZADO') return 'Sincronizado';
    if (syncEstado === 'SINCRONIZANDO') return 'Sincronizando';
    if (syncEstado === 'ERROR') return 'Error de sync';
    return 'Sin sincronizar';
};

const statusIcon = (estado) => {
    if (estado === 'SINCRONIZADO') return 'cloud-done';
    if (estado === 'SINCRONIZANDO') return 'sync';
    if (estado === 'ERROR') return 'alert-circle';
    return 'cloud-upload';
};

export default function RelevamientosScreen({ onOpenRelevamiento }) {
    const { theme, typography } = useTheme();
    const [relevamientos, setRelevamientos] = useState([]);
    const [statusFilter, setStatusFilter] = useState('TODOS');
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState('');
    const filterOptions = [
        { key: 'TODOS', label: 'Todos' },
        { key: 'PENDIENTES', label: 'Pendientes' },
        { key: 'REALIZADOS', label: 'Realizados' },
        { key: 'SINCRONIZADOS', label: 'Sincronizados' },
        { key: 'SIN_SYNC', label: 'Sin sync' },
    ];

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
        if (statusFilter === 'SINCRONIZADOS') {
            return relevamientos.filter((item) => DONE_STATES.includes(item.estado) && item.sync_estado === 'SINCRONIZADO');
        }
        if (statusFilter === 'PENDIENTES') {
            return relevamientos.filter((item) => !DONE_STATES.includes(item.estado));
        }
        if (statusFilter === 'REALIZADOS') {
            return relevamientos.filter((item) => DONE_STATES.includes(item.estado));
        }
        if (statusFilter === 'SIN_SYNC') {
            return relevamientos.filter((item) => item.sync_estado !== 'SINCRONIZADO');
        }
        return relevamientos;
    }, [relevamientos, statusFilter]);

    return (
        <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
            <ScrollView
                contentContainerStyle={styles.content}
                refreshControl={
                    <RefreshControl
                        refreshing={refreshing}
                        onRefresh={() => loadRelevamientos(true)}
                        colors={[theme.colors.primary]}
                        tintColor={theme.colors.primary}
                    />
                }
            >
                <StaggeredItem index={0}>
                    <View style={styles.titleRow}>
                        <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                            Lista de relevamientos
                        </Text>
                        <Pressable onPress={() => loadRelevamientos(true)} style={styles.refreshBtn}>
                            {refreshing ? (
                                <ActivityIndicator size="small" color={theme.colors.primary} />
                            ) : (
                                <Ionicons name="refresh" size={18} color={theme.colors.icon} />
                            )}
                        </Pressable>
                    </View>
                </StaggeredItem>
                <StaggeredItem index={1}>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.filtersRow}>
                        {filterOptions.map((option) => {
                            const selected = statusFilter === option.key;
                            return (
                                <Pressable
                                    key={option.key}
                                    onPress={() => setStatusFilter(option.key)}
                                    style={[
                                        styles.filterChip,
                                        { backgroundColor: theme.colors.surface, borderColor: theme.colors.border },
                                        selected && { backgroundColor: theme.colors.primary, borderColor: theme.colors.primary },
                                    ]}
                                >
                                    <Text
                                        style={[
                                            styles.filterChipText,
                                            { color: theme.colors.text, fontFamily: typography.medium },
                                            selected && { color: theme.colors.white, fontFamily: typography.bold },
                                        ]}
                                    >
                                        {option.label}
                                    </Text>
                                </Pressable>
                            );
                        })}
                    </ScrollView>
                </StaggeredItem>

                {loading ? (
                    <View style={styles.centerBox}>
                        <ActivityIndicator size="large" color={theme.colors.primary} />
                        <Text style={[styles.infoText, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                            Cargando relevamientos...
                        </Text>
                    </View>
                ) : null}

                {!loading && !!error ? (
                    <View style={[styles.messageCard, { backgroundColor: theme.colors.dangerSoft, borderColor: theme.colors.danger }]}>
                        <Text style={[styles.infoText, { color: theme.colors.danger, fontFamily: typography.semibold }]}>
                            {`Sin conexion con el servidor. Mostrando datos locales. (${error})`}
                        </Text>
                    </View>
                ) : null}

                {!loading && filteredRelevamientos.length === 0 ? (
                    <View style={[styles.messageCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                        <Text style={[styles.infoText, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                            {error
                                ? 'Sin conexion y no hay relevamientos locales para el filtro seleccionado.'
                                : 'No hay relevamientos para el filtro seleccionado.'}
                        </Text>
                    </View>
                ) : null}

                {!loading && filteredRelevamientos.map((item, index) => (
                    <StaggeredItem key={item.id} index={index + 2}>
                        {(() => {
                            const isDone = DONE_STATES.includes(item.estado);
                            return (
                        <Pressable
                            onPress={() => onOpenRelevamiento && onOpenRelevamiento(item.id)}
                            style={[styles.card, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border, shadowColor: theme.colors.shadow }]}
                        >
                            <Text style={[styles.title, { color: theme.colors.text, fontFamily: typography.semibold }]}>
                                {item.titulo?.trim()
                                    ? item.titulo.trim()
                                    : item.observaciones?.trim()
                                    ? `Relevamiento: ${item.observaciones.trim().slice(0, 42)}`
                                    : `Relevamiento Institucion #${item.id_institucion || '-'}`}
                            </Text>

                            <View style={styles.statusRow}>
                                <View style={[styles.statusPill, { backgroundColor: `${progressColor(item.estado, theme.colors)}18` }]}>
                                    <Text style={[styles.statusText, { color: progressColor(item.estado, theme.colors), fontFamily: typography.bold }]}>
                                        {progressLabel(item)}
                                    </Text>
                                </View>
                                {isDone ? (
                                    <View style={[styles.statusPill, { backgroundColor: `${statusColor(item.sync_estado, theme.colors)}18` }]}>
                                        <Ionicons
                                            name={statusIcon(item.sync_estado)}
                                            size={13}
                                            color={statusColor(item.sync_estado, theme.colors)}
                                        />
                                        <Text style={[styles.statusText, styles.syncStatusText, { color: statusColor(item.sync_estado, theme.colors), fontFamily: typography.bold }]}>
                                            {syncLabel(item.sync_estado)}
                                        </Text>
                                    </View>
                                ) : null}
                            </View>

                            <View style={styles.metaRow}>
                                <Ionicons name="calendar-outline" size={15} color={theme.colors.textSoft} />
                                <Text style={[styles.metaText, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                                    {formatDate(item.created_at)}
                                </Text>
                            </View>

                            <View style={styles.metaRow}>
                                <Ionicons name="location-outline" size={15} color={theme.colors.textSoft} />
                                <Text style={[styles.metaText, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>
                                    {item.direccion_objetivo || (item.latitud && item.longitud ? `${item.latitud}, ${item.longitud}` : 'Sin direccion')}
                                </Text>
                            </View>
                        </Pressable>
                            );
                        })()}
                    </StaggeredItem>
                ))}
            </ScrollView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    content: {
        padding: 20,
    },
    sectionTitle: {
        fontSize: fontSizes.xl,
        marginBottom: 16,
    },
    titleRow: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
    },
    refreshBtn: {
        width: 36,
        height: 36,
        borderRadius: radii.full,
        alignItems: 'center',
        justifyContent: 'center',
        marginBottom: 10,
    },
    filtersRow: {
        paddingBottom: 12,
        paddingRight: 8,
    },
    filterChip: {
        borderWidth: 1,
        borderRadius: radii.full,
        paddingHorizontal: 12,
        paddingVertical: 7,
        marginRight: 8,
    },
    filterChipText: {
        fontSize: fontSizes.xs,
    },
    centerBox: {
        alignItems: 'center',
        justifyContent: 'center',
        paddingVertical: 22,
    },
    messageCard: {
        borderRadius: radii.xl,
        borderWidth: 1,
        padding: 14,
        marginBottom: 10,
    },
    infoText: {
        fontSize: fontSizes.xs,
    },
    card: {
        borderRadius: radii.xl,
        borderWidth: 1,
        padding: 16,
        marginBottom: 12,
        shadowOffset: { width: 0, height: 6 },
        shadowOpacity: 0.04,
        shadowRadius: 12,
        elevation: 1,
    },
    title: {
        fontSize: fontSizes.base,
        marginBottom: 8,
    },
    statusRow: {
        flexDirection: 'row',
        flexWrap: 'wrap',
        gap: 6,
        marginBottom: 8,
    },
    statusPill: {
        flexDirection: 'row',
        alignItems: 'center',
        borderRadius: radii.full,
        paddingHorizontal: 8,
        paddingVertical: 4,
    },
    statusText: {
        fontSize: fontSizes.xs,
    },
    syncStatusText: {
        marginLeft: 4,
    },
    metaRow: {
        flexDirection: 'row',
        alignItems: 'center',
        marginTop: 4,
    },
    metaText: {
        fontSize: fontSizes.xs,
        marginLeft: 6,
    },
});
