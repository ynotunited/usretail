import React, { useState } from 'react';
import { Play, Activity, Clock, Users, Layers } from 'lucide-react';

const MOCK_RUNS = [
  { id: 'run-001', date: '2024-11-01T10:30:00Z', status: 'complete', analyst: 'jsmith', pop: 30, inc: 20, gap: 25, trans: 15, road: 10 },
  { id: 'run-002', date: '2024-11-01T14:15:00Z', status: 'partial', analyst: 'jsmith', pop: 30, inc: 20, gap: 25, trans: 15, road: 10 },
  { id: 'run-003', date: '2024-11-02T09:00:00Z', status: 'failed', analyst: 'mchen', pop: 40, inc: 10, gap: 30, trans: 10, road: 10 },
];

const AnalysisRuns: React.FC = () => {
  const [loading, setLoading] = useState(false);

  // Simulate starting an async task
  const handleReRun = () => {
    setLoading(true);
    setTimeout(() => setLoading(false), 2000);
  };

  return (
    <div style={{ display: 'flex', height: '100%', width: '100%' }}>
      <div style={{ flex: 1, padding: 'var(--space-lg)', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        
        <div className="flex-between stagger-1" style={{ marginBottom: 'var(--space-lg)' }}>
          <h1>Analysis Runs</h1>
          <button className="btn-primary" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <Activity size={16} /> New Analysis
          </button>
        </div>

        <div className="glass-panel scrollable-y stagger-2" style={{ flex: 1 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead style={{ position: 'sticky', top: 0, background: 'var(--bg-panel)', backdropFilter: 'blur(10px)', borderBottom: '1px solid var(--border-light)' }}>
              <tr>
                <th style={{ padding: 'var(--space-md)' }}>Run ID</th>
                <th style={{ padding: 'var(--space-md)' }}>Date</th>
                <th style={{ padding: 'var(--space-md)' }}>Analyst</th>
                <th style={{ padding: 'var(--space-md)' }}>Weights (Pop/Inc/Gap)</th>
                <th style={{ padding: 'var(--space-md)' }}>Status</th>
                <th style={{ padding: 'var(--space-md)' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_RUNS.map((run) => (
                <tr key={run.id} style={{ borderBottom: '1px solid var(--border-light)' }}>
                  <td style={{ padding: 'var(--space-md)', fontWeight: 'bold' }}>{run.id}</td>
                  <td style={{ padding: 'var(--space-md)' }}>
                    <div className="flex-center" style={{ justifyContent: 'flex-start', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                      <Clock size={14} /> {new Date(run.date).toLocaleString()}
                    </div>
                  </td>
                  <td style={{ padding: 'var(--space-md)' }}>
                    <div className="flex-center" style={{ justifyContent: 'flex-start', gap: '0.5rem', color: 'var(--text-secondary)' }}>
                      <Users size={14} /> {run.analyst}
                    </div>
                  </td>
                  <td style={{ padding: 'var(--space-md)', color: 'var(--text-secondary)' }}>
                    {run.pop}% / {run.inc}% / {run.gap}%
                  </td>
                  <td style={{ padding: 'var(--space-md)' }}>
                    {run.status === 'complete' && <span className="badge info">Complete</span>}
                    {run.status === 'partial' && <span className="badge warning">Partial</span>}
                    {run.status === 'failed' && <span className="badge error" style={{ background: 'rgba(244,63,94,0.2)', color: '#FDA4AF' }}>Failed</span>}
                  </td>
                  <td style={{ padding: 'var(--space-md)' }}>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <button className="btn-secondary" onClick={handleReRun} title="Re-run with same inputs" style={{ padding: '4px 8px' }}>
                        <Play size={14} />
                      </button>
                      <button className="btn-secondary" title="Compare against..." style={{ padding: '4px 8px' }}>
                        <Layers size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>

      {loading && (
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="glass-panel" style={{ padding: 'var(--space-xl)', textAlign: 'center' }}>
            <div className="skeleton" style={{ width: '60px', height: '60px', borderRadius: '50%', margin: '0 auto var(--space-md)' }}></div>
            <h3>Running Analysis</h3>
            <p style={{ color: 'var(--text-secondary)' }}>Scoring sites across all layers...</p>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnalysisRuns;
