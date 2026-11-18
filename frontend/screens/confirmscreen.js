// confirmscreen.js — "Is this your supplement?" Name, maker, who it's for, what we read — in one summary.
import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TextInput, Image, Pressable, StyleSheet, Modal, ActivityIndicator, ScrollView } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Screen, Button, Notice, Chip, Icon, IconCircle, C, T, shadow } from '../ui';
import { api, getProfile, cachedProfile, describeProfile, errorMessage } from '../config';

// Manufacturer line: "official" = the registered maker(s) of this brand in our data.
const MAKER = {
  verified:          { status: 'ok',      chip: 'Genuine',       text: c => c.official?.length ? 'The pack shows the official maker of this brand.' : 'A registered manufacturer.' },
  verified_by_brand: { status: 'ok',      chip: 'Official maker', text: c => `Check that your pack shows ${c.official.join(' or ')}. If it shows a different company, it may be fake.` },
  unregistered:      { status: 'caution', chip: 'Not registered', text: c => `"${c.printed_name}" is not in our list of registered manufacturers. Genuine packs show a registered maker and a DRAP registration number.` },
  brand_seen:        { status: 'info',    chip: 'Not verified',   text: () => "This brand is not in our list of verified manufacturers, so we can't confirm it is genuine. Genuine packs show the maker's address and a DRAP registration number." },
  not_found:         { status: 'info',    chip: 'Not seen',       text: () => "We couldn't see the maker's name. Genuine packs show the maker and a DRAP registration number. Buy from a licensed pharmacy." },
  mismatch:          { status: 'caution', chip: 'Check maker',    text: c => `This brand is usually made by ${c.expected}. Some brands are made under licence by another company. If your pack doesn't say "under licence", it may not be genuine.` },
};

// Shown on its own (no product page behind it) when the scanned product is a medicine, or one we have no data on.
function NotSupported({ medicine, typed, onScan, onType }) {
  return (
    <ScrollView style={{ flex: 1, backgroundColor: C.soft }} contentContainerStyle={[s.dim, { flexGrow: 1 }]}>
      <View style={s.popup}>
        <View style={s.popIcon}><Icon name={medicine ? 'medical' : 'help-circle'} size={26} color={C.caution} /></View>
        <Text style={s.popTitle}>
          {medicine ? `${typed || 'This'} is a medicine, not a supplement`
            : typed ? `We don't have ${typed} in our data` : "We couldn't read what's in this pack"}
        </Text>
        <Text style={[T.sub, { textAlign: 'center' }]}>
          {medicine
            ? 'MediSafe checks vitamins, minerals and herbal supplements only, so there is no report for medicines.'
            : typed ? "Scan the pack instead: we read the ingredients and their amounts from the label, so any brand can be checked."
            : "We couldn't read the ingredients in the photo and couldn't find this product online. Try a clearer photo of the label."}
        </Text>
        <View style={{ alignSelf: 'stretch', gap: 8, marginTop: 8 }}>
          <Button label="Scan a supplement" icon="camera-outline" onPress={onScan} />
          <Button label={typed ? 'Type the name again' : 'It is a supplement: type its name'} kind="secondary" small onPress={onType} />
        </View>
      </View>
    </ScrollView>
  );
}

const Row = ({ icon, label, children, onPress, last }) => {
  const Wrap = onPress ? Pressable : View;
  return (
    <Wrap onPress={onPress} style={[s.row, !last && s.rowLine]} {...(onPress ? { accessibilityRole: 'button' } : {})}>
      <Icon name={icon} size={22} color={C.brand} style={{ marginTop: 2 }} />
      <View style={{ flex: 1 }}>
        <Text style={T.small}>{label}</Text>
        {children}
      </View>
      {onPress ? <Icon name="chevron-forward" size={20} color={C.faint} style={{ alignSelf: 'center' }} /> : null}
    </Wrap>
  );
};

