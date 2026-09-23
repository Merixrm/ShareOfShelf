import React, { useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { MapPin } from 'lucide-react';
import { MASHHAD_CENTER } from '@/lib/mockData';
import { toFa } from '@/lib/format';
import StorePopupCard from './StorePopupCard';

// Color scale by observation intensity (0..1)
function heatColor(t) {
  if (t > 0.75) return '#dc2626';
  if (t > 0.5) return '#ea580c';
  if (t > 0.3) return '#d97706';
  return '#16a34a';
}

export default function DistributionMap({ points, mode = 'store', onSelectStore, height = 560, center, zoom = 12 }) {
  const maxCount = useMemo(() => Math.max(1, ...points.map((p) => p.count)), [points]);

  return (
    <div className="relative w-full overflow-hidden rounded-xl border border-border" style={{ height }}>
      <MapContainer
        center={center || [MASHHAD_CENTER.lat, MASHHAD_CENTER.lng]}
        zoom={zoom}
        scrollWheelZoom
        style={{ height: '100%', width: '100%' }}
        attributionControl
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; OpenStreetMap contributors'
          subdomains={['a', 'b', 'c']}
        />
        {points.map((p) => {
          const t = p.count / maxCount;
          const color = mode === 'heatmap' ? heatColor(t) : '#1e3a5f';
          const radius = mode === 'heatmap' ? 14 + t * 30 : 7 + t * 4;
          const fillOpacity = mode === 'heatmap' ? 0.22 + t * 0.28 : 0.85;
          return (
            <CircleMarker
              key={p.store.id}
              center={[p.lat, p.lng]}
              radius={radius}
              pathOptions={{
                color: mode === 'heatmap' ? color : '#ffffff',
                weight: mode === 'heatmap' ? 0 : 2,
                fillColor: color,
                fillOpacity,
              }}
              eventHandlers={{ click: () => onSelectStore?.(p.store) }}
            >
              {mode === 'store' && (
                <Tooltip direction="top" offset={[0, -6]} opacity={1}>
                  <span dir="rtl" className="text-xs font-medium">{p.store.name}</span>
                </Tooltip>
              )}
              <Popup>
                <StorePopupCard point={p} />
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {/* Legend */}
      <div className="absolute bottom-3 left-3 z-[1000] rounded-lg border border-border bg-card/95 px-3 py-2 shadow-sm backdrop-blur">
        <p className="mb-1.5 text-[10px] font-semibold text-muted-foreground">
          {mode === 'heatmap' ? 'تراکم مشاهدات' : 'فروشگاه‌های پایش‌شده'}
        </p>
        {mode === 'heatmap' ? (
          <div className="flex items-center gap-1.5">
            {['#16a34a', '#d97706', '#ea580c', '#dc2626'].map((c) => (
              <span key={c} className="h-2.5 w-6 rounded-sm" style={{ backgroundColor: c, opacity: 0.8 }} />
            ))}
            <span className="ml-1 text-[10px] text-muted-foreground">کم → زیاد</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
            <MapPin className="h-3 w-3 text-primary" />
            <span>{toFa(points.length)} فروشگاه</span>
          </div>
        )}
      </div>
    </div>
  );
}