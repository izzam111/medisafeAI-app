// homescreen.js — header (logo), search, nutrient cards that slide by themselves (tap one to read more), the scan
// button, how it works, and one plain line at the bottom: for information only. History and Profile have their own tabs.
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { View, Text, Pressable, ScrollView, Modal, Animated, PanResponder, StyleSheet, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useFocusEffect } from '@react-navigation/native';
import { Screen, Icon, Logo, C, T, shadow } from '../ui';
import { getProfile, cachedProfile } from '../config';

// Nutrient cards (NIH Office of Dietary Supplements fact sheets). Tap a card to read what the nutrient does and which
// fruits and vegetables give it. A different 6 are shown each time Home opens. "Adults need" = daily amount for ages 19-50.
const NUTRIENTS = [
  { key: 'iron', food: "1 cup of cooked lentils (daal) gives about 6 mg of iron: most of a man's daily need and a third of a woman's.", name: 'Iron', icon: 'water', tag: 'A mineral your blood needs to carry oxygen to every part of your body.',
    does: 'Iron helps red blood cells carry oxygen around your body. Low iron makes you tired and weak and can lead to anaemia.',
    good: 'Women with periods need more iron than men. Tea and coffee block iron; vitamin C helps your body absorb it.',
    fruitsVeg: ['Spinach', 'Lentils (daal)', 'Chickpeas', 'Kidney beans', 'Peas'],
    other: 'Red meat, chicken liver, fish and eggs.', need: 'Men 8 mg, women 18 mg a day' },
  { key: 'vitc', food: "One guava gives about 125 mg of vitamin C, more than a whole day's need.", name: 'Vitamin C', icon: 'nutrition', tag: 'A vitamin found in fresh fruit that helps wounds heal and helps you absorb iron.',
    does: 'Vitamin C helps wounds heal, keeps gums and skin healthy, supports the immune system and helps you absorb iron.',
    good: 'Your body cannot store it, so you need some every day. Long cooking destroys much of it, so fresh fruit is best.',
    fruitsVeg: ['Guava', 'Oranges and kinnow', 'Lemon', 'Strawberries', 'Tomatoes', 'Capsicum'],
    other: 'Potatoes and green chillies also add some.', need: 'Men 90 mg, women 75 mg a day' },
  { key: 'vitd', food: 'Food alone rarely covers it: one egg yolk gives only about 1 mcg (44 IU) of the 15 mcg you need.', name: 'Vitamin D', icon: 'sunny', tag: 'The "sunshine vitamin" your skin makes in sunlight, needed for strong bones.',
    does: 'Vitamin D helps your body absorb calcium, which keeps bones and teeth strong. It also supports muscles.',
    good: 'Your skin makes vitamin D in sunlight. Very few foods contain it, which is why many people need a supplement.',
    fruitsVeg: ['Mushrooms grown in sunlight (small amounts)'],
    other: 'Sunlight, egg yolks, fish such as salmon, and fortified milk.', need: '15 mcg (600 IU) a day' },
  { key: 'calcium', food: '1 cup of milk gives about 300 mg of calcium, so 3 cups of milk or yogurt cover most of your day.', name: 'Calcium', icon: 'body', tag: 'The main mineral in your bones and teeth, also needed by your muscles and heart.',
    does: 'Calcium builds strong bones and teeth and helps your muscles, nerves and heart work properly.',
    good: 'Your body absorbs it best in amounts of 500 mg or less at a time. The calcium in spinach is poorly absorbed.',
    fruitsVeg: ['Mustard greens (saag)', 'Broccoli', 'Okra (bhindi)', 'Cabbage'],
    other: 'Milk, yogurt, cheese and almonds.', need: '1,000 mg a day' },
  { key: 'b12', food: '1 cup of milk gives about 1.2 mcg of B12, so 2 cups of milk cover your whole day.', name: 'Vitamin B12', icon: 'flash', tag: 'A vitamin from animal foods that keeps your nerves and blood cells healthy.',
    does: 'Vitamin B12 helps make red blood cells and keeps your nerves and brain working well.',
    good: 'Fruits and vegetables do not contain B12. Vegetarians and older adults are more likely to run low.',
    fruitsVeg: ['None: B12 comes only from animal foods'],
    other: 'Meat, fish, eggs, milk and yogurt.', need: '2.4 mcg a day' },
  { key: 'folate', food: "1 cup of cooked lentils gives about 360 mcg of folate, almost a whole day's need.", name: 'Folate', icon: 'heart', tag: 'A B vitamin your body uses to make new cells, very important in pregnancy.',
    does: 'Folate (folic acid) helps your body make new cells and DNA. It is especially important before and during early pregnancy.',
    good: 'Folic acid before and in early pregnancy helps prevent birth defects of the baby\'s brain and spine.',
    fruitsVeg: ['Spinach', 'Lentils', 'Chickpeas', 'Peas', 'Broccoli', 'Oranges'],
    other: 'Beans, eggs and fortified flour.', need: '400 mcg a day (600 mcg in pregnancy)' },
  { key: 'potassium', food: 'One medium banana gives about 420 mg of potassium; a medium potato with its skin gives about 900 mg.', name: 'Potassium', icon: 'pulse', tag: 'A mineral that keeps your heartbeat steady and your blood pressure healthy.',
    does: 'Potassium helps your heart beat steadily, your muscles move and keeps blood pressure in a healthy range.',
    good: 'Most people get enough from food. People with kidney problems should not take potassium supplements without a doctor.',
    fruitsVeg: ['Bananas', 'Potatoes', 'Dates', 'Apricots', 'Tomatoes', 'Spinach'],
    other: 'Milk, yogurt and beans.', need: 'Men 3,400 mg, women 2,600 mg a day' },
  { key: 'vita', food: "Half a cup of raw carrots gives about 460 mcg of vitamin A: about half a man's daily need and two-thirds of a woman's.", name: 'Vitamin A', icon: 'eye', tag: 'A vitamin that helps you see in dim light and keeps your skin healthy.',
    does: 'Vitamin A helps you see in dim light and keeps your skin and immune system healthy.',
    good: 'Too much vitamin A from supplements can be harmful, especially in pregnancy. Food sources are the safest.',
    fruitsVeg: ['Carrots', 'Mangoes', 'Sweet potatoes', 'Pumpkin', 'Spinach', 'Apricots'],
    other: 'Liver, eggs and milk.', need: 'Men 900 mcg, women 700 mcg a day' },
  { key: 'magnesium', food: "A small handful of almonds (about 23, or 28 g) gives 80 mg of magnesium, about a quarter of a woman's daily need.", name: 'Magnesium', icon: 'barbell', tag: 'A mineral that helps your muscles, nerves and heart work and gives you energy.',
    does: 'Magnesium helps your muscles and nerves work, keeps your heartbeat steady and helps turn food into energy.',
    good: 'Too much from supplements can cause loose stools. Food sources do not cause this.',
    fruitsVeg: ['Spinach', 'Bananas', 'Beans', 'Avocado'],
    other: 'Almonds, cashews, seeds and whole wheat.', need: 'Men 400 mg, women 310 mg a day' },
  { key: 'zinc', food: "85 g (3 oz) of cooked beef gives about 5 mg of zinc, roughly half a man's daily need.", name: 'Zinc', icon: 'shield-checkmark', tag: 'A mineral that helps your body fight infections and heal wounds.',
    does: 'Zinc helps your immune system fight germs, helps wounds heal and supports taste and smell.',
    good: 'Taking a lot of zinc for a long time can lower your copper level. Stay within the safe limit.',
    fruitsVeg: ['Chickpeas', 'Lentils', 'Peas', 'Beans'],
    other: 'Meat, chicken, nuts and seeds.', need: 'Men 11 mg, women 8 mg a day' },
  { key: 'vitk', food: "Half a cup of cooked spinach gives about 440 mcg of vitamin K, several days' worth.", name: 'Vitamin K', icon: 'bandage', tag: 'A vitamin from green leafy vegetables that helps your blood clot when you are cut.',
    does: 'Vitamin K helps your blood clot when you are cut and helps keep bones healthy.',
    good: 'If you take a blood-thinning medicine, keep the amount of green leafy vegetables steady and talk to your doctor.',
    fruitsVeg: ['Spinach', 'Mustard greens (saag)', 'Broccoli', 'Cabbage', 'Lettuce'],
    other: 'Vegetable oils such as soybean oil.', need: 'Men 120 mcg, women 90 mcg a day' },
  { key: 'vite', food: 'A small handful of almonds (about 23) gives about 7 mg of vitamin E, almost half your daily need.', name: 'Vitamin E', icon: 'leaf', tag: 'An antioxidant vitamin that protects your cells from damage.',
    does: 'Vitamin E is an antioxidant: it protects your cells from damage and supports the immune system.',
    good: 'High-dose vitamin E supplements can increase bleeding risk. Food sources are safe.',
    fruitsVeg: ['Spinach', 'Broccoli', 'Mangoes', 'Kiwi'],
    other: 'Almonds, sunflower seeds and vegetable oils.', need: '15 mg a day' },
  { key: 'b6', name: 'Vitamin B6', icon: 'sparkles', tag: 'A B vitamin that helps your body use protein and keeps your brain and nerves working.',
    does: 'Vitamin B6 helps your body use protein, make red blood cells and keep your brain and immune system working well.',
    good: 'Very high doses from supplements taken for a long time can damage nerves, causing numb or tingling hands and feet.',
    fruitsVeg: ['Bananas', 'Potatoes', 'Chickpeas', 'Spinach', 'Avocado'],
    other: 'Chicken, fish and fortified cereals.', need: '1.3 mg a day',
    food: "1 cup of cooked chickpeas (chanay) gives about 1.1 mg of vitamin B6, almost a whole day's need." },
  { key: 'b3', name: 'Niacin (B3)', icon: 'flame', tag: 'A B vitamin that helps your body turn food into energy.',
    does: 'Niacin helps turn the food you eat into energy and keeps your skin, nerves and digestion healthy.',
    good: 'High-dose niacin supplements often cause flushing: red, warm, itchy skin. They can also affect the liver.',
    fruitsVeg: ['Potatoes', 'Peas', 'Mushrooms', 'Avocado'],
    other: 'Chicken, fish, peanuts and whole wheat.', need: 'Men 16 mg, women 14 mg a day',
    food: "85 g (3 oz) of cooked chicken breast gives about 10 mg of niacin, around two-thirds of your daily need." },
  { key: 'omega3', name: 'Omega-3', icon: 'fish', tag: 'A healthy fat found in fish and nuts that is good for your heart and brain.',
    does: 'Omega-3 fats are part of every cell in your body and support your heart, brain and eyes.',
    good: 'Fish gives the omega-3 types (EPA and DHA) your body uses most. Plants give ALA, which your body converts only in small amounts.',
    fruitsVeg: ['Brussels sprouts (small amounts)', 'Spinach (small amounts)'],
    other: 'Fish such as salmon, walnuts, flaxseeds and chia seeds.', need: 'Men 1.6 g, women 1.1 g a day (plant omega-3)',
    food: "A small handful of walnuts (28 g, about 7 walnuts) gives about 2.5 g of plant omega-3, more than a day's need." },
  { key: 'iodine', name: 'Iodine', icon: 'beaker', tag: 'A mineral your thyroid gland needs to control your energy and growth.',
    does: 'Iodine helps your thyroid gland make hormones that control your energy, growth and how your body uses food.',
    good: 'Too little iodine can cause goitre (a swollen thyroid). Using iodized salt is the easiest way to get enough.',
    fruitsVeg: ['Seaweed', 'Prunes (small amounts)', 'Potatoes (small amounts)'],
    other: 'Iodized salt, fish, milk, yogurt and eggs.', need: '150 mcg a day (220 mcg in pregnancy)',
    food: "Just a quarter teaspoon of iodized salt gives about 76 mcg of iodine, half your daily need." },
  { key: 'selenium', name: 'Selenium', icon: 'flower', tag: 'A mineral that protects your cells and helps your thyroid work.',
    does: 'Selenium protects your cells from damage, supports your immune system and helps your thyroid work.',
    good: 'Too much selenium can cause hair and nail loss. A single Brazil nut can hold more than a whole day\'s amount.',
    fruitsVeg: ['Mushrooms', 'Spinach (small amounts)'],
    other: 'Fish, eggs, chicken and whole wheat.', need: '55 mcg a day',
    food: "One egg gives about 15 mcg of selenium, over a quarter of your daily need." },
];
const shuffled = () => [...NUTRIENTS].sort(() => Math.random() - 0.5).slice(0, 6);
const EVERY = 5000;        // ms each card stays before the next one slides in
const RESUME = 6000;       // after the user swipes, wait this long before sliding again

