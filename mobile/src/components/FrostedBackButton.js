import { Pressable, StyleSheet, View } from 'react-native';
import { BlurView } from 'expo-blur';
import { Ionicons } from '@expo/vector-icons';

export default function FrostedBackButton({
  onPress,
  disabled = false,
  iconColor = '#FFFFFF',
  tint = 'light',
  size = 36,
  iconSize = 22,
  style,
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel="Volver"
      onPress={disabled ? undefined : onPress}
      style={({ pressed }) => [
        styles.button,
        { width: size, height: size, borderRadius: size / 2 },
        disabled && styles.disabled,
        pressed && !disabled && styles.pressed,
        style,
      ]}
    >
      <BlurView intensity={34} tint={tint} style={StyleSheet.absoluteFill} />
      <View pointerEvents="none" style={[styles.veil, { borderRadius: size / 2 }]} />
      <Ionicons name="chevron-back" size={iconSize} color={iconColor} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.38)',
    backgroundColor: 'rgba(255,255,255,0.18)',
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.16,
    shadowRadius: 14,
    elevation: 6,
  },
  veil: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(255,255,255,0.16)',
  },
  pressed: {
    transform: [{ scale: 0.96 }],
    opacity: 0.88,
  },
  disabled: {
    opacity: 0.5,
  },
});
