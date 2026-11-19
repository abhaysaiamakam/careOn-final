import React from 'react';
import { AlertCircle, Inbox, Bed, Activity, FileText } from 'lucide-react';

const iconMap = {
  inbox: Inbox,
  alert: AlertCircle,
  bed: Bed,
  activity: Activity,
  file: FileText,
};

export function EmptyState({
  icon = 'inbox',
  title = 'No Data Available',
  message = 'There are no active records in the central registry at this time.',
  action = null,
  compact = false,
}) {
  const IconComponent = iconMap[icon] || Inbox;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: compact ? '24px 16px' : '48px 24px',
        backgroundColor: '#FFFFFF',
        border: '1px solid #E5E7EB',
        borderRadius: '8px',
        textAlign: 'center',
        minHeight: compact ? '160px' : '260px',
      }}
    >
      <div
        style={{
          width: compact ? '40px' : '52px',
          height: compact ? '40px' : '52px',
          borderRadius: '50%',
          backgroundColor: '#F3F4F6',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#6B7280',
          marginBottom: '16px',
        }}
      >
        <IconComponent size={compact ? 22 : 28} strokeWidth={1.75} />
      </div>
      <h3
        style={{
          fontSize: compact ? '14px' : '16px',
          fontWeight: 600,
          color: '#111827',
          marginBottom: '6px',
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: compact ? '12px' : '14px',
          color: '#6B7280',
          maxWidth: '420px',
          lineHeight: 1.5,
          marginBottom: action ? '20px' : '0',
        }}
      >
        {message}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
}

export default EmptyState;
