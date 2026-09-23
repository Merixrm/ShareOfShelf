import React from 'react';
import { MapPin, Package, Eye, Calendar, Layers } from 'lucide-react';
import { toFa, faPct, faDateLong } from '@/lib/format';

// Content rendered inside a Leaflet popup (RTL).
export default function StorePopupCard({ point }) {
  const sos = Math.min(100, 18 + point.count * 1.4);
  return (
    <div dir="rtl" className="w-64 rounded-xl bg-card text-card-foreground">
      <div className="flex items-center gap-2 border-b border-border bg-primary px-3 py-2.5">
        <MapPin className="h-4 w-4 text-brand" />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold text-primary-foreground">{point.store.name}</p>
          <p className="truncate text-[10px] text-primary-foreground/70">{point.store.district}</p>
        </div>
      </div>
      <div className="space-y-2.5 p-3 text-xs">
        <Row icon={Package} label="محصول‌های شناسایی‌شده" value={`${toFa(point.products)} نوع`} />
        <Row icon={Eye} label="تعداد مشاهدات" value={toFa(point.observations)} />
        <Row icon={Layers} label="برندهای موجود">
          <div className="flex flex-wrap justify-end gap-1">
            {point.brands.slice(0, 4).map((b) => (
              <span key={b} className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-foreground">{b}</span>
            ))}
          </div>
        </Row>
        <Row icon={Calendar} label="آخرین مشاهده" value={faDateLong(point.last)} />
        <div className="flex items-center justify-between border-t border-border pt-2">
          <span className="text-muted-foreground">سهم قفسه در این فروشگاه</span>
          <span className="font-bold text-brand">{faPct(sos)}</span>
        </div>
      </div>
    </div>
  );
}

function Row({ icon: Icon, label, value, children }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </span>
      {children ?? <span className="font-medium text-foreground">{value}</span>}
    </div>
  );
}