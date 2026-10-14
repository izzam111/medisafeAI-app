// resultsscreen.js — MediSafe AI — FINAL BEAUTIFUL VERSION
// Everything visible. Nothing hidden. Smooth. Professional. Easy to read.

import React, { useEffect, useState, useRef } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, Image,
  StyleSheet, StatusBar, ActivityIndicator,
  Platform, SafeAreaView, Animated
} from 'react-native';
import axios from 'axios';

const API_BASE = 'http://172.21.17.231:8000'; 
const api = axios.create({ timeout: 15000 });

const C = {
  navy:     '#0D1B3E',
  navyMid:  '#1A3A7A',
  blue:     '#4A9FFF',
  bg:       '#F0F4FA',
  card:     '#FFFFFF',
  border:   '#E2E8F4',
  muted:    '#94A3B8',
  text:     '#0F172A',
  sub:      '#475569',
  green:    '#059669',
  greenBg:  '#ECFDF5',
  greenBdr: '#34D399',
  amber:    '#D97706',
  amberBg:  '#FFFBEB',
  amberBdr: '#FCD34D',
  red:      '#DC2626',
  redBg:    '#FEF2F2',
  redBdr:   '#FECACA',
};

// ─────────────────────────────────────────────────────────────────────────────
// FOOD CARD — always shows reason, tap for extra detail
// ─────────────────────────────────────────────────────────────────────────────
const FoodCard = ({ item, isAvoid }) => {
  const [expanded, setExpanded] = useState(false);
  const col = isAvoid ? C.red   : C.green;
  const bg  = isAvoid ? '#FFF5F5' : '#F0FFF8';
  const bdr = isAvoid ? C.redBdr : C.greenBdr;

  return (
    <TouchableOpacity
      onPress={() => setExpanded(p => !p)}
      activeOpacity={0.85}
      style={[fc.card, { backgroundColor: bg, borderColor: expanded ? col : bdr }]}
    >
      {/* Header row */}
      <View style={fc.header}>
        <View style={[fc.iconBox, { backgroundColor: isAvoid ? '#FFE4E4' : '#D1FAE5' }]}>
          <Text style={fc.icon}>{isAvoid ? '🚫' : '✅'}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={[fc.foodName, { color: col }]}>{item.food}</Text>
          <Text style={[fc.tag, { color: col }]}>
            {isAvoid ? 'Tap to see why to avoid this' : 'Tap to see why this helps'}
          </Text>
        </View>
        <View style={[fc.detailBtn, { backgroundColor: col }]}>
          <Text style={fc.detailBtnTxt}>{expanded ? '▲ Less' : '▼ Why?'}</Text>
        </View>
      </View>

      {/* Short summary — always visible */}
      <Text style={fc.summary} numberOfLines={expanded ? undefined : 2}>
        {item.reason}
      </Text>

      {/* Detail — shown when tapped */}
      {expanded && (
        <View style={[fc.detailBox, { borderTopColor: bdr }]}>
          <View style={[fc.actionRow, { backgroundColor: isAvoid ? '#FFF0F0' : '#F0FFF4' }]}>
            <Text style={{ fontSize: 22, marginTop: 2 }}>{isAvoid ? '⏰' : '🍽️'}</Text>
            <View style={{ flex: 1 }}>
              <Text style={[fc.actionTitle, { color: col }]}>
                {isAvoid ? 'What you should do' : 'How to get the best result'}
              </Text>
              <Text style={fc.actionBody}>
                {isAvoid
                  ? `Wait at least 2 hours between taking your supplement and eating or drinking ${item.food}. This gives your body time to absorb the supplement properly.`
                  : `Eat ${item.food} just before or with your supplement. The nutrients in it help your body absorb the supplement much more effectively.`
                }
              </Text>
            </View>
          </View>
        </View>
      )}
    </TouchableOpacity>
  );
};

