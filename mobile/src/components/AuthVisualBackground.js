import React from 'react';
import { StyleSheet, View } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { designColors } from '../theme';

export default function AuthVisualBackground({ children }) {
  return (
    <View style={styles.container}>
      <LinearGradient
        pointerEvents="none"
        colors={[designColors.bgSecondary, designColors.white]}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
        style={StyleSheet.absoluteFill}
      />

      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    overflow: 'hidden',
  },
});
