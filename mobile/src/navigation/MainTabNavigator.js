import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import HomeScreen from '../screens/HomeScreen';
import { fontSizes } from '../theme';

const Tab = createBottomTabNavigator();

function TabBar({ state, descriptors, navigation, onOpenSettings }) {
    const { theme, typography } = useTheme();

    return (
        <View style={[styles.tabBar, { backgroundColor: theme.colors.surface, borderTopColor: theme.colors.border, shadowColor: theme.colors.shadow }]}>
            {state.routes.map((route, index) => {
                const { options } = descriptors[route.key];
                const isFocused = state.index === index;

                const onPress = () => {
                    const event = navigation.emit({
                        type: 'tabPress',
                        target: route.key,
                        canPreventDefault: true,
                    });

                    if (!isFocused && !event.defaultPrevented) {
                        navigation.navigate(route.name);
                    }
                };

                const iconName = 'home';

                return (
                    <Pressable key={route.key} onPress={onPress} style={styles.tabItem}>
                        <Ionicons
                            name={isFocused ? iconName : iconName + '-outline'}
                            size={24}
                            color={theme.colors.icon}
                        />
                        <Text style={[styles.tabLabel, {
                            color: isFocused ? theme.colors.primary : theme.colors.textSoft,
                            fontFamily: isFocused ? typography.semibold : typography.medium
                        }]}>
                            {route.name}
                        </Text>
                    </Pressable>
                );
            })}

            <Pressable onPress={onOpenSettings} style={styles.tabItem}>
                <Ionicons name="menu" size={28} color={theme.colors.icon} />
                <Text style={[styles.tabLabel, { color: theme.colors.textSoft, fontFamily: typography.medium }]}>
                    Menú
                </Text>
            </Pressable>
        </View>
    );
}

export default function MainTabNavigator({ onOpenSettings }) {
    return (
        <Tab.Navigator
            tabBar={(props) => <TabBar {...props} onOpenSettings={onOpenSettings} />}
            screenOptions={{ headerShown: false }}
        >
            <Tab.Screen name="Inicio" component={HomeScreen} />
        </Tab.Navigator>
    );
}

const styles = StyleSheet.create({
    tabBar: {
        flexDirection: 'row',
        height: 85,
        paddingBottom: 25,
        paddingTop: 10,
        borderTopWidth: 1,
    },
    tabItem: {
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
    },
    tabLabel: {
        fontSize: fontSizes.xs,
        marginTop: 4,
    },
});
