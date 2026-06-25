import React, { useEffect, useRef } from 'react';
import { StyleSheet, Animated, Dimensions, Easing, View } from 'react-native';
import { useTheme } from '../context/ThemeContext';

const { width } = Dimensions.get('window');

export default function SplashScreen() {
    const { branding, theme } = useTheme();
    const fadeAnim = useRef(new Animated.Value(0)).current;
    const scaleAnim = useRef(new Animated.Value(0.98)).current;
    const exitTranslateX = useRef(new Animated.Value(0)).current;

    useEffect(() => {
        Animated.sequence([
            Animated.parallel([
                Animated.timing(fadeAnim, {
                    toValue: 1,
                    duration: 280,
                    useNativeDriver: true,
                }),
                Animated.timing(scaleAnim, {
                    toValue: 1,
                    duration: 280,
                    easing: Easing.out(Easing.cubic),
                    useNativeDriver: true,
                }),
            ]),
            Animated.delay(520),
            Animated.parallel([
                Animated.timing(exitTranslateX, {
                    toValue: width * 0.42,
                    duration: 560,
                    easing: Easing.inOut(Easing.cubic),
                    useNativeDriver: true,
                }),
                Animated.timing(scaleAnim, {
                    toValue: 0.96,
                    duration: 560,
                    easing: Easing.inOut(Easing.cubic),
                    useNativeDriver: true,
                }),
                Animated.timing(fadeAnim, {
                    toValue: 0,
                    duration: 560,
                    easing: Easing.inOut(Easing.cubic),
                    useNativeDriver: true,
                }),
            ]),
        ]).start();
    }, []);

    return (
        <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
            <Animated.Image
                source={branding.assets.logo}
                resizeMode="contain"
                style={[
                    styles.logo,
                    {
                    opacity: fadeAnim,
                    transform: [{ scale: scaleAnim }, { translateX: exitTranslateX }],
                    },
                ]}
            />
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    logo: {
        width: 260,
        height: 96,
    },
});
