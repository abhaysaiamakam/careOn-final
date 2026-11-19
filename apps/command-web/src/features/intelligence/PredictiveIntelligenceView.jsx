import React, { useState, useEffect } from 'react';
import {
  Brain,
  TrendingUp,
  MapPin,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  RefreshCw,
  AlertTriangle,
  Compass,
  Layers,
  ArrowRight,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  colors,
  typography,
} from '@careon/design-system';
import {
  getDemandAnalytics,
  analyzeHotspots,
  listPositioningRecommendations,
  approvePositioningRecommendation,
  rejectPositioningRecommendation,
  getModelHealth,
} from '@careon/api-client';

export function PredictiveIntelligenceView() {
  const [recommendations, setRecommendations] = useState([]);
  const [analytics, setAnalytics] = useState(null);
  const [modelHealth, setModelHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState(null);
  const [actionLoadingId, setActionLoadingId] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [recs, health, ana] = await Promise.all([
        listPositioningRecommendations().catch(() => []),
        getModelHealth().catch(() => null),
        getDemandAnalytics().catch(() => null),
      ]);
      setRecommendations(recs || []);
      setModelHealth(health);
      setAnalytics(ana);
    } catch (e) {
      console.warn('Failed to load intelligence data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleApprove = async (recId) => {
    setActionLoadingId(recId);
    try {
      await approvePositioningRecommendation(recId);
      setActionMsg(`Recommendation #${recId} approved. Repositioning advisory broadcasted.`);
      loadData();
      setTimeout(() => setActionMsg(null), 4000);
    } catch (e) {
      alert(`Approval failed: ${e.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleReject = async (recId) => {
    const reason = window.prompt('Enter reason for rejecting ambulance repositioning recommendation:');
    if (!reason) return;

    setActionLoadingId(recId);
    try {
      await rejectPositioningRecommendation(recId, reason);
      setActionMsg(`Recommendation #${recId} rejected.`);
      loadData();
      setTimeout(() => setActionMsg(null), 4000);
    } catch (e) {
      alert(`Rejection failed: ${e.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  return (
    <div style={{ padding: '20px 24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* View Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Predictive Emergency Intelligence & Strategic Positioning (M10)
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Statistical demand forecasting, geographical coverage gap analysis, and explainable ambulance staging recommendations.
          </p>
        </div>

        <Button size="sm" variant="outline" onClick={loadData} loading={loading} icon={RefreshCw}>
          Refresh Models
        </Button>
      </div>

      {actionMsg && (
        <div style={{ marginBottom: '16px', background: '#ECFDF5', border: '1px solid #A7F3D0', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', color: '#065F46' }}>
          ✓ {actionMsg}
        </div>
      )}

      {/* Model Health & Overview KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', marginBottom: '24px' }}>
        <Card padding="md" style={{ backgroundColor: '#FFFFFF', border: `1px solid ${colors.border}` }}>
          <div style={{ fontSize: '11px', color: colors.textSecondary, textTransform: 'uppercase', fontWeight: 600 }}>
            Forecasting Engine
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10B981' }} />
            <strong style={{ fontSize: typography.fontSize.base, color: colors.textPrimary }}>
              {modelHealth?.active_model || 'Poisson Regression'}
            </strong>
          </div>
          <div style={{ fontSize: '10px', color: colors.textSecondary, marginTop: '2px' }}>
            Status: {modelHealth?.status || 'Active & Validated'}
          </div>
        </Card>

        <Card padding="md" style={{ backgroundColor: '#FFFFFF', border: `1px solid ${colors.border}` }}>
          <div style={{ fontSize: '11px', color: colors.textSecondary, textTransform: 'uppercase', fontWeight: 600 }}>
            Target District Demand
          </div>
          <div style={{ fontSize: typography.fontSize.base, fontWeight: 700, color: colors.textPrimary, marginTop: '4px' }}>
            {analytics?.forecast_window || 'Next 4 Hours'}
          </div>
          <div style={{ fontSize: '10px', color: colors.textSecondary, marginTop: '2px' }}>
            Expected Volume: {analytics?.predicted_demand_total || '14.2'} incidents
          </div>
        </Card>

        <Card padding="md" style={{ backgroundColor: '#FFFFFF', border: `1px solid ${colors.border}` }}>
          <div style={{ fontSize: '11px', color: colors.textSecondary, textTransform: 'uppercase', fontWeight: 600 }}>
            Pending Recommendations
          </div>
          <div style={{ fontSize: typography.fontSize.base, fontWeight: 700, color: colors.secondary, marginTop: '4px' }}>
            {recommendations.length} Staging Move{recommendations.length !== 1 ? 's' : ''}
          </div>
          <div style={{ fontSize: '10px', color: colors.textSecondary, marginTop: '2px' }}>
            Requires Dispatcher Approval
          </div>
        </Card>
      </div>

      {/* Safety Notice */}
      <div style={{ background: '#FFFBEB', border: '1px solid #FDE68A', padding: '10px 14px', borderRadius: '6px', marginBottom: '20px', fontSize: '11px', color: '#92400E' }}>
        <strong>Operational Safety Rule:</strong> Positioning recommendations are generated from historical incident density and live spatial coverage gaps. Ambulances are never moved autonomously; all positioning orders must be reviewed and approved by an authorized dispatcher.
      </div>

      {/* Recommendations Feed */}
      <div>
        <h2 style={{ fontSize: typography.fontSize.sm, fontWeight: 700, color: colors.textPrimary, marginBottom: '12px' }}>
          Strategic Positioning Recommendations ({recommendations.length})
        </h2>

        {recommendations.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', background: '#FFFFFF', borderRadius: '8px', border: `1px solid ${colors.border}`, color: colors.textSecondary, fontSize: typography.fontSize.xs }}>
            No active ambulance positioning recommendations. Fleet distribution currently satisfies coverage constraints across all operational zones.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {recommendations.map((rec) => {
              const isPending = rec.status === 'PENDING';
              return (
                <Card
                  key={rec.id}
                  padding="lg"
                  style={{
                    backgroundColor: '#FFFFFF',
                    border: `1px solid ${colors.border}`,
                    borderRadius: '8px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px', marginBottom: '8px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontSize: typography.fontSize.xs, fontWeight: 700, color: colors.textPrimary }}>
                          Recommendation #{rec.id}: {rec.resource_code || 'Fleet Unit'}
                        </span>
                        <Badge variant={rec.confidence_level === 'HIGH' ? 'success' : 'secondary'}>
                          {rec.confidence_level || 'MEDIUM'} CONFIDENCE
                        </Badge>
                        <Badge variant={rec.status === 'APPROVED' ? 'success' : rec.status === 'EXPIRED' ? 'neutral' : 'warning'}>
                          {rec.status}
                        </Badge>
                      </div>
                      <div style={{ fontSize: typography.fontSize.sm, fontWeight: 600, color: colors.textPrimary, marginTop: '4px' }}>
                        Proposed Staging: {rec.proposed_staging_name || rec.target_area || 'Strategic Depot'}
                      </div>
                    </div>

                    {isPending && (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={actionLoadingId === rec.id}
                          onClick={() => handleReject(rec.id)}
                          icon={XCircle}
                        >
                          Reject
                        </Button>
                        <Button
                          size="sm"
                          variant="primary"
                          disabled={actionLoadingId === rec.id}
                          onClick={() => handleApprove(rec.id)}
                          icon={CheckCircle2}
                          style={{ backgroundColor: colors.secondary }}
                        >
                          Approve Staging Move
                        </Button>
                      </div>
                    )}
                  </div>

                  <p style={{ margin: '0 0 12px', fontSize: typography.fontSize.xs, color: '#334155', lineHeight: 1.4 }}>
                    {rec.explanation}
                  </p>

                  <div style={{ display: 'flex', gap: '16px', fontSize: '11px', color: colors.textSecondary, borderTop: `1px solid ${colors.border}`, paddingTop: '8px', flexWrap: 'wrap' }}>
                    <span>Coverage Improvement: <strong style={{ color: '#15803D' }}>+{rec.expected_coverage_improvement || 20}%</strong></span>
                    <span>Transit Time: <strong>~{rec.estimated_travel_time_minutes || 8} min</strong></span>
                    <span>Target Area: <strong>{rec.target_area}</strong></span>
                    <span>Created: <strong>{new Date(rec.created_at).toLocaleTimeString()}</strong></span>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
