// authscreen.js — Sign in (email or username + password). New users tap "Sign up" below.
import React, { useState } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Formik } from 'formik';
import * as Yup from 'yup';
import { signInWithEmailAndPassword, sendPasswordResetEmail } from 'firebase/auth';
import { Screen, Button, Notice, Logo, C, T } from '../ui';
import { Field, PasswordField, LinkText } from '../forms';
import { auth, authMessage, firebaseReady } from '../firebase';
import { api, emailForLogin, errorMessage } from '../config';

const schema = Yup.object({
  identifier: Yup.string().trim().required('Enter your email or username.')
    .test('looks-right', 'Enter a valid email, or a username of 3-20 characters.',
      v => !v || (v.includes('@') ? Yup.string().email().isValidSync(v) : /^[A-Za-z0-9_.]{3,20}$/.test(v))),
  password: Yup.string().required('Enter your password.'),
});

export default function AuthScreen({ navigation }) {
  const [show, setShow] = useState(false);
  const [msg, setMsg]   = useState(null);          // { kind, text }

  const signIn = async ({ identifier, password }, { setSubmitting }) => {
    setMsg(null);
    try {
      let email = identifier.trim();
      if (!email.includes('@')) email = await emailForLogin(email);       // username → the account's email
      await signInWithEmailAndPassword(auth, email, password);
      navigation.replace('Home');
    } catch (e) {
      setMsg({ kind: 'stop', text: e.response ? errorMessage(e) : authMessage(e) });
    } finally {
      setSubmitting(false);
    }
  };

  const forgot = async identifier => {
    setMsg(null);
    try {
      const email = identifier.includes('@') ? identifier.trim() : await emailForLogin(identifier);
      const check = await api.post('/account-exists', { email }, { timeout: 8000 }).catch(() => null);
      if (check?.data?.exists === false) return setMsg({ kind: 'caution', text: `There is no account with ${email}.` });
      await sendPasswordResetEmail(auth, email);
      setMsg({ kind: 'ok', text: `We sent a reset link to ${email}. Check your spam folder too.` });
    } catch (e) {
      setMsg({ kind: 'stop', text: e.response ? errorMessage(e) : authMessage(e) });
    }
  };

  return (
    <Formik initialValues={{ identifier: '', password: '' }} validationSchema={schema} onSubmit={signIn}>
      {({ values, errors, touched, handleChange, handleBlur, handleSubmit, isSubmitting }) => (
        <Screen>
          <View style={s.brand}>
            <Logo size={64} />
            <Text style={s.name}>MediSafe AI</Text>
            <Text style={s.motto}>Know what you take, before you take it.</Text>
          </View>

          {!firebaseReady && <Notice kind="caution" title="Firebase is not set up yet">Paste your Firebase web config into frontend/firebase.js.</Notice>}

          <Text style={[T.h2, { marginBottom: 14 }]}>Sign in</Text>
          <View style={{ gap: 14 }}>
            <Field label="Email or username" icon="person-outline" value={values.identifier}
              onChangeText={handleChange('identifier')} onBlur={handleBlur('identifier')}
              placeholder="you@example.com or username" autoCapitalize="none" autoCorrect={false}
              keyboardType="email-address" textContentType="username"
              error={touched.identifier && errors.identifier} />
            <PasswordField label="Password" value={values.password} onChangeText={handleChange('password')}
              onBlur={handleBlur('password')} placeholder="Your password" textContentType="password"
              show={show} onToggle={() => setShow(v => !v)} error={touched.password && errors.password} />
          </View>

          <View style={s.row}>
            <LinkText onPress={() => values.identifier.trim().length >= 3
              ? forgot(values.identifier)
              : setMsg({ kind: 'caution', text: 'Type your email or username first.' })}>Forgot password?</LinkText>
          </View>

          {msg ? <View style={{ marginTop: 14 }}><Notice kind={msg.kind}>{msg.text}</Notice></View> : null}

          <View style={{ marginTop: 22 }}>
            <Button label="Sign in" onPress={handleSubmit} loading={isSubmitting} disabled={!firebaseReady} />
          </View>

          <Text style={s.switch}>
            Don't have an account? <LinkText onPress={() => navigation.navigate('SignUp')}>Sign up</LinkText>
          </Text>
        </Screen>
      )}
    </Formik>
  );
}

const s = StyleSheet.create({
  brand:  { alignItems: 'center', gap: 6, marginTop: 28, marginBottom: 34 },
  name:   { fontSize: 26, fontWeight: '800', color: C.ink, marginTop: 8 },
  motto:  { fontSize: 15, color: C.sub, fontStyle: 'italic' },
  row:    { alignItems: 'flex-end', marginTop: 10 },
  switch: { textAlign: 'center', fontSize: 15, color: C.sub, marginTop: 24 },
});
