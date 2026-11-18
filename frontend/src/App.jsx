import React, { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import Footer from './components/Footer';
import SaharaChatbot from './components/SaharaChatbot';
import NotificationDrawer from './components/NotificationDrawer';
import PortalBar from './apps/portal/PortalBar';
import ResponderApp from './apps/responder/ResponderApp';
import HospitalApp from './apps/hospital/HospitalApp';
import SuperAdminApp from './apps/super-admin/SuperAdminApp';

// Pages
import Home from './pages/Home';
import ReportEmergency from './pages/ReportEmergency';
import TrackRequest from './pages/TrackRequest';
import AdminDashboard from './pages/AdminDashboard';
import PrivacyPolicy from './pages/PrivacyPolicy';
import UserLogin from './pages/UserLogin';
import UserRegister from './pages/UserRegister';
import UserDashboard from './pages/UserDashboard';
import AdminLogin from './pages/AdminLogin';

import {
  fetchHealth,
  fetchStats,
  fetchNotifications,
  markNotificationAsRead,
  getStoredUserSession,
  getStoredAdminSession,
  logoutUser,
  logoutAdmin,
} from './api';
import './App.css';

// Helper to determine initial tab from URL path
function getTabFromPath(pathname) {
  if (pathname.startsWith('/responder')) return 'responder';
  if (pathname.startsWith('/hospital')) return 'hospital';
  if (pathname.startsWith('/super-admin') || pathname === '/admin/root') return 'super_admin';
  if (pathname === '/user/login') return 'user_login';
  if (pathname === '/user/register') return 'user_register';
  if (pathname === '/user/dashboard' || pathname === '/user/history') return 'user_dashboard';
  if (pathname === '/user/report' || pathname === '/report') return 'user_report';
  if (pathname === '/user/track' || pathname === '/track') return 'user_track';
  if (pathname === '/admin/login') return 'admin_login';
  if (pathname.startsWith('/admin')) return 'admin_dashboard';
  if (pathname === '/privacy') return 'privacy';
  return 'home';
}

function getPathFromTab(tab) {
  switch (tab) {
    case 'responder': return '/responder';
    case 'hospital': return '/hospital';
    case 'super_admin': return '/super-admin';
    case 'user_login': return '/user/login';
    case 'user_register': return '/user/register';
    case 'user_dashboard': return '/user/dashboard';
    case 'user_report':
    case 'report': return '/user/report';
    case 'user_track':
    case 'track': return '/user/track';
    case 'admin_login': return '/admin/login';
    case 'admin_dashboard':
    case 'admin': return '/admin/dashboard';
    case 'privacy': return '/privacy';
    case 'home':
    default: return '/';
  }
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState({ total: 5, pending: 2, responded: 2, resolved: 1, critical: 2 });
  const [currentTab, setCurrentTab] = useState(() => {
    if (typeof window !== 'undefined') {
      return getTabFromPath(window.location.pathname);
    }
    return 'home';
  });
  const [activeIncidentCode, setActiveIncidentCode] = useState('CARE-2026-101');
  const [lang, setLang] = useState(() => localStorage.getItem('careon_lang') || 'en');
  const [notifications, setNotifications] = useState([]);
  const [showNotifications, setShowNotifications] = useState(false);

  // Independent Dual Sessions
  const [userSession, setUserSession] = useState(() => getStoredUserSession());
  const [adminSession, setAdminSession] = useState(() => getStoredAdminSession());

  // Handle URL history popstate (Back/Forward browser buttons)
  useEffect(() => {
    const handlePopState = () => {
      setCurrentTab(getTabFromPath(window.location.pathname));
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleLangChange = (newLang) => {
    setLang(newLang);
    localStorage.setItem('careon_lang', newLang);
  };

  const loadSystemData = useCallback(async () => {
    try {
      const [healthData, statsData, notifs] = await Promise.all([
        fetchHealth().catch(() => ({ status: 'degraded' })),
        fetchStats().catch(() => ({ total: 5, pending: 2, responded: 2, resolved: 1, critical: 2 })),
        fetchNotifications().catch(() => []),
      ]);
      setHealth(healthData);
      setStats(statsData);
      setNotifications(notifs);
    } catch (err) {
      console.error('Error fetching system data:', err);
    }
  }, []);

  useEffect(() => {
    loadSystemData();
    const interval = setInterval(loadSystemData, 8000);
    return () => clearInterval(interval);
  }, [loadSystemData]);

  const handleNavigate = (tab, code = null) => {
    if (code) {
      setActiveIncidentCode(code);
    }
    setCurrentTab(tab);
    const targetPath = getPathFromTab(tab);
    if (typeof window !== 'undefined' && window.location.pathname !== targetPath) {
      window.history.pushState(null, '', targetPath);
    }
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleUserLoginSuccess = (user) => {
    setUserSession(user);
    handleNavigate('user_dashboard');
    loadSystemData();
  };

  const handleAdminLoginSuccess = (admin) => {
    setAdminSession(admin);
    handleNavigate('admin_dashboard');
    loadSystemData();
  };

  const handleLogoutUser = () => {
    logoutUser();
    setUserSession(null);
    handleNavigate('home');
  };

  const handleLogoutAdmin = () => {
    logoutAdmin();
    setAdminSession(null);
    handleNavigate('admin_login');
  };

  const handleEmergencySubmitted = (code) => {
    setActiveIncidentCode(code);
    handleNavigate('user_track', code);
    loadSystemData();
  };

  const handleMarkAsRead = async (id) => {
    await markNotificationAsRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    );
  };

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  const currentApp = (() => {
    if (currentTab === 'responder') return 'responder';
    if (currentTab === 'hospital') return 'hospital';
    if (currentTab === 'super_admin') return 'super_admin';
    if (currentTab.startsWith('admin')) return 'dispatcher';
    return 'citizen';
  })();

  const handleSelectApp = (appId) => {
    if (appId === 'citizen') handleNavigate('home');
    else if (appId === 'dispatcher') handleNavigate('admin_dashboard');
    else if (appId === 'responder') handleNavigate('responder');
    else if (appId === 'hospital') handleNavigate('hospital');
    else if (appId === 'super_admin') handleNavigate('super_admin');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      {/* Ecosystem Portal Switcher Bar */}
      <PortalBar currentApp={currentApp} onSelectApp={handleSelectApp} />

      <Header
        health={health}
        onRefresh={loadSystemData}
        currentTab={currentTab}
        onTabChange={handleNavigate}
        lang={lang}
        onLangChange={handleLangChange}
        unreadCount={unreadCount}
        onOpenNotifications={() => setShowNotifications(true)}
        userSession={userSession}
        adminSession={adminSession}
        onLogoutUser={handleLogoutUser}
        onLogoutAdmin={handleLogoutAdmin}
      />

      <main className="container" style={{ flex: 1, padding: '1rem 0' }}>
        {/* Responder Application */}
        {currentTab === 'responder' && (
          <ResponderApp />
        )}

        {/* Hospital Emergency Portal */}
        {currentTab === 'hospital' && (
          <HospitalApp />
        )}

        {/* Super Admin Console */}
        {currentTab === 'super_admin' && (
          <SuperAdminApp />
        )}

        {/* Public Home */}
        {currentTab === 'home' && (
          <Home lang={lang} onNavigate={handleNavigate} />
        )}

        {/* User Portal Pages */}
        {currentTab === 'user_login' && (
          <UserLogin
            lang={lang}
            onLoginSuccess={handleUserLoginSuccess}
            onNavigate={handleNavigate}
          />
        )}

        {currentTab === 'user_register' && (
          <UserRegister
            lang={lang}
            onRegisterSuccess={handleUserLoginSuccess}
            onNavigate={handleNavigate}
          />
        )}

        {currentTab === 'user_dashboard' && (
          <UserDashboard
            lang={lang}
            currentUser={userSession}
            onNavigate={handleNavigate}
            onSelectIncident={(code) => setActiveIncidentCode(code)}
          />
        )}

        {(currentTab === 'user_report' || currentTab === 'report') && (
          <ReportEmergency
            lang={lang}
            onSubmitted={handleEmergencySubmitted}
            currentUser={userSession}
          />
        )}

        {(currentTab === 'user_track' || currentTab === 'track') && (
          <TrackRequest
            lang={lang}
            initialIncidentCode={activeIncidentCode}
            onNavigate={handleNavigate}
          />
        )}

        {/* Admin Portal Pages */}
        {currentTab === 'admin_login' && (
          <AdminLogin
            lang={lang}
            onLoginSuccess={handleAdminLoginSuccess}
            onNavigate={handleNavigate}
          />
        )}

        {(currentTab === 'admin_dashboard' || currentTab === 'admin') && (
          <AdminDashboard
            lang={lang}
            currentUser={adminSession}
            onNavigate={handleNavigate}
          />
        )}

        {/* Privacy & Legal */}
        {currentTab === 'privacy' && (
          <PrivacyPolicy />
        )}
      </main>

      <SaharaChatbot
        lang={lang}
        onNavigate={handleNavigate}
      />

      <NotificationDrawer
        isOpen={showNotifications}
        onClose={() => setShowNotifications(false)}
        notifications={notifications}
        onMarkAsRead={handleMarkAsRead}
      />

      <Footer lang={lang} onTabChange={handleNavigate} />
    </div>
  );
}
