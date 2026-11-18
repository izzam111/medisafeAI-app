// config.js — backend address, login token on every request, profile and history
import AsyncStorage from '@react-native-async-storage/async-storage';
import axios from 'axios';
import { auth } from './firebase';
import { ageFrom } from './forms';

export const API_BASE = 'http://172.21.251.134:8000';

export const api = axios.create({ baseURL: API_BASE, timeout: 90000 });

// Every request carries the logged-in user's Firebase token, so the backend knows whose data it is.
api.interceptors.request.use(async cfg => {
  const user = auth.currentUser;
  if (user) cfg.headers.Authorization = `Bearer ${await user.getIdToken()}`;
  return cfg;
});

// Turns an axios error into one sentence the user can act on.
export function errorMessage(e) {
  if (e.response?.data?.detail) {
    const d = e.response.data.detail;
    return typeof d === 'string' ? d : 'Please check the details you entered.';
  }
  if (e.code === 'ECONNABORTED') return 'The server took too long to answer. Try again.';
  return `Can't reach the MediSafe server at ${API_BASE}. Check the server is running and the phone is on the same Wi-Fi.`;
}

// Profile is saved to the user's account (Firestore) and cached on the phone for speed.
const PROFILE_KEY = () => `medisafe_profile_${auth.currentUser?.uid || 'guest'}`;

// Returns the profile, or null if this account has none. Server first (it is the real copy), phone copy if offline.
// `missing` is only true when the server itself said "no profile" - a slow network never counts as missing.
export async function getProfile({ withStatus = false } = {}) {
  let cached = null;
  try {
    cached = JSON.parse(await AsyncStorage.getItem(PROFILE_KEY()));
    if (cached?.dob) cached.age = ageFrom(cached.dob);
  } catch { /* nothing cached */ }
  try {
    if (cached?._pending) {                          // saved while offline: send it now
      const { _pending, age, email, photo, ...p } = cached;
      await api.put('/profile', p, { timeout: 15000 });
      cached = { ...cached, _pending: undefined };
      await AsyncStorage.setItem(PROFILE_KEY(), JSON.stringify(cached));
    }
    const res = await api.get('/profile', { timeout: 15000 });
    const prof = res.data.profile;
    if (prof) await AsyncStorage.setItem(PROFILE_KEY(), JSON.stringify(prof));
    const out = prof || cached || null;
    return withStatus ? { profile: out, missing: !out } : out;
  } catch {
    return withStatus ? { profile: cached, missing: false } : cached;
  }
}

// The phone's copy, straight away (no waiting for the server). Screens show this first, then refresh.
export async function cachedProfile() {
  try {
    const c = JSON.parse(await AsyncStorage.getItem(PROFILE_KEY()));
    if (c?.dob) c.age = ageFrom(c.dob);
    return c;
  } catch {
    return null;
  }
}

// offlineOk (used right after sign up): if the server can't be reached, keep it on the phone and send it later.
export async function saveProfile(p, { offlineOk = false } = {}) {
  try {
    await api.put('/profile', p, { timeout: 12000 });  // the server checks it first; only a valid profile is kept
  } catch (e) {
    if (!offlineOk || e.response) throw e;           // a real "this is wrong" answer from the server is always shown
    await AsyncStorage.setItem(PROFILE_KEY(), JSON.stringify({ ...p, age: ageFrom(p.dob), _pending: true }));
    return;
  }
  await AsyncStorage.setItem(PROFILE_KEY(), JSON.stringify({ ...p, age: ageFrom(p.dob) }));
}

// Sign up: is this email / username free? Returns { email_taken, username_taken } (null = couldn't check).
export async function checkAvailable({ email, username }) {
  try {
    const res = await api.post('/auth/available', { email: email || null, username: username || null }, { timeout: 8000 });
    return res.data;
  } catch {
    return { email_taken: null, username_taken: null };
  }
}

// Sign in with a username: the server finds the account's email.
export async function emailForLogin(identifier) {
  const res = await api.post('/auth/login-email', { identifier: identifier.trim() }, { timeout: 10000 });
  return res.data.email;
}

// Profile picture: shrunk on the phone (300 px) and kept in the user's own record.
export async function savePhoto(dataUrl) {
  await api.put('/profile/photo', { image: dataUrl });
}
export async function deletePhoto() {
  await api.delete('/profile/photo');
}

export function describeProfile(p) {
  if (!p) return '';
  const parts = [`${p.sex === 'female' ? 'Female' : 'Male'}, ${p.age}`];
  if (p.sex === 'female' && p.periods === 'irregular') parts.push('oligomenorrhea');
  if (p.pregnant) parts.push('pregnant');
  if (p.breastfeeding) parts.push('breastfeeding');
  return parts.join(', ');
}

// Past checks come from the user's account (kept on the server, so they are there after signing out and back in).
// A copy is kept on the phone per account, so the list shows at once and still shows when the server is slow.
const HISTORY_KEY = () => `medisafe_history_${auth.currentUser?.uid || 'guest'}`;

export async function cachedHistory() {
  try { return JSON.parse(await AsyncStorage.getItem(HISTORY_KEY())); } catch { return null; }
}

export async function getHistory() {
  try {
    const res = await api.get('/history', { timeout: 20000 });
    await AsyncStorage.setItem(HISTORY_KEY(), JSON.stringify(res.data.history));
    return res.data.history;
  } catch {
    return (await cachedHistory()) || [];
  }
}
