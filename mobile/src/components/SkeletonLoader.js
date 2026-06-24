import React, { useEffect, useRef } from 'react';
import { View, StyleSheet, Animated } from 'react-native';
import { useTheme } from '../context/ThemeContext';
import { radii } from '../theme';

export default function SkeletonLoader({
    width = '100%',
    height = 20,
    borderRadius = radii.lg,
    style,
    delay = 0
}) {
    const { theme } = useTheme();
    const opacityAnim = useRef(new Animated.Value(0.3)).current;
    const slideAnim = useRef(new Animated.Value(-100)).current;

    useEffect(() => {
        // Staggered entry
        Animated.sequence([
            Animated.delay(delay),
            Animated.parallel([
                Animated.loop(
                    Animated.sequence([
                        Animated.timing(opacityAnim, {
                            toValue: 0.8,
                            duration: 800,
                            useNativeDriver: true,
                        }),
                        Animated.timing(opacityAnim, {
                            toValue: 0.3,
                            duration: 800,
                            useNativeDriver: true,
                        })
                    ])
                ),
                Animated.loop(
                    Animated.timing(slideAnim, {
                        toValue: 400,
                        duration: 1500,
                        useNativeDriver: true,
                    })
                )
            ])
        ]).start();
    }, []);

    return (
        <View
            style={[
                styles.skeletonContainer,
                {
                    width,
                    height,
                    borderRadius,
                    backgroundColor: theme.colors.surfaceAlt,
                },
                style
            ]}
        >
            <Animated.View
                style={[
                    styles.shimmer,
                    {
                        backgroundColor: theme.mode === 'dark' ? 'rgba(255,255,255,0.05)' : 'rgba(255,255,255,0.4)',
                        opacity: opacityAnim,
                        transform: [{ translateX: slideAnim }]
                    }
                ]}
            />
        </View>
    );
}

const styles = StyleSheet.create({
    skeletonContainer: {
        overflow: 'hidden',
        position: 'relative',
    },
    shimmer: {
        position: 'absolute',
        top: 0,
        left: 0,
        bottom: 0,
        width: '50%',
    }
});
