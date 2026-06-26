import React, { useState } from 'react';
import { AlertTriangle, MapPin, ChevronRight, BarChart2 } from 'lucide-react';
import SiteDetailPanel from '../components/SiteDetailPanel';

const MOCK_SITES = [
  { id: '1', rank: 1, score: 87.5, lat: 30.2672, lon: -97.7431, partial: false, override: false, pop: 85, inc: 90, trans: 75, road: 80, gap: 95, conflict: false, status: 'approved' },
  { id: '2', rank: 2, score: 82.1, lat: 30.2800, lon: -97.7400, partial: true, override: false, pop: 70, inc: 85, trans: 80, road: 85, gap: 88, conflict: true, status: 'under_review' },
  { id: '3', rank: 3, score: 79.4, lat: 30.2500, lon: -97.7500, partial: false, override: true, pop: 90, inc: 70, trans: 65, road: 70, gap: 92, conflict: false, status: 'rejected' },
];

const SitesList: React.FC = () => {
  const [selectedSite, setSelectedSite] = useState<any | null>(null);

  return (
    <div className="sites-container" style={{ display: 'flex', height: '100%', width: '100%' }}>
      
      {/* Main List Area */}
      <div style={{ flex: 1, padding: 'var(--space-lg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div className="flex-between" style={{ marginBottom: 'var(--space-lg)' }}>
          <h1>Candidate Sites</h1>
          <button className="btn-secondary" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <BarChart2 size={16} /> Export CSV
          </button>
        </div>

        <div className="glass-panel scrollable-y" style={{ flex: 1, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-panel)', backdropFilter: 'blur(10px)', borderBottom: '1px solid var(--border-light)' }}>
              <tr>
                <th style={{ padding: 'var(--space-md)' }}>Rank</th>
                <th style={{ padding: 'var(--space-md)' }}>Score</th>
                <th style={{ padding: 'var(--space-md)' }}>Location</th>
                <th style={{ padding: 'var(--space-md)' }}>Pop</th>
                <th style={{ padding: 'var(--space-md)' }}>Inc</th>
                <th style={{ padding: 'var(--space-md)' }}>Gap</th>
                <th style={{ padding: 'var(--space-md)' }}>Status</th>
                <th style={{ padding: 'var(--space-md)' }}></th>
              </tr>
            </thead>
            <tbody>
              {MOCK_SITES.map((site) => (
                <tr 
                  key={site.id} 
                  style={{ 
                    borderBottom: '1px solid var(--border-light)', 
                    cursor: 'pointer',
                    background: selectedSite?.id === site.id ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                    transition: 'background 0.2s'
                  }}
                  onClick={() => setSelectedSite(site)}
                  className="table-row-hover"
                >
                  <td style={{ padding: 'var(--space-md)' }}>
                    <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: 'var(--bg-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                      {site.rank}
                    </div>
                  </td>
                  <td style={{ padding: 'var(--space-md)', fontWeight: 'var(--weight-bold)', color: 'var(--accent-blue)' }}>
                    {site.score.toFixed(1)}
                  </td>
                  <td style={{ padding: 'var(--space-md)' }}>
                    <div className="flex-center" style={{ gap: '0.25rem', justifyContent: 'flex-start', fontSize: 'var(--font-sm)', color: 'var(--text-secondary)' }}>
                      <MapPin size={14} /> {site.lat.toFixed(4)}, {site.lon.toFixed(4)}
                    </div>
                  </td>
                  <td style={{ padding: 'var(--space-md)' }}>{site.pop}</td>
                  <td style={{ padding: 'var(--space-md)' }}>{site.inc}</td>
                  <td style={{ padding: 'var(--space-md)' }}>{site.gap}</td>
                  <td style={{ padding: 'var(--space-md)' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                      {site.partial && <span className="badge warning" title="Partial Data Used"><AlertTriangle size={12}/> Partial</span>}
                      {site.conflict && <span className="badge error" style={{ background: 'rgba(244,63,94,0.2)', color: '#FDA4AF' }} title="Conflicting Source"><AlertTriangle size={12}/> Conflict</span>}
                      {site.status === 'under_review' && <span className="badge warning">Under Review</span>}
                      {site.status === 'rejected' && <span className="badge error" style={{ background: 'rgba(244,63,94,0.2)', color: '#FDA4AF' }}>Rejected</span>}
                    </div>
                  </td>
                  <td style={{ padding: 'var(--space-md)', color: 'var(--text-secondary)' }}>
                    <ChevronRight size={16} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Slide-in Detail Panel */}
      <SiteDetailPanel site={selectedSite} onClose={() => setSelectedSite(null)} />

      <style>{`
        .table-row-hover:hover {
          background: rgba(255,255,255,0.03) !important;
        }
        .badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 2px 8px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
        }
        .badge.warning { background: rgba(245, 158, 11, 0.2); color: #FCD34D; }
        .badge.info { background: rgba(59, 130, 246, 0.2); color: #93C5FD; }
      `}</style>
    </div>
  );
};

export default SitesList;
