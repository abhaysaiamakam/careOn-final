import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchIncidents,
  fetchResources,
  fetchProviders,
  fetchShortages,
  fetchAnalytics,
  fetchPredictions,
  fetchFeedbackList,
  updateIncidentStatus,
  updateIncidentPriority,
  confirmAllocation,
  releaseAllocation,
  updateResourceStatus,
  createProviderEnquiry,
  updateProviderEnquiry,
  acknowledgeCancellation,
  resolveIncident,
  resetSimulationData,
} from '../api';
import { useTranslation } from '../translations';
import GoogleMap from '../components/GoogleMap';
import {
  ShieldCheck,
  RefreshCw,
  AlertTriangle,
  RotateCcw,
  Truck,
  Building2,
  Brain,
  MapPin,
  Flame,
  Activity,
  Layers,
  FileCheck2,
  TrendingUp,
  Waves,
  CheckCircle2,
  Clock,
  Send,
  Eye,
  X
} from 'lucide-react';

export default function AdminDashboard({ lang = 'en', currentUser, onNavigate }) {
  const { t } = useTranslation(lang);
  const [activeTab, setActiveTab] = useState('overview'); // overview, incidents, resources, allocation, providers, map, simulation, verification, disaster, analytics

  const [incidents, setIncidents] = useState([]);
  const [resources, setResources] = useState([]);
  const [providers, setProviders] = useState([]);
  const [shortages, setShortages] = useState({ shortages: [], available_fleet_summary: {} });
  const [analytics, setAnalytics] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [feedbackList, setFeedbackList] = useState([]);

  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [actionNotice, setActionNotice] = useState(null);

  // Selected Incident Drawer / Modal
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [overridePriority, setOverridePriority] = useState('Critical');
  const [priorityReason, setPriorityReason] = useState('');
  const [adminNotes, setAdminNotes] = useState('');

  // Simulation State
  const [isSimulatingMapMovement, setIsSimulatingMapMovement] = useState(false);

  const showNotice = (msg) => {
    setActionNotice(msg);
    setTimeout(() => setActionNotice(null), 4000);
  };

  const loadAllData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    setLoading(true);
    try {
      const [inc, res, prov, short, ana, pred, fb] = await Promise.all([
        fetchIncidents({}, 'admin').catch(() => []),
        fetchResources({}, 'admin').catch(() => []),
        fetchProviders('admin').catch(() => []),
        fetchShortages().catch(() => ({ shortages: [], available_fleet_summary: {} })),
        fetchAnalytics().catch(() => null),
        fetchPredictions().catch(() => []),
        fetchFeedbackList().catch(() => []),
      ]);
      setIncidents(inc);
      setResources(res);
      setProviders(prov);
      setShortages(short);
      setAnalytics(ana);
      setPredictions(pred);
      setFeedbackList(fb);
      if (isManualRefresh) {
        showNotice(t('feed_refreshed') || 'Feed refreshed successfully with live incident data.');
      }
    } catch (err) {
      console.error('Failed to load admin dashboard data:', err);
    } finally {
      setLoading(false);
      if (isManualRefresh) setRefreshing(false);
    }
  }, [t]);

  useEffect(() => {
    loadAllData();
    const interval = setInterval(loadAllData, 6000); // 6s refresh
    return () => clearInterval(interval);
  }, [loadAllData]);

  // Actions
  const handleVerify = async (incId) => {
    try {
      await updateIncidentStatus(incId, 'Verified', 'Coordinator verified incident via direct review.');
      showNotice(`Incident #${incId} marked as Verified.`);
      await loadAllData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handlePriorityOverride = async (incId) => {
    if (!priorityReason.trim()) {
      alert('Please enter a coordinator reason for overriding priority.');
      return;
    }
    try {
      await updateIncidentPriority(incId, overridePriority, priorityReason);
      showNotice(`Priority updated to ${overridePriority}.`);
      setPriorityReason('');
      await loadAllData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleAssignResource = async (incId, resId) => {
    try {
      await confirmAllocation(incId, resId, 'Assigned by Command Centre Coordinator.');
      showNotice(`Resource successfully assigned and dispatched.`);
      await loadAllData();
    } catch (err) {
      alert(`Assignment failed: ${err.message}`);
    }
  };

  const handleReleaseResource = async (resId) => {
    try {
      await updateResourceStatus(resId, 'Available');
      showNotice(`Resource status updated to Available.`);
      await loadAllData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleAcknowledgeCancellation = async (incId) => {
    try {
      await acknowledgeCancellation(incId);
      showNotice(`Cancellation acknowledged. All attached resources safely released.`);
      await loadAllData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleResolveIncident = async (incId) => {
    try {
      await resolveIncident(incId, 'Coordinator marked incident resolved onsite.');
      showNotice(`Incident #${incId} successfully resolved.`);
      await loadAllData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleSimulateContactProvider = async (incId, provId) => {
    try {
      await createProviderEnquiry({
        incident_id: incId,
        provider_id: provId,
        charge_quote: 1500.0,
        subsidy_amount: 500.0,
        user_consent: 'Pending',
        response_time_minutes: 12,
        notes: 'Simulated partner enquiry - provider confirmed vehicle standby.',
      });
      showNotice(`Partner contacted. Awaiting user consent for quotation.`);
      await loadAllData();
    } catch (err) {
      alert(err.message);
    }
  };

  const handleResetDemoData = async () => {
    if (!window.confirm('Reset database to original clean demonstration state?')) return;
    try {
      await resetSimulationData();
      showNotice('Demo database reset to clean state successfully.');
      await loadAllData();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div>
      {/* Toast Notice */}
      {actionNotice && (
        <div
          style={{
            position: 'fixed',
            top: '80px',
            right: '24px',
            zIndex: 3000,
            backgroundColor: '#0f4c5c',
            color: '#ffffff',
            padding: '12px 20px',
            borderRadius: '8px',
            fontWeight: 700,
            fontSize: '13.5px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
          }}
        >
          ✓ {actionNotice}
        </div>
      )}

      {/* Header Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '24px' }}>🛡️</span>
            <h1 style={{ fontSize: '24px', fontWeight: 800, color: '#0f4c5c', margin: 0 }}>
              {t('command_centre_title') || 'Command Centre'}
            </h1>
            <span className="status-badge badge-resolved" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <ShieldCheck size={14} />
              <span>{currentUser?.name || 'Aastha Singh'} ({t('admin_role') || 'Coordinator'})</span>
            </span>
          </div>
          <div style={{ fontSize: '13px', color: '#64748b', marginTop: '4px' }}>
            {t('command_centre_subtitle') || 'Real-time incident triage, capability matching, shortage alerts, and partner coordination across Mysuru.'}
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            className="btn btn-outline btn-sm"
            onClick={() => loadAllData(true)}
            disabled={loading || refreshing}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
            <span>{refreshing ? t('refreshing') || 'Refreshing...' : t('refresh_feed') || 'Refresh Feed'}</span>
          </button>
          <button className="btn btn-primary-red btn-sm" onClick={handleResetDemoData}>
            ↺ {t('reset_demo_state') || 'Reset Demo State'}
          </button>
        </div>
      </div>

      {/* Top 4 Overview Metric Cards */}
      <div className="grid-4" style={{ marginBottom: '24px' }}>
        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#fee2e2', color: '#991b1b' }}>🚨</div>
          <div>
            <div className="stat-val">{analytics?.active_incidents || incidents.filter(i => !['Resolved','Cancelled'].includes(i.status)).length}</div>
            <div className="stat-label">{t('stat_active_incidents') || 'Active Incidents'}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#fef3c7', color: '#92400e' }}>⚡</div>
          <div>
            <div className="stat-val">{analytics?.critical_incidents || incidents.filter(i => i.priority === 'Critical').length}</div>
            <div className="stat-label">{t('stat_critical_priority') || 'Critical Priority'}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#ecfdf5', color: '#047857' }}>🚑</div>
          <div>
            <div className="stat-val">{resources.filter(r => r.status === 'Available').length}</div>
            <div className="stat-label">{t('stat_fleet_available') || 'Fleet Available'}</div>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon" style={{ backgroundColor: '#fff1f2', color: '#be123c' }}>⚠️</div>
          <div>
            <div className="stat-val">{shortages.shortages?.length || 0}</div>
            <div className="stat-label">{t('stat_active_shortages') || 'Active Shortages'}</div>
          </div>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '8px',
          overflowX: 'auto',
          borderBottom: '2px solid #e2e8f0',
          paddingBottom: '8px',
          marginBottom: '24px',
        }}
      >
        {[
          { id: 'overview', label: t('tab_overview', '📊 Overview') },
          { id: 'incidents', label: `${t('tab_incidents', '🚨 Incidents')} (${incidents.length})` },
          { id: 'resources', label: `${t('tab_resources', '🚑 Fleet Resources')} (${resources.length})` },
          { id: 'allocation', label: t('tab_allocations', '🧠 Smart Allocation') },
          { id: 'providers', label: `${t('tab_providers', '🏥 External Partners')} (${providers.length})` },
          { id: 'map', label: t('tab_map', '🗺️ Mysuru Live Map') },
          { id: 'simulation', label: t('tab_simulation', '🎯 Shortage Challenge') },
          { id: 'verification', label: t('tab_verification', '🔍 Trust & Verification') },
          { id: 'disaster', label: t('tab_disaster', '🌊 Disaster Relief') },
          { id: 'analytics', label: t('tab_analytics', '📈 Analytics & Predictions') },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '8px 14px',
              borderRadius: '6px',
              fontWeight: 700,
              fontSize: '13px',
              whiteSpace: 'nowrap',
              backgroundColor: activeTab === tab.id ? '#0f4c5c' : '#ffffff',
              color: activeTab === tab.id ? '#ffffff' : '#475569',
              border: '1px solid',
              borderColor: activeTab === tab.id ? '#0f4c5c' : '#cbd5e1',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ==================================================================== */}
      {/* TAB 1: OVERVIEW */}
      {/* ==================================================================== */}
      {activeTab === 'overview' && (
        <div className="grid-2">
          {/* Active Incidents Queue */}
          <div className="card">
            <h3 className="card-title">
              <span>Active Incident Priority Queue</span>
              <button className="btn btn-sm btn-outline" onClick={() => setActiveTab('incidents')}>
                View All
              </button>
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {incidents.slice(0, 5).map((inc) => (
                <div
                  key={inc.id}
                  style={{
                    padding: '12px',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    backgroundColor: inc.status === 'Verification Pending' ? '#fffbeb' : '#ffffff',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                      <strong>{inc.incident_code}</strong>
                      <span className={`status-badge ${inc.priority === 'Critical' ? 'badge-critical' : 'badge-high'}`}>
                        {inc.priority}
                      </span>
                      {inc.is_duplicate && (
                        <span className="status-badge badge-critical" style={{ fontSize: '10px' }}>
                          Duplicate Flag
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: '12.5px', color: '#64748b' }}>
                      {inc.category} • {inc.location_name}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => {
                        setSelectedIncident(inc);
                        setActiveTab('incidents');
                      }}
                    >
                      Inspect
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Quick Fleet & Shortage Summary */}
          <div className="card">
            <h3 className="card-title">Fleet Availability & Immediate Shortages</h3>

            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#0f4c5c', marginBottom: '8px' }}>
                Fleet Categories:
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px' }}>
                {resources.map((res) => (
                  <div
                    key={res.id}
                    style={{
                      padding: '8px 10px',
                      backgroundColor: '#f8fafc',
                      borderRadius: '6px',
                      border: '1px solid #e2e8f0',
                      fontSize: '12px',
                      display: 'flex',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>{res.resource_code} ({res.category})</span>
                    <strong style={{ color: res.status === 'Available' ? '#166534' : '#1e40af' }}>
                      {res.status}
                    </strong>
                  </div>
                ))}
              </div>
            </div>

            {shortages.shortages && shortages.shortages.length > 0 && (
              <div style={{ backgroundColor: '#fff1f2', border: '1px solid #fecdd3', padding: '12px', borderRadius: '8px' }}>
                <div style={{ fontWeight: 800, color: '#9f1239', fontSize: '13px', marginBottom: '4px' }}>
                  ⚠️ Critical Shortage Detected:
                </div>
                <div style={{ fontSize: '12.5px', color: '#881337', lineHeight: 1.4 }}>
                  {shortages.shortages.map((s, idx) => (
                    <div key={idx}>
                      • Missing <strong>{s.missing_resource_type}</strong> for {s.incident_code}. Recommended action: coordinate with <strong>{s.suggested_provider?.name || 'Registered Partner'}</strong>.
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: INCIDENT MANAGEMENT */}
      {/* ==================================================================== */}
      {activeTab === 'incidents' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 800 }}>Incident Management & Verification Queue</h3>
          </div>

          <div className="table-wrapper">
            <table className="careon-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Category</th>
                  <th>Location</th>
                  <th>Reporter</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Verified</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr key={inc.id}>
                    <td><strong>{inc.incident_code}</strong></td>
                    <td>{inc.category}</td>
                    <td>{inc.location_name}</td>
                    <td>{inc.contact_name} ({inc.contact_phone})</td>
                    <td>
                      <span className={`status-badge ${inc.priority === 'Critical' ? 'badge-critical' : inc.priority === 'High' ? 'badge-high' : 'badge-low'}`}>
                        {inc.priority}
                      </span>
                    </td>
                    <td>
                      <span className="status-badge badge-dispatched">{inc.status}</span>
                    </td>
                    <td>
                      {inc.is_verified ? (
                        <span style={{ color: '#166534', fontWeight: 700 }}>✓ Verified</span>
                      ) : (
                        <button
                          className="btn btn-outline btn-sm"
                          onClick={() => handleVerify(inc.id)}
                          style={{ fontSize: '11px', padding: '3px 6px' }}
                        >
                          Verify OTP
                        </button>
                      )}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          className="btn btn-teal btn-sm"
                          onClick={() => setSelectedIncident(inc)}
                          style={{ fontSize: '11.5px', padding: '4px 8px' }}
                        >
                          Details
                        </button>

                        {inc.status === 'Cancelled' && (
                          <button
                            className="btn btn-outline btn-sm"
                            onClick={() => handleAcknowledgeCancellation(inc.id)}
                            style={{ fontSize: '11px', color: '#f59e0b', padding: '4px 8px' }}
                          >
                            Release Fleet
                          </button>
                        )}

                        {inc.status !== 'Resolved' && inc.status !== 'Cancelled' && (
                          <button
                            className="btn btn-outline btn-sm"
                            onClick={() => handleResolveIncident(inc.id)}
                            style={{ fontSize: '11px', color: '#166534', padding: '4px 8px' }}
                          >
                            Resolve
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Selected Incident Drawer / Details Modal */}
          {selectedIncident && (
            <div className="modal-overlay" onClick={() => setSelectedIncident(null)}>
              <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <h3 style={{ fontSize: '18px', fontWeight: 800 }}>
                    Incident Details: {selectedIncident.incident_code}
                  </h3>
                  <button onClick={() => setSelectedIncident(null)} style={{ fontSize: '18px' }}>✕</button>
                </div>

                <div style={{ fontSize: '13.5px', lineHeight: 1.6, marginBottom: '16px' }}>
                  <p><strong>Category:</strong> {selectedIncident.category}</p>
                  <p><strong>Description:</strong> {selectedIncident.description}</p>
                  <p><strong>Location:</strong> {selectedIncident.location_name} ({selectedIncident.latitude.toFixed(4)}, {selectedIncident.longitude.toFixed(4)})</p>
                  <p><strong>Casualties / Affected:</strong> {selectedIncident.affected_people} individuals</p>
                  <p><strong>Help Requested:</strong> {selectedIncident.help_required}</p>
                  <p><strong>Contact:</strong> {selectedIncident.contact_name} ({selectedIncident.contact_phone})</p>
                  <p><strong>Initial Priority Reason:</strong> {selectedIncident.priority_reason}</p>
                </div>

                {/* Priority Override Section */}
                <div style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #e2e8f0', marginBottom: '16px' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', marginBottom: '8px', color: '#0f4c5c' }}>
                    Coordinator Priority Adjustment
                  </div>
                  <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
                    <select
                      className="form-select"
                      style={{ width: '130px' }}
                      value={overridePriority}
                      onChange={(e) => setOverridePriority(e.target.value)}
                    >
                      <option value="Critical">Critical</option>
                      <option value="High">High</option>
                      <option value="Medium">Medium</option>
                      <option value="Low">Low</option>
                    </select>
                    <input
                      type="text"
                      className="form-input"
                      placeholder="Reason for change (e.g. Multi-vehicle escalation)..."
                      value={priorityReason}
                      onChange={(e) => setPriorityReason(e.target.value)}
                    />
                  </div>
                  <button
                    className="btn btn-teal btn-sm"
                    onClick={() => handlePriorityOverride(selectedIncident.id)}
                  >
                    Save Priority Change
                  </button>
                </div>

                {/* Conflict-Free Resource Assignment Action */}
                <div style={{ backgroundColor: '#f0fdf4', padding: '14px', borderRadius: '8px', border: '1px solid #bbf7d0' }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', marginBottom: '8px', color: '#166534' }}>
                    Available Fleet Units (Direct Assignment):
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {resources.filter(r => r.status === 'Available').map(res => (
                      <button
                        key={res.id}
                        className="btn btn-sm btn-outline"
                        style={{ backgroundColor: '#ffffff', color: '#166534', fontWeight: 600 }}
                        onClick={() => handleAssignResource(selectedIncident.id, res.id)}
                      >
                        + Assign {res.name} ({res.category})
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 3: RESOURCE MANAGEMENT */}
      {/* ==================================================================== */}
      {activeTab === 'resources' && (
        <div className="card">
          <h3 className="card-title">Emergency Fleet Management</h3>
          <p style={{ color: '#64748b', fontSize: '13.5px', marginBottom: '20px' }}>
            Monitor vehicle availability, maintenance states, and current active assignments. Double-assignment is prevented at the database transaction layer.
          </p>

          <div className="grid-3">
            {resources.map((res) => (
              <div
                key={res.id}
                style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '16px',
                  backgroundColor: '#ffffff',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <div>
                    <strong style={{ fontSize: '15px', color: '#0f172a' }}>{res.name}</strong>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>Code: {res.resource_code}</div>
                  </div>
                  <span
                    className={`status-badge ${res.status === 'Available' ? 'badge-resolved' : res.status === 'Assigned' ? 'badge-dispatched' : 'badge-low'}`}
                  >
                    {res.status}
                  </span>
                </div>

                <div style={{ fontSize: '12.5px', color: '#475569', lineHeight: 1.5, marginBottom: '12px' }}>
                  <div><strong>Category:</strong> {res.category}</div>
                  <div><strong>Base:</strong> {res.location_name}</div>
                  <div><strong>Capabilities:</strong> {res.capabilities}</div>
                  <div><strong>Contact:</strong> {res.contact_phone}</div>
                </div>

                <div style={{ display: 'flex', gap: '6px' }}>
                  {res.status !== 'Available' ? (
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => handleReleaseResource(res.id)}
                      style={{ color: '#166534' }}
                    >
                      Mark Available
                    </button>
                  ) : (
                    <button
                      className="btn btn-outline btn-sm"
                      onClick={() => updateResourceStatus(res.id, 'Under Maintenance')}
                      style={{ color: '#d97706' }}
                    >
                      Set Maintenance
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 4: SMART ALLOCATION & SHORTAGES */}
      {/* ==================================================================== */}
      {activeTab === 'allocation' && (
        <div>
          {/* Explainable Allocation Card */}
          <div className="card">
            <h3 className="card-title">Smart Resource Allocation Engine</h3>
            <p style={{ color: '#64748b', fontSize: '13.5px', marginBottom: '16px' }}>
              Evaluates incident urgency, capability match, and geographic travel time while strictly enforcing conflict prevention.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {incidents.filter(i => !['Resolved','Cancelled'].includes(i.status)).map((inc) => {
                const assigned = resources.find(r => r.current_assignment_id === inc.id);

                return (
                  <div
                    key={inc.id}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                      padding: '16px',
                      backgroundColor: assigned ? '#f0fdf4' : '#ffffff',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <strong>{inc.incident_code}</strong>
                        <span>({inc.category} in {inc.location_name})</span>
                        <span className={`status-badge ${inc.priority === 'Critical' ? 'badge-critical' : 'badge-high'}`}>
                          {inc.priority}
                        </span>
                      </div>
                      <span className="status-badge badge-dispatched">{inc.status}</span>
                    </div>

                    {assigned ? (
                      <div style={{ fontSize: '13px', color: '#166534' }}>
                        ✓ <strong>Assigned Resource:</strong> {assigned.name} ({assigned.category}) • Base: {assigned.location_name}
                      </div>
                    ) : (
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                        <div style={{ fontSize: '13px', color: '#b91c1c' }}>
                          ⚠️ Unassigned incident. Seeking specialist team match...
                        </div>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          {resources.filter(r => r.status === 'Available').slice(0, 2).map((res) => (
                            <button
                              key={res.id}
                              className="btn btn-teal btn-sm"
                              onClick={() => handleAssignResource(inc.id, res.id)}
                            >
                              Allocate {res.resource_code}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Shortage Management Panel */}
          <div className="card" style={{ backgroundColor: '#fff1f2', borderColor: '#fecdd3' }}>
            <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#9f1239', marginBottom: '8px' }}>
              Active Resource Shortage Management
            </h3>
            <p style={{ color: '#881337', fontSize: '13.5px', marginBottom: '16px' }}>
              When city fleet resources are depleted, CareOn recommends engaging external partner hospitals or private ambulances.
            </p>

            {shortages.shortages && shortages.shortages.length > 0 ? (
              shortages.shortages.map((s, idx) => (
                <div
                  key={idx}
                  style={{
                    backgroundColor: '#ffffff',
                    border: '1px solid #fda4af',
                    padding: '14px',
                    borderRadius: '8px',
                    marginBottom: '10px',
                  }}
                >
                  <div style={{ fontWeight: 800, color: '#9f1239', fontSize: '14px', marginBottom: '4px' }}>
                    Incident {s.incident_code}: Shortage of {s.missing_resource_type}
                  </div>
                  <div style={{ fontSize: '13px', color: '#334155', marginBottom: '8px' }}>
                    Location: {s.location} • Category: {s.category}
                  </div>
                  {s.suggested_provider && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: '12.5px', color: '#0f4c5c' }}>
                        Recommended External Partner: <strong>{s.suggested_provider.name}</strong> (Base: ₹{s.suggested_provider.estimated_charge})
                      </div>
                      <button
                        className="btn btn-primary-red btn-sm"
                        onClick={() => handleSimulateContactProvider(s.incident_id, s.suggested_provider.id)}
                      >
                        Simulate Partner Contact
                      </button>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div style={{ color: '#166534', fontWeight: 600, fontSize: '13px' }}>
                ✓ No active fleet shortages at this time. All active calls have available response units.
              </div>
            )}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 5: EXTERNAL PROVIDERS */}
      {/* ==================================================================== */}
      {activeTab === 'providers' && (
        <div className="card">
          <h3 className="card-title">Registered Partners & External Providers Directory</h3>
          <p style={{ color: '#64748b', fontSize: '13.5px', marginBottom: '20px' }}>
            CareOn operates with a partner-first fallback strategy. An external provider quotation requires informed user consent before dispatch confirmation.
          </p>

          <div className="grid-2">
            {providers.map((prov) => (
              <div
                key={prov.id}
                style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '16px',
                  backgroundColor: prov.is_registered_partner ? '#f0fdfa' : '#ffffff',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                  <div>
                    <h4 style={{ fontSize: '16px', fontWeight: 800, color: '#0f172a' }}>{prov.name}</h4>
                    <div style={{ fontSize: '12px', color: '#64748b' }}>
                      {prov.provider_type} • {prov.location_name}
                    </div>
                  </div>
                  <span className={`status-badge ${prov.is_registered_partner ? 'badge-resolved' : 'badge-low'}`}>
                    {prov.is_registered_partner ? 'Registered Partner' : 'Fallback Directory'}
                  </span>
                </div>

                <div style={{ fontSize: '13px', color: '#475569', lineHeight: 1.5, marginBottom: '14px' }}>
                  <div><strong>Contact Person:</strong> {prov.contact_person} ({prov.phone})</div>
                  <div><strong>Capabilities:</strong> {prov.service_capabilities}</div>
                  <div><strong>Base Service Charge:</strong> ₹{prov.estimated_base_charge}</div>
                </div>

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="btn btn-teal btn-sm"
                    onClick={() => {
                      const firstActiveInc = incidents.find(i => !['Resolved','Cancelled'].includes(i.status));
                      if (firstActiveInc) {
                        handleSimulateContactProvider(firstActiveInc.id, prov.id);
                      } else {
                        alert('No active emergency incidents currently requiring external dispatch.');
                      }
                    }}
                  >
                    Simulate Contact & Quotation
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 6: LIVE MAP & DISPATCH */}
      {/* ==================================================================== */}
      {activeTab === 'map' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 800 }}>Live Geographical Dispatch & Tracking</h3>
              <p style={{ color: '#64748b', fontSize: '13px' }}>
                OpenStreetMap Leaflet visualization showing active emergency pins, available units, and partner facilities.
              </p>
            </div>
            <button
              className="btn btn-primary-red btn-sm"
              onClick={() => setIsSimulatingMapMovement(!isSimulatingMapMovement)}
            >
              {isSimulatingMapMovement ? '⏸ Pause Movement Simulation' : '▶ Simulate Live Dispatch Movement'}
            </button>
          </div>

          <GoogleMap
            incidents={incidents}
            resources={resources}
            providers={providers}
            isSimulationActive={isSimulatingMapMovement}
          />
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 7: SIMULATION CENTRE (RESOURCE SHORTAGE CHALLENGE) */}
      {/* ==================================================================== */}
      {activeTab === 'simulation' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0f4c5c' }}>
                🎯 Resource Shortage Challenge — Expo Demonstration
              </h3>
              <p style={{ color: '#64748b', fontSize: '14px', maxWidth: '720px', marginTop: '4px' }}>
                This interactive walkthrough demonstrates CareOn's core technical value: multi-incident prioritization, conflict prevention, shortage detection, and external provider coordination.
              </p>
            </div>
            <button className="btn btn-primary-red btn-sm" onClick={handleResetDemoData}>
              ↺ Reset Scenario to Step 1
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ padding: '16px', border: '1px solid #e2e8f0', borderRadius: '8px', backgroundColor: '#f8fafc' }}>
              <div style={{ fontWeight: 800, fontSize: '15px', color: '#0f172a', marginBottom: '6px' }}>
                Step 1: Multiple Simultaneous Emergencies Loaded
              </div>
              <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.5 }}>
                Three simultaneous emergencies are active across Mysuru (Sayyaji Rao Road cardiac arrest, Kuvempunagar road accident, and Gokulam kitchen fire).
              </p>
            </div>

            <div style={{ padding: '16px', border: '1px solid #e2e8f0', borderRadius: '8px', backgroundColor: '#f8fafc' }}>
              <div style={{ fontWeight: 800, fontSize: '15px', color: '#0f172a', marginBottom: '6px' }}>
                Step 2: Fleet Constrained (Only 1 Ambulance Available)
              </div>
              <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.5 }}>
                Ambulance 01 is assigned to CARE-2026-101. Ambulance 03 is in maintenance. Only CityCare Ambulance 02 remains in the active fleet.
              </p>
            </div>

            <div style={{ padding: '16px', border: '1px solid #e2e8f0', borderRadius: '8px', backgroundColor: '#f8fafc' }}>
              <div style={{ fontWeight: 800, fontSize: '15px', color: '#0f172a', marginBottom: '6px' }}>
                Step 3: Run Allocation & Demonstrate Conflict Prevention
              </div>
              <p style={{ fontSize: '13px', color: '#64748b', lineHeight: 1.5, marginBottom: '10px' }}>
                The smart allocator awards the remaining ambulance to the highest priority call. The system strictly blocks assigning the occupied ambulance to another active incident.
              </p>
              <button
                className="btn btn-teal btn-sm"
                onClick={() => {
                  const amb2 = resources.find(r => r.resource_code === 'AMB-02');
                  const inc102 = incidents.find(i => i.incident_code === 'CARE-2026-102');
                  if (amb2 && inc102) {
                    handleAssignResource(inc102.id, amb2.id);
                  }
                }}
              >
                Assign AMB-02 to CARE-2026-102
              </button>
            </div>

            <div style={{ padding: '16px', border: '1px solid #fecdd3', borderRadius: '8px', backgroundColor: '#fff1f2' }}>
              <div style={{ fontWeight: 800, fontSize: '15px', color: '#9f1239', marginBottom: '6px' }}>
                Step 4: Shortage Alert & Partner Enquiry
              </div>
              <p style={{ fontSize: '13px', color: '#881337', lineHeight: 1.5, marginBottom: '10px' }}>
                CARE-2026-103 experiences a critical fleet shortage. Contact the registered partner (CityCare Private Fleet) and record the quotation (₹1,500).
              </p>
              <button
                className="btn btn-primary-red btn-sm"
                onClick={() => {
                  const inc103 = incidents.find(i => i.incident_code === 'CARE-2026-103');
                  const prov = providers[1] || providers[0];
                  if (inc103 && prov) {
                    handleSimulateContactProvider(inc103.id, prov.id);
                  }
                }}
              >
                Record Partner Quote for CARE-2026-103
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 8: VERIFICATION & TRUST REVIEW */}
      {/* ==================================================================== */}
      {activeTab === 'verification' && (
        <div className="card">
          <h3 className="card-title">Reporter Verification & Trust Review</h3>
          <p style={{ color: '#64748b', fontSize: '13.5px', marginBottom: '20px' }}>
            CareOn assesses trust signals (phone format, OTP verification, proximity duplicates, reporting history) to prevent deliberate misuse without deterring genuine citizens.
          </p>

          <div className="table-wrapper">
            <table className="careon-table">
              <thead>
                <tr>
                  <th>Incident Code</th>
                  <th>Contact Person</th>
                  <th>Phone Number</th>
                  <th>OTP Status</th>
                  <th>Duplicate Check</th>
                  <th>Trust Decision</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr key={inc.id}>
                    <td><strong>{inc.incident_code}</strong></td>
                    <td>{inc.contact_name}</td>
                    <td>{inc.contact_phone}</td>
                    <td>
                      {inc.is_verified ? (
                        <span style={{ color: '#166534', fontWeight: 700 }}>✓ Verified (Code: {inc.verification_otp})</span>
                      ) : (
                        <span style={{ color: '#b45309', fontWeight: 600 }}>Awaiting OTP ({inc.verification_otp})</span>
                      )}
                    </td>
                    <td>
                      {inc.is_duplicate ? (
                        <span className="status-badge badge-critical">Flagged Proximity Duplicate</span>
                      ) : (
                        <span style={{ color: '#166534' }}>✓ Unique Incident</span>
                      )}
                    </td>
                    <td>
                      <span className="status-badge badge-resolved">Genuine Incident</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 9: DISASTER RELIEF MODE */}
      {/* ==================================================================== */}
      {activeTab === 'disaster' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#0f4c5c' }}>
                🌊 Disaster Management & Mass Casualty Extension
              </h3>
              <p style={{ color: '#64748b', fontSize: '13px' }}>
                Tracking supplies (food, drinking water, family tents) and coordination for large-scale urban flooding or structural collapse.
              </p>
            </div>
          </div>

          <div className="grid-2">
            <div style={{ border: '1px solid #bae6fd', backgroundColor: '#f0f9ff', padding: '16px', borderRadius: '10px' }}>
              <h4 style={{ fontSize: '15px', fontWeight: 700, color: '#0369a1', marginBottom: '8px' }}>
                Active Disaster Incident: CARE-2026-104 (Hebbal Lake Catchment, Mysuru)
              </h4>
              <p style={{ fontSize: '13px', color: '#0c4a6e', lineHeight: 1.5, marginBottom: '12px' }}>
                Affected Individuals: <strong>25 residents trapped by flash flooding</strong>.<br/>
                Relief Supplies Requested: <i>Drinking water (500L), ready-to-eat meals (100 pkts), inflatable rescue rafts.</i>
              </p>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  className="btn btn-teal btn-sm"
                  onClick={() => {
                    const relRes = resources.find(r => r.resource_code === 'REL-01');
                    const inc104 = incidents.find(i => i.incident_code === 'CARE-2026-104');
                    if (relRes && inc104) {
                      handleAssignResource(inc104.id, relRes.id);
                    }
                  }}
                >
                  Dispatch Disaster Relief Supply Van 01
                </button>
              </div>
            </div>

            <div style={{ border: '1px solid #bbf7d0', backgroundColor: '#f0fdf4', padding: '16px', borderRadius: '10px' }}>
              <h4 style={{ fontSize: '15px', fontWeight: 700, color: '#166534', marginBottom: '8px' }}>
                Available Relief Assets
              </h4>
              <div style={{ fontSize: '13px', color: '#14532d', lineHeight: 1.6 }}>
                <div>• <strong>REL-01:</strong> Disaster Relief Van (Food & Clean Water Supply) — Available</div>
                <div>• <strong>SHELTER-01:</strong> Community Relief Centre (150 capacity, Kuvempunagar, Mysuru) — Available</div>
                <div>• <strong>RES-01:</strong> Urban Search & Rescue Squad (Inflatable boats) — Available</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================================================================== */}
      {/* TAB 10: ANALYTICS & ML PREDICTIONS */}
      {/* ==================================================================== */}
      {activeTab === 'analytics' && (
        <div>
          {/* Performance KPIs */}
          <div className="grid-3" style={{ marginBottom: '20px' }}>
            <div className="card" style={{ marginBottom: 0 }}>
              <div style={{ fontSize: '13px', color: '#64748b', fontWeight: 700 }}>AVG COORDINATOR RATING</div>
              <div style={{ fontSize: '32px', fontWeight: 800, color: '#f59e0b', margin: '6px 0' }}>
                ★ 4.9 / 5.0
              </div>
              <div style={{ fontSize: '12px', color: '#10b981' }}>From 14 verified reporter reviews</div>
            </div>

            <div className="card" style={{ marginBottom: 0 }}>
              <div style={{ fontSize: '13px', color: '#64748b', fontWeight: 700 }}>ESTIMATED AVERAGE ETA</div>
              <div style={{ fontSize: '32px', fontWeight: 800, color: '#0f4c5c', margin: '6px 0' }}>
                7.4 mins
              </div>
              <div style={{ fontSize: '12px', color: '#64748b' }}>Urban corridor with 1.25x traffic factor</div>
            </div>

            <div className="card" style={{ marginBottom: 0 }}>
              <div style={{ fontSize: '13px', color: '#64748b', fontWeight: 700 }}>CONFLICT PREVENTION RATE</div>
              <div style={{ fontSize: '32px', fontWeight: 800, color: '#10b981', margin: '6px 0' }}>
                100%
              </div>
              <div style={{ fontSize: '12px', color: '#10b981' }}>0 double-assignments recorded</div>
            </div>
          </div>

          {/* Machine Learning / Heuristic Shortage Risk Prediction */}
          <div className="card">
            <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#0f4c5c', marginBottom: '8px' }}>
              🤖 ML-Based Resource Shortage Risk Predictor
            </h3>
            <p style={{ color: '#64748b', fontSize: '13px', marginBottom: '16px' }}>
              Calculates estimated demand surges by zone, time-of-day multipliers, and active fleet buffer.
            </p>

            <div className="table-wrapper">
              <table className="careon-table">
                <thead>
                  <tr>
                    <th>Geographic Zone</th>
                    <th>Predicted Shortage Risk</th>
                    <th>Risk Score</th>
                    <th>Resource in Demand</th>
                    <th>Time Context</th>
                    <th>Recommended Coordinator Action</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.map((p, idx) => (
                    <tr key={idx}>
                      <td><strong>{p.zone}</strong></td>
                      <td>
                        <span className={`status-badge ${p.predicted_shortage_risk === 'High' ? 'badge-critical' : p.predicted_shortage_risk === 'Moderate' ? 'badge-high' : 'badge-resolved'}`}>
                          {p.predicted_shortage_risk} Risk
                        </span>
                      </td>
                      <td>{p.risk_score}</td>
                      <td>{p.likely_resource_in_demand}</td>
                      <td>{p.time_window_context}</td>
                      <td style={{ fontSize: '12px', color: '#0f4c5c' }}>{p.recommended_coordinator_action}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ marginTop: '12px', fontSize: '11.5px', color: '#94a3b8', fontStyle: 'italic' }}>
              Notice: Sample-data predictive baseline model for university demonstration. Not an official municipal emergency forecast.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
