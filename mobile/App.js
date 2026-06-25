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
import RegisterScreen from './src/screens/RegisterScreen';
import HomeScreen from './src/screens/HomeScreen';
import Banner from './src/components/Banner';
import BottomNav from './src/components/BottomNav';
import SettingsPanel from './src/components/SettingsPanel';
import PageTransition from './src/components/PageTransition';
import SkeletonLoader from './src/components/SkeletonLoader';
import CitizenLegajoScreen from './src/screens/CitizenLegajoScreen';
import RelevamientosScreen from './src/screens/RelevamientosScreen';
import RelevamientoDetailScreen from './src/screens/RelevamientoDetailScreen';
import NewRelevamientoScreen from './src/screens/NewRelevamientoScreen';
import citizenLegajoService from './src/services/citizenLegajoService';
import relevamientoService from './src/services/relevamientoService';

let hasBootstrappedOnce = false;

function AppContent() {
  const { theme, isDark } = useTheme();
  const { user, isAuthenticated, loading: authLoading, logout } = useAuth();
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
  const [citizenLegajoOpen, setCitizenLegajoOpen] = useState(false);
  const [newRelevamientoOpen, setNewRelevamientoOpen] = useState(false);
  const [selectedRelevamientoId, setSelectedRelevamientoId] = useState(null);
  const [showRegister, setShowRegister] = useState(false); // Para mostrar pantalla de registro

  const [syncStatus, setSyncStatus] = useState('synced');
  const [syncPendingCount, setSyncPendingCount] = useState(0);
  const saveRelevamientoLockRef = useRef(false);
  const lastConnectivityStateRef = useRef(null);
  const syncInProgressRef = useRef(false);
  const reconnectDebounceRef = useRef(null);

  const runBackgroundSync = async () => {
    if (syncInProgressRef.current) return;
    syncInProgressRef.current = true;
    try {
      await citizenLegajoService.syncPendingOperations();
      await relevamientoService.syncPendingOperations();
    } catch {
      // Sin conectividad o error temporal: se mantiene en cola.
    } finally {
      syncInProgressRef.current = false;
      await refreshSyncStatus();
    }
  };

  const refreshSyncStatus = async () => {
    const pendingCitizen = await citizenLegajoService.getPendingCount();
    const pendingRelevamientos = await relevamientoService.getPendingCount();
    const pending = pendingCitizen + pendingRelevamientos;
    setSyncPendingCount(pending);
    setSyncStatus(pending > 0 ? 'pending' : 'synced');
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
      return;
    }

    runBackgroundSync();
    const timer = setInterval(async () => {
      await runBackgroundSync();
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
            onStartNewRelevamiento={() => setNewRelevamientoOpen(true)}
            onOpenRelevamiento={(id) => setSelectedRelevamientoId(id)}
          />
        );
      default:
        return (
          <HomeScreen
            onOpenRelevamientos={() => handleTabPress('Relevamientos')}
            onSyncPress={handleManualSync}
            syncPendingCount={syncPendingCount}
          />
        );
    }
  };

  const handleSaveNewRelevamiento = async (payload) => {
    if (saveRelevamientoLockRef.current) return;
    saveRelevamientoLockRef.current = true;
    try {
      const result = await relevamientoService.saveRelevamiento({
        ...payload,
        usuario_username: user?.username || null,
      });
      setNewRelevamientoOpen(false);

      const pending = await relevamientoService.getPendingCount();
      const isOffline = !!result?.syncResult?.offline;
      if (isOffline) {
        Alert.alert('Sin conexion', 'Adjuntos pendientes. Se subiran automaticamente cuando vuelva internet.');
      } else if (pending > 0 || result?.syncResult?.failed > 0) {
        Alert.alert('Guardado local', 'Se guardo en el movil y se sincronizara cuando vuelva internet.');
      }

      refreshSyncStatus();
    } catch (error) {
      Alert.alert('Error al guardar', error?.message || 'No se pudo guardar el relevamiento.');
    } finally {
      saveRelevamientoLockRef.current = false;
    }
  };

  const handleManualSync = async () => {
    if (!isAuthenticated) return;
    if (syncInProgressRef.current) return;

    try {
      syncInProgressRef.current = true;
      setSyncStatus('syncing');
      const [citizenResult, relevamientoResult] = await Promise.all([
        citizenLegajoService.syncPendingOperations(),
        relevamientoService.syncPendingOperations(),
      ]);

      await refreshSyncStatus();

      const synced = (citizenResult?.synced || 0) + (relevamientoResult?.synced || 0);
      const failed = (citizenResult?.failed || 0) + (relevamientoResult?.failed || 0);
      const firstRelevamientoError = relevamientoResult?.errors?.[0]?.message;

      if (failed > 0) {
        Alert.alert(
          'Sincronizacion parcial',
          `Sincronizados: ${synced}\nFallidos: ${failed}${firstRelevamientoError ? `\nDetalle: ${firstRelevamientoError}` : ''}`
        );
      } else if (synced > 0) {
        Alert.alert('Sincronizacion completa', `Sincronizados: ${synced}`);
      } else if (relevamientoResult?.offline || citizenResult?.offline) {
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

  return (
    <View style={[styles.container, { backgroundColor: theme.colors.background }]}>
      <StatusBar barStyle={isDark ? "light-content" : "dark-content"} />

      {!isAuthenticated ? (
        showRegister ? (
          <RegisterScreen onBackToLogin={() => setShowRegister(false)} />
        ) : (
          <LoginScreen onNavigateToRegister={() => setShowRegister(true)} />
        )
      ) : (
        <View style={{ flex: 1 }}>
          {citizenLegajoOpen ? (
            <CitizenLegajoScreen
              onClose={() => setCitizenLegajoOpen(false)}
              onSaved={refreshSyncStatus}
            />
          ) : newRelevamientoOpen ? (
            <NewRelevamientoScreen
              onCancel={() => setNewRelevamientoOpen(false)}
              onSave={handleSaveNewRelevamiento}
            />
          ) : selectedRelevamientoId ? (
            <RelevamientoDetailScreen
              relevamientoId={selectedRelevamientoId}
              onClose={() => setSelectedRelevamientoId(null)}
              syncStatus={syncStatus}
              syncPendingCount={syncPendingCount}
              onSyncPress={handleManualSync}
            />
          ) : (
            <>
              <Banner
                title={activeTab}
                syncStatus={syncStatus}
                syncPendingCount={syncPendingCount}
                onSyncPress={handleManualSync}
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
                pendingCount={syncPendingCount}
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
          setCitizenLegajoOpen(false);
          setNewRelevamientoOpen(false);
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
