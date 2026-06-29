import React, { useState, useEffect, useRef } from 'react';
import { View, StyleSheet, StatusBar, Alert, AppState } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { useFonts, Manrope_400Regular, Manrope_500Medium, Manrope_600SemiBold, Manrope_700Bold, Manrope_800ExtraBold } from '@expo-google-fonts/manrope';
import * as ScreenOrientation from 'expo-screen-orientation';
import NetInfo from '@react-native-community/netinfo';

import { ThemeProvider, useTheme } from './src/context/ThemeContext';
import { AuthProvider, useAuth } from './src/context/AuthContext';
import SplashScreen from './src/screens/SplashScreen';
import LoginScreen from './src/screens/LoginScreen';
import HomeScreen from './src/screens/HomeScreen';
import Banner from './src/components/Banner';
import BottomNav from './src/components/BottomNav';
import SettingsPanel from './src/components/SettingsPanel';
import PageTransition from './src/components/PageTransition';
import SkeletonLoader from './src/components/SkeletonLoader';
import RelevamientosScreen from './src/screens/RelevamientosScreen';
import RelevamientoDetailScreen from './src/screens/RelevamientoDetailScreen';
import relevamientoService from './src/services/relevamientoService';

let hasBootstrappedOnce = false;
const NEW_RELEVAMIENTO_STATES = ['ASIGNADO'];

