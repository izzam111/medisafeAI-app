// profilescreen.js — Edit profile (Formik). Name, username, date of birth, gender and women's health.
// Also used once for older accounts that have no profile yet (route param `next` = where to go after saving).
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { Formik } from 'formik';
import * as Yup from 'yup';
import { Screen, Button, Notice, C, T } from '../ui';
import { Field, DobField, Choice, PERIOD_OPTIONS, dobToIso, isoToDob, ageFrom } from '../forms';
import { getProfile, saveProfile, checkAvailable, errorMessage } from '../config';
import { auth } from '../firebase';

const NAME = /^[A-Za-z\u0600-\u06FF][A-Za-z\u0600-\u06FF .'-]{1,39}$/;
const age = v => ageFrom(dobToIso(v));
const asksPeriods = v => v.sex === 'female' && age(v.dob) >= 8;
const asksPregnancy = v => v.sex === 'female' && age(v.dob) >= 12 && age(v.dob) <= 55 && !(age(v.dob) >= 35 && v.periods === 'no');

const schema = Yup.object({
  name: Yup.string().trim().required('Enter your name.').matches(NAME, 'Letters and spaces only, 2-40 characters.'),
  username: Yup.string().trim().nullable().matches(/^[A-Za-z0-9_.]{3,20}$/, { message: '3-20 characters: letters, numbers, dot or underscore.', excludeEmptyString: true }),
  dob: Yup.string().required('Enter your date of birth.')
    .test('real', 'Enter a real date as DD/MM/YYYY.', v => !!dobToIso(v))
    .test('range', 'Age must be between 1 and 120.', v => !dobToIso(v) || (age(v) >= 1 && age(v) <= 120)),
  sex: Yup.string().nullable().required('Choose one.'),
  periods: Yup.string().nullable().test('asked', 'Choose one.', function (v) { return !asksPeriods(this.parent) || !!v; }),
  pregnant: Yup.boolean().nullable().test('asked', 'Choose one.', function (v) { return !asksPregnancy(this.parent) || v !== null; }),
  breastfeeding: Yup.boolean().nullable().test('asked', 'Choose one.', function (v) { return !asksPregnancy(this.parent) || v !== null; }),
});

export default function ProfileScreen({ route, navigation }) {
  const next = route.params?.next;
  const [start, setStart] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getProfile().then(p => setStart({
      name: p?.name || auth.currentUser?.displayName || '', username: p?.username || '',
      dob: isoToDob(p?.dob), sex: p?.sex || null, periods: p?.periods || null,
      pregnant: p?.pregnant ?? null, breastfeeding: p?.breastfeeding ?? null, _old: p,
    }));
  }, []);

  const save = async (v, { setSubmitting, setFieldError }) => {
    setError(null);
    try {
      const username = v.username.trim().toLowerCase() || null;
      if (username && username !== v._old?.username) {
        const r = await checkAvailable({ username });
        if (r.username_taken) { setFieldError('username', 'This username is taken. Try another.'); return; }
      }
      await saveProfile({
        name: v.name.trim(), username, dob: dobToIso(v.dob), sex: v.sex,
        periods: asksPeriods(v) ? v.periods : null,
        pregnant: asksPregnancy(v) ? !!v.pregnant : false, breastfeeding: asksPregnancy(v) ? !!v.breastfeeding : false,
      });
      next ? navigation.replace(next) : navigation.goBack();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (!start) return <Screen title="Edit profile" onBack={() => navigation.goBack()}><ActivityIndicator color={C.brand} style={{ marginTop: 40 }} /></Screen>;

  return (
    <Formik initialValues={start} validationSchema={schema} onSubmit={save}>
      {({ values, errors, touched, handleChange, handleBlur, setFieldValue, handleSubmit, isSubmitting }) => {
        const err = k => touched[k] && errors[k];
        return (
          <Screen title={next ? 'Your health profile' : 'Edit profile'} onBack={() => navigation.goBack()} bg={C.soft}
            footer={<Button label="Save" icon="checkmark" onPress={handleSubmit} loading={isSubmitting} />}>
            {next ? <Text style={[T.sub, { marginBottom: 14 }]}>We need this once, to check if a supplement and its dose are right for you.</Text> : null}

            <Text style={s.group}>Account</Text>
            <View style={s.card}>
              <Field label="Full name" icon="person-outline" value={values.name} onChangeText={handleChange('name')}
                onBlur={handleBlur('name')} autoCapitalize="words" error={err('name')} />
              <Field label="Username" icon="at" value={values.username} onChangeText={handleChange('username')}
                onBlur={handleBlur('username')} autoCapitalize="none" autoCorrect={false} error={err('username')} />
            </View>

            <Text style={s.group}>About you</Text>
            <View style={s.card}>
              <DobField value={values.dob} onChange={v => setFieldValue('dob', v)} error={err('dob')} />
              <Choice label="Gender" value={values.sex} onChange={v => setFieldValue('sex', v)} error={err('sex')}
                options={[{ value: 'male', label: 'Male' }, { value: 'female', label: 'Female' }]} />
            </View>

            {asksPeriods(values) && <>
              <Text style={s.group}>Women's health</Text>
              <View style={s.card}>
                <Choice label="Periods" value={values.periods} onChange={v => setFieldValue('periods', v)}
                  error={err('periods')} options={PERIOD_OPTIONS} />
                {asksPregnancy(values) && <>
                  <Choice label="Are you pregnant?" value={values.pregnant} onChange={v => setFieldValue('pregnant', v)}
                    error={err('pregnant')} options={[{ value: false, label: 'No' }, { value: true, label: 'Yes' }]} />
                  <Choice label="Are you breastfeeding?" value={values.breastfeeding} onChange={v => setFieldValue('breastfeeding', v)}
                    error={err('breastfeeding')} options={[{ value: false, label: 'No' }, { value: true, label: 'Yes' }]} />
                </>}
              </View>
            </>}

            {error ? <View style={{ marginTop: 12 }}><Notice kind="stop">{error}</Notice></View> : null}
          </Screen>
        );
      }}
    </Formik>
  );
}

const s = StyleSheet.create({
  group: { fontSize: 13, fontWeight: '700', color: C.sub, letterSpacing: 0.8, textTransform: 'uppercase', marginTop: 16, marginBottom: 8, marginLeft: 4 },
  card:  { backgroundColor: '#fff', borderRadius: 14, borderWidth: 1, borderColor: C.line, padding: 16, gap: 16 },
});
