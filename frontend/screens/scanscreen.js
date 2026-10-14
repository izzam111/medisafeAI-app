// scanscreen.js — MediSafe AI
// FIXED: passes extracted_supplement_names (not raw OCR) to purposescreen
// Supports scanning up to 4 supplement images

import React, { useState, useRef } from 'react';
import {
  View, Text, TouchableOpacity, Image, ScrollView,
  StyleSheet, StatusBar, SafeAreaView, ActivityIndicator,
  Alert, Platform
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import axios from 'axios';

const API_BASE = 'http://172.21.17.231:8000';

const C = {
  primary: '#0D1B3E', primary2: '#1A3A7A', accent: '#4A9FFF',
  bg: '#F2F4F8', card: '#FFFFFF', border: '#DDE3EE',
  muted: '#7A8AAA', text: '#111827', textSub: '#4B5563',
  green: '#10B981', red: '#EF4444',
};

export default function ScanScreen({ navigation }) {
  const [images, setImages]         = useState([]);   // [{uri, file}]
  const [scanning, setScanning]     = useState(false);
  const [scanned, setScanned]       = useState(null); // API response
  const [error, setError]           = useState(null);

  const MAX_IMAGES = 4;

  // ── Pick image ────────────────────────────────────────────────────────────
  const pickImage = async () => {
    if (images.length >= MAX_IMAGES) {
      Alert.alert('Maximum reached', `You can scan up to ${MAX_IMAGES} supplements.`);
      return;
    }
    const result = await ImagePicker.launchCameraAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.85,
      allowsEditing: true,
    });
    if (!result.canceled && result.assets?.length > 0) {
      setImages(prev => [...prev, result.assets[0]]);
      setScanned(null);
      setError(null);
    }
  };

  const pickFromGallery = async () => {
    if (images.length >= MAX_IMAGES) {
      Alert.alert('Maximum reached', `You can scan up to ${MAX_IMAGES} supplements.`);
      return;
    }
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Images,
      quality: 0.85,
    });
    if (!result.canceled && result.assets?.length > 0) {
      setImages(prev => [...prev, result.assets[0]]);
      setScanned(null);
      setError(null);
    }
  };

  const removeImage = (index) => {
    setImages(prev => prev.filter((_, i) => i !== index));
    setScanned(null);
    setError(null);
  };

  // ── Scan all images ───────────────────────────────────────────────────────
  const scanImages = async () => {
    if (images.length === 0) {
      Alert.alert('No images', 'Please take or select at least one supplement photo.');
      return;
    }
    setScanning(true);
    setError(null);
    try {
      const formData = new FormData();
      images.forEach((img, idx) => {
        formData.append('files', {
          uri: img.uri,
          type: 'image/jpeg',
          name: `supplement_${idx + 1}.jpg`,
        });
      });

      const res = await axios.post(`${API_BASE}/scan-supplement`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      });

      if (!res.data.success) {
        setError(res.data.message || 'Some images were not recognised as supplements.');
        return;
      }

      setScanned(res.data);
    } catch (e) {
      setError(e.message || 'Connection failed. Make sure the backend is running.');
    } finally {
      setScanning(false);
    }
  };

  // ── Proceed to purpose screen ─────────────────────────────────────────────
  // KEY FIX: Use extracted_supplement_names, NOT raw scannedText
  const proceed = () => {
    if (!scanned) return;

    const extractedNames = scanned.extracted_supplement_names || [];
    const scannedText    = scanned.extracted_text || '';

    // Build supplement names list — prefer extracted names, fall back to OCR text
    const supplementNames = extractedNames.length > 0
      ? extractedNames
      : scannedText ? [scannedText] : [];

    if (supplementNames.length === 0) {
      Alert.alert('No supplement found', 'Could not identify any supplement. Please try a clearer image.');
      return;
    }

    navigation.navigate('Purpose', {
      // Pass the CLEAN extracted name(s), not full OCR garbage
      supplementName: supplementNames[0],          // primary supplement
      allSupplementNames: supplementNames,          // all scanned supplements
      scannedText: scannedText,                     // raw OCR for reference
      imageUri: images[0]?.uri || null,
      allImages: images.map(img => img.uri),
    });
  };

  return (
    <View style={s.root}>
      <StatusBar barStyle="light-content" backgroundColor={C.primary} />
      <SafeAreaView style={{ backgroundColor: C.primary }}>
        <View style={s.header}>
          <TouchableOpacity onPress={() => navigation.goBack()} style={s.backBtn}>
            <Text style={s.backIcon}>‹</Text><Text style={s.backTxt}>Back</Text>
          </TouchableOpacity>
          <Text style={s.headerTitle}>Scan Supplement</Text>
          <View style={{ width: 64 }} />
        </View>
      </SafeAreaView>

      <ScrollView style={s.scroll} contentContainerStyle={s.scrollContent}>

        {/* Instructions */}
        <View style={s.instructionCard}>
          <Text style={s.instructionTitle}>📸  How to scan</Text>
          <Text style={s.instructionTxt}>
            Take a clear photo of the supplement label — make sure the product name is visible.
            You can scan up to 4 supplements to check interactions.
          </Text>
        </View>

        {/* Image thumbnails */}
        {images.length > 0 && (
          <View style={s.imageGrid}>
            {images.map((img, idx) => (
              <View key={idx} style={s.thumbWrap}>
                <Image source={{ uri: img.uri }} style={s.thumb} resizeMode="cover" />
                <View style={s.thumbBadge}>
                  <Text style={s.thumbBadgeTxt}>#{idx + 1}</Text>
                </View>
                <TouchableOpacity style={s.removeBtn} onPress={() => removeImage(idx)}>
                  <Text style={s.removeTxt}>✕</Text>
                </TouchableOpacity>
              </View>
            ))}
            {images.length < MAX_IMAGES && (
              <TouchableOpacity style={s.addMoreBtn} onPress={pickImage}>
                <Text style={s.addMoreIcon}>+</Text>
                <Text style={s.addMoreTxt}>Add More</Text>
              </TouchableOpacity>
            )}
          </View>
        )}

        {/* Camera / Gallery buttons */}
        {images.length === 0 && (
          <View style={s.scanButtons}>
            <TouchableOpacity style={s.cameraBtn} onPress={pickImage} activeOpacity={0.88}>
              <Text style={s.cameraBtnIcon}>📷</Text>
              <Text style={s.cameraBtnTxt}>Take Photo</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.galleryBtn} onPress={pickFromGallery} activeOpacity={0.88}>
              <Text style={s.galleryBtnIcon}>🖼️</Text>
              <Text style={s.galleryBtnTxt}>From Gallery</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Scan result */}
        {scanned && (
          <View style={s.resultCard}>
            <Text style={s.resultTitle}>✅  Scan Complete</Text>
            {(scanned.extracted_supplement_names || []).map((name, idx) => (
              <View key={idx} style={s.resultRow}>
                <Text style={s.resultIcon}>💊</Text>
                <Text style={s.resultName}>{name}</Text>
              </View>
            ))}
            {(!scanned.extracted_supplement_names || scanned.extracted_supplement_names.length === 0) && (
              <Text style={s.resultFallback}>
                Extracted: {(scanned.extracted_text || '').slice(0, 80)}…
              </Text>
            )}
          </View>
        )}

        {/* Error */}
        {error && (
          <View style={s.errorCard}>
            <Text style={s.errorTitle}>⚠️  Problem</Text>
            <Text style={s.errorTxt}>{error}</Text>
          </View>
        )}

        {/* Scan button */}
        {images.length > 0 && !scanned && !scanning && (
          <TouchableOpacity style={s.scanBtn} onPress={scanImages} activeOpacity={0.88}>
            <Text style={s.scanBtnTxt}>🔍  Scan {images.length} Supplement{images.length > 1 ? 's' : ''}</Text>
          </TouchableOpacity>
        )}

        {/* Loading */}
        {scanning && (
          <View style={s.loadingBox}>
            <ActivityIndicator size="large" color={C.accent} />
            <Text style={s.loadingTxt}>Scanning with AI…</Text>
            <Text style={s.loadingSub}>OCR reading label · CLIP validating image</Text>
          </View>
        )}

        {/* Proceed */}
        {scanned && (
          <TouchableOpacity style={s.proceedBtn} onPress={proceed} activeOpacity={0.88}>
            <Text style={s.proceedTxt}>Continue → Tell us why you take this  ›</Text>
          </TouchableOpacity>
        )}

        {/* Re-scan */}
        {images.length > 0 && (
          <TouchableOpacity style={s.rescanBtn} onPress={() => { setImages([]); setScanned(null); setError(null); }}>
            <Text style={s.rescanTxt}>↺  Start Over</Text>
          </TouchableOpacity>
        )}

      </ScrollView>

      <SafeAreaView style={{ backgroundColor: C.card }}>
        <View style={s.footer}><Text style={s.footerTxt}>⚕️ For informational use only · Always consult your doctor</Text></View>
      </SafeAreaView>
    </View>
  );
}

