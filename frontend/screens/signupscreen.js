// signupscreen.js — Sign up in a few short steps (no long scrolling form):
//   1 Account (name, email) · 2 Password · 3 About you (date of birth, gender) · 4 Women's health (females only)
import React, { useEffect, useRef, useState } from 'react';
import { View, Text, StyleSheet, Animated } from 'react-native';
import { Formik } from 'formik';
import * as Yup from 'yup';
import { createUserWithEmailAndPassword, updateProfile } from 'firebase/auth';
import { Screen, Button, Notice, Icon, C, T } from '../ui';
import { Field, PasswordField, DobField, Choice, LinkText, PERIOD_OPTIONS, dobToIso, ageFrom } from '../forms';
import { auth, authMessage } from '../firebase';
import { checkAvailable, saveProfile, errorMessage } from '../config';

const NAME = /^[A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF .'-]{1,39}$/;

const STEPS = [
  { title: "Let's get you started", sub: 'Your account details.', fields: ['name', 'email'] },
  { title: 'Keep it safe', sub: 'Choose a password you can remember.', fields: ['password', 'confirm'] },
  { title: 'A little about you', sub: 'This decides which doses are right for you.', fields: ['dob', 'sex'] },
  { title: "Women's health", sub: 'Periods, pregnancy and breastfeeding change what your body needs.', fields: ['periods', 'pregnant', 'breastfeeding'] },
];

const age = v => ageFrom(dobToIso(v));
const asksPregnancy = v => v.sex === 'female' && age(v.dob) >= 12 && age(v.dob) <= 55 && !(age(v.dob) >= 35 && v.periods === 'no');

const schema = Yup.object({
  name: Yup.string().trim().required('Enter your name.').matches(NAME, 'Letters and spaces only, 2-40 characters.'),
  email: Yup.string().trim().required('Enter your email.').email('That email doesn\'t look right.'),
  password: Yup.string().required('Choose a password.').min(8, 'At least 8 characters.')
    .matches(/[A-Za-z]/, 'Use at least one letter.').matches(/\d/, 'Use at least one number.'),
  confirm: Yup.string().required('Type your password again.').oneOf([Yup.ref('password')], "The passwords don't match."),
  dob: Yup.string().required('Enter your date of birth.')
    .test('real', 'Enter a real date as DD/MM/YYYY.', v => !!dobToIso(v))
    .test('range', 'Age must be between 1 and 120.', v => !dobToIso(v) || (age(v) >= 1 && age(v) <= 120)),
  sex: Yup.string().required('Choose one.'),
  periods: Yup.string().nullable().when(['sex', 'dob'], ([sex, dob], sc) =>
    sex === 'female' && age(dob) >= 8 ? sc.required('Choose one.') : sc),
  pregnant: Yup.boolean().nullable().test('asked', 'Choose one.', function (v) { return !asksPregnancy(this.parent) || v !== null; }),
  breastfeeding: Yup.boolean().nullable().test('asked', 'Choose one.', function (v) { return !asksPregnancy(this.parent) || v !== null; }),
});

export default function SignUpScreen({ navigation }) {
  const [step, setStep] = useState(0);
  const [show, setShow] = useState(false);
  const [emailState, setEmailState] = useState(null);  // null | 'checking' | 'free' | 'taken'
  const checked = useRef({});                           // email -> true (taken) / false (free)
  const timer = useRef(null);
  const [error, setError] = useState(null);
  const fade = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    fade.setValue(0);
    Animated.timing(fade, { toValue: 1, duration: 220, useNativeDriver: true }).start();
  }, [step]);

  const lastStep = values => (values.sex === 'female' && age(values.dob) >= 8 ? 3 : 2);

  // Checks the email while the user types (after a short pause), so "already has an account" shows on this page.
  const checkEmail = async (raw) => {
    const email = raw.trim().toLowerCase();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return false;
    if (email in checked.current) { setEmailState(checked.current[email] ? 'taken' : 'free'); return checked.current[email]; }
    setEmailState('checking');
    const r = await checkAvailable({ email });
    if (r.email_taken === null) { setEmailState(null); return false; }   // couldn't check: Firebase will catch it at the end
    checked.current[email] = r.email_taken;
    setEmailState(r.email_taken ? 'taken' : 'free');
    return r.email_taken;
  };
  const onEmail = (t, setFieldValue) => {
    setFieldValue('email', t);
    setEmailState(null);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => checkEmail(t), 600);
  };

  const next = async (form) => {
    const { values, validateForm, setTouched } = form;
    const fields = STEPS[step].fields;
    const errs = await validateForm();
    setTouched(Object.fromEntries(fields.map(k => [k, true])), false);
    if (fields.some(k => errs[k])) return;
    if (step === 0) {                                     // email already used? (usually already checked while typing)
      const taken = await checkEmail(values.email);
      if (taken) return;                                  // message is shown under the email box
    }
    if (step < lastStep(values)) setStep(step + 1);
    else form.submitForm();
  };

  const create = async (v, { setSubmitting }) => {
    setError(null);
    try {
      const female = v.sex === 'female';
      const profile = {
        name: v.name.trim(), dob: dobToIso(v.dob), sex: v.sex,
        periods: female && age(v.dob) >= 8 ? v.periods : null,
        pregnant: asksPregnancy(v) ? !!v.pregnant : false, breastfeeding: asksPregnancy(v) ? !!v.breastfeeding : false,
      };
      const cred = await withTimeout(createUserWithEmailAndPassword(auth, v.email.trim(), v.password), 20000);
      updateProfile(cred.user, { displayName: profile.name }).catch(() => {});
      await saveProfile(profile, { offlineOk: true });    // if the server is slow, it is kept on the phone and sent later
      navigation.reset({ index: 0, routes: [{ name: 'Home' }] });
    } catch (e) {
      if (e.code === 'auth/email-already-in-use') { setStep(0); setEmailState('taken'); return; }
      setError(e.message === 'timeout' ? 'No internet connection. Check your connection and try again.'
        : e.response ? errorMessage(e) : authMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Formik validationSchema={schema} onSubmit={create} validateOnChange={false}
      initialValues={{ name: '', email: '', password: '', confirm: '', dob: '', sex: null,
                       periods: null, pregnant: null, breastfeeding: null }}>
      {form => {
        const { values, errors, touched, handleChange, handleBlur, setFieldValue, isSubmitting } = form;
        const err = k => touched[k] && errors[k];
        const total = (step < 2 || values.sex === null) ? 4 : lastStep(values) + 1;
        const done = step === lastStep(values);
        return (
          <Screen onBack={() => (step ? setStep(step - 1) : navigation.goBack())} scroll={false}
            footer={<>
              <Button label={done ? 'Create account' : 'Continue'} icon={done ? 'checkmark' : 'arrow-forward'}
                onPress={() => next(form)} loading={isSubmitting} />
              <Text style={s.switch}>Already have an account? <LinkText onPress={() => navigation.navigate('Auth')}>Sign in</LinkText></Text>
            </>}>
            <View style={s.body}>
              <View style={s.progress} accessibilityLabel={`Step ${step + 1} of ${total}`}>
                {Array.from({ length: total }, (_, i) => <View key={i} style={[s.bar, i <= step && s.barOn]} />)}
              </View>
              <Text style={s.stepNo}>Step {step + 1} of {total}</Text>
              <Animated.View style={{ opacity: fade, gap: 14 }}>
                <View>
                  <Text style={T.title}>{STEPS[step].title}</Text>
                  <Text style={[T.sub, { marginTop: 4 }]}>{STEPS[step].sub}</Text>
                </View>

                {step === 0 && <>
                  <Field label="Full name" icon="person-outline" value={values.name} onChangeText={handleChange('name')}
                    onBlur={handleBlur('name')} placeholder="e.g. Izza Maryam" autoCapitalize="words" error={err('name')} />
                  <Field label="Email" icon="mail-outline" value={values.email} placeholder="you@example.com"
                    onChangeText={t => onEmail(t, setFieldValue)}
                    onBlur={e => { handleBlur('email')(e); checkEmail(values.email); }} keyboardType="email-address"
                    autoCapitalize="none" autoCorrect={false}
                    error={err('email') || (emailState === 'taken' ? 'This email already has an account.' : null)}
                    hint={emailState === 'checking' ? 'Checking…' : emailState === 'free' ? '✓ Email is free to use' : null} />
                  {emailState === 'taken' ? (
                    <Text style={s.hint}>Is it yours? <LinkText onPress={() => navigation.navigate('Auth')}>Sign in instead</LinkText></Text>
                  ) : null}
                </>}

                {step === 1 && <>
                  <PasswordField label="Password" value={values.password} onChangeText={handleChange('password')}
                    onBlur={handleBlur('password')} placeholder="At least 8 characters, a letter and a number"
                    textContentType="newPassword" show={show} onToggle={() => setShow(v => !v)} error={err('password')} />
                  <PasswordField label="Confirm password" value={values.confirm} onChangeText={handleChange('confirm')}
                    onBlur={handleBlur('confirm')} placeholder="Type it again" show={show} onToggle={() => setShow(v => !v)}
                    error={err('confirm')} />
                  <Strength password={values.password} />
                </>}

                {step === 2 && <>
                  <DobField value={values.dob} onChange={v => setFieldValue('dob', v)} error={err('dob')} />
                  <Choice label="Gender" value={values.sex} error={err('sex')}
                    onChange={v => { setFieldValue('sex', v); if (v === 'male') { setFieldValue('periods', null); setFieldValue('pregnant', null); setFieldValue('breastfeeding', null); } }}
                    options={[{ value: 'male', label: 'Male' }, { value: 'female', label: 'Female' }]} />
                </>}

                {step === 3 && <>
                  <Choice label="Periods" value={values.periods} onChange={v => setFieldValue('periods', v)}
                    error={err('periods')} options={PERIOD_OPTIONS} />
                  {asksPregnancy(values) && <>
                    <Choice label="Are you pregnant?" value={values.pregnant} onChange={v => setFieldValue('pregnant', v)}
                      error={err('pregnant')} options={[{ value: false, label: 'No' }, { value: true, label: 'Yes' }]} />
                    <Choice label="Are you breastfeeding?" value={values.breastfeeding} onChange={v => setFieldValue('breastfeeding', v)}
                      error={err('breastfeeding')} options={[{ value: false, label: 'No' }, { value: true, label: 'Yes' }]} />
                  </>}
                </>}

                {error ? <Notice kind="stop">{error}</Notice> : null}
              </Animated.View>
            </View>
          </Screen>
        );
      }}
    </Formik>
  );
}

// Gives up after `ms` (so a bad connection shows a message instead of loading forever)
const withTimeout = (p, ms) => Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error('timeout')), ms))]);

