import React, { useState, useEffect } from 'react';
import { Clock, AlertTriangle, Trash2, ArrowRight, CheckCircle2 } from 'lucide-react';
import {
  Button,
  Card,
  Badge,
  Alert,
  colors,
  typography,
} from '@careon/design-system';
import { getLocalDrafts, deleteLocalDraft } from '../services/offlineDrafts.js';

export function DraftsManager({ onNavigate }) {
  const [drafts, setDrafts] = useState([]);

  const loadDrafts = () => {
    setDrafts(getLocalDrafts());
  };

  useEffect(() => {
    loadDrafts();
  }, []);

  const handleDelete = (id) => {
    deleteLocalDraft(id);
    loadDrafts();
  };

  const handleResume = (id) => {
    onNavigate(`/report?draftId=${encodeURIComponent(id)}`);
  };

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto', padding: '24px 16px' }}>
      <h1 style={{ margin: '0 0 8px', fontSize: '1.5rem', fontWeight: typography.fontWeight.bold, color: colors.textPrimary }}>
        Saved Local Emergency Drafts
      </h1>
      <p style={{ margin: '0 0 20px', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
        These emergency reports were drafted while offline or saved for review.
      </p>

      <Alert variant="warning" icon={AlertTriangle}>
        <strong>CRITICAL SAFETY RULE:</strong> Local drafts have NOT been transmitted to emergency dispatch. Responders will NOT be dispatched until you review and submit the report while online.
      </Alert>

      {drafts.length === 0 ? (
        <Card padding="lg" style={{ textAlign: 'center', color: colors.textSecondary }}>
          No local drafts stored. All emergency reports are submitted or discarded.
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {drafts.map((d) => (
            <Card
              key={d.id}
              padding="md"
              style={{
                borderLeft: d.isStale ? '4px solid #D99022' : `4px solid ${colors.secondary}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <strong style={{ fontSize: typography.fontSize.base, color: colors.textPrimary }}>
                      {d.category || 'Uncategorized Emergency'}
                    </strong>
                    {d.isStale && (
                      <Badge variant="warning">
                        Stale (&gt; 24h old)
                      </Badge>
                    )}
                  </div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textSecondary }}>
                    Location: {d.location_name || 'No location specified'}
                  </div>
                </div>

                <span style={{ fontSize: typography.fontSize.xs, color: colors.textMuted }}>
                  {new Date(d.updatedAt || d.createdAt).toLocaleString()}
                </span>
              </div>

              {d.description && (
                <p style={{ margin: '0 0 16px', fontSize: typography.fontSize.sm, color: colors.textSecondary }}>
                  "{d.description}"
                </p>
              )}

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', borderTop: `1px solid ${colors.border}`, paddingTop: '12px' }}>
                <Button
                  size="sm"
                  variant="tertiary"
                  onClick={() => handleDelete(d.id)}
                  icon={Trash2}
                >
                  Discard
                </Button>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => handleResume(d.id)}
                  icon={ArrowRight}
                  iconPosition="right"
                >
                  Resume & Submit
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
