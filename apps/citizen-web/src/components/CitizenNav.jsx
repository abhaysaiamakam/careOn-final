import React, { useState } from 'react';
import { Shield, PlusCircle, Search, Clock, User, Settings, LogOut, LogIn, Menu, X, Bell, Users } from 'lucide-react';
import { colors, typography, Button } from '@careon/design-system';
import { useAuth } from '@careon/auth';

export function CitizenNav({ currentPath, onNavigate }) {
  const { user, isAuthenticated, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { label: 'Home', path: '/', icon: Shield },
    { label: 'Track Request', path: '/track', icon: Search },
    ...(isAuthenticated
      ? [
          { label: 'Dashboard', path: '/dashboard', icon: Shield },
          { label: 'Contacts', path: '/contacts', icon: Users },
          { label: 'History', path: '/history', icon: Clock },
          { label: 'Profile', path: '/profile', icon: User },
        ]
      : []),
    { label: 'Settings', path: '/settings', icon: Settings },
  ];

  const handleLinkClick = (path) => {
    setMobileMenuOpen(false);
    onNavigate(path);
  };

  return (
    <header
      style={{
        backgroundColor: colors.surface,
        borderBottom: `1px solid ${colors.border}`,
        position: 'sticky',
        top: 0,
        zIndex: 500,
        fontFamily: typography.fontFamily.sans,
      }}
    >
      <div
        style={{
          maxWidth: '1120px',
          margin: '0 auto',
          padding: '0 16px',
          height: '64px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {/* Brand / Logo */}
        <div
          onClick={() => handleLinkClick('/')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            cursor: 'pointer',
            userSelect: 'none',
          }}
        >
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: '6px',
              backgroundColor: colors.secondary,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: colors.primary,
              fontWeight: typography.fontWeight.bold,
              fontSize: '18px',
            }}
          >
            +
          </div>
          <div>
            <span
              style={{
                fontSize: typography.fontSize.lg,
                fontWeight: typography.fontWeight.bold,
                color: colors.textPrimary,
                letterSpacing: '-0.02em',
              }}
            >
              CareOn
            </span>
            <span
              style={{
                fontSize: typography.fontSize.xs,
                fontWeight: typography.fontWeight.semibold,
                color: colors.secondary,
                marginLeft: '6px',
                padding: '2px 6px',
                backgroundColor: '#FEF2F2',
                borderRadius: '4px',
                border: '1px solid #FECACA',
              }}
            >
              CITIZEN
            </span>
          </div>
        </div>

        {/* Desktop Navigation Links */}
        <nav
          style={{
            display: 'none',
            alignItems: 'center',
            gap: '24px',
          }}
          className="desktop-nav-links"
        >
          {navItems.map((item) => {
            const isActive = currentPath === item.path;
            return (
              <button
                key={item.path}
                onClick={() => handleLinkClick(item.path)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: '8px 0',
                  color: isActive ? colors.secondary : colors.textPrimary,
                  fontSize: typography.fontSize.sm,
                  fontWeight: isActive ? typography.fontWeight.semibold : typography.fontWeight.medium,
                  cursor: 'pointer',
                  position: 'relative',
                  borderBottom: isActive ? `2px solid ${colors.secondary}` : '2px solid transparent',
                  transition: 'color 0.15s ease',
                }}
              >
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Desktop Right Actions */}
        <div
          style={{
            display: 'none',
            alignItems: 'center',
            gap: '12px',
          }}
          className="desktop-nav-actions"
        >
          {/* Quick Emergency SOS button */}
          <Button
            size="sm"
            variant="primary"
            onClick={() => handleLinkClick('/report')}
            icon={PlusCircle}
          >
            Report Emergency
          </Button>

          {isAuthenticated ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <button
                onClick={() => handleLinkClick('/notifications')}
                style={{
                  background: 'none',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '6px',
                  padding: '6px 8px',
                  cursor: 'pointer',
                  color: colors.textSecondary,
                  display: 'flex',
                  alignItems: 'center',
                }}
                title="Notifications"
              >
                <Bell size={16} />
              </button>
              <button
                onClick={logout}
                style={{
                  background: 'none',
                  border: `1px solid ${colors.border}`,
                  borderRadius: '6px',
                  padding: '6px 12px',
                  fontSize: typography.fontSize.sm,
                  color: colors.textSecondary,
                  cursor: 'pointer',
                }}
              >
                Log Out
              </button>
            </div>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => handleLinkClick('/login')}
              icon={LogIn}
            >
              Sign In
            </Button>
          )}
        </div>

        {/* Mobile Hamburger Button */}
        <div className="mobile-nav-toggle" style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <Button
            size="sm"
            variant="primary"
            onClick={() => handleLinkClick('/report')}
            style={{ padding: '6px 10px' }}
          >
            SOS
          </Button>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            style={{
              background: 'none',
              border: `1px solid ${colors.border}`,
              borderRadius: '6px',
              padding: '6px 8px',
              cursor: 'pointer',
              color: colors.textPrimary,
              display: 'flex',
              alignItems: 'center',
            }}
            aria-label="Toggle menu"
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div
          style={{
            backgroundColor: colors.surface,
            borderBottom: `1px solid ${colors.border}`,
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.path;
            return (
              <button
                key={item.path}
                onClick={() => handleLinkClick(item.path)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  backgroundColor: isActive ? '#FEF2F2' : 'transparent',
                  color: isActive ? colors.secondary : colors.textPrimary,
                  border: 'none',
                  fontSize: typography.fontSize.base,
                  fontWeight: isActive ? typography.fontWeight.semibold : typography.fontWeight.medium,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <Icon size={18} color={isActive ? colors.secondary : colors.textSecondary} />
                {item.label}
              </button>
            );
          })}

          <div style={{ height: '1px', backgroundColor: colors.border, margin: '8px 0' }} />

          {isAuthenticated ? (
            <Button
              variant="secondary"
              fullWidth
              onClick={() => {
                logout();
                setMobileMenuOpen(false);
              }}
              icon={LogOut}
            >
              Sign Out ({user?.name || user?.email})
            </Button>
          ) : (
            <Button
              variant="secondary"
              fullWidth
              onClick={() => handleLinkClick('/login')}
              icon={LogIn}
            >
              Sign In / Register
            </Button>
          )}
        </div>
      )}

      {/* Responsive media query styling */}
      <style>{`
        @media (min-width: 768px) {
          .desktop-nav-links { display: flex !important; }
          .desktop-nav-actions { display: flex !important; }
          .mobile-nav-toggle { display: none !important; }
        }
      `}</style>
    </header>
  );
}
