import React, { useState, useEffect, useRef } from 'react';
import { View, Text, StyleSheet, ScrollView, Pressable, Dimensions } from 'react-native';
import { useTheme } from '../context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import MaskedView from '@react-native-masked-view/masked-view';
import StaggeredItem from '../components/StaggeredItem';
import CustomButton from '../components/CustomButton';
import { fontSizes, radii } from '../theme';

const { width } = Dimensions.get('window');

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

const TASK_LIST = [
    { id: '1', title: 'Encuesta de Vulnerabilidad Territorial', status: 'Pendiente', time: '14:00', type: 'Relevamiento', dateOffset: 0 },
    { id: '2', title: 'Autorización de Subsidio Habitacional', status: 'En Proceso', time: '09:00', type: 'Trámite', dateOffset: 1 },
    { id: '3', title: 'Inspección de Sede Vecinal San Martín', status: 'Completado', time: '11:00', type: 'Legajo Espacios', dateOffset: -1 },
];

export default function TasksScreen({ onOpenSurvey }) {
    const { theme, typography } = useTheme();
    const [selectedDate, setSelectedDate] = useState(new Date());

    const handleOpenTask = (task) => {
        if (task.title === 'Encuesta de Vulnerabilidad Territorial' && onOpenSurvey) {
            onOpenSurvey('vulnerability');
        }
    };
    const [dates, setDates] = useState([]);
    const scrollRef = useRef(null);

    useEffect(() => {
        const dateArray = [];
        const today = new Date();
        for (let i = -15; i < 15; i++) {
            const date = new Date();
            date.setDate(today.getDate() + i);
            dateArray.push(date);
        }
        setDates(dateArray);

        setTimeout(() => {
            if (scrollRef.current) {
                scrollRef.current.scrollTo({ x: 15 * 70 - (width / 2) + 35, animated: true });
            }
        }, 500);
    }, []);

    const formatDate = (date) => {
        const days = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
        const months = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC'];
        return {
            dayName: days[date.getDay()],
            dayNum: date.getDate(),
            monthAbbr: months[date.getMonth()],
            isToday: date.toDateString() === new Date().toDateString(),
            isSelected: date.toDateString() === selectedDate.toDateString()
        };
    };

    const getFilteredTasks = () => {
        const today = new Date();
        const diffTime = selectedDate.getTime() - today.getTime();
        const diffDays = Math.round(diffTime / (1000 * 3600 * 24));
        return TASK_LIST.filter(task => task.dateOffset === diffDays);
    };

    const filteredTasks = getFilteredTasks();

    return (
        <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
            <View style={[styles.calendarContainer, { borderBottomColor: theme.colors.border }]}>
                <ScrollView
                    ref={scrollRef}
                    horizontal
                    showsHorizontalScrollIndicator={false}
                    contentContainerStyle={styles.calendarScroll}
                >
                    {dates.map((date, index) => {
                        const info = formatDate(date);
                        return (
                            <Pressable
                                key={index}
                                onPress={() => setSelectedDate(date)}
                                style={[
                                    styles.dateCard,
                                    { backgroundColor: theme.colors.surface },
                                    info.isSelected && { backgroundColor: theme.colors.primary, transform: [{ scale: 1.05 }] }
                                ]}
                            >
                                <Text style={[
                                    styles.dayName,
                                    { color: theme.colors.textSoft, fontFamily: typography.extrabold },
                                    info.isSelected && { color: '#FFF' }
                                ]}>
                                    {info.dayName}
                                </Text>
                                <Text style={[
                                    styles.dayNum,
                                    { color: theme.colors.text, fontFamily: typography.bold },
                                    info.isSelected && { color: '#FFF' }
                                ]}>
                                    {info.dayNum}
                                </Text>
                                <Text style={[
                                    styles.monthAbbr,
                                    { color: theme.colors.textSoft, fontFamily: typography.medium },
                                    info.isSelected && { color: '#FFF' }
                                ]}>
                                    {info.monthAbbr}
                                </Text>
                                {info.isToday && !info.isSelected && (
                                    <View style={[styles.todayDot, { backgroundColor: theme.colors.primary }]} />
                                )}
                            </Pressable>
                        );
                    })}
                </ScrollView>
            </View>

            <ScrollView contentContainerStyle={styles.content}>
                <StaggeredItem index={0}>
                    <View style={styles.headerRow}>
                        <Text style={[styles.sectionTitle, { color: theme.colors.text, fontFamily: typography.bold }]}>
                            {selectedDate.toDateString() === new Date().toDateString() ? 'Tareas de Hoy' : 'Tareas del Día'}
                        </Text>
                        <View style={[styles.countBadge, { backgroundColor: theme.colors.surface }]}>
                            <Text style={[styles.countText, { color: theme.colors.primary, fontFamily: typography.bold }]}>
                                {filteredTasks.length}
                            </Text>
                        </View>
                    </View>
                </StaggeredItem>

                {filteredTasks.length > 0 ? (
                    filteredTasks.map((task, index) => (
                        <StaggeredItem key={task.id} index={index + 1}>
                            <View style={[styles.taskCard, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
                                <View style={styles.cardHeader}>
                                    <View style={[styles.statusBadge, { backgroundColor: task.status === 'Completado' ? `${theme.colors.success}20` : `${theme.colors.primary}20` }]}>
                                        <Text style={[styles.statusText, { color: task.status === 'Completado' ? theme.colors.success : theme.colors.primary, fontFamily: typography.bold }]}>
                                            {task.status.toUpperCase()}
                                        </Text>
                                    </View>
                                    <Text style={[styles.timeText, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>{task.time}</Text>
                                </View>

                                <Text style={[styles.taskTitle, { color: theme.colors.text, fontFamily: typography.semibold }]}>{task.title}</Text>

                                <View style={styles.cardFooter}>
                                    <Text style={[styles.typeText, { color: theme.colors.textMuted, fontFamily: typography.regular }]}>{task.type}</Text>
                                    <View style={styles.actions}>
                                        <CustomButton
                                            title="ABRIR"
                                            onPress={() => handleOpenTask(task)}
                                            size="SM"
                                            style={{ width: 100 }}
                                        />
                                    </View>
                                </View>
                            </View>
                        </StaggeredItem>
                    ))
                ) : (
                    <StaggeredItem index={1}>
                        <View style={styles.emptyContainer}>
                            <GradientIcon name="calendar-outline" size={60} style={{ opacity: 0.3 }} colors={theme.colors.gradients?.brand || ['#5059BC', '#F98DFF']} />
                            <Text style={[styles.emptyText, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                                No hay tareas programadas para este día
                            </Text>
                        </View>
                    </StaggeredItem>
                )}
            </ScrollView>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
    },
    calendarContainer: {
        height: 110,
        paddingTop: 10,
        borderBottomWidth: 1,
    },
    calendarScroll: {
        paddingHorizontal: 15,
        alignItems: 'center',
    },
    dateCard: {
        width: 60,
        height: 80,
        borderRadius: radii['2xl'],
        justifyContent: 'center',
        alignItems: 'center',
        marginHorizontal: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.05,
        shadowRadius: 5,
        elevation: 2,
    },
    dayName: {
        fontSize: fontSizes.xs,
        marginBottom: 2,
    },
    dayNum: {
        fontSize: fontSizes.lg,
    },
    monthAbbr: {
        fontSize: fontSizes.xxs,
        marginTop: 2,
        letterSpacing: 0.5,
    },
    todayDot: {
        width: 4,
        height: 4,
        borderRadius: radii.sm,
        position: 'absolute',
        bottom: 8,
    },
    content: {
        padding: 20,
    },
    headerRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 16,
    },
    sectionTitle: {
        fontSize: fontSizes.xl,
    },
    countBadge: {
        paddingHorizontal: 12,
        paddingVertical: 4,
        borderRadius: radii.xl,
    },
    countText: {
        fontSize: fontSizes.sm,
    },
    taskCard: {
        padding: 20,
        borderRadius: radii['3xl'],
        borderWidth: 1,
        marginBottom: 16,
    },
    cardHeader: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: 12,
    },
    statusBadge: {
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: radii.lg,
    },
    statusText: {
        fontSize: fontSizes.xs,
        letterSpacing: 0.5,
    },
    timeText: {
        fontSize: fontSizes.xs,
    },
    taskTitle: {
        fontSize: fontSizes.base,
        marginBottom: 12,
        lineHeight: 22,
    },
    cardFooter: {
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginTop: 4,
    },
    typeText: {
        fontSize: fontSizes.sm,
    },
    buttonContainer: {
        borderRadius: radii.xl,
        overflow: 'hidden',
    },
    gradientButton: {
        paddingHorizontal: 20,
        paddingVertical: 8,
        justifyContent: 'center',
        alignItems: 'center',
    },
    actionBtnText: {
        color: '#FFF',
        fontSize: fontSizes.xs,
    },
    emptyContainer: {
        alignItems: 'center',
        marginTop: 60,
    },
    emptyText: {
        marginTop: 16,
        fontSize: fontSizes.base,
        textAlign: 'center',
        paddingHorizontal: 40,
        lineHeight: 24,
    }
});