// The card, opened: a sheet from the bottom. Drag the handle (or the title) down to close it, or tap outside it.
function NutrientSheet({ item, onClose }) {
  const { height } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const y = useRef(new Animated.Value(0)).current;
  useEffect(() => { if (item) y.setValue(0); }, [item]);

  const pan = useRef(PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: (_, g) => g.dy > 4,
    onPanResponderMove: (_, g) => y.setValue(Math.max(0, g.dy)),
    onPanResponderRelease: (_, g) => {
      if (g.dy > 90 || g.vy > 0.8) {
        Animated.timing(y, { toValue: height, duration: 180, useNativeDriver: true }).start(onClose);
      } else {
        Animated.spring(y, { toValue: 0, useNativeDriver: true, bounciness: 4 }).start();
      }
    },
  })).current;

  return (
    <Modal visible={!!item} transparent animationType="slide" statusBarTranslucent onRequestClose={onClose}>
      <Pressable style={s.dim} onPress={onClose} accessibilityLabel="Close" />
      {item && (
        <Animated.View style={[s.sheet, { maxHeight: height * 0.85, paddingBottom: insets.bottom + 16, transform: [{ translateY: y }] }]}>
          <View {...pan.panHandlers}>
            <View style={s.grabArea}><View style={s.grab} /></View>
            <View style={s.sheetHead}>
              <View style={s.factIcon}><Icon name={item.icon} size={24} color={C.brand} /></View>
              <View style={{ flex: 1 }}>
                <Text style={s.sheetTitle}>{item.name}</Text>
                <Text style={s.factTxt}>{item.tag}</Text>
              </View>
            </View>
          </View>
          <ScrollView style={{ flexShrink: 1 }} contentContainerStyle={{ paddingBottom: 8 }}>
            <Text style={s.h}>What it does</Text>
            <Text style={s.p}>{item.does}</Text>
            <Text style={s.h}>Good to know</Text>
            <Text style={s.p}>{item.good}</Text>
            <Text style={s.h}>Fruits and vegetables</Text>
            <View style={s.chips}>
              {item.fruitsVeg.map(x => <View key={x} style={s.chip}><Text style={s.chipTxt}>{x}</Text></View>)}
            </View>
            <Text style={s.h}>Other natural sources</Text>
            <Text style={s.p}>{item.other}</Text>
            <Text style={s.h}>Adults need</Text>
            <Text style={s.p}>{item.need}</Text>
            <View style={s.foodBox}>
              <View style={s.foodHead}>
                <Icon name="restaurant-outline" size={18} color={C.brandDark} />
                <Text style={s.foodLabel}>Food fact</Text>
              </View>
              <Text style={s.foodTxt}>{item.food}</Text>
            </View>
            <Text style={s.src}>Source: NIH Office of Dietary Supplements</Text>
          </ScrollView>
        </Animated.View>
      )}
    </Modal>
  );
}

