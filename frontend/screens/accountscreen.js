// accountscreen.js — the Profile tab: account details and health details, with Edit and Sign out.
import React, { useCallback, useState } from 'react';
import { View, Text, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { signOut } from 'firebase/auth';
import { Screen, Button, Icon, Avatar, C, T } from '../ui';
import { LinkText, periodLabel, isoToDob } from '../forms';
import { getProfile, cachedProfile } from '../config';
import { auth } from '../firebase';

const Row = ({ label, value, last }) => (
  <View style={[s.row, !last && s.rowLine]}>
    <Text style={s.rowLabel}>{label}</Text>
    <Text style={s.rowValue}>{value}</Text>
  </View>
);

export default function AccountScreen({ navigation }) {
  const [p, setP] = useState(null);

  const [loaded, setLoaded] = useState(false);
  useFocusEffect(useCallback(() => {
    cachedProfile().then(c => c && setP(x => x ?? c));                 // the phone's copy shows at once
    getProfile().then(x => { if (x) setP(x); setLoaded(true); });     // then the account's copy
  }, []));
  const me = auth.currentUser;

  const logout = async () => { await signOut(auth); navigation.reset({ index: 0, routes: [{ name: 'Auth' }] }); };
  const female = p?.sex === 'female';
  const yesNo = v => (v ? 'Yes' : 'No');

  return (
    <Screen title="Profile" bg={C.soft} tabs={{ navigation, current: 'Profile' }}
      right={p ? (
        <Pressable onPress={() => navigation.navigate('EditProfile')} hitSlop={10} style={s.edit}
          accessibilityRole="button" accessibilityLabel="Edit profile">
          <Icon name="create-outline" size={20} color={C.brand} />
          <Text style={s.editTxt}>Edit</Text>
        </Pressable>
      ) : null}>
      {!p && !loaded ? <ActivityIndicator color={C.brand} style={{ marginTop: 40 }} /> : !p ? (
        <View style={{ alignItems: 'center', gap: 10, paddingTop: 30 }}>
          <Avatar size={96} />
          <Text style={T.title}>{me?.displayName || 'Your profile'}</Text>
          <Text style={T.sub}>{me?.email}</Text>
          <Text style={[T.sub, { textAlign: 'center', marginTop: 8 }]}>Add your date of birth and gender once, so every check is made for you.</Text>
          <View style={{ alignSelf: 'stretch', marginTop: 8 }}>
            <Button label="Add your details" icon="create-outline" onPress={() => navigation.navigate('EditProfile')} />
          </View>
          <LinkText onPress={logout} style={{ marginTop: 18 }}>Sign out</LinkText>
        </View>
      ) : <>
        <View style={s.top}>
          <Avatar sex={p.sex} size={104} />
          <Text style={[T.title, { marginTop: 12 }]}>{p.name || 'Your name'}</Text>
          {p.username ? <Text style={T.sub}>@{p.username}</Text> : null}
        </View>

        <Text style={s.group}>Account</Text>
        <View style={s.card}>
          <Row label="Name" value={p.name || 'Not set'} />
          {p.username ? <Row label="Username" value={'@' + p.username} /> : null}
          <Row label="Email" value={p.email || auth.currentUser?.email || ''} last />
        </View>

        <Text style={s.group}>About you</Text>
        <View style={s.card}>
          <Row label="Date of birth" value={p.dob ? isoToDob(p.dob) : 'Not set'} />
          <Row label="Age" value={p.age != null ? `${p.age} years` : 'Not set'} />
          <Row label="Gender" value={female ? 'Female' : 'Male'} last={!female} />
          {female ? <>
            <Row label="Periods" value={p.periods ? periodLabel(p.periods) : 'Not asked'} />
            <Row label="Pregnant" value={yesNo(p.pregnant)} />
            <Row label="Breastfeeding" value={yesNo(p.breastfeeding)} last />
          </> : null}
        </View>

        <View style={s.privacy}>
          <Icon name="lock-closed" size={14} color={C.sub} />
          <Text style={[T.small, { flex: 1 }]}>Your details are private to your account. The AI never sees your name or email.</Text>
        </View>
        <LinkText onPress={logout} style={s.signout}>Sign out</LinkText>
      </>}

    </Screen>
  );
}

const s = StyleSheet.create({
  top:      { alignItems: 'center', paddingVertical: 10, marginBottom: 6 },
  plus:     { position: 'absolute', right: 0, bottom: 2, width: 34, height: 34, borderRadius: 17, backgroundColor: C.brand,
              alignItems: 'center', justifyContent: 'center', borderWidth: 3, borderColor: C.soft },
  group:    { fontSize: 13, fontWeight: '700', color: C.sub, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 18, marginBottom: 8, marginLeft: 4 },
  card:     { backgroundColor: '#fff', borderRadius: 14, borderWidth: 1, borderColor: C.line, paddingHorizontal: 16 },
  row:      { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 14, gap: 12 },
  rowLine:  { borderBottomWidth: 1, borderBottomColor: C.line },
  rowLabel: { fontSize: 15, color: C.sub },
  rowValue: { fontSize: 16, fontWeight: '600', color: C.ink, flexShrink: 1, textAlign: 'right' },
  edit:     { flexDirection: 'row', alignItems: 'center', gap: 4 },
  editTxt:  { color: C.brand, fontSize: 16, fontWeight: '600' },
  signout:  { textAlign: 'center', marginTop: 26, marginBottom: 10, fontSize: 16 },
  privacy:  { flexDirection: 'row', gap: 8, alignItems: 'center', marginTop: 18, paddingHorizontal: 4 },
  dim:      { flex: 1, backgroundColor: 'rgba(15,23,42,0.4)' },
  sheet:    { backgroundColor: '#fff', borderTopLeftRadius: 20, borderTopRightRadius: 20, padding: 20, paddingBottom: 34, gap: 10 },
});
