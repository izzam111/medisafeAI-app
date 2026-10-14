//homescreen.js
import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, TouchableHighlight,
  StyleSheet, StatusBar, ScrollView, Platform,
  SafeAreaView, Modal, Animated, Pressable, Easing, Dimensions,
  PanResponder,
} from 'react-native';

const { width: SCREEN_W } = Dimensions.get('window');

/* ─── TOKENS ─── */
const C = {
  primary:     '#1B4F72',
  primaryDark: '#154360',
  primary2:    '#2874A6',
  accentBlue:  '#5DADE2',
  bg:          '#EBF5FB',
  card:        '#FFFFFF',
  border:      '#D6EAF8',
  text:        '#1A252F',
  textSub:     '#5D6D7E',
  muted:       '#85929E',
  green:       '#27AE60',
  amber:       '#E67E22',
  red:         '#E74C3C',
};

/* ─── SUPPLEMENTS ─── */
const SUPPLEMENTS = [
  'Centrum','Centrum Silver','Centrum Men','Centrum Women',
  'Supradyn','Supradyn Energy','Supradyn Kids',
  'Omega-3','Fish Oil','Cod Liver Oil',
  'Vitamin D','Vitamin D3','Vitamin D3 + K2',
  'Vitamin C','Vitamin C 500mg','Vitamin C 1000mg',
  'Vitamin B12','Vitamin B Complex','Vitamin E',
  'Zinc','Zinc + Vitamin C','Zinc Picolinate',
  'Magnesium','Magnesium Glycinate','Magnesium Citrate',
  'Calcium','Calcium + Vitamin D','Calcium Carbonate',
  'Iron','Iron + Folic Acid','Ferrous Sulphate',
  'Folic Acid','Folate','Biotin','Biotin 5000mcg',
  'Collagen','Collagen Peptides','Marine Collagen',
  'Multivitamin',"Men's Multivitamin","Women's Multivitamin",
  'Prenatal Vitamins','Probiotics','Probiotic 10 Billion CFU',
  'Melatonin','Melatonin 5mg','Melatonin 10mg',
  'Ashwagandha','Ashwagandha KSM-66',
  'Turmeric','Turmeric + Black Pepper','Curcumin',
  'CoQ10','Coenzyme Q10','Glucosamine','Glucosamine + Chondroitin',
  'Whey Protein','Plant Protein','Creatine','BCAA','Amino Acids',
  'Spirulina','Chlorella','Evening Primrose Oil','Flaxseed Oil',
  'Garlic Extract','Black Seed Oil','Nigella Sativa',
  'Milk Thistle','Echinacea','Elderberry',
  'Ginkgo Biloba','Ginseng','Rhodiola Rosea',
  'Alpha Lipoic Acid','NAC','L-Carnitine','5-HTP','L-Theanine',
  'Selenium','Iodine','Chromium','Copper','Potassium','Electrolytes',
  'Vitamin A','Vitamin K','Vitamin K2',
  'Niacin','Riboflavin','Thiamine','Pantothenic Acid',
  'Saw Palmetto','Berberine','Cinnamon Extract',
  'Green Tea Extract','Resveratrol','Lutein','Zeaxanthin',
  'Hair Vitamins','Skin Vitamins','Nail Vitamins',
  'Kids Multivitamin',"Children's Omega-3",
  'Senior Multivitamin','Immune Support','Energy Supplement',
];

