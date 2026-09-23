import React from 'react';

// Compact representation of a brand presence / coverage bar in RTL.
export default function BrandBarRow({ name, color, value, max, suffix = '', highlight = false }) {
  const pct = max ? (value / max) * 100 : 0;
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="flex items-center gap-2 font-medium text-foreground">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
          {name}
        </span>
        <span className="font-semibold text-foreground ltr-nums">{suffix}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color, opacity: highlight ? 1 : 0.85 }}
        />
      </div>
    </div>
  );
}