import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
  Image,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useTheme } from '../context/ThemeContext';
import { useAuth } from '../context/AuthContext';
import { Ionicons } from '@expo/vector-icons';
import CustomButton from '../components/CustomButton';
import AuthVisualBackground from '../components/AuthVisualBackground';
import { fontSizes, radii } from '../theme';

export default function LoginScreen() {
  const { theme, typography, isDark, branding } = useTheme();
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleLogin = async () => {
    setError('');

    const trimmedUsername = username.trim();
    const trimmedPassword = password.trim();

    if (!trimmedUsername || !trimmedPassword) {
      setError('Por favor, ingresa todos los datos.');
      return;
    }

    if (trimmedUsername.length < 3) {
      setError('El usuario debe tener al menos 3 caracteres.');
      return;
    }

    setIsLoggingIn(true);
    const result = await login(trimmedUsername, trimmedPassword);
    setIsLoggingIn(false);

    if (!result.success) {
      setError(result.error);
    }
  };

  return (
    <AuthVisualBackground>
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.container}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          bounces={false}
          keyboardShouldPersistTaps="always"
          keyboardDismissMode="on-drag"
        >
            <View style={styles.header}>
              <Image source={branding.assets.logo} style={styles.logo} resizeMode="contain" />
            </View>

            <View
              style={[
                styles.form,
                {
                  borderColor: theme.colors.border,
                  backgroundColor: isDark ? 'rgba(20,20,24,0.92)' : 'rgba(255,255,255,0.92)',
                  shadowColor: theme.colors.auth?.glow || theme.colors.primary,
                },
              ]}
            >
              <View style={styles.cardHeader}>
                <Text style={[styles.title, { fontFamily: typography.bold, color: theme.colors.text }]}>Bienvenido</Text>
                <Text style={[styles.subtitle, { fontFamily: typography.regular, color: theme.colors.textMuted }]}>
                  {branding.loginSubtitle}
                </Text>
              </View>

              {!!error && (
                <View
                  style={[
                    styles.errorContainer,
                    {
                      backgroundColor: theme.colors.dangerSoft,
                      borderColor: theme.colors.danger,
                    },
                  ]}
                >
                  <Text style={[styles.errorText, { color: theme.colors.danger, fontFamily: typography.medium }]}>{error}</Text>
                </View>
              )}

              <View style={styles.inputGroup}>
                <Text style={[styles.label, { fontFamily: typography.semibold, color: theme.colors.text }]}>Usuario</Text>
                <View
                  style={[
                    styles.input,
                    { borderColor: theme.colors.border, backgroundColor: isDark ? theme.colors.surface : theme.colors.surfaceAlt },
                    !!error && username === '' && { borderColor: theme.colors.danger },
                  ]}
                >
                  <Ionicons
                    name="person-outline"
                    size={20}
                    color={theme.colors.textSoft}
                    style={styles.leftIcon}
                  />
                  <TextInput
                    placeholder="Ingrese su usuario"
                    placeholderTextColor={theme.colors.textSoft}
                    style={[styles.field, { fontFamily: typography.regular, color: theme.colors.text }]}
                    autoCapitalize="none"
                    value={username}
                    onChangeText={(text) => {
                      setUsername(text);
                      setError('');
                    }}
                  />
                </View>
              </View>

              <View style={styles.inputGroup}>
                <Text style={[styles.label, { fontFamily: typography.semibold, color: theme.colors.text }]}>Contraseña</Text>
                <View
                  style={[
                    styles.input,
                    styles.passwordInputWrapper,
                    { borderColor: theme.colors.border, backgroundColor: isDark ? theme.colors.surface : theme.colors.surfaceAlt },
                    !!error && password === '' && { borderColor: theme.colors.danger },
                  ]}
                >
                  <Ionicons
                    name="lock-closed-outline"
                    size={20}
                    color={theme.colors.textSoft}
                    style={styles.leftIcon}
                  />
                  <TextInput
                    placeholder="********"
                    placeholderTextColor={theme.colors.textSoft}
                    secureTextEntry={!showPassword}
                    style={[styles.field, { fontFamily: typography.regular, color: theme.colors.text }]}
                    value={password}
                    onChangeText={(text) => {
                      setPassword(text);
                      setError('');
                    }}
                  />
                  <Pressable onPress={() => setShowPassword(!showPassword)} style={styles.eyeIcon}>
                    <Ionicons
                      name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                      size={22}
                      color={theme.colors.textSoft}
                    />
                  </Pressable>
                </View>
              </View>

              <CustomButton
                title="Ingresar"
                onPress={handleLogin}
                loading={isLoggingIn}
                size="L"
                pressAnimation="scale"
                style={styles.buttonMargin}
              />

            </View>

            <View style={styles.footerContainer}>
              <Text style={[styles.footerText, { fontFamily: typography.bold, color: theme.colors.textMuted }]}>
                ICORE 2026
              </Text>
            </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </AuthVisualBackground>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
    padding: 24,
    justifyContent: 'center',
  },
  header: {
    alignItems: 'center',
    marginBottom: 4,
  },
  logo: {
    width: 200,
    height: 200,
    marginBottom: 12,
  },
  title: {
    fontSize: fontSizes['2xl'],
    marginBottom: 8,
    textAlign: 'center',
  },
  subtitle: {
    fontSize: fontSizes.base,
    textAlign: 'center',
    marginBottom: 14,
  },
  form: {
    width: '100%',
    borderWidth: 1,
    borderRadius: radii['2xl'],
    padding: 18,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 10 },
    shadowOpacity: 0.2,
    shadowRadius: 18,
    elevation: 6,
  },
  cardHeader: {
    alignItems: 'center',
    marginBottom: 8,
  },
  errorContainer: {
    padding: 12,
    borderRadius: radii.xl,
    marginBottom: 20,
    borderWidth: 1,
  },
  errorText: {
    fontSize: fontSizes.sm,
    textAlign: 'center',
  },
  inputGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: fontSizes.sm,
    marginBottom: 8,
  },
  input: {
    height: 56,
    borderWidth: 1,
    borderRadius: radii.xl,
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
  },
  passwordInputWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  eyeIcon: {
    padding: 8,
  },
  field: {
    flex: 1,
    fontSize: fontSizes.base,
  },
  leftIcon: {
    marginRight: 10,
  },
  buttonMargin: {
    marginTop: 20,
  },
  footerContainer: {
    alignItems: 'center',
    marginTop: 20,
  },
  footerText: {
    fontSize: fontSizes.sm,
    fontWeight: '700',
  },
});