const fc = StyleSheet.create({
  card:       { borderRadius:16, borderWidth:2, padding:14, marginBottom:10 },
  header:     { flexDirection:'row', alignItems:'flex-start', gap:12, marginBottom:8 },
  iconBox:    { width:40, height:40, borderRadius:12, alignItems:'center', justifyContent:'center' },
  icon:       { fontSize:20 },
  foodName:   { fontSize:16, fontWeight:'800', marginBottom:2 },
  tag:        { fontSize:11.5, fontWeight:'600' },
  detailBtn:  { paddingHorizontal:12, paddingVertical:6, borderRadius:20 },
  detailBtnTxt:{ color:'#fff', fontSize:12, fontWeight:'700' },
  summary:    { fontSize:13.5, color:C.sub, lineHeight:20, marginBottom:4 },
  detailBox:  { marginTop:12, paddingTop:12, borderTopWidth:1 },
  actionRow:  { flexDirection:'row', alignItems:'flex-start', gap:10, borderRadius:12, padding:12 },
  actionIcon: { fontSize:22, marginTop:2 },
  actionTitle:{ fontSize:13, fontWeight:'700', marginBottom:4 },
  actionBody: { fontSize:13, color:C.text, lineHeight:20 },
});

// ─────────────────────────────────────────────────────────────────────────────
// BENEFIT / WARNING ROW
// ─────────────────────────────────────────────────────────────────────────────
const InfoRow = ({ text, type }) => {
  const cfg = {
    benefit: { bg:'#F0FFF8', border:'#A7F3D0', dot:'#059669', label:'Benefit' },
    warning: { bg:'#FFFBEB', border:'#FDE68A', dot:'#D97706', label:'Warning' },
  }[type];
  return (
    <View style={[ir.row, { backgroundColor: cfg.bg, borderColor: cfg.border }]}>
      <View style={[ir.dot, { backgroundColor: cfg.dot }]} />
      <Text style={ir.txt}>{text}</Text>
    </View>
  );
};

const ir = StyleSheet.create({
  row: { flexDirection:'row', alignItems:'flex-start', gap:10, borderRadius:10,
         borderWidth:1.5, padding:10, marginBottom:6 },
  dot: { width:8, height:8, borderRadius:4, marginTop:5, flexShrink:0 },
  txt: { flex:1, fontSize:13.5, color:C.sub, lineHeight:20 },
});

