// forms.js — form fields shared by Sign in, Sign up and Edit profile (used with Formik).
import React, { useState } from 'react';
import { View, Text, TextInput, Pressable, Modal, StyleSheet, Platform } from 'react-native';
import DateTimePicker from '@react-native-community/datetimepicker';
import { Icon, C, T, Button } from './ui';

// ── Date helpers: the form keeps "DD/MM/YYYY", the server gets "YYYY-MM-DD" ────
export function dobToIso(text) {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text || '');
  if (!m) return null;
  const [, d, mo, y] = m.map(Number);
  const date = new Date(Date.UTC(y, mo - 1, d));
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== mo - 1 || date.getUTCDate() !== d) return null;  // e.g. 30/02
  return `${y}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
}
export const isoToDob = iso => (iso ? iso.split('-').reverse().join('/') : '');
export function ageFrom(iso) {
  if (!iso) return null;
  const [y, m, d] = iso.split('-').map(Number);
  const now = new Date();
  return now.getFullYear() - y - ((now.getMonth() + 1 < m || (now.getMonth() + 1 === m && now.getDate() < d)) ? 1 : 0);
}
const maskDob = t => {
  const digits = t.replace(/\D/g, '').slice(0, 8);
  return [digits.slice(0, 2), digits.slice(2, 4), digits.slice(4)].filter(Boolean).join('/');
};

// ── Fields ─────────────────────────────────────────────────────────────────────
export function Field({ label, icon, error, hint, right, style, ...input }) {
  const [focus, setFocus] = useState(false);
  return (
    <View style={style}>
      {label ? <Text style={f.label}>{label}</Text> : null}
      <View style={[f.box, focus && f.focus, error && f.bad]}>
        {icon ? <Icon name={icon} size={20} color={focus ? C.brand : C.sub} /> : null}
        <TextInput style={f.input} placeholderTextColor={C.faint} onFocus={() => setFocus(true)}
          {...input} onBlur={e => { setFocus(false); input.onBlur?.(e); }} />
        {right}
      </View>
      {error ? <Text style={f.err}>{error}</Text> : hint ? <Text style={f.hint}>{hint}</Text> : null}
    </View>
  );
}

export function PasswordField({ show, onToggle, ...props }) {
  return (
    <Field icon="lock-closed-outline" secureTextEntry={!show} autoCapitalize="none" autoCorrect={false} {...props}
      right={onToggle ? (
        <Pressable onPress={onToggle} hitSlop={10} accessibilityLabel={show ? 'Hide password' : 'Show password'}>
          <Icon name={show ? 'eye-off-outline' : 'eye-outline'} size={22} color={C.sub} />
        </Pressable>
      ) : null} />
  );
}

// Date of birth: type it as DD/MM/YYYY, or tap the calendar.
export function DobField({ value, onChange, error, label = 'Date of birth' }) {
  const [open, setOpen] = useState(false);
  const [temp, setTemp] = useState(null);             // date shown on the iPhone wheel; saved when "Done" is pressed
  const iso = dobToIso(value);
  const age = ageFrom(iso);
  const start = iso ? new Date(iso + 'T12:00:00') : new Date(2000, 0, 1);
  const pick = date => {
    if (!date) return;
    onChange(`${String(date.getDate()).padStart(2, '0')}/${String(date.getMonth() + 1).padStart(2, '0')}/${date.getFullYear()}`);
  };
  return (
    <View>
      <Field label={label} icon="calendar-outline" value={value} onChangeText={t => onChange(maskDob(t))}
        placeholder="DD/MM/YYYY" keyboardType="number-pad" maxLength={10} error={error}
        hint={age !== null && age >= 0 && !error ? `Age: ${age}` : null}
        right={
          <Pressable onPress={() => { setTemp(start); setOpen(true); }} hitSlop={10} accessibilityLabel="Open calendar" style={f.calBtn}>
            <Icon name="calendar" size={20} color={C.brand} />
          </Pressable>
        } />
      {open && Platform.OS === 'android' ? (
        <DateTimePicker value={start} mode="date" maximumDate={new Date()} minimumDate={new Date(1906, 0, 1)}
          onChange={(e, d) => { setOpen(false); if (e.type === 'set') pick(d); }} />
      ) : null}
      {Platform.OS !== 'android' ? (
        <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
          <Pressable style={f.dim} onPress={() => setOpen(false)} />
          <View style={f.sheet}>
            <Text style={[T.h3, { textAlign: 'center' }]}>Date of birth</Text>
            <DateTimePicker value={temp || start} mode="date" display="spinner" maximumDate={new Date()}
              minimumDate={new Date(1906, 0, 1)} onChange={(e, d) => d && setTemp(d)} themeVariant="light" />
            <Button label="Done" small onPress={() => { pick(temp || start); setOpen(false); }} />
          </View>
        </Modal>
      ) : null}
    </View>
  );
}

// One choice from a short list, shown as rows with a radio dot.
export function Choice({ label, options, value, onChange, error }) {
  return (
    <View>
      {label ? <Text style={f.label}>{label}</Text> : null}
      <View style={[f.choices, options.length <= 2 && { flexDirection: 'row' }]} accessibilityRole="radiogroup">
        {options.map(o => {
          const on = o.value === value;
          return (
            <Pressable key={String(o.value)} onPress={() => onChange(o.value)} accessibilityRole="radio"
              accessibilityState={{ selected: on }} style={[f.choice, on && f.choiceOn, options.length <= 2 && { flex: 1 }]}>
              <View style={[f.radio, on && f.radioOn]}>{on ? <View style={f.radioDot} /> : null}</View>
              <View style={{ flex: 1 }}>
                <Text style={[f.choiceTxt, on && { color: C.brandDark }]}>{o.label}</Text>
                {o.help ? <Text style={f.choiceHelp}>{o.help}</Text> : null}
              </View>
            </Pressable>
          );
        })}
      </View>
      {error ? <Text style={f.err}>{error}</Text> : null}
    </View>
  );
}

// Plain blue text link, e.g. "Sign up" or "Forgot password?"
export const LinkText = ({ children, onPress, style }) => (
  <Text onPress={onPress} style={[f.link, style]} accessibilityRole="link">{children}</Text>
);

// Periods options. Oligomenorrhea = periods that come rarely or on no regular schedule (fewer than ~8 a year).
export const PERIOD_OPTIONS = [
  { value: 'yes', label: 'Regular periods', help: 'About once a month' },
  { value: 'irregular', label: 'Oligomenorrhea', help: 'Periods come rarely or at unpredictable times' },
  { value: 'no', label: 'No periods', help: 'Not started yet, stopped, or after menopause' },
];
export const periodLabel = v => (PERIOD_OPTIONS.find(o => o.value === v) || {}).label || 'Not set';

const f = StyleSheet.create({
  label:     { fontSize: 14, fontWeight: '600', color: C.sub, marginBottom: 6 },
  box:       { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 52, borderRadius: 12, borderWidth: 1.5,
               borderColor: C.line, backgroundColor: '#fff', paddingHorizontal: 14 },
  focus:     { borderColor: C.brand },
  bad:       { borderColor: C.danger },
  input:     { flex: 1, minWidth: 0, fontSize: 16, color: C.ink, paddingVertical: 12 },
  err:       { color: C.danger, fontSize: 13, marginTop: 5 },
  hint:      { color: C.sub, fontSize: 13, marginTop: 5 },
  calBtn:    { paddingLeft: 6, paddingVertical: 6 },
  dim:       { flex: 1, backgroundColor: 'rgba(15,23,42,0.4)' },
  sheet:     { backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: 34, gap: 8 },
  choices:   { gap: 8 },
  choice:    { flexDirection: 'row', alignItems: 'center', gap: 12, borderRadius: 12, borderWidth: 1.5, borderColor: C.line,
               paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff' },
  choiceOn:  { borderColor: C.brand, backgroundColor: C.tint },
  radio:     { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: C.faint, alignItems: 'center', justifyContent: 'center' },
  radioOn:   { borderColor: C.brand },
  radioDot:  { width: 10, height: 10, borderRadius: 5, backgroundColor: C.brand },
  choiceTxt: { fontSize: 16, fontWeight: '600', color: C.ink },
  choiceHelp:{ fontSize: 13, color: C.sub, marginTop: 1 },
  link:      { color: C.brand, fontSize: 15, fontWeight: '600' },
});
