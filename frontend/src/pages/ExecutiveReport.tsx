import React from 'react';
import { Download, Printer } from 'lucide-react';

const ExecutiveReport: React.FC = () => {
  return (
    <div style={{ display: 'flex', height: '100%', width: '100%', flexDirection: 'column', alignItems: 'center' }}>
      
      <div className="flex-between stagger-1" style={{ width: '100%', maxWidth: '900px', padding: 'var(--space-lg)', paddingBottom: 0 }}>
        <h1>Executive Report</h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn-secondary" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <Download size={16} /> Export CSV
          </button>
          <button className="btn-primary" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <Printer size={16} /> Export PDF
          </button>
        </div>
      </div>

      <div className="scrollable-y" style={{ width: '100%', flex: 1, padding: 'var(--space-lg)', display: 'flex', justifyContent: 'center' }}>
        <div className="glass-panel stagger-2" style={{ width: '100%', maxWidth: '900px', padding: 'var(--space-xl)', background: 'var(--bg-secondary)' }}>
          
          <div style={{ borderBottom: '2px solid var(--border-light)', paddingBottom: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
            <h2 style={{ fontSize: 'var(--font-2xl)', color: 'var(--accent-blue)', marginBottom: 'var(--space-sm)' }}>Retail Site Selection Strategy</h2>
            <div className="flex-between" style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-sm)' }}>
              <span>Analysis Run: RUN-001</span>
              <span>Date: Nov 1, 2024</span>
            </div>
          </div>

          <h3 style={{ marginBottom: 'var(--space-sm)' }}>Methodology</h3>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 'var(--space-xl)', fontSize: 'var(--font-sm)' }}>
            The composite suitability scores are calculated using a weighted overlay model. The current active model assigns 30% weight to population density, 25% to competitor gap, 20% to income demographics, 15% to transit access, and 10% to road visibility.
          </p>

          <h3 style={{ marginBottom: 'var(--space-sm)' }}>Executive Summary</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-md)', marginBottom: 'var(--space-xl)' }}>
            <div style={{ padding: 'var(--space-md)', background: 'rgba(255,255,255,0.05)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Top Candidate</div>
              <div style={{ fontSize: 'var(--font-xl)', fontWeight: 'bold', color: 'var(--accent-cyan)' }}>Site #12 (Score: 87.5)</div>
            </div>
            <div style={{ padding: 'var(--space-md)', background: 'rgba(255,255,255,0.05)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Total Evaluated</div>
              <div style={{ fontSize: 'var(--font-xl)', fontWeight: 'bold' }}>420 Sites</div>
            </div>
            <div style={{ padding: 'var(--space-md)', background: 'rgba(255,255,255,0.05)', borderRadius: 'var(--radius-md)' }}>
              <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Analyst Overrides</div>
              <div style={{ fontSize: 'var(--font-xl)', fontWeight: 'bold', color: 'var(--accent-rose)' }}>3 Applied</div>
            </div>
          </div>

          <h3 style={{ marginBottom: 'var(--space-sm)' }}>Limitations & Warnings</h3>
          <div className="banner warning stagger-3" style={{ marginBottom: 'var(--space-md)' }}>
            <AlertTriangle size={18} />
            <span>Partial Data Used: Some demographic data relies on county-level fallback due to census tract suppression. Confidence scores for Site #15 and #22 are reduced.</span>
          </div>

        </div>
      </div>
    </div>
  );
};

// Add lucide import for AlertTriangle here
import { AlertTriangle } from 'lucide-react';

export default ExecutiveReport;
