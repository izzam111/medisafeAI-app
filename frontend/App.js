// app.js
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import SplashScreen from './screens/splashscreen';
import HomeScreen from './screens/homescreen';
import ScanScreen from './screens/scanscreen';
import PurposeScreen from './screens/purposescreen';
import ResultsScreen from './screens/resultsscreen';

const Stack = createNativeStackNavigator();

export default function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator 
        initialRouteName="Splash" 
        screenOptions={{ headerShown: false }}
      >
        <Stack.Screen name="Splash" component={SplashScreen} />
        <Stack.Screen name="Home" component={HomeScreen} />
        <Stack.Screen name="Scan" component={ScanScreen} />
        <Stack.Screen name="Purpose" component={PurposeScreen} />
        <Stack.Screen name="Results" component={ResultsScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}