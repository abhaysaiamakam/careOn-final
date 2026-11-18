import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PortalBar from '../apps/portal/PortalBar';
import { Button, Card, Badge, Input, StatusIndicator } from '../packages/design-system';
import { apiClient, responderApi, hospitalApi, superAdminApi } from '../packages/api-client';

describe('Milestone 3 — Five-Application Ecosystem & Frontend Architecture', () => {
  describe('PortalBar Application Switcher', () => {
    it('renders all five application options', () => {
      const handleSelect = vi.fn();
      render(<PortalBar currentApp="citizen" onSelectApp={handleSelect} />);

      expect(screen.getByText(/Citizen SOS/i)).toBeInTheDocument();
      expect(screen.getByText(/Dispatch Command/i)).toBeInTheDocument();
      expect(screen.getByText(/Field Responder/i)).toBeInTheDocument();
      expect(screen.getByText(/Hospital Portal/i)).toBeInTheDocument();
      expect(screen.getByText(/Super Admin/i)).toBeInTheDocument();
    });

    it('triggers onSelectApp when an app button is clicked', () => {
      const handleSelect = vi.fn();
      render(<PortalBar currentApp="citizen" onSelectApp={handleSelect} />);

      const responderBtn = screen.getByText(/Field Responder/i).closest('button');
      fireEvent.click(responderBtn);

      expect(handleSelect).toHaveBeenCalledWith('responder');
    });
  });

  describe('Design System Tokens & Components', () => {
    it('renders Button with variants and handles clicks', () => {
      const handleClick = vi.fn();
      render(
        <Button variant="danger" size="lg" onClick={handleClick}>
          Emergency SOS
        </Button>
      );
      const btn = screen.getByText('Emergency SOS');
      expect(btn).toBeInTheDocument();
      fireEvent.click(btn);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('renders Badge with correct status semantics', () => {
      render(<Badge variant="critical">CRITICAL</Badge>);
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    });

    it('renders Card with header and content', () => {
      render(
        <Card header={<div>Mission Header</div>}>
          <div>Incident in progress</div>
        </Card>
      );
      expect(screen.getByText('Mission Header')).toBeInTheDocument();
      expect(screen.getByText('Incident in progress')).toBeInTheDocument();
    });

    it('renders Input with labels and error states', () => {
      render(
        <Input
          label="Ambulance Code"
          value="AMB-01"
          onChange={() => {}}
          error="Invalid unit ID"
        />
      );
      expect(screen.getByText('Ambulance Code')).toBeInTheDocument();
      expect(screen.getByText('Invalid unit ID')).toBeInTheDocument();
    });

    it('renders StatusIndicator with label', () => {
      render(<StatusIndicator status="active" label="Telemetry Connected" />);
      expect(screen.getByText('Telemetry Connected')).toBeInTheDocument();
    });
  });

  describe('Unified API Client Contracts', () => {
    it('exports all 5 domain-specific API clients', () => {
      expect(apiClient).toBeDefined();
      expect(typeof responderApi.getProfile).toBe('function');
      expect(typeof responderApi.acceptMission).toBe('function');
      expect(typeof hospitalApi.getReadiness).toBe('function');
      expect(typeof hospitalApi.updateReadiness).toBe('function');
      expect(typeof superAdminApi.getSystemHealth).toBe('function');
      expect(typeof superAdminApi.getAuditLogs).toBe('function');
    });
  });
});
