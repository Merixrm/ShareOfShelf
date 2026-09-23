import React from 'react';
import { AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { toFa } from '@/lib/format';

function FaTooltip({ active, payload, label, unit }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-semibold text-foreground">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="flex items-center gap-1.5 text-muted-foreground">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.color || p.stroke }} />
          {p.name}: <span className="font-medium text-foreground">{toFa(p.value)}</span>
          {unit ? ` ${unit}` : ''}
        </p>
      ))}
    </div>
  );
}

// Multi-series trend. series: [{name, color, data[]}] aligned to labels[].
export default function TrendArea({ labels, series, height = 240, single = false, unit = '' }) {
  if (!series || series.length === 0) {
    return (
      <div className="flex items-center justify-center text-xs text-muted-foreground" style={{ height }}>
        داده‌ای برای نمایش وجود ندارد
      </div>
    );
  }
  const data = labels.map((l, i) => {
    const row = { name: l };
    series.forEach((s) => { row[s.name] = s.data[i] ?? 0; });
    return row;
  });
  const isArea = single || series.length === 1;

  return (
    <ResponsiveContainer width="100%" height={height}>
      {isArea ? (
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="ta-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={series[0].color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={series[0].color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={36} tickFormatter={(v) => toFa(v)} />
          <Tooltip content={<FaTooltip unit={unit} />} cursor={{ stroke: 'hsl(var(--border))' }} />
          <Area type="monotone" dataKey={series[0].name} stroke={series[0].color} strokeWidth={2} fill="url(#ta-grad)" />
        </AreaChart>
      ) : (
        <LineChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 10, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={36} tickFormatter={(v) => toFa(v)} />
          <Tooltip content={<FaTooltip unit={unit} />} cursor={{ stroke: 'hsl(var(--border))' }} />
          <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'Vazirmatn' }} iconType="circle" iconSize={8} />
          {series.map((s) => (
            <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
          ))}
        </LineChart>
      )}
    </ResponsiveContainer>
  );
}