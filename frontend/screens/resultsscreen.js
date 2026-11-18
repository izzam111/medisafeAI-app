// resultsscreen.js — supplement safety report, laid out like a clean medical report. Read aloud included.
import React, { useEffect, useState } from 'react';
import { View, Text, Image, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import * as Speech from 'expo-speech';
import { Screen, Button, Notice, Chip, Icon, IconCircle, STATUS, C, T } from '../ui';
import { api, errorMessage, describeProfile } from '../config';

// What happens while the report is made, ticked off one by one
const PREP = ['Your age, sex and health', 'Dose against the NIH safe limits', 'Your reason for taking it', 'Fruits and vegetables', 'Writing your report'];
function Preparing({ name }) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setStage(i => Math.min(i + 1, PREP.length - 1)), 1800);
    return () => clearInterval(t);
  }, []);
  return (
    <View style={s.prep} accessibilityLiveRegion="polite">
      <Text style={T.title}>Preparing your report</Text>
      <Text style={[T.sub, { marginTop: 4, marginBottom: 18 }]}>Checking {name} for you.</Text>
      {PREP.map((step, i) => (
        <View key={step} style={s.prepRow}>
          {i < stage ? <Icon name="checkmark-circle" size={22} color={C.safe} />
            : i === stage ? <ActivityIndicator size="small" color={C.brand} style={{ width: 22 }} />
            : <Icon name="ellipse-outline" size={22} color={C.line} />}
          <Text style={[T.body, { color: i <= stage ? C.ink : C.faint, fontWeight: i === stage ? '600' : '400' }]}>{step}</Text>
        </View>
      ))}
      <Text style={[T.small, { marginTop: 16 }]}>This can take up to a minute.</Text>
    </View>
  );
}

const VERDICT = {
  'Safe':             { status: 'ok',      title: 'Safe for you' },
  'Use with caution': { status: 'caution', title: 'Take with care' },
  'Not safe':         { status: 'stop',    title: 'Not safe for you' },
};
const CHECK_LABEL = { ok: 'OK', caution: 'Check', stop: 'Not suitable', info: 'Check pack' };
const REASON = { helps: ['ok', 'Helps'], no: ['stop', "Won't help"], unsure: ['stop', 'Not proven'] };

const Section = ({ icon, title, children }) => (
  <View style={{ marginTop: 24 }}>
    <View style={s.sectionHead}>
      {icon ? <View style={s.secIcon}><Icon name={icon} size={18} color={C.brand} /></View> : null}
      <Text style={s.sectionTitle}>{title}</Text>
    </View>
    <View style={s.sheet}>{children}</View>
  </View>
);

const Line = ({ label, children, last }) => (
  <View style={[s.line, !last && s.lineBorder]}>
    <Text style={s.lineLabel}>{label}</Text>
    <View style={{ flex: 1 }}>{children}</View>
  </View>
);

const Bullets = ({ items, color = C.sub }) => items.map((t, i) => (
  <View key={i} style={s.li}><View style={[s.dot, { backgroundColor: color }]} /><Text style={[T.body, { flex: 1 }]}>{t}</Text></View>
));

function Nutrient({ n, last }) {
  const pct = n.percent_of_need;
  const color = n.over_limit ? C.danger : C.brand;
  const label = pct == null ? '' : pct >= 200 ? `${Math.round(pct / 100)} times your daily need` : `${pct}% of your daily need`;
  return (
    <View style={[s.nutrient, !last && s.lineBorder]}>
      <View style={{ flexDirection: 'row' }}>
        <Text style={[T.body, { flex: 1 }]}>{n.nutrient}</Text>
        <Text style={[T.h3, { color }]}>{n.per_tablet}</Text>
      </View>
      {pct != null && <View style={s.track}><View style={[s.fill, { width: `${Math.min(pct, 100)}%`, backgroundColor: color }]} /></View>}
      <Text style={[T.small, n.over_limit && { color: C.danger, fontWeight: '700' }]}>
        {label}{label ? '. ' : ''}{n.safe_limit.startsWith('No') ? 'No upper limit set.' : `Safe limit ${n.safe_limit} a day.`}
      </Text>
    </View>
  );
}