// Live password checklist
function Strength({ password }) {
  const rules = [['8+ characters', password.length >= 8], ['A letter', /[A-Za-z]/.test(password)], ['A number', /\d/.test(password)]];
  return (
    <View style={s.rules}>
      {rules.map(([label, ok]) => (
        <View key={label} style={s.rule}>
          <Icon name={ok ? 'checkmark-circle' : 'ellipse-outline'} size={16} color={ok ? C.safe : C.faint} />
          <Text style={[T.small, ok && { color: C.safe }]}>{label}</Text>
        </View>
      ))}
    </View>
  );
}

const s = StyleSheet.create({
  body:     { flex: 1, paddingHorizontal: 20, paddingTop: 4 },
  progress: { flexDirection: 'row', gap: 6 },
  bar:      { flex: 1, height: 4, borderRadius: 2, backgroundColor: C.line },
  barOn:    { backgroundColor: C.brand },
  stepNo:   { fontSize: 13, color: C.sub, marginTop: 8, marginBottom: 14 },
  switch:   { textAlign: 'center', fontSize: 15, color: C.sub, marginTop: 4 },
  rules:    { flexDirection: 'row', gap: 16, flexWrap: 'wrap' },
  hint:     { fontSize: 14, color: C.sub, marginTop: -6 },
  rule:     { flexDirection: 'row', alignItems: 'center', gap: 5 },
});
