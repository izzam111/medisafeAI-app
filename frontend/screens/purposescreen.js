// purposescreen.js — MediSafe AI
// Asks the user WHY they are taking EACH supplement separately
// Supports 1-4 supplements from scan

import React, { useState } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity, TextInput,
  StyleSheet, StatusBar, SafeAreaView, Platform, Alert
} from 'react-native';

const C = {
  navy:     '#0D1B3E',
  navyLight:'#1A3A7A',
  blue:     '#4A9FFF',
  bg:       '#F0F4FA',
  card:     '#FFFFFF',
  border:   '#DDE3EE',
  muted:    '#7A8AAA',
  text:     '#111827',
  sub:      '#4B5563',
  green:    '#059669',
  greenBg:  '#ECFDF5',
};

const COMMON_REASONS = [
  'Treating anaemia / low blood',
  'Pregnancy / fetal development',
  'Bone health / osteoporosis',
  'Immunity / cold and flu',
  'Energy and reducing fatigue',
  'Sleep and relaxation',
  'Hair, skin and nails',
  'Joint pain / inflammation',
  'Heart health / cholesterol',
  'General health / daily vitamin',
  'Muscle recovery after exercise',
  'Stress and anxiety',
  'Brain and memory',
  'Blood sugar / diabetes support',
  'Digestive health / constipation',
];

