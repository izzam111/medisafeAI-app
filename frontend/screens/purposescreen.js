// purposescreen.js — "Why do you take it?"
// Tap the box and the list drops down right under it. Tick as many reasons as you like (up to 5), tap again to untick.
// "Other" opens a text box where you write your own reason. Only reasons this product is really used for are listed.
import React, { useEffect, useState } from 'react';
import { View, Text, TextInput, Pressable, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { Screen, Button, Icon, C, T } from '../ui';
import { api } from '../config';

const MAX = 5;            // the server accepts at most 5 reasons

export default function ReasonsScreen({ route, navigation }) {
  const { scan, photo, profile, name } = route.params;
  const [options, setOptions] = useState(null);
  const [picked, setPicked]   = useState([]);          // reasons ticked in the list
  const [other, setOther]     = useState(false);       // "Other" ticked
  const [own, setOwn]         = useState('');          // what the user wrote for "Other"
  const [open, setOpen]       = useState(false);

  useEffect(() => {
    api.post('/suggest-reasons', { scan_id: scan.scan_id, name, age: profile.age, sex: profile.sex, periods: profile.periods },
             { timeout: 30000 })
      .then(res => setOptions(res.data.reasons))
      .catch(() => setOptions([]));
  }, []);

  const reasons = [...picked, ...(other && own.trim() ? [own.trim()] : [])];
  const count = picked.length + (other ? 1 : 0);
  const full = count >= MAX;
  const go = list => navigation.navigate('Report', { scan, photo, profile, name, reasons: list });

  const toggle = r => setPicked(p => p.includes(r) ? p.filter(x => x !== r) : full ? p : [...p, r]);
  const toggleOther = () => {
    if (other) { setOther(false); setOwn(''); }
    else if (!full) setOther(true);                       // the text box opens right under "Other"
  };

  const summary = options === null ? 'Loading reasons…'
    : count === 0 ? 'Choose your reasons'
    : `${count} chosen`;

  return (
    <Screen title="Your reason" step={2} onBack={() => navigation.goBack()}
      footer={<>
        <Button label="See my report" icon="document-text" disabled={!reasons.length || (other && !own.trim())}
          onPress={() => go(reasons)} />
        <Button label="Skip this question" kind="ghost" small onPress={() => go([])} />
      </>}>
      <Text style={T.title}>Why do you take {name}?</Text>
      <Text style={[T.sub, { marginTop: 6, marginBottom: 18 }]}>
        Choose one or more reasons. We'll tell you if {name} really helps with each.
      </Text>

      <Text style={s.label}>Reasons</Text>
      <Pressable onPress={() => options && setOpen(o => !o)} style={[s.select, (open || count > 0) && s.selectOn, open && s.selectOpen]}
        accessibilityRole="button" accessibilityState={{ expanded: open }}
        accessibilityLabel={`${summary}. Tap to ${open ? 'close' : 'open'} the list`}>
        {options === null ? <ActivityIndicator color={C.brand} /> : null}
        <Text style={[s.selectTxt, count === 0 && { color: C.faint }]}>{summary}</Text>
        <Icon name={open ? 'chevron-up' : 'chevron-down'} size={22} color={C.sub} />
      </Pressable>

      {/* The list drops down from the box */}
      {open && (
        <View style={s.drop}>
          <ScrollView style={{ maxHeight: 290 }} nestedScrollEnabled showsVerticalScrollIndicator persistentScrollbar
            keyboardShouldPersistTaps="handled">
            {(options || []).map(r => {
              const on = picked.includes(r);
              const off = !on && full;
              return (
                <Pressable key={r} onPress={() => toggle(r)} disabled={off}
                  accessibilityRole="checkbox" accessibilityState={{ checked: on, disabled: off }}
                  style={({ pressed }) => [s.row, s.rowLine, (pressed || on) && { backgroundColor: C.tint }, off && { opacity: 0.45 }]}>
                  <Icon name={on ? 'checkmark-circle' : 'ellipse-outline'} size={24} color={on ? C.brand : C.faint} />
                  <Text style={[s.rowTxt, on && { fontWeight: '700', color: C.brandDark }]}>{r}</Text>
                </Pressable>
              );
            })}
          </ScrollView>
          {/* "Other" stays in view under the list, however long the list is */}
          <Pressable onPress={toggleOther} disabled={!other && full}
              accessibilityRole="checkbox" accessibilityState={{ checked: other }}
              style={({ pressed }) => [s.row, s.otherRow, (pressed || other) && { backgroundColor: C.tint }, !other && full && { opacity: 0.45 }]}>
              <Icon name={other ? 'checkmark-circle' : 'ellipse-outline'} size={24} color={other ? C.brand : C.faint} />
              <Text style={[s.rowTxt, other && { fontWeight: '700', color: C.brandDark }]}>Other</Text>
            </Pressable>
          {other && (
            <View style={s.otherBox}>
              <TextInput style={s.input} value={own} onChangeText={setOwn} autoFocus maxLength={80} returnKeyType="done"
                onSubmitEditing={() => own.trim() && setOpen(false)}
                placeholder="Write your reason, e.g. Hair fall" placeholderTextColor={C.faint} />
            </View>
          )}
          <Pressable onPress={() => setOpen(false)} style={s.done} accessibilityRole="button">
            <Text style={s.doneTxt}>Done</Text>
          </Pressable>
        </View>
      )}
      {full && open ? <Text style={[T.small, { marginTop: 6, marginLeft: 4 }]}>You can choose up to {MAX} reasons.</Text> : null}

      {/* Chosen reasons: tap the cross to remove one */}
      {!open && picked.length > 0 && (
        <View style={s.chips}>
          {picked.map(r => (
            <View key={r} style={s.chip}>
              <Text style={s.chipTxt}>{r}</Text>
              <Pressable onPress={() => toggle(r)} hitSlop={10} accessibilityRole="button" accessibilityLabel={`Remove ${r}`}>
                <Icon name="close-circle" size={20} color={C.brandDark} />
              </Pressable>
            </View>
          ))}
        </View>
      )}

      {/* Only after "Other" is chosen */}
      {other && !open && (
        <View style={{ marginTop: 18 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center' }}>
            <Text style={[s.label, { flex: 1 }]}>Other reason</Text>
            <Pressable onPress={toggleOther} hitSlop={10} accessibilityRole="button" accessibilityLabel="Remove other reason">
              <Text style={s.remove}>Remove</Text>
            </Pressable>
          </View>
          <TextInput style={s.input} value={own} onChangeText={setOwn} maxLength={80} returnKeyType="done"
            placeholder="Write your reason, e.g. Hair fall" placeholderTextColor={C.faint} />
          <Text style={[T.small, { marginTop: 6, marginLeft: 4 }]}>We'll check if {name} really helps with it.</Text>
        </View>
      )}
    </Screen>
  );
}

const s = StyleSheet.create({
  label:      { fontSize: 14, fontWeight: '700', color: C.sub, marginBottom: 8, marginLeft: 4 },
  select:     { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, borderRadius: 16, borderWidth: 2,
                borderColor: C.line, backgroundColor: '#fff', paddingHorizontal: 16, paddingVertical: 12 },
  selectOn:   { borderColor: C.brand },
  selectOpen: { borderBottomLeftRadius: 0, borderBottomRightRadius: 0 },
  selectTxt:  { flex: 1, fontSize: 18, lineHeight: 24, color: C.ink, fontWeight: '600' },
  drop:       { borderWidth: 2, borderTopWidth: 0, borderColor: C.brand, borderBottomLeftRadius: 16, borderBottomRightRadius: 16,
                backgroundColor: '#fff', overflow: 'hidden' },
  row:        { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 15, paddingHorizontal: 16 },
  rowLine:    { borderBottomWidth: 1, borderBottomColor: C.line },
  otherRow:   { borderTopWidth: 1, borderTopColor: C.line },
  otherBox:   { paddingHorizontal: 14, paddingBottom: 14, backgroundColor: C.tint },
  rowTxt:     { flex: 1, fontSize: 17, lineHeight: 23, color: C.ink },
  done:       { borderTopWidth: 1, borderTopColor: C.line, paddingVertical: 13, alignItems: 'center' },
  doneTxt:    { fontSize: 16, fontWeight: '700', color: C.brandDark },
  chips:      { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 },
  chip:       { flexDirection: 'row', alignItems: 'center', gap: 6, backgroundColor: C.tint, borderRadius: 20,
                paddingVertical: 8, paddingLeft: 14, paddingRight: 10, maxWidth: '100%' },
  chipTxt:    { fontSize: 15, fontWeight: '600', color: C.brandDark, flexShrink: 1 },
  remove:     { fontSize: 14, fontWeight: '700', color: C.brandDark, marginBottom: 8, marginRight: 4 },
  input:      { fontSize: 18, color: C.ink, backgroundColor: '#fff', borderRadius: 16, paddingHorizontal: 16, paddingVertical: 14,
                borderWidth: 2, borderColor: C.brand },
});
