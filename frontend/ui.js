// ui.js — colours, text styles and the building blocks every screen shares
import React, { useState } from 'react';
import { View, Text, Image, Pressable, StyleSheet, StatusBar, ScrollView, ActivityIndicator, Platform, KeyboardAvoidingView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

export const C = {
  bg:        '#FFFFFF',
  soft:      '#F4F6FA',
  ink:       '#0F172A',
  sub:       '#475569',
  faint:     '#94A3B8',
  line:      '#E2E8F0',
  brand:     '#2457C5',
  brandDark: '#173E91',
  tint:      '#EAF1FD',
  safe:      '#15803D', safeBg:    '#E9F7EE',
  caution:   '#C2410C', cautionBg: '#FFF1E6',
  danger:    '#C0261A', dangerBg:  '#FDECEA',
};

export const T = StyleSheet.create({
  hero:  { fontSize: 32, lineHeight: 38, fontWeight: '800', color: C.ink },
  title: { fontSize: 26, lineHeight: 32, fontWeight: '800', color: C.ink },
  h2:    { fontSize: 20, lineHeight: 26, fontWeight: '700', color: C.ink },
  h3:    { fontSize: 17, lineHeight: 23, fontWeight: '700', color: C.ink },
  body:  { fontSize: 17, lineHeight: 25, color: C.ink },
  sub:   { fontSize: 16, lineHeight: 23, color: C.sub },
  small: { fontSize: 14, lineHeight: 20, color: C.sub },
});

export const Icon = ({ name, size = 22, color = C.ink, style }) =>
  <Ionicons name={name} size={size} color={color} style={style} />;

export const STATUS = {
  ok:      { icon: 'checkmark-circle', color: C.safe,    bg: C.safeBg },
  caution: { icon: 'alert-circle',     color: C.caution, bg: C.cautionBg },
  stop:    { icon: 'close-circle',     color: C.danger,  bg: C.dangerBg },
  info:    { icon: 'information-circle', color: C.sub,   bg: C.soft },
};

export const shadow = Platform.select({
  ios: { shadowColor: '#0B2A22', shadowOpacity: 0.08, shadowRadius: 14, shadowOffset: { width: 0, height: 4 } },
  default: { elevation: 3, shadowColor: '#0B2A22' },
});

// Screen: header (back, title, step dots), content, footer with the main action.
export function Screen({ title, onBack, step, right, children, footer, scroll = true, bg = C.bg, scrollRef, tabs, header }) {
  const Body = scroll ? ScrollView : View;
  return (
    <SafeAreaView style={[s.root, { backgroundColor: bg }]} edges={['top', 'bottom']}>
      <StatusBar barStyle="dark-content" backgroundColor={bg} />
      {header || <View style={s.bar}>
        <View style={s.side}>
          {onBack ? (
            <Pressable onPress={onBack} hitSlop={14} style={s.back} accessibilityRole="button" accessibilityLabel="Go back">
              <Icon name="arrow-back" size={24} color={C.ink} />
            </Pressable>
          ) : null}
        </View>
        <View style={{ alignItems: 'center' }}>
          {title ? <Text style={s.barTitle}>{title}</Text> : null}
          {step ? (
            <View style={s.dots} accessibilityLabel={`Step ${step} of 3`}>
              {[1, 2, 3].map(i => <View key={i} style={[s.dot, i === step && s.dotOn, i < step && { backgroundColor: C.brand }]} />)}
            </View>
          ) : null}
        </View>
        <View style={[s.side, { alignItems: 'flex-end' }]}>{right}</View>
      </View>}
      {/* the keyboard pushes the content up instead of covering what you type */}
      <KeyboardAvoidingView style={{ flex: 1 }} behavior="padding">
        <Body style={{ flex: 1 }} {...(scroll ? { ref: scrollRef, contentContainerStyle: s.content, keyboardShouldPersistTaps: 'handled',
                                                   automaticallyAdjustKeyboardInsets: true } : {})}>
          {children}
        </Body>
        {footer ? <View style={s.footer}>{footer}</View> : null}
      </KeyboardAvoidingView>
      {tabs ? <TabBar navigation={tabs.navigation} current={tabs.current} /> : null}
    </SafeAreaView>
  );
}

export function Button({ label, icon, onPress, kind = 'primary', disabled, loading, small }) {
  const look = {
    primary:   { bg: C.brand, fg: '#fff' },
    secondary: { bg: '#fff', fg: C.brandDark, border: C.line },
    ghost:     { bg: 'transparent', fg: C.brandDark },
    white:     { bg: '#fff', fg: C.brandDark },
  }[kind];
  return (
    <Pressable onPress={onPress} disabled={disabled || loading} accessibilityRole="button" accessibilityLabel={label}
      style={({ pressed }) => [s.btn, small && s.btnSmall, { backgroundColor: look.bg },
        look.border && { borderWidth: 1.5, borderColor: look.border }, pressed && { opacity: 0.85 },
        (disabled || loading) && { opacity: 0.4 }]}>
      {loading ? <ActivityIndicator color={look.fg} /> : (
        <>
          {icon ? <Icon name={icon} size={small ? 18 : 20} color={look.fg} /> : null}
          <Text style={[s.btnTxt, small && { fontSize: 15 }, { color: look.fg }]}>{label}</Text>
        </>
      )}
    </Pressable>
  );
}

// Bottom navigation for the three main pages: Home, History, Profile (icons only).
const TABS = [{ name: 'Home', icon: 'home' }, { name: 'History', icon: 'time' }, { name: 'Profile', icon: 'person' }];
export function TabBar({ navigation, current }) {
  return (
    <View style={s.tabs} accessibilityRole="tablist">
      {TABS.map(t => {
        const on = t.name === current;
        return (
          <Pressable key={t.name} style={s.tab} accessibilityRole="tab" accessibilityLabel={t.name} accessibilityState={{ selected: on }}
            onPress={() => !on && navigation.reset({ index: 0, routes: [{ name: t.name }] })}>
            <Icon name={on ? t.icon : `${t.icon}-outline`} size={26} color={on ? C.brand : C.faint} />
            <View style={[s.tabDot, on && { backgroundColor: C.brand }]} />
          </Pressable>
        );
      })}
    </View>
  );
}

// The MediSafe mark: blue rounded square with a white cross.
export const Logo = ({ size = 34 }) => (
  <View style={{ width: size, height: size, borderRadius: size * 0.3, backgroundColor: C.brand, alignItems: 'center', justifyContent: 'center' }}>
    <View style={{ position: 'absolute', width: size * 0.2, height: size * 0.56, borderRadius: size * 0.06, backgroundColor: '#fff' }} />
    <View style={{ position: 'absolute', width: size * 0.56, height: size * 0.2, borderRadius: size * 0.06, backgroundColor: '#fff' }} />
  </View>
);

// Round profile picture: the user's photo, or a plain male/female icon.
export function Avatar({ photo, sex, size = 40 }) {
  if (photo) return <Image source={{ uri: photo }} style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: C.soft }} />;
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: C.tint, alignItems: 'center', justifyContent: 'center' }}>
      <Icon name={sex === 'female' ? 'woman' : sex === 'male' ? 'man' : 'person'} size={size * 0.55} color={C.brandDark} />
    </View>
  );
}