function AppContent() {
  const { theme, isDark } = useTheme();
  const { user, isAuthenticated, loading: authLoading, logout } = useAuth();
  const displayName = user?.username || user?.nombre || 'Usuario';
  const [fontsLoaded] = useFonts({
    Manrope_400Regular,
    Manrope_500Medium,
    Manrope_600SemiBold,
    Manrope_700Bold,
    Manrope_800ExtraBold,
  });

  const [isLoading, setIsLoading] = useState(!hasBootstrappedOnce);
  const [isPageLoading, setIsPageLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('Inicio');
  const [settingsVisible, setSettingsVisible] = useState(false);
  const [selectedRelevamientoId, setSelectedRelevamientoId] = useState(null);

  const [syncStatus, setSyncStatus] = useState('synced');
  const [syncPendingCount, setSyncPendingCount] = useState(0);
  const [newRelevamientosCount, setNewRelevamientosCount] = useState(0);
  const [assignedRelevamientos, setAssignedRelevamientos] = useState([]);
  const lastConnectivityStateRef = useRef(null);
  const syncInProgressRef = useRef(false);
  const reconnectDebounceRef = useRef(null);

  const runBackgroundSync = async () => {
    if (syncInProgressRef.current) return;
    syncInProgressRef.current = true;
    try {
      await relevamientoService.syncPendingOperations();
    } catch {
      // Sin conectividad o error temporal: se mantiene en cola.
    } finally {
      syncInProgressRef.current = false;
      await refreshSyncStatus();
    }
  };

  const refreshSyncStatus = async () => {
    const pendingRelevamientos = await relevamientoService.getPendingCount();
    setSyncPendingCount(pendingRelevamientos);
    setSyncStatus(pendingRelevamientos > 0 ? 'pending' : 'synced');
  };

  const refreshNewRelevamientosCount = async () => {
    try {
      const result = await relevamientoService.getRelevamientos({ refreshFromRemote: true });
      setAssignedRelevamientos(result.records || []);
      const nextCount = (result.records || []).filter((item) =>
        NEW_RELEVAMIENTO_STATES.includes(String(item.estado || '').toUpperCase())
      ).length;
      setNewRelevamientosCount(nextCount);
    } catch {
      setAssignedRelevamientos([]);
      setNewRelevamientosCount(0);
    }
  };

  useEffect(() => {
    if (fontsLoaded && !authLoading) {
      if (hasBootstrappedOnce) {
        setIsLoading(false);
        return;
      }
      const timer = setTimeout(() => {
        hasBootstrappedOnce = true;
        setIsLoading(false);
      }, 1450);
      return () => clearTimeout(timer);
    }
  }, [fontsLoaded, authLoading]);

  useEffect(() => {
    const lockPortrait = async () => {
      try {
        await ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.PORTRAIT);
      } catch {
        // En algunos entornos (web/simulator) puede no aplicar; no es bloqueante.
      }
    };

    lockPortrait();
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') lockPortrait();
    });
    return () => {
      sub?.remove?.();
    };
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setSyncStatus('synced');
      setSyncPendingCount(0);
      setNewRelevamientosCount(0);
      return;
    }

    runBackgroundSync();
    refreshNewRelevamientosCount();
    const timer = setInterval(async () => {
      await runBackgroundSync();
      await refreshNewRelevamientosCount();
    }, 8000);
    const unsubscribeNetInfo = NetInfo.addEventListener(async (state) => {
      const isConnected = !!state?.isConnected && state?.isInternetReachable !== false;
      const prev = lastConnectivityStateRef.current;
      lastConnectivityStateRef.current = isConnected;
      if (!prev && isConnected) {
        if (reconnectDebounceRef.current) {
          clearTimeout(reconnectDebounceRef.current);
        }
        reconnectDebounceRef.current = setTimeout(async () => {
          await runBackgroundSync();
          await refreshNewRelevamientosCount();
        }, 1800);
      }
    });

    return () => {
      clearInterval(timer);
      unsubscribeNetInfo?.();
      if (reconnectDebounceRef.current) {
        clearTimeout(reconnectDebounceRef.current);
      }
    };
  }, [isAuthenticated]);

  if (isLoading || !fontsLoaded) {
    return <SplashScreen />;
  }

  const handleTabPress = (tab) => {
    if (tab === activeTab) return;
    setIsPageLoading(true);
    setActiveTab(tab);
    // Simulate content loading for smooth feel
    setTimeout(() => {
      setIsPageLoading(false);
    }, 800);
  };

  const renderScreen = () => {
    if (isPageLoading) {
      return (
        <View style={{ flex: 1, padding: 20 }}>
          {/* Header Skeleton */}
          <SkeletonLoader height={40} width="60%" borderRadius={10} style={{ marginBottom: 30 }} delay={0} />

          {/* Content Block 1 */}
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 20 }}>
            <SkeletonLoader height={120} width="48%" borderRadius={20} delay={100} />
            <SkeletonLoader height={120} width="48%" borderRadius={20} delay={150} />
          </View>

          {/* Content Block 2 */}
          <SkeletonLoader height={180} borderRadius={25} style={{ marginBottom: 20 }} delay={200} />

          {/* Content Block 3 (Staggered list) */}
          <SkeletonLoader height={60} borderRadius={15} style={{ marginBottom: 12 }} delay={250} />
          <SkeletonLoader height={60} borderRadius={15} style={{ marginBottom: 12 }} delay={300} />
          <SkeletonLoader height={60} borderRadius={15} delay={350} />
        </View>
      );
    }

    switch (activeTab) {
      case 'Relevamientos':
        return (
          <RelevamientosScreen
            onOpenRelevamiento={(id) => setSelectedRelevamientoId(id)}
          />
        );
      default:
      return (
          <HomeScreen
            onOpenRelevamientos={() => handleTabPress('Relevamientos')}
            onOpenRelevamiento={(id) => setSelectedRelevamientoId(id)}
            onRefresh={handleHomeRefresh}
            assignedRelevamientos={assignedRelevamientos}
          />
        );
    }
  };

  const handleManualSync = async () => {
    if (!isAuthenticated) return;
    if (syncInProgressRef.current) return;

    try {
      syncInProgressRef.current = true;
      setSyncStatus('syncing');
      const relevamientoResult = await relevamientoService.syncPendingOperations();

      await refreshSyncStatus();

      const synced = relevamientoResult?.synced || 0;
      const failed = relevamientoResult?.failed || 0;
      const firstRelevamientoError = relevamientoResult?.errors?.[0]?.message;

      if (failed > 0) {
        Alert.alert(
          'Sincronizacion parcial',
          `Sincronizados: ${synced}\nFallidos: ${failed}${firstRelevamientoError ? `\nDetalle: ${firstRelevamientoError}` : ''}`
        );
      } else if (synced > 0) {
        Alert.alert('Sincronizacion completa', `Sincronizados: ${synced}`);
      } else if (relevamientoResult?.offline) {
        Alert.alert('Sin conexion', 'Adjuntos pendientes. Se reintentara automaticamente al recuperar internet.');
      } else {
        Alert.alert('Sincronizacion', 'No habia elementos pendientes.');
      }
    } catch (error) {
      setSyncStatus('pending');
      Alert.alert('Sincronizacion', error?.message || 'No se pudo sincronizar.');
    } finally {
      syncInProgressRef.current = false;
      await refreshSyncStatus();
    }
  };

  const handleHomeRefresh = async () => {
    if (!isAuthenticated) return;
    await runBackgroundSync();
    await refreshNewRelevamientosCount();
    await refreshSyncStatus();
  };

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar barStyle={isDark ? "light-content" : "dark-content"} />

      {!isAuthenticated ? (
        <LoginScreen />
      ) : (
        <View style={{ flex: 1 }}>
          {selectedRelevamientoId ? (
            <RelevamientoDetailScreen
              relevamientoId={selectedRelevamientoId}
              onClose={() => {
                setSelectedRelevamientoId(null);
                refreshNewRelevamientosCount();
              }}
              syncStatus={syncStatus}
              syncPendingCount={syncPendingCount}
              onSyncPress={handleManualSync}
            />
          ) : (
            <>
              <Banner
                title={activeTab === 'Inicio' ? `Hola, ${displayName}` : activeTab}
                syncStatus={syncStatus}
                syncPendingCount={syncPendingCount}
                onSyncPress={handleManualSync}
                showBackButton={activeTab !== 'Inicio'}
                onBackPress={() => handleTabPress('Inicio')}
                preserveTitleCase={activeTab === 'Inicio'}
              />

              <View style={{ flex: 1 }}>
                <PageTransition activeTab={activeTab}>
                  {renderScreen()}
                </PageTransition>
              </View>

              <BottomNav
                activeTab={activeTab}
                onTabPress={handleTabPress}
                onOpenSettings={() => setSettingsVisible(true)}
                pendingCount={newRelevamientosCount}
              />
            </>
          )}
        </View>
      )}

      {/* Settings Panel is always ready but hidden */}
      <SettingsPanel
        visible={!!settingsVisible}
        onClose={() => setSettingsVisible(false)}
        onLogout={() => {
          setSettingsVisible(false);
          logout();
          setActiveTab('Inicio');
          setSelectedRelevamientoId(null);
        }}
      />
    </View>
  );
}

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <AuthProvider>
          <ThemeProvider>
            <AppContent />
          </ThemeProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
