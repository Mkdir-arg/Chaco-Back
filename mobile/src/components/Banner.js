import { View, Text, StyleSheet, Platform, Pressable, ImageBackground, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import { useTheme } from '../context/ThemeContext';
import { fontSizes, radii } from '../theme';

export default function Banner({
    title,
    syncStatus = 'synced',
    syncPendingCount = 0,
    onSyncPress,
    showBackButton = false,
    onBackPress,
}) {
    const { theme, typography, branding } = useTheme();
    const isSynced = syncStatus === 'synced';
    const isSyncing = syncStatus === 'syncing';
    const useSolidBanner = branding.banner?.mode === 'solid';

    const bannerContent = (
        <SafeAreaView>
            <View style={styles.content}>
                <View style={styles.headerRow}>
                    <View style={styles.leftHeaderGroup}>
                        {showBackButton ? (
                            <TouchableOpacity onPress={onBackPress} style={styles.backBtn}>
                                <Ionicons name="chevron-back" size={22} color="#FFF" />
                            </TouchableOpacity>
                        ) : null}
                        <Text style={[styles.title, { color: '#FFF', fontFamily: typography.extrabold }]}>
                            {title.toUpperCase()}
                        </Text>
                    </View>

                    <View style={styles.iconGroup}>
                        <Pressable style={styles.iconButton} onPress={onSyncPress}>
                            <Ionicons
                                name={isSyncing ? 'sync' : (isSynced ? 'cloud-done' : 'cloud-upload')}
                                size={28}
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

                        <Pressable style={styles.notificationContainer}>
                            <Ionicons name="notifications-outline" size={26} color="#FFF" />
                            <View style={[
                                styles.badge,
                                {
                                    borderColor: '#FFF',
                                    backgroundColor: theme.colors.danger,
                                }
                            ]}>
                                <Text style={[styles.badgeText, { fontFamily: typography.bold }]}>2</Text>
                            </View>
                        </Pressable>
                    </View>
                </View>
            </View>
        </SafeAreaView>
    );

    return (
        <View style={styles.shadowContainer}>
            {useSolidBanner ? (
                <LinearGradient
                    colors={theme.colors.gradients?.brand || [branding.banner?.color || theme.colors.primary, theme.colors.secondary]}
                    start={{ x: 0, y: 0 }}
                    end={{ x: 1, y: 1 }}
                    style={[
                        styles.container,
                        {
                            borderBottomWidth: 1,
                            borderBottomColor: theme.colors.borderStrong || theme.colors.border,
                        },
                    ]}
                >
                    {bannerContent}
                </LinearGradient>
            ) : (
                <ImageBackground
                    source={branding.assets.bannerBackground}
                    style={[
                        styles.container,
                        {
                            borderBottomWidth: 1,
                            borderBottomColor: theme.colors.border,
                        },
                    ]}
                    imageStyle={{ opacity: 1 }}
                    resizeMode="cover"
                >
                    {bannerContent}
                </ImageBackground>
            )}
        </View>
    );
}

const styles = StyleSheet.create({
    shadowContainer: {
        shadowColor: '#000000',
        shadowOffset: { width: 0, height: 8 },
        shadowOpacity: 0.14,
        shadowRadius: 12,
        elevation: 8,
        zIndex: 10,
    },
    container: {
        paddingTop: Platform.OS === 'android' ? 28 : 6,
        paddingBottom: 12,
        borderBottomLeftRadius: radii['2xl'],
        borderBottomRightRadius: radii['2xl'],
        overflow: 'hidden',
    },
    content: {
        paddingHorizontal: 24,
    },
    headerRow: {
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
        width: 30,
        height: 30,
        borderRadius: radii.full,
        backgroundColor: 'rgba(255,255,255,0.18)',
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: 10,
    },
    title: {
        fontSize: fontSizes.xl,
        letterSpacing: 0,
        flexShrink: 1,
        textShadowColor: 'rgba(0, 0, 0, 0.1)',
        textShadowOffset: { width: 0, height: 2 },
        textShadowRadius: 4,
    },
    notificationContainer: {
        position: 'relative',
        padding: 4,
    },
    iconGroup: {
        flexDirection: 'row',
        alignItems: 'center',
    },
    iconButton: {
        padding: 4,
        marginRight: 8,
        position: 'relative',
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
    badge: {
        position: 'absolute',
        top: 0,
        right: 0,
        minWidth: 18,
        height: 18,
        borderRadius: radii.full,
        justifyContent: 'center',
        alignItems: 'center',
        borderWidth: 1.5,
    },
    badgeText: {
        color: '#FFF',
        fontSize: fontSizes.xs,
        textAlign: 'center',
    },
});
