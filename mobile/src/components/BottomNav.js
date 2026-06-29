import React, { useEffect, useRef, useState } from 'react';
import { Animated, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { BlurView } from 'expo-blur';
import { LinearGradient } from 'expo-linear-gradient';
import { useTheme } from '../context/ThemeContext';
import { fontSizes, radii } from '../theme';

const NAV_ITEMS = [
    { id: 'Inicio', label: 'Inicio', icon: 'home-outline', activeIcon: 'home' },
    { id: 'Relevamientos', label: 'Relevamientos', icon: 'clipboard-outline', activeIcon: 'clipboard' },
];

const MENU_ITEM = { id: 'Menu', label: 'Menu', icon: 'person-circle-outline' };

export default function BottomNav({ activeTab, onTabPress, onOpenSettings, pendingCount = 0 }) {
    const { typography, isDark, theme } = useTheme();
    const [contentWidth, setContentWidth] = useState(0);
    const activeIndex = Math.max(0, NAV_ITEMS.findIndex((item) => item.id === activeTab));
    const activeIndexAnim = useRef(new Animated.Value(activeIndex)).current;
    const bubblePulseAnim = useRef(new Animated.Value(1)).current;

    const isAndroid = Platform.OS === 'android';
    const iconColor = isDark ? theme.colors.secondary : theme.colors.primary;
    const blurTint = Platform.OS === 'ios'
        ? (isDark ? 'systemUltraThinMaterialDark' : 'systemUltraThinMaterialLight')
        : (isDark ? 'dark' : 'light');
    const containerStyle = isDark ? styles.containerDark : styles.containerLight;
    const frostStyle = isDark ? styles.frostDark : styles.frostLight;
    const activeBubbleStyle = isDark ? styles.activeBubbleDark : styles.activeBubbleLight;
    const navCount = NAV_ITEMS.length + 1;
    const itemWidth = contentWidth > 0 ? contentWidth / navCount : 0;

    useEffect(() => {
        Animated.parallel([
            Animated.spring(activeIndexAnim, {
                toValue: activeIndex,
                damping: 20,
                stiffness: 220,
                mass: 0.8,
                useNativeDriver: true,
            }),
            Animated.sequence([
                Animated.timing(bubblePulseAnim, {
                    toValue: 1.04,
                    duration: 120,
                    useNativeDriver: true,
                }),
                Animated.spring(bubblePulseAnim, {
                    toValue: 1,
                    damping: 8,
                    stiffness: 180,
                    mass: 0.7,
                    useNativeDriver: true,
                }),
            ]),
        ]).start();
    }, [activeIndex, activeIndexAnim, bubblePulseAnim]);

    const bubbleScaleX = bubblePulseAnim;
    const bubbleTranslateX = activeIndexAnim.interpolate({
        inputRange: NAV_ITEMS.map((_, index) => index),
        outputRange: NAV_ITEMS.map((_, index) => (itemWidth * index) + 5),
        extrapolate: 'clamp',
    });

    return (
        <View pointerEvents="box-none" style={styles.wrap}>
            <View style={[styles.container, containerStyle, isAndroid && (isDark ? styles.containerAndroidDark : styles.containerAndroidLight)]}>
                <BlurView
                    intensity={isAndroid ? 38 : 64}
                    tint={blurTint}
                    experimentalBlurMethod={isAndroid ? 'none' : undefined}
                    blurReductionFactor={isAndroid ? 4 : 2}
                    style={StyleSheet.absoluteFill}
                />
                <View pointerEvents="none" style={[styles.frost, frostStyle]} />
                {isAndroid && (
                    <>
                        <LinearGradient
                            pointerEvents="none"
                            colors={isDark
                                ? ['rgba(255,255,255,0.17)', 'rgba(255,255,255,0.05)', 'rgba(255,255,255,0.10)']
                                : ['rgba(255,255,255,0.72)', 'rgba(255,255,255,0.32)', 'rgba(255,255,255,0.58)']}
                            locations={[0, 0.5, 1]}
                            start={{ x: 0.08, y: 0 }}
                            end={{ x: 0.92, y: 1 }}
                            style={StyleSheet.absoluteFill}
                        />
                        <View pointerEvents="none" style={[styles.androidFrostVeil, isDark ? styles.androidFrostVeilDark : styles.androidFrostVeilLight]} />
                        <View pointerEvents="none" style={styles.androidTopHighlight} />
                    </>
                )}

                <View
                    style={styles.content}
                    onLayout={(event) => setContentWidth(event.nativeEvent.layout.width)}
                >
                    {itemWidth > 0 && (
                        <Animated.View
                            pointerEvents="none"
                            style={[
                                styles.activeBubble,
                                activeBubbleStyle,
                                {
                                    width: itemWidth - 10,
                                    transform: [
                                        { translateX: bubbleTranslateX },
                                        { scaleX: bubbleScaleX },
                                        { scaleY: bubblePulseAnim },
                                    ],
                                },
                            ]}
                        />
                    )}

                    {NAV_ITEMS.map((item) => {
                        const isActive = activeTab === item.id;
                        const showBadge = item.id === 'Relevamientos' && pendingCount > 0;

                        return (
                            <Pressable
                                key={item.id}
                                onPress={() => onTabPress(item.id)}
                                accessibilityRole="button"
                                accessibilityLabel={item.id}
                                style={({ pressed }) => [
                                    styles.tabItem,
                                    pressed && styles.pressedTab,
                                ]}
                            >
                                <Ionicons
                                    name={isActive ? item.activeIcon : item.icon}
                                    size={isActive ? 24 : 22}
                                    color={iconColor}
                                />
                                {showBadge && (
                                    <View style={styles.badge} />
                                )}
                                <Text
                                    numberOfLines={1}
                                    adjustsFontSizeToFit
                                    minimumFontScale={0.82}
                                    style={[
                                        styles.tabLabel,
                                        {
                                            color: iconColor,
                                            fontFamily: isActive ? typography.bold : typography.medium,
                                        },
                                    ]}
                                >
                                    {item.label}
                                </Text>
                            </Pressable>
                        );
                    })}

                    <Pressable
                        onPress={onOpenSettings}
                        accessibilityRole="button"
                        accessibilityLabel={MENU_ITEM.label}
                        style={({ pressed }) => [
                            styles.tabItem,
                            pressed && styles.pressedTab,
                        ]}
                    >
                        <Ionicons name={MENU_ITEM.icon} size={23} color={iconColor} />
                        <Text
                            numberOfLines={1}
                            style={[styles.tabLabel, { color: iconColor, fontFamily: typography.medium }]}
                        >
                            {MENU_ITEM.label}
                        </Text>
                    </Pressable>
                </View>
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    wrap: {
        position: 'absolute',
        left: 24,
        right: 24,
        bottom: Platform.OS === 'ios' ? 18 : 14,
        height: 68,
        zIndex: 20,
    },
    container: {
        flex: 1,
        overflow: 'hidden',
        borderWidth: 1,
        borderRadius: 34,
        shadowColor: '#000000',
        shadowOffset: { width: 0, height: 5 },
        shadowOpacity: Platform.OS === 'android' ? 0.06 : 0.10,
        shadowRadius: Platform.OS === 'android' ? 6 : 11,
        elevation: Platform.OS === 'android' ? 3 : 8,
    },
    containerDark: {
        borderColor: 'rgba(255,255,255,0.10)',
        backgroundColor: 'rgba(255,255,255,0.01)',
    },
    containerLight: {
        borderColor: 'rgba(17,24,39,0.08)',
        backgroundColor: 'rgba(255,255,255,0.03)',
    },
    containerAndroidDark: {
        borderColor: 'rgba(255,255,255,0.13)',
        backgroundColor: 'rgba(16,18,24,0.32)',
    },
    containerAndroidLight: {
        borderColor: 'rgba(255,255,255,0.52)',
        backgroundColor: 'rgba(255,255,255,0.24)',
    },
    frost: {
        ...StyleSheet.absoluteFillObject,
    },
    frostDark: {
        backgroundColor: 'rgba(255,255,255,0.02)',
    },
    frostLight: {
        backgroundColor: 'rgba(255,255,255,0.08)',
    },
    androidFrostVeil: {
        ...StyleSheet.absoluteFillObject,
    },
    androidFrostVeilDark: {
        backgroundColor: 'rgba(8,10,16,0.12)',
    },
    androidFrostVeilLight: {
        backgroundColor: 'rgba(255,255,255,0.18)',
    },
    androidTopHighlight: {
        position: 'absolute',
        top: 1,
        left: 18,
        right: 18,
        height: 1,
        backgroundColor: 'rgba(255,255,255,0.48)',
        borderRadius: radii.full,
    },
    content: {
        flex: 1,
        flexDirection: 'row',
        alignItems: 'center',
        paddingHorizontal: 7,
        paddingVertical: 6,
    },
    activeBubble: {
        position: 'absolute',
        top: 5,
        bottom: 5,
        left: 0,
        overflow: 'hidden',
        borderRadius: 28,
    },
    activeBubbleDark: {
        backgroundColor: 'rgba(255,255,255,0.16)',
    },
    activeBubbleLight: {
        backgroundColor: 'rgba(255,255,255,0.72)',
    },
    tabItem: {
        position: 'relative',
        flex: 1,
        height: 56,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 28,
        paddingHorizontal: 2,
        zIndex: 1,
    },
    pressedTab: {
        opacity: 0.82,
        transform: [{ scale: 0.98 }],
    },
    badge: {
        position: 'absolute',
        top: 8,
        right: 28,
        width: 11,
        height: 11,
        borderRadius: radii.full,
        borderWidth: 1.5,
        borderColor: 'rgba(255,255,255,0.92)',
        backgroundColor: '#EF4444',
    },
    tabLabel: {
        width: '100%',
        marginTop: 2,
        fontSize: 10.5,
        lineHeight: 13,
        textAlign: 'center',
    },
});
