import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  SafeAreaView,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { mobileApi } from './src/services/api';
import { secureStorage } from './src/services/secureStore';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [profile, setProfile] = useState(null);
  const [activeMission, setActiveMission] = useState(null);

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Required', 'Please enter your email and password');
      return;
    }
    try {
      setLoading(true);
      const data = await mobileApi.login(email, password);
      mobileApi.setAccessToken(data.access_token);
      if (data.refresh_token) {
        await secureStorage.saveRefreshToken(data.refresh_token);
      }
      setIsAuthenticated(true);
      await loadProfile();
    } catch (err) {
      Alert.alert('Login Failed', err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadProfile = async () => {
    try {
      const p = await mobileApi.getProfile();
      setProfile(p);
      setActiveMission(p.active_mission || null);
    } catch (err) {
      console.warn('Profile load error:', err);
    }
  };

  const handleAdvanceStatus = async (newStatus) => {
    if (!activeMission) return;
    try {
      setLoading(true);
      const res = await mobileApi.updateStatus(activeMission.id, newStatus);
      if (newStatus === 'Completed') {
        setActiveMission(null);
      } else {
        setActiveMission(res);
      }
      Alert.alert('Status Updated', `Mission is now: ${newStatus}`);
    } catch (err) {
      Alert.alert('Update Failed', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await secureStorage.clearTokens();
    mobileApi.setAccessToken(null);
    setIsAuthenticated(false);
    setProfile(null);
    setActiveMission(null);
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      {!isAuthenticated ? (
        <View style={styles.loginCard}>
          <Text style={styles.brandTitle}>CAREON FIELD RESPONDER</Text>
          <Text style={styles.brandSubtitle}>Secure Mobile Mission Access</Text>

          <TextInput
            style={styles.input}
            placeholder="Responder Email"
            placeholderTextColor="#64748b"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
          />

          <TextInput
            style={styles.input}
            placeholder="Password"
            placeholderTextColor="#64748b"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
          />

          <TouchableOpacity style={styles.primaryButton} onPress={handleLogin} disabled={loading}>
            {loading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>SIGN IN TO UNIT</Text>
            )}
          </TouchableOpacity>
        </View>
      ) : (
        <ScrollView style={styles.content}>
          <View style={styles.headerRow}>
            <View>
              <Text style={styles.unitCode}>
                {profile?.assigned_resource?.code || 'PARAMEDIC UNIT'}
              </Text>
              <Text style={styles.subtext}>
                {profile?.user?.name} • {profile?.assigned_resource?.name}
              </Text>
            </View>
            <TouchableOpacity onPress={handleLogout} style={styles.logoutBtn}>
              <Text style={styles.logoutText}>LOGOUT</Text>
            </TouchableOpacity>
          </View>

          {activeMission ? (
            <View style={styles.missionCard}>
              <View style={styles.badgeRow}>
                <Text style={styles.badgeEmergency}>CRITICAL DISPATCH</Text>
                <Text style={styles.badgeStatus}>{activeMission.status.toUpperCase()}</Text>
              </View>

              <Text style={styles.missionTitle}>{activeMission.title}</Text>
              <Text style={styles.locationText}>📍 {activeMission.location_name}</Text>
              <Text style={styles.descText}>{activeMission.description}</Text>

              <View style={styles.buttonContainer}>
                {activeMission.status === 'Active' && (
                  <TouchableOpacity
                    style={[styles.primaryButton, { backgroundColor: '#10b981' }]}
                    onPress={() => handleAdvanceStatus('Accepted')}
                  >
                    <Text style={styles.buttonText}>ACCEPT DISPATCH</Text>
                  </TouchableOpacity>
                )}
                {activeMission.status === 'Accepted' && (
                  <TouchableOpacity
                    style={[styles.primaryButton, { backgroundColor: '#3b82f6' }]}
                    onPress={() => handleAdvanceStatus('En Route')}
                  >
                    <Text style={styles.buttonText}>EN ROUTE TO SCENE</Text>
                  </TouchableOpacity>
                )}
                {activeMission.status === 'En Route' && (
                  <TouchableOpacity
                    style={[styles.primaryButton, { backgroundColor: '#f59e0b' }]}
                    onPress={() => handleAdvanceStatus('On Scene')}
                  >
                    <Text style={styles.buttonText}>ARRIVED ON SCENE</Text>
                  </TouchableOpacity>
                )}
                {activeMission.status === 'On Scene' && (
                  <TouchableOpacity
                    style={[styles.primaryButton, { backgroundColor: '#8b5cf6' }]}
                    onPress={() => handleAdvanceStatus('Transporting')}
                  >
                    <Text style={styles.buttonText}>TRANSPORTING TO HOSPITAL</Text>
                  </TouchableOpacity>
                )}
                {activeMission.status === 'Transporting' && (
                  <TouchableOpacity
                    style={[styles.primaryButton, { backgroundColor: '#10b981' }]}
                    onPress={() => handleAdvanceStatus('Completed')}
                  >
                    <Text style={styles.buttonText}>COMPLETE / HANDOVER</Text>
                  </TouchableOpacity>
                )}
              </View>
            </View>
          ) : (
            <View style={styles.idleCard}>
              <Text style={styles.idleTitle}>Unit Standing By</Text>
              <Text style={styles.idleDesc}>
                No active missions assigned. Listening for dispatch notifications.
              </Text>
            </View>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#090d16',
  },
  loginCard: {
    flex: 1,
    justifyContent: 'center',
    padding: 24,
  },
  brandTitle: {
    color: '#ef4444',
    fontSize: 22,
    fontWeight: '800',
    textAlign: 'center',
    letterSpacing: 1,
  },
  brandSubtitle: {
    color: '#94a3b8',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 32,
    marginTop: 6,
  },
  input: {
    backgroundColor: '#111827',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    color: '#fff',
    padding: 14,
    fontSize: 16,
    marginBottom: 16,
  },
  primaryButton: {
    backgroundColor: '#ef4444',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 15,
  },
  content: {
    flex: 1,
    padding: 16,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#111827',
    padding: 16,
    borderRadius: 12,
    marginBottom: 16,
  },
  unitCode: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '800',
  },
  subtext: {
    color: '#94a3b8',
    fontSize: 12,
    marginTop: 4,
  },
  logoutBtn: {
    padding: 8,
  },
  logoutText: {
    color: '#ef4444',
    fontSize: 12,
    fontWeight: '700',
  },
  missionCard: {
    backgroundColor: '#131c2e',
    borderWidth: 2,
    borderColor: '#ef4444',
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
  },
  badgeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  badgeEmergency: {
    backgroundColor: '#ef4444',
    color: '#fff',
    fontSize: 10,
    fontWeight: '800',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  badgeStatus: {
    color: '#60a5fa',
    fontSize: 12,
    fontWeight: '700',
  },
  missionTitle: {
    color: '#fff',
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 8,
  },
  locationText: {
    color: '#cbd5e1',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
  },
  descText: {
    color: '#94a3b8',
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 20,
  },
  buttonContainer: {
    gap: 10,
  },
  idleCard: {
    backgroundColor: '#111827',
    borderRadius: 12,
    padding: 32,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#1e293b',
  },
  idleTitle: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 8,
  },
  idleDesc: {
    color: '#94a3b8',
    fontSize: 13,
    textAlign: 'center',
  },
});
