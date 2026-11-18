// searchscreen.js — find a supplement by name. Typing "a" shows names starting with A, "app" narrows further.
import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, TextInput, Pressable, ScrollView, ActivityIndicator, StyleSheet } from 'react-native';
import { Screen, Notice, Icon, C, T } from '../ui';
import { api, errorMessage } from '../config';

// Names that start with the text first, then names with a later word that starts with it ("d3" → Calvit D3).
function match(names, text) {
  const q = text.trim().toLowerCase();
  if (!q) return names;
  const first = names.filter(n => n.toLowerCase().startsWith(q));
  const word = names.filter(n => !first.includes(n) && n.toLowerCase().split(/[\s/()+-]+/).some(w => w.startsWith(q)));
  return [...first, ...word];
}

export default function SearchScreen({ navigation }) {
  const [names, setNames] = useState(null);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(null);           // name being opened
  const [error, setError] = useState(null);

  useEffect(() => {
    api.get('/products').then(r => setNames(r.data.products)).catch(e => { setNames([]); setError(errorMessage(e)); });
  }, []);
  const results = useMemo(() => match(names || [], text), [names, text]);

  const open = async name => {
    setBusy(name); setError(null);
    try {
      const res = await api.post('/search-product', { name });
      navigation.navigate('Confirm', { scan: res.data, photo: null });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Screen title="Search" onBack={() => navigation.goBack()} bg={C.soft} scroll={false}>
      <View style={{ flex: 1, paddingHorizontal: 20, paddingTop: 8 }}>
      <View style={s.box}>
        <Icon name="search" size={22} color={C.sub} />
        <TextInput style={s.input} value={text} onChangeText={setText} autoFocus autoCorrect={false}
          placeholder="Type a supplement name" placeholderTextColor={C.faint} returnKeyType="search"
          accessibilityLabel="Supplement name" />
        {text ? (
          <Pressable onPress={() => setText('')} hitSlop={10} accessibilityLabel="Clear">
            <Icon name="close-circle" size={22} color={C.faint} />
          </Pressable>
        ) : null}
      </View>

      {error ? <View style={{ marginBottom: 12 }}><Notice kind="stop">{error}</Notice></View> : null}

      {names === null ? <ActivityIndicator color={C.brand} style={{ marginTop: 30 }} /> : (
        <>
          <Text style={[T.small, { marginBottom: 8, marginLeft: 4 }]}>
            {text.trim() ? `${results.length} found` : `All ${names.length} supplements we can check`}
          </Text>
          <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingBottom: 40 }}>
            {results.length ? (
              <View style={s.card}>
                {results.map((n, i) => (
                  <Pressable key={n} onPress={() => open(n)} disabled={!!busy} accessibilityRole="button"
                    style={({ pressed }) => [s.row, i < results.length - 1 && s.line, pressed && { backgroundColor: C.soft }]}>
                    <Icon name="medical" size={18} color={C.brand} />
                    <Text style={[T.body, { flex: 1 }]}>{n}</Text>
                    {busy === n ? <ActivityIndicator color={C.brand} /> : <Icon name="chevron-forward" size={18} color={C.faint} />}
                  </Pressable>
                ))}
              </View>
            ) : (
              <View style={s.none}>
                <Icon name="search-outline" size={36} color={C.faint} />
                <Text style={[T.h3, { textAlign: 'center' }]}>We don't have "{text.trim()}"</Text>
                <Text style={[T.sub, { textAlign: 'center' }]}>MediSafe checks the vitamins, minerals and herbal supplements in its data. Medicines are not included.</Text>
              </View>
            )}
          </ScrollView>
        </>
      )}
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  box:   { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#fff', borderRadius: 16, paddingHorizontal: 16,
           minHeight: 56, borderWidth: 2, borderColor: C.brand, marginBottom: 14 },
  input: { flex: 1, minWidth: 0, fontSize: 18, color: C.ink, paddingVertical: 12 },
  card:  { backgroundColor: '#fff', borderRadius: 20, paddingHorizontal: 16 },
  row:   { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 15 },
  line:  { borderBottomWidth: 1, borderBottomColor: C.line },
  none:  { alignItems: 'center', gap: 10, paddingTop: 40, paddingHorizontal: 20 },
});
