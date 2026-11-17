// firebase.js — Firebase login (email + password). Paste your project's web config below.
// Firebase console → Project settings → General → Your apps → Web app → "SDK setup and configuration" → Config
import { initializeApp } from 'firebase/app';
import { initializeAuth, getReactNativePersistence } from 'firebase/auth';
import AsyncStorage from '@react-native-async-storage/async-storage';

const firebaseConfig = {
  apiKey: 'AIzaSyBja2ZUAox5bqq1rYJnwB-EgxDoW37IqTQ',
  authDomain: 'medisafe-72256.firebaseapp.com',
  projectId: 'medisafe-72256',
  storageBucket: 'medisafe-72256.firebasestorage.app',
  messagingSenderId: '1044786536177',
  appId: '1:1044786536177:web:15219544c78e996db39350',
};

export const firebaseReady = !firebaseConfig.apiKey.startsWith('PASTE');

const app = initializeApp(firebaseConfig);

// Keeps the user logged in after closing the app.
export const auth = initializeAuth(app, { persistence: getReactNativePersistence(AsyncStorage) });

// Firebase error codes → one plain sentence for the user.
export function authMessage(e) {
  const code = e?.code || '';
  if (code.includes('invalid-credential') || code.includes('wrong-password') || code.includes('user-not-found'))
    return 'Email or password is wrong.';
  if (code.includes('email-already-in-use')) return 'An account with this email already exists. Log in instead.';
  if (code.includes('invalid-email')) return 'That email address is not valid.';
  if (code.includes('weak-password')) return 'Password must be at least 6 characters.';
  if (code.includes('network')) return 'No internet connection. Check your connection and try again.';
  if (code.includes('too-many-requests')) return 'Too many tries. Wait a minute and try again.';
  return 'Something went wrong. Please try again.';
}