/* ─── FACT CARDS — `what` field added ─── */
const FACT_CARDS = [
  {
    emoji: '☀️', name: 'Vitamin D', tag: 'Bone & Immunity', color: '#E67E22',
    what: 'A fat-soluble vitamin your body synthesises when skin is exposed to sunlight. It exists in two main forms: D2 (from plants) and D3 (from animals and sunlight). D3 is used in most supplements as it raises blood levels more effectively.',
    fact: 'Essential for calcium absorption and bone strength. Deficiency is strongly linked to fatigue, depression, and weakened immunity. A large portion of the global population is deficient, especially in low-sunlight regions.',
    sources: 'Salmon · Egg yolks · Fortified milk · Sunlight',
  },
  {
    emoji: '🌿', name: 'Magnesium', tag: 'Muscle & Nerve', color: '#27AE60',
    what: 'An essential mineral and electrolyte found in every cell of the human body. It is the fourth most abundant mineral overall and is required for hundreds of enzymatic processes — from energy production to protein synthesis.',
    fact: 'Involved in over 300 biochemical reactions in the body. It regulates muscle contractions, nerve signals, blood pressure, and blood sugar levels. Many people are deficient without realising it.',
    sources: 'Spinach · Almonds · Pumpkin seeds · Dark chocolate',
  },
  {
    emoji: '🐟', name: 'Omega-3', tag: 'Heart & Brain', color: '#2874A6',
    what: 'A family of polyunsaturated fatty acids. The three key types are ALA (from plants), EPA and DHA (from fish and algae). EPA and DHA are the forms the body uses most directly, and they cannot be made by the body in meaningful amounts.',
    fact: 'Actively reduces inflammation and supports both heart and brain function. The body cannot produce it — it must come entirely from diet or supplements.',
    sources: 'Salmon · Mackerel · Chia seeds · Walnuts · Flaxseed',
  },
  {
    emoji: '🫐', name: 'Vitamin C', tag: 'Immunity & Skin', color: '#8E44AD',
    what: 'A water-soluble vitamin also known as ascorbic acid. Unlike most animals, humans cannot produce Vitamin C on their own — making it an essential daily nutrient. It is among the most widely researched vitamins in existence.',
    fact: 'A powerful antioxidant that protects cells from damage, boosts immune defence, helps heal wounds faster, and is essential for collagen production — keeping skin firm and youthful.',
    sources: 'Citrus fruits · Bell peppers · Strawberries · Kiwi',
  },
  {
    emoji: '⚡', name: 'Vitamin B12', tag: 'Energy & Nerves', color: '#C0392B',
    what: 'A water-soluble vitamin also called cobalamin — the largest and most structurally complex vitamin known. It is unique in containing the mineral cobalt at its core, and is found almost exclusively in animal-based foods.',
    fact: 'Critical for red blood cell formation and healthy nerve function. A deficiency can cause extreme fatigue, brain fog, and lasting nerve damage. Especially important for vegetarians and vegans.',
    sources: 'Meat · Fish · Dairy · Eggs · Fortified cereals',
  },
  {
    emoji: '🦴', name: 'Calcium', tag: 'Bones & Teeth', color: '#1ABC9C',
    what: 'The most abundant mineral in the human body. About 99% is stored in bones and teeth, giving them structure and hardness. The remaining 1% circulates in blood and is used for muscle contractions, nerve signalling, and blood clotting.',
    fact: 'Works best when paired with Vitamin D for proper absorption. Critical throughout all life stages — from childhood bone development to preventing osteoporosis in older age.',
    sources: 'Milk · Yogurt · Cheese · Broccoli · Tofu',
  },
  {
    emoji: '💪', name: 'Iron', tag: 'Blood & Oxygen', color: '#C0392B',
    what: 'A trace mineral and key component of haemoglobin — the protein in red blood cells that carries oxygen from the lungs to the rest of the body. There are two dietary forms: haem iron (animal sources, absorbed easily) and non-haem iron (plant sources).',
    fact: 'Without enough iron you feel constantly tired and breathless. Women of reproductive age, vegetarians, and athletes are most at risk of deficiency.',
    sources: 'Red meat · Lentils · Spinach · Fortified cereals',
  },
  {
    emoji: '🧠', name: 'Ashwagandha', tag: 'Stress & Focus', color: '#6C3483',
    what: 'An ancient medicinal herb (Withania somnifera) native to India, North Africa, and the Mediterranean. Classified as an adaptogen — a natural substance that helps the body resist physical and mental stress. Used for over 3,000 years in Ayurvedic medicine.',
    fact: 'Helps the body manage stress by lowering cortisol levels. Clinical studies also show improvements in focus, sleep quality, and physical stamina.',
    sources: 'Root extract · Supplement capsules · Herbal teas',
  },
  {
    emoji: '🫀', name: 'CoQ10', tag: 'Heart Energy', color: '#D35400',
    what: 'Coenzyme Q10 is a naturally occurring compound found in nearly every cell. It is a critical component of the mitochondria — the cell\'s power plant — helping convert food into usable energy (ATP). It also functions as a potent antioxidant.',
    fact: 'Acts like a battery charger for your heart and muscle cells. Naturally produced by the body but levels decline significantly with age. People on statin medications often need supplementation.',
    sources: 'Beef · Pork · Sardines · Peanuts · Supplement form',
  },
  {
    emoji: '🌱', name: 'Zinc', tag: 'Immunity & Healing', color: '#148F77',
    what: 'An essential trace mineral present in all body tissues. It is the second most abundant trace mineral in the body after iron. The body does not store zinc, so regular daily intake is necessary. It is involved in over 300 enzyme activities.',
    fact: 'Essential for immune system function, wound healing, and DNA synthesis. Even mild deficiency noticeably impairs immunity. Also plays a key role in taste, smell, and reproductive health.',
    sources: 'Oysters · Beef · Pumpkin seeds · Chickpeas',
  },
];

