import React, { useMemo, useState } from 'react';
import { Award, Package, Store, Eye, MapPin, TrendingUp, Trophy, AlertCircle } from 'lucide-react';
import { useFilters } from '@/lib/FilterContext';
import { BRANDS, products, observations, productById, storeById, brandTrendData, shareOfShelfData } from '@/lib/mockData';
import PageHero from '@/components/PageHero';
import SectionCard from '@/components/SectionCard';
import FilterBar from '@/components/FilterBar';
import ProductImage from '@/components/ProductImage';
import TrendArea from '@/components/charts/TrendArea';
import BarCompare from '@/components/charts/BarCompare';
import KpiCard from '@/components/KpiCard';
import { toFa, faPct, faDate } from '@/lib/format';

export default function Brands() {
  const { filters } = useFilters();
  const [selected, setSelected] = useState(BRANDS.map((b) => b.id));

  const brandStats = useMemo(() => {
    return BRANDS.map((b) => {
      const bProducts = products.filter((p) => p.brandId === b.id);
      const obs = observations.filter((o) => {
        const p = productById[o.product_id];
        if (!p || p.brandId !== b.id) return false;
        if (filters.flavor && p.flavor !== filters.flavor) return false;
        if (filters.size && p.size !== filters.size) return false;
        if (filters.dateFrom && o.observed_at < filters.dateFrom) return false;
        if (filters.dateTo && o.observed_at > filters.dateTo) return false;
        return true;
      });
      const storeIds = new Set(obs.map((o) => o.store_id));
      const districts = new Set([...storeIds].map((id) => storeById[id]?.district).filter(Boolean));
      const byProduct = {};
      obs.forEach((o) => {
        byProduct[o.product_id] = (byProduct[o.product_id] || 0) + o.detected_count;
      });
      const ranked = Object.entries(byProduct)
        .map(([pid, c]) => ({ product: productById[pid], count: c }))
        .sort((a, b) => b.count - a.count);
      return {
        brand: b, skuCount: bProducts.length, stores: storeIds.size,
        observations: obs.length, geoCoverage: districts.size,
        best: ranked[0]?.product, worst: ranked[ranked.length - 1]?.product,
        facings: obs.reduce((s, o) => s + o.detected_count, 0),
        area: obs.reduce((s, o) => s + o.shelf_area, 0),
      };
    });
  }, [filters]);

  const trend = useMemo(() => {
    const t = brandTrendData(filters);
    return { labels: t.labels, series: t.series.filter((s, i) => selected.includes(BRANDS[i]?.id)) };
  }, [filters, selected]);

  const compare = useMemo(() => {
    const sos = shareOfShelfData(filters);
    return sos.filter((s) => {
      const bid = BRANDS.find((b) => b.name === s.brand)?.id;
      return selected.includes(bid);
    });
  }, [filters, selected]);

  const toggle = (id) => setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <div className="space-y-5">
      <PageHero title="تحلیل برند" subtitle="عملکرد سطح برند، مقایسه رقبا و روند حضور در بازار">
        <FilterBar show={['flavor', 'size', 'period']} compact />
      </PageHero>

      {/* Brand cards */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {brandStats.map((bs) => (
          <div key={bs.brand.id} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="h-9 w-9 rounded-lg" style={{ backgroundColor: bs.brand.color }} />
                <div>
                  <p className="text-sm font-bold text-foreground">{bs.brand.name}</p>
                  <p className="text-[10px] text-muted-foreground">{bs.brand.short}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => toggle(bs.brand.id)}
                className={`h-5 w-5 rounded border-2 transition ${selected.includes(bs.brand.id) ? 'border-brand bg-brand' : 'border-border bg-card'}`}
              />
            </div>
            <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
              <Stat label="SKU" value={toFa(bs.skuCount)} icon={Package} />
              <Stat label="فروشگاه" value={toFa(bs.stores)} icon={Store} />
              <Stat label="مشاهدات" value={toFa(bs.observations)} icon={Eye} />
              <Stat label="منطقه" value={toFa(bs.geoCoverage)} icon={MapPin} />
            </div>
          </div>
        ))}
      </div>

      {/* SoS per brand + compare metrics */}
      <div className="grid gap-4 lg:grid-cols-3">
        <SectionCard title="روند حضور برند" subtitle="تغییرات هفتگی facings" className="lg:col-span-2">
          <TrendArea labels={trend.labels} series={trend.series} height={280} unit=" facing" />
        </SectionCard>
        <SectionCard title="مقایسه برندها" subtitle="سهم قفسه بر اساس facing و فضای اشغالی">
          <div className="space-y-3">
            {brandStats.map((bs) => {
              const totalFacings = brandStats.reduce((s, x) => s + x.facings, 0);
              const totalArea = brandStats.reduce((s, x) => s + x.area, 0);
              const fPct = totalFacings ? (bs.facings / totalFacings) * 100 : 0;
              const aPct = totalArea ? (bs.area / totalArea) * 100 : 0;
              return (
                <div key={bs.brand.id}>
                  <div className="mb-1 flex items-center justify-between text-xs">
                    <span className="font-medium text-foreground">{bs.brand.name}</span>
                    <span className="text-muted-foreground">{faPct(fPct)} · {faPct(aPct)}</span>
                  </div>
                  <div className="space-y-1">
                    <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full" style={{ width: `${fPct}%`, backgroundColor: bs.brand.color }} />
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                      <div className="h-full rounded-full opacity-60" style={{ width: `${aPct}%`, backgroundColor: bs.brand.color }} />
                    </div>
                  </div>
                </div>
              );
            })}
            <div className="flex items-center gap-3 border-t border-border pt-2 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1"><span className="h-1.5 w-3 rounded-full bg-primary" /> سهم facing</span>
              <span className="flex items-center gap-1"><span className="h-1.5 w-3 rounded-full bg-primary opacity-60" /> سهم فضای قفسه</span>
            </div>
          </div>
        </SectionCard>
      </div>

      {/* Best / worst products */}
      <div className="grid gap-4 md:grid-cols-2">
        {brandStats.map((bs) => (
          <SectionCard key={bs.brand.id} title={bs.brand.name} subtitle="بهترین و ضعیف‌ترین محصول">
            <div className="grid grid-cols-2 gap-3">
              <BestWorst icon={Trophy} label="بهترین محصول" product={bs.best} accent="success" />
              <BestWorst icon={AlertCircle} label="ضعیف‌ترین محصول" product={bs.worst} accent="destructive" />
            </div>
          </SectionCard>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value, icon: Icon }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="text-muted-foreground">{label}</span>
      <span className="mr-auto font-semibold text-foreground">{value}</span>
    </div>
  );
}

function BestWorst({ icon: Icon, label, product, accent }) {
  const color = accent === 'success' ? 'text-success' : 'text-destructive';
  return (
    <div className="rounded-lg border border-border p-2.5">
      <p className={`mb-2 flex items-center gap-1 text-[10px] font-medium ${color}`}><Icon className="h-3 w-3" /> {label}</p>
      {product ? (
        <div className="flex items-center gap-2">
          <ProductImage product={product} size={34} />
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold text-foreground">{product.flavor}</p>
            <p className="truncate text-[10px] text-muted-foreground">{product.sku} · {product.size}</p>
          </div>
        </div>
      ) : <p className="text-xs text-muted-foreground">داده‌ای موجود نیست</p>}
    </div>
  );
}