function Facts() {
  const [FACTS] = useState(shuffled);                     // a fresh set each time Home opens
  const { width } = useWindowDimensions();
  const cardW = width - 40;                               // same side margins as the rest of the page
  const step = cardW + 12;
  const ref = useRef(null);
  const [index, setIndex] = useState(0);
  const at = useRef(0);                                   // the card on screen now
  const [paused, setPaused] = useState(false);            // user swiping, or a card is open
  const [open, setOpen] = useState(null);                 // the nutrient whose details are showing
  const resumeTimer = useRef(null);

  useEffect(() => {
    if (paused || open) return;
    const t = setInterval(() => {
      const next = (at.current + 1) % FACTS.length;
      at.current = next;
      setIndex(next);
      ref.current?.scrollTo({ x: next * step, animated: true });
    }, EVERY);
    return () => clearInterval(t);
  }, [paused, open, step]);
  useEffect(() => () => clearTimeout(resumeTimer.current), []);

  const hold = () => { clearTimeout(resumeTimer.current); setPaused(true); };
  const release = e => {
    const i = Math.round(e.nativeEvent.contentOffset.x / step);
    at.current = Math.max(0, Math.min(FACTS.length - 1, i));
    setIndex(at.current);
    clearTimeout(resumeTimer.current);
    resumeTimer.current = setTimeout(() => setPaused(false), RESUME);
  };

  return (
    <View style={{ marginTop: 22 }}>
      <Text style={[s.section, { marginTop: 0 }]}>Know your nutrients</Text>
      <ScrollView ref={ref} horizontal showsHorizontalScrollIndicator={false} decelerationRate="fast"
        snapToInterval={step} snapToAlignment="start" disableIntervalMomentum
        style={{ marginHorizontal: -20 }} contentContainerStyle={{ paddingHorizontal: 20, gap: 12 }}
        onScrollBeginDrag={hold} onMomentumScrollEnd={release} onScrollEndDrag={release}>
        {FACTS.map(f => (
          <Pressable key={f.key} onPress={() => setOpen(f)} style={({ pressed }) => [s.fact, { width: cardW }, pressed && { opacity: 0.9 }]}
            accessibilityRole="button" accessibilityLabel={`${f.name}. ${f.tag}. Tap to read more`}>
            <View style={s.factIcon}><Icon name={f.icon} size={24} color={C.brand} /></View>
            <View style={{ flex: 1 }}>
              <Text style={s.factTitle}>{f.name}</Text>
              <Text style={s.factTxt}>{f.tag}</Text>
              <Text style={s.factMore}>Tap to read more</Text>
            </View>
          </Pressable>
        ))}
      </ScrollView>
      <View style={s.dots}>
        {FACTS.map((f, i) => <View key={f.key} style={[s.dot, i === index && s.dotOn]} />)}
      </View>

      <NutrientSheet item={open} onClose={() => setOpen(null)} />
    </View>
  );
}