/* ─── ECG LOGO ─── */
function ECGLogo({ size = 44 }) {
  const col = '#5DADE2';
  const h   = 2;
  const W   = size;
  return (
    <View style={{ width: W, height: 24, position: 'relative' }}>
      <View style={{ position:'absolute', left:0, top:11, width:W*0.18, height:h, backgroundColor:col, borderRadius:1 }} />
      <View style={{ position:'absolute', left:W*0.17, top:7, width:W*0.09, height:h, backgroundColor:col, borderRadius:1, transform:[{rotate:'-45deg'}] }} />
      <View style={{ position:'absolute', left:W*0.24, top:14, width:W*0.09, height:h, backgroundColor:col, borderRadius:1, transform:[{rotate:'45deg'}] }} />
      <View style={{ position:'absolute', left:W*0.33, top:0, width:h, height:18, backgroundColor:col, borderRadius:1 }} />
      <View style={{ position:'absolute', left:W*0.33+h, top:4, width:h, height:20, backgroundColor:col, borderRadius:1 }} />
      <View style={{ position:'absolute', left:W*0.33+h*2, top:22, width:W*0.06, height:h, backgroundColor:col, borderRadius:1 }} />
      <View style={{ position:'absolute', left:W*0.42, top:14, width:W*0.10, height:h, backgroundColor:col, borderRadius:1, transform:[{rotate:'-40deg'}] }} />
      <View style={{ position:'absolute', left:W*0.52, top:7, width:W*0.10, height:h, backgroundColor:col, borderRadius:1, transform:[{rotate:'-20deg'}] }} />
      <View style={{ position:'absolute', left:W*0.60, top:8, width:W*0.10, height:h, backgroundColor:col, borderRadius:1, transform:[{rotate:'20deg'}] }} />
      <View style={{ position:'absolute', left:W*0.70, top:11, width:W*0.30, height:h, backgroundColor:col, borderRadius:1 }} />
    </View>
  );
}

/* ─── TAB ICONS ─── */
function HomeIcon({ active }) {
  const col = active ? C.primary : C.muted;
  return (
    <View style={{ width:28, height:24, alignItems:'center' }}>
      <View style={{ position:'absolute', top:0, left:0, width:0, height:0, borderLeftWidth:14, borderRightWidth:0, borderBottomWidth:12, borderLeftColor:'transparent', borderRightColor:'transparent', borderBottomColor:col }} />
      <View style={{ position:'absolute', top:0, right:0, width:0, height:0, borderRightWidth:14, borderLeftWidth:0, borderBottomWidth:12, borderRightColor:'transparent', borderLeftColor:'transparent', borderBottomColor:col }} />
      <View style={{ position:'absolute', bottom:0, width:20, height:14, borderWidth:2, borderColor:col, borderRadius:1, alignItems:'center', justifyContent:'flex-end', backgroundColor:'transparent' }}>
        <View style={{ width:6, height:9, backgroundColor:col, borderTopLeftRadius:2, borderTopRightRadius:2, marginBottom:-2 }} />
      </View>
    </View>
  );
}

function CameraIcon() {
  return (
    <View style={{ alignItems:'center' }}>
      <View style={{ width:10, height:5, backgroundColor:'#fff', borderTopLeftRadius:3, borderTopRightRadius:3, marginBottom:-1, alignSelf:'center' }} />
      <View style={{ width:28, height:20, borderRadius:5, borderWidth:2.5, borderColor:'#fff', alignItems:'center', justifyContent:'center' }}>
        <View style={{ width:11, height:11, borderRadius:5.5, borderWidth:2, borderColor:'#fff', alignItems:'center', justifyContent:'center' }}>
          <View style={{ width:3.5, height:3.5, borderRadius:2, backgroundColor:'#fff' }} />
        </View>
      </View>
    </View>
  );
}

function InfoIcon({ active }) {
  const col = active ? C.primary : C.muted;
  return (
    <View style={{ width:22, height:22, borderRadius:11, borderWidth:2, borderColor:col, alignItems:'center', justifyContent:'center' }}>
      <View style={{ width:2.5, height:2.5, borderRadius:1.5, backgroundColor:col, marginBottom:2 }} />
      <View style={{ width:2, height:7, borderRadius:1, backgroundColor:col }} />
    </View>
  );
}

