import React, { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Target, TrendingDown, AlertTriangle, MapPin, Store, ArrowLeft } from 'lucide-react';
import { useFilters } from '@/lib/FilterContext';
import { opportunityInsights, areaStrengthData, mapPoints, stores, productById, observations, BRANDS } from '@/lib/mockData';
import PageHero from '@/components/PageHero';
import FilterBar from '@/components/FilterBar';
import SectionCard from '@/components/SectionCard';
import EmptyState from '@/components/EmptyState';
import { toFa } from '@/lib/format';

export default function Opportunities() {
  const { filters } = useFilters();
  const navigate = useNavigate();

  const insights = useMemo(() => opportunityInsights(filters), [filters]);
  const areas = useMemo(() => areaStrengthData(filters), [filters]);
  const strong = areas.slice(0, 5);
  const weak = [...areas].sort((a, b) => a.count - b.count).slice(0, 5);
  const maxArea = Math.max(1, ...areas.map((a) => a.count));

  // stores missing selected SKU
  const missingStores = useMemo(() => {
    if (!filters.sku) return [];
    const product = observations.some((o) => productById[o.product_id]?.sku === filters.sku)
      ? Object.values(productById).find((p) => p.sku === filters.sku || p.id === filters.sku)
      : null;
    if (!product) return [];
    const carrying = new Set(observations.filter((o) => o.product_id === product.id).map((o) => o.store_id));
    return stores.filter((s) => !carrying.has(s.id)).slice(0, 8);
  }, [filters.sku]);

  return (
    <div className="space-y-5">
      <PageHero title="فرصت‌های بازار" subtitle="تحلیل شکاف‌های توزیع: مناطق با حضور قوی/ضعیف، تسلط رقبا و فروشگاه‌های فاقد محصول موردنظر.">
        <FilterBar show={['brand', 'flavor', 'size', 'sku', 'period']} compact />
      </PageHero>

      {/* Insight cards */}
      <div>
        <h3 className="mb-3 flex items-center gap-2 text-sm font-bold text-foreground"><Target className="h-4 w-4 text-brand" /> فرصت‌های توزیع</h3>
        {insights.length ? (
          <div className="grid gap-3 md:grid-cols-2">
            {insights.map((ins) => (
              <div key={ins.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full" style={{ backgroundColor: ins.color }} />
                    <span className="text-sm font-bold text-foreground">{ins.brand}</span>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">{ins.district}</span>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${ins.severity === 'بحرانی' ? 'bg-destructive/10 text-destructive' : ins.severity === 'بالا' ? 'bg-warning/15 text-warning' : 'bg-primary/10 text-primary'}`}>{ins.severity}</span>
                </div>
                <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{ins.text}</p>
                <div className="mt-3 flex items-center justify-between border-t border-border pt-2.5 text-[11px]">
                  <span className="text-muted-foreground">حضور این برند: <span className="font-semibold text-destructive">{toFa(ins.mine)}</span></span>
                  <span className="text-muted-foreground">رقبا: <span className="font-semibold text-foreground">{toFa(ins.comp)}</span></span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-border bg-card"><EmptyState icon={Target} title="فرصت آشکاری یافت نشد" description="با انتخاب برند یا محصول خاص، شکاف‌های توزیع نمایش داده می‌شوند." /></div>
        )}
      </div>

      {/* Strong / weak areas */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="مناطق با حضور قوی" subtitle="بیشترین تراکم مشاهدات">
          <div className="space-y-3">
            {strong.map((a) => (
              <AreaBar key={a.district} name={a.district} value={a.count} max={maxArea} color="#16a34a" />
            ))}
          </div>
        </SectionCard>
        <SectionCard title="مناطق با حضور ضعیف" subtitle="کمترین تراکم مشاهدات" help="مناطقی که نیاز به توسعه توزیع دارند.">
          <div className="space-y-3">
            {weak.map((a) => (
              <AreaBar key={a.district} name={a.district} value={a.count} max={maxArea} color="#dc2626" />
            ))}
          </div>
        </SectionCard>
      </div>

      {/* Missing SKU stores */}
      <SectionCard
        title="فروشگاه‌های فاقد محصول انتخاب‌شده"
        subtitle={filters.sku ? 'فروشگاه‌هایی که این SKU در آن‌ها مشاهده نشده است' : 'برای مشاهده، یک SKU از فیلترها انتخاب کنید'}
      >
        {filters.sku && missingStores.length ? (
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {missingStores.map((s) => (
              <button key={s.id} onClick={() => navigate(`/stores/${s.id}`)} className="group rounded-lg border border-border p-3 text-right transition hover:border-brand/40">
                <div className="flex items-center justify-between">
                  <p className="truncate text-xs font-semibold text-foreground">{s.name}</p>
                  <ArrowLeft className="h-3.5 w-3.5 text-muted-foreground transition group-hover:text-brand" />
                </div>
                <p className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground"><MapPin className="h-3 w-3" /> {s.district}</p>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState icon={Store} title={filters.sku ? 'همه فروشگاه‌ها این محصول را دارند' : 'SKUای انتخاب نشده'} description={filters.sku ? 'فرصت توزیع وجود ندارد.' : 'از فیلتر بالا یک SKU انتخاب کنید.'} />
        )}
      </SectionCard>
    </div>
  );
}

function AreaBar({ name, value, max, color }) {
  const pct = max ? (value / max) * 100 : 0;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-medium text-foreground">{name}</span>
        <span className="text-muted-foreground">{toFa(value)} مشاهده</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}