// ─────────────────────────────────────────────────────────────────────────────
// SUPPLEMENT CARD — full visible layout, nothing hidden
// ─────────────────────────────────────────────────────────────────────────────
const SupCard = ({ supp, purpose, verdict, index, total, imageUri, allImages }) => {
  const fade  = useRef(new Animated.Value(0)).current;
  const slide = useRef(new Animated.Value(24)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(fade,  { toValue:1, duration:600, delay:index*180, useNativeDriver:true }),
      Animated.timing(slide, { toValue:0, duration:500, delay:index*180, useNativeDriver:true }),
    ]).start();
  }, []);

  if (supp.error) {
    return (
      <Animated.View style={[su.card, { opacity:fade, borderLeftColor:C.red, borderLeftWidth:5 }]}>
        <Text style={{ fontSize:16, fontWeight:'700', color:C.red, marginBottom:6 }}>
          ❌  Supplement Not Found: {supp.name}
        </Text>
        <Text style={{ fontSize:13.5, color:C.sub, lineHeight:21 }}>{supp.message}</Text>
        <Text style={{ fontSize:13, color:C.muted, marginTop:8 }}>
          💡 Try scanning again more clearly, or type the name directly.
        </Text>
      </Animated.View>
    );
  }

  const accent = supp.color || C.blue;

  // Verdict setup
  const VERDICTS = {
    'Valid':           { bg:C.greenBg, border:C.greenBdr, color:C.green, icon:'✅', title:'Safe for This Purpose', msg: verdict?.explanation || 'This is a recognised and appropriate use of this supplement. You can take it for this reason.' },
    'Partially Valid': { bg:C.amberBg, border:C.amberBdr, color:C.amber, icon:'⚠️', title:'Check With Your Doctor First', msg:'This supplement is not specifically designed for this purpose. It may give some benefit, but please speak to your doctor before using it for this reason.' },
    'Not Valid':       { bg:C.redBg,   border:C.redBdr,   color:C.red,   icon:'🚫', title:'Not Suitable for This Purpose', msg: verdict?.explanation || 'This supplement is not designed for the reason you gave. Please see your doctor to find the right supplement for your needs.' },
  };
  const VD = verdict ? VERDICTS[verdict.validity] : null;
  const hasPurpose = purpose && purpose !== 'General use / no specific reason';

  return (
    <Animated.View style={[su.card, { opacity:fade, transform:[{translateY:slide}] }]}>

      {/* ═══ TOP BAR — supplement name ═══ */}
      <View style={[su.topBar, { backgroundColor: accent }]}>
        {total > 1 && (
          <View style={su.numCircle}>
            <Text style={su.numTxt}>{index + 1}</Text>
          </View>
        )}
        <View style={{ flex: 1 }}>
          <Text style={su.suppName}>{supp.name}</Text>
          <Text style={su.suppScientific} numberOfLines={1}>{supp.full_name}</Text>
        </View>
        <View style={su.categoryTag}>
          <Text style={su.categoryTxt}>{supp.category_label || 'Supplement'}</Text>
        </View>
      </View>

      {/* Scanned image — show relevant image for each supplement */}
      {(allImages && allImages[index]) ? (
        <View style={su.imageWrap}>
          <Image source={{ uri: allImages[index] }} style={su.image} resizeMode="cover" />
          <View style={su.imageOverlay}>
            <Text style={su.imageOverlayTxt}>📷  Scanned Label</Text>
          </View>
        </View>
      ) : (imageUri && index === 0) ? (
        <View style={su.imageWrap}>
          <Image source={{ uri: imageUri }} style={su.image} resizeMode="cover" />
          <View style={su.imageOverlay}>
            <Text style={su.imageOverlayTxt}>📷  Scanned Label</Text>
          </View>
        </View>
      ) : null}

      <View style={su.body}>

        {/* ═══ YOUR REASON ═══ */}
        {hasPurpose && (
          <View style={su.purposeBox}>
            <Text style={su.purposeEmoji}>💬</Text>
            <View style={{ flex: 1 }}>
              <Text style={su.purposeLabel}>YOUR REASON FOR TAKING THIS</Text>
              <Text style={su.purposeText}>"{purpose}"</Text>
            </View>
          </View>
        )}

        {/* ═══ SAFETY VERDICT ═══ */}
        {VD ? (
          <View style={[su.verdictBox, { backgroundColor:VD.bg, borderColor:VD.border }]}>
            <View style={[su.verdictTopBar, { backgroundColor:VD.color }]}>
              <Text style={su.verdictTopBarTxt}>
                {VD.icon}  IS IT SAFE?  {VD.icon}
              </Text>
            </View>
            <View style={su.verdictContent}>
              <Text style={[su.verdictTitle, { color:VD.color }]}>{VD.title}</Text>
              <Text style={su.verdictMsg}>{VD.msg}</Text>
            </View>
          </View>
        ) : (
          <View style={[su.verdictBox, { backgroundColor:'#EFF6FF', borderColor:'#BFDBFE' }]}>
            <View style={[su.verdictTopBar, { backgroundColor:C.blue }]}>
              <Text style={su.verdictTopBarTxt}>ℹ️  GENERAL SAFETY INFORMATION</Text>
            </View>
            <View style={su.verdictContent}>
              <Text style={[su.verdictTitle, { color:'#1D4ED8' }]}>Showing General Information</Text>
              <Text style={su.verdictMsg}>
                You did not give a reason for taking this supplement, so we are showing general safety and food interaction information.
              </Text>
            </View>
          </View>
        )}

        {/* ═══ WHAT IS THIS SUPPLEMENT? ═══ */}
        <View style={su.section}>
          <View style={[su.sectionHead, { backgroundColor: accent }]}>
            <Text style={su.sectionHeadTxt}>🏥  WHAT IS THIS SUPPLEMENT FOR?</Text>
          </View>
          <View style={su.sectionBody}>
            <Text style={su.bodyTxt}>{supp.used_for}</Text>
          </View>
        </View>

        {/* ═══ BEST KNOWN FOR ═══ */}
        <View style={su.knownBox}>
          <Text style={su.knownStar}>⭐</Text>
          <View style={{ flex: 1 }}>
            <Text style={su.knownLabel}>MOST COMMONLY USED FOR</Text>
            <Text style={su.knownTxt}>{supp.best_known_for}</Text>
          </View>
        </View>

        {/* ═══ BENEFITS ═══ */}
        <View style={su.section}>
          <View style={[su.sectionHead, { backgroundColor: C.green }]}>
            <Text style={su.sectionHeadTxt}>✅  BENEFITS OF TAKING THIS</Text>
          </View>
          <View style={su.sectionBody}>
            {(supp.pros || []).map((p, i) => (
              <InfoRow key={i} text={p} type="benefit" />
            ))}
          </View>
        </View>

        {/* ═══ SIDE EFFECTS ═══ */}
        <View style={su.section}>
          <View style={[su.sectionHead, { backgroundColor: C.amber }]}>
            <Text style={su.sectionHeadTxt}>⚠️  SIDE EFFECTS & WARNINGS</Text>
          </View>
          <View style={su.sectionBody}>
            {(supp.cons || []).map((c, i) => (
              <InfoRow key={i} text={c} type="warning" />
            ))}
          </View>
        </View>

        {/* ═══ FOOD GUIDE ═══ */}
        <View style={su.section}>
          {/* Foods that help */}
          <View style={[su.sectionHead, { backgroundColor: C.green }]}>
            <Text style={su.sectionHeadTxt}>🥗  FOODS THAT HELP — Eat These</Text>
          </View>
          <View style={su.sectionBody}>
            <Text style={su.foodGuideSub}>
              These fruits and vegetables make your supplement work better. They help your body absorb it more effectively.
            </Text>
            {supp.foods_to_eat?.length > 0
              ? supp.foods_to_eat.map((f, i) => <FoodCard key={i} item={f} isAvoid={false} />)
              : <Text style={su.noFoodTxt}>No specific foods needed — this supplement works well with any normal meal.</Text>
            }
          </View>
        </View>

        <View style={su.section}>
          {/* Foods to avoid */}
          <View style={[su.sectionHead, { backgroundColor: C.red }]}>
            <Text style={su.sectionHeadTxt}>🚫  FOODS TO AVOID — These Block It</Text>
          </View>
          <View style={su.sectionBody}>
            <Text style={su.foodGuideSub}>
              These foods reduce how well your supplement is absorbed. Take your supplement separately from these.
            </Text>
            {supp.foods_to_avoid?.length > 0
              ? supp.foods_to_avoid.map((f, i) => <FoodCard key={i} item={f} isAvoid={true} />)
              : <Text style={su.noFoodTxt}>No foods to avoid — safe to take with any meal.</Text>
            }
          </View>
        </View>

        <Text style={su.interactHint}>
          👆 Tap the "Why?" button on any food above to see the full explanation
        </Text>

      </View>
    </Animated.View>
  );
};