/* ─────────────────────────────────────────────────────
   FACT CARD DETAIL MODAL
   Order: WHAT IT IS → ABOUT → NATURAL SOURCES
───────────────────────────────────────────────────── */
function FactCardModal({ card, onClose }) {
  if (!card) return null;
  return (
    <Modal visible={!!card} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={fdm.overlay} onPress={onClose}>
        <Pressable style={fdm.sheet} onPress={e => e.stopPropagation()}>
          <View style={fdm.handle} />
          <View style={[fdm.accentBar, { backgroundColor: card.color }]} />

          <View style={fdm.headerRow}>
            <View style={[fdm.emojiBox, { backgroundColor: card.color + '20' }]}>
              <Text style={fdm.emoji}>{card.emoji}</Text>
            </View>
            <View style={fdm.headerMeta}>
              <Text style={fdm.name}>{card.name}</Text>
              <View style={[fdm.tag, { backgroundColor: card.color + '20' }]}>
                <Text style={[fdm.tagText, { color: card.color }]}>{card.tag}</Text>
              </View>
            </View>
          </View>

          <View style={fdm.divider} />

          {/* 1 — WHAT IT IS */}
          <View style={[fdm.sectionBlock, { borderLeftColor: card.color }]}>
            <Text style={[fdm.sectionLabel, { color: card.color }]}>WHAT IT IS</Text>
            <Text style={fdm.sectionText}>{card.what}</Text>
          </View>

          {/* 2 — ABOUT */}
          <View style={[fdm.sectionBlock, { borderLeftColor: C.primary2 }]}>
            <Text style={[fdm.sectionLabel, { color: C.primary2 }]}>ABOUT</Text>
            <Text style={fdm.sectionText}>{card.fact}</Text>
          </View>

          {/* 3 — NATURAL SOURCES */}
          <View style={fdm.srcBox}>
            <Text style={fdm.srcLabel}>NATURAL SOURCES</Text>
            <Text style={fdm.srcVal}>{card.sources}</Text>
          </View>

          <TouchableOpacity style={[fdm.closeBtn, { backgroundColor: card.color }]} onPress={onClose} activeOpacity={0.88}>
            <Text style={fdm.closeBtnText}>Close</Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const fdm = StyleSheet.create({
  overlay:      { flex:1, backgroundColor:'rgba(0,0,0,0.5)', justifyContent:'flex-end' },
  sheet:        { backgroundColor:C.card, borderTopLeftRadius:28, borderTopRightRadius:28, padding:24, paddingBottom:40, overflow:'hidden' },
  handle:       { width:40, height:4, backgroundColor:C.border, borderRadius:2, alignSelf:'center', marginBottom:20 },
  accentBar:    { position:'absolute', top:0, left:0, right:0, height:4 },
  headerRow:    { flexDirection:'row', alignItems:'center', gap:14, marginBottom:16 },
  emojiBox:     { width:58, height:58, borderRadius:16, alignItems:'center', justifyContent:'center' },
  emoji:        { fontSize:30 },
  headerMeta:   { flex:1, gap:6 },
  name:         { fontSize:22, fontWeight:'800', color:C.text, letterSpacing:-0.3 },
  tag:          { alignSelf:'flex-start', paddingHorizontal:10, paddingVertical:4, borderRadius:7 },
  tagText:      { fontSize:11, fontWeight:'700', letterSpacing:0.3 },
  divider:      { height:1, backgroundColor:C.border, marginBottom:18 },
  sectionBlock: { borderLeftWidth:3, paddingLeft:12, marginBottom:18 },
  sectionLabel: { fontSize:9.5, fontWeight:'800', letterSpacing:1.2, marginBottom:6 },
  sectionText:  { fontSize:13.5, color:C.textSub, lineHeight:21 },
  srcBox:       { backgroundColor:C.bg, borderRadius:12, padding:14, marginBottom:24 },
  srcLabel:     { fontSize:9.5, fontWeight:'800', color:C.muted, letterSpacing:1, marginBottom:5 },
  srcVal:       { fontSize:13.5, color:C.textSub, fontWeight:'500', lineHeight:21 },
  closeBtn:     { borderRadius:14, paddingVertical:16, alignItems:'center' },
  closeBtnText: { color:'#fff', fontWeight:'700', fontSize:16 },
});

/* ─────────────────────────────────────────────────────
   FACT CAROUSEL
   — 10s pause, 1.4s slide (very slow)
   — Touch pauses it; release resumes
   — No dots, no "Tap for more"
───────────────────────────────────────────────────── */
const CARD_W   = SCREEN_W - 40;
const PAUSE_MS = 10000;
const SLIDE_MS = 1400;

function FactCarousel() {
  const [index,      setIndex]      = useState(0);
  const [activeCard, setActiveCard] = useState(null);
  const translateX                  = useRef(new Animated.Value(0)).current;
  const total                       = FACT_CARDS.length;
  const isPaused                    = useRef(false);
  const timerRef                    = useRef(null);
  const animRef                     = useRef(null);
  const indexRef                    = useRef(0);

  const advance = useCallback((fromIndex) => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      if (isPaused.current) return;
      const next = (fromIndex + 1) % total;
      const anim = Animated.timing(translateX, {
        toValue: -(next * (CARD_W + 16)),
        duration: SLIDE_MS,
        easing: Easing.inOut(Easing.cubic),
        useNativeDriver: true,
      });
      animRef.current = anim;
      anim.start(({ finished }) => {
        if (finished) {
          indexRef.current = next;
          setIndex(next);
          advance(next);
        }
      });
    }, PAUSE_MS);
  }, [total]);

  useEffect(() => {
    advance(0);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (animRef.current) animRef.current.stop();
    };
  }, []);

  const panResponder = useRef(
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onPanResponderGrant: () => {
        isPaused.current = true;
        if (timerRef.current) clearTimeout(timerRef.current);
        if (animRef.current) animRef.current.stop();
      },
      onPanResponderRelease: () => {
        isPaused.current = false;
        advance(indexRef.current);
      },
      onPanResponderTerminate: () => {
        isPaused.current = false;
        advance(indexRef.current);
      },
    })
  ).current;

  return (
    <View style={fc.wrapper}>
      <View style={fc.outer} {...panResponder.panHandlers}>
        <Animated.View style={[fc.inner, { transform: [{ translateX }] }]}>
          {FACT_CARDS.map((card, i) => (
            <TouchableOpacity
              key={i}
              activeOpacity={0.9}
              onPress={() => setActiveCard(card)}
            >
              <View style={[fc.card, { borderTopColor: card.color }]}>
                <View style={fc.cardHeader}>
                  <View style={[fc.emojiBox, { backgroundColor: card.color + '18' }]}>
                    <Text style={fc.emoji}>{card.emoji}</Text>
                  </View>
                  <View style={fc.cardMeta}>
                    <Text style={fc.cardName}>{card.name}</Text>
                    <View style={[fc.tag, { backgroundColor: card.color + '20' }]}>
                      <Text style={[fc.tagText, { color: card.color }]}>{card.tag}</Text>
                    </View>
                  </View>
                </View>
                <View style={fc.divider} />
                <Text style={fc.fact}>{card.fact}</Text>
                <View style={fc.srcBox}>
                  <Text style={fc.srcLabel}>NATURAL SOURCES</Text>
                  <Text style={fc.srcVal}>{card.sources}</Text>
                </View>
              </View>
            </TouchableOpacity>
          ))}
        </Animated.View>
      </View>
      {/* dots removed */}
      <FactCardModal card={activeCard} onClose={() => setActiveCard(null)} />
    </View>
  );
}

