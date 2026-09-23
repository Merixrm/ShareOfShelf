import React, { useMemo } from 'react';
import { Package, Barcode, Store, Eye, Percent, MapPin, ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useFilters } from '@/lib/FilterContext';
import { computeKpis, brandPresenceData, shareOfShelfData, topProducts, marketCoverageData, brandTrendData } from '@/lib/mockData';
import KpiCard from '@/components/KpiCard';
import SectionCard from '@/components/SectionCard';
import FilterBar from '@/components/FilterBar';
import ProductImage from '@/components/ProductImage';
import BrandBarRow from '@/components/BrandBarRow';
import TrendArea from '@/components/charts/TrendArea';
import DonutChart from '@/components/charts/DonutChart';
import { toFa, faPct } from '@/lib/format';

export default function Dashboard() {
  const { filters } = useFilters();
  const kpis = useMemo(() => computeKpis(filters), [filters]);
  const sos = useMemo(() => shareOfShelfData(filters), [filters]);
  const coverage = useMemo(() => marketCoverageData(filters), [filters]);
  const top = useMemo(() => topProducts(filters, 7), [filters]);
  const trend = useMemo(() => brandTrendData(filters), [filters]);
  const presence = useMemo(() => brandPresenceData(filters), [filters]);

  const donutData = sos.map((s) => ({ name: s.brand, value: s.area, color: s.color }));
  const maxPresence = Math.max(1, ...presence.map((p) => p.observations));
  const maxCoverage = 100;

  return (
    <div className="space-y-5">
      {/* Hero */}
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="border-r-2 border-brand p-5">
          <h2 className="text-lg font-bold text-foreground sm:text-xl">سامانه هوشمند پایش بازار و قفسه فروشگاه‌ها</h2>
          <p className="mt-1.5 max-w-3xl text-sm text-muted-foreground">
            تحلیل هوشمند حضور محصولات، سهم قفسه و شبکه توزیع بر اساس داده‌های بینایی ماشین
          </p>
        </div>
        <div className="border-t border-border bg-muted/30 p-3">
          <FilterBar show={['brand', 'flavor', 'size', 'period']} />
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <KpiCard label="محصولات شناسایی‌شده" value={kpis.products} icon={Package} accent />
        <KpiCard label="SKUهای منحصربه‌فرد" value={kpis.skus} icon={Barcode} />
        <KpiCard label="فروشگاه‌های پایش‌شده" value={kpis.stores} icon={Store} />
        <KpiCard label="مشاهدات محصولات" value={kpis.observations} icon={Eye} delta={kpis.deltaPct} />
        <KpiCard label="میانگین سهم قفسه" value={kpis.avgSos} format="pct" icon={Percent} />
        <KpiCard label="مناطق تحت پوشش" value={kpis.regions} icon={MapPin} />
      </div>

      {/* Trend + Share of Shelf donut */}
      <div className="grid gap-4 lg:grid-cols-3">
        <SectionCard
          title="حضور برندها"
          subtitle="روند هفتگی تعداد facings شناسایی‌شده"
          help="نمودار تعاملی؛ با کلیک روی نام هر برند در راهنما، آن را نمایش/مخفی کنید."
          className="lg:col-span-2"
        >
          <TrendArea labels={trend.labels} series={trend.series} height={280} unit=" facing" />
        </SectionCard>

        <SectionCard title="سهم قفسه برندها" subtitle="بر اساس فضای اشغال‌شده" help="سهم هر برند از مجموع فضای قفسه اشغال‌شده">
          {donutData.length ? (
            <>
              <DonutChart data={donutData} centerLabel="سهم برندها" centerValue="۱۰۰٪" />
              <div className="mt-3 space-y-1.5">
                {sos.map((s) => (
                  <div key={s.brand} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-foreground">
                      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: s.color }} />
                      {s.brand}
                    </span>
                    <span className="font-semibold text-foreground">{faPct(s.areaPct)}</span>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </SectionCard>
      </div>

      {/* Top products + coverage */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard
          title="محصولات پرتکرار"
          subtitle="پرتکرارترین SKUهای شناسایی‌شده"
          actions={<Link to="/products" className="flex items-center gap-1 text-xs font-medium text-brand hover:underline">همه محصولات <ArrowLeft className="h-3 w-3" /></Link>}
        >
          <div className="space-y-3">
            {top.map((r, i) => (
              <div key={r.product.id} className="flex items-center gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-bold text-muted-foreground">{toFa(i + 1)}</span>
                <ProductImage product={r.product} size={36} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-foreground">{r.product.brand} — {r.product.flavor}</p>
                  <p className="truncate text-[10px] text-muted-foreground">{r.product.sku} · {r.product.size}</p>
                </div>
                <div className="text-left">
                  <p className="text-xs font-bold text-foreground">{toFa(r.count)}</p>
                  <p className="text-[10px] text-muted-foreground">{toFa(r.stores)} فروشگاه</p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>

        <SectionCard title="پوشش بازار" subtitle="درصد فروشگاه‌های پایش‌شده دارای هر برند" help="نسبت تعداد فروشگاه‌های حاوی برند به کل فروشگاه‌های پایش‌شده">
          <div className="space-y-4">
            {coverage.map((c) => (
              <div key={c.brand}>
                <div className="mb-1.5 flex items-center justify-between text-xs">
                  <span className="font-medium text-foreground">{c.brand}</span>
                  <span className="text-muted-foreground">{toFa(c.stores)} فروشگاه · <span className="font-semibold text-foreground">{faPct(c.coverage)}</span></span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full transition-all duration-500" style={{ width: `${c.coverage}%`, backgroundColor: c.color }} />
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}