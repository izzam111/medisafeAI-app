// App.js — Splash → Sign in / Sign up → Home ⇄ History ⇄ Profile (bottom tabs) → Scan or Search → Confirm → Reasons → Report
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import SplashScreen from './screens/splashscreen';
import AuthScreen from './screens/authscreen';
import SignUpScreen from './screens/signupscreen';
import HomeScreen from './screens/homescreen';
import HistoryScreen from './screens/historyscreen';
import AccountScreen from './screens/accountscreen';
import ProfileScreen from './screens/profilescreen';
import ScanScreen from './screens/scanscreen';
import SearchScreen from './screens/searchscreen';
import ConfirmScreen from './screens/confirmscreen';
import ReasonsScreen from './screens/purposescreen';
import ReportScreen from './screens/resultsscreen';

const Stack = createNativeStackNavigator();
const TAB = { animation: 'none', gestureEnabled: false };            // Home, History and Profile switch instantly, like tabs

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Stack.Navigator initialRouteName="Splash" screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Splash" component={SplashScreen} />
          <Stack.Screen name="Auth" component={AuthScreen} />
          <Stack.Screen name="SignUp" component={SignUpScreen} />
          <Stack.Screen name="Home" component={HomeScreen} options={TAB} />
          <Stack.Screen name="History" component={HistoryScreen} options={TAB} />
          <Stack.Screen name="Profile" component={AccountScreen} options={TAB} />
          <Stack.Screen name="EditProfile" component={ProfileScreen} />
          <Stack.Screen name="Scan" component={ScanScreen} />
          <Stack.Screen name="Search" component={SearchScreen} />
          <Stack.Screen name="Confirm" component={ConfirmScreen} />
          <Stack.Screen name="Reasons" component={ReasonsScreen} />
          <Stack.Screen name="Report" component={ReportScreen} />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
