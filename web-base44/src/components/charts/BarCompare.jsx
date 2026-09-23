import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { toFa, faPct } from '@/lib/format';

// Grouped vertical bars for comparing two metrics per category.
// data: [{ brand, facingsPct, areaPct, color }]
export default function BarCompare({ data, height = 260, metrics }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }} barGap={4}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
        <XAxis dataKey="brand" tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} />
        <YAxis tick={{ fontSize: 11, fill: 'hsl(var(--muted-foreground))' }} axisLine={false} tickLine={false} width={40} tickFormatter={(v) => toFa(v)} />
        <Tooltip
          cursor={{ fill: 'hsl(var(--muted))', opacity: 0.4 }}
          content={({ active, payload, label }) =>
            active && payload?.length ? (
              <div className="rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-md">
                <p className="mb-1 font-semibold text-foreground">{label}</p>
                {payload.map((p, i) => (
                  <p key={i} className="flex items-center gap-1.5 text-muted-foreground">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: p.fill }} />
                    {p.name}: <span className="font-medium text-foreground">{faPct(p.value)}</span>
                  </p>
                ))}
              </div>
            ) : null
          }
        />
        <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'Vazirmatn' }} iconType="circle" iconSize={8} />
        {metrics.map((m) => (
          <Bar key={m.key} dataKey={m.key} name={m.label} fill={m.color} radius={[4, 4, 0, 0]} maxBarSize={28} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}