// historyscreen.js — every check the user has made, newest first. Tap one to open its report.
import React, { useCallback, useState } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Screen, Icon, STATUS, C, T } from '../ui';
import { getHistory, cachedHistory } from '../config';

const VERDICT_STATUS = { 'Safe': 'ok', 'Use with caution': 'caution', 'Not safe': 'stop' };
const SHORT = { 'Safe': 'Safe', 'Use with caution': 'Take care', 'Not safe': 'Not safe' };

export function HistoryList({ items, navigation }) {
  return (
    <View style={s.list}>
      {items.map((h, i) => {
        const st = STATUS[VERDICT_STATUS[h.verdict]] || STATUS.caution;
        return (
          <Pressable key={h.id} style={({ pressed }) => [s.row, i > 0 && s.line, pressed && { backgroundColor: C.soft }]}
            accessibilityRole="button" onPress={() => navigation.navigate('Report', { savedId: h.id })}>
            <View style={[s.mark, { backgroundColor: st.color }]} />
            <View style={{ flex: 1 }}>
              <Text style={T.h3} numberOfLines={1}>{h.name}</Text>
              <Text style={T.small}>{h.date ? new Date(h.date).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' }) : ''} · {h.for}</Text>
            </View>
            <Text style={[s.verdict, { color: st.color, backgroundColor: st.bg }]}>{SHORT[h.verdict] || h.verdict}</Text>
            <Icon name="chevron-forward" size={18} color={C.faint} />
          </Pressable>
        );
      })}
    </View>
  );
}

export default function HistoryScreen({ navigation }) {
  const [items, setItems] = useState(null);
  const [refreshing, setRefreshing] = useState(true);
  useFocusEffect(useCallback(() => {
    setRefreshing(true);
    cachedHistory().then(c => c && setItems(x => x ?? c));          // the phone's copy shows at once
    getHistory().then(h => { setItems(h); setRefreshing(false); });  // then the account's full list
  }, []));

  return (
    <Screen title="History" bg={C.soft} tabs={{ navigation, current: 'History' }}>
      {items === null || (refreshing && !items.length) ? <ActivityIndicator color={C.brand} style={{ marginTop: 40 }} /> : items.length ? (
        <>
          <Text style={[T.small, { marginBottom: 10 }]}>{items.length} check{items.length > 1 ? 's' : ''}, newest first</Text>
          <HistoryList items={items} navigation={navigation} />
        </>
      ) : (
        <View style={s.empty}>
          <Icon name="time-outline" size={40} color={C.faint} />
          <Text style={[T.h3, { textAlign: 'center' }]}>No checks yet</Text>
          <Text style={[T.sub, { textAlign: 'center' }]}>Scan or search a supplement, and its report will be saved here.</Text>
        </View>
      )}
    </Screen>
  );
}

const s = StyleSheet.create({
  list:    { backgroundColor: '#fff', borderRadius: 16, borderWidth: 1, borderColor: C.line, overflow: 'hidden' },
  row:     { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14, paddingHorizontal: 14 },
  line:    { borderTopWidth: 1, borderTopColor: C.line },
  mark:    { width: 4, alignSelf: 'stretch', borderRadius: 2 },
  verdict: { fontSize: 12, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 6, overflow: 'hidden' },
  empty:   { alignItems: 'center', gap: 10, paddingTop: 80, paddingHorizontal: 30 },
});
