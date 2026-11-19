import React, { useState, useEffect } from 'react';
import * as apiClient from '@careon/api-client';
import { AuthProvider, useAuth } from '@careon/auth';
import { CitizenNav } from './components/CitizenNav.jsx';
import { CitizenFooter } from './components/CitizenFooter.jsx';
import { OfflineBanner } from './components/OfflineBanner.jsx';
import { InstallPrompt } from './components/InstallPrompt.jsx';

import { Home } from './pages/Home.jsx';
import { ReportEmergency } from './pages/ReportEmergency.jsx';
import { TrackIncident } from './pages/TrackIncident.jsx';
import { CitizenDashboard } from './pages/CitizenDashboard.jsx';
import { EmergencyHistory } from './pages/EmergencyHistory.jsx';
import { Profile } from './pages/Profile.jsx';
import { EmergencyContacts } from './pages/EmergencyContacts.jsx';
import { Notifications } from './pages/Notifications.jsx';
import { Settings } from './pages/Settings.jsx';
import { DraftsManager } from './pages/DraftsManager.jsx';
import { Login } from './pages/Login.jsx';
import { Register } from './pages/Register.jsx';

import { initPWA } from './services/pwa.js';

function CitizenAppShell() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname || '/');
  const [searchParams, setSearchParams] = useState(new URLSearchParams(window.location.search));
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    initPWA(() => {
      console.log('CareOn Citizen ServiceWorker has update ready.');
    });

    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
      setSearchParams(new URLSearchParams(window.location.search));
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (toUrl) => {
    const url = new URL(toUrl, window.location.origin);
    window.history.pushState({}, '', url.pathname + url.search);
    setCurrentPath(url.pathname);
    setSearchParams(new URLSearchParams(url.search));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // Route selector
  const renderRoute = () => {
    if (currentPath === '/report') {
      const draftId = searchParams.get('draftId');
      const cat = searchParams.get('category');
      return <ReportEmergency onNavigate={navigate} initialDraftId={draftId} initialCategory={cat} />;
    }
    if (currentPath === '/track') {
      const id = searchParams.get('id');
      return <TrackIncident onNavigate={navigate} initialId={id} />;
    }
    if (currentPath === '/dashboard') {
      return isAuthenticated ? (
        <CitizenDashboard onNavigate={navigate} />
      ) : (
        <Login onNavigate={navigate} />
      );
    }
    if (currentPath === '/history') {
      return isAuthenticated ? (
        <EmergencyHistory onNavigate={navigate} />
      ) : (
        <Login onNavigate={navigate} />
      );
    }
    if (currentPath === '/profile') {
      return isAuthenticated ? (
        <Profile onNavigate={navigate} />
      ) : (
        <Login onNavigate={navigate} />
      );
    }
    if (currentPath === '/contacts') {
      return <EmergencyContacts onNavigate={navigate} />;
    }
    if (currentPath === '/notifications') {
      return <Notifications onNavigate={navigate} />;
    }
    if (currentPath === '/settings') {
      return <Settings onNavigate={navigate} />;
    }
    if (currentPath === '/drafts') {
      return <DraftsManager onNavigate={navigate} />;
    }
    if (currentPath === '/login') {
      return <Login onNavigate={navigate} />;
    }
    if (currentPath === '/register') {
      return <Register onNavigate={navigate} />;
    }
    // Default Home
    return <Home onNavigate={navigate} />;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', backgroundColor: '#FFFFFF' }}>
      <OfflineBanner />
      <InstallPrompt />
      <CitizenNav currentPath={currentPath} onNavigate={navigate} />
      <main style={{ flex: 1 }}>
        {renderRoute()}
      </main>
      <CitizenFooter onNavigate={navigate} />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider apiClient={apiClient}>
      <CitizenAppShell />
    </AuthProvider>
  );
}
