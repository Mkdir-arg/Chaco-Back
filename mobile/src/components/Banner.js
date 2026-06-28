import { View, Text, StyleSheet, Pressable } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import { fontSizes, radii } from '../theme';
import FrostedBackButton from './FrostedBackButton';

export default function Banner({
    title,
    syncStatus = 'synced',
    syncPendingCount = 0,
    onSyncPress,
    showBackButton = false,
    onBackPress,
}) {
    const { theme, typography } = useTheme();
    const isSynced = syncStatus === 'synced';
    const isSyncing = syncStatus === 'syncing';

    return (
        <View style={styles.shadowContainer}>
            <LinearGradient
                colors={theme.colors.gradients?.brand || [theme.colors.primary, theme.colors.secondary]}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.container}
            >
                <SafeAreaView>
                    <View style={styles.headerRow}>
                        <View style={styles.leftHeaderGroup}>
                            {showBackButton ? (
                                <FrostedBackButton
                                    onPress={onBackPress}
                                    size={48}
                                    iconSize={30}
                                    iconColor="#FFFFFF"
                                    tint="dark"
                                    style={styles.backBtn}
                                />
                            ) : null}
                            <Text numberOfLines={1} style={[styles.title, { color: '#FFF', fontFamily: typography.bold }]}>
                                {title}
                            </Text>
                        </View>

                        <Pressable style={styles.iconButton} onPress={onSyncPress} accessibilityRole="button" accessibilityLabel="Sincronizar">
                            <Ionicons
                                name={isSyncing ? 'sync' : (isSynced ? 'cloud-done' : 'cloud-upload')}
                                size={27}
                                color="#FFF"
                            />
                            {syncPendingCount > 0 ? (
                                <View style={[styles.syncBadge, { borderColor: '#FFF', backgroundColor: theme.colors.warning }]}>
                                    <Text style={[styles.syncBadgeText, { fontFamily: typography.bold }]}>
                                        {syncPendingCount > 99 ? '99+' : syncPendingCount}
                                    </Text>
                                </View>
                            ) : null}
                        </Pressable>
                    </View>
                </SafeAreaView>
            </LinearGradient>
        </View>
    );
}

const styles = StyleSheet.create({
    shadowContainer: {
        shadowColor: '#000000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.10,
        shadowRadius: 4,
        elevation: 3,
        zIndex: 10,
    },
    container: {
        borderBottomWidth: StyleSheet.hairlineWidth,
        borderBottomColor: 'rgba(0,0,0,0.12)',
    },
    headerRow: {
        minHeight: 62,
        paddingHorizontal: 14,
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
    },
    leftHeaderGroup: {
        flexDirection: 'row',
        alignItems: 'center',
        flexShrink: 1,
        minWidth: 0,
    },
    backBtn: {
        marginRight: 12,
    },
    title: {
        fontSize: 21,
        lineHeight: 27,
        letterSpacing: 0,
        flexShrink: 1,
    },
    iconButton: {
        width: 48,
        height: 42,
        borderRadius: 21,
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        marginLeft: 12,
        backgroundColor: 'rgba(255,255,255,0.16)',
        borderWidth: 1,
        borderColor: 'rgba(255,255,255,0.34)',
    },
    syncBadge: {
        position: 'absolute',
        top: -2,
        right: -4,
        minWidth: 16,
        height: 16,
        borderRadius: radii.lg,
        justifyContent: 'center',
        alignItems: 'center',
        borderWidth: 1.5,
        paddingHorizontal: 3,
    },
    syncBadgeText: {
        color: '#FFF',
        fontSize: fontSizes.xxs,
        lineHeight: 10,
    },
});
