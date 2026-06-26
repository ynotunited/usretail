import React, { useState, useRef } from 'react';
import {
  Upload, AlertTriangle, CheckCircle, Info, GitBranch,
  ChevronDown, ChevronRight, Trash2, GitMerge, Tag, Clock,
  Shield, Database
} from 'lucide-react';

// ── Mock data (reflects real API shape) ──────────────────────────────────────

const MOCK_VALIDATION = {
  summary: { errors: 2, warnings: 3, infos: 1 },
  issues: [
    { id: '1', row_index: 12, severity: 'error', rule_name: 'out_of_bounds', message: 'Geometry bounding box falls outside US extent (lon -65 to -180, lat 17 to 72).', raw_value: '(-75.12, 40.01, -75.11, 40.02)', created_at: '2024-11-01T10:00:00Z' },
    { id: '2', row_index: 47, severity: 'error', rule_name: 'invalid_topology', message: 'Geometry topology invalid: Self-intersection at or near point (−97.7, 30.2).', raw_value: 'Self-intersection', created_at: '2024-11-01T10:00:00Z' },
    { id: '3', row_index: 5, severity: 'warning', rule_name: 'missing_required_attribute', message: "Required attribute 'population' is missing or null.", raw_value: 'population', created_at: '2024-11-01T10:00:00Z' },
    { id: '4', row_index: null, severity: 'warning', rule_name: 'duplicate_geometries', message: '2 near-duplicate geometries detected by spatial fingerprint (centroid ±1m + area). Row indices: [22, 91].', raw_value: '22,91', created_at: '2024-11-01T10:00:00Z' },
    { id: '5', row_index: null, severity: 'info', rule_name: 'srs_reprojection', message: 'Input SRS EPSG:4269 detected. Features reprojected to EPSG:4326.', raw_value: 'EPSG:4269', created_at: '2024-11-01T10:00:00Z' },
    { id: '6', row_index: 91, severity: 'warning', rule_name: 'missing_required_attribute', message: "Required attribute 'tract_id' is missing or null.", raw_value: 'tract_id', created_at: '2024-11-01T10:00:00Z' },
  ],
};

const MOCK_LINEAGE = {
  dataset: { id: 'ds-001', source_id: 'census_acs_2022', name: 'ACS 2022 Demographics', vintage_year: 2022, ingested_at: '2024-10-15T09:00:00Z', confidence: 'high' },
  layers: [
    { id: 'l-001', name: 'Population Density', import_status: 'imported', confidence: 'high', ingested_at: '2024-10-15T09:01:00Z', feature_count: 847, validation_errors: 0, validation_warnings: 1 },
    { id: 'l-002', name: 'Income Distribution', import_status: 'imported', confidence: 'medium', ingested_at: '2024-10-15T09:03:00Z', feature_count: 843, validation_errors: 2, validation_warnings: 3 },
  ],
  versions: [
    { id: 'v-001', version_tag: 'v1', created_by: 'jsmith', locked_at: '2024-10-20T14:00:00Z', notes: 'Initial locked version for Q4 analysis.' },
  ],
};

const AUTO_FIX_SUGGESTIONS: Record<string, string> = {
  out_of_bounds: 'Check source data projection. If the data was exported from a non-WGS84 SRS, re-export with EPSG:4326.',
  invalid_topology: 'Use ST_MakeValid() in PostGIS or shapely.make_valid() to auto-repair this geometry.',
  missing_required_attribute: 'Provide a default value or filter this feature out before import.',
  duplicate_geometries: 'Review the "Duplicates" tab to merge or discard these features.',
  srs_reprojection: 'No action required — reprojection was applied automatically.',
};

// ── Sub-components ────────────────────────────────────────────────────────────

const SeverityIcon: React.FC<{ severity: string }> = ({ severity }) => {
  if (severity === 'error') return <AlertTriangle size={14} color="var(--accent-rose)" />;
  if (severity === 'warning') return <AlertTriangle size={14} color="#FCD34D" />;
  return <Info size={14} color="var(--accent-cyan)" />;
};