export default function ConfirmScreen({ route, navigation }) {
  const { photo } = route.params;
  const [scan, setScan] = useState(route.params.scan);     // replaced when the full ingredient list is found online
  // Only the front of the pack was in the photo (or nothing readable): find the full ingredient list ourselves,
  // from the NIH label database or the brand's website. The user doesn't scan again or type anything.
  const needsLookup = !scan.product.medicine && !['search', 'ocr'].includes(scan.product.source) && !scan.label?.composition_source
    && (scan.label?.facts_seen === false || !scan.product.supported);
  const [lookup, setLookup] = useState(needsLookup ? 'busy' : 'idle');   // busy | done | none | idle
  useEffect(() => {
    if (!needsLookup) return;
    api.post('/lookup-composition', { scan_id: scan.scan_id }, { timeout: 60000 })
      .then(res => { setScan(res.data); setLookup('done'); if (!name.trim()) { setName(res.data.product.name || ''); setEditing(false); } })
      .catch(() => setLookup('none'));
  }, []);
  const [profile, setProfile] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [name, setName] = useState(scan.product.name || '');
  const [editing, setEditing] = useState(!scan.product.identified);
  const [refused, setRefused] = useState(null);           // 'medicine' | 'unknown' for a typed name we can't check
  const [checking, setChecking] = useState(false);
  const [names, setNames] = useState([]);                  // products we can check, for picking instead of typing
  useEffect(() => { api.get('/products').then(r => setNames(r.data.products)).catch(() => {}); }, []);
  const q = name.trim().toLowerCase();
  const picks = editing && q.length >= 2 && !names.some(n => n.toLowerCase() === q)
    ? names.filter(n => n.toLowerCase().includes(q)).slice(0, 5) : [];
  useFocusEffect(useCallback(() => {
    // the phone's copy is used straight away; the account's copy only fills in if the phone has none
    cachedProfile().then(c => {
      if (c) { setProfile(c); setLoaded(true); getProfile().then(x => x && setProfile(x)); }
      else getProfile().then(x => { setProfile(x); setLoaded(true); });
    });
  }, []));

  const company = scan.company;
  const maker = MAKER[company.status];
  const fake = company.status === 'mismatch';
  const unknown = !scan.product.supported && !editing;     // medicine, or a product we have no data on

  const next = async () => {
    const typed = name.trim();
    if (typed !== (scan.product.name || '')) {             // a typed name: check we can report on it first
      setChecking(true);
      try {
        const res = await api.post('/check-name', { name: typed });
        // a name we don't know is fine when the pack's own composition was read from the photo
        const fromLabel = Object.keys(scan.label?.amounts || {}).length > 0;
        if (res.data.status === 'medicine' || (res.data.status === 'unknown' && !fromLabel)) return setRefused(res.data.status);
      } catch { /* server check failed: the report step will still refuse unknown products */ }
      finally { setChecking(false); }
    }
    navigation.navigate('Reasons', { scan, photo, profile, name: typed });
  };
  const label = scan.label;
  const extra = (label.all_ingredients || []).filter(x => !x.checked).map(x => x.amount ? `${x.name} ${x.amount}` : x.name);
  const frontOnly = scan.product.source !== 'search' && label.facts_seen === false;

  // Clearly read, known product: a short "Found it" card, then straight on to the reason step.
  const [full, setFull] = useState(false);
  const eligible = !full && scan.product.supported && scan.product.identified && scan.product.source === 'ocr'
    && company.status !== 'mismatch';
  const quick = eligible && !!profile;
  if (eligible && !loaded) return <View style={s.quickRoot} />;   // wait for the profile, so no page flashes first

  if (lookup === 'busy' && !scan.product.supported) {        // nothing readable yet: wait for the lookup
    return (
      <View style={s.dim}>
        <View style={s.popup}>
          <ActivityIndicator size="large" color={C.brand} />
          <Text style={s.popTitle}>Looking up this product</Text>
          <Text style={[T.sub, { textAlign: 'center' }]}>We couldn't read the ingredients in the photo, so we're finding its full ingredient list.</Text>
        </View>
      </View>
    );
  }

  if (unknown || refused) {
    return (
      <NotSupported medicine={refused ? refused === 'medicine' : scan.product.medicine} typed={refused ? name.trim() : null}
        onScan={() => navigation.goBack()} onType={() => { setRefused(null); setName(''); setEditing(true); }} />
    );
  }

  if (quick) {
    return (
      <View style={s.quickRoot}>
        <View style={s.quickCard}>
          {photo ? <Image source={{ uri: photo }} style={s.quickPhoto} /> : null}
          <View style={[s.valueRow, { justifyContent: 'center' }]}>
            <Icon name="checkmark-circle" size={22} color={C.safe} />
            <Text style={[T.small, { fontWeight: '700', color: C.safe }]}>Found it</Text>
          </View>
          <Text style={[T.title, { textAlign: 'center' }]}>{name}</Text>
          {company.name ? (
            <View style={[s.valueRow, { justifyContent: 'center' }]}>
              <Text style={T.sub}>by {company.name}</Text>
              <Chip status={maker.status} label={maker.chip} />
            </View>
          ) : null}
          <View style={{ alignSelf: 'stretch', gap: 6, marginTop: 8 }}>
            <Button label="Continue" icon="arrow-forward" onPress={() => navigation.replace('Reasons', { scan, photo, profile, name: name.trim() })} />
            <Button label="Not this one? Change it" kind="ghost" small onPress={() => { setFull(true); setEditing(true); }} />
          </View>
        </View>
      </View>
    );
  }

  // An account that never saved its details adds them once here, then comes straight back to this page.
  const footer = unknown ? null : loaded && !profile ? (
    <Button label="Add your details to continue" icon="person-add-outline" onPress={() => navigation.navigate('EditProfile')} />
  ) : (
    <Button label="Yes, this is it" icon="arrow-forward" disabled={name.trim().length < 2 || !profile || lookup === 'busy'}
      loading={checking} onPress={next} />
  );

  return (
    <Screen title="Your supplement" step={1} onBack={() => navigation.goBack()} footer={footer} bg={C.soft}>
      <View style={s.head}>
        {photo ? <Image source={{ uri: photo }} style={s.photo} /> : null}
        <View style={{ flex: 1 }}>
          <Text style={editing ? T.title : T.small}>{unknown ? 'We found' : editing ? 'What is the name on the pack?' : 'Is this your supplement?'}</Text>
          {editing ? null : (
            <>
              <Text style={T.title}>{name || 'Unknown product'}</Text>
              {!unknown && (
                <Pressable onPress={() => setEditing(true)} hitSlop={10} style={s.change} accessibilityRole="button">
                  <Icon name="pencil" size={15} color={C.brandDark} />
                  <Text style={s.changeTxt}>Wrong name? Change it</Text>
                </Pressable>
              )}
            </>
          )}
        </View>
      </View>
      {editing && (
        <TextInput style={[s.input, { marginBottom: 12 }]} value={name} onChangeText={setName} autoFocus
          placeholder="Type the name, e.g. Neurobion" placeholderTextColor={C.faint} returnKeyType="done" />
      )}
      {editing && !scan.product.identified && !q && (
        <Text style={[T.sub, { marginBottom: 12 }]}>We couldn't read the name on this pack. Start typing it and pick it from the list.</Text>
      )}
      {picks.length > 0 && (
        <View style={[s.card, { marginTop: -6, marginBottom: 14 }]}>
          {picks.map((n, i) => (
            <Pressable key={n} onPress={() => { setName(n); setEditing(false); }} accessibilityRole="button"
              style={[s.pick, i < picks.length - 1 && s.rowLine]}>
              <Icon name="medical" size={18} color={C.brand} />
              <Text style={[T.body, { flex: 1 }]}>{n}</Text>
              <Icon name="chevron-forward" size={18} color={C.faint} />
            </Pressable>
          ))}
        </View>
      )}
      {!editing && scan.product.source === 'composition' && name === scan.product.name && (
        <Notice kind="info" title="This brand is not in our data">
          {"That's fine: we read what's in it and how much from your pack, and check those exact amounts for you. If you know the brand name, tap \"Change it\"."}
        </Notice>
      )}
      {!editing && scan.product.source === 'ingredients' && name === scan.product.name && (
        <Notice kind="caution" title="We couldn't read the brand name">
          {`The label shows what's inside, so we'll check it as ${name.replace(/ supplement$/, '')}. If you know the brand, tap "Change it".`}
        </Notice>
      )}



      {!unknown && <View style={s.card}>
        <Row icon="business" label="Manufacturer">
          <View style={s.valueRow}>
            <Text style={[T.h3, { flexShrink: 1 }]}>{company.name || company.printed_name || 'Not seen on the pack'}</Text>
            <Chip status={maker.status} label={maker.chip} />
          </View>
          {maker.text(company) ? <Text style={[T.small, { marginTop: 4 }]}>{maker.text(company)}</Text> : null}
        </Row>
        {(
          <Row icon="person" label="Checking for" onPress={() => navigation.navigate('EditProfile')}>
            <Text style={T.h3}>{profile ? describeProfile(profile) : 'Add your health profile'}</Text>
          </Row>
        )}
        {(
          <Row icon="reader" label={scan.product.source === 'search' ? 'Strength' : "What's in this pack"} last>
            {label.strength.length ? label.strength.map(x => (
              <View key={x.nutrient} style={s.valueRow}>
                <Text style={[T.body, { flex: 1 }]}>{x.nutrient}</Text>
                <Text style={T.h3}>{x.amount}</Text>
              </View>
            )) : <Text style={T.body}>{scan.product.source === 'search'
              ? "You searched by name, so the report will use this product's usual strength."
              : scan.product.dataset_key ? "We couldn't read the strength. The report will use this product's usual information."
              : "We couldn't read the amounts in the photo."}</Text>}
            {label.composition_source ? (
              <Text style={[T.small, { marginTop: 6 }]}>Full ingredient list from {label.composition_source.name}. Check that the strength on your pack matches.</Text>
            ) : null}
            {extra.length ? (
              <Text style={[T.small, { marginTop: 6 }]}>Also on the label: {extra.join(', ')}. These have no NIH safety limit, so they are listed, not checked.</Text>
            ) : null}
            {label.directions ? <Text style={[T.small, { marginTop: 6 }]}>Directions: {label.directions}</Text> : null}
            {label.age_text ? <Text style={[T.small, { marginTop: 2 }]}>Age warning: {label.age_text}</Text> : null}
          </Row>
        )}
      </View>}

      {!unknown && lookup === 'busy' && (
        <View style={[s.card, { marginTop: 14, flexDirection: 'row', alignItems: 'center', gap: 12, padding: 16 }]}>
          <ActivityIndicator color={C.brand} />
          <Text style={[T.body, { flex: 1 }]}>Your photo shows only the front. Finding the full ingredient list for this product…</Text>
        </View>
      )}
      {!unknown && lookup === 'none' && frontOnly && (
        <View style={{ marginTop: 14 }}>
          <Notice kind="caution" title="Only the front of the pack was checked">
            We couldn't find this product's full ingredient list, so the report uses what we read from the front.
          </Notice>
        </View>
      )}
    </Screen>
  );
}