export default function HomeScreen({ navigation }) {
  const [profile, setProfile] = useState(null);

  useFocusEffect(useCallback(() => {
    cachedProfile().then(c => c && setProfile(c));     // show at once from the phone
    getProfile().then(p => p && setProfile(p));
  }, []));

  // Search and Scan go straight on: the details saved in the Profile tab are used for every check.
  const go = to => navigation.navigate(to);

  const header = (
    <View style={s.header}>
      <Logo size={30} />
      <Text style={s.brandTxt}>MediSafe</Text>
    </View>
  );

  return (
    <Screen header={header} bg={C.soft} tabs={{ navigation, current: 'Home' }} footer={
      <View style={s.note}>
        <Icon name="alert-circle-outline" size={15} color="#000" />
        <Text style={s.noteTxt}>Information only. Follow your doctor's advice.</Text>
      </View>}>
      <Text style={T.small}>{profile?.name ? `Hello, ${profile.name.split(' ')[0]}` : 'Welcome'}</Text>
      <Text style={[T.hero, { marginTop: 2 }]}>Is your supplement safe for you?</Text>

      <Pressable onPress={() => go('Search')} style={s.search} accessibilityRole="search" accessibilityLabel="Search supplements by name">
        <Icon name="search" size={20} color={C.sub} />
        <Text style={[T.sub, { flex: 1 }]}>Search a supplement by name</Text>
      </Pressable>

      <Facts />

      <Pressable onPress={() => go('Scan')} style={({ pressed }) => [s.scan, pressed && { opacity: 0.92 }]}
        accessibilityRole="button" accessibilityLabel="Scan a supplement">
        <View style={s.scanIcon}><Icon name="camera" size={24} color={C.brand} /></View>
        <View style={{ flex: 1 }}>
          <Text style={s.scanTitle}>Scan a supplement</Text>
          <Text style={s.scanSub}>Take a photo of the pack</Text>
        </View>
        <Icon name="arrow-forward" size={22} color="#fff" />
      </Pressable>

      {/* Just information, not buttons */}
      <Text style={s.section}>How it works</Text>
      <View style={s.how}>
        {[['camera-outline', 'Take a photo', 'of the pack'], ['shield-checkmark-outline', 'We check it', 'against your profile'],
          ['document-text-outline', 'Read your report', 'dose, foods, safety']].map(([icon, label, sub], i) => (
          <View key={label} style={s.howStep}>
            <Text style={s.howNo}>{i + 1}</Text>
            <Icon name={icon} size={22} color={C.sub} />
            <Text style={s.howTxt}>{label}</Text>
            <Text style={s.howSub}>{sub}</Text>
          </View>
        ))}
      </View>

    </Screen>
  );
}

