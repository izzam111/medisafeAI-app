import React, { useEffect, useRef } from 'react';
import {
  View, Text, StyleSheet, StatusBar,
  Animated, Easing, Platform,
} from 'react-native';

export default function SplashScreen({ navigation }) {
  // Animations
  const ringScale   = useRef(new Animated.Value(0.4)).current;
  const ringOpacity = useRef(new Animated.Value(0)).current;
  const ring2Scale  = useRef(new Animated.Value(0.6)).current;
  const ring2Opacity= useRef(new Animated.Value(0)).current;
  const logoOpacity = useRef(new Animated.Value(0)).current;
  const logoScale   = useRef(new Animated.Value(0.7)).current;
  const textOpacity = useRef(new Animated.Value(0)).current;
  const textY       = useRef(new Animated.Value(14)).current;
  const barWidth    = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Ring pulse out
    Animated.sequence([
      Animated.delay(200),
      Animated.parallel([
        Animated.timing(ringOpacity, { toValue: 0.18, duration: 600, useNativeDriver: true }),
        Animated.timing(ringScale,   { toValue: 1,    duration: 700, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
      ]),
    ]).start();

    Animated.sequence([
      Animated.delay(400),
      Animated.parallel([
        Animated.timing(ring2Opacity, { toValue: 0.10, duration: 600, useNativeDriver: true }),
        Animated.timing(ring2Scale,   { toValue: 1,    duration: 700, easing: Easing.out(Easing.cubic), useNativeDriver: true }),
      ]),
    ]).start();

    // Logo pop in
    Animated.sequence([
      Animated.delay(350),
      Animated.parallel([
        Animated.timing(logoOpacity, { toValue: 1, duration: 500, useNativeDriver: true }),
        Animated.spring(logoScale,   { toValue: 1, friction: 6, tension: 80, useNativeDriver: true }),
      ]),
    ]).start();

    // Text slide up
    Animated.sequence([
      Animated.delay(650),
      Animated.parallel([
        Animated.timing(textOpacity, { toValue: 1, duration: 450, useNativeDriver: true }),
        Animated.timing(textY,       { toValue: 0, duration: 450, easing: Easing.out(Easing.quad), useNativeDriver: true }),
      ]),
    ]).start();

    // Progress bar
    Animated.sequence([
      Animated.delay(700),
      Animated.timing(barWidth, { toValue: 1, duration: 1400, easing: Easing.inOut(Easing.quad), useNativeDriver: false }),
    ]).start();

    const t = setTimeout(() => navigation.replace('Home'), 2800);
    return () => clearTimeout(t);
  }, []);

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" backgroundColor="#0D1B3E" />

      {/* Decorative rings */}
      <Animated.View style={[s.ring, s.ringLarge,  { opacity: ringOpacity,  transform: [{ scale: ringScale }]  }]} />
      <Animated.View style={[s.ring, s.ringMedium, { opacity: ring2Opacity, transform: [{ scale: ring2Scale }] }]} />

      {/* Logo block */}
      <Animated.View style={[s.logoWrap, { opacity: logoOpacity, transform: [{ scale: logoScale }] }]}>
        {/* Shield shape made from views */}
        <View style={s.shieldOuter}>
          <View style={s.shieldInner}>
            <Text style={s.shieldPlus}>+</Text>
          </View>
        </View>
      </Animated.View>

      {/* Text */}
      <Animated.View style={{ opacity: textOpacity, transform: [{ translateY: textY }], alignItems: 'center' }}>
        <Text style={s.appName}>MediSafe <Text style={s.appNameAccent}>AI</Text></Text>
        <Text style={s.tagline}>Smart Supplement Safety</Text>
      </Animated.View>

      {/* Progress bar */}
      <View style={s.barTrack}>
        <Animated.View style={[s.barFill, {
          width: barWidth.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] })
        }]} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#0D1B3E',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 24,
  },

  // Rings
  ring: {
    position: 'absolute',
    borderRadius: 999,
    borderWidth: 1.5,
    borderColor: '#4A7FD4',
  },
  ringLarge:  { width: 320, height: 320 },
  ringMedium: { width: 220, height: 220 },

  // Shield logo
  logoWrap: { marginBottom: 4 },
  shieldOuter: {
    width: 100,
    height: 100,
    backgroundColor: '#1A3A7A',
    borderRadius: 28,
    borderWidth: 2,
    borderColor: '#3B6FD4',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#3B6FD4',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.6,
    shadowRadius: 20,
    elevation: 12,
  },
  shieldInner: {
    width: 60,
    height: 60,
    backgroundColor: '#2A5FC4',
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  shieldPlus: {
    fontSize: 36,
    color: '#FFFFFF',
    fontWeight: '300',
    lineHeight: 40,
  },

  // Text
  appName: {
    fontSize: 36,
    fontWeight: '800',
    color: '#FFFFFF',
    letterSpacing: -0.8,
  },
  appNameAccent: {
    color: '#4A9FFF',
  },
  tagline: {
    fontSize: 14,
    color: '#6B8EC4',
    fontWeight: '500',
    letterSpacing: 0.6,
    marginTop: 4,
  },

  // Progress bar
  barTrack: {
    position: 'absolute',
    bottom: 52,
    width: 140,
    height: 3,
    backgroundColor: '#1A3A7A',
    borderRadius: 2,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    backgroundColor: '#4A9FFF',
    borderRadius: 2,
  },
});
