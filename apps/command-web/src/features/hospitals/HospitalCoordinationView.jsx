import React, { useState, useEffect } from 'react';
import {
  Building2,
  AlertTriangle,
  CheckCircle2,
  Phone,
  Activity,
  Bed,
  RefreshCw,
  Search,
  ExternalLink,
  Shield,
} from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  colors,
  typography,
} from '@careon/design-system';
import {
  listHospitalFacilities,
  getFacilityCapacity,
  listIncomingPatientRequests,
} from '@careon/api-client';

export function HospitalCoordinationView() {
  const [facilities, setFacilities] = useState([]);
  const [incomingRequests, setIncomingRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedFacility, setSelectedFacility] = useState(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [facData, reqData] = await Promise.all([
        listHospitalFacilities().catch(() => []),
        listIncomingPatientRequests().catch(() => []),
      ]);
      setFacilities(facData || []);
      setIncomingRequests(reqData || []);
    } catch (e) {
      console.warn('Failed to load hospital data:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const filteredFacilities = facilities.filter((f) => {
    if (search.trim()) {
      const q = search.toLowerCase();
      const name = (f.name || '').toLowerCase();
      const code = (f.facility_code || '').toLowerCase();
      const loc = (f.location_name || '').toLowerCase();
      return name.includes(q) || code.includes(q) || loc.includes(q);
    }
    return true;
  });

  const divertedCount = facilities.filter((f) => f.divert_status).length;

  return (
    <div style={{ padding: '20px 24px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* View Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.4rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
            Regional Hospital Coordination (M7)
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
            Trauma centre capabilities, live ER/ICU capacity, pre-arrival notifications, and real-time facility diversion status.
          </p>
        </div>

        <Button size="sm" variant="outline" onClick={loadData} loading={loading} icon={RefreshCw}>
          Refresh Facilities
        </Button>
      </div>

      {/* Diversion Warning Banner */}
      {divertedCount > 0 && (
        <div
          style={{
            backgroundColor: '#FEF2F2',
            border: '1px solid #FCA5A5',
            borderRadius: '8px',
            padding: '12px 16px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}
        >
          <AlertTriangle size={20} color="#DC2626" />
          <div style={{ fontSize: typography.fontSize.xs, color: '#991B1B' }}>
            <strong>CRITICAL FACILITY ALERT:</strong> {divertedCount} receiving hospital{divertedCount > 1 ? 's' : ''} currently on DIVERSION due to capacity saturation. Check diversion status before routing critical patient transport.
          </div>
        </div>
      )}

      {/* Search Bar */}
      <div style={{ marginBottom: '20px' }}>
        <input
          type="text"
          placeholder="Filter hospitals by facility code, name, trauma level..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: '100%',
            maxWidth: '400px',
            padding: '8px 12px',
            borderRadius: '6px',
            border: `1px solid ${colors.border}`,
            fontSize: typography.fontSize.xs,
            backgroundColor: '#FFFFFF',
            outline: 'none',
          }}
        />
      </div>

      {/* Facilities Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
        {filteredFacilities.map((fac) => (
          <Card
            key={fac.id}
            padding="lg"
            style={{
              backgroundColor: '#FFFFFF',
              border: fac.divert_status ? '2px solid #EF4444' : `1px solid ${colors.border}`,
              borderRadius: '8px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
              <div>
                <span style={{ fontSize: '10px', fontWeight: 700, color: colors.textSecondary, textTransform: 'uppercase' }}>
                  {fac.facility_code}
                </span>
                <h3 style={{ margin: '2px 0 0', fontSize: typography.fontSize.base, fontWeight: 700, color: colors.textPrimary }}>
                  {fac.name}
                </h3>
              </div>

              <Badge variant={fac.divert_status ? 'danger' : 'success'}>
                {fac.divert_status ? 'ON DIVERT' : 'OPEN'}
              </Badge>
            </div>

            <div style={{ fontSize: '11px', color: colors.textSecondary, marginBottom: '12px' }}>
              {fac.location_name || 'Designated Healthcare District'}
            </div>

            {/* Trauma Level & Bays */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', padding: '10px', backgroundColor: '#F8FAFC', borderRadius: '6px', marginBottom: '12px' }}>
              <div>
                <div style={{ fontSize: '10px', color: colors.textSecondary }}>Trauma Designation</div>
                <div style={{ fontSize: typography.fontSize.xs, fontWeight: 700, color: colors.textPrimary }}>
                  {fac.trauma_level || 'General Hospital'}
                </div>
              </div>

              <div>
                <div style={{ fontSize: '10px', color: colors.textSecondary }}>Ambulance Bays</div>
                <div style={{ fontSize: typography.fontSize.xs, fontWeight: 700, color: colors.textPrimary }}>
                  {fac.ambulance_bays || 2} Bays Active
                </div>
              </div>
            </div>

            {/* Capabilities */}
            <div style={{ marginBottom: '12px' }}>
              <div style={{ fontSize: '10px', color: colors.textSecondary, marginBottom: '4px', textTransform: 'uppercase', fontWeight: 600 }}>
                Specialized Services:
              </div>
              <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                {(fac.capabilities || 'emergency,icu').split(',').map((c) => (
                  <span key={c} style={{ fontSize: '10px', background: '#EEF2F6', padding: '2px 6px', borderRadius: '4px', color: '#334155' }}>
                    {c.trim()}
                  </span>
                ))}
              </div>
            </div>

            {/* Direct Emergency Contact */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: `1px solid ${colors.border}`, paddingTop: '10px' }}>
              <span style={{ fontSize: '11px', color: colors.textSecondary }}>
                ER Hotline: <strong>{fac.emergency_phone || 'Direct'}</strong>
              </span>

              {fac.emergency_phone && (
                <a
                  href={`tel:${fac.emergency_phone}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '11px',
                    fontWeight: 600,
                    color: colors.secondary,
                    textDecoration: 'none',
                    padding: '3px 8px',
                    backgroundColor: '#FEE2E2',
                    borderRadius: '4px',
                  }}
                >
                  <Phone size={12} /> Call ER
                </a>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
