import React, { useState, useEffect } from 'react';
import { Bell, CheckCircle2, RefreshCw } from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  colors,
  typography,
} from '@careon/design-system';
import { getNotifications, markNotificationAsRead } from '@careon/api-client';

export function Notifications() {
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchNotifs = async () => {
    setLoading(true);
    try {
      const data = await getNotifications();
      setNotifications(data || []);
    } catch (e) {
      console.warn('Failed to load notifications:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNotifs();
  }, []);

  const handleMarkRead = async (id) => {
    try {
      await markNotificationAsRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch (e) {
      console.error('Failed to mark read:', e);
    }
  };

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: '24px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Notifications & Alerts
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
            Operational updates regarding reported emergencies and account security.
          </p>
        </div>
        <Button size="sm" variant="tertiary" onClick={fetchNotifs} icon={RefreshCw}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <Card padding="md" style={{ textAlign: 'center', color: colors.textSecondary }}>
          Loading notifications...
        </Card>
      ) : notifications.length === 0 ? (
        <Card padding="lg" style={{ textAlign: 'center', color: colors.textSecondary }}>
          No notifications yet. You will receive updates here when an emergency request changes status.
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {notifications.map((n) => (
            <Card
              key={n.id}
              padding="sm"
              style={{
                backgroundColor: n.is_read ? colors.surface : '#FEF2F2',
                border: `1px solid ${n.is_read ? colors.border : '#FECACA'}`,
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                gap: '12px',
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                  <strong style={{ fontSize: typography.fontSize.sm, color: colors.textPrimary }}>
                    {n.title}
                  </strong>
                  {!n.is_read && (
                    <Badge variant="emergency" size="sm">
                      New
                    </Badge>
                  )}
                </div>
                <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                  {n.message}
                </div>
                <div style={{ fontSize: '11px', color: colors.textMuted, marginTop: '4px' }}>
                  {new Date(n.created_at).toLocaleString()}
                </div>
              </div>

              {!n.is_read && (
                <button
                  onClick={() => handleMarkRead(n.id)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: colors.secondary,
                    cursor: 'pointer',
                    fontSize: typography.fontSize.xs,
                    padding: '4px 8px',
                  }}
                >
                  Mark read
                </button>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
