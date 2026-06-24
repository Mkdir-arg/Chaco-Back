import React, { useRef } from 'react';
import { Pressable, Text, StyleSheet, View, Platform, Animated, ActivityIndicator } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { useTheme } from '../context/ThemeContext';
import { Ionicons } from '@expo/vector-icons';
import { designColors, fontSizes, radii } from '../theme';

const SIZES = {
    XS: { h: 32, px: 12, fontSize: fontSizes.xs, iconSize: fontSizes.sm },
    SM: { h: 36, px: 12, fontSize: fontSizes.sm, iconSize: fontSizes.base },
    Base: { h: 40, px: 16, fontSize: fontSizes.sm, iconSize: fontSizes.lg },
    L: { h: 48, px: 20, fontSize: fontSizes.base, iconSize: fontSizes.xl },
    XL: { h: 52, px: 24, fontSize: fontSizes.base, iconSize: 22 },
};

const CustomButton = ({
    title,
    onPress,
    disabled = false,
    style,
    textStyle,
    iconLeft,
    iconRight,
    size = 'Base',
    variant = 'primary', // primary, secondary, tertiary
    loading = false,
    pressAnimation = 'none' // none | scale
}) => {
    const { theme, typography } = useTheme();
    const config = SIZES[size] || SIZES.Base;
    const pressScale = useRef(new Animated.Value(1)).current;

    const animatePress = (toValue) => {
        if (pressAnimation !== 'scale' || disabled || loading) return;
        Animated.spring(pressScale, {
            toValue,
            useNativeDriver: true,
            speed: 28,
            bounciness: 4,
        }).start();
    };

    const getVariantStyles = (pressed, isDisabled) => {
        if (isDisabled) {
            switch (variant) {
                case 'secondary':
                    return {
                        bg: theme.colors.button?.disabled?.bg || '#F3F4F6',
                        text: theme.colors.button?.disabled?.text || designColors.disabledText,
                        stroke: theme.colors.button?.disabled?.border || designColors.borderBase,
                        strokeWidth: 1
                    };
                case 'tertiary':
                    return {
                        bg: theme.colors.button?.disabled?.bg || '#F3F4F6',
                        text: theme.colors.button?.disabled?.text || designColors.disabledText,
                        stroke: theme.colors.button?.disabled?.border || designColors.borderBase,
                        strokeWidth: 1
                    };
                default: // primary
                    return {
                        bg: theme.colors.button?.disabled?.bg || '#F3F4F6',
                        text: theme.colors.button?.disabled?.text || designColors.disabledText,
                        stroke: theme.colors.button?.disabled?.border || designColors.borderBase,
                        strokeWidth: 1
                    };
            }
        }

        if (pressed) {
            switch (variant) {
                case 'secondary':
                    return {
                        bg: theme.colors.button?.secondary?.hoverBg || designColors.bgTertiary,
                        text: theme.colors.button?.secondary?.text || designColors.textBody,
                        stroke: theme.colors.button?.secondary?.border || designColors.borderBase,
                        strokeWidth: 1,
                        shadow: '#F3F4F6'
                    };
                case 'tertiary':
                    return {
                        bg: theme.colors.button?.tertiary?.hoverBg || designColors.bgBrandSoft,
                        text: theme.colors.button?.tertiary?.hoverText || designColors.brand,
                        stroke: theme.colors.button?.tertiary?.hoverBorder || designColors.brand,
                        strokeWidth: 1,
                        shadow: '#F3F4F6'
                    };
                default: // primary
                    return {
                        isGradient: true,
                        text: theme.colors.white,
                        stroke: theme.colors.primary,
                        strokeWidth: 2,
                        shadow: '#E5E7EB'
                    };
            }
        }

        // Initial State
        switch (variant) {
            case 'secondary':
                return {
                    bg: theme.colors.button?.secondary?.bg || designColors.bgSecondary,
                    text: theme.colors.button?.secondary?.text || designColors.textBody,
                    stroke: theme.colors.button?.secondary?.border || designColors.borderBase,
                    strokeWidth: 1
                };
            case 'tertiary':
                return {
                    bg: theme.colors.button?.tertiary?.bg || designColors.white,
                    text: theme.colors.button?.tertiary?.text || designColors.brand,
                    stroke: theme.colors.button?.tertiary?.border || designColors.brand,
                    strokeWidth: 1
                };
            default: // primary
                return {
                    isGradient: true,
                    text: theme.colors.white,
                    stroke: 'transparent',
                    strokeWidth: 0
                };
        }
    };

    return (
        <Animated.View style={[styles.container, style, { transform: [{ scale: pressScale }] }]}>
            <Pressable
                onPress={onPress}
                onPressIn={() => animatePress(0.94)}
                onPressOut={() => animatePress(1)}
                disabled={disabled || loading}
                accessibilityRole="button"
                accessibilityState={{ disabled: disabled || loading, busy: loading }}
                style={({ pressed }) => {
                    const v = getVariantStyles(pressed, disabled);
                    return [
                        styles.buttonBase,
                        {
                            height: config.h,
                            backgroundColor: v.bg || 'transparent',
                            borderColor: v.stroke,
                            borderWidth: v.strokeWidth,
                        },
                        pressed && !disabled && v.shadow && {
                            ...Platform.select({
                                ios: {
                                    shadowColor: v.shadow,
                                    shadowOffset: { width: 0, height: 1 },
                                    shadowOpacity: 1,
                                    shadowRadius: 2,
                                },
                                android: {
                                    elevation: 4,
                                },
                            })
                        }
                    ];
                }}
            >
                {({ pressed }) => {
                    const v = getVariantStyles(pressed, disabled);
                    const content = (
                        <View style={[styles.contentRow, { paddingHorizontal: config.px }]}>
                            {iconLeft && !loading && (
                                <Ionicons
                                    name={iconLeft}
                                    size={config.iconSize}
                                    color={v.text}
                                    style={styles.iconLeft}
                                />
                            )}
                            {loading ? (
                                <View style={styles.loadingRow}>
                                    <ActivityIndicator size="small" color={v.text} />
                                </View>
                            ) : (
                                <Text style={[
                                    styles.text,
                                    {
                                        fontFamily: typography.medium,
                                        fontSize: config.fontSize,
                                        color: v.text
                                    },
                                    textStyle
                                ]}>
                                    {title}
                                </Text>
                            )}
                            {iconRight && !loading && (
                                <Ionicons
                                    name={iconRight}
                                    size={config.iconSize}
                                    color={v.text}
                                    style={styles.iconRight}
                                />
                            )}
                        </View>
                    );

                    if (v.isGradient && !disabled) {
                        return (
                            <LinearGradient
                                colors={theme.colors.gradients?.buttonPrimary || [designColors.brand, designColors.pink]}
                                start={{ x: 0, y: 0 }}
                                end={{ x: 1, y: 1 }}
                                style={styles.gradient}
                            >
                                {pressed && <View style={[styles.hoverOverlay, { backgroundColor: theme.colors.gradients?.buttonPrimaryPressedOverlay || 'rgba(0, 0, 0, 0.2)' }]} />}
                                {content}
                            </LinearGradient>
                        );
                    }

                    return content;
                }}
            </Pressable>
        </Animated.View>
    );
};

const styles = StyleSheet.create({
    container: {
        borderRadius: radii.full,
        overflow: 'hidden',
    },
    buttonBase: {
        borderRadius: radii.full,
        justifyContent: 'center',
        alignItems: 'center',
        width: '100%',
    },
    gradient: {
        flex: 1,
        width: '100%',
        justifyContent: 'center',
        alignItems: 'center',
    },
    hoverOverlay: {
        ...StyleSheet.absoluteFillObject,
        backgroundColor: 'transparent',
    },
    contentRow: {
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'center',
    },
    loadingRow: {
        flexDirection: 'row',
        alignItems: 'center',
        minWidth: 52,
        justifyContent: 'center',
    },
    text: {
        letterSpacing: 0,
    },
    iconLeft: {
        marginRight: 6,
    },
    iconRight: {
        marginLeft: 6,
    },
});

export default CustomButton;