export const Card = ({ children, style }) => <View style={[s.card, style]}>{children}</View>;

export const IconCircle = ({ name, color = C.brand, bg = C.tint, size = 44 }) => (
  <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: bg, alignItems: 'center', justifyContent: 'center' }}>
    <Icon name={name} size={size * 0.5} color={color} />
  </View>
);

// Tap to open / close. Keeps long details out of the way until someone wants them.
export function Accordion({ icon, color = C.brand, title, summary, children, open: startOpen = false }) {
  const [open, setOpen] = useState(startOpen);
  return (
    <View style={s.acc}>
      <Pressable onPress={() => setOpen(o => !o)} style={s.accHead} accessibilityRole="button"
        accessibilityState={{ expanded: open }}>
        <IconCircle name={icon} color={color} bg={color + '18'} size={40} />
        <View style={{ flex: 1 }}>
          <Text style={T.h3}>{title}</Text>
          {summary ? <Text style={T.small} numberOfLines={1}>{summary}</Text> : null}
        </View>
        <Icon name={open ? 'chevron-up' : 'chevron-down'} size={22} color={C.faint} />
      </Pressable>
      {open ? <View style={s.accBody}>{children}</View> : null}
    </View>
  );
}

// Segmented control: one row of options, one selected. Used in forms.
export function Segmented({ options, value, onChange }) {
  return (
    <View style={s.seg} accessibilityRole="radiogroup">
      {options.map(o => {
        const on = o.value === value;
        return (
          <Pressable key={String(o.value)} onPress={() => onChange(o.value)} style={[s.segItem, on && s.segOn]}
            accessibilityRole="radio" accessibilityState={{ selected: on }}>
            <Text style={[s.segTxt, on && { color: '#fff' }]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// Small coloured result label: ok | caution | stop
export function Chip({ status, label }) {
  const st = STATUS[status];
  return (
    <View style={[s.chip, { backgroundColor: st.bg }]}>
      <Icon name={st.icon} size={15} color={st.color} />
      <Text style={[s.chipTxt, { color: st.color }]}>{label}</Text>
    </View>
  );
}

// Coloured message: kind = ok | caution | stop
export function Notice({ kind, title, children, icon }) {
  const st = STATUS[kind];
  return (
    <View style={[s.notice, { backgroundColor: st.bg }]}>
      <Icon name={icon || st.icon} size={24} color={st.color} />
      <View style={{ flex: 1 }}>
        {title ? <Text style={[T.h3, { color: st.color, marginBottom: 2 }]}>{title}</Text> : null}
        {typeof children === 'string' ? <Text style={T.body}>{children}</Text> : children}
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  root:     { flex: 1 },
  bar:      { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingVertical: 8, minHeight: 56 },
  side:     { minWidth: 72 },
  back:     { width: 44, height: 44, alignItems: 'flex-start', justifyContent: 'center' },
  barTitle: { fontSize: 17, fontWeight: '700', color: C.ink },
  dots:     { flexDirection: 'row', gap: 6, marginTop: 6 },
  dot:      { width: 8, height: 8, borderRadius: 4, backgroundColor: C.line },
  dotOn:    { width: 22, backgroundColor: C.brand },
  content:  { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 32 },
  footer:   { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 12, gap: 8 },
  btn:      { minHeight: 54, borderRadius: 12, flexDirection: 'row', gap: 8, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 20 },
  btnSmall: { minHeight: 44, borderRadius: 10 },
  btnTxt:   { fontSize: 17, fontWeight: '600', letterSpacing: 0.2 },
  card:     { backgroundColor: '#fff', borderRadius: 16, padding: 18, borderWidth: 1, borderColor: C.line },
  acc:      { backgroundColor: '#fff', borderRadius: 20, marginBottom: 12, ...shadow },
  accHead:  { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, minHeight: 72 },
  accBody:  { paddingHorizontal: 18, paddingBottom: 18 },
  seg:      { flexDirection: 'row', backgroundColor: C.soft, borderRadius: 14, padding: 4, gap: 4 },
  segItem:  { flex: 1, minHeight: 46, borderRadius: 11, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 },
  segOn:    { backgroundColor: C.brand },
  segTxt:   { fontSize: 16, fontWeight: '700', color: C.sub },
  chip:     { flexDirection: 'row', alignItems: 'center', gap: 4, borderRadius: 10, paddingHorizontal: 8, paddingVertical: 4, alignSelf: 'flex-start' },
  chipTxt:  { fontSize: 13, fontWeight: '700' },
  tabs:     { flexDirection: 'row', borderTopWidth: 1, borderTopColor: C.line, backgroundColor: '#fff', paddingTop: 8, paddingBottom: 4 },
  tab:      { flex: 1, alignItems: 'center', gap: 4, paddingVertical: 4 },
  tabDot:   { width: 5, height: 5, borderRadius: 3, backgroundColor: 'transparent' },
  notice:   { flexDirection: 'row', gap: 12, borderRadius: 18, padding: 16, marginBottom: 12 },
});