export default function ReportScreen({ route, navigation }) {
  const { savedId } = route.params;                  // set when opening a past check from Home
  const { scan, name } = route.params;
  const [data, setData]         = useState(null);
  const [error, setError]       = useState(null);
  const [speaking, setSpeaking] = useState(false);

  const load = async () => {
    setError(null); setData(null);
    try {
      if (savedId) {
        const res = await api.get(`/report/${savedId}`);
        setData(res.data);
      } else {
        const { profile, reasons } = route.params;
        const res = await api.post('/safety-report', {
          scan_id: scan.scan_id, supplement_name: name, reasons,
          age: profile.age, sex: profile.sex, periods: profile.periods,
          pregnant: !!profile.pregnant, breastfeeding: !!profile.breastfeeding,
        });
        setData(res.data);
      }
    } catch (e) {
      setError(errorMessage(e));
    }
  };
  useEffect(() => { load(); return () => Speech.stop(); }, []);

  const again = () => { Speech.stop(); navigation.reset({ index: 1, routes: [{ name: 'Home' }, { name: 'Scan' }] }); };

  if (!data) {
    return (
      <Screen title="Safety report" step={savedId ? null : 3} onBack={() => navigation.goBack()} bg={C.soft}
        footer={error ? <>
          <Button label="Scan another pack" icon="camera" onPress={again} />
          <Button label="Try again" kind="ghost" small onPress={load} />
        </> : null}>
        {error ? (
          <View style={s.loading}>
            <IconCircle name="document-text" size={84} color={C.caution} bg={C.cautionBg} />
            <Text style={[T.title, { textAlign: 'center' }]}>We can't make this report</Text>
            <Text style={[T.sub, { textAlign: 'center' }]}>{error}</Text>
            <Text style={[T.small, { textAlign: 'center', marginTop: 4 }]}>MediSafe gives no advice on products outside its data.</Text>
          </View>
        ) : (
          savedId ? (
            <View style={s.loading}>
              <ActivityIndicator size="large" color={C.brand} />
              <Text style={[T.sub, { textAlign: 'center' }]}>Opening your saved report.</Text>
            </View>
          ) : <Preparing name={name} />
        )}
      </Screen>
    );
  }

  const r = data.report;
  const profile = data.profile;
  const reasons = data.reasons || [];
  const photo = route.params.photo || data.thumb;
  const v = VERDICT[r.is_safe_to_take.verdict];
  const st = STATUS[r.is_safe_to_take.tone || v.status];
  const dose = r.recommended_dosage || {};
  const sum = dose.summary || {};
  const purpose = r.purpose_check?.results || [];
  const made = r.is_safe_to_take.checks.find(c => c.key === 'maker');

  const speak = () => {
    if (speaking) { Speech.stop(); setSpeaking(false); return; }
    const isRed = (r.is_safe_to_take.tone || v.status) === 'stop';
    const doseText = isRed ? '' : sum.doctor_only ? 'Only take this if your doctor prescribed it.'
      : `How to take it: ${sum.amount || 'the amount on the pack'}, ${sum.how_often || 'as the pack says'}, ${sum.when || 'at any time'}.`
        + (sum.short_course ? ' Use it for a short course only.' : '');
    setSpeaking(true);
    Speech.speak(`${data.product.name}. ${r.is_safe_to_take.title || v.title}. ${r.is_safe_to_take.reason} ${doseText}`,
      { language: 'en', rate: 0.9, onDone: () => setSpeaking(false), onStopped: () => setSpeaking(false) });
  };

  const ORDER = { stop: 0, caution: 1, info: 2, ok: 3 };
  // The maker is shown in the report header; the checks list is about your health.
  const checks = r.is_safe_to_take.checks.filter(c => c.key !== 'maker').sort((a, b) => ORDER[a.status] - ORDER[b.status]);
  const issues = checks.filter(c => c.status === 'stop' || c.status === 'caution').length;
  let n = 0;                                          // section numbers, only for sections that are shown
  const num = () => ++n;
  // Red result (not safe, or not for your reason): no dose or food advice, only why and what it is.
  const red = (r.is_safe_to_take.tone || v.status) === 'stop';

  return (
    <Screen title="Safety report" step={savedId ? null : 3} onBack={() => navigation.goBack()} bg={C.soft}
      footer={<>
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={{ flex: 1 }}><Button label="Home" icon="home-outline" kind="secondary" onPress={() => { Speech.stop(); navigation.popToTop(); }} /></View>
          <View style={{ flex: 1.4 }}><Button label="Scan another" icon="scan-outline" onPress={again} /></View>
        </View>
      </>}>

      {/* Report header */}
      <View style={s.sheet}>
        <View style={s.reportHead}>
          {photo ? <Image source={{ uri: photo }} style={s.photo} /> : <View style={[s.photo, s.photoEmpty]}><Icon name="medical" size={26} color={C.brand} /></View>}
          <View style={{ flex: 1 }}>
            <Text style={s.kicker}>SUPPLEMENT SAFETY REPORT</Text>
            <Text style={T.title}>{data.product.name}</Text>
            <Text style={T.small}>{new Date().toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}</Text>
          </View>
        </View>
        <Line label="Made by">
          <View style={s.inline}>
            <Text style={[T.body, { flexShrink: 1 }]}>{data.company.name || 'Not seen on the pack'}</Text>
            {made ? <Chip status={made.status} label={{ ok: data.company.status === 'verified' ? 'Genuine' : 'Official maker', caution: 'Check maker', info: data.company.status === 'brand_seen' ? 'Not verified' : 'Not seen', stop: 'Check maker' }[made.status]} /> : null}
          </View>
        </Line>
        <Line label="Checked for"><Text style={T.body}>{describeProfile(profile)}</Text></Line>
        <Line label="Reasons" last><Text style={T.body}>{reasons.length ? reasons.join(', ') : 'Not given'}</Text></Line>
      </View>

      {/* Verdict */}
      <View style={[s.verdict, { backgroundColor: st.bg, borderColor: st.color }]}>
        <View style={s.inline}>
          <Icon name={st.icon} size={40} color={st.color} />
          <View style={{ flex: 1 }}>
            <Text style={[s.verdictTitle, { color: st.color }]}>{r.is_safe_to_take.title || v.title}</Text>
            <Text style={[T.small, { color: st.color, fontWeight: '700' }]}>
              {issues ? `${issues} thing${issues > 1 ? 's' : ''} to check below` : 'No problems found for your profile'}
            </Text>
          </View>
        </View>
        <Text style={[T.body, { marginTop: 10 }]}>{r.is_safe_to_take.reason}</Text>
        <View style={s.glance}>
          {checks.map((c, i) => (
            <View key={c.key + i} style={s.glanceItem}>
              <Icon name={STATUS[c.status].icon} size={16} color={STATUS[c.status].color} />
              <Text style={s.glanceTxt}>{c.title}</Text>
            </View>
          ))}
        </View>
        <Pressable onPress={speak} style={s.speak} accessibilityRole="button">
          <Icon name={speaking ? 'stop-circle' : 'volume-high'} size={20} color={C.brandDark} />
          <Text style={s.speakTxt}>{speaking ? 'Stop reading' : 'Read aloud'}</Text>
        </Pressable>
      </View>

      {/* 1. Checks, most serious first */}
      <Section n={num()} icon="shield-checkmark" title="Safety checks">
        {checks.map((c, i) => {
          const cs = STATUS[c.status];
          return (
            <View key={c.key + i} style={[s.check, { borderLeftColor: cs.color, backgroundColor: c.status === 'ok' || c.status === 'info' ? '#fff' : cs.bg }, i < checks.length - 1 && { marginBottom: 8 }]}>
              <View style={s.checkHead}>
                <Icon name={cs.icon} size={20} color={cs.color} />
                <Text style={[T.h3, { flex: 1 }]}>{c.title}</Text>
                <Text style={[s.checkTag, { color: cs.color }]}>{c.key === 'reason' && c.status === 'stop' ? 'Not for this' : CHECK_LABEL[c.status]}</Text>
              </View>
              <Text style={[T.sub, { marginTop: 4, color: C.ink }]}>{c.text}</Text>
            </View>
          );
        })}
      </Section>

      {red ? null : <>
      {/* 2. Dose */}
      <Section n={num()} icon="time" title="How to take it">
        {sum.doctor_only ? (
          <View style={[s.alert, { backgroundColor: C.dangerBg, borderColor: C.danger }]}>
            <Icon name="medkit" size={24} color={C.danger} />
            <Text style={[T.h3, { color: C.danger, flex: 1 }]}>Only take this if your doctor prescribed it.</Text>
          </View>
        ) : (
          <>
            <View style={s.tiles}>
              {[['pill', 'Amount', sum.amount || 'As on the pack'], ['repeat', 'How often', sum.how_often || 'As on the pack'],
                ['restaurant', 'When', sum.when || 'Any time']].map(([icon, label, value]) => (
                <View key={label} style={s.tile}>
                  <Icon name={icon === 'pill' ? 'ellipse' : icon} size={18} color={C.brand} />
                  <Text style={T.small}>{label}</Text>
                  <Text style={s.tileValue}>{value}</Text>
                </View>
              ))}
            </View>
            {sum.usual ? <Text style={[T.small, { marginTop: 8 }]}>We couldn't read the directions, so this is the usual dose for this kind of supplement. Check your pack.</Text> : null}
            {sum.short_course ? (
              <View style={[s.alert, { backgroundColor: C.cautionBg, borderColor: C.caution, marginTop: 10 }]}>
                <Icon name="calendar" size={20} color={C.caution} />
                <Text style={[T.sub, { color: C.ink, flex: 1 }]}><Text style={{ fontWeight: '800', color: C.caution }}>Short course only. </Text>Not for daily use over many months unless a doctor advises.</Text>
              </View>
            ) : null}
          </>
        )}
      </Section>

      {/* 3. Strength */}
      {dose.nutrients?.length ? (
        <Section n={num()} icon="flask" title="What's in one tablet">
          {dose.strength_source === 'typical' ? <Text style={[T.small, { marginBottom: 6 }]}>Usual strength of this product.</Text> : null}
          {dose.nutrients.map((x, i) => <Nutrient key={x.nutrient} n={x} last={i === dose.nutrients.length - 1} />)}
          {dose.steps?.length > 1 ? (<><Text style={[T.h3, s.sub]}>Tips</Text><Bullets items={dose.steps.slice(1)} /></>) : null}
          {dose.note ? <Text style={[T.sub, { marginTop: 6 }]}>{dose.note}</Text> : null}
        </Section>
      ) : null}

      {/* 4. Food and timing */}
      <Section n={num()} icon="nutrition" title="Food and timing">
        {!sum.doctor_only ? (
          <View style={[s.alert, { backgroundColor: C.tint, borderColor: C.brand, marginBottom: 10 }]}>
            <Icon name="restaurant" size={20} color={C.brandDark} />
            <Text style={[T.sub, { color: C.ink, flex: 1 }]}>
              <Text style={{ fontWeight: '800' }}>Take it {sum.when || 'at any time of day'}. </Text>
              {/meal|food/.test(sum.when || '') ? 'Taking it with food also helps avoid an upset stomach.' : ''}
            </Text>
          </View>
        ) : null}
        <View style={[s.foodBox, { backgroundColor: C.safeBg, borderColor: C.safe }]}>
          <View style={s.inline}><Icon name="leaf" size={20} color={C.safe} /><Text style={[T.h3, { color: C.safe }]}>Fruits and vegetables that help</Text></View>
          {r.recommended_foods.length ? r.recommended_foods.map((f, i) => (
            <View key={i} style={[s.foodRow, i > 0 && s.foodLine]}>
              <Text style={s.foodName}>{f.food}</Text>
              <Text style={T.small}>{f.reason}</Text>
            </View>
          )) : <Text style={[T.sub, { marginTop: 6 }]}>None needed. Any fresh fruit or vegetable you normally eat is fine.</Text>}
        </View>
        {r.foods_to_avoid.length ? (
          <View style={[s.foodBox, { backgroundColor: C.dangerBg, borderColor: C.danger, marginTop: 10 }]}>
            <View style={s.inline}><Icon name="hourglass" size={20} color={C.danger} /><Text style={[T.h3, { color: C.danger, flex: 1 }]}>Don't eat within 2 hours of your tablet</Text></View>
            <Text style={[T.small, { marginTop: 4 }]}>These are still healthy. Just eat them at a different time of day.</Text>
            {r.foods_to_avoid.map((f, i) => (
              <View key={i} style={[s.foodRow, s.foodLine]}>
                <Text style={s.foodName}>{f.food}</Text>
                <Text style={T.small}>{f.reason}</Text>
              </View>
            ))}
          </View>
        ) : (
          <View style={[s.inline, { marginTop: 12 }]}>
            <Icon name="checkmark-circle" size={20} color={C.safe} />
            <Text style={[T.sub, { flex: 1 }]}>No fruit or vegetable gets in the way of this supplement.</Text>
          </View>
        )}
      </Section>

      </>}

      {/* 5. Reasons */}
      {purpose.length ? (
        <Section n={num()} icon="help-circle" title="Does it help with your reason?">
          {purpose.map((p, i) => (
            <View key={p.reason} style={[s.reasonRow, i < purpose.length - 1 && s.lineBorder]}>
              <View style={s.checkHead}>
                <Icon name={STATUS[REASON[p.result][0]].icon} size={20} color={STATUS[REASON[p.result][0]].color} />
                <Text style={[T.h3, { flex: 1 }]}>{p.reason}</Text>
                <Text style={[s.checkTag, { color: STATUS[REASON[p.result][0]].color }]}>{REASON[p.result][1]}</Text>
              </View>
              <Text style={[T.sub, { marginTop: 4 }]}>{p.text}</Text>
            </View>
          ))}
          {r.purpose_check.ai_note ? <Text style={[T.sub, { marginTop: 10 }]}>{r.purpose_check.ai_note}</Text> : null}
        </Section>
      ) : null}

      {/* 6. About */}
      <Section n={num()} icon="book" title="About this supplement">
        {r.actual_usage ? (
          <View style={[s.aboutBox, { backgroundColor: C.tint }]}>
            <View style={s.inline}><Icon name="medical" size={18} color={C.brandDark} /><Text style={[s.label, { marginBottom: 0, color: C.brandDark }]}>USED FOR</Text></View>
            <Text style={[T.body, { marginTop: 6 }]}>{r.actual_usage}</Text>
          </View>
        ) : null}
        {r.facts ? (
          <View style={[s.aboutBox, { backgroundColor: C.soft }]}>
            <View style={s.inline}><Icon name="bulb" size={18} color={C.sub} /><Text style={[s.label, { marginBottom: 0 }]}>GOOD TO KNOW</Text></View>
            <Text style={[T.body, { marginTop: 6 }]}>{r.facts}</Text>
          </View>
        ) : null}
        {r.benefits?.length ? (
          <View style={s.aboutList}>
            <Text style={[s.label, { color: C.safe }]}>BENEFITS</Text>
            {r.benefits.map((t, i) => (
              <View key={i} style={s.aboutItem}><Icon name="checkmark-circle" size={18} color={C.safe} /><Text style={[T.body, { flex: 1 }]}>{t}</Text></View>
            ))}
          </View>
        ) : null}
        {r.side_effects?.length ? (
          <View style={s.aboutList}>
            <Text style={[s.label, { color: C.caution }]}>POSSIBLE SIDE EFFECTS</Text>
            {r.side_effects.map((t, i) => (
              <View key={i} style={s.aboutItem}><Icon name="alert-circle" size={18} color={C.caution} /><Text style={[T.body, { flex: 1 }]}>{t}</Text></View>
            ))}
          </View>
        ) : null}
        {r.notes?.length ? (
          <View style={s.aboutList}>
            <Text style={s.label}>NOTES</Text>
            {r.notes.map((t, i) => (
              <View key={i} style={s.aboutItem}><Icon name="information-circle" size={18} color={C.sub} /><Text style={[T.body, { flex: 1 }]}>{t}</Text></View>
            ))}
          </View>
        ) : null}
      </Section>

      <View style={s.sources}>
        <Icon name="information-circle-outline" size={18} color={C.sub} />
        <Text style={[T.small, { flex: 1 }]}>
          Sources: daily needs and safe limits from the NIH Office of Dietary Supplements; fruit and vegetable advice from
          documented interactions and our trained model. Follow the directions on the pack, or your doctor's advice.
        </Text>
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  loading:      { alignItems: 'center', gap: 16, paddingTop: 90 },
  prep:         { backgroundColor: '#fff', borderRadius: 14, borderWidth: 1, borderColor: C.line, padding: 20, marginTop: 20 },
  prepRow:      { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 8 },
  sheet:        { backgroundColor: '#fff', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: C.line },
  reportHead:   { flexDirection: 'row', alignItems: 'center', gap: 14, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: C.line },
  kicker:       { fontSize: 12, fontWeight: '800', letterSpacing: 1, color: C.brand, marginBottom: 2 },
  photo:        { width: 64, height: 64, borderRadius: 14, backgroundColor: C.soft },
  photoEmpty:   { alignItems: 'center', justifyContent: 'center', backgroundColor: C.tint },
  line:         { flexDirection: 'row', paddingVertical: 12, gap: 12 },
  lineBorder:   { borderBottomWidth: 1, borderBottomColor: C.line },
  lineLabel:    { width: 96, fontSize: 15, color: C.sub, paddingTop: 2 },
  inline:       { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  verdict:      { borderRadius: 14, padding: 18, marginTop: 14, borderWidth: 1.5 },
  verdictTitle: { fontSize: 26, lineHeight: 31, fontWeight: '800' },
  glance:       { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 14 },
  glanceItem:   { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: 'rgba(255,255,255,0.8)', borderRadius: 14,
                  paddingHorizontal: 10, paddingVertical: 6 },
  glanceTxt:    { fontSize: 14, fontWeight: '600', color: C.ink },
  speak:        { flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start', backgroundColor: '#fff',
                  borderRadius: 10, borderWidth: 1, borderColor: C.line, paddingHorizontal: 14, paddingVertical: 9, marginTop: 14 },
  speakTxt:     { fontSize: 15, fontWeight: '600', color: C.brandDark },
  sectionHead:  { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8, marginLeft: 2 },
  secIcon:      { width: 32, height: 32, borderRadius: 10, backgroundColor: C.tint, alignItems: 'center', justifyContent: 'center' },
  num:          { width: 28, height: 28, borderRadius: 14, backgroundColor: C.brand, alignItems: 'center', justifyContent: 'center' },
  numTxt:       { color: '#fff', fontWeight: '800', fontSize: 15 },
  sectionTitle: { flex: 1, fontSize: 19, fontWeight: '800', color: C.ink },
  check:        { borderLeftWidth: 5, borderRadius: 12, paddingVertical: 12, paddingHorizontal: 12, borderWidth: 1, borderColor: C.line },
  checkHead:    { flexDirection: 'row', alignItems: 'center', gap: 8 },
  checkTag:     { fontSize: 13, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.5 },
  alert:        { flexDirection: 'row', alignItems: 'center', gap: 10, borderRadius: 14, borderWidth: 1, padding: 12 },
  tiles:        { flexDirection: 'row', gap: 8 },
  tile:         { flex: 1, backgroundColor: C.soft, borderRadius: 14, padding: 12, gap: 4 },
  tileValue:    { fontSize: 16, lineHeight: 21, fontWeight: '800', color: C.ink },
  foodBox:      { borderRadius: 14, borderWidth: 1, padding: 14 },
  foodRow:      { paddingVertical: 9 },
  foodLine:     { borderTopWidth: 1, borderTopColor: 'rgba(0,0,0,0.07)' },
  foodName:     { fontSize: 17, fontWeight: '800', color: C.ink, marginBottom: 2 },
  reasonRow:    { paddingVertical: 12 },
  label:        { fontSize: 12, fontWeight: '800', letterSpacing: 1, color: C.sub, marginBottom: 6 },
  sub:          { marginTop: 14, marginBottom: 6 },
  li:           { flexDirection: 'row', gap: 10, marginBottom: 6, alignItems: 'flex-start' },
  dot:          { width: 8, height: 8, borderRadius: 4, marginTop: 9 },
  nutrient:     { paddingVertical: 10, gap: 6 },
  track:        { height: 8, borderRadius: 4, backgroundColor: C.line, overflow: 'hidden' },
  fill:         { height: '100%', borderRadius: 4 },
  aboutBox:     { borderRadius: 14, padding: 14, marginBottom: 10 },
  aboutList:    { marginTop: 8, marginBottom: 4 },
  aboutItem:    { flexDirection: 'row', gap: 10, alignItems: 'flex-start', marginBottom: 8, paddingTop: 2 },
  sources:      { flexDirection: 'row', gap: 8, marginTop: 20, paddingHorizontal: 4 },
});
