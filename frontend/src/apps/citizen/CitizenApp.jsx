import React, { useState } from 'react';
import Home from '../../pages/Home';
import ReportEmergency from '../../pages/ReportEmergency';
import TrackRequest from '../../pages/TrackRequest';
import UserDashboard from '../../pages/UserDashboard';
import UserLogin from '../../pages/UserLogin';
import UserRegister from '../../pages/UserRegister';
import SaharaChatbot from '../../components/SaharaChatbot';
import { languages } from '../../translations';
import { ShieldAlert, MapPin, Compass, User as UserIcon, Globe, PhoneCall } from 'lucide-react';

export default function CitizenApp({ activeSubView = 'home', onNavigate }) {
  const [currentView, setCurrentView] = useState(activeSubView);
  const [lang, setLang] = useState('en');
  const [trackingToken, setTrackingToken] = useState('');

  const navigateTo = (view, token = '') => {
    if (token) setTrackingToken(token);
    setCurrentView(view);
    if (onNavigate) onNavigate(view);
  };

  const t = languages[lang] || languages.en;

  return (
    <div className="citizen-app-container" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#0a0e17' }}>
      {/* Top Citizen Sub-header */}
      <div style={{
        backgroundColor: '#111827',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        padding: '8px 20px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: 'rgba(239, 68, 68, 0.15)',
            color: '#ef4444',
            padding: '4px 10px',
            borderRadius: '9999px',
            fontSize: '0.75rem',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            <ShieldAlert size={14} /> Citizen Assistance Portal
          </span>
          <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>
            Direct emergency access & real-time dispatch tracking
          </span>
        </div>

        {/* Action Pills & Multilingual Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => navigateTo('report')}
            style={{
              backgroundColor: '#ef4444',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '0.8rem',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <PhoneCall size={14} /> SOS REPORT
          </button>
          <button
            onClick={() => navigateTo('track')}
            style={{
              backgroundColor: '#1f2937',
              color: '#f8fafc',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              borderRadius: '6px',
              padding: '6px 12px',
              fontSize: '0.8rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Compass size={14} /> Track Status
          </button>
          
          {/* Language Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginLeft: '6px' }}>
            <Globe size={14} style={{ color: '#94a3b8' }} />
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              style={{
                backgroundColor: '#1f2937',
                color: '#f8fafc',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '6px',
                padding: '4px 8px',
                fontSize: '0.75rem',
                cursor: 'pointer',
              }}
            >
              <option value="en">English</option>
              <option value="hi">हिंदी (Hindi)</option>
              <option value="kn">ಕನ್ನಡ (Kannada)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Citizen Content Router */}
      <div style={{ flex: 1 }}>
        {currentView === 'home' && <Home setTab={navigateTo} />}
        {currentView === 'report' && <ReportEmergency setTab={navigateTo} />}
        {currentView === 'track' && <TrackRequest trackingToken={trackingToken} setTab={navigateTo} />}
        {currentView === 'dashboard' && <UserDashboard setTab={navigateTo} />}
        {currentView === 'login' && <UserLogin setTab={navigateTo} />}
        {currentView === 'register' && <UserRegister setTab={navigateTo} />}
      </div>

      {/* Sahara Caring Emergency Companion */}
      <SaharaChatbot />
    </div>
  );
}
