import React, { useRef, useEffect, useState } from 'react';
import { View, Text, StyleSheet, Animated, Pressable, Dimensions, Switch, Platform, Modal } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import CustomButton from './CustomButton';
import { designColors, fontSizes, radii } from '../theme';

const { width } = Dimensions.get('window');
const PANEL_WIDTH = width * 0.8;

export default function SettingsPanel({ visible, onClose, onLogout }) {
    const { theme, isDark, toggleTheme, typography } = useTheme();
    const { user } = useAuth();
    // Start from -PANEL_WIDTH to slide from the left
    const slideAnim = useRef(new Animated.Value(-PANEL_WIDTH)).current;
    const [shouldRender, setShouldRender] = useState(visible);
    const displayName = user?.username || user?.nombre || 'Usuario';
    const initials = displayName
        .split(' ')
        .filter(Boolean)
        .slice(0, 2)
        .map((part) => part[0]?.toUpperCase())
        .join('') || 'U';
    const roleLabel = user?.grupos?.[0]?.nombre || (user?.es_admin ? 'Administrador' : 'Usuario');

    useEffect(() => {
        if (visible) {
            setShouldRender(true);
            Animated.spring(slideAnim, {
                toValue: 0,
                useNativeDriver: true,
                bounciness: 0,
            }).start();
        } else {
            Animated.timing(slideAnim, {
                toValue: -PANEL_WIDTH,
                duration: 250,
                useNativeDriver: true,
            }).start(() => {
                setShouldRender(false);
            });
        }
    }, [visible]);

    return (
        <Modal
            visible={shouldRender}
            transparent={true}
            animationType="none"
            onRequestClose={onClose}
        >
            <View style={styles.overlay}>
                <Animated.View
                    style={[
                        styles.panel,
                        {
                            backgroundColor: theme.colors.surface,
                            transform: [{ translateX: slideAnim }]
                        }
                    ]}
                >
                    <View style={styles.topActions}>
                        <Pressable onPress={onClose} style={styles.closeButton}>
                            <Ionicons name="close" size={28} color={theme.colors.text} />
                        </Pressable>
                    </View>

                    <View style={styles.header}>
                        <View style={[styles.avatar, { backgroundColor: theme.colors.primary }]}>
                            <Text style={[styles.avatarText, { fontFamily: typography.bold }]}>{initials}</Text>
                        </View>
                        <View style={styles.userInfo}>
                            <Text style={[styles.userName, { color: theme.colors.text, fontFamily: typography.bold }]}>{displayName}</Text>
                            <Text style={[styles.userRole, { color: theme.colors.textSoft, fontFamily: typography.regular }]}>{roleLabel}</Text>
                        </View>
                    </View>

                    <View style={styles.divider} />

                    <View style={styles.menuContent}>
                        <View style={styles.menuItem}>
                            <View style={styles.menuLabel}>
                                <Ionicons name={isDark ? "moon" : "sunny"} size={22} color={theme.colors.icon} />
                                <Text style={[styles.menuText, { color: theme.colors.text, fontFamily: typography.medium }]}>Modo Oscuro</Text>
                            </View>
                            <Switch
                                value={!!isDark}
                                onValueChange={toggleTheme}
                                trackColor={{ false: '#D1D5DB', true: '#4B5563' }}
                                thumbColor={isDark ? theme.colors.secondary : theme.colors.primary}
                                ios_backgroundColor="#D1D5DB"
                            />
                        </View>

                        <Pressable style={styles.menuItem}>
                            <View style={styles.menuLabel}>
                                <Ionicons name="notifications-outline" size={22} color={theme.colors.icon} />
                                <Text style={[styles.menuText, { color: theme.colors.text, fontFamily: typography.medium }]}>Notificaciones</Text>
                            </View>
                        </Pressable>
                    </View>

                    <View style={styles.footer}>
                        <CustomButton
                            title="Cerrar Sesión"
                            onPress={onLogout}
                            iconLeft="log-out-outline"
                            size="L"
                        />
                    </View>
                </Animated.View>
                <Pressable style={styles.dismiss} onPress={onClose} />
            </View>
        </Modal>
    );
}

const styles = StyleSheet.create({
    overlay: {
        flex: 1,
        backgroundColor: 'rgba(0,0,0,0.5)',
        flexDirection: 'row',
    },
    dismiss: {
        flex: 1,
    },
    panel: {
        position: 'absolute',
        left: 0,
        top: 0,
        bottom: 0,
        width: PANEL_WIDTH,
        padding: 24,
        paddingTop: Platform.OS === 'ios' ? 50 : 30,
        shadowColor: designColors.shadow,
        shadowOffset: { width: 2, height: 0 },
        shadowOpacity: 0.1,
        shadowRadius: 10,
        elevation: 5,
        zIndex: 1001,
    },
    topActions: {
        flexDirection: 'row',
        justifyContent: 'flex-end',
        marginBottom: 10,
    },
    closeButton: {
        padding: 8,
    },
    header: {
        flexDirection: 'row',
        alignItems: 'center',
        marginBottom: 30,
    },
    avatar: {
        width: 60,
        height: 60,
        borderRadius: radii.full,
        justifyContent: 'center',
        alignItems: 'center',
    },
    avatarText: {
        color: designColors.white,
        fontSize: fontSizes.xl,
    },
    userInfo: {
        marginLeft: 16,
    },
    userName: {
        fontSize: fontSizes.lg,
    },
    userRole: {
        fontSize: fontSizes.sm,
    },
    divider: {
        height: 1,
        backgroundColor: designColors.borderBase,
        marginBottom: 30,
    },
    menuContent: {
        flex: 1,
    },
    menuItem: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingVertical: 16,
    },
    menuLabel: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    menuText: {
        fontSize: fontSizes.base,
        marginLeft: 12,
    },
    footer: {
        paddingBottom: 20,
    },
});
