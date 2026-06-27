import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' ? window.innerWidth <= 768 : false);
  const [showLayerPanel, setShowLayerPanel] = useState(() => typeof window !== 'undefined' ? window.innerWidth > 768 : false);
  const [layerVisibility, setLayerVisibility] = useState({
    competitorDensity: true,
    populationDensity: true,
  });
  const navigate = useNavigate();
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

  useEffect(() => {
    const handleResize = () => {
      const mobile = window.innerWidth <= 768;
      setIsMobile(mobile);
      setShowLayerPanel((current) => (mobile ? current : true));
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const visibleLayers = Object.values(layerVisibility).filter(Boolean).length;

  return (
    <div
      className="map-explorer-container"
      style={{
        display: 'flex',
        height: '100%',
        width: '100%',
        position: 'relative',
        paddingBottom: isMobile ? '88px' : '0',
      }}
    >
      
      {/* Sidebar for Map Analysis Controls */}
      <div 
        className={`map-sidebar glass-panel ${showLayerPanel ? 'visible' : 'hidden'}`}
        style={{
          width: isMobile ? '100%' : showLayerPanel ? '35%' : '0',
          minWidth: isMobile ? '100%' : showLayerPanel ? '300px' : '0',
          margin: '0',
          borderTopRightRadius: isMobile ? 'var(--radius-lg)' : 0,
          borderBottomRightRadius: 0,
          transition: 'all 0.3s ease',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 10,
          boxShadow: isMobile && showLayerPanel ? '0 -18px 40px rgba(0, 0, 0, 0.42)' : undefined,
        }}
      >
        <div style={{ padding: 'var(--space-md)', borderBottom: '1px solid var(--border-light)' }}>
          <div
            style={{
              width: '48px',
              height: '4px',
              borderRadius: '999px',
              background: 'rgba(255,255,255,0.2)',
              margin: isMobile ? '0 auto var(--space-sm)' : '0 0 var(--space-sm)',
            }}
          />
          <h2 style={{ fontSize: 'var(--font-xl)', fontWeight: 'var(--weight-semibold)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Layers size={20} className="text-accent-blue" />
            Analysis Layers
          </h2>
        </div>

        <div className="scrollable-y" style={{ flex: 1, padding: 'var(--space-md)' }}>
          <div className="layer-item">
            <div className="flex-between">
              <span style={{ fontWeight: 'var(--weight-medium)' }}>Competitor Density</span>
              <button
                type="button"
                className={`toggle-switch ${layerVisibility.competitorDensity ? 'active' : ''}`}
                aria-pressed={layerVisibility.competitorDensity}
                aria-label="Toggle Competitor Density"
                onClick={() =>
                  setLayerVisibility((current) => ({
                    ...current,
                    competitorDensity: !current.competitorDensity,
                  }))
                }
              />
            </div>
            <div
              style={{
                marginTop: 'var(--space-sm)',
                fontSize: 'var(--font-xs)',
                color: layerVisibility.competitorDensity ? 'var(--text-secondary)' : 'rgba(148,163,184,0.5)',
                opacity: layerVisibility.competitorDensity ? 1 : 0.55,
              }}
            >
              Source: OSM • Vintage: 2024
            </div>
            {!layerVisibility.competitorDensity && (
              <div style={{ marginTop: 'var(--space-xs)', fontSize: 'var(--font-xs)', color: 'var(--text-secondary)' }}>
                Layer hidden from the map preview
              </div>
            )}
          </div>

          <div className="layer-item" style={{ marginTop: 'var(--space-md)' }}>
            <div className="flex-between">
              <span style={{ fontWeight: 'var(--weight-medium)' }}>Population Density</span>
              <button
                type="button"
                className={`toggle-switch ${layerVisibility.populationDensity ? 'active' : ''}`}
                aria-pressed={layerVisibility.populationDensity}
                aria-label="Toggle Population Density"
                onClick={() =>
                  setLayerVisibility((current) => ({
                    ...current,
                    populationDensity: !current.populationDensity,
                  }))
                }
              />
            </div>
            <div
              style={{
                marginTop: 'var(--space-sm)',
                fontSize: 'var(--font-xs)',
                color: layerVisibility.populationDensity ? 'var(--text-secondary)' : 'rgba(148,163,184,0.5)',
                opacity: layerVisibility.populationDensity ? 1 : 0.55,
              }}
            >
              Source: Census ACS • Vintage: 2022
            </div>
            <div
              style={{
                marginTop: 'var(--space-xs)',
                fontSize: 'var(--font-xs)',
                color: layerVisibility.populationDensity ? 'var(--accent-rose)' : 'rgba(244,63,94,0.5)',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                opacity: layerVisibility.populationDensity ? 1 : 0.55,
              }}
            >
              <AlertTriangle size={12} /> Some tracts suppressed
            </div>
            {!layerVisibility.populationDensity && (
              <div style={{ marginTop: 'var(--space-xs)', fontSize: 'var(--font-xs)', color: 'var(--text-secondary)' }}>
                Population layer is currently off
              </div>
            )}
          </div>
        </div>

        <div style={{ padding: 'var(--space-md)', borderTop: '1px solid var(--border-light)' }}>
          <button
            className="btn-primary"
            type="button"
            onClick={() => navigate('/analysis')}
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
          >
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
            style={{
              width: '100%',
              height: '100%',
              filter: visibleLayers === 2 ? 'none' : 'saturate(0.9) brightness(0.95)',
              transition: 'filter 0.25s ease',
            }}
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
            zIndex: 20,
            boxShadow: '0 10px 24px rgba(0,0,0,0.35)',
          }}
          onClick={() => setShowLayerPanel(!showLayerPanel)}
          aria-label={showLayerPanel ? 'Hide analysis layers' : 'Show analysis layers'}
          aria-expanded={showLayerPanel}
        >
          <Layers size={20} color={showLayerPanel ? 'var(--accent-blue)' : 'var(--text-primary)'} />
        </button>

        <div
          style={{
            position: 'absolute',
            top: 'var(--space-md)',
            right: 'var(--space-md)',
            zIndex: 20,
            padding: '0.5rem 0.75rem',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(2,6,23,0.82)',
            border: '1px solid var(--border-light)',
            color: 'var(--text-primary)',
            fontSize: 'var(--font-xs)',
            maxWidth: isMobile ? 'calc(100% - 92px)' : 'none',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {visibleLayers} layer{visibleLayers === 1 ? '' : 's'} active
        </div>
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
          border: none;
          padding: 0;
          flex-shrink: 0;
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
        .toggle-switch:not(.active) {
          background: rgba(255, 255, 255, 0.12);
        }
        .toggle-switch:not(.active)::after {
          background: rgba(255, 255, 255, 0.55);
        }
        .text-accent-blue {
          color: var(--accent-blue);
        }

        @media (max-width: 768px) {
          .map-sidebar {
            position: absolute !important;
            bottom: 88px;
            left: 0;
            width: 100% !important;
            min-width: 100% !important;
            height: min(68vh, 560px) !important;
            border-radius: var(--radius-lg) var(--radius-lg) 0 0 !important;
            transform: translateY(${showLayerPanel ? '0' : 'calc(100% + 88px)'});
          }

          .map-explorer-container {
            padding-bottom: 88px;
          }

          .map-sidebar .layer-item {
            padding: var(--space-sm);
          }
        }
      `}</style>
    </div>
  );
};

export default MapExplorer;
