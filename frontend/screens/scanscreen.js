// scanscreen.js — full-screen camera like the phone's own. One photo is enough; more sides optional.
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, Image, Pressable, StyleSheet, Animated, StatusBar } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import * as Manipulator from 'expo-image-manipulator';
import { Button, Icon, IconCircle, C, T } from '../ui';
import { api, errorMessage } from '../config';

const STEPS = ['Checking the photo', 'Reading the label', 'Checking who made it'];

// The guide frame on screen, as parts of the camera view. Only what is inside it is sent (with a small margin).
const FRAME = { top: 0.18, bottom: 0.30, left: 0.07, right: 0.07 };

// Which part of the photo was inside the frame. The preview fills the screen ("cover"), so the photo is
// scaled and its overflow cut off at the sides; this undoes that to find the frame in photo pixels.
function frameCrop(photoW, photoH, viewW, viewH) {
  const scale = Math.max(viewW / photoW, viewH / photoH);
  const offX = (photoW * scale - viewW) / 2, offY = (photoH * scale - viewH) / 2;
  const fw = viewW * (1 - FRAME.left - FRAME.right), fh = viewH * (1 - FRAME.top - FRAME.bottom);
  const pad = 0.06;                                         // keep a little around the frame, so nothing is cut off
  let x = (viewW * FRAME.left - fw * pad + offX) / scale, y = (viewH * FRAME.top - fh * pad + offY) / scale;
  let w = (fw * (1 + 2 * pad)) / scale, h = (fh * (1 + 2 * pad)) / scale;
  x = Math.max(0, x); y = Math.max(0, y);
  w = Math.min(w, photoW - x); h = Math.min(h, photoH - y);
  return { originX: Math.round(x), originY: Math.round(y), width: Math.round(w), height: Math.round(h) };
}

// Shrink the photo on the phone before sending: about 0.3 MB instead of 3–5 MB, so the upload is quick.
// Camera photos are first cut down to the frame; gallery photos are sent whole.
async function shrink(uri, crop) {
  try {
    const ctx = Manipulator.ImageManipulator.manipulate(uri);
    if (crop && crop.width > 50 && crop.height > 50) ctx.crop(crop);
    ctx.resize({ width: Math.min(1024, crop?.width || 1024) });
    const img = await ctx.renderAsync();
    const out = await img.saveAsync({ compress: 0.7, format: Manipulator.SaveFormat.JPEG });
    return out.uri;
  } catch {
    return uri;                                  // if resizing fails, send the original
  }
}

function Progress({ stage }) {
  const pulse = useRef(new Animated.Value(0.35)).current;
  useEffect(() => {
    const loop = Animated.loop(Animated.sequence([
      Animated.timing(pulse, { toValue: 1, duration: 600, useNativeDriver: true }),
      Animated.timing(pulse, { toValue: 0.35, duration: 600, useNativeDriver: true }),
    ]));
    loop.start();
    return () => loop.stop();
  }, []);
  return (
    <View style={{ gap: 12 }} accessibilityLiveRegion="polite">
      <Text style={T.h2}>Reading your label</Text>
      {STEPS.map((step, i) => {
        const done = i < stage, now = i === stage;
        return (
          <View key={step} style={s.stepRow}>
            {done ? <Icon name="checkmark-circle" size={26} color={C.safe} />
              : now ? <Animated.View style={[s.nowDot, { opacity: pulse }]} />
              : <Icon name="ellipse-outline" size={26} color={C.line} />}
            <Text style={[T.body, { color: done || now ? C.ink : C.faint, fontWeight: now ? '700' : '400' }]}>{step}</Text>
          </View>
        );
      })}
    </View>
  );
}