export default function PurposeScreen({ route, navigation }) {
  const {
    supplementName     = 'Unknown Supplement',
    allSupplementNames = [],
    scannedText        = '',
    imageUri           = null,
    allImages          = [],
  } = route.params || {};

  // Build the full list of supplements
  const supplements = allSupplementNames.length > 0
    ? allSupplementNames
    : supplementName && supplementName !== 'Unknown Supplement'
      ? [supplementName]
      : ['Unknown Supplement'];

  // Track which supplement we're currently asking about (step 0, 1, 2...)
  const [currentStep, setCurrentStep] = useState(0);

  // Store purpose for each supplement
  const [purposes, setPurposes] = useState(
    supplements.map(() => '')
  );

  const currentSupp   = supplements[currentStep];
  const currentPurpose = purposes[currentStep];
  const isLastStep    = currentStep === supplements.length - 1;

  const updatePurpose = (text) => {
    const updated = [...purposes];
    updated[currentStep] = text;
    setPurposes(updated);
  };

  const selectReason = (reason) => {
    updatePurpose(reason);
  };

  const goNext = () => {
    if (!currentPurpose.trim()) {
      Alert.alert(
        'Please give a reason',
        `Tell us why you are taking ${currentSupp} so we can check if it is right for you.`
      );
      return;
    }
    if (isLastStep) {
      // All purposes collected — go to results
      navigation.navigate('Results', {
        supplementName:      supplements[0],
        allSupplementNames:  supplements,
        allPurposes:         purposes,
        userPurpose:         purposes[0], // primary purpose for backwards compat
        scannedText,
        imageUri,
        allImages,
      });
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  const goBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    } else {
      navigation.goBack();
    }
  };

  const skipPurpose = () => {
    const updated = [...purposes];
    updated[currentStep] = 'General use / no specific reason';
    setPurposes(updated);
    if (isLastStep) {
      navigation.navigate('Results', {
        supplementName:     supplements[0],
        allSupplementNames: supplements,
        allPurposes:        [...purposes.slice(0, currentStep), 'General use / no specific reason'],
        userPurpose:        purposes[0] || 'General use / no specific reason',
        scannedText,
        imageUri,
        allImages,
      });
    } else {
      setCurrentStep(currentStep + 1);
    }
  };

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.navy} />

      <SafeAreaView style={{ backgroundColor: C.navy }}>
        <View style={s.header}>
          <TouchableOpacity style={s.backBtn} onPress={goBack}>
            <Text style={s.backIcon}>‹</Text>
            <Text style={s.backTxt}>Back</Text>
          </TouchableOpacity>
          <Text style={s.headerTitle}>Why Are You Taking This?</Text>
          <View style={{ width: 64 }} />
        </View>
      </SafeAreaView>

      <ScrollView style={s.scroll} contentContainerStyle={s.content}>

        {/* Progress indicator — only show if multiple supplements */}
        {supplements.length > 1 && (
          <View style={s.progressWrap}>
            <Text style={s.progressTxt}>
              Supplement {currentStep + 1} of {supplements.length}
            </Text>
            <View style={s.progressBar}>
              {supplements.map((_, i) => (
                <View
                  key={i}
                  style={[
                    s.progressDot,
                    { backgroundColor: i <= currentStep ? C.navy : C.border }
                  ]}
                />
              ))}
            </View>
          </View>
        )}

        {/* Supplement name card */}
        <View style={s.suppCard}>
          <Text style={s.suppLabel}>Supplement</Text>
          <Text style={s.suppName}>{currentSupp}</Text>
          <Text style={s.suppSub}>
            Tell us why you are taking this supplement. This helps us check if it is right for your purpose and give you personalised advice.
          </Text>
        </View>

        {/* Common reasons chips */}
        <Text style={s.sectionTitle}>Tap the reason that applies to you:</Text>
        <View style={s.chipsWrap}>
          {COMMON_REASONS.map((reason, i) => {
            const selected = currentPurpose === reason;
            return (
              <TouchableOpacity
                key={i}
                style={[s.chip, selected && s.chipSelected]}
                onPress={() => selectReason(reason)}
                activeOpacity={0.75}
              >
                <Text style={[s.chipTxt, selected && s.chipTxtSelected]}>
                  {reason}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        {/* Or type your own */}
        <Text style={s.orTxt}>— or type your own reason —</Text>
        <TextInput
          style={s.input}
          placeholder={`e.g. I am taking ${currentSupp} for...`}
          placeholderTextColor={C.muted}
          value={currentPurpose}
          onChangeText={updatePurpose}
          multiline
          numberOfLines={3}
        />

        {/* Current selection preview */}
        {currentPurpose.trim() ? (
          <View style={s.selectedBox}>
            <Text style={s.selectedLabel}>Your reason:</Text>
            <Text style={s.selectedTxt}>"{currentPurpose}"</Text>
          </View>
        ) : null}

        {/* Continue button */}
        <TouchableOpacity style={s.continueBtn} onPress={goNext} activeOpacity={0.88}>
          <Text style={s.continueTxt}>
            {isLastStep
              ? '✅  Get Safety Report'
              : `Continue to Next Supplement →`
            }
          </Text>
        </TouchableOpacity>

        {/* Skip option */}
        <TouchableOpacity style={s.skipBtn} onPress={skipPurpose}>
          <Text style={s.skipTxt}>Skip — I don't want to give a reason</Text>
        </TouchableOpacity>

        <View style={s.disclaimer}>
          <Text style={s.disclaimerTxt}>
            Your reason helps us check whether this supplement is appropriate for your purpose. We do not store this information.
          </Text>
        </View>

        <View style={{ height: 30 }} />
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  root:       { flex: 1, backgroundColor: C.bg },
  header:     { backgroundColor: C.navy, flexDirection: 'row', alignItems: 'center',
                justifyContent: 'space-between', paddingHorizontal: 16,
                paddingTop: Platform.OS === 'android' ? 14 : 4, paddingBottom: 14 },
  backBtn:    { flexDirection: 'row', alignItems: 'center', gap: 4, width: 64 },
  backIcon:   { fontSize: 28, color: '#fff', marginTop: -2 },
  backTxt:    { fontSize: 16, color: '#fff', fontWeight: '500' },
  headerTitle:{ fontSize: 17, fontWeight: '700', color: '#fff' },

  scroll:     { flex: 1 },
  content:    { padding: 16, paddingBottom: 40 },

  progressWrap:{ backgroundColor: C.card, borderRadius: 14, padding: 14,
                 marginBottom: 16, borderWidth: 1, borderColor: C.border,
                 alignItems: 'center' },
  progressTxt: { fontSize: 13, color: C.muted, marginBottom: 10, fontWeight: '600' },
  progressBar: { flexDirection: 'row', gap: 8 },
  progressDot: { width: 32, height: 6, borderRadius: 3 },

  suppCard:   { backgroundColor: C.navy, borderRadius: 18, padding: 20, marginBottom: 20 },
  suppLabel:  { fontSize: 11, color: 'rgba(255,255,255,0.6)', fontWeight: '700',
                letterSpacing: 0.8, marginBottom: 6 },
  suppName:   { fontSize: 22, fontWeight: '800', color: '#fff', marginBottom: 8 },
  suppSub:    { fontSize: 13.5, color: 'rgba(255,255,255,0.72)', lineHeight: 20 },

  sectionTitle: { fontSize: 15, fontWeight: '700', color: C.text, marginBottom: 12 },

  chipsWrap:  { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 20 },
  chip:       { backgroundColor: C.card, borderWidth: 1.5, borderColor: C.border,
                paddingHorizontal: 14, paddingVertical: 9, borderRadius: 25 },
  chipSelected:{ backgroundColor: C.navy, borderColor: C.navy },
  chipTxt:    { fontSize: 13.5, color: C.text, fontWeight: '500' },
  chipTxtSelected: { color: '#fff', fontWeight: '700' },

  orTxt:      { fontSize: 13, color: C.muted, textAlign: 'center', marginBottom: 10 },
  input:      { backgroundColor: C.card, borderRadius: 14, borderWidth: 1.5,
                borderColor: C.border, padding: 14, fontSize: 14, color: C.text,
                minHeight: 80, textAlignVertical: 'top', marginBottom: 14 },

  selectedBox:{ backgroundColor: C.greenBg, borderRadius: 12, padding: 14,
                borderWidth: 1, borderColor: C.green, marginBottom: 16 },
  selectedLabel:{ fontSize: 11, fontWeight: '700', color: C.green, marginBottom: 4 },
  selectedTxt:{ fontSize: 14, color: '#065F46', lineHeight: 20 },

  continueBtn:{ backgroundColor: C.navy, paddingVertical: 18, borderRadius: 16,
                alignItems: 'center', marginBottom: 10 },
  continueTxt:{ color: '#fff', fontSize: 16.5, fontWeight: '700' },

  skipBtn:    { paddingVertical: 12, alignItems: 'center', marginBottom: 16 },
  skipTxt:    { fontSize: 13.5, color: C.muted, textDecorationLine: 'underline' },

  disclaimer: { backgroundColor: '#EFF6FF', borderRadius: 12, padding: 14,
                borderLeftWidth: 3, borderLeftColor: C.blue },
  disclaimerTxt: { fontSize: 12.5, color: '#1E40AF', lineHeight: 19 },
});