const su = StyleSheet.create({
  card:         { backgroundColor:C.card, borderRadius:22, marginBottom:22,
                  shadowColor:'#000', shadowOffset:{width:0,height:4},
                  shadowOpacity:0.10, shadowRadius:14, elevation:6 },

  topBar:       { borderTopLeftRadius:22, borderTopRightRadius:22,
                  padding:18, flexDirection:'row', alignItems:'flex-start', gap:12 },
  numCircle:    { width:36, height:36, borderRadius:18,
                  backgroundColor:'rgba(255,255,255,0.22)',
                  alignItems:'center', justifyContent:'center' },
  numTxt:       { color:'#fff', fontSize:15, fontWeight:'900' },
  suppName:     { fontSize:22, fontWeight:'900', color:'#fff', lineHeight:28 },
  suppScientific:{ fontSize:12, color:'rgba(255,255,255,0.65)', marginTop:3 },
  categoryTag:  { backgroundColor:'rgba(255,255,255,0.18)',
                  paddingHorizontal:10, paddingVertical:5, borderRadius:12, marginTop:2 },
  categoryTxt:  { fontSize:10.5, color:'#fff', fontWeight:'800' },

  imageWrap:    { position:'relative' },
  image:        { width:'100%', height:180 },
  imageOverlay: { position:'absolute', bottom:0, left:0, right:0,
                  backgroundColor:'rgba(10,22,40,0.6)',
                  paddingHorizontal:14, paddingVertical:7 },
  imageOverlayTxt:{ color:'#fff', fontSize:12, fontWeight:'600' },

  body:         { padding:16 },

  purposeBox:   { flexDirection:'row', alignItems:'flex-start', gap:12,
                  backgroundColor:'#EEF2FF', borderRadius:14, padding:14,
                  borderWidth:1.5, borderColor:'#C7D2FE', marginBottom:14 },
  purposeEmoji: { fontSize:24, marginTop:1 },
  purposeLabel: { fontSize:10, fontWeight:'900', color:'#4338CA',
                  letterSpacing:0.7, marginBottom:5 },
  purposeText:  { fontSize:15, color:'#1E1B4B', fontWeight:'600',
                  fontStyle:'italic', lineHeight:22 },

  verdictBox:   { borderRadius:18, borderWidth:2, marginBottom:18, overflow:'hidden' },
  verdictTopBar:{ paddingVertical:10, paddingHorizontal:16, alignItems:'center' },
  verdictTopBarTxt:{ color:'#fff', fontSize:13, fontWeight:'900', letterSpacing:0.8 },
  verdictContent:{ padding:16 },
  verdictTitle: { fontSize:18, fontWeight:'900', marginBottom:8 },
  verdictMsg:   { fontSize:14, color:C.sub, lineHeight:22 },

  section:      { marginBottom:18 },
  sectionHead:  { borderTopLeftRadius:14, borderTopRightRadius:14,
                  paddingHorizontal:14, paddingVertical:11 },
  sectionHeadTxt:{ color:'#fff', fontSize:13, fontWeight:'900', letterSpacing:0.3 },
  sectionBody:  { backgroundColor:'#FAFBFF', borderBottomLeftRadius:14,
                  borderBottomRightRadius:14, borderWidth:1.5, borderTopWidth:0,
                  borderColor:C.border, padding:14 },
  bodyTxt:      { fontSize:14.5, color:C.text, lineHeight:23 },

  knownBox:     { flexDirection:'row', alignItems:'flex-start', gap:12,
                  backgroundColor:'#FFFBEB', borderRadius:16, padding:14,
                  borderWidth:2, borderColor:'#FDE68A', marginBottom:18 },
  knownStar:    { fontSize:24, marginTop:1 },
  knownLabel:   { fontSize:10, fontWeight:'900', color:'#92400E',
                  letterSpacing:0.7, marginBottom:5 },
  knownTxt:     { fontSize:15, color:'#78350F', lineHeight:22,
                  fontStyle:'italic', fontWeight:'500' },

  foodGuideSub: { fontSize:13.5, color:C.muted, marginBottom:12,
                  lineHeight:20, fontStyle:'italic' },
  noFoodTxt:    { fontSize:14, color:C.muted, fontStyle:'italic', lineHeight:21 },
  interactHint: { fontSize:12, color:C.muted, textAlign:'center',
                  marginTop:4, fontStyle:'italic' },
});

