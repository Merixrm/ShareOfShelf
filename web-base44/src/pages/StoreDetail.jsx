import React, { useMemo } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ArrowRight, Store, Package, Eye, Calendar, MapPin, Crown, Sparkles } from 'lucide-react';
import { storeDetail, mapPoints, nearbyStores, productById } from '@/lib/mockData';
import SectionCard from '@/components/SectionCard';
import KpiCard from '@/components/KpiCard';
import ProductImage from '@/components/ProductImage';
import StatusBadge from '@/components/StatusBadge';
import DistributionMap from '@/components/DistributionMap';
import EmptyState from '@/components/EmptyState';
import { toFa, faPct, faDate, faDateLong } from '@/lib/format';

export default function StoreDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const detail = useMemo(() => storeDetail(id), [id]);

  const points = useMemo(() => {
    if (!detail) return [];
    const all = mapPoints({});
    const nearby = nearbyStores(id, 8, 4).map((s) => s.id);
    const ids = new Set([id, ...nearby]);
    return all.filter((p) => ids.has(p.store.id));
  }, [detail, id]);

  if (!detail) {
    return <EmptyState title="فروشگاه یافت نشد" action={<Link to="/stores" className="text-brand">بازگشت</Link>} />;
  }

  const { store, products, brands, observationCount, lastInspection, sosByBrand, dominant, missing, opportunities } = detail;

  return (
    <div className="space-y-5">
      <button onClick={() => navigate('/stores')} className="flex items-center gap-1 text-xs text-muted-foreground transition hover:text-foreground">
        <ArrowRight className="h-3.5 w-3.5" /> بازگشت به فروشگاه‌ها
      </button>

      {/* Header */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground"><Store className="h-6 w-6" /></div>
            <div>
              <h2 className="text-lg font-bold text-foreground">{store.name}</h2>
              <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground"><MapPin className="h-3 w-3" /> {store.address}</p>
            </div>
          </div>
          <div className="text-left">
            <p className="text-[10px] text-muted-foreground">برند غالب</p>
            <p className="flex items-center gap-1.5 font-bold text-foreground">
              <Crown className="h-4 w-4 text-warning" /> {dominant}
            </p>
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiCard label="محصولات شناسایی‌شده" value={products.length} icon={Package} accent />
        <KpiCard label="برندهای موجود" value={brands.length} icon={Store} />
        <KpiCard label="کل مشاهدات" value={observationCount} icon={Eye} />
        <KpiCard label="آخرین بازرسی" value={lastInspection ? faDateLong(lastInspection) : '—'} icon={Calendar} format="raw" />
      </div>

      {/* Map + SoS */}
      <div className="grid gap-4 lg:grid-cols-3">
        <SectionCard title="موقعیت فروشگاه" subtitle="فروشگاه و فروشگاه‌های مجاور" className="lg:col-span-2">
          <DistributionMap points={points} mode="store" height={360} center={[store.latitude, store.longitude]} zoom={14} onSelectStore={(s) => navigate(`/stores/${s.id}`)} />
        </SectionCard>
        <SectionCard title="سهم قفسه بر اساس برند" subtitle="در این فروشگاه">
          <div className="space-y-3">
            {sosByBrand.map((r) => (
              <div key={r.brand}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1.5 font-medium text-foreground">
                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: r.color }} />{r.brand}
                  </span>
                  <span className="font-semibold text-foreground">{faPct(r.facingsPct)}</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full" style={{ width: `${r.facingsPct}%`, backgroundColor: r.color }} />
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>

      {/* Opportunities + missing */}
      <div className="grid gap-4 lg:grid-cols-2">
        <SectionCard title="فرصت‌های توزیع" subtitle="محصولاتی که در فروشگاه‌های مجاور پرفروش‌اند اما در این فروشگاه نیستند" help="محصولاتی که در فروشگاه‌های نزدیک به‌وفور دیده می‌شوند ولی در این فروشگاه حضور ندارند — فرصت توزیع.">
          <div className="space-y-2.5">
            {opportunities.length ? opportunities.map((o) => (
              <div key={o.product.id} className="flex items-center gap-3 rounded-lg border border-warning/30 bg-warning/5 p-2.5">
                <ProductImage product={o.product} size={36} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-semibold text-foreground">{o.product.brand} — {o.product.flavor}</p>
                  <p className="truncate text-[10px] text-muted-foreground">{o.product.sku} · {o.product.size}</p>
                </div>
                <div className="flex items-center gap-1 rounded-full bg-warning/15 px-2 py-1 text-[10px] font-medium text-warning">
                  <Sparkles className="h-3 w-3" /> {toFa(o.nearbyCount)} مشاهده مجاور
                </div>
              </div>
            )) : <EmptyState title="فرصت مشخصی یافت نشد" description="این فروشگاه پوشش خوبی دارد." />}
          </div>
        </SectionCard>

        <SectionCard title="محصولات مفقود" subtitle="محصولات برندهای حاضر که در این فروشگاه نیستند">
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            {missing.slice(0, 9).map((p) => (
              <div key={p.id} className="flex flex-col items-center gap-1.5 rounded-lg border border-border p-2 text-center">
                <ProductImage product={p} size={32} />
                <p className="text-[10px] font-medium text-foreground">{p.flavor}</p>
                <p className="text-[9px] text-muted-foreground">{p.size}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}