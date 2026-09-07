import { useEffect, useState, useMemo } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMapEvents, CircleMarker } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { api } from '../services/api';

// Fix for default marker icon in Leaflet + Vite
import icon from 'leaflet/dist/images/marker-icon.png';
import iconShadow from 'leaflet/dist/images/marker-shadow.png';

const DefaultIcon = L.icon({
  iconUrl: icon,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41]
});
L.Marker.prototype.options.icon = DefaultIcon;

const stationIcon = L.divIcon({
  className: 'custom-station-icon',
  html: `<div style="width: 14px; height: 14px; background-color: white; border: 3px solid #0f172a; border-radius: 50%; box-shadow: 0 0 0 2px rgba(255,255,255,0.8);"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7]
});

const haltIcon = L.divIcon({
  className: 'custom-halt-icon',
  html: `<div style="width: 8px; height: 8px; background-color: #cbd5e1; border: 2px solid #334155; border-radius: 50%;"></div>`,
  iconSize: [8, 8],
  iconAnchor: [4, 4]
});

function MapClickHandler({ onMapClick }: { onMapClick: () => void }) {
  useMapEvents({
    click: () => {
      onMapClick();
    },
  });
  return null;
}

interface MapStation {
  name?: string;
  station_name?: string;
  node_id?: string;
  station_code?: string;
  latitude?: string | number;
  lat?: string | number;
  longitude?: string | number;
  lon?: string | number;
  lng?: string | number;
  railway_type?: string;
  operator?: string;
  network?: string;
}

interface MapNode {
  id: string;
  lat: number;
  lon: number;
  name?: string;
}

interface HyderabadMapProps {
  blocks: any[];
  selectedBlockId?: string | null;
  blockDetail?: any;
  onBlockSelect: (id: string | null) => void;
}

export default function HyderabadMap({ blocks, selectedBlockId, blockDetail, onBlockSelect }: HyderabadMapProps) {
  const [mapData, setMapData] = useState<any>(null);

  useEffect(() => {
    api.getHyderabadMap().then(setMapData).catch(console.error);
  }, []);

  const popupPosition = useMemo(() => {
    if (!selectedBlockId) return null;
    const block = blocks.find((b: any) => b.block_id === selectedBlockId);
    if (!block || !block.geometry) return null;
    try {
      const layer = L.geoJSON(block.geometry);
      return layer.getBounds().getCenter();
    } catch (e) {
      return null;
    }
  }, [selectedBlockId, blocks]);

  if (!mapData) {
    return <div className="w-full h-full flex items-center justify-center bg-slate-800 text-slate-400 rounded-xl">Loading map data...</div>;
  }

  // Center of Hyderabad
  const center: [number, number] = [17.3850, 78.4867];
  const hasSelection = !!selectedBlockId;

  return (
    <div className="w-full h-full rounded-xl overflow-hidden border border-slate-700 relative z-0">
      <MapContainer center={center} zoom={11} style={{ height: '100%', width: '100%' }}>
        <MapClickHandler onMapClick={() => onBlockSelect(null)} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {/* Base Network Layer */}
        {mapData.network && (
          <GeoJSON
            key="base-network"
            data={mapData.network}
            style={() => ({
              color: '#64748b', // subdued gray for base network
              weight: 2,
              opacity: 0.5
            })}
          />
        )}

        {/* All Maintenance Blocks */}
        {blocks.map((block: any) => {
          if (!block.geometry) return null;
          const isSelected = selectedBlockId === block.block_id;
          
          return (
            <GeoJSON
              key={`block-${block.block_id}-${isSelected}`} // force re-render on selection state change
              data={block.geometry}
              style={() => ({
                color: isSelected ? '#f97316' : '#0ea5e9', // orange if selected, blue if not
                weight: isSelected ? 6 : 4,
                opacity: isSelected ? 1 : (hasSelection ? 0.2 : 0.8)
              })}
              eventHandlers={{
                click: (e) => {
                  L.DomEvent.stopPropagation(e as any);
                  onBlockSelect(block.block_id);
                }
              }}
            />
          );
        })}

        {/* Selected Block Popup (Standalone) */}
        {selectedBlockId && popupPosition && (() => {
          const block = blocks.find((b: any) => b.block_id === selectedBlockId);
          if (!block) return null;
          return (
            <Popup position={popupPosition} eventHandlers={{ remove: () => onBlockSelect(null) }} autoPan={false}>
              <div className="text-sm font-sans min-w-[200px]">
                <div className="font-bold text-slate-800 text-base mb-1">{block.block_id}</div>
                <div className="text-slate-600 mb-2">{block.date} | {block.start_time} - {block.end_time}</div>
                <div className="grid grid-cols-2 gap-2 text-xs mb-2">
                  <div className="bg-slate-100 p-1.5 rounded">
                    <span className="text-slate-400 block text-[10px] uppercase">Corridor</span>
                    <span className="font-medium text-slate-700">{block.corridor_id}</span>
                  </div>
                  <div className="bg-slate-100 p-1.5 rounded">
                    <span className="text-slate-400 block text-[10px] uppercase">Utilization</span>
                    <span className="font-medium text-slate-700">{block.utilization}%</span>
                  </div>
                </div>
                
                {blockDetail && blockDetail.block.block_id === block.block_id ? (
                  <div className="mt-3 border-t pt-2">
                    <span className="text-slate-400 block text-[10px] uppercase mb-1">Optimization Rationale</span>
                    <ul className="list-disc pl-4 text-xs text-slate-600 space-y-1">
                      {blockDetail.explanation.map((exp: string, idx: number) => (
                        <li key={idx}>{exp}</li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <div className="mt-3 text-xs text-sky-600 animate-pulse">Loading advanced details...</div>
                )}
              </div>
            </Popup>
          );
        })()}

        {/* Station Markers */}
        {mapData.stations && mapData.stations.map((station: MapStation, i: number) => {
          const lat = parseFloat((station.latitude || station.lat) as string);
          const lon = parseFloat((station.longitude || station.lon || station.lng) as string);
          if (!isNaN(lat) && !isNaN(lon)) {
            return (
              <Marker 
                key={`station-${i}`} 
                position={[lat, lon]}
                icon={station.railway_type === 'halt' ? haltIcon : stationIcon}
                eventHandlers={{
                  click: (e) => L.DomEvent.stopPropagation(e as any)
                }}
              >
                <Popup>
                  <div className="font-sans min-w-[200px]">
                    <div className="font-bold text-slate-800 text-sm border-b pb-1 mb-2">
                      {station.station_name || station.name || 'Station'}
                    </div>
                    <div className="text-xs text-slate-600 space-y-1">
                      {(station.station_code || station.node_id) && (
                        <div><span className="font-semibold text-slate-500">Code:</span> {station.station_code || station.node_id}</div>
                      )}
                      <div><span className="font-semibold text-slate-500">Lat:</span> {lat.toFixed(4)}</div>
                      <div><span className="font-semibold text-slate-500">Lon:</span> {lon.toFixed(4)}</div>
                      {station.railway_type && (
                        <div><span className="font-semibold text-slate-500">Type:</span> {station.railway_type}</div>
                      )}
                      {station.operator && (
                        <div><span className="font-semibold text-slate-500">Operator:</span> {station.operator}</div>
                      )}
                      {station.network && (
                        <div><span className="font-semibold text-slate-500">Network:</span> {station.network}</div>
                      )}
                    </div>
                  </div>
                </Popup>
              </Marker>
            );
          }
          return null;
        })}

        {/* Node Markers (if provided by backend in future) */}
        {mapData.nodes && mapData.nodes.map((node: MapNode, i: number) => {
          const lat = parseFloat(node.lat as any);
          const lon = parseFloat(node.lon as any);
          if (!isNaN(lat) && !isNaN(lon)) {
            return (
              <CircleMarker 
                key={`node-${i}`} 
                center={[lat, lon]}
                radius={5}
                color="#8b5cf6" // distinct purple for nodes
                fillColor="#8b5cf6"
                fillOpacity={0.7}
                weight={2}
                eventHandlers={{
                  click: (e) => L.DomEvent.stopPropagation(e as any)
                }}
              >
                <Popup>
                  <div className="font-sans min-w-[150px]">
                    <div className="font-bold text-slate-800 text-sm border-b pb-1 mb-1">
                      Railway Node
                    </div>
                    <div className="text-xs text-slate-600 space-y-1 mt-2">
                      <div><span className="font-semibold text-slate-500">ID:</span> {node.id}</div>
                      {node.name && <div><span className="font-semibold text-slate-500">Name:</span> {node.name}</div>}
                      <div><span className="font-semibold text-slate-500">Lat:</span> {lat.toFixed(4)}</div>
                      <div><span className="font-semibold text-slate-500">Lon:</span> {lon.toFixed(4)}</div>
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            );
          }
          return null;
        })}
      </MapContainer>
    </div>
  );
}