// ─────────────────────────────────────────────────────────────────────────────
// MAIN SCREEN
// ─────────────────────────────────────────────────────────────────────────────
export default function ResultsScreen({ route, navigation }) {
  const {
    scannedText        = '',
    imageUri           = null,
    supplementName     = '',
    userPurpose        = '',
    allSupplementNames = [],
    allPurposes        = [],
    allImages          = [],
  } = route.params || {};

  const [data,     setData]     = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [verdicts, setVerdicts] = useState({});

  useEffect(() => { fetchAll(); }, []);

  const fetchAll = async () => {
    try {
      setLoading(true); setError(null); setVerdicts({});

      const names = [];
      if (allSupplementNames?.length > 0)
        allSupplementNames.forEach(n => {
          if (n?.trim() && n !== 'Unknown Supplement') names.push(n.trim());
        });
      if (!names.length && supplementName?.trim() && supplementName !== 'Unknown Supplement')
        names.push(supplementName.trim());
      if (!names.length && scannedText?.trim()) {
        try {
          const lu = await api.post(`${API_BASE}/supplement-lookup`,
            { name: scannedText }, { timeout: 8000 });
          if (lu.data?.matched) names.push(lu.data.matched);
          else if (lu.data?.suggestions?.length) names.push(lu.data.suggestions[0]);
        } catch (_) {}
      }
      if (!names.length && scannedText?.trim())
        names.push(scannedText.trim().split(' ').slice(0, 3).join(' '));
      if (!names.length) {
        setError('Could not find the supplement. Please go back and try again.');
        setLoading(false); return;
      }

      let res;
      try {
        res = await api.post(`${API_BASE}/analyze-supplements`, {
          supplements: names,
          purpose: allPurposes?.[0] || userPurpose || '',
        }, { timeout: 15000 });
      } catch (e) {
        setError(e.code === 'ECONNABORTED'
          ? `Timed out. Is the server running? Check IP: ${API_BASE}`
          : `Cannot connect: ${e.message}`);
        setLoading(false); return;
      }

      setData(res.data);
      setLoading(false);

      // Run purpose validation for each supplement after results show
      const newV = {};
      for (let i = 0; i < names.length; i++) {
        const p = allPurposes?.[i] || (i === 0 ? userPurpose : '') || '';
        if (!p || p === 'General use / no specific reason') continue;
        try {
          const pv = await api.post(`${API_BASE}/validate-purpose`,
            { supplement_name: names[i], user_purpose: p },
            { timeout: 8000 });
          if (pv.data?.validity) newV[names[i]] = pv.data;
        } catch (_) {}
      }
      if (Object.keys(newV).length) setVerdicts(newV);

    } catch (e) {
      setError(e?.message || 'Something went wrong. Please try again.');
      setLoading(false);
    }
  };

  // ── Loading ───────────────────────────────────────────────────────────────
  if (loading) return (
    <View style={ms.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.navy} />
      <SafeAreaView style={{ backgroundColor: C.navy }}>
        <View style={ms.header}>
          <View style={{ width: 60 }} />
          <Text style={ms.headerTxt}>Safety Report</Text>
          <View style={{ width: 60 }} />
        </View>
      </SafeAreaView>
      <View style={ms.center}>
        <ActivityIndicator size="large" color={C.blue} />
        <Text style={ms.loadTitle}>Checking Your Supplement</Text>
        <Text style={ms.loadSub}>
          Looking up food interactions and preparing your personalised safety report. This takes just a moment…
        </Text>
      </View>
      <SafeAreaView style={{ backgroundColor: C.card }}>
        <View style={ms.footer}>
          <Text style={ms.footerTxt}>⚕️ For information only · Always ask your doctor</Text>
        </View>
      </SafeAreaView>
    </View>
  );

  // ── Error ─────────────────────────────────────────────────────────────────
  if (error || !data) return (
    <View style={ms.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.navy} />
      <SafeAreaView style={{ backgroundColor: C.navy }}>
        <View style={ms.header}>
          <TouchableOpacity style={ms.backBtn} onPress={() => navigation.goBack()}>
            <Text style={ms.backIcon}>‹</Text><Text style={ms.backTxt}>Back</Text>
          </TouchableOpacity>
          <Text style={ms.headerTxt}>Safety Report</Text>
          <View style={{ width: 60 }} />
        </View>
      </SafeAreaView>
      <View style={ms.center}>
        <Text style={{ fontSize: 54, marginBottom: 12 }}>📡</Text>
        <Text style={ms.loadTitle}>Could Not Connect</Text>
        <Text style={ms.loadSub}>{error}</Text>
        <View style={ms.helpBox}>
          <Text style={ms.helpTitle}>How to fix this:</Text>
          <Text style={ms.helpTxt}>
            {'1. Run ipconfig on your laptop\n2. Find your WiFi IPv4 address\n3. Update line 9 in resultsscreen.js\n4. Make sure the server is running\n5. Both phone and laptop on same WiFi'}
          </Text>
        </View>
        <TouchableOpacity style={ms.btn} onPress={fetchAll}>
          <Text style={ms.btnTxt}>🔄  Try Again</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[ms.btn, { backgroundColor: C.muted, marginTop: 8 }]}
          onPress={() => navigation.goBack()}
        >
          <Text style={ms.btnTxt}>← Go Back</Text>
        </TouchableOpacity>
      </View>
      <SafeAreaView style={{ backgroundColor: C.card }}>
        <View style={ms.footer}>
          <Text style={ms.footerTxt}>⚕️ For information only · Always ask your doctor</Text>
        </View>
      </SafeAreaView>
    </View>
  );

  // ── Results ───────────────────────────────────────────────────────────────
  const supps = data.supplements || [];

  return (
    <View style={ms.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.navy} />
      <SafeAreaView style={{ backgroundColor: C.navy }}>
        <View style={ms.header}>
          <TouchableOpacity style={ms.backBtn} onPress={() => navigation.goBack()}>
            <Text style={ms.backIcon}>‹</Text><Text style={ms.backTxt}>Back</Text>
          </TouchableOpacity>
          <Text style={ms.headerTxt}>Safety Report</Text>
          <View style={{ width: 60 }} />
        </View>
      </SafeAreaView>

      <ScrollView
        style={ms.scroll}
        contentContainerStyle={ms.content}
        showsVerticalScrollIndicator={false}
      >
        {/* One card per supplement */}
        {supps.map((supp, i) => (
          <SupCard
            key={i}
            supp={supp}
            purpose={allPurposes?.[i] || (i === 0 ? userPurpose : '') || ''}
            verdict={verdicts[supp.name] || null}
            index={i}
            total={supps.length}
            imageUri={imageUri}
            allImages={allImages}
          />
        ))}

        {/* Disclaimer */}
        <View style={ms.disclaimer}>
          <Text style={ms.disclaimerTxt}>
            ⚕️ This report is for general information only and is not medical advice. Always speak to your doctor or pharmacist before starting, stopping, or changing any supplement — especially if you take other medicines or have a health condition.
          </Text>
        </View>

        <TouchableOpacity
          style={ms.primaryBtn}
          onPress={() => navigation.navigate('Scan')}
          activeOpacity={0.88}
        >
          <Text style={ms.primaryBtnTxt}>📸  Scan Another Supplement</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={ms.secondaryBtn}
          onPress={() => navigation.navigate('Home')}
          activeOpacity={0.88}
        >
          <Text style={ms.secondaryBtnTxt}>Back to Home</Text>
        </TouchableOpacity>

        <View style={{ height: 40 }} />
      </ScrollView>

      <SafeAreaView style={{ backgroundColor: C.card }}>
        <View style={ms.footer}>
          <Text style={ms.footerTxt}>⚕️ For information only · Always ask your doctor</Text>
        </View>
      </SafeAreaView>
    </View>
  );
}

