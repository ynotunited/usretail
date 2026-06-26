import React, { Suspense, lazy, useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Map as MapIcon, List, Database, Settings, FileText, PlayCircle } from 'lucide-react';
import './layout.css';

const MapExplorer = lazy(() => import('./pages/MapExplorer'));
const SitesList = lazy(() => import('./pages/SitesList'));
const DataImports = lazy(() => import('./pages/DataImports'));
const AnalysisRuns = lazy(() => import('./pages/AnalysisRuns'));
const ExecutiveReport = lazy(() => import('./pages/ExecutiveReport'));

type ThemePreference = 'midnight-glass' | 'aurora-slate';
type AnalysisMode = 'production' | 'exploratory';
type DataRefresh = 'manual' | 'hourly';

type WorkspaceSettings = {
  analysisMode: AnalysisMode;
  theme: ThemePreference;
  dataRefresh: DataRefresh;
};

const SETTINGS_STORAGE_KEY = 'retailiq.workspace-settings';

const defaultSettings: WorkspaceSettings = {
  analysisMode: 'production',
  theme: 'midnight-glass',
  dataRefresh: 'manual',
};

const themeLabelMap: Record<ThemePreference, string> = {
  'midnight-glass': 'Midnight Glass',
  'aurora-slate': 'Aurora Slate',
};

const analysisLabelMap: Record<AnalysisMode, string> = {
  production: 'Production, Austin TX',
  exploratory: 'Exploratory sandbox',
};

const refreshLabelMap: Record<DataRefresh, string> = {
  manual: 'Manual',
  hourly: 'Hourly',
};

const loadSettings = (): WorkspaceSettings => {
  if (typeof window === 'undefined') {
    return defaultSettings;
  }

  try {
    const raw = window.localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return defaultSettings;
    const parsed = JSON.parse(raw) as Partial<WorkspaceSettings>;
    return {
      analysisMode: parsed.analysisMode === 'exploratory' ? 'exploratory' : 'production',
      theme: parsed.theme === 'aurora-slate' ? 'aurora-slate' : 'midnight-glass',
      dataRefresh: parsed.dataRefresh === 'hourly' ? 'hourly' : 'manual',
    };
  } catch {
    return defaultSettings;
  }
};

const AppContent: React.FC = () => {
  const location = useLocation();
  const [settings, setSettings] = useState<WorkspaceSettings>(() => loadSettings());
  const [draftSettings, setDraftSettings] = useState<WorkspaceSettings>(() => loadSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = settings.theme;
    window.localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
  }, [settings]);

  useEffect(() => {
    if (!settingsOpen) {
      return;
    }

    setDraftSettings(settings);
  }, [settings, settingsOpen]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setSettingsOpen(false);
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, []);

  const openSettings = () => {
    setDraftSettings(settings);
    setSettingsOpen(true);
  };

  const saveSettings = () => {
    setSettings(draftSettings);
    setSettingsOpen(false);
  };

  const navItems = [
    { path: '/', label: 'Map Explorer', icon: MapIcon },
    { path: '/sites', label: 'Candidate Sites', icon: List },
    { path: '/analysis', label: 'Analysis Runs', icon: PlayCircle },
    { path: '/report', label: 'Executive Report', icon: FileText },
    { path: '/data', label: 'Data Hub', icon: Database },
  ];

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <nav className="sidebar glass-panel">
        <div className="sidebar-header">
          <div className="logo-placeholder"></div>
          <h2>RetailIQ</h2>
        </div>
        
        <div className="nav-links">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`nav-item ${isActive ? 'active' : ''}`}
              >
                <Icon size={20} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>

        <div className="sidebar-footer">
          <button
            className="nav-item"
            type="button"
            onClick={openSettings}
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
          >
            <Settings size={20} />
            <span>Settings</span>
          </button>
          <div className="user-profile">
            <div className="avatar">A</div>
            <span>Analyst</span>
          </div>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="main-content">
        <Suspense fallback={<div className="page-loading">Loading workspace…</div>}>
          <Routes>
            <Route path="/" element={<MapExplorer />} />
            <Route path="/sites" element={<SitesList />} />
            <Route path="/analysis" element={<AnalysisRuns />} />
            <Route path="/report" element={<ExecutiveReport />} />
            <Route path="/data" element={<DataImports />} />
          </Routes>
        </Suspense>
      </main>

      {/* Mobile Bottom Navigation (Visible only on small screens via CSS) */}
      <nav className="bottom-nav glass-panel">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`bottom-nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={24} />
              <span className="font-xs">{item.label}</span>
            </Link>
          );
        })}
        <button
          className="bottom-nav-item bottom-nav-action"
          type="button"
          onClick={openSettings}
          aria-haspopup="dialog"
          aria-expanded={settingsOpen}
        >
          <Settings size={24} />
          <span className="font-xs">Settings</span>
        </button>
      </nav>

      {settingsOpen && (
        <div
          className="settings-backdrop"
          role="presentation"
          onClick={() => setSettingsOpen(false)}
        >
          <aside
            className="settings-panel glass-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Settings"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="settings-header">
              <div>
                <div className="settings-kicker">Workspace</div>
                <h2>Settings</h2>
              </div>
              <button
                type="button"
                className="settings-close"
                onClick={() => setSettingsOpen(false)}
                aria-label="Close settings"
              >
                ×
              </button>
            </div>

            <label className="settings-section settings-field">
              <span className="settings-label">Analysis mode</span>
              <select
                className="settings-control"
                value={draftSettings.analysisMode}
                onChange={(event) =>
                  setDraftSettings((current) => ({
                    ...current,
                    analysisMode: event.target.value as AnalysisMode,
                  }))
                }
              >
                <option value="production">{analysisLabelMap.production}</option>
                <option value="exploratory">{analysisLabelMap.exploratory}</option>
              </select>
            </label>

            <label className="settings-section settings-field">
              <span className="settings-label">Theme</span>
              <select
                className="settings-control"
                value={draftSettings.theme}
                onChange={(event) =>
                  setDraftSettings((current) => ({
                    ...current,
                    theme: event.target.value as ThemePreference,
                  }))
                }
              >
                <option value="midnight-glass">{themeLabelMap['midnight-glass']}</option>
                <option value="aurora-slate">{themeLabelMap['aurora-slate']}</option>
              </select>
            </label>

            <label className="settings-section settings-field">
              <span className="settings-label">Data refresh</span>
              <select
                className="settings-control"
                value={draftSettings.dataRefresh}
                onChange={(event) =>
                  setDraftSettings((current) => ({
                    ...current,
                    dataRefresh: event.target.value as DataRefresh,
                  }))
                }
              >
                <option value="manual">{refreshLabelMap.manual}</option>
                <option value="hourly">{refreshLabelMap.hourly}</option>
              </select>
            </label>

            <div className="settings-actions">
              <button type="button" className="btn-secondary" onClick={() => setSettingsOpen(false)}>
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={saveSettings}>
                Save
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
};

const App: React.FC = () => {
  return (
    <Router>
      <AppContent />
    </Router>
  );
};

export default App;
