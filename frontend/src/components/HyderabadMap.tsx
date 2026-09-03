import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, Marker, Popup } from 'react-leaflet';
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

  if (!mapData) {
    return <div className="w-full h-full flex items-center justify-center bg-slate-800 text-slate-400 rounded-xl">Loading map data...</div>;
  }

  // Center of Hyderabad
  const center: [number, number] = [17.3850, 78.4867];
  const hasSelection = !!selectedBlockId;

  return (
    <div className="w-full h-full rounded-xl overflow-hidden border border-slate-700 relative z-0">
      <MapContainer center={center} zoom={11} style={{ height: '100%', width: '100%' }}>
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
            >
              {isSelected && (
                <Popup autoPan={false}>
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
              )}
            </GeoJSON>
          );
        })}

        {/* Station Markers */}
        {mapData.stations && mapData.stations.map((station: any, i: number) => {
          const lat = parseFloat(station.latitude || station.lat);
          const lon = parseFloat(station.longitude || station.lon || station.lng);
          if (!isNaN(lat) && !isNaN(lon)) {
            return (
              <Marker key={`station-${i}`} position={[lat, lon]}>
                <Popup>
                  <div className="font-semibold text-slate-800">
                    {station.station_name || station.name || 'Station'}
                  </div>
                  {station.station_code && (
                    <div className="text-xs text-slate-500">{station.station_code}</div>
                  )}
                </Popup>
              </Marker>
            );
          }
          return null;
        })}
      </MapContainer>
    </div>
  );
}
