import React, { useEffect, useState } from 'react';
import { Layers, Activity, AlertTriangle } from 'lucide-react';

const INITIAL_VIEW_STATE = {
  longitude: -97.7431, // Default: Austin, TX
  latitude: 30.2672,
  zoom: 11,
  pitch: 45,
  bearing: -17.6
};

// OpenStreetMap style since we don't have Mapbox API keys
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const MapExplorer: React.FC = () => {
  const [showLayerPanel, setShowLayerPanel] = useState(true);
  const [MapComponents, setMapComponents] = useState<{
    Map: React.ComponentType<any>;
    NavigationControl: React.ComponentType<any>;
    ScaleControl: React.ComponentType<any>;
    maplibregl: any;
  } | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      import('react-map-gl/maplibre'),
      import('maplibre-gl'),
      import('maplibre-gl/dist/maplibre-gl.css'),
    ]).then(([mapModule, maplibreModule]) => {
      if (!active) return;
      setMapComponents({
        Map: mapModule.default,
        NavigationControl: mapModule.NavigationControl,
        ScaleControl: mapModule.ScaleControl,
        maplibregl: maplibreModule.default,
      });
    });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="map-explorer-container" style={{ display: 'flex', height: '100%', width: '100%', position: 'relative' }}>
      
      {/* Sidebar for Map Analysis Controls */}
      <div 
        className={`map-sidebar glass-panel ${showLayerPanel ? 'visible' : 'hidden'}`}
        style={{
          width: showLayerPanel ? '35%' : '0',
          minWidth: showLayerPanel ? '300px' : '0',
          margin: '0',
          borderTopRightRadius: 0,
          borderBottomRightRadius: 0,
          transition: 'all 0.3s ease',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 10
        }}
      >
        <div style={{ padding: 'var(--space-md)', borderBottom: '1px solid var(--border-light)' }}>
          <h2 style={{ fontSize: 'var(--font-xl)', fontWeight: 'var(--weight-semibold)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Layers size={20} className="text-accent-blue" />
            Analysis Layers
          </h2>
        </div>

        <div className="scrollable-y" style={{ flex: 1, padding: 'var(--space-md)' }}>
          <div className="layer-item">
            <div className="flex-between">
              <span style={{ fontWeight: 'var(--weight-medium)' }}>Competitor Density</span>
              <div className="toggle-switch active"></div>
            </div>
            <div style={{ marginTop: 'var(--space-sm)', fontSize: 'var(--font-xs)', color: 'var(--text-secondary)' }}>
              Source: OSM • Vintage: 2024
            </div>
          </div>

          <div className="layer-item" style={{ marginTop: 'var(--space-md)' }}>
            <div className="flex-between">
              <span style={{ fontWeight: 'var(--weight-medium)' }}>Population Density</span>
              <div className="toggle-switch active"></div>
            </div>
            <div style={{ marginTop: 'var(--space-sm)', fontSize: 'var(--font-xs)', color: 'var(--text-secondary)' }}>
              Source: Census ACS • Vintage: 2022
            </div>
            <div style={{ marginTop: 'var(--space-xs)', fontSize: 'var(--font-xs)', color: 'var(--accent-rose)', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <AlertTriangle size={12} /> Some tracts suppressed
            </div>
          </div>
        </div>

        <div style={{ padding: 'var(--space-md)', borderTop: '1px solid var(--border-light)' }}>
          <button className="btn-primary" style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
            <Activity size={18} />
            Run Analysis
          </button>
        </div>
      </div>

      {/* Main Map Area */}
      <div className="map-area" style={{ flex: 1, position: 'relative' }}>
        {MapComponents ? (
          <MapComponents.Map
            mapLib={MapComponents.maplibregl}
            initialViewState={INITIAL_VIEW_STATE}
            mapStyle={MAP_STYLE}
            style={{ width: '100%', height: '100%' }}
          >
            <MapComponents.NavigationControl position="top-right" />
            <MapComponents.ScaleControl position="bottom-right" />
          </MapComponents.Map>
        ) : (
          <div className="glass-panel" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            Loading map engine...
          </div>
        )}

        {/* Floating toggle button for mobile or when collapsed */}
        <button 
          className="glass-panel flex-center"
          style={{
            position: 'absolute',
            top: 'var(--space-md)',
            left: 'var(--space-md)',
            width: '40px',
            height: '40px',
            borderRadius: '50%',
            zIndex: 20
          }}
          onClick={() => setShowLayerPanel(!showLayerPanel)}
        >
          <Layers size={20} color={showLayerPanel ? 'var(--accent-blue)' : 'var(--text-primary)'} />
        </button>
      </div>

      {/* Basic internal styling for this component */}
      <style>{`
        .layer-item {
          background: rgba(0,0,0,0.2);
          padding: var(--space-md);
          border-radius: var(--radius-md);
          border: 1px solid var(--border-light);
        }
        .toggle-switch {
          width: 36px;
          height: 20px;
          background: var(--bg-secondary);
          border-radius: 10px;
          position: relative;
          cursor: pointer;
        }
        .toggle-switch::after {
          content: '';
          position: absolute;
          top: 2px;
          left: 2px;
          width: 16px;
          height: 16px;
          background: var(--text-secondary);
          border-radius: 50%;
          transition: 0.2s;
        }
        .toggle-switch.active {
          background: var(--accent-blue);
        }
        .toggle-switch.active::after {
          left: 18px;
          background: white;
        }
        .text-accent-blue {
          color: var(--accent-blue);
        }

        @media (max-width: 768px) {
          .map-sidebar {
            position: absolute !important;
            bottom: 0;
            left: 0;
            width: 100% !important;
            min-width: 100% !important;
            height: 50% !important;
            border-radius: var(--radius-lg) var(--radius-lg) 0 0 !important;
            transform: translateY(${showLayerPanel ? '0' : '100%'});
          }
        }
      `}</style>
    </div>
  );
};

export default MapExplorer;