const s = StyleSheet.create({
  dim:       { flex: 1, backgroundColor: C.soft, alignItems: 'center', justifyContent: 'center', padding: 24 },
  popup:     { width: '100%', maxWidth: 380, backgroundColor: '#fff', borderRadius: 18, padding: 24, alignItems: 'center', gap: 10,
               borderWidth: 1, borderColor: C.line },
  popIcon:   { width: 52, height: 52, borderRadius: 26, backgroundColor: C.cautionBg, alignItems: 'center', justifyContent: 'center', marginBottom: 4 },
  popTitle:  { fontSize: 20, lineHeight: 26, fontWeight: '700', color: C.ink, textAlign: 'center' },
  head:      { flexDirection: 'row', alignItems: 'center', gap: 16, marginBottom: 18 },
  photo:     { width: 96, height: 96, borderRadius: 20, backgroundColor: '#fff' },
  input:     { marginTop: 6, fontSize: 20, fontWeight: '700', color: C.ink, backgroundColor: '#fff', borderRadius: 14,
               paddingHorizontal: 14, paddingVertical: 12, borderWidth: 2, borderColor: C.brand },
  change:    { flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 6 },
  changeTxt: { fontSize: 15, fontWeight: '700', color: C.brandDark },
  card:      { backgroundColor: '#fff', borderRadius: 20, paddingHorizontal: 16 },
  row:       { flexDirection: 'row', gap: 14, paddingVertical: 16 },
  rowLine:   { borderBottomWidth: 1, borderBottomColor: C.line },
  quickRoot: { flex: 1, backgroundColor: C.soft, alignItems: 'center', justifyContent: 'center', padding: 24 },
  quickCard: { width: '100%', maxWidth: 360, backgroundColor: '#fff', borderRadius: 18, padding: 24, alignItems: 'center', gap: 10, borderWidth: 1, borderColor: C.line },
  quickPhoto:{ width: 110, height: 110, borderRadius: 22, backgroundColor: C.soft },
  pick:      { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 14 },
  valueRow:  { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 4, flexWrap: 'wrap' },
});
