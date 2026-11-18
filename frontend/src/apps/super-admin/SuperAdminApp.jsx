import React, { useState, useEffect } from 'react';
import { superAdminApi } from '../../packages/api-client';
import useAuth from '../../auth/useAuth';
import {
  ShieldAlert,
  Server,
  Database,
  Radio,
  Users,
  Building,
  FileText,
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Search,
  Filter,
} from 'lucide-react';

export default function SuperAdminApp() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState('health'); // 'health' | 'users' | 'audit' | 'analytics'
  const [health, setHealth] = useState(null);
  const [users, setUsers] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [auditFilter, setAuditFilter] = useState('');
  const [selectedUser, setSelectedUser] = useState(null);
  const [newRole, setNewRole] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      const [hData, aData, uData, lData] = await Promise.all([
        superAdminApi.getSystemHealth().catch(() => null),
        superAdminApi.getOperationsSummary().catch(() => null),
        superAdminApi.getUsers().catch(() => []),
        superAdminApi.getAuditLogs().catch(() => ({ items: [] })),
      ]);
      setHealth(hData);
      setAnalytics(aData);
      setUsers(Array.isArray(uData) ? uData : []);
      setAuditLogs(lData?.items || []);
    } catch (err) {
      console.warn('Super admin load error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRoleChange = async (userId, role) => {
    try {
      await superAdminApi.updateUserRole(userId, role);
      await loadData();
      alert(`User role updated to ${role}`);
    } catch (err) {
      alert(`Role change failed: ${err.message}`);
    }
  };

  const handleStatusToggle = async (userId, currentActive) => {
    try {
      await superAdminApi.updateUserStatus(userId, !currentActive, 'Administrative toggle');
      await loadData();
    } catch (err) {
      alert(`Status toggle failed: ${err.message}`);
    }
  };

  const filteredLogs = auditLogs.filter((log) => {
    if (!auditFilter) return true;
    const term = auditFilter.toLowerCase();
    return (
      (log.action && log.action.toLowerCase().includes(term)) ||
      (log.actor && log.actor.toLowerCase().includes(term)) ||
      (log.entity_type && log.entity_type.toLowerCase().includes(term)) ||
      (log.details && log.details.toLowerCase().includes(term))
    );
  });

  return (
    <div style={{
      maxWidth: '1280px',
      margin: '0 auto',
      padding: '24px 20px',
      color: '#f8fafc',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      {/* Super Admin Top Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px',
        backgroundColor: '#0f172a',
        padding: '20px 24px',
        borderRadius: '16px',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        marginBottom: '24px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '46px',
            height: '46px',
            borderRadius: '12px',
            backgroundColor: 'rgba(239, 68, 68, 0.2)',
            color: '#ef4444',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}>
            <ShieldAlert size={26} />
          </div>
          <div>
            <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
              Super Admin & Governance Console
              <span style={{
                fontSize: '0.7rem',
                backgroundColor: '#ef4444',
                color: '#fff',
                padding: '2px 8px',
                borderRadius: '999px',
                fontWeight: 800,
              }}>
                LEVEL 0 ROOT
              </span>
            </h1>
            <div style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '4px' }}>
              Infrastructure verification, multi-tenant RBAC, and global operational audit
            </div>
          </div>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          style={{
            backgroundColor: '#1e293b',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            color: '#94a3b8',
            padding: '10px 16px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            cursor: 'pointer',
            fontSize: '0.85rem',
            fontWeight: 600,
          }}
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          REFRESH TELEMETRY
        </button>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        gap: '8px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        marginBottom: '24px',
        paddingBottom: '8px',
      }}>
        {[
          { id: 'health', label: 'System Health & Infrastructure', icon: Server },
          { id: 'users', label: 'User & Role Governance', icon: Users },
          { id: 'audit', label: 'Central Audit Inspector', icon: FileText },
          { id: 'analytics', label: 'Global Operations Analytics', icon: Activity },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                backgroundColor: isActive ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                color: isActive ? '#60a5fa' : '#94a3b8',
                border: isActive ? '1px solid rgba(59, 130, 246, 0.3)' : '1px solid transparent',
                borderRadius: '8px',
                padding: '10px 16px',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab 1: System Health */}
      {activeTab === 'health' && (
        <div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '16px',
            marginBottom: '24px',
          }}>
            {/* DB Status */}
            <div style={{
              backgroundColor: '#111827',
              borderRadius: '12px',
              padding: '20px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>POSTGRESQL DATABASE</span>
                <Database size={20} style={{ color: health?.database_connected ? '#10b981' : '#ef4444' }} />
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: health?.database_connected ? '#34d399' : '#f87171' }}>
                {health?.database_connected ? 'CONNECTED' : 'DISCONNECTED'}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '6px' }}>
                Active pool & transactional persistence
              </div>
            </div>

            {/* PostGIS Status */}
            <div style={{
              backgroundColor: '#111827',
              borderRadius: '12px',
              padding: '20px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>POSTGIS 3.5 SPATIAL</span>
                <Server size={20} style={{ color: health?.postgis_available ? '#3b82f6' : '#f59e0b' }} />
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: health?.postgis_available ? '#60a5fa' : '#fbbf24' }}>
                {health?.postgis_available ? 'POSTGIS ACTIVE' : 'STANDARD PG'}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '6px' }}>
                GiST indexes & SRID 4326 geometry
              </div>
            </div>

            {/* Redis Status */}
            <div style={{
              backgroundColor: '#111827',
              borderRadius: '12px',
              padding: '20px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>REDIS CACHE</span>
                <Radio size={20} style={{ color: health?.redis_connected ? '#10b981' : '#94a3b8' }} />
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: health?.redis_connected ? '#34d399' : '#94a3b8' }}>
                {health?.redis_connected ? 'SYNCHRONIZED' : 'IN-MEMORY DEV'}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '6px' }}>
                Rate limiting & session family revokes
              </div>
            </div>

            {/* Global Audit Count */}
            <div style={{
              backgroundColor: '#111827',
              borderRadius: '12px',
              padding: '20px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600 }}>AUDIT LOG ENTRIES</span>
                <FileText size={20} style={{ color: '#8b5cf6' }} />
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#f8fafc' }}>
                {health?.audit_log_count ?? 0}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '6px' }}>
                Tamper-evident audit chain
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: User Governance */}
      {activeTab === 'users' && (
        <div style={{
          backgroundColor: '#111827',
          borderRadius: '14px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          overflow: 'hidden',
        }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Platform Users & RBAC Roles</h3>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#0f172a', color: '#94a3b8', textAlign: 'left' }}>
                <th style={{ padding: '12px 16px' }}>USER</th>
                <th style={{ padding: '12px 16px' }}>CONTACT</th>
                <th style={{ padding: '12px 16px' }}>ROLE</th>
                <th style={{ padding: '12px 16px' }}>STATUS</th>
                <th style={{ padding: '12px 16px' }}>ACTIONS</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ fontWeight: 600, color: '#f8fafc' }}>{u.name}</div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>{u.email}</div>
                  </td>
                  <td style={{ padding: '12px 16px', color: '#cbd5e1' }}>{u.phone}</td>
                  <td style={{ padding: '12px 16px' }}>
                    <select
                      value={u.role}
                      onChange={(e) => handleRoleChange(u.id, e.target.value)}
                      style={{
                        backgroundColor: '#1e293b',
                        color: '#f8fafc',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        borderRadius: '6px',
                        padding: '4px 8px',
                        fontSize: '0.8rem',
                      }}
                    >
                      <option value="citizen">Citizen</option>
                      <option value="dispatcher">Dispatcher</option>
                      <option value="responder">Responder</option>
                      <option value="hospital_staff">Hospital Staff</option>
                      <option value="org_admin">Org Admin</option>
                      <option value="super_admin">Super Admin</option>
                    </select>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      color: u.is_active ? '#34d399' : '#f87171',
                    }}>
                      {u.is_active ? <CheckCircle size={12} /> : <XCircle size={12} />}
                      {u.is_active ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <button
                      onClick={() => handleStatusToggle(u.id, u.is_active)}
                      style={{
                        backgroundColor: u.is_active ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                        color: u.is_active ? '#f87171' : '#34d399',
                        border: 'none',
                        padding: '4px 10px',
                        borderRadius: '6px',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {u.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 3: Central Audit Log */}
      {activeTab === 'audit' && (
        <div style={{
          backgroundColor: '#111827',
          borderRadius: '14px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          overflow: 'hidden',
        }}>
          <div style={{
            padding: '16px 20px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '16px',
          }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
              Live System Audit Logs ({filteredLogs.length})
            </h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', maxWidth: '320px', width: '100%' }}>
              <input
                type="text"
                placeholder="Filter action, actor, or details..."
                value={auditFilter}
                onChange={(e) => setAuditFilter(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  backgroundColor: '#0f172a',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  borderRadius: '6px',
                  color: '#fff',
                  fontSize: '0.8rem',
                }}
              />
            </div>
          </div>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ backgroundColor: '#0f172a', color: '#94a3b8', textAlign: 'left' }}>
                <th style={{ padding: '12px 16px' }}>TIMESTAMP</th>
                <th style={{ padding: '12px 16px' }}>ACTION</th>
                <th style={{ padding: '12px 16px' }}>ACTOR</th>
                <th style={{ padding: '12px 16px' }}>ENTITY</th>
                <th style={{ padding: '12px 16px' }}>DETAILS</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.slice(0, 30).map((log) => (
                <tr key={log.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.75rem' }}>
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    <span style={{
                      backgroundColor: 'rgba(59, 130, 246, 0.15)',
                      color: '#60a5fa',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                    }}>
                      {log.action}
                    </span>
                  </td>
                  <td style={{ padding: '12px 16px', fontWeight: 600, color: '#f8fafc' }}>
                    {log.actor}
                  </td>
                  <td style={{ padding: '12px 16px', color: '#cbd5e1' }}>
                    {log.entity_type}:{log.entity_id}
                  </td>
                  <td style={{ padding: '12px 16px', color: '#94a3b8', fontSize: '0.8rem' }}>
                    {log.details || '—'}
                  </td>
                </tr>
              ))}
              {filteredLogs.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '32px', color: '#64748b' }}>
                    No matching audit log entries found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Tab 4: Global Analytics */}
      {activeTab === 'analytics' && (
        <div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: '16px',
          }}>
            <div style={{ backgroundColor: '#111827', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600, marginBottom: '8px' }}>TOTAL INCIDENTS RECORDED</div>
              <div style={{ fontSize: '2rem', fontWeight: 800 }}>{analytics?.incidents?.total ?? 0}</div>
              <div style={{ fontSize: '0.8rem', color: '#38bdf8', marginTop: '4px' }}>Active: {analytics?.incidents?.active ?? 0}</div>
            </div>

            <div style={{ backgroundColor: '#111827', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600, marginBottom: '8px' }}>CRITICAL LIFE-SAFETY INCIDENTS</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#f87171' }}>{analytics?.incidents?.critical ?? 0}</div>
              <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px' }}>Requiring immediate ALS / Trauma</div>
            </div>

            <div style={{ backgroundColor: '#111827', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600, marginBottom: '8px' }}>ACTIVE FLEET READINESS</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: '#34d399' }}>{analytics?.fleet?.available ?? 0}</div>
              <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px' }}>Deployed: {analytics?.fleet?.deployed ?? 0} / Total: {analytics?.fleet?.total ?? 0}</div>
            </div>

            <div style={{ backgroundColor: '#111827', padding: '20px', borderRadius: '12px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
              <div style={{ fontSize: '0.85rem', color: '#94a3b8', fontWeight: 600, marginBottom: '8px' }}>HOSPITALS ON DIVERT</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: analytics?.hospitals?.on_divert > 0 ? '#fbbf24' : '#34d399' }}>
                {analytics?.hospitals?.on_divert ?? 0}
              </div>
              <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px' }}>Emergency department capacity status</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