const fc = StyleSheet.create({
  wrapper:    { marginBottom: 28 },
  outer:      { width: CARD_W, overflow: 'hidden', alignSelf: 'center' },
  inner:      { flexDirection: 'row' },
  card: {
    width: CARD_W,
    marginRight: 16,
    backgroundColor: C.card,
    borderRadius: 18,
    padding: 20,
    borderWidth: 1,
    borderColor: C.border,
    borderTopWidth: 4,
    minHeight: 240,
  },
  cardHeader: { flexDirection:'row', alignItems:'center', gap:14, marginBottom:14 },
  emojiBox:   { width:50, height:50, borderRadius:14, alignItems:'center', justifyContent:'center' },
  emoji:      { fontSize:26 },
  cardMeta:   { flex:1, gap:6 },
  cardName:   { fontSize:18, fontWeight:'800', color:C.text, letterSpacing:-0.3 },
  tag:        { alignSelf:'flex-start', paddingHorizontal:10, paddingVertical:4, borderRadius:7 },
  tagText:    { fontSize:11, fontWeight:'700', letterSpacing:0.3 },
  divider:    { height:1, backgroundColor:C.border, marginBottom:14 },
  fact:       { fontSize:13.5, color:C.textSub, lineHeight:21, marginBottom:16, flex:1 },
  srcBox:     { backgroundColor:C.bg, borderRadius:10, padding:12 },
  srcLabel:   { fontSize:9.5, fontWeight:'800', color:C.muted, letterSpacing:1, marginBottom:4 },
  srcVal:     { fontSize:12.5, color:C.textSub, fontWeight:'500' },
});

/* ─────────────────────────────────────────────────────
   HOW MEDISAFE WORKS  — replaces "What MediSafe Checks"
   Clean numbered timeline: step circle + connector line + card
───────────────────────────────────────────────────── */
const HOW_STEPS = [
  {
    step: '01',
    title: 'Scan or Search',
    body: 'Point your camera at any supplement label, or type the name. MediSafe reads every ingredient automatically.',
    color: C.primary,
    line: C.accentBlue,
  },
  {
    step: '02',
    title: 'AI Analysis',
    body: 'Each ingredient is cross-referenced against food interaction data and clinical safety profiles in seconds.',
    color: '#8E44AD',
    line: '#C39BD3',
  },
  {
    step: '03',
    title: 'Risk Assessment',
    body: 'You receive a clear Low, Moderate, or High risk rating — no medical jargon, no guesswork.',
    color: '#E67E22',
    line: '#FAD7A0',
  },
  {
    step: '04',
    title: 'Your Safety Report',
    body: 'A plain-English report tells you exactly what to eat, what to avoid, and why it matters for your health.',
    color: C.green,
    line: '#A9DFBF',
  },
];

