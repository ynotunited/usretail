import React, { useState } from 'react';
import { X, Sparkles, AlertTriangle, UserCog } from 'lucide-react';

interface SiteDetailPanelProps {
  site: any;
  onClose: () => void;
}

const SiteDetailPanel: React.FC<SiteDetailPanelProps> = ({ site, onClose }) => {
  const [status, setStatus] = useState(site?.status || 'approved');
  const [justification, setJustification] = useState('');
  const [savedMessage, setSavedMessage] = useState('');

  React.useEffect(() => {
    setStatus(site?.status || 'approved');
    setJustification('');
    setSavedMessage('');
  }, [site]);

  const handleUpdate = () => {
    setSavedMessage(`Status updated to ${status.replace('_', ' ')}.`);
  };

  return (
    <div 
      className="site-detail-panel glass-panel"
      style={{
        width: site ? '400px' : '0',
        minWidth: site ? '350px' : '0',
        borderLeft: '1px solid var(--border-light)',
        borderTopRightRadius: 0,
        borderBottomRightRadius: 0,
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative'
      }}
    >
      {site && (
        <>
          {/* Header */}
            <div className="flex-between" style={{ padding: 'var(--space-md)', borderBottom: '1px solid var(--border-light)' }}>
              <div>
                <div style={{ fontSize: 'var(--font-sm)', color: 'var(--text-secondary)', fontWeight: 'bold', textTransform: 'uppercase' }}>
                  Rank #{site.rank}
                </div>
                <h2 style={{ fontSize: 'var(--font-2xl)', fontWeight: 'bold', color: 'var(--accent-blue)', marginTop: '-4px' }}>
                  {site.score.toFixed(1)}
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Close site details"
                style={{ padding: '4px', borderRadius: '50%', background: 'var(--bg-secondary)' }}
              >
                <X size={18} />
              </button>
            </div>

          {/* Body */}
          <div className="scrollable-y" style={{ flex: 1, padding: 'var(--space-md)' }}>
            
            {/* AI Insights Block */}
            <div style={{ background: 'linear-gradient(145deg, rgba(59, 130, 246, 0.1), rgba(6, 182, 212, 0.05))', padding: 'var(--space-md)', borderRadius: 'var(--radius-md)', border: '1px solid rgba(59, 130, 246, 0.2)', marginBottom: 'var(--space-lg)' }}>
              <div className="flex-center" style={{ justifyContent: 'flex-start', gap: '0.5rem', color: 'var(--accent-blue)', fontWeight: 'bold', marginBottom: 'var(--space-sm)' }}>
                <Sparkles size={16} /> AI Narrative Insight
              </div>
              <p style={{ fontSize: 'var(--font-sm)', color: 'rgba(255,255,255,0.9)' }}>
                This site exhibits exceptionally high competitor gap (Score: {site.gap}), indicating an underserved micro-market. Paired with strong population density ({site.pop}), it is highly recommended despite moderate transit access.
              </p>
            </div>

            {/* Score Breakdown Bars */}
            <h3 style={{ fontSize: 'var(--font-sm)', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 'var(--space-md)' }}>Factor Breakdown</h3>
            
            {[
              { label: 'Population Density', value: site.pop, weight: '30%' },
              { label: 'Income & Demographics', value: site.inc, weight: '20%' },
              { label: 'Competitor Gap', value: site.gap, weight: '25%' },
              { label: 'Transit Access', value: site.trans, weight: '15%' },
              { label: 'Road Visibility', value: site.road, weight: '10%' },
            ].map(factor => (
              <div key={factor.label} style={{ marginBottom: 'var(--space-md)' }}>
                <div className="flex-between" style={{ fontSize: 'var(--font-sm)', marginBottom: '4px' }}>
                  <span>{factor.label} <span style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>({factor.weight})</span></span>
                  <span style={{ fontWeight: 'bold' }}>{factor.value}</span>
                </div>
                <div style={{ width: '100%', height: '6px', background: 'var(--bg-secondary)', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${factor.value}%`, height: '100%', background: 'var(--accent-cyan)', borderRadius: '3px' }}></div>
                </div>
              </div>
            ))}

            {/* Warnings & Alerts */}
            {site.partial && (
              <div style={{ marginTop: 'var(--space-lg)', padding: 'var(--space-sm)', background: 'rgba(245, 158, 11, 0.1)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: 'var(--radius-md)', display: 'flex', gap: '0.5rem' }}>
                <AlertTriangle size={16} color="#FCD34D" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div style={{ fontSize: 'var(--font-sm)', color: '#FCD34D' }}>
                  <strong>Partial Data Warning:</strong> Demographic scores rely on county-level fallback due to census tract suppression.
                </div>
              </div>
            )}

            {site.conflict && (
              <div style={{ marginTop: 'var(--space-sm)', padding: 'var(--space-sm)', background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: 'var(--radius-md)', display: 'flex', gap: '0.5rem' }}>
                <AlertTriangle size={16} color="#FDA4AF" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div style={{ fontSize: 'var(--font-sm)', color: '#FDA4AF' }}>
                  <strong>Conflicting Source Alert:</strong> OSM and Commercial dataset (DataAxle) coordinates disagree on this location by &gt;50m.
                </div>
              </div>
            )}

            {/* Analyst Override & Status */}
            <div style={{ marginTop: 'var(--space-xl)' }}>
              <div className="flex-between" style={{ marginBottom: 'var(--space-sm)' }}>
                <h3 style={{ fontSize: 'var(--font-sm)', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Analyst Override</h3>
                {site.override && <span style={{ fontSize: '10px', background: 'var(--accent-blue)', padding: '2px 6px', borderRadius: '8px', color: 'white' }}>Active</span>}
              </div>
              <div style={{ marginBottom: 'var(--space-sm)' }}>
                <select 
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  aria-label="Analyst override status"
                  style={{ width: '100%', padding: 'var(--space-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', color: 'var(--text-primary)', outline: 'none' }}
                >
                  <option value="approved">✅ Approved</option>
                  <option value="under_review">⏳ Under review</option>
                  <option value="rejected">❌ Rejected</option>
                </select>
              </div>
              <textarea 
                placeholder="Enter justification to override this recommendation..."
                value={justification}
                onChange={(event) => setJustification(event.target.value)}
                aria-label="Override justification"
                style={{ width: '100%', minHeight: '80px', background: 'var(--bg-secondary)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: 'var(--space-sm)', color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 'var(--font-sm)', resize: 'vertical' }}
              ></textarea>
              <button
                className="btn-secondary"
                type="button"
                onClick={handleUpdate}
                aria-label="Save analyst override"
                style={{ width: '100%', marginTop: 'var(--space-sm)', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
              >
                <UserCog size={16} /> Update Status
              </button>
              {savedMessage && (
                <div style={{ marginTop: 'var(--space-sm)', fontSize: 'var(--font-sm)', color: 'var(--accent-emerald)' }}>
                  {savedMessage}
                </div>
              )}
            </div>

          </div>
        </>
      )}

      <style>{`
        @media (max-width: 768px) {
          .site-detail-panel {
            position: fixed !important;
            top: 0; right: 0; bottom: 0;
            width: 100% !important;
            max-width: 400px;
            z-index: 2000;
            transform: translateX(${site ? '0' : '100%'});
          }
        }
      `}</style>
    </div>
  );
};

export default SiteDetailPanel;