const ms = StyleSheet.create({
  root:       { flex:1, backgroundColor:C.bg },
  header:     { backgroundColor:C.navy, flexDirection:'row', alignItems:'center',
                justifyContent:'space-between', paddingHorizontal:16,
                paddingTop:Platform.OS==='android'?14:4, paddingBottom:14 },
  backBtn:    { flexDirection:'row', alignItems:'center', gap:4, width:60 },
  backIcon:   { fontSize:28, color:'#fff', marginTop:-2 },
  backTxt:    { fontSize:16, color:'#fff', fontWeight:'500' },
  headerTxt:  { fontSize:17, fontWeight:'700', color:'#fff' },
  scroll:     { flex:1 },
  content:    { padding:14, paddingBottom:32 },
  center:     { flex:1, justifyContent:'center', alignItems:'center', padding:28, gap:14 },
  loadTitle:  { fontSize:22, fontWeight:'800', color:C.text, textAlign:'center' },
  loadSub:    { fontSize:14, color:C.muted, textAlign:'center', lineHeight:22 },
  helpBox:    { backgroundColor:'#FEF9C3', borderRadius:16, padding:18, width:'100%', marginTop:4 },
  helpTitle:  { fontSize:14, fontWeight:'800', color:'#78350F', marginBottom:8 },
  helpTxt:    { fontSize:13.5, color:'#78350F', lineHeight:24 },
  btn:        { backgroundColor:C.navy, paddingHorizontal:36, paddingVertical:15,
                borderRadius:14, marginTop:10 },
  btnTxt:     { color:'#fff', fontWeight:'700', fontSize:15 },
  disclaimer: { backgroundColor:'#EFF6FF', borderRadius:16, padding:18, marginBottom:18,
                borderLeftWidth:4, borderLeftColor:C.blue },
  disclaimerTxt:{ fontSize:13, color:'#1E40AF', lineHeight:21 },
  primaryBtn: { backgroundColor:C.navy, paddingVertical:17, borderRadius:16,
                alignItems:'center', marginBottom:10 },
  primaryBtnTxt:{ color:'#fff', fontSize:16, fontWeight:'700' },
  secondaryBtn:{ backgroundColor:C.card, paddingVertical:16, borderRadius:16,
                 alignItems:'center', borderWidth:1.5, borderColor:C.border, marginBottom:8 },
  secondaryBtnTxt:{ color:C.text, fontSize:15, fontWeight:'600' },
  footer:     { backgroundColor:C.card, borderTopWidth:1, borderTopColor:C.border,
                paddingVertical:10, alignItems:'center' },
  footerTxt:  { fontSize:11.5, color:C.muted },
});
