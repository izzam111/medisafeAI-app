// splashscreen.js — brand screen while the app starts, then Home (signed in) or Sign in
import React, { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, StatusBar, Animated, Easing } from 'react-native';
import { onAuthStateChanged } from 'firebase/auth';
import { C } from '../ui';
import { auth } from '../firebase';

export default function SplashScreen({ navigation }) {
  const show = useRef(new Animated.Value(0)).current;
  const ring = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(show, { toValue: 1, duration: 700, easing: Easing.out(Easing.cubic), useNativeDriver: true }).start();
    Animated.loop(Animated.timing(ring, { toValue: 1, duration: 1800, easing: Easing.out(Easing.quad), useNativeDriver: true })).start();
    let user, waited = false, known = false;
    const go = () => waited && known && navigation.replace(user ? 'Home' : 'Auth');
    const stop = onAuthStateChanged(auth, u => { user = u; known = true; go(); });
    const timer = setTimeout(() => { waited = true; go(); }, 1600);
    return () => { clearTimeout(timer); stop(); };
  }, []);

  const scale = show.interpolate({ inputRange: [0, 1], outputRange: [0.85, 1] });
  const ringScale = ring.interpolate({ inputRange: [0, 1], outputRange: [1, 1.9] });
  const ringFade = ring.interpolate({ inputRange: [0, 1], outputRange: [0.35, 0] });

  return (
    <View style={s.root}>
      <StatusBar barStyle="dark-content" backgroundColor="#fff" />
      <View style={[s.blob, { top: -120, right: -90 }]} />
      <View style={[s.blob, { bottom: -140, left: -110, backgroundColor: '#F1F6FF' }]} />

      <Animated.View style={{ alignItems: 'center', opacity: show, transform: [{ scale }] }}>
        <View style={s.logoWrap}>
          <Animated.View style={[s.ring, { opacity: ringFade, transform: [{ scale: ringScale }] }]} />
          <View style={s.mark}>
            <View style={s.crossV} />
            <View style={s.crossH} />
            <View style={s.check} />
          </View>
        </View>
        <Text style={s.name}>MediSafe<Text style={{ color: C.brand }}> AI</Text></Text>
      </Animated.View>

      <View style={s.footer}>
        <View style={s.line} />
        <Text style={s.foot}>Checked against NIH daily limits</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  root:     { flex: 1, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
  blob:     { position: 'absolute', width: 320, height: 320, borderRadius: 160, backgroundColor: C.tint },
  logoWrap: { width: 120, height: 120, alignItems: 'center', justifyContent: 'center', marginBottom: 26 },
  ring:     { position: 'absolute', width: 96, height: 96, borderRadius: 30, backgroundColor: C.brand },
  mark:     { width: 96, height: 96, borderRadius: 30, backgroundColor: C.brand, alignItems: 'center', justifyContent: 'center',
              shadowColor: C.brandDark, shadowOpacity: 0.3, shadowRadius: 18, shadowOffset: { width: 0, height: 10 }, elevation: 8 },
  crossV:   { position: 'absolute', width: 20, height: 54, borderRadius: 6, backgroundColor: '#fff' },
  crossH:   { position: 'absolute', width: 54, height: 20, borderRadius: 6, backgroundColor: '#fff' },
  check:    { position: 'absolute', right: 14, bottom: 14, width: 18, height: 18, borderRadius: 9, backgroundColor: '#22C55E',
              borderWidth: 3, borderColor: C.brand },
  name:     { fontSize: 34, fontWeight: '800', color: C.ink, letterSpacing: -0.5 },
  tag:      { fontSize: 17, color: C.sub, marginTop: 8 },
  footer:   { position: 'absolute', bottom: 48, alignItems: 'center', gap: 10 },
  line:     { width: 36, height: 4, borderRadius: 2, backgroundColor: C.line },
  foot:     { fontSize: 13, color: C.faint, letterSpacing: 0.3 },
});
