import React, { useState } from 'react';
import {
    View,
    Text,
    TextInput,
    Pressable,
    StyleSheet,
    ScrollView,
    KeyboardAvoidingView,
    Platform,
    Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useTheme } from '../context/ThemeContext';
import { supabase } from '../context/AuthContext';
import CustomButton from '../components/CustomButton';
import FrostedBackButton from '../components/FrostedBackButton';
import { fontSizes, radii } from '../theme';

export default function RegisterScreen({ onBackToLogin }) {
    const { theme, typography, isDark, branding } = useTheme();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [nombre, setNombre] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [error, setError] = useState('');
    const [isRegistering, setIsRegistering] = useState(false);

    const handleRegister = async () => {
        setError('');

        const trimmedUsername = username.trim();
        const trimmedPassword = password.trim();
        const trimmedNombre = nombre.trim();
        const trimmedConfirmPassword = confirmPassword.trim();

        if (!trimmedUsername || !trimmedPassword || !trimmedNombre || !trimmedConfirmPassword) {
            setError('Por favor, completá todos los campos.');
            return;
        }

        if (trimmedUsername.length < 3) {
            setError('El usuario debe tener al menos 3 caracteres.');
            return;
        }

        if (trimmedPassword.length < 6) {
            setError('La contraseña debe tener al menos 6 caracteres.');
            return;
        }

        if (trimmedPassword !== trimmedConfirmPassword) {
            setError('Las contraseñas no coinciden.');
            return;
        }

        setIsRegistering(true);

        try {
            const { data: existingUser } = await supabase
                .from('usuarios')
                .select('id')
                .eq('username', trimmedUsername)
                .single();

            if (existingUser) {
                setError('Este usuario ya está registrado.');
                setIsRegistering(false);
                return;
            }

            const { error: insertError } = await supabase
                .from('usuarios')
                .insert([
                    {
                        username: trimmedUsername,
                        password: trimmedPassword,
                        nombre: trimmedNombre,
                        es_admin: false,
                        foto: null,
                        activo: true,
                    },
                ])
                .select()
                .single();

            if (insertError) {
                setError(`Error al crear el usuario: ${insertError.message}`);
                return;
            }

            Alert.alert('Registro exitoso', 'Tu cuenta fue creada. Ahora iniciá sesión.', [
                {
                    text: 'OK',
                    onPress: () => {
                        setUsername('');
                        setPassword('');
                        setConfirmPassword('');
                        setNombre('');
                        onBackToLogin();
                    },
                },
            ]);
        } catch (err) {
            setError(`Error al registrar: ${err.message}`);
        } finally {
            setIsRegistering(false);
        }
    };

    const inputBaseStyle = {
        borderColor: theme.colors.border,
        backgroundColor: isDark ? theme.colors.surface : theme.colors.surfaceAlt,
    };

    const errorBorderStyle = { borderColor: theme.colors.danger };

    return (
        <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
            style={[styles.container, { backgroundColor: theme.colors.background }]}
        >
            <ScrollView
                contentContainerStyle={styles.scrollContent}
                bounces={false}
                keyboardShouldPersistTaps="always"
                keyboardDismissMode="on-drag"
            >
                    <View style={styles.header}>
                        <FrostedBackButton
                            onPress={onBackToLogin}
                            iconColor={theme.colors.icon}
                            tint={isDark ? 'dark' : 'light'}
                            style={styles.backButton}
                        />
                        <Text style={[styles.title, { fontFamily: typography.bold, color: theme.colors.text }]}>
                            Crear cuenta
                        </Text>
                        <Text style={[styles.subtitle, { fontFamily: typography.regular, color: theme.colors.textMuted }]}>
                            {branding.registerSubtitle}
                        </Text>
                    </View>

                    <View style={[styles.form, { backgroundColor: theme.colors.surface, borderColor: theme.colors.border }]}>
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
                                <Text style={[styles.errorText, { color: theme.colors.danger, fontFamily: typography.medium }]}>
                                    {error}
                                </Text>
                            </View>
                        )}

                        <View style={styles.inputGroup}>
                            <Text style={[styles.label, { fontFamily: typography.semibold, color: theme.colors.text }]}>
                                Nombre completo
                            </Text>
                            <View
                                style={[
                                    styles.input,
                                    inputBaseStyle,
                                    !!error && nombre === '' && errorBorderStyle,
                                ]}
                            >
                                <TextInput
                                    placeholder="Tu nombre"
                                    placeholderTextColor={theme.colors.textSoft}
                                    style={[styles.field, { fontFamily: typography.regular, color: theme.colors.text }]}
                                    value={nombre}
                                    onChangeText={(text) => {
                                        setNombre(text);
                                        setError('');
                                    }}
                                />
                            </View>
                        </View>

                        <View style={styles.inputGroup}>
                            <Text style={[styles.label, { fontFamily: typography.semibold, color: theme.colors.text }]}>
                                Usuario
                            </Text>
                            <View
                                style={[
                                    styles.input,
                                    inputBaseStyle,
                                    !!error && username === '' && errorBorderStyle,
                                ]}
                            >
                                <TextInput
                                    placeholder="tu_usuario"
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
                            <Text style={[styles.label, { fontFamily: typography.semibold, color: theme.colors.text }]}>
                                Contraseña
                            </Text>
                            <View
                                style={[
                                    styles.input,
                                    styles.passwordInputWrapper,
                                    inputBaseStyle,
                                    !!error && password === '' && errorBorderStyle,
                                ]}
                            >
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

                        <View style={styles.inputGroup}>
                            <Text style={[styles.label, { fontFamily: typography.semibold, color: theme.colors.text }]}>
                                Confirmar contraseña
                            </Text>
                            <View
                                style={[
                                    styles.input,
                                    styles.passwordInputWrapper,
                                    inputBaseStyle,
                                    !!error && confirmPassword === '' && errorBorderStyle,
                                ]}
                            >
                                <TextInput
                                    placeholder="********"
                                    placeholderTextColor={theme.colors.textSoft}
                                    secureTextEntry={!showConfirmPassword}
                                    style={[styles.field, { fontFamily: typography.regular, color: theme.colors.text }]}
                                    value={confirmPassword}
                                    onChangeText={(text) => {
                                        setConfirmPassword(text);
                                        setError('');
                                    }}
                                />
                                <Pressable onPress={() => setShowConfirmPassword(!showConfirmPassword)} style={styles.eyeIcon}>
                                    <Ionicons
                                        name={showConfirmPassword ? 'eye-off-outline' : 'eye-outline'}
                                        size={22}
                                        color={theme.colors.textSoft}
                                    />
                                </Pressable>
                            </View>
                        </View>

                        <CustomButton
                            title="Registrarse"
                            onPress={handleRegister}
                            loading={isRegistering}
                            size="L"
                            style={styles.buttonMargin}
                        />

                        <View style={styles.loginLinkContainer}>
                            <Text style={[styles.loginLinkText, { fontFamily: typography.regular, color: theme.colors.textMuted }]}>
                                ¿Ya tenés cuenta?{' '}
                            </Text>
                            <Pressable onPress={onBackToLogin}>
                                <Text style={[styles.loginLink, { fontFamily: typography.semibold, color: theme.colors.primary }]}>
                                    Iniciá sesión
                                </Text>
                            </Pressable>
                        </View>
                    </View>
            </ScrollView>
        </KeyboardAvoidingView>
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
        marginBottom: 24,
        paddingTop: 20,
    },
    backButton: {
        marginBottom: 16,
    },
    title: {
        fontSize: fontSizes['3xl'],
        marginBottom: 8,
    },
    subtitle: {
        fontSize: fontSizes.base,
    },
    form: {
        width: '100%',
        borderWidth: 1,
        borderRadius: radii['2xl'],
        padding: 18,
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
        marginBottom: 18,
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
    buttonMargin: {
        marginTop: 10,
    },
    loginLinkContainer: {
        flexDirection: 'row',
        justifyContent: 'center',
        marginTop: 20,
    },
    loginLinkText: {
        fontSize: fontSizes.sm,
    },
    loginLink: {
        fontSize: fontSizes.sm,
    },
});
