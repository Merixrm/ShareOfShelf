import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Flame, MapPin, Store, ChevronLeft } from 'lucide-react';
import { useFilters } from '@/lib/FilterContext';
import { mapPoints } from '@/lib/mockData';
import PageHero from '@/components/PageHero';
import FilterBar from '@/components/FilterBar';
import DistributionMap from '@/components/DistributionMap';
import EmptyState from '@/components/EmptyState';
import { toFa } from '@/lib/format';

export default function DistributionMapPage() {
  const { filters } = useFilters();
  const navigate = useNavigate();
  const [mode, setMode] = useState('heatmap');

  const points = useMemo(() => mapPoints(filters), [filters]);

  const activeFilter = filters.brandId || filters.flavor || filters.size || filters.sku;

  return (
    <div className="space-y-5">
      <PageHero
        title="نقشه هوشمند توزیع"
        subtitle="تمرکز مشاهدات محصول و موقعیت فروشگاه‌های پایش‌شده در مشهد. با انتخاب محصول، فقط موقعیت‌های دارای آن محصول نمایش داده می‌شوند."
      >
        <FilterBar show={['brand', 'flavor', 'size', 'sku', 'period']} compact />
      </PageHero>

      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-3">
        <div className="inline-flex rounded-lg border border-border p-0.5">
          <button
            type="button"
            onClick={() => setMode('heatmap')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition ${mode === 'heatmap' ? 'bg-brand text-brand-foreground' : 'text-muted-foreground hover:text-foreground'}`}
          >
            <Flame className="h-3.5 w-3.5" /> نقشه حرارتی
          </button>
          <button
            type="button"
            onClick={() => setMode('store')}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition ${mode === 'store' ? 'bg-brand text-brand-foreground' : 'text-muted-foreground hover:text-foreground'}`}
          >
            <MapPin className="h-3.5 w-3.5" /> نقشه فروشگاه‌ها
          </button>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Store className="h-4 w-4" />
          <span>{toFa(points.length)} فروشگاه نمایش داده شده</span>
          {activeFilter && <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-medium text-brand">فیلتر محصول فعال</span>}
        </div>
      </div>

      {/* Map */}
      {points.length ? (
        <DistributionMap points={points} mode={mode} height={560} onSelectStore={(s) => navigate(`/stores/${s.id}`)} />
      ) : (
        <div className="rounded-xl border border-border bg-card">
          <EmptyState
            icon={MapPin}
            title="موردی برای نمایش روی نقشه نیست"
            description="با تغییر فیلترها، موقعیت محصولات را روی نقشه ببینید."
          />
        </div>
      )}

      {/* Store list */}
      <div>
        <div className="mb-3 flex items-center gap-2">
          <h3 className="text-sm font-bold text-foreground">فروشگاه‌های منطبق</h3>
          <span className="text-xs text-muted-foreground">({toFa(points.length)})</span>
        </div>
        <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {points.slice(0, 16).map((p) => (
            <button
              key={p.store.id}
              onClick={() => navigate(`/stores/${p.store.id}`)}
              className="group rounded-xl border border-border bg-card p-3 text-right transition hover:border-brand/40 hover:shadow-sm"
            >
              <div className="flex items-center justify-between">
                <p className="truncate text-xs font-bold text-foreground">{p.store.name}</p>
                <ChevronLeft className="h-3.5 w-3.5 text-muted-foreground transition group-hover:text-brand" />
              </div>
              <p className="mt-0.5 truncate text-[10px] text-muted-foreground">{p.store.district}</p>
              <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
                <span>{toFa(p.products)} محصول</span>
                <span>{toFa(p.observations)} مشاهده</span>
                <span>{toFa(p.brands.length)} برند</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}