const s = StyleSheet.create({
  root:          { flex:1, backgroundColor:C.bg },
  header:        { backgroundColor:C.primary, flexDirection:'row', alignItems:'center', justifyContent:'space-between', paddingHorizontal:16, paddingTop:Platform.OS==='android'?14:4, paddingBottom:14 },
  backBtn:       { flexDirection:'row', alignItems:'center', gap:2, width:64 },
  backIcon:      { fontSize:28, color:'#fff', marginTop:-2 },
  backTxt:       { fontSize:16, color:'#fff', fontWeight:'500' },
  headerTitle:   { fontSize:17, fontWeight:'700', color:'#fff' },
  scroll:        { flex:1 },
  scrollContent: { padding:16, paddingBottom:40 },
  instructionCard:{ backgroundColor:C.card, borderRadius:14, padding:14, marginBottom:16, borderWidth:1, borderColor:C.border },
  instructionTitle:{ fontSize:15, fontWeight:'700', color:C.primary, marginBottom:6 },
  instructionTxt:{ fontSize:13, color:C.textSub, lineHeight:19 },
  imageGrid:     { flexDirection:'row', flexWrap:'wrap', gap:10, marginBottom:16 },
  thumbWrap:     { width:90, height:90, borderRadius:10, overflow:'hidden', position:'relative' },
  thumb:         { width:'100%', height:'100%' },
  thumbBadge:    { position:'absolute', top:4, left:4, backgroundColor:'rgba(13,27,62,0.7)', paddingHorizontal:6, paddingVertical:2, borderRadius:6 },
  thumbBadgeTxt: { color:'#fff', fontSize:10, fontWeight:'700' },
  removeBtn:     { position:'absolute', top:4, right:4, backgroundColor:'rgba(239,68,68,0.85)', width:22, height:22, borderRadius:11, alignItems:'center', justifyContent:'center' },
  removeTxt:     { color:'#fff', fontSize:12, fontWeight:'700' },
  addMoreBtn:    { width:90, height:90, borderRadius:10, borderWidth:2, borderColor:C.accent, borderStyle:'dashed', alignItems:'center', justifyContent:'center' },
  addMoreIcon:   { fontSize:24, color:C.accent },
  addMoreTxt:    { fontSize:11, color:C.accent, fontWeight:'600', marginTop:2 },
  scanButtons:   { gap:12, marginBottom:16 },
  cameraBtn:     { backgroundColor:C.primary, paddingVertical:18, borderRadius:14, alignItems:'center', flexDirection:'row', justifyContent:'center', gap:10 },
  cameraBtnIcon: { fontSize:22 },
  cameraBtnTxt:  { color:'#fff', fontSize:16, fontWeight:'700' },
  galleryBtn:    { backgroundColor:C.card, paddingVertical:16, borderRadius:14, alignItems:'center', borderWidth:1.5, borderColor:C.border, flexDirection:'row', justifyContent:'center', gap:10 },
  galleryBtnIcon:{ fontSize:22 },
  galleryBtnTxt: { color:C.text, fontSize:15, fontWeight:'600' },
  resultCard:    { backgroundColor:'#ECFDF5', borderRadius:12, padding:14, marginBottom:16, borderWidth:1.5, borderColor:'#6EE7B7' },
  resultTitle:   { fontSize:15, fontWeight:'700', color:'#065F46', marginBottom:10 },
  resultRow:     { flexDirection:'row', alignItems:'center', gap:8, marginBottom:6 },
  resultIcon:    { fontSize:18 },
  resultName:    { fontSize:15, fontWeight:'600', color:'#065F46' },
  resultFallback:{ fontSize:12, color:C.muted, fontStyle:'italic' },
  errorCard:     { backgroundColor:'#FEF2F2', borderRadius:12, padding:14, marginBottom:16, borderWidth:1.5, borderColor:'#FCA5A5' },
  errorTitle:    { fontSize:14, fontWeight:'700', color:'#991B1B', marginBottom:4 },
  errorTxt:      { fontSize:13, color:'#B91C1C', lineHeight:19 },
  scanBtn:       { backgroundColor:'#1A3A7A', paddingVertical:16, borderRadius:14, alignItems:'center', marginBottom:12 },
  scanBtnTxt:    { color:'#fff', fontSize:16, fontWeight:'700' },
  loadingBox:    { alignItems:'center', padding:24, gap:8 },
  loadingTxt:    { fontSize:16, fontWeight:'600', color:C.text },
  loadingSub:    { fontSize:12, color:C.muted },
  proceedBtn:    { backgroundColor:C.primary, paddingVertical:18, borderRadius:14, alignItems:'center', marginBottom:12 },
  proceedTxt:    { color:'#fff', fontSize:16, fontWeight:'700' },
  rescanBtn:     { paddingVertical:12, alignItems:'center' },
  rescanTxt:     { color:C.muted, fontSize:14, fontWeight:'600' },
  footer:        { backgroundColor:C.card, borderTopWidth:1, borderTopColor:C.border, paddingVertical:10, alignItems:'center' },
  footerTxt:     { fontSize:11.5, color:C.muted },
});
