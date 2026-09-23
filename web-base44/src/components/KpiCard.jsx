import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { faNum, faPct, toFa } from '@/lib/format';

export default function KpiCard({ label, value, unit, delta, format = 'num', icon: Icon, accent = false, help }) {
  const formatted = format === 'pct' ? faPct(value, 1) : format === 'raw' ? value : faNum(value);
  const DeltaIcon = delta > 0 ? TrendingUp : delta < 0 ? TrendingDown : Minus;
  const deltaColor = delta > 0 ? 'text-success' : delta < 0 ? 'text-destructive' : 'text-muted-foreground';

  return (
    <div className={`group relative overflow-hidden rounded-xl border bg-card p-4 transition-shadow hover:shadow-md ${accent ? 'border-brand/30' : 'border-border'}`}>
      {accent && <span className="absolute inset-y-0 right-0 w-1 bg-brand" />}
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {Icon && (
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${accent ? 'bg-brand/10 text-brand' : 'bg-muted text-muted-foreground'}`}>
            <Icon className="h-4 w-4" />
          </div>
        )}
      </div>
      <div className="mt-2.5 flex items-end gap-2">
        <span className="text-2xl font-bold tracking-tight text-foreground">{formatted}</span>
        {unit && <span className="mb-0.5 text-xs text-muted-foreground">{unit}</span>}
      </div>
      {delta !== undefined && (
        <div className="mt-2 flex items-center gap-1 text-xs">
          <span className={`flex items-center gap-0.5 font-medium ${deltaColor}`}>
            <DeltaIcon className="h-3 w-3" />
            {toFa(Math.abs(delta).toFixed(1))}٪
          </span>
          <span className="text-muted-foreground">نسبت به دوره قبل</span>
        </div>
      )}
    </div>
  );
}