function HowItWorksSection() {
  return (
    <View style={hw.container}>
      {HOW_STEPS.map((item, i) => (
        <View key={item.step} style={hw.row}>
          <View style={hw.leftCol}>
            <View style={[hw.circle, { backgroundColor: item.color }]}>
              <Text style={hw.circleNum}>{item.step}</Text>
            </View>
            {i < HOW_STEPS.length - 1 && (
              <View style={[hw.connector, { backgroundColor: item.line }]} />
            )}
          </View>
          <View style={[hw.card, { borderLeftColor: item.color }]}>
            <Text style={[hw.cardTitle, { color: item.color }]}>{item.title}</Text>
            <Text style={hw.cardBody}>{item.body}</Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const hw = StyleSheet.create({
  container:  { paddingHorizontal:20, marginBottom:8 },
  row:        { flexDirection:'row', gap:16 },
  leftCol:    { alignItems:'center', width:36 },
  circle:     { width:36, height:36, borderRadius:18, alignItems:'center', justifyContent:'center', zIndex:1 },
  circleNum:  { color:'#fff', fontSize:12, fontWeight:'800', letterSpacing:0.5 },
  connector:  { width:2, flex:1, minHeight:20, marginVertical:4, borderRadius:1, opacity:0.45 },
  card: {
    flex:1,
    backgroundColor:C.card,
    borderRadius:14,
    borderWidth:1,
    borderColor:C.border,
    borderLeftWidth:3,
    padding:16,
    marginBottom:14,
  },
  cardTitle:  { fontSize:15, fontWeight:'800', marginBottom:6, letterSpacing:-0.2 },
  cardBody:   { fontSize:13, color:C.textSub, lineHeight:20 },
});

/* ─── ABOUT MODAL ─── */
function AboutModal({ visible, onClose }) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable style={am.overlay} onPress={onClose}>
        <Pressable style={am.sheet} onPress={e => e.stopPropagation()}>
          <View style={am.handle} />
          <View style={am.heroRow}>
            <View style={am.heroIconBox}><ECGLogo size={44} /></View>
            <View>
              <Text style={am.heroName}>MediSafe <Text style={{ color: C.accentBlue }}>AI</Text></Text>
              <Text style={am.heroSub}>Version 1.0  ·  AI-Powered Safety</Text>
            </View>
          </View>
          <Text style={am.desc}>
            MediSafe AI reads supplement labels and checks for food interactions — delivering a plain-English safety report in seconds.
          </Text>
          <View style={am.divider} />
          <Text style={am.featLabel}>FEATURES</Text>
          {[
            { icon: '📸', t: 'Scan any supplement label with your camera' },
            { icon: '🔍', t: 'Search 100+ supplements by name instantly'  },
            { icon: '🍽️', t: 'See which foods to eat or avoid'             },
            { icon: '📊', t: 'Low / Moderate / High risk rating'           },
            { icon: '💬', t: 'Plain-English explanation for every result'  },
          ].map(item => (
            <View key={item.t} style={am.row}>
              <View style={am.rowBox}><Text style={{ fontSize: 17 }}>{item.icon}</Text></View>
              <Text style={am.rowText}>{item.t}</Text>
            </View>
          ))}
          <View style={am.divider} />
          <View style={am.disclaimer}>
            <Text style={am.disclaimerTitle}>⚕️  Medical Disclaimer</Text>
            <Text style={am.disclaimerText}>
              AI-generated information only. Not a substitute for professional medical advice. Always consult your doctor or pharmacist before making changes.
            </Text>
          </View>
          <TouchableOpacity style={am.closeBtn} onPress={onClose} activeOpacity={0.88}>
            <Text style={am.closeBtnText}>Done</Text>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
const am = StyleSheet.create({
  overlay:         { flex:1, backgroundColor:'rgba(0,0,0,0.5)', justifyContent:'flex-end' },
  sheet:           { backgroundColor:C.card, borderTopLeftRadius:28, borderTopRightRadius:28, padding:24, paddingBottom:40 },
  handle:          { width:40, height:4, backgroundColor:C.border, borderRadius:2, alignSelf:'center', marginBottom:22 },
  heroRow:         { flexDirection:'row', alignItems:'center', gap:14, marginBottom:14 },
  heroIconBox:     { width:56, height:56, backgroundColor:C.primary, borderRadius:16, alignItems:'center', justifyContent:'center' },
  heroName:        { fontSize:22, fontWeight:'800', color:C.text },
  heroSub:         { fontSize:12, color:C.muted, marginTop:3 },
  desc:            { fontSize:14, color:C.textSub, lineHeight:22, marginBottom:14 },
  divider:         { height:1, backgroundColor:C.border, marginVertical:14 },
  featLabel:       { fontSize:10, fontWeight:'700', color:C.muted, letterSpacing:1.2, marginBottom:12 },
  row:             { flexDirection:'row', alignItems:'center', gap:12, marginBottom:11 },
  rowBox:          { width:34, height:34, backgroundColor:C.bg, borderRadius:10, alignItems:'center', justifyContent:'center' },
  rowText:         { flex:1, fontSize:14, color:C.text, fontWeight:'500' },
  disclaimer:      { backgroundColor:C.bg, borderRadius:12, padding:14, marginBottom:20 },
  disclaimerTitle: { fontSize:12, fontWeight:'700', color:C.primary, marginBottom:5 },
  disclaimerText:  { fontSize:12.5, color:C.textSub, lineHeight:19 },
  closeBtn:        { backgroundColor:C.primary, borderRadius:14, paddingVertical:16, alignItems:'center' },
  closeBtnText:    { color:'#fff', fontWeight:'700', fontSize:16 },
});

/* ─── HOME SCREEN ─── */
export default function HomeScreen({ navigation }) {
  const [query,     setQuery]   = useState('');
  const [focused,   setFocused] = useState(false);
  const [aboutOpen, setAbout]   = useState(false);

  const suggestions = useMemo(() => {
    if (query.trim().length < 2) return [];
    const q = query.toLowerCase();
    return SUPPLEMENTS.filter(s => s.toLowerCase().includes(q)).slice(0, 6);
  }, [query]);

  const handleSearch = useCallback((text) => {
    const term = text || query;
    if (!term.trim()) return;
    navigation.navigate('Results', { scannedText: term, imageUri: null, isManualSearch: true });
  }, [query, navigation]);

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return { hi: 'Good morning 👋', sub: "Know what you're taking today." };
    if (h < 17) return { hi: 'Good afternoon 👋', sub: 'Your daily supplement check.' };
    return             { hi: 'Good evening 👋',   sub: 'Scan or search any supplement.' };
  };
  const g = greeting();

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.primary} />

      <SafeAreaView style={s.topSafe}>
        <View style={s.topBlock}>
          <View style={s.headerRow}>
            <View style={s.headerLeft}>
              <ECGLogo size={44} />
              <Text style={s.headerApp}>MediSafe <Text style={s.headerAI}>AI</Text></Text>
            </View>
          </View>
          <View style={s.heroInner}>
            <View style={s.bubble1} />
            <View style={s.bubble2} />
            <Text style={s.heroGreet}>{g.hi}</Text>
            <Text style={s.heroSub}>{g.sub}</Text>
          </View>
        </View>
      </SafeAreaView>

      <ScrollView
        style={s.scroll}
        contentContainerStyle={s.scrollContent}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={[s.sectionLabel, { marginTop: 24 }]}>Search Supplement</Text>
        <View style={[s.searchWrap, focused && s.searchFocused]}>
          <Text style={s.searchEmoji}>🔍</Text>
          <TextInput
            style={s.searchInput}
            placeholder="e.g. Centrum, Omega-3, Vitamin D..."
            placeholderTextColor={C.muted}
            value={query}
            onChangeText={setQuery}
            onFocus={() => setFocused(true)}
            onBlur={() => setTimeout(() => setFocused(false), 160)}
            onSubmitEditing={() => handleSearch()}
            returnKeyType="search"
            autoCorrect={false}
          />
          {query.length > 0 && (
            <TouchableOpacity onPress={() => setQuery('')} hitSlop={{ top:10, bottom:10, left:10, right:10 }}>
              <View style={s.clearIcon}><Text style={s.clearText}>✕</Text></View>
            </TouchableOpacity>
          )}
        </View>

        {suggestions.length > 0 && (
          <View style={s.suggBox}>
            {suggestions.map((item, i) => (
              <TouchableHighlight
                key={item}
                underlayColor={C.bg}
                style={[s.sugg, i < suggestions.length - 1 && s.suggBorder]}
                onPress={() => { setQuery(item); handleSearch(item); }}
              >
                <View style={s.suggRow}>
                  <View style={s.suggIconBox}><Text>💊</Text></View>
                  <Text style={s.suggText}>{item}</Text>
                  <Text style={s.suggArrow}>›</Text>
                </View>
              </TouchableHighlight>
            ))}
          </View>
        )}

        {query.trim().length >= 2 && suggestions.length === 0 && (
          <TouchableOpacity style={s.noMatch} onPress={() => handleSearch()} activeOpacity={0.8}>
            <Text style={s.noMatchText}>
              Search for "<Text style={{ fontWeight:'700' }}>{query}</Text>"  →
            </Text>
          </TouchableOpacity>
        )}

        <Text style={[s.sectionLabel, { marginTop: 30 }]}>Supplement Spotlight</Text>
        <FactCarousel />

        <Text style={s.sectionLabel}>How MediSafe Works</Text>
        <HowItWorksSection />

        <View style={{ height: 18 }} />
      </ScrollView>

      <SafeAreaView style={s.tabSafe}>
        <View style={s.tabBar}>
          <View style={s.tabItem}>
            <View style={s.activeBar} />
            <HomeIcon active={true} />
            <Text style={s.tabLabelA}>Home</Text>
          </View>
          <View style={s.fabWrap}>
            <TouchableOpacity style={s.fab} onPress={() => navigation.navigate('Scan')} activeOpacity={0.85}>
              <CameraIcon />
              <Text style={s.fabLabel}>Scan</Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={s.tabItem} onPress={() => setAbout(true)} activeOpacity={0.7}>
            <InfoIcon active={false} />
            <Text style={s.tabLabel}>About</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>

      <AboutModal visible={aboutOpen} onClose={() => setAbout(false)} />
    </View>
  );
}

/* ─── STYLES ─── */
const s = StyleSheet.create({
  root:     { flex:1, backgroundColor:C.bg },
  topSafe:  { backgroundColor:C.primary },
  topBlock: { backgroundColor:C.primary, overflow:'hidden' },
  headerRow: {
    flexDirection:'row', alignItems:'center',
    paddingHorizontal:20,
    paddingTop: Platform.OS === 'android' ? 14 : 6,
    paddingBottom:10,
  },
  headerLeft: { flexDirection:'row', alignItems:'center', gap:12 },
  headerApp:  { fontSize:21, fontWeight:'800', color:'#fff', letterSpacing:-0.4 },
  headerAI:   { color:C.accentBlue },
  heroInner: {
    paddingHorizontal:22, paddingTop:8, paddingBottom:28,
    position:'relative', overflow:'hidden',
  },
  bubble1: { position:'absolute', right:-50, top:-40, width:180, height:180, borderRadius:90, backgroundColor:'rgba(93,173,226,0.10)' },
  bubble2: { position:'absolute', right:40, bottom:-60, width:130, height:130, borderRadius:65, backgroundColor:'rgba(255,255,255,0.04)' },
  heroGreet: { fontSize:24, fontWeight:'800', color:'#fff', letterSpacing:-0.5, marginBottom:6 },
  heroSub:   { fontSize:15, color:'rgba(255,255,255,0.60)', fontWeight:'400' },
  scroll:        { flex:1 },
  scrollContent: { paddingBottom:8 },
  sectionLabel: {
    fontSize:10.5, fontWeight:'700', color:C.muted,
    letterSpacing:1.1, textTransform:'uppercase',
    marginBottom:12, paddingHorizontal:20,
  },
  searchWrap: {
    flexDirection:'row', alignItems:'center',
    backgroundColor:C.card, borderRadius:14,
    borderWidth:1.5, borderColor:C.border,
    paddingHorizontal:14,
    paddingVertical: Platform.OS === 'ios' ? 13 : 5,
    gap:10, marginHorizontal:20, marginBottom:4, marginTop:0,
  },
  searchFocused: { borderColor:C.primary2, borderWidth:2 },
  searchEmoji:   { fontSize:16, color:C.muted },
  searchInput:   { flex:1, fontSize:15, color:C.text, paddingVertical:0 },
  clearIcon:     { width:22, height:22, backgroundColor:C.border, borderRadius:11, alignItems:'center', justifyContent:'center' },
  clearText:     { fontSize:11, color:C.textSub, fontWeight:'700' },
  suggBox: {
    backgroundColor:C.card, borderRadius:14,
    borderWidth:1, borderColor:C.border,
    marginHorizontal:20, marginBottom:4, overflow:'hidden',
  },
  sugg:       {},
  suggBorder: { borderBottomWidth:1, borderBottomColor:C.border },
  suggRow:    { flexDirection:'row', alignItems:'center', gap:12, paddingHorizontal:14, paddingVertical:13 },
  suggIconBox:{ width:32, height:32, backgroundColor:C.bg, borderRadius:8, alignItems:'center', justifyContent:'center' },
  suggText:   { flex:1, fontSize:15, color:C.text, fontWeight:'500' },
  suggArrow:  { fontSize:20, color:C.muted },
  noMatch: {
    backgroundColor:C.bg, borderRadius:12,
    padding:14, marginHorizontal:20, marginTop:4,
    borderWidth:1, borderColor:C.border,
  },
  noMatchText: { fontSize:14, color:C.primary2 },
  tabSafe: { backgroundColor:C.card },
  tabBar: {
    backgroundColor:C.card,
    borderTopWidth:1, borderTopColor:C.border,
    flexDirection:'row', alignItems:'flex-end',
    paddingBottom: Platform.OS === 'ios' ? 10 : 12,
    paddingTop:10, paddingHorizontal:16,
    height: Platform.OS === 'ios' ? 76 : 70,
  },
  tabItem:   { flex:1, alignItems:'center', justifyContent:'flex-end', gap:5, position:'relative' },
  activeBar: { position:'absolute', top:-10, left:'15%', right:'15%', height:2.5, backgroundColor:C.primary, borderBottomLeftRadius:2, borderBottomRightRadius:2 },
  tabLabelA: { fontSize:10.5, color:C.primary, fontWeight:'700' },
  tabLabel:  { fontSize:10.5, color:C.muted, fontWeight:'500' },
  fabWrap:   { flex:1.2, alignItems:'center', marginTop:-30 },
  fab: {
    width:64, height:64, backgroundColor:C.primary,
    borderRadius:32, alignItems:'center', justifyContent:'center',
    borderWidth:4, borderColor:C.card,
    shadowColor:C.primaryDark,
    shadowOffset:{ width:0, height:6 },
    shadowOpacity:0.4, shadowRadius:10,
    elevation:10, gap:3,
  },
  fabLabel: { color:'#fff', fontSize:9.5, fontWeight:'700' },
});