const SeverityBadge: React.FC<{ severity: string }> = ({ severity }) => {
  const colors: Record<string, string> = {
    error: 'rgba(244,63,94,0.15)',
    warning: 'rgba(245,158,11,0.15)',
    info: 'rgba(6,182,212,0.15)',
  };
  const textColors: Record<string, string> = {
    error: '#FDA4AF',
    warning: '#FCD34D',
    info: '#67E8F9',
  };
  return (
    <span style={{ background: colors[severity], color: textColors[severity], padding: '2px 8px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, textTransform: 'uppercase' }}>
      {severity}
    </span>
  );
};

// ── Tabs ──────────────────────────────────────────────────────────────────────

const TABS = ['Upload', 'Validation Results', 'Duplicates', 'Data Lineage'];

// ── Main Component ────────────────────────────────────────────────────────────

const DataImports: React.FC = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [uploaded, setUploaded] = useState<string | null>(null);
  const [expandedIssue, setExpandedIssue] = useState<string | null>(null);
  const [expandedLayer, setExpandedLayer] = useState<string | null>(null);
  const [dupResolved, setDupResolved] = useState<Record<string, string>>({});
  const fileRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setUploaded(file.name);
      setActiveTab(1);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploaded(file.name);
      setActiveTab(1);
    }
  };

  const dupRows = MOCK_VALIDATION.issues.filter(i => i.rule_name === 'duplicate_geometries');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', width: '100%', padding: 'var(--space-lg)', overflow: 'hidden' }}>
      
      {/* Header */}
      <div className="flex-between stagger-1" style={{ marginBottom: 'var(--space-lg)' }}>
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Database size={24} color="var(--accent-blue)" /> Data Hub
        </h1>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {uploaded && (
            <div style={{ background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.3)', padding: '6px 12px', borderRadius: 'var(--radius-md)', fontSize: 'var(--font-sm)', color: '#6EE7B7', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <CheckCircle size={14} /> {uploaded}
            </div>
          )}
        </div>
      </div>

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: 'var(--space-lg)', borderBottom: '1px solid var(--border-light)', paddingBottom: '0' }}>
        {TABS.map((tab, i) => {
          const isActive = activeTab === i;
          const hasBadge = i === 1 && MOCK_VALIDATION.summary.errors > 0;
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(i)}
              style={{
                padding: '8px 16px',
                background: 'none',
                borderBottom: isActive ? '2px solid var(--accent-blue)' : '2px solid transparent',
                color: isActive ? 'var(--accent-blue)' : 'var(--text-secondary)',
                fontWeight: isActive ? 600 : 400,
                fontSize: 'var(--font-sm)',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {tab}
              {hasBadge && (
                <span style={{ background: 'var(--accent-rose)', color: 'white', borderRadius: '10px', padding: '1px 6px', fontSize: '10px' }}>
                  {MOCK_VALIDATION.summary.errors}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <div className="scrollable-y" style={{ flex: 1 }}>

        {/* ── Tab 0: Upload ──────────────────────────────────────────────── */}
        {activeTab === 0 && (
          <div style={{ maxWidth: '640px', margin: '0 auto' }}>
            <div
              className="glass-panel"
              onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              style={{
                padding: 'var(--space-xl)',
                textAlign: 'center',
                cursor: 'pointer',
                border: `2px dashed ${isDragging ? 'var(--accent-blue)' : 'var(--border-light)'}`,
                background: isDragging ? 'rgba(59,130,246,0.07)' : undefined,
                transition: 'all 0.2s',
                borderRadius: 'var(--radius-lg)',
              }}
            >
              <Upload size={40} color="var(--accent-blue)" style={{ marginBottom: 'var(--space-md)' }} />
              <h3 style={{ marginBottom: '8px' }}>Drop GeoJSON or Shapefile ZIP here</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-sm)' }}>Or click to browse — GeoJSON, .shp (zipped), CSV with lat/lon</p>
              <input ref={fileRef} type="file" style={{ display: 'none' }} accept=".geojson,.json,.zip,.csv" onChange={handleFileChange} />
            </div>

            <div style={{ marginTop: 'var(--space-lg)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-md)' }}>
              {[
                { label: 'Coordinate Validation', desc: 'Rejects non-US coordinates', icon: Shield },
                { label: 'SRS Auto-Reprojection', desc: 'Auto-converts to EPSG:4326', icon: GitBranch },
                { label: 'Topology Check', desc: 'Detects self-intersections', icon: CheckCircle },
                { label: 'Duplicate Detection', desc: 'Spatial fingerprint ±1m', icon: GitMerge },
              ].map(f => {
                const Icon = f.icon;
                return (
                  <div key={f.label} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: 'var(--space-md)', display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                    <Icon size={18} color="var(--accent-emerald)" style={{ flexShrink: 0, marginTop: '2px' }} />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 'var(--font-sm)' }}>{f.label}</div>
                      <div style={{ color: 'var(--text-secondary)', fontSize: 'var(--font-xs)' }}>{f.desc}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Tab 1: Validation Results ──────────────────────────────────── */}
        {activeTab === 1 && (
          <div>
            {/* Summary */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
              {[
                { label: 'Errors', value: MOCK_VALIDATION.summary.errors, color: 'var(--accent-rose)' },
                { label: 'Warnings', value: MOCK_VALIDATION.summary.warnings, color: '#FCD34D' },
                { label: 'Info', value: MOCK_VALIDATION.summary.infos, color: 'var(--accent-cyan)' },
              ].map(s => (
                <div key={s.label} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: 'var(--space-md)', textAlign: 'center' }}>
                  <div style={{ fontSize: 'var(--font-2xl)', fontWeight: 700, color: s.color }}>{s.value}</div>
                  <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>{s.label}</div>
                </div>
              ))}
            </div>

            {/* Issue rows */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
              {MOCK_VALIDATION.issues.map(issue => {
                const isExpanded = expandedIssue === issue.id;
                const suggestion = AUTO_FIX_SUGGESTIONS[issue.rule_name];
                return (
                  <div
                    key={issue.id}
                    style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', overflow: 'hidden' }}
                  >
                    <div
                      className="flex-between"
                      style={{ padding: 'var(--space-md)', cursor: 'pointer' }}
                      onClick={() => setExpandedIssue(isExpanded ? null : issue.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, minWidth: 0 }}>
                        <SeverityIcon severity={issue.severity} />
                        <div style={{ minWidth: 0 }}>
                          <div className="flex-center" style={{ justifyContent: 'flex-start', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <SeverityBadge severity={issue.severity} />
                            <code style={{ fontSize: '11px', color: 'var(--text-secondary)', background: 'rgba(255,255,255,0.05)', padding: '1px 6px', borderRadius: '4px' }}>{issue.rule_name}</code>
                            {issue.row_index !== null && (
                              <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>Row {issue.row_index}</span>
                            )}
                          </div>
                          <p className="text-truncate" style={{ fontSize: 'var(--font-sm)', marginTop: '4px', color: 'rgba(255,255,255,0.85)' }}>{issue.message}</p>
                        </div>
                      </div>
                      {isExpanded ? <ChevronDown size={16} color="var(--text-secondary)" /> : <ChevronRight size={16} color="var(--text-secondary)" />}
                    </div>
                    {isExpanded && (
                      <div style={{ borderTop: '1px solid var(--border-light)', padding: 'var(--space-md)', background: 'rgba(0,0,0,0.2)' }}>
                        {issue.raw_value && (
                          <div style={{ marginBottom: 'var(--space-sm)' }}>
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Raw Value:</span>
                            <code style={{ display: 'block', fontSize: 'var(--font-xs)', color: '#67E8F9', marginTop: '4px' }}>{issue.raw_value}</code>
                          </div>
                        )}
                        {suggestion && (
                          <div style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', borderRadius: 'var(--radius-sm)', padding: '8px 12px' }}>
                            <div style={{ fontSize: '11px', color: '#6EE7B7', fontWeight: 600, marginBottom: '4px' }}>💡 Auto-Fix Suggestion</div>
                            <p style={{ fontSize: 'var(--font-xs)', color: 'rgba(255,255,255,0.8)' }}>{suggestion}</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Tab 2: Duplicates ──────────────────────────────────────────── */}
        {activeTab === 2 && (
          <div>
            {dupRows.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 'var(--space-xl)', color: 'var(--text-secondary)' }}>
                <CheckCircle size={40} color="var(--accent-emerald)" style={{ marginBottom: 'var(--space-md)' }} />
                <p>No duplicate geometries detected.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                {dupRows.map(dup => {
                  const rawIds = (dup.raw_value || '').split(',').map(s => s.trim()).filter(Boolean);
                  const resolved = dupResolved[dup.id];
                  return (
                    <div key={dup.id} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: 'var(--space-md)' }}>
                      <div className="flex-between" style={{ marginBottom: 'var(--space-sm)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <AlertTriangle size={16} color="#FCD34D" />
                          <span style={{ fontWeight: 600 }}>Duplicate pair detected</span>
                        </div>
                        {resolved && (
                          <span style={{ fontSize: '11px', background: 'rgba(16,185,129,0.2)', color: '#6EE7B7', padding: '2px 8px', borderRadius: '10px' }}>
                            Resolved: {resolved}
                          </span>
                        )}
                      </div>
                      <p style={{ fontSize: 'var(--font-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--space-md)' }}>{dup.message}</p>
                      <div style={{ display: 'flex', gap: 'var(--space-sm)', flexWrap: 'wrap', marginBottom: 'var(--space-md)' }}>
                        {rawIds.map(rowIdx => (
                          <span key={rowIdx} style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-light)', padding: '4px 10px', borderRadius: 'var(--radius-sm)', fontSize: 'var(--font-xs)' }}>
                            Row {rowIdx}
                          </span>
                        ))}
                      </div>
                      {!resolved && (
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button
                            className="btn-secondary"
                            onClick={() => setDupResolved(p => ({ ...p, [dup.id]: 'Merged' }))}
                            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: 'var(--font-sm)' }}
                          >
                            <GitMerge size={14} /> Merge
                          </button>
                          <button
                            className="btn-secondary"
                            onClick={() => setDupResolved(p => ({ ...p, [dup.id]: 'Discarded' }))}
                            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: 'var(--font-sm)', color: 'var(--accent-rose)', borderColor: 'rgba(244,63,94,0.3)' }}
                          >
                            <Trash2 size={14} /> Discard
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── Tab 3: Data Lineage ────────────────────────────────────────── */}
        {activeTab === 3 && (
          <div>
            <div style={{ marginBottom: 'var(--space-lg)' }}>
              <div className="flex-between" style={{ marginBottom: 'var(--space-md)' }}>
                <div>
                  <h2 style={{ fontSize: 'var(--font-xl)' }}>{MOCK_LINEAGE.dataset.name}</h2>
                  <div style={{ display: 'flex', gap: '1rem', marginTop: '4px', fontSize: 'var(--font-xs)', color: 'var(--text-secondary)' }}>
                    <span>Source: <strong style={{ color: 'var(--text-primary)' }}>{MOCK_LINEAGE.dataset.source_id}</strong></span>
                    <span>Vintage: <strong style={{ color: 'var(--text-primary)' }}>{MOCK_LINEAGE.dataset.vintage_year}</strong></span>
                    <span>Confidence: <strong style={{ color: 'var(--accent-emerald)' }}>{MOCK_LINEAGE.dataset.confidence}</strong></span>
                  </div>
                </div>
                <button className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: 'var(--font-sm)' }}>
                  <Tag size={14} /> Lock Version
                </button>
              </div>

              {/* Versions */}
              <div style={{ marginBottom: 'var(--space-lg)' }}>
                <h3 style={{ fontSize: 'var(--font-sm)', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>Locked Versions</h3>
                {MOCK_LINEAGE.versions.map(v => (
                  <div key={v.id} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', padding: 'var(--space-md)', display: 'flex', gap: '1rem', alignItems: 'center' }}>
                    <Tag size={16} color="var(--accent-blue)" />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600 }}>{v.version_tag}</div>
                      <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-secondary)' }}>{v.notes}</div>
                    </div>
                    <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} /> {new Date(v.locked_at).toLocaleDateString()} by {v.created_by}
                    </div>
                  </div>
                ))}
              </div>

              {/* Layers */}
              <h3 style={{ fontSize: 'var(--font-sm)', textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 'var(--space-sm)' }}>Layer Provenance</h3>
              {MOCK_LINEAGE.layers.map(layer => {
                const isExpanded = expandedLayer === layer.id;
                return (
                  <div key={layer.id} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', overflow: 'hidden', marginBottom: 'var(--space-sm)' }}>
                    <div
                      className="flex-between"
                      style={{ padding: 'var(--space-md)', cursor: 'pointer' }}
                      onClick={() => setExpandedLayer(isExpanded ? null : layer.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        <div>
                          <div style={{ fontWeight: 600 }}>{layer.name}</div>
                          <div style={{ fontSize: 'var(--font-xs)', color: 'var(--text-secondary)' }}>
                            {layer.feature_count?.toLocaleString()} features • {new Date(layer.ingested_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        {layer.validation_errors > 0 && <span className="badge" style={{ background: 'rgba(244,63,94,0.15)', color: '#FDA4AF' }}>{layer.validation_errors} errors</span>}
                        {layer.validation_warnings > 0 && <span className="badge" style={{ background: 'rgba(245,158,11,0.15)', color: '#FCD34D' }}>{layer.validation_warnings} warnings</span>}
                        <span style={{ fontSize: '11px', color: layer.confidence === 'high' ? 'var(--accent-emerald)' : '#FCD34D', fontWeight: 600, textTransform: 'uppercase' }}>{layer.confidence}</span>
                      </div>
                    </div>
                    {isExpanded && (
                      <div style={{ borderTop: '1px solid var(--border-light)', padding: 'var(--space-md)', background: 'rgba(0,0,0,0.15)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                        <div><div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Layer ID</div><code style={{ fontSize: 'var(--font-xs)', color: 'var(--accent-cyan)' }}>{layer.id}</code></div>
                        <div><div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Import Status</div><span style={{ fontSize: 'var(--font-sm)', color: 'var(--accent-emerald)' }}>{layer.import_status}</span></div>
                        <div><div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Ingested At</div><span style={{ fontSize: 'var(--font-sm)' }}>{new Date(layer.ingested_at).toLocaleString()}</span></div>
                        <div><div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Features</div><span style={{ fontSize: 'var(--font-sm)' }}>{layer.feature_count?.toLocaleString()}</span></div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

export default DataImports;
