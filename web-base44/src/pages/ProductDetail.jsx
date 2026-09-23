import React, { useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Eye, Store, MapPin, Percent, Activity, Trophy } from 'lucide-react';
import { productDetail, mapPoints, storeById } from '@/lib/mockData';
import SectionCard from '@/components/SectionCard';
import KpiCard from '@/components/KpiCard';
import ProductImage from '@/components/ProductImage';
import StatusBadge from '@/components/StatusBadge';
import TrendArea from '@/components/charts/TrendArea';
import DistributionMap from '@/components/DistributionMap';
import EmptyState from '@/components/EmptyState';
import { toFa, faPct, faDate, faDateLong } from '@/lib/format';

export default function ProductDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const detail = useMemo(() => productDetail(id), [id]);

  if (!detail) {
    return <EmptyState title="محصول یافت نشد" description="محصول موردنظر وجود ندارد." action={<Link to="/products" className="text-brand">بازگشت به محصولات</Link>} />;
  }

  const { product, storeCoverage, totalDetections, sos, trend, competitors, recent, status, geoPoints, lastSeen } = detail;
  const points = mapPoints({ sku: product.sku });
  const trendLabels = trend.map((_, i) => `${toFa(12 - i)} هفته`);

  return (
    <div className="space-y-5">
      <button onClick={() => navigate('/products')} className="flex items-center gap-1 text-xs text-muted-foreground transition hover:text-foreground">
        <ArrowRight className="h-3.5 w-3.5" /> بازگشت به محصولات
      </button>

      {/* Header */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <ProductImage product={product} size={72} />
          <div className="flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-bold text-foreground">{product.brand} — {product.flavor}</h2>
              <StatusBadge status={status} />
            </div>
            <p className="mt-1 font-mono text-xs text-muted-foreground ltr-nums">{product.sku} · {product.size}</p>
            <p className="mt-1 text-xs text-muted-foreground">آخرین مشاهده: {faDateLong(lastSeen)}</p>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="کل مشاهدات" value={totalDetections} icon={Eye} accent />
        <KpiCard label="فروشگاه‌های دارای محصول" value={storeCoverage} icon={Store} />
        <KpiCard label="پوشش جغرافیایی" value={geoPoints.length} unit="منطقه" icon={MapPin} />
        <KpiCard label="سهم قفسه" value={sos} format="pct" icon={Percent} />
      </div>

      {/* Map + trend */}
      <div className="grid gap-4 lg:grid-cols-3">
        <SectionCard title="موقعیت جغرافیایی" subtitle="فروشگاه‌هایی که این محصول در آن‌ها مشاهده شده" className="lg:col-span-2">
          <DistributionMap points={points} mode="store" height={360} onSelectStore={(s) => navigate(`/stores/${s.id}`)} />
        </SectionCard>
        <SectionCard title="روند توزیع" subtitle="تغییرات هفتگی تعداد مشاهدات">
          <TrendArea labels={trendLabels} series={[{ name: 'مشاهدات', color: product.color, data: trend }]} single height={300} />
        </SectionCard>
      </div>

      {/* Competitors + recent */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="رقبا در کنار این محصول" subtitle="محصولاتی که اغلب در همان قفسه‌ها مشاهده می‌شوند" help="محصولاتی که بیشترین هم‌مشاهده با این محصول در فروشگاه‌های یکسان را دارند.">
          <div className="space-y-2.5">
            {competitors.length ? competitors.map((c) => (
              <div key={c.product.id} className="flex items-center gap-3 rounded-lg border border-border p-2.5">
                <ProductImage product={c.product} size={36} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-foreground">{c.product.brand} — {c.product.flavor}</p>
                  <p className="truncate text-[10px] text-muted-foreground">{c.product.sku}</p>
                </div>
                <div className="text-left">
                  <p className="text-xs font-bold text-foreground">{toFa(c.stores)}</p>
                  <p className="text-[10px] text-muted-foreground">فروشگاه مشترک</p>
                </div>
              </div>
            )) : <EmptyState title="رقبی یافت نشد" />}
          </div>
        </SectionCard>

        <SectionCard title="مشاهدات اخیر" subtitle="آخرین بازرسی‌های این محصول">
          <div className="space-y-2">
            {recent.map((o) => {
              const s = storeById[o.store_id];
              return (
                <div key={o.id} className="flex items-center justify-between rounded-lg border border-border p-2.5 text-xs">
                  <div className="flex items-center gap-2">
                    <Store className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="font-medium text-foreground">{s?.name}</span>
                  </div>
                  <div className="flex items-center gap-3 text-muted-foreground">
                    <span>{toFa(o.detected_count)} facing</span>
                    <span>{faDate(o.observed_at)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}