const s = StyleSheet.create({
  header:     { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 20, paddingVertical: 12,
                backgroundColor: '#fff', borderBottomWidth: 1, borderBottomColor: C.line, marginBottom: 14 },
  brandTxt:   { fontSize: 18, fontWeight: '800', color: C.ink, letterSpacing: 0.2 },
  search:     { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 18, backgroundColor: '#fff', borderRadius: 12,
                paddingHorizontal: 14, minHeight: 50, borderWidth: 1, borderColor: C.line },
  fact:       { flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: '#fff', borderRadius: 16, padding: 16,
                minHeight: 104, borderWidth: 1, borderColor: C.line },
  factIcon:   { width: 48, height: 48, borderRadius: 24, backgroundColor: C.tint, alignItems: 'center', justifyContent: 'center' },
  factTitle:  { fontSize: 16, fontWeight: '700', color: C.ink },
  factTxt:    { fontSize: 14, lineHeight: 20, color: C.sub, marginTop: 3 },
  dots:       { flexDirection: 'row', justifyContent: 'center', gap: 6, marginTop: 10 },
  dot:        { width: 6, height: 6, borderRadius: 3, backgroundColor: C.line },
  dotOn:      { width: 18, backgroundColor: C.brand },
  factMore:   { fontSize: 13, fontWeight: '600', color: C.brandDark, marginTop: 6 },
  dim:        { flex: 1, backgroundColor: 'rgba(0,0,0,0.35)' },
  sheet:      { position: 'absolute', left: 0, right: 0, bottom: 0, backgroundColor: '#fff', borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingHorizontal: 20 },
  grabArea:   { paddingTop: 10, paddingBottom: 14, alignItems: 'center' },
  grab:       { width: 44, height: 5, borderRadius: 3, backgroundColor: '#C5CBD6' },
  sheetHead:  { flexDirection: 'row', alignItems: 'center', gap: 14, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: C.line },
  sheetTitle: { fontSize: 20, fontWeight: '800', color: C.ink },
  h:          { fontSize: 13, fontWeight: '700', color: C.sub, letterSpacing: 0.6, textTransform: 'uppercase', marginTop: 16, marginBottom: 6 },
  p:          { fontSize: 16, lineHeight: 23, color: C.ink },
  chips:      { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip:       { backgroundColor: C.tint, borderRadius: 16, paddingVertical: 6, paddingHorizontal: 12 },
  chipTxt:    { fontSize: 14, fontWeight: '600', color: C.brandDark },
  foodBox:    { backgroundColor: C.tint, borderRadius: 14, padding: 14, marginTop: 18 },
  foodHead:   { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  foodLabel:  { fontSize: 13, fontWeight: '700', color: C.brandDark, letterSpacing: 0.6, textTransform: 'uppercase' },
  foodTxt:    { fontSize: 16, lineHeight: 23, color: C.ink },
  src:        { fontSize: 12, color: C.faint, marginTop: 18 },
  scan:       { marginTop: 20, flexDirection: 'row', alignItems: 'center', gap: 14, backgroundColor: C.brand, borderRadius: 16,
                paddingVertical: 14, paddingHorizontal: 16, ...shadow },
  scanIcon:   { width: 44, height: 44, borderRadius: 22, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  scanTitle:  { fontSize: 17, fontWeight: '700', color: '#fff' },
  scanSub:    { fontSize: 13, color: 'rgba(255,255,255,0.88)', marginTop: 2 },
  section:    { fontSize: 13, fontWeight: '700', color: C.sub, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 26, marginBottom: 10 },
  how:        { flexDirection: 'row', gap: 8 },
  howStep:    { flex: 1, alignItems: 'center', gap: 4, paddingVertical: 4 },
  howNo:      { fontSize: 12, fontWeight: '700', color: C.faint },
  howTxt:     { fontSize: 14, fontWeight: '600', color: C.ink, textAlign: 'center', marginTop: 2 },
  howSub:     { fontSize: 12, color: C.sub, textAlign: 'center' },
  note:       { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 5 },
  noteTxt:    { fontSize: 12, color: '#000' },
});