export default function ScanScreen({ navigation }) {
  const camera = useRef(null);
  const [permission, requestPermission] = useCameraPermissions();
  const [photos, setPhotos]   = useState([]);        // photos already accepted
  const [preview, setPreview] = useState(null);      // photo waiting for "Use photo"
  const [busy, setBusy]       = useState(false);
  const [stage, setStage]     = useState(0);
  const [problem, setProblem] = useState(null);
  const [ready, setReady]     = useState(false);     // the camera must finish starting before a photo can be taken
  const [snapping, setSnapping] = useState(false);
  const [torch, setTorch]     = useState(false);
  const [view, setView]       = useState({ w: 0, h: 0 });   // size of the camera view, to map the frame onto the photo
  useEffect(() => { if (preview) setReady(false); }, [preview]);   // the camera restarts after a retake

  useEffect(() => {
    if (!busy) return;
    setStage(0);
    const t = setInterval(() => setStage(i => Math.min(i + 1, STEPS.length - 1)), 2500);
    return () => clearInterval(t);
  }, [busy]);

  const capture = async () => {
    if (!ready || snapping) return;
    setSnapping(true);
    try {
      const pic = await camera.current?.takePictureAsync({ quality: 0.6 });
      if (pic?.uri) {
        const crop = view.w && pic.width ? frameCrop(pic.width, pic.height, view.w, view.h) : null;
        setPreview(await shrink(pic.uri, crop)); setProblem(null);
      }
      else setProblem("The photo didn't come through. Please try again.");
    } catch {
      setProblem('The camera is still starting. Wait a second and try again.');
    } finally {
      setSnapping(false);
    }
  };

  const pickGallery = async () => {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!perm.granted) return setProblem("Allow MediSafe to use your photos in the phone settings.");
    const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ['images'], quality: 0.8 });
    if (!res.canceled) { setPreview(await shrink(res.assets[0].uri)); setProblem(null); }
  };

  const read = async list => {
    setBusy(true); setProblem(null);
    try {
      const form = new FormData();
      list.forEach((uri, i) => form.append('files', { uri, type: 'image/jpeg', name: `photo_${i + 1}.jpg` }));
      const res = await api.post('/scan-supplement', form, { headers: { 'Content-Type': 'multipart/form-data' } });
      if (!res.data.success) {
        setProblem("This doesn't look like a supplement pack. Try again with the name facing the camera.");
        setPhotos([]); setPreview(null);
      } else {
        navigation.navigate('Confirm', { scan: res.data, photo: list[0] });
        setPhotos([]); setPreview(null);
      }
    } catch (e) {
      setProblem(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const usePhoto = () => read([...photos, preview]);
  const addSide = () => { setPhotos(p => [...p, preview]); setPreview(null); };

  // ── Camera permission not given yet ─────────────────────────────────────────
  if (permission && !permission.granted && !preview) {
    return (
      <SafeAreaView style={s.permRoot}>
        <Pressable onPress={() => navigation.goBack()} style={s.closeLight} accessibilityLabel="Close">
          <Icon name="close" size={26} color={C.ink} />
        </Pressable>
        <View style={s.permBody}>
          <IconCircle name="camera" size={110} />
          <Text style={[T.title, { textAlign: 'center' }]}>Allow the camera to scan your supplement</Text>
          <Text style={[T.sub, { textAlign: 'center' }]}>The photo is only used to read the label.</Text>
        </View>
        <View style={{ padding: 20, gap: 8 }}>
          <Button label="Allow camera" icon="camera" onPress={requestPermission} />
          <Button label="Choose a photo instead" kind="ghost" small onPress={pickGallery} />
        </View>
      </SafeAreaView>
    );
  }

  const showing = preview;

  return (
    <View style={s.root} onLayout={e => setView({ w: e.nativeEvent.layout.width, h: e.nativeEvent.layout.height })}>
      <StatusBar barStyle="light-content" backgroundColor="#000" />
      {showing
        ? <Image source={{ uri: showing }} style={s.previewImg} resizeMode="contain" />
        : <CameraView ref={camera} style={StyleSheet.absoluteFill} facing="back" enableTorch={torch}
            onCameraReady={() => setReady(true)} onMountError={() => setProblem("The camera couldn't start. Choose a photo from the gallery instead.")} />}

      <SafeAreaView edges={['top']} style={s.top}>
        <Pressable onPress={() => navigation.goBack()} style={s.close} accessibilityLabel="Close">
          <Icon name="close" size={26} color="#fff" />
        </Pressable>
        {!showing && (
          <View style={s.hint}>
            <Text style={s.hintTxt}>{photos.length ? 'Now take another side' : 'Fit the name inside the frame'}</Text>
          </View>
        )}
        <View style={{ width: 44 }} />
      </SafeAreaView>

      {!showing && !busy && (
        <>
          {/* everything outside the frame is dimmed: only the inside is sent */}
          <View pointerEvents="none" style={[s.shade, { top: 0, left: 0, right: 0, height: `${FRAME.top * 100}%` }]} />
          <View pointerEvents="none" style={[s.shade, { bottom: 0, left: 0, right: 0, height: `${FRAME.bottom * 100}%` }]} />
          <View pointerEvents="none" style={[s.shade, { top: `${FRAME.top * 100}%`, bottom: `${FRAME.bottom * 100}%`, left: 0, width: `${FRAME.left * 100}%` }]} />
          <View pointerEvents="none" style={[s.shade, { top: `${FRAME.top * 100}%`, bottom: `${FRAME.bottom * 100}%`, right: 0, width: `${FRAME.right * 100}%` }]} />
          <View style={s.frame} pointerEvents="none">
            {['tl', 'tr', 'bl', 'br'].map(k => <View key={k} style={[s.corner, s[k]]} />)}
          </View>
        </>
      )}

      {showing || busy ? (
        <SafeAreaView edges={['bottom']} style={s.sheet}>
          {busy ? <Progress stage={stage} /> : (
            <>
              <Text style={[T.h2, { textAlign: 'center' }]}>Is the name clear?</Text>
              <Button label="Use this photo" icon="checkmark" onPress={usePhoto} />
              <View style={s.row2}>
                <View style={{ flex: 1 }}><Button small kind="secondary" label="Retake" icon="refresh" onPress={() => setPreview(null)} /></View>
                {photos.length < 2 && (
                  <View style={{ flex: 1 }}><Button small kind="secondary" label="Add a side" icon="add" onPress={addSide} /></View>
                )}
              </View>
            </>
          )}
        </SafeAreaView>
      ) : (
        <SafeAreaView edges={['bottom']} style={s.controls}>
          {problem ? <View style={s.problem}><Icon name="alert-circle" size={20} color="#FFB4AB" /><Text style={s.problemTxt}>{problem}</Text></View> : null}
          <View style={s.controlRow}>
            <Pressable onPress={pickGallery} style={s.sideBtn} accessibilityRole="button" accessibilityLabel="Choose from gallery">
              <View style={s.roundBtn}><Icon name="images-outline" size={22} color="#fff" /></View>
              <Text style={s.sideTxt}>Gallery</Text>
            </Pressable>
            <Pressable onPress={capture} disabled={!ready || snapping} style={[s.shutter, (!ready || snapping) && { opacity: 0.4 }]}
              accessibilityRole="button" accessibilityLabel={ready ? 'Take photo' : 'Camera starting'}>
              <View style={s.shutterInner} />
            </Pressable>
            <View style={s.sideBtn}>
              {photos.length > 0 ? (
                <Pressable onPress={() => read(photos)} style={{ alignItems: 'center', gap: 6 }} accessibilityRole="button" accessibilityLabel="Done, read the label">
                  <View style={[s.roundBtn, { backgroundColor: C.brand, borderColor: C.brand }]}><Icon name="checkmark" size={24} color="#fff" /></View>
                  <Text style={s.sideTxt}>Done ({photos.length})</Text>
                </Pressable>
              ) : (
                <Pressable onPress={() => setTorch(t => !t)} style={{ alignItems: 'center', gap: 6 }} accessibilityRole="button"
                  accessibilityLabel={torch ? 'Turn light off' : 'Turn light on'}>
                  <View style={[s.roundBtn, torch && { backgroundColor: '#fff' }]}><Icon name={torch ? 'flash' : 'flash-outline'} size={22} color={torch ? '#000' : '#fff'} /></View>
                  <Text style={s.sideTxt}>Light</Text>
                </Pressable>
              )}
            </View>
          </View>
        </SafeAreaView>
      )}
    </View>
  );
}

const CORNER = 40;
const s = StyleSheet.create({
  root:        { flex: 1, backgroundColor: '#000' },
  top:         { position: 'absolute', top: 0, left: 0, right: 0, flexDirection: 'row', alignItems: 'center',
                 justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 8 },
  close:       { width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(0,0,0,0.45)', alignItems: 'center', justifyContent: 'center' },
  hint:        { backgroundColor: 'rgba(0,0,0,0.45)', borderRadius: 20, paddingHorizontal: 16, paddingVertical: 9 },
  hintTxt:     { color: '#fff', fontSize: 16, fontWeight: '600' },
  frame:       { position: 'absolute', top: `${FRAME.top * 100}%`, bottom: `${FRAME.bottom * 100}%`, left: `${FRAME.left * 100}%`, right: `${FRAME.right * 100}%` },
  shade:       { position: 'absolute', backgroundColor: 'rgba(0,0,0,0.45)' },
  previewImg:  { position: 'absolute', top: 60, left: 0, right: 0, bottom: 260 },
  roundBtn:    { width: 52, height: 52, borderRadius: 26, borderWidth: 1.5, borderColor: 'rgba(255,255,255,0.6)',
                 backgroundColor: 'rgba(255,255,255,0.12)', alignItems: 'center', justifyContent: 'center' },
  corner:      { position: 'absolute', width: CORNER, height: CORNER, borderColor: '#fff' },
  tl:          { top: 0, left: 0, borderTopWidth: 3, borderLeftWidth: 3, borderTopLeftRadius: 12 },
  tr:          { top: 0, right: 0, borderTopWidth: 3, borderRightWidth: 3, borderTopRightRadius: 12 },
  bl:          { bottom: 0, left: 0, borderBottomWidth: 3, borderLeftWidth: 3, borderBottomLeftRadius: 12 },
  br:          { bottom: 0, right: 0, borderBottomWidth: 3, borderRightWidth: 3, borderBottomRightRadius: 12 },
  controls:    { position: 'absolute', bottom: 0, left: 0, right: 0, paddingBottom: 18, paddingTop: 16,
                 backgroundColor: 'rgba(0,0,0,0.35)' },
  controlRow:  { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-around' },
  sideBtn:     { width: 84, alignItems: 'center', gap: 6 },
  galleryIcon: { width: 52, height: 52, borderRadius: 16, backgroundColor: 'rgba(255,255,255,0.22)', alignItems: 'center', justifyContent: 'center' },
  sideTxt:     { color: 'rgba(255,255,255,0.9)', fontSize: 13, fontWeight: '500' },
  shutter:     { width: 78, height: 78, borderRadius: 39, borderWidth: 4, borderColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  shutterInner:{ width: 62, height: 62, borderRadius: 31, backgroundColor: '#fff' },
  problem:     { flexDirection: 'row', gap: 8, alignItems: 'center', marginHorizontal: 16, marginBottom: 14,
                 backgroundColor: 'rgba(58,23,20,0.9)', borderRadius: 14, padding: 12 },
  problemTxt:  { color: '#fff', fontSize: 15, flex: 1, lineHeight: 21 },
  sheet:       { position: 'absolute', bottom: 0, left: 0, right: 0, backgroundColor: '#fff', borderTopLeftRadius: 28,
                 borderTopRightRadius: 28, paddingHorizontal: 20, paddingTop: 22, paddingBottom: 14, gap: 10 },
  row2:        { flexDirection: 'row', gap: 10 },
  stepRow:     { flexDirection: 'row', alignItems: 'center', gap: 12 },
  nowDot:      { width: 26, height: 26, borderRadius: 13, borderWidth: 6, borderColor: C.brand },
  permRoot:    { flex: 1, backgroundColor: '#fff' },
  closeLight:  { width: 44, height: 44, borderRadius: 22, backgroundColor: C.soft, alignItems: 'center', justifyContent: 'center', margin: 16 },
  permBody:    { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, paddingHorizontal: 